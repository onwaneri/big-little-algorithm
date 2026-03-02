"""
Big-Little Matching Algorithm
==============================
Dynamically handles any participant counts.

  D = len(bigs) - len(littles)
  D > 0  →  D trios of (1 little + 2 bigs)
  D < 0  →  |D| trios of (2 littles + 1 big)
  D = 0  →  pure 1-to-1, no trios

Manual overrides are read from overrides.csv if present:
  Columns: Little_1, Little_2, Big_1, Big_2
  Leave Little_2 or Big_2 empty for duos / 2-big trios.

Banned pairs are read from banned_pairs.csv if present:
  Columns: Little, Big
  Specifies little-big pairs that cannot be matched together.

Input CSVs:
  bigs.csv     — columns: Name, Rank1, Rank2, …, RankN
  littles.csv  — columns: Name, Rank1, Rank2, …, RankN
"""

import os
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from difflib import get_close_matches
import sys


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PREF_COLS = ["Rank1", "Rank2", "Rank3", "Rank4", "Rank5"]
BIGS_FILE         = "bigs.csv"
LITTLES_FILE      = "littles.csv"
OVERRIDES_FILE    = "overrides.csv"
BANNED_PAIRS_FILE = "banned_pairs.csv"
OUTPUT_FILE       = "final_matches.csv"
FUZZY_CUTOFF      = 0.75
MAX_RANK          = len(PREF_COLS)  # default 5; functions accept max_rank parameter


def _normalize_name(name: str) -> str:
    """Normalise a name for comparison/roster lookup.

    Trims whitespace, collapses repeated spaces, and title‑cases the string.
    The routine is intentionally conservative so that "JOHN   doe" → "John Doe"
    while already-proper names are left untouched.  Both the command-line recipe
    and the backend CSV parser use the same logic.
    """
    # convert to str in case we get NaN or other types
    s = str(name).strip()
    # collapse internal whitespace
    s = " ".join(s.split())
    # titlecase to normalise casing
    return s.title()


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

def rank_to_score(rank: int | None, max_rank: int = MAX_RANK) -> float:
    """Rank 1 → 100%, Rank N → (100/N)%, Unranked → 0%."""
    if rank is None:
        return 0.0
    return (max_rank + 1 - rank) / max_rank * 100.0


def _weighted_pair_score(
    ls: float,
    bs: float,
    big_weight: float,
    little_has_prefs: bool,
    big_has_prefs: bool,
) -> float:
    """Weighted pair score that excludes parties with no preferences.

    If only one party submitted preferences, their score determines the pair score.
    If neither submitted preferences, returns a neutral 50.0.
    """
    if little_has_prefs and big_has_prefs:
        return (1.0 - big_weight) * ls + big_weight * bs
    elif little_has_prefs:
        return ls
    elif big_has_prefs:
        return bs
    return 50.0


# ---------------------------------------------------------------------------
# Data Loading & Validation
# ---------------------------------------------------------------------------

def load_and_validate(filepath: str, group_name: str) -> pd.DataFrame:
    """Load a CSV and ensure required columns exist."""
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        sys.exit(f"[ERROR] File not found: {filepath}")

    df.columns = [c.strip() for c in df.columns]
    df["Name"] = df["Name"].str.strip()

    missing = [c for c in ["Name"] + PREF_COLS if c not in df.columns]
    if missing:
        sys.exit(f"[ERROR] {filepath} is missing columns: {missing}")

    for col in PREF_COLS:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

    print(f"[INFO] Loaded {len(df)} {group_name}.")
    return df.reset_index(drop=True)


