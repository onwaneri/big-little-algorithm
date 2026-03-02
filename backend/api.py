"""
FastAPI backend for the Big-Little Matching Algorithm.

Endpoints:
  POST /api/match             — run the full algorithm, return matches + scores
  POST /api/parse-csv         — parse a participants CSV (Name, Rank1-RankN)
  POST /api/parse-overrides-csv — parse an overrides CSV (Little_1, Little_2, Big_1, Big_2)
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
    little_1: str
    little_2: str | None = None   # populated for 2-little trios
    big_1: str
    big_2: str | None = None      # populated for 2-big trios


class TwinPair(BaseModel):
    person_1: str
    person_2: str
    group: Literal["big", "little"]


class BannedPair(BaseModel):
    little: str
    big: str


class MatchRequest(BaseModel):
    littles: list[Person]
    bigs: list[Person]
    overrides: list[OverrideMatch] = []
    twins: list[TwinPair] = []
    banned: list[BannedPair] = []
    big_weight: float = 0.5                  # 0 = favor littles, 1 = favor bigs
    every_big_needs_little: bool = True      # if False, surplus bigs go unmatched
    every_little_needs_big: bool = True      # if False, surplus littles go unmatched
    num_preferences: int = 5                 # max preferences submitted (used as max_rank)


class Match(BaseModel):
    little: str
    little_2: str | None = None
    big_1: str
    big_2: str | None = None
    trio: bool


class SatisfactionRow(BaseModel):
    little: str
    little_2: str | None = None
    big_1: str
    big_2: str | None = None
    little_score: float | None = None
    little_2_score: float | None = None
    big_1_score: float | None = None
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
    unmatched_bigs: list[str] = []
    unmatched_littles: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_prefs_dict(people: list[Person]) -> dict[str, list[str]]:
    return {p.name: p.preferences for p in people}


def _rank_cols_from_df(df: pd.DataFrame) -> list[str]:
    """Return sorted RankN columns present in df."""
    cols = [c for c in df.columns if c.startswith("Rank") and c[4:].isdigit()]
    return sorted(cols, key=lambda c: int(c[4:]))


def _df_to_pref_list(df: pd.DataFrame) -> list[dict]:
    rank_cols = _rank_cols_from_df(df)
    result = []
    for _, row in df.iterrows():
        prefs = [
            str(row[col]).strip()
            for col in rank_cols
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
    littles_names = [p.name for p in req.littles]
    bigs_names    = [p.name for p in req.bigs]
    little_set = set(littles_names)
    big_set    = set(bigs_names)

    if not littles_names or not bigs_names:
        raise HTTPException(status_code=400, detail="Need at least one little and one big.")

    # Validate preference names reference the correct group
    for p in req.littles:
        bad = [n for n in p.preferences if n not in big_set]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"Little '{p.name}' has unknown big(s) in preferences: {bad}",
            )
    for p in req.bigs:
        bad = [n for n in p.preferences if n not in little_set]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"Big '{p.name}' has unknown little(s) in preferences: {bad}",
            )

    # Validate override names
    for ov in req.overrides:
        if ov.little_1 not in little_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.little_1}' not in littles roster.")
        if ov.little_2 and ov.little_2 not in little_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.little_2}' not in littles roster.")
        if ov.big_1 not in big_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.big_1}' not in bigs roster.")
        if ov.big_2 and ov.big_2 not in big_set:
            raise HTTPException(status_code=400, detail=f"Override: '{ov.big_2}' not in bigs roster.")
        if ov.little_2 and ov.big_2:
            raise HTTPException(
                status_code=400,
                detail="Override cannot have both little_2 and big_2 set simultaneously.",
            )

    little_prefs = _build_prefs_dict(req.littles)
    big_prefs    = _build_prefs_dict(req.bigs)
    # Save originals for satisfaction scoring
    orig_little_prefs = little_prefs
    orig_big_prefs    = big_prefs

    # Collect overridden members and remove from pools / preference lists
    overridden_littles = set()
    overridden_bigs    = set()
    for ov in req.overrides:
        overridden_littles.add(ov.little_1)
        if ov.little_2:
            overridden_littles.add(ov.little_2)
        overridden_bigs.add(ov.big_1)
        if ov.big_2:
            overridden_bigs.add(ov.big_2)

    all_override_names = overridden_littles | overridden_bigs
    little_prefs = remove_from_prefs(little_prefs, all_override_names)
    big_prefs    = remove_from_prefs(big_prefs,    all_override_names)

    little_pool = [l for l in littles_names if l not in overridden_littles]
    big_pool    = [b for b in bigs_names    if b not in overridden_bigs]

    # Validate and process twin pairs
    for tw in req.twins:
        if tw.person_1 == tw.person_2:
            raise HTTPException(status_code=400, detail=f"Twin pair cannot list the same person twice: '{tw.person_1}'.")
        if tw.group == "big":
            for p in (tw.person_1, tw.person_2):
                if p not in big_set:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' not in bigs roster.")
                if p in overridden_bigs:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' is already locked in an override.")
        else:
            for p in (tw.person_1, tw.person_2):
                if p not in little_set:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' not in littles roster.")
                if p in overridden_littles:
                    raise HTTPException(status_code=400, detail=f"Twin: '{p}' is already locked in an override.")

    big_twin_pairs    = [(t.person_1, t.person_2) for t in req.twins if t.group == "big"]
    little_twin_pairs = [(t.person_1, t.person_2) for t in req.twins if t.group == "little"]

    # Validate and process banned pairs
    for ban in req.banned:
        if ban.little not in little_set:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.little}' not in littles roster.")
        if ban.big not in big_set:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.big}' not in bigs roster.")
        if ban.little in overridden_littles:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.little}' is already locked in an override.")
        if ban.big in overridden_bigs:
            raise HTTPException(status_code=400, detail=f"Banned pair: '{ban.big}' is already locked in an override.")

    # Remove banned pairs from preference lists
    banned_set = {(ban.little, ban.big) for ban in req.banned}
    for little, prefs in little_prefs.items():
        little_prefs[little] = [b for b in prefs if (little, b) not in banned_set]
    for big, prefs in big_prefs.items():
        big_prefs[big] = [l for l in prefs if (l, big) not in banned_set]

    try:
        twin_trios_2bigs, twin_trios_2littles, little_pool, big_pool, little_prefs, big_prefs = (
            select_twin_trios(big_twin_pairs, little_twin_pairs, little_pool, big_pool, little_prefs, big_prefs)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Compute D and decide whether to create trios
    D = len(big_pool) - len(little_pool)

    # If config says not to force everyone matched, truncate to equal sizes
    unmatched_bigs: list[str] = []
    unmatched_littles: list[str] = []
    if D > 0 and not req.every_big_needs_little:
        # Leave D bigs unmatched — trim big pool to match little pool size
        unmatched_bigs = big_pool[len(little_pool):]
        big_pool = big_pool[:len(little_pool)]
        D = 0
    elif D < 0 and not req.every_little_needs_big:
        # Leave |D| littles unmatched — trim little pool to match big pool size
        unmatched_littles = little_pool[len(big_pool):]
        little_pool = little_pool[:len(big_pool)]
        D = 0

    trios_2bigs, trios_2littles = select_trios(D, little_pool, big_pool, little_prefs, big_prefs)

    # Remove trio members and run 1-to-1 matching
    trio_littles_used = (
        {l for l, _, _ in trios_2bigs}
        | {l1 for l1, _, _ in trios_2littles}
        | {l2 for _, l2, _ in trios_2littles}
    )
    trio_bigs_used = (
        {b1 for _, b1, _ in trios_2bigs}
        | {b2 for _, _, b2 in trios_2bigs}
        | {b for _, _, b in trios_2littles}
    )
    remaining_littles = [l for l in little_pool if l not in trio_littles_used]
    remaining_bigs    = [b for b in big_pool    if b not in trio_bigs_used]

    max_rank = max(req.num_preferences, 1)
    duo_matches = optimize_matching(
        remaining_littles, remaining_bigs, little_prefs, big_prefs,
        big_weight=req.big_weight, max_rank=max_rank,
    )

    # Incorporate overrides into result sets
    override_trios_2bigs:    list[tuple[str, str, str]] = []
    override_trios_2littles: list[tuple[str, str, str]] = []
    override_duos: dict[str, str] = {}
    for ov in req.overrides:
        if ov.little_2:
            override_trios_2littles.append((ov.little_1, ov.little_2, ov.big_1))
        elif ov.big_2:
            override_trios_2bigs.append((ov.little_1, ov.big_1, ov.big_2))
        else:
            override_duos[ov.little_1] = ov.big_1

    all_duos         = {**duo_matches, **override_duos}
    all_trios_2bigs  = twin_trios_2bigs  + trios_2bigs  + override_trios_2bigs
    all_trios_2lit   = twin_trios_2littles + trios_2littles + override_trios_2littles

    # Compute satisfaction using original (unfiltered) prefs so scores are accurate
    sat_df = compute_satisfaction(
        all_duos, all_trios_2bigs, all_trios_2lit,
        orig_little_prefs, orig_big_prefs,
        big_weight=req.big_weight, max_rank=max_rank,
    )

    # Build match list
    matches_out: list[Match] = []
    for little, big in all_duos.items():
        matches_out.append(Match(little=little, little_2=None, big_1=big, big_2=None, trio=False))
    for little, b1, b2 in all_trios_2bigs:
        matches_out.append(Match(little=little, little_2=None, big_1=b1, big_2=b2, trio=True))
    for l1, l2, big in all_trios_2lit:
        matches_out.append(Match(little=l1, little_2=l2, big_1=big, big_2=None, trio=True))

    matches_out.sort(key=lambda m: m.little)

    # Build satisfaction list
    sat_out: list[SatisfactionRow] = []
    for _, row in sat_df.iterrows():
        sat_out.append(
            SatisfactionRow(
                little=row["Little_1"],
                little_2=None if pd.isna(row["Little_2"]) else str(row["Little_2"]),
                big_1=row["Big_1"],
                big_2=None if pd.isna(row["Big_2"]) else str(row["Big_2"]),
                little_score=_nan_to_none(row["Little_1_Score"]),
                little_2_score=_nan_to_none(row["Little_2_Score"]),
                big_1_score=_nan_to_none(row["Big_1_Score"]),
                big_2_score=_nan_to_none(row["Big_2_Score"]),
                pair_score=row["Pair_Score"],
            )
        )

    # Build summary
    pair_scores  = sat_df["Pair_Score"].sort_values().reset_index(drop=True)
    median_score = float(pair_scores.iloc[len(pair_scores) // 2])
    avg_score    = float(pair_scores.mean())

    # Mutual = both primary parties scored >= 80% (only when both submitted prefs)
    l1_scores = sat_df["Little_1_Score"].fillna(-1)
    b1_scores = sat_df["Big_1_Score"].fillna(-1)
    mutual_mask  = (l1_scores >= 80) & (b1_scores >= 80)
    mutual_count = int(mutual_mask.sum())

    return MatchResponse(
        matches=matches_out,
        satisfaction=sat_out,
        summary=Summary(
            median_pair_score=round(median_score, 1),
            average_pair_score=round(avg_score, 1),
            mutual_count=mutual_count,
        ),
        unmatched_bigs=sorted(unmatched_bigs),
        unmatched_littles=sorted(unmatched_littles),
    )


@app.post("/api/parse-csv")
def parse_csv(file: UploadFile = File(...)) -> list[dict]:
    """
    Parse a participants CSV and return structured person list.
    Accepts two formats:
      - Standard: columns Name, Rank1, Rank2, ..., RankN (any N)
      - Google Form: columns Timestamp, Name, <pref col 1>, <pref col 2>, ...
        (Timestamp is dropped; all columns after Name become preferences)
    """
    try:
        contents = file.file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")

    df.columns = [c.strip() for c in df.columns]

    # Auto-detect Google Form format: has "Timestamp" column or no RankN columns
    rank_cols = [c for c in df.columns if c.startswith("Rank") and c[4:].isdigit()]
    is_form_format = "Timestamp" in df.columns or (not rank_cols and "Name" in df.columns)

    if is_form_format:
        # Drop Timestamp
        if "Timestamp" in df.columns:
            df = df.drop(columns=["Timestamp"])

        # All remaining columns after "Name" are the preference columns
        other_cols = [c for c in df.columns if c != "Name"]
        if not other_cols:
            raise HTTPException(
                status_code=400,
                detail="CSV must have at least one preference column after 'Name'.",
            )
        rename_map = {old: f"Rank{i+1}" for i, old in enumerate(other_cols)}
        df = df.rename(columns=rename_map)
        rank_cols = [f"Rank{i+1}" for i in range(len(other_cols))]

    if "Name" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must have a 'Name' column.")

    rank_cols = _rank_cols_from_df(df)
    if not rank_cols:
        raise HTTPException(status_code=400, detail="CSV has no preference columns (Rank1, Rank2, …).")

    df["Name"] = df["Name"].astype(str).str.strip()
    df = df[df["Name"].notna() & (df["Name"] != "") & (df["Name"] != "nan")]
    for col in rank_cols:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

    return _df_to_pref_list(df)


@app.post("/api/parse-overrides-csv")
def parse_overrides_csv(file: UploadFile = File(...)) -> list[dict]:
    """
    Parse an overrides CSV with columns: Little_1, Little_2, Big_1, Big_2
    (Little_2 and Big_2 may be empty). Returns list of OverrideMatch dicts.
    """
    try:
        contents = file.file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}")

    df.columns = [c.strip() for c in df.columns]
    if "Little_1" not in df.columns or "Big_1" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail="Overrides CSV must have at minimum 'Little_1' and 'Big_1' columns.",
        )
    for col in ["Little_2", "Big_2"]:
        if col not in df.columns:
            df[col] = ""

    def _normalize_name(val: str) -> str:
        s = str(val).strip()
        s = " ".join(s.split())
        return s.title()

    for col in ["Little_1", "Little_2", "Big_1", "Big_2"]:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")
        df[col] = df[col].apply(_normalize_name)

    result = []
    for _, row in df.iterrows():
        l2 = row["Little_2"] or None
        b2 = row["Big_2"] or None
        if l2 and b2:
            raise HTTPException(
                status_code=400,
                detail="Override row cannot have both Little_2 and Big_2 set.",
            )
        result.append({
            "little_1": row["Little_1"],
            "little_2": l2,
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
