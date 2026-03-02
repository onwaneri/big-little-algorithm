"""
FastAPI backend for the Big-Little Matching Algorithm.

Endpoints:
  POST /api/match             — run the full algorithm, return matches + scores
  POST /api/parse-csv         — parse a participants CSV (Name, Rank1-5)
  POST /api/parse-overrides-csv — parse an overrides CSV (Freshman_1, Freshman_2, Big_1, Big_2)
"""

import io
import math
import sys
import os
from typing import Literal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from big_little_matching import (
    PREF_COLS,
    build_preference_lists,
    compute_satisfaction,
    optimize_matching,
    remove_from_prefs,
    select_trios,
    select_twin_trios,
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
    preferences: list[str]


class OverrideMatch(BaseModel):
    freshman_1: str
    freshman_2: str | None = None   # populated for 2-little trios
    big_1: str
    big_2: str | None = None        # populated for 2-big trios


class TwinPair(BaseModel):
    person_1: str
    person_2: str
    group: Literal["sophomore", "freshman"]


class BannedPair(BaseModel):
    freshman: str
    sophomore: str


class MatchRequest(BaseModel):
    freshmen: list[Person]
    sophomores: list[Person]
    overrides: list[OverrideMatch] = []
    twins: list[TwinPair] = []
    banned: list[BannedPair] = []


class Match(BaseModel):
    freshman: str
    freshman_2: str | None = None
    big_1: str
    big_2: str | None = None
    trio: bool


class SatisfactionRow(BaseModel):
    freshman: str
    freshman_2: str | None = None
    big_1: str
    big_2: str | None = None
    freshman_score: float
    freshman_2_score: float | None = None
    big_1_score: float
    big_2_score: float | None = None
    pair_score: float


class Summary(BaseModel):
    median_pair_score: float
    average_pair_score: float
    mutual_count: int


class MatchResponse(BaseModel):
    matches: list[Match]
    satisfaction: list[SatisfactionRow]
    summary: Summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_prefs_dict(people: list[Person]) -> dict[str, list[str]]:
    return {p.name: p.preferences for p in people}


def _df_to_pref_list(df: pd.DataFrame) -> list[dict]:
    result = []
    for _, row in df.iterrows():
        prefs = [
            str(row[col]).strip()
            for col in PREF_COLS
            if col in df.columns and str(row[col]).strip() not in ("", "nan")
        ]
        result.append({"name": str(row["Name"]).strip(), "preferences": prefs})
    return result


def _nan_to_none(val) -> float | None:
    if val is None:
        return None
    try:
        if math.isnan(float(val)):
            return None
    except (TypeError, ValueError):
        return None
    return float(val)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/match", response_model=MatchResponse)
def run_match(req: MatchRequest) -> MatchResponse:
    """Run the full matching algorithm and return results."""
    freshmen_names   = [p.name for p in req.freshmen]
    sophomores_names = [p.name for p in req.sophomores]
    fresh_set = set(freshmen_names)
    soph_set  = set(sophomores_names)

    if not freshmen_names or not sophomores_names:
        raise HTTPException(status_code=400, detail="Need at least one freshman and one sophomore.")

    # Validate preference names reference the correct group
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

    # Validate override names
    for ov in req.overrides:
        if ov.freshman_1 not in fresh_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.freshman_1}' not in freshmen roster.")
        if ov.freshman_2 and ov.freshman_2 not in fresh_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.freshman_2}' not in freshmen roster.")
        if ov.big_1 not in soph_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.big_1}' not in sophomores roster.")
        if ov.big_2 and ov.big_2 not in soph_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.big_2}' not in sophomores roster.")
        if ov.freshman_2 and ov.big_2:
            raise HTTPException(
                status_code=400,
                detail="Override cannot have both freshman_2 and big_2 set simultaneously.",
            )

    fresh_prefs = _build_prefs_dict(req.freshmen)
    soph_prefs  = _build_prefs_dict(req.sophomores)
    # Save originals for satisfaction scoring (removal operations return new dicts)
    orig_fresh_prefs = fresh_prefs
    orig_soph_prefs  = soph_prefs

    # Collect overridden members and remove from pools / preference lists
    overridden_fresh = set()
    overridden_soph  = set()
    for ov in req.overrides:
        overridden_fresh.add(ov.freshman_1)
        if ov.freshman_2:
            overridden_fresh.add(ov.freshman_2)
        overridden_soph.add(ov.big_1)
        if ov.big_2:
            overridden_soph.add(ov.big_2)

    all_override_names = overridden_fresh | overridden_soph
    fresh_prefs = remove_from_prefs(fresh_prefs, all_override_names)
    soph_prefs  = remove_from_prefs(soph_prefs,  all_override_names)

    fresh_pool = [f for f in freshmen_names   if f not in overridden_fresh]
    soph_pool  = [s for s in sophomores_names if s not in overridden_soph]

    # Validate and process twin pairs
    for tw in req.twins:
        if tw.person_1 == tw.person_2:
            raise HTTPException(status_code=400, detail=f"Twin pair cannot list the same person twice: '{tw.person_1}'.")
        if tw.group == "sophomore":
            for p in (tw.person_1, tw.person_2):
                if p not in soph_set:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' not in sophomores roster.")
                if p in overridden_soph:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' is already locked in an override.")
        else:
            for p in (tw.person_1, tw.person_2):
                if p not in fresh_set:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' not in freshmen roster.")
                if p in overridden_fresh:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' is already locked in an override.")

    soph_twin_pairs  = [(t.person_1, t.person_2) for t in req.twins if t.group == "sophomore"]
    fresh_twin_pairs = [(t.person_1, t.person_2) for t in req.twins if t.group == "freshman"]

    # Validate and process banned pairs
    for ban in req.banned:
        if ban.freshman not in fresh_set:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.freshman}' not in freshmen roster.")
        if ban.sophomore not in soph_set:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.sophomore}' not in sophomores roster.")
        if ban.freshman in overridden_fresh:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.freshman}' is already locked in an override.")
        if ban.sophomore in overridden_soph:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.sophomore}' is already locked in an override.")

    # Remove banned pairs from preference lists
    banned_set = {(ban.freshman, ban.sophomore) for ban in req.banned}
    for freshman, prefs in fresh_prefs.items():
        fresh_prefs[freshman] = [s for s in prefs if (freshman, s) not in banned_set]
    for sophomore, prefs in soph_prefs.items():
        soph_prefs[sophomore] = [f for f in prefs if (f, sophomore) not in banned_set]

    try:
        twin_trios_2bigs, twin_trios_2littles, fresh_pool, soph_pool, fresh_prefs, soph_prefs = (
            select_twin_trios(soph_twin_pairs, fresh_twin_pairs, fresh_pool, soph_pool, fresh_prefs, soph_prefs)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Select remaining trios based on D
    D = len(soph_pool) - len(fresh_pool)
    trios_2bigs, trios_2littles = select_trios(D, fresh_pool, soph_pool, fresh_prefs, soph_prefs)

    # Remove trio members and run 1-to-1 matching
    trio_fresh_used = (
        {f for f, _, _ in trios_2bigs}
        | {f1 for f1, _, _ in trios_2littles}
        | {f2 for _, f2, _ in trios_2littles}
    )
    trio_soph_used = (
        {b1 for _, b1, _ in trios_2bigs}
        | {b2 for _, _, b2 in trios_2bigs}
        | {s for _, _, s in trios_2littles}
    )
    remaining_fresh = [f for f in fresh_pool if f not in trio_fresh_used]
    remaining_soph  = [s for s in soph_pool  if s not in trio_soph_used]

    duo_matches = optimize_matching(remaining_fresh, remaining_soph, fresh_prefs, soph_prefs)

    # Incorporate overrides into result sets
    override_trios_2bigs:    list[tuple[str, str, str]] = []
    override_trios_2littles: list[tuple[str, str, str]] = []
    override_duos: dict[str, str] = {}
    for ov in req.overrides:
        if ov.freshman_2:
            override_trios_2littles.append((ov.freshman_1, ov.freshman_2, ov.big_1))
        elif ov.big_2:
            override_trios_2bigs.append((ov.freshman_1, ov.big_1, ov.big_2))
        else:
            override_duos[ov.freshman_1] = ov.big_1

    all_duos         = {**duo_matches, **override_duos}
    all_trios_2bigs  = twin_trios_2bigs  + trios_2bigs  + override_trios_2bigs
    all_trios_2lit   = twin_trios_2littles + trios_2littles + override_trios_2littles

    # Compute satisfaction using original (unfiltered) prefs so scores are accurate
    sat_df = compute_satisfaction(
        all_duos, all_trios_2bigs, all_trios_2lit, orig_fresh_prefs, orig_soph_prefs
    )

    # Build match list
    matches_out: list[Match] = []
    for fresh, soph in all_duos.items():
        matches_out.append(Match(freshman=fresh, freshman_2=None, big_1=soph, big_2=None, trio=False))
    for fresh, b1, b2 in all_trios_2bigs:
        matches_out.append(Match(freshman=fresh, freshman_2=None, big_1=b1, big_2=b2, trio=True))
    for f1, f2, soph in all_trios_2lit:
        matches_out.append(Match(freshman=f1, freshman_2=f2, big_1=soph, big_2=None, trio=True))
    matches_out.sort(key=lambda m: m.freshman)

    # Build satisfaction list
    sat_out: list[SatisfactionRow] = []
    for _, row in sat_df.iterrows():
        sat_out.append(
            SatisfactionRow(
                freshman=row["Freshman_1"],
                freshman_2=None if pd.isna(row["Freshman_2"]) else str(row["Freshman_2"]),
                big_1=row["Big_1"],
                big_2=None if pd.isna(row["Big_2"]) else str(row["Big_2"]),
                freshman_score=row["Freshman_1_Score"],
                freshman_2_score=_nan_to_none(row["Freshman_2_Score"]),
                big_1_score=row["Big_1_Score"],
                big_2_score=_nan_to_none(row["Big_2_Score"]),
                pair_score=row["Pair_Score"],
            )
        )

    # Build summary
    pair_scores  = sat_df["Pair_Score"].sort_values().reset_index(drop=True)
    median_score = float(pair_scores.iloc[len(pair_scores) // 2])
    avg_score    = float(pair_scores.mean())

    # Mutual = both primary parties scored >= 80%
    mutual_mask = (sat_df["Freshman_1_Score"] >= 80) & (sat_df["Big_1_Score"] >= 80)
    mutual_count = int(mutual_mask.sum())

    return MatchResponse(
        matches=matches_out,
        satisfaction=sat_out,
        summary=Summary(
            median_pair_score=round(median_score, 1),
            average_pair_score=round(avg_score, 1),
            mutual_count=mutual_count,
        ),
    )


@app.post("/api/parse-csv")
def parse_csv(file: UploadFile = File(...)) -> list[dict]:
    """
    Parse a participants CSV and return structured person list.
    Accepts two formats:
      - Standard: columns Name, Rank1, Rank2, Rank3, Rank4, Rank5
      - Google Form: columns Timestamp, Name, <First choice [of big]>, <Second choice [of big]>, ...
        (Timestamp is dropped; preference columns are detected by the prefix "First choice")
    """
    try:
        contents = file.file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")

    df.columns = [c.strip() for c in df.columns]

    # Auto-detect Google Form format: has "Timestamp" column or preference cols start with "First choice"
    is_form_format = "Timestamp" in df.columns or any(
        c.startswith("First choice") for c in df.columns
    )

    if is_form_format:
        # Drop Timestamp
        if "Timestamp" in df.columns:
            df = df.drop(columns=["Timestamp"])

        # All remaining columns after "Name" are the preference columns (in form order)
        other_cols = [c for c in df.columns if c != "Name"]
        if len(other_cols) < 5:
            raise HTTPException(
                status_code=400,
                detail=f"Google Form CSV must have at least 5 preference columns after 'Name'; found {len(other_cols)}.",
            )
        rename_map = {old: new for old, new in zip(other_cols[:5], PREF_COLS)}
        df = df.rename(columns=rename_map)

    if "Name" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must have a 'Name' column.")
    missing_pref = [c for c in PREF_COLS if c not in df.columns]
    if missing_pref:
        raise HTTPException(status_code=400, detail=f"CSV is missing preference columns: {missing_pref}")

    df["Name"] = df["Name"].astype(str).str.strip()
    # Drop rows with blank/nan Name (non-submitters will still be included as long as Name is set)
    df = df[df["Name"].notna() & (df["Name"] != "") & (df["Name"] != "nan")]
    for col in PREF_COLS:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

    return _df_to_pref_list(df)


@app.post("/api/parse-overrides-csv")
def parse_overrides_csv(file: UploadFile = File(...)) -> list[dict]:
    """
    Parse an overrides CSV with columns: Freshman_1, Freshman_2, Big_1, Big_2
    (Freshman_2 and Big_2 may be empty). Returns list of OverrideMatch dicts.
    """
    try:
        contents = file.file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")

    df.columns = [c.strip() for c in df.columns]
    if "Freshman_1" not in df.columns or "Big_1" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail="Overrides CSV must have at minimum 'Freshman_1' and 'Big_1' columns.",
        )
    for col in ["Freshman_2", "Big_2"]:
        if col not in df.columns:
            df[col] = ""
    # normalization helper (shared with main algorithm)
    def _normalize_name(val: str) -> str:
        s = str(val).strip()
        s = " ".join(s.split())
        return s.title()

    for col in ["Freshman_1", "Freshman_2", "Big_1", "Big_2"]:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")
        df[col] = df[col].apply(_normalize_name)

    result = []
    for _, row in df.iterrows():
        f2 = row["Freshman_2"] or None
        b2 = row["Big_2"] or None
        if f2 and b2:
            raise HTTPException(
                status_code=400,
                detail=f"Override row cannot have both Freshman_2 and Big_2 set.",
            )
        result.append({
            "freshman_1": row["Freshman_1"],
            "freshman_2": f2,
            "big_1": row["Big_1"],
            "big_2": b2,
        })
    return result


# ---------------------------------------------------------------------------
# Serve React frontend (production — only if dist/ exists)
# ---------------------------------------------------------------------------
_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(_dist):
    # Serve compiled JS/CSS assets under /assets — never conflicts with /api/*
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    # Catch-all: serve index.html for every non-API path so React Router works.
    # This route is registered LAST, so all /api/* routes above take priority.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(os.path.join(_dist, "index.html"))