def load_form_csv(filepath: str, group_name: str) -> pd.DataFrame:
    """
    Parse a Google Form export CSV.
    - Drops the Timestamp column
    - Finds the 5 preference columns (those starting with pref_col_prefix)
    - Renames them to Rank1-Rank5
    - Rows with a blank Name (non-submitters with blank prefs) are kept as-is
    - Returns a cleaned DataFrame compatible with load_and_validate output
    """
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        sys.exit(f"[ERROR] File not found: {filepath}")

    df.columns = [c.strip() for c in df.columns]

    # Drop Timestamp if present
    if "Timestamp" in df.columns:
        df = df.drop(columns=["Timestamp"])

    # All columns after "Name" are the preference columns (in form order)
    other_cols = [c for c in df.columns if c != "Name"]
    if len(other_cols) < 5:
        sys.exit(
            f"[ERROR] {filepath}: expected at least 5 preference columns after 'Name', "
            f"found {len(other_cols)}: {other_cols}"
        )

    rename_map = {old: new for old, new in zip(other_cols[:5], PREF_COLS)}
    df = df.rename(columns=rename_map)

    # Keep only Name + Rank1-5 (drop any extra columns)
    keep = ["Name"] + PREF_COLS
    df = df[[c for c in keep if c in df.columns]]

    df["Name"] = df["Name"].astype(str).str.strip()
    # Drop rows where Name is blank or "nan" (malformed rows)
    df = df[df["Name"].notna() & (df["Name"] != "") & (df["Name"] != "nan")]

    for col in PREF_COLS:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

    print(f"[INFO] Loaded {len(df)} {group_name} from '{filepath}'.")
    return df.reset_index(drop=True)


