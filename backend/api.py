"""
FastAPI backend for the Big-Little Matching Algorithm.
Exposes the matching logic from big_little_matching.py over HTTP.

Endpoints:
  POST /api/match       — run the full algorithm, return matches + scores
  POST /api/parse-csv   — parse an uploaded CSV, return structured person list
"""

import io
import math
import sys
import os

# Allow importing big_little_matching.py from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from big_little_matching import (
    PREF_COLS,
    build_preference_lists,
    compute_satisfaction,
    optimize_matching,
    select_trio,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Big-Little Matching API")

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class Person(BaseModel):
    name: str
    preferences: list[str]  # up to 5 names, in ranked order


class MatchRequest(BaseModel):
    freshmen: list[Person]
    sophomores: list[Person]


class Match(BaseModel):
    freshman: str
    big_1: str
    big_2: str | None
    trio: bool


class SatisfactionRow(BaseModel):
    freshman: str
    big_1: str
    big_2: str | None
    freshman_score: float
    big_1_score: float
    big_2_score: float | None
    pair_score: float


class Summary(BaseModel):
    median_pair_score: float
    average_pair_score: float
    mutual_count: int  # pairs where both sides scored >= 80%


class MatchResponse(BaseModel):
    matches: list[Match]
    satisfaction: list[SatisfactionRow]
    summary: Summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_prefs_dict(people: list[Person]) -> dict[str, list[str]]:
    """Convert list of Person models to the {name: [ranked names]} dict."""
    return {p.name: p.preferences for p in people}


def _df_to_pref_list(df: pd.DataFrame) -> list[dict]:
    """Convert a loaded CSV DataFrame to a list of {name, preferences} dicts."""
    result = []
    for _, row in df.iterrows():
        prefs = [
            str(row[col]).strip()
            for col in PREF_COLS
            if col in df.columns and str(row[col]).strip() not in ("", "nan")
        ]
        result.append({"name": str(row["Name"]).strip(), "preferences": prefs})
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/match", response_model=MatchResponse)
def run_match(req: MatchRequest) -> MatchResponse:
    """Run the full matching algorithm and return results."""
    freshmen_names = [p.name for p in req.freshmen]
    sophomores_names = [p.name for p in req.sophomores]

    n_fresh = len(freshmen_names)
    n_sophs = len(sophomores_names)

    if n_sophs - n_fresh != 1:
        raise HTTPException(
            status_code=400,
            detail=f"Expected exactly 1 more sophomore than freshman "
                   f"(got {n_fresh} freshmen, {n_sophs} sophomores).",
        )

    fresh_prefs = _build_prefs_dict(req.freshmen)
    soph_prefs = _build_prefs_dict(req.sophomores)

    # Validate that preference names exist in the other group's roster
    fresh_set = set(freshmen_names)
    soph_set = set(sophomores_names)
    for p in req.freshmen:
        bad = [n for n in p.preferences if n not in soph_set]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"Freshman '{p.name}' has unknown sophomore(s) in preferences: {bad}",
            )
    for p in req.sophomores:
        bad = [n for n in p.preferences if n not in fresh_set]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"Sophomore '{p.name}' has unknown freshman in preferences: {bad}",
            )

    # Select trio
    trio_fresh, trio_big1, trio_big2 = select_trio(
        freshmen_names, sophomores_names, fresh_prefs, soph_prefs
    )

    # Remove trio from pool
    remaining_freshmen = [f for f in freshmen_names if f != trio_fresh]
    remaining_sophs = [s for s in sophomores_names if s not in {trio_big1, trio_big2}]

    # Optimise 1-to-1 matching
    gs_matches = optimize_matching(
        remaining_freshmen, remaining_sophs, fresh_prefs, soph_prefs
    )

    # Compute satisfaction DataFrame
    sat_df = compute_satisfaction(
        gs_matches, trio_fresh, (trio_big1, trio_big2), fresh_prefs, soph_prefs
    )

    # Build match list (sorted by freshman name)
    matches_out: list[Match] = []
    for fresh, soph in sorted(gs_matches.items()):
        matches_out.append(Match(freshman=fresh, big_1=soph, big_2=None, trio=False))
    matches_out.append(
        Match(freshman=trio_fresh, big_1=trio_big1, big_2=trio_big2, trio=True)
    )
    matches_out.sort(key=lambda m: m.freshman)

    # Build satisfaction list
    sat_out: list[SatisfactionRow] = []
    for _, row in sat_df.iterrows():
        big2_score = row["Big_2_Score"]
        sat_out.append(
            SatisfactionRow(
                freshman=row["Freshman"],
                big_1=row["Big_1"],
                big_2=row["Big_2"] if row["Big_2"] else None,
                freshman_score=row["Freshman_Score"],
                big_1_score=row["Big_1_Score"],
                big_2_score=None if (big2_score is None or (isinstance(big2_score, float) and math.isnan(big2_score))) else big2_score,
                pair_score=row["Pair_Score"],
            )
        )

    # Build summary
    pair_scores = sat_df["Pair_Score"].sort_values().reset_index(drop=True)
    median = float(pair_scores.iloc[len(pair_scores) // 2])
    average = float(pair_scores.mean())
    mutual_count = int(
        ((sat_df["Freshman_Score"] >= 80) & (sat_df["Big_1_Score"] >= 80)).sum()
    )

    return MatchResponse(
        matches=matches_out,
        satisfaction=sat_out,
        summary=Summary(
            median_pair_score=round(median, 1),
            average_pair_score=round(average, 1),
            mutual_count=mutual_count,
        ),
    )


@app.post("/api/parse-csv")
def parse_csv(file: UploadFile = File(...)) -> list[dict]:
    """
    Parse an uploaded CSV (Name, Rank1-5) and return a list of
    {name, preferences} objects ready for the match endpoint.
    """
    try:
        contents = file.file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")

    df.columns = [c.strip() for c in df.columns]
    if "Name" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must have a 'Name' column.")
    missing_pref = [c for c in PREF_COLS if c not in df.columns]
    if missing_pref:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing preference columns: {missing_pref}",
        )

    df["Name"] = df["Name"].astype(str).str.strip()
    for col in PREF_COLS:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

    return _df_to_pref_list(df)