def load_overrides(filepath: str, fresh_names: set, soph_names: set) -> list[dict]:
    """
    Load overrides.csv if it exists. Returns a list of override dicts with keys:
      freshman_1, freshman_2 (or None), big_1, big_2 (or None)
    Validates all names against rosters.
    """
    if not os.path.exists(filepath):
        return []

    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        sys.exit(f"[ERROR] Could not read {filepath}: {e}")

    df.columns = [c.strip() for c in df.columns]
    required = ["Little_1", "Big_1"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        sys.exit(f"[ERROR] {filepath} must have columns: Little_1, Little_2, Big_1, Big_2")

    # Fill optional columns
    for col in ["Little_2", "Big_2"]:
        if col not in df.columns:
            df[col] = ""
    for col in ["Little_1", "Little_2", "Big_1", "Big_2"]:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")
        df[col] = df[col].apply(_normalize_name)

    overrides = []
    for _, row in df.iterrows():
        l1 = row["Little_1"]
        l2 = row["Little_2"] or None
        b1 = row["Big_1"]
        b2 = row["Big_2"] or None

        # Validate names
        errors = []
        if l1 not in fresh_names:
            errors.append(f"Little '{l1}' not in littles roster")
        if l2 and l2 not in fresh_names:
            errors.append(f"Little '{l2}' not in littles roster")
        if b1 not in soph_names:
            errors.append(f"Big '{b1}' not in bigs roster")
        if b2 and b2 not in soph_names:
            errors.append(f"Big '{b2}' not in bigs roster")
        if errors:
            sys.exit(f"[ERROR] Override row has invalid names: {'; '.join(errors)}")

        # Must be duo, 2-big trio, or 2-little trio — not ambiguous
        if l2 and b2:
            sys.exit(
                f"[ERROR] Override row has both Little_2 and Big_2 set. "
                f"Each override must be a duo, 2-big trio (l1+b1+b2), "
                f"or 2-little trio (l1+l2+b1)."
            )

        overrides.append({"little_1": l1, "little_2": l2, "big_1": b1, "big_2": b2})
        kind = "duo" if not l2 and not b2 else ("2-big trio" if b2 else "2-little trio")
        print(f"[INFO] Override ({kind}): {l1}" + (f" & {l2}" if l2 else "") +
              f" ↔ {b1}" + (f" & {b2}" if b2 else ""))

    return overrides


def load_banned_pairs(filepath: str, fresh_names: set, soph_names: set) -> list[dict]:
    """
    Load banned_pairs.csv if it exists. Returns a list of banned pair dicts with keys:
      freshman, sophomore
    Validates all names against rosters.
    """
    if not os.path.exists(filepath):
        return []

    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        sys.exit(f"[ERROR] Could not read {filepath}: {e}")

    df.columns = [c.strip() for c in df.columns]
    required = ["Little", "Big"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        sys.exit(f"[ERROR] {filepath} must have columns: Little, Big")

    for col in ["Little", "Big"]:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")
        df[col] = df[col].apply(_normalize_name)

    banned = []
    for _, row in df.iterrows():
        little = row["Little"]
        big    = row["Big"]

        if not little or not big:
            continue

        # Validate names
        errors = []
        if little not in fresh_names:
            errors.append(f"Little '{little}' not in littles roster")
        if big not in soph_names:
            errors.append(f"Big '{big}' not in bigs roster")
        if errors:
            sys.exit(f"[ERROR] Banned pair row has invalid names: {'; '.join(errors)}")

        banned.append({"little": little, "big": big})
        print(f"[INFO] Banned pair: {little!r} ↔ {big!r}")

    return banned


def check_name_mismatches(
    prefs_df: pd.DataFrame,
    valid_names: set,
    ranker_group: str,
    ranked_group: str,
) -> dict[str, str]:
    """Warn about names in preference columns that don't match the valid roster."""
    corrections: dict[str, str] = {}
    seen_bad: set[str] = set()

    for _, row in prefs_df.iterrows():
        for col in PREF_COLS:
            name = row[col]
            if not name or name in valid_names or name in seen_bad:
                continue
            seen_bad.add(name)
            matches = get_close_matches(name, valid_names, n=3, cutoff=FUZZY_CUTOFF)
            if len(matches) == 1:
                print(
                    f"[WARNING] {ranker_group} '{row['Name']}' ranked "
                    f"'{name}' — not found; auto-correcting to '{matches[0]}'."
                )
                corrections[name] = matches[0]
            elif matches:
                print(
                    f"[WARNING] {ranker_group} '{row['Name']}' ranked "
                    f"'{name}' — not found. Possible: {matches}. Entry ignored."
                )
            else:
                print(
                    f"[WARNING] {ranker_group} '{row['Name']}' ranked "
                    f"'{name}' — no close match found; entry ignored."
                )
    return corrections


def apply_corrections(df: pd.DataFrame, corrections: dict[str, str]) -> pd.DataFrame:
    for col in PREF_COLS:
        df[col] = df[col].replace(corrections)
    return df


def build_preference_lists(
    df: pd.DataFrame, valid_names: set
) -> dict[str, list[str]]:
    """Build ordered, deduplicated preference lists filtering invalid names."""
    prefs: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        seen = set()
        ordered = []
        for col in PREF_COLS:
            val = row[col]
            if val and val in valid_names and val not in seen:
                ordered.append(val)
                seen.add(val)
        prefs[row["Name"]] = ordered
    return prefs


def remove_from_prefs(
    prefs: dict[str, list[str]], names_to_remove: set
) -> dict[str, list[str]]:
    """Remove specified names from all preference lists."""
    return {
        person: [n for n in pref_list if n not in names_to_remove]
        for person, pref_list in prefs.items()
        if person not in names_to_remove
    }


# ---------------------------------------------------------------------------
# Mutual Score
# ---------------------------------------------------------------------------

def mutual_score(
    fresh: str,
    soph: str,
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
    max_rank: int = 5,
) -> float:
    """
    Combined mutual preference strength (lower = more mutually preferred).
    Score = (rank_of_soph_in_fresh_list + rank_of_fresh_in_soph_list) / 2.
    Unranked parties incur a penalty of max_rank + 1.
    """
    penalty = max_rank + 1
    fp = fresh_prefs.get(fresh, [])
    rank_f = fp.index(soph) + 1 if soph in fp else penalty
    sp = soph_prefs.get(soph, [])
    rank_s = sp.index(fresh) + 1 if fresh in sp else penalty
    return (rank_f + rank_s) / 2.0


# ---------------------------------------------------------------------------
# Trio Selection
# ---------------------------------------------------------------------------

def _find_best_trio_2bigs(
    fresh_pool: list[str],
    soph_pool: list[str],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> tuple[str, str, str]:
    """
    Find (freshman, big1, big2) that minimises mutual_score(f,b1) + mutual_score(f,b2).
    This gives the 1-little-2-bigs trio with the most mutual enthusiasm.
    """
    best_score = float("inf")
    best = ("", "", "")
    for fresh in fresh_pool:
        scored = sorted(soph_pool, key=lambda s: mutual_score(fresh, s, fresh_prefs, soph_prefs))
        top_k = scored[:10]
        for i, b1 in enumerate(top_k):
            for b2 in top_k[i + 1:]:
                score = (
                    mutual_score(fresh, b1, fresh_prefs, soph_prefs)
                    + mutual_score(fresh, b2, fresh_prefs, soph_prefs)
                )
                if score < best_score:
                    best_score = score
                    best = (fresh, b1, b2)
    return best


def _find_best_trio_2littles(
    fresh_pool: list[str],
    soph_pool: list[str],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> tuple[str, str, str]:
    """
    Find (fresh1, fresh2, soph) that minimises mutual_score(f1,s) + mutual_score(f2,s).
    This gives the 2-littles-1-big trio with the most mutual enthusiasm.
    Returns (fresh1, fresh2, soph).
    """
    best_score = float("inf")
    best = ("", "", "")
    for soph in soph_pool:
        scored = sorted(fresh_pool, key=lambda f: mutual_score(f, soph, fresh_prefs, soph_prefs))
        top_k = scored[:10]
        for i, f1 in enumerate(top_k):
            for f2 in top_k[i + 1:]:
                score = (
                    mutual_score(f1, soph, fresh_prefs, soph_prefs)
                    + mutual_score(f2, soph, fresh_prefs, soph_prefs)
                )
                if score < best_score:
                    best_score = score
                    best = (f1, f2, soph)
    return best


def select_trios(
    D: int,
    fresh_pool: list[str],
    soph_pool: list[str],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """
    Select trios based on D = len(sophs) - len(fresh).

    D > 0  →  D trios of (freshman, big1, big2)     returned in trios_2bigs
    D < 0  →  |D| trios of (fresh1, fresh2, soph)   returned in trios_2littles
    D = 0  →  no trios

    Returns (trios_2bigs, trios_2littles) where each is a list of 3-tuples.
    Members are removed from the pools greedily after each selection.
    """
    trios_2bigs: list[tuple[str, str, str]] = []
    trios_2littles: list[tuple[str, str, str]] = []

    avail_fresh = list(fresh_pool)
    avail_soph = list(soph_pool)
    cur_fresh_prefs = dict(fresh_prefs)
    cur_soph_prefs = dict(soph_prefs)

    if D > 0:
        for _ in range(D):
            trio = _find_best_trio_2bigs(avail_fresh, avail_soph, cur_fresh_prefs, cur_soph_prefs)
            fresh, b1, b2 = trio
            trios_2bigs.append(trio)
            avail_fresh.remove(fresh)
            avail_soph.remove(b1)
            avail_soph.remove(b2)
            removed = {fresh, b1, b2}
            cur_fresh_prefs = remove_from_prefs(cur_fresh_prefs, removed)
            cur_soph_prefs = remove_from_prefs(cur_soph_prefs, removed)
    elif D < 0:
        for _ in range(abs(D)):
            trio = _find_best_trio_2littles(avail_fresh, avail_soph, cur_fresh_prefs, cur_soph_prefs)
            f1, f2, soph = trio
            trios_2littles.append(trio)
            avail_fresh.remove(f1)
            avail_fresh.remove(f2)
            avail_soph.remove(soph)
            removed = {f1, f2, soph}
            cur_fresh_prefs = remove_from_prefs(cur_fresh_prefs, removed)
            cur_soph_prefs = remove_from_prefs(cur_soph_prefs, removed)

    return trios_2bigs, trios_2littles


# ---------------------------------------------------------------------------
# Twin-Pair Selection
# ---------------------------------------------------------------------------

def select_twin_trios(
    soph_twin_pairs: list[tuple[str, str]],
    fresh_twin_pairs: list[tuple[str, str]],
    fresh_pool: list[str],
    soph_pool: list[str],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> tuple[
    list[tuple[str, str, str]],  # 2-big trios  (freshman, big1, big2)
    list[tuple[str, str, str]],  # 2-little trios (fresh1, fresh2, soph)
    list[str],                   # remaining fresh_pool
    list[str],                   # remaining soph_pool
    dict[str, list[str]],        # updated fresh_prefs
    dict[str, list[str]],        # updated soph_prefs
]:
    """
    Process twin pairs before the main trio/matching algorithm.

    Sophomore twins (B1, B2): algorithm picks the best available freshman.
    Freshman twins  (F1, F2): algorithm picks the best available sophomore.

    Members are removed from the pools after each selection.
    Returns updated pools and prefs for downstream use.
    """
    avail_fresh = list(fresh_pool)
    avail_soph  = list(soph_pool)
    cur_fresh_prefs = dict(fresh_prefs)
    cur_soph_prefs  = dict(soph_prefs)
    trios_2bigs:    list[tuple[str, str, str]] = []
    trios_2littles: list[tuple[str, str, str]] = []

    for b1, b2 in soph_twin_pairs:
        if not avail_fresh:
            raise ValueError(f"No freshmen available to assign to sophomore twins {b1!r} & {b2!r}")
        best_f = min(
            avail_fresh,
            key=lambda f: (
                mutual_score(f, b1, cur_fresh_prefs, cur_soph_prefs)
                + mutual_score(f, b2, cur_fresh_prefs, cur_soph_prefs)
            ),
        )
        trios_2bigs.append((best_f, b1, b2))
        avail_fresh.remove(best_f)
        avail_soph.remove(b1)
        avail_soph.remove(b2)
        removed = {best_f, b1, b2}
        cur_fresh_prefs = remove_from_prefs(cur_fresh_prefs, removed)
        cur_soph_prefs  = remove_from_prefs(cur_soph_prefs,  removed)
        print(f"[INFO] Twin trio (soph): {best_f!r} ↔ {b1!r} & {b2!r}")

    for f1, f2 in fresh_twin_pairs:
        if not avail_soph:
            raise ValueError(f"No sophomores available to assign to freshman twins {f1!r} & {f2!r}")
        best_b = min(
            avail_soph,
            key=lambda b: (
                mutual_score(f1, b, cur_fresh_prefs, cur_soph_prefs)
                + mutual_score(f2, b, cur_fresh_prefs, cur_soph_prefs)
            ),
        )
        trios_2littles.append((f1, f2, best_b))
        avail_fresh.remove(f1)
        avail_fresh.remove(f2)
        avail_soph.remove(best_b)
        removed = {f1, f2, best_b}
        cur_fresh_prefs = remove_from_prefs(cur_fresh_prefs, removed)
        cur_soph_prefs  = remove_from_prefs(cur_soph_prefs,  removed)
        print(f"[INFO] Twin trio (fresh): {f1!r} & {f2!r} ↔ {best_b!r}")

    return trios_2bigs, trios_2littles, avail_fresh, avail_soph, cur_fresh_prefs, cur_soph_prefs


# ---------------------------------------------------------------------------
# Optimal 1-to-1 Matching
# ---------------------------------------------------------------------------

def optimize_matching(
    littles: list[str],
    bigs: list[str],
    little_prefs: dict[str, list[str]],
    big_prefs: dict[str, list[str]],
    big_weight: float = 0.5,
    max_rank: int = MAX_RANK,
) -> dict[str, str]:
    """
    Find the 1-to-1 matching that maximises the median pair score.

    Pair score = big_weight * big_score + (1 - big_weight) * little_score.
    Parties with no preferences are excluded from their half of the score.
    Returns {little -> big} mapping.
    """
    if not littles:
        return {}

    n = len(littles)
    scores = np.zeros((n, n))
    for i, little in enumerate(littles):
        lp = little_prefs.get(little, [])
        for j, big in enumerate(bigs):
            bp = big_prefs.get(big, [])
            r_little = lp.index(big) + 1 if big in lp else None
            r_big    = bp.index(little) + 1 if little in bp else None
            ls = rank_to_score(r_little, max_rank)
            bs = rank_to_score(r_big, max_rank)
            scores[i, j] = _weighted_pair_score(ls, bs, big_weight, bool(lp), bool(bp))

    target = (n + 1) // 2
    distinct = sorted(set(scores.flatten()), reverse=True)
    best_t = 0.0
    for t in distinct:
        above = (scores >= t - 1e-9).astype(float)
        ri, ci = linear_sum_assignment(-above)
        if above[ri, ci].sum() >= target:
            best_t = t
            break

    BIG = 10_000.0
    final = np.where(scores >= best_t - 1e-9, BIG + scores, scores)
    row_ind, col_ind = linear_sum_assignment(-final)
    return {littles[i]: bigs[j] for i, j in zip(row_ind, col_ind)}


# ---------------------------------------------------------------------------
# Satisfaction Scoring
# ---------------------------------------------------------------------------

def compute_satisfaction(
    duo_matches: dict[str, str],
    trios_2bigs: list[tuple[str, str, str]],
    trios_2littles: list[tuple[str, str, str]],
    little_prefs: dict[str, list[str]],
    big_prefs: dict[str, list[str]],
    big_weight: float = 0.5,
    max_rank: int = MAX_RANK,
) -> pd.DataFrame:
    """
    One row per match. Unified schema:
      Little_1, Little_2, Big_1, Big_2,
      Little_1_Score, Little_2_Score, Big_1_Score, Big_2_Score,
      Pair_Score, Match_Type
    Score is None when the person submitted no preferences at all.
    """
    rows = []

    # Regular 1-to-1 duos
    for little, big in duo_matches.items():
        lp = little_prefs.get(little, [])
        bp = big_prefs.get(big, [])
        r_l = lp.index(big) + 1 if big in lp else None
        r_b = bp.index(little) + 1 if little in bp else None
        ls = rank_to_score(r_l, max_rank)
        bs = rank_to_score(r_b, max_rank)
        rows.append({
            "Little_1": little, "Little_2": None,
            "Big_1": big, "Big_2": None,
            "Little_1_Score": ls if lp else None,
            "Little_2_Score": None,
            "Big_1_Score": bs if bp else None,
            "Big_2_Score": None,
            "Pair_Score": _weighted_pair_score(ls, bs, big_weight, bool(lp), bool(bp)),
            "Match_Type": "Duo",
        })

    # 2-big trios: (little, big1, big2)
    for little, b1, b2 in trios_2bigs:
        lp  = little_prefs.get(little, [])
        bp1 = big_prefs.get(b1, [])
        bp2 = big_prefs.get(b2, [])
        r_l1 = lp.index(b1) + 1 if b1 in lp else None
        r_l2 = lp.index(b2) + 1 if b2 in lp else None
        r_b1 = bp1.index(little) + 1 if little in bp1 else None
        r_b2 = bp2.index(little) + 1 if little in bp2 else None
        # little score: average across both bigs
        ls  = (rank_to_score(r_l1, max_rank) + rank_to_score(r_l2, max_rank)) / 2
        b1s = rank_to_score(r_b1, max_rank)
        b2s = rank_to_score(r_b2, max_rank)
        # Combined big score: average of both bigs' scores
        bigs_have_prefs = bool(bp1) or bool(bp2)
        bs_combined = (
            ((b1s if bp1 else 0) + (b2s if bp2 else 0)) /
            max(1, int(bool(bp1)) + int(bool(bp2)))
        )
        rows.append({
            "Little_1": little, "Little_2": None,
            "Big_1": b1, "Big_2": b2,
            "Little_1_Score": ls if lp else None,
            "Little_2_Score": None,
            "Big_1_Score": b1s if bp1 else None,
            "Big_2_Score": b2s if bp2 else None,
            "Pair_Score": _weighted_pair_score(ls, bs_combined, big_weight, bool(lp), bigs_have_prefs),
            "Match_Type": "Trio",
        })

    # 2-little trios: (little1, little2, big)
    for l1, l2, big in trios_2littles:
        lp1 = little_prefs.get(l1, [])
        lp2 = little_prefs.get(l2, [])
        bp  = big_prefs.get(big, [])
        r_l1 = lp1.index(big) + 1 if big in lp1 else None
        r_l2 = lp2.index(big) + 1 if big in lp2 else None
        r_b1 = bp.index(l1) + 1 if l1 in bp else None
        r_b2 = bp.index(l2) + 1 if l2 in bp else None
        l1s = rank_to_score(r_l1, max_rank)
        l2s = rank_to_score(r_l2, max_rank)
        bs  = (rank_to_score(r_b1, max_rank) + rank_to_score(r_b2, max_rank)) / 2
        # Combined little score: average across both littles
        littles_have_prefs = bool(lp1) or bool(lp2)
        ls_combined = (
            ((l1s if lp1 else 0) + (l2s if lp2 else 0)) /
            max(1, int(bool(lp1)) + int(bool(lp2)))
        )
        rows.append({
            "Little_1": l1, "Little_2": l2,
            "Big_1": big, "Big_2": None,
            "Little_1_Score": l1s if lp1 else None,
            "Little_2_Score": l2s if lp2 else None,
            "Big_1_Score": bs if bp else None,
            "Big_2_Score": None,
            "Pair_Score": _weighted_pair_score(ls_combined, bs, big_weight, littles_have_prefs, bool(bp)),
            "Match_Type": "Trio",
        })

    df = pd.DataFrame(rows)
    return df.sort_values("Little_1").reset_index(drop=True)


def print_satisfaction_summary(sat_df: pd.DataFrame) -> None:
    """Print a formatted satisfaction breakdown."""
    print("\n" + "=" * 58)
    print("  SATISFACTION SUMMARY")
    print("=" * 58)

    def show_dist(scores: pd.Series, label: str) -> None:
        scores = scores.dropna()
        print(f"\n  {label} ({len(scores)} entries):")
        for score, cnt in scores.value_counts().sort_index(ascending=False).items():
            print(f"    {score:.1f}%  : {cnt:>3} person(s)")
        print(f"    Average score : {scores.mean():.1f}%")

    show_dist(sat_df["Pair_Score"], "Pair scores")
    little_scores = pd.concat([sat_df["Little_1_Score"], sat_df["Little_2_Score"]]).dropna()
    show_dist(little_scores, "Littles")
    big_scores = pd.concat([sat_df["Big_1_Score"], sat_df["Big_2_Score"]]).dropna()
    show_dist(big_scores, "Bigs")

    pair_scores = sat_df["Pair_Score"].sort_values().reset_index(drop=True)
    median = pair_scores.iloc[len(pair_scores) // 2]
    print(f"\n  Median pair score : {median:.1f}")
    print(f"  Average pair score: {pair_scores.mean():.1f}")
    print("=" * 58 + "\n")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_output(
    duo_matches: dict[str, str],
    trios_2bigs: list[tuple[str, str, str]],
    trios_2littles: list[tuple[str, str, str]],
) -> pd.DataFrame:
    """Unified output DataFrame. Match_Type is 'Duo' or 'Trio'."""
    rows = []
    for little, big in duo_matches.items():
        rows.append({"Little_1": little, "Little_2": "", "Big_1": big, "Big_2": "", "Match_Type": "Duo"})
    for little, b1, b2 in trios_2bigs:
        rows.append({"Little_1": little, "Little_2": "", "Big_1": b1, "Big_2": b2, "Match_Type": "Trio"})
    for l1, l2, big in trios_2littles:
        rows.append({"Little_1": l1, "Little_2": l2, "Big_1": big, "Big_2": "", "Match_Type": "Trio"})
    return pd.DataFrame(rows).sort_values("Little_1").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n====================================================")
    print("   Big-Little Matching Algorithm")
    print("====================================================\n")

    # 1. Load data
    bigs_df    = load_form_csv(BIGS_FILE, "Bigs")
    littles_df = load_form_csv(LITTLES_FILE, "Littles")
    big_names    = set(bigs_df["Name"])
    little_names = set(littles_df["Name"])

    # 2. Load manual overrides
    overrides = load_overrides(OVERRIDES_FILE, little_names, big_names)
    overridden_littles = set()
    overridden_bigs    = set()
    for ov in overrides:
        overridden_littles.add(ov["little_1"])
        if ov["little_2"]:
            overridden_littles.add(ov["little_2"])
        overridden_bigs.add(ov["big_1"])
        if ov["big_2"]:
            overridden_bigs.add(ov["big_2"])

    # 3. Detect and correct name mismatches
    print("\n[INFO] Checking for name mismatches in Little rankings...")
    littles_df = apply_corrections(littles_df, check_name_mismatches(littles_df, big_names, "Little", "Big"))
    print("[INFO] Checking for name mismatches in Big rankings...")
    bigs_df = apply_corrections(bigs_df, check_name_mismatches(bigs_df, little_names, "Big", "Little"))

    # 4. Build preference lists
    little_prefs = build_preference_lists(littles_df, big_names)
    big_prefs    = build_preference_lists(bigs_df, little_names)

    # 4a. Load and apply banned pairs
    banned = load_banned_pairs(BANNED_PAIRS_FILE, little_names, big_names)
    banned_set = {(ban["little"], ban["big"]) for ban in banned}
    for little, prefs in little_prefs.items():
        little_prefs[little] = [b for b in prefs if (little, b) not in banned_set]
    for big, prefs in big_prefs.items():
        big_prefs[big] = [l for l in prefs if (l, big) not in banned_set]

    # 5. Remove overridden members from the pools and preference lists
    little_pool = [l for l in little_names if l not in overridden_littles]
    big_pool    = [b for b in big_names    if b not in overridden_bigs]
    all_override_names = overridden_littles | overridden_bigs
    little_prefs = remove_from_prefs(little_prefs, all_override_names)
    big_prefs    = remove_from_prefs(big_prefs,    all_override_names)

    # 6. Compute D and select trios
    D = len(big_pool) - len(little_pool)
    if D > 0:
        print(f"\n[INFO] D={D}: selecting {D} trio(s) of (1 little + 2 bigs)...")
    elif D < 0:
        print(f"\n[INFO] D={D}: selecting {abs(D)} trio(s) of (2 littles + 1 big)...")
    else:
        print("\n[INFO] D=0: equal counts — pure 1-to-1 matching, no trios.")

    trios_2bigs, trios_2littles = select_trios(D, little_pool, big_pool, little_prefs, big_prefs)

    for little, b1, b2 in trios_2bigs:
        print(f"[INFO] 2-big trio: {little!r} ↔ {b1!r} & {b2!r}")
    for l1, l2, big in trios_2littles:
        print(f"[INFO] 2-little trio: {l1!r} & {l2!r} ↔ {big!r}")

    # 7. Remove trio members from pool, then run 1-to-1 matching
    trio_littles_used = {l for l, _, _ in trios_2bigs} | {l1 for l1, _, _ in trios_2littles} | {l2 for _, l2, _ in trios_2littles}
    trio_bigs_used    = {b1 for _, b1, _ in trios_2bigs} | {b2 for _, _, b2 in trios_2bigs} | {b for _, _, b in trios_2littles}
    remaining_littles = [l for l in little_pool if l not in trio_littles_used]
    remaining_bigs    = [b for b in big_pool    if b not in trio_bigs_used]

    assert len(remaining_littles) == len(remaining_bigs), (
        f"Pool mismatch after trio removal: {len(remaining_littles)} littles vs {len(remaining_bigs)} bigs"
    )

    print(f"[INFO] Optimising {len(remaining_littles)} 1-to-1 pairings...")
    duo_matches = optimize_matching(remaining_littles, remaining_bigs, little_prefs, big_prefs)

    # 8. Incorporate overrides into the match lists
    override_trios_2bigs:    list[tuple[str, str, str]] = []
    override_trios_2littles: list[tuple[str, str, str]] = []
    override_duos: dict[str, str] = {}
    for ov in overrides:
        l1, l2, b1, b2 = ov["little_1"], ov["little_2"], ov["big_1"], ov["big_2"]
        if l2:
            override_trios_2littles.append((l1, l2, b1))
        elif b2:
            override_trios_2bigs.append((l1, b1, b2))
        else:
            override_duos[l1] = b1

    all_duos        = {**duo_matches, **override_duos}
    all_trios_2bigs = trios_2bigs + override_trios_2bigs
    all_trios_2lit  = trios_2littles + override_trios_2littles

    # 9. Build output and satisfaction scores
    output_df = build_output(all_duos, all_trios_2bigs, all_trios_2lit)
    sat_df    = compute_satisfaction(all_duos, all_trios_2bigs, all_trios_2lit, little_prefs, big_prefs)

    # 10. Print and save
    print("\n[RESULTS] Final Pairings:")
    print(output_df.to_string(index=False))
    print_satisfaction_summary(sat_df)

    output_df.to_csv(OUTPUT_FILE, index=False)
    sat_df.to_csv("satisfaction_scores.csv", index=False)
    print(f"[INFO] Saved pairings to '{OUTPUT_FILE}'")
    print("[INFO] Saved satisfaction scores to 'satisfaction_scores.csv'\n")


if __name__ == "__main__":
    main()
