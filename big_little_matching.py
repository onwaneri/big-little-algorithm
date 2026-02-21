"""
Big-Little Matching Algorithm for Sigma Nu Fraternity
======================================================
Dynamically handles any participant counts.

  D = len(sophomores) - len(freshmen)
  D > 0  →  D trios of (1 freshman + 2 bigs)
  D < 0  →  |D| trios of (2 freshmen + 1 big)
  D = 0  →  pure 1-to-1, no trios

Manual overrides are read from overrides.csv if present:
  Columns: Freshman_1, Freshman_2, Big_1, Big_2
  Leave Freshman_2 or Big_2 empty for duos / 2-big trios.

Input CSVs:
  sophomores.csv  — columns: Name, Rank1, Rank2, Rank3, Rank4, Rank5
  freshmen.csv    — columns: Name, Rank1, Rank2, Rank3, Rank4, Rank5
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
SOPHOMORES_FILE = "sophomores.csv"
FRESHMEN_FILE   = "freshmen.csv"
OVERRIDES_FILE  = "overrides.csv"
OUTPUT_FILE     = "final_matches.csv"
FUZZY_CUTOFF    = 0.75
MAX_RANK        = len(PREF_COLS)  # 5
ALPHA           = 0.1


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

def rank_to_score(rank: int | None) -> float:
    """Rank 1 → 100%, Rank 2 → 80%, …, Rank 5 → 20%, Unranked → 0%."""
    if rank is None:
        return 0.0
    return (MAX_RANK + 1 - rank) / MAX_RANK * 100.0


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
    required = ["Freshman_1", "Big_1"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        sys.exit(f"[ERROR] {filepath} must have columns: Freshman_1, Freshman_2, Big_1, Big_2")

    # Fill optional columns
    for col in ["Freshman_2", "Big_2"]:
        if col not in df.columns:
            df[col] = ""
    for col in ["Freshman_1", "Freshman_2", "Big_1", "Big_2"]:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

    overrides = []
    for _, row in df.iterrows():
        f1 = row["Freshman_1"]
        f2 = row["Freshman_2"] or None
        b1 = row["Big_1"]
        b2 = row["Big_2"] or None

        # Validate names
        errors = []
        if f1 not in fresh_names:
            errors.append(f"Freshman '{f1}' not in freshmen roster")
        if f2 and f2 not in fresh_names:
            errors.append(f"Freshman '{f2}' not in freshmen roster")
        if b1 not in soph_names:
            errors.append(f"Big '{b1}' not in sophomores roster")
        if b2 and b2 not in soph_names:
            errors.append(f"Big '{b2}' not in sophomores roster")
        if errors:
            sys.exit(f"[ERROR] Override row has invalid names: {'; '.join(errors)}")

        # Must be duo, 2-big trio, or 2-little trio — not ambiguous
        if f2 and b2:
            sys.exit(
                f"[ERROR] Override row has both Freshman_2 and Big_2 set. "
                f"Each override must be a duo, 2-big trio (f1+b1+b2), "
                f"or 2-little trio (f1+f2+b1)."
            )

        overrides.append({"freshman_1": f1, "freshman_2": f2, "big_1": b1, "big_2": b2})
        kind = "duo" if not f2 and not b2 else ("2-big trio" if b2 else "2-little trio")
        print(f"[INFO] Override ({kind}): {f1}" + (f" & {f2}" if f2 else "") +
              f" ↔ {b1}" + (f" & {b2}" if b2 else ""))

    return overrides


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
    max_rank: int = MAX_RANK,
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
# Optimal 1-to-1 Matching
# ---------------------------------------------------------------------------

def optimize_matching(
    freshmen: list[str],
    sophomores: list[str],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> dict[str, str]:
    """
    Find the 1-to-1 matching that maximises the median pair score.

    Pair score = fs * bs / 100 + ALPHA * (fs + bs) / 2
    Returns {freshman -> sophomore} mapping.
    """
    if not freshmen:
        return {}

    n = len(freshmen)
    scores = np.zeros((n, n))
    for i, fresh in enumerate(freshmen):
        fp = fresh_prefs.get(fresh, [])
        for j, soph in enumerate(sophomores):
            sp = soph_prefs.get(soph, [])
            r_fresh = fp.index(soph) + 1 if soph in fp else None
            r_soph  = sp.index(fresh) + 1 if fresh in sp else None
            fs = rank_to_score(r_fresh)
            bs = rank_to_score(r_soph)
            scores[i, j] = fs * bs / 100 + ALPHA * (fs + bs) / 2

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
    return {freshmen[i]: sophomores[j] for i, j in zip(row_ind, col_ind)}


# ---------------------------------------------------------------------------
# Satisfaction Scoring
# ---------------------------------------------------------------------------

def compute_satisfaction(
    duo_matches: dict[str, str],
    trios_2bigs: list[tuple[str, str, str]],
    trios_2littles: list[tuple[str, str, str]],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> pd.DataFrame:
    """
    One row per match. Unified schema:
      Freshman_1, Freshman_2, Big_1, Big_2,
      Freshman_1_Score, Freshman_2_Score, Big_1_Score, Big_2_Score,
      Pair_Score, Match_Type
    Empty/None where not applicable.
    """
    rows = []

    # Regular 1-to-1 duos
    for fresh, soph in duo_matches.items():
        fp = fresh_prefs.get(fresh, [])
        sp = soph_prefs.get(soph, [])
        r_f = fp.index(soph) + 1 if soph in fp else None
        r_s = sp.index(fresh) + 1 if fresh in sp else None
        fs = rank_to_score(r_f)
        bs = rank_to_score(r_s)
        rows.append({
            "Freshman_1": fresh, "Freshman_2": None,
            "Big_1": soph, "Big_2": None,
            "Freshman_1_Score": fs, "Freshman_2_Score": None,
            "Big_1_Score": bs, "Big_2_Score": None,
            "Pair_Score": fs * bs / 100 + ALPHA * (fs + bs) / 2,
            "Match_Type": "Duo",
        })

    # 2-big trios: (freshman, big1, big2)
    for fresh, b1, b2 in trios_2bigs:
        fp  = fresh_prefs.get(fresh, [])
        sp1 = soph_prefs.get(b1, [])
        sp2 = soph_prefs.get(b2, [])
        r_f1 = fp.index(b1) + 1 if b1 in fp else None
        r_f2 = fp.index(b2) + 1 if b2 in fp else None
        r_b1 = sp1.index(fresh) + 1 if fresh in sp1 else None
        r_b2 = sp2.index(fresh) + 1 if fresh in sp2 else None
        fs  = (rank_to_score(r_f1) + rank_to_score(r_f2)) / 2
        b1s = rank_to_score(r_b1)
        b2s = rank_to_score(r_b2)
        rows.append({
            "Freshman_1": fresh, "Freshman_2": None,
            "Big_1": b1, "Big_2": b2,
            "Freshman_1_Score": fs, "Freshman_2_Score": None,
            "Big_1_Score": b1s, "Big_2_Score": b2s,
            "Pair_Score": fs * b1s * b2s / 10000 + ALPHA * (fs + b1s + b2s) / 3,
            "Match_Type": "Trio",
        })

    # 2-little trios: (fresh1, fresh2, soph)
    for f1, f2, soph in trios_2littles:
        fp1 = fresh_prefs.get(f1, [])
        fp2 = fresh_prefs.get(f2, [])
        sp  = soph_prefs.get(soph, [])
        r_f1 = fp1.index(soph) + 1 if soph in fp1 else None
        r_f2 = fp2.index(soph) + 1 if soph in fp2 else None
        r_b1 = sp.index(f1) + 1 if f1 in sp else None
        r_b2 = sp.index(f2) + 1 if f2 in sp else None
        f1s = rank_to_score(r_f1)
        f2s = rank_to_score(r_f2)
        bs  = (rank_to_score(r_b1) + rank_to_score(r_b2)) / 2
        rows.append({
            "Freshman_1": f1, "Freshman_2": f2,
            "Big_1": soph, "Big_2": None,
            "Freshman_1_Score": f1s, "Freshman_2_Score": f2s,
            "Big_1_Score": bs, "Big_2_Score": None,
            "Pair_Score": f1s * f2s * bs / 10000 + ALPHA * (f1s + f2s + bs) / 3,
            "Match_Type": "Trio",
        })

    df = pd.DataFrame(rows)
    return df.sort_values("Freshman_1").reset_index(drop=True)


def print_satisfaction_summary(sat_df: pd.DataFrame) -> None:
    """Print a formatted satisfaction breakdown."""
    print("\n" + "=" * 58)
    print("  SATISFACTION SUMMARY")
    print("=" * 58)

    score_labels = {rank_to_score(r): f"{rank_to_score(r):.0f}%" for r in range(1, MAX_RANK + 1)}
    score_labels[0.0] = "0% (Unranked)"

    def show_dist(scores: pd.Series, label: str) -> None:
        scores = scores.dropna()
        print(f"\n  {label} ({len(scores)} entries):")
        for score, cnt in scores.value_counts().sort_index(ascending=False).items():
            lbl = score_labels.get(round(score, 4), f"{score:.1f}%")
            print(f"    {lbl:15s} : {cnt:>3} person(s)")
        print(f"    Average score : {scores.mean():.1f}%")

    show_dist(sat_df["Pair_Score"], "Pair scores")
    fresh_scores = pd.concat([sat_df["Freshman_1_Score"], sat_df["Freshman_2_Score"]]).dropna()
    show_dist(fresh_scores, "Freshmen")
    soph_scores = pd.concat([sat_df["Big_1_Score"], sat_df["Big_2_Score"]]).dropna()
    show_dist(soph_scores, "Sophomores")

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
    for fresh, soph in duo_matches.items():
        rows.append({"Freshman_1": fresh, "Freshman_2": "", "Big_1": soph, "Big_2": "", "Match_Type": "Duo"})
    for fresh, b1, b2 in trios_2bigs:
        rows.append({"Freshman_1": fresh, "Freshman_2": "", "Big_1": b1, "Big_2": b2, "Match_Type": "Trio"})
    for f1, f2, soph in trios_2littles:
        rows.append({"Freshman_1": f1, "Freshman_2": f2, "Big_1": soph, "Big_2": "", "Match_Type": "Trio"})
    return pd.DataFrame(rows).sort_values("Freshman_1").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n====================================================")
    print("   Sigma Nu Big-Little Matching Algorithm")
    print("====================================================\n")

    # 1. Load data
    sophs_df  = load_and_validate(SOPHOMORES_FILE, "Sophomores")
    fresh_df  = load_and_validate(FRESHMEN_FILE, "Freshmen")
    soph_names = set(sophs_df["Name"])
    fresh_names = set(fresh_df["Name"])

    # 2. Load manual overrides
    overrides = load_overrides(OVERRIDES_FILE, fresh_names, soph_names)
    overridden_fresh = set()
    overridden_soph  = set()
    for ov in overrides:
        overridden_fresh.add(ov["freshman_1"])
        if ov["freshman_2"]:
            overridden_fresh.add(ov["freshman_2"])
        overridden_soph.add(ov["big_1"])
        if ov["big_2"]:
            overridden_soph.add(ov["big_2"])

    # 3. Detect and correct name mismatches
    print("\n[INFO] Checking for name mismatches in Freshman rankings...")
    fresh_df = apply_corrections(fresh_df, check_name_mismatches(fresh_df, soph_names, "Freshman", "Sophomore"))
    print("[INFO] Checking for name mismatches in Sophomore rankings...")
    sophs_df = apply_corrections(sophs_df, check_name_mismatches(sophs_df, fresh_names, "Sophomore", "Freshman"))

    # 4. Build preference lists
    fresh_prefs = build_preference_lists(fresh_df, soph_names)
    soph_prefs  = build_preference_lists(sophs_df, fresh_names)

    # 5. Remove overridden members from the pools and preference lists
    fresh_pool = [f for f in fresh_names if f not in overridden_fresh]
    soph_pool  = [s for s in soph_names  if s not in overridden_soph]
    all_override_names = overridden_fresh | overridden_soph
    fresh_prefs = remove_from_prefs(fresh_prefs, all_override_names)
    soph_prefs  = remove_from_prefs(soph_prefs,  all_override_names)

    # 6. Compute D and select trios
    D = len(soph_pool) - len(fresh_pool)
    if D > 0:
        print(f"\n[INFO] D={D}: selecting {D} trio(s) of (1 little + 2 bigs)...")
    elif D < 0:
        print(f"\n[INFO] D={D}: selecting {abs(D)} trio(s) of (2 littles + 1 big)...")
    else:
        print("\n[INFO] D=0: equal counts — pure 1-to-1 matching, no trios.")

    trios_2bigs, trios_2littles = select_trios(D, fresh_pool, soph_pool, fresh_prefs, soph_prefs)

    for fresh, b1, b2 in trios_2bigs:
        print(f"[INFO] 2-big trio: {fresh!r} ↔ {b1!r} & {b2!r}")
    for f1, f2, soph in trios_2littles:
        print(f"[INFO] 2-little trio: {f1!r} & {f2!r} ↔ {soph!r}")

    # 7. Remove trio members from pool, then run 1-to-1 matching
    trio_fresh_used = {f for f, _, _ in trios_2bigs} | {f1 for f1, _, _ in trios_2littles} | {f2 for _, f2, _ in trios_2littles}
    trio_soph_used  = {b1 for _, b1, _ in trios_2bigs} | {b2 for _, _, b2 in trios_2bigs} | {s for _, _, s in trios_2littles}
    remaining_fresh = [f for f in fresh_pool if f not in trio_fresh_used]
    remaining_soph  = [s for s in soph_pool  if s not in trio_soph_used]

    assert len(remaining_fresh) == len(remaining_soph), (
        f"Pool mismatch after trio removal: {len(remaining_fresh)} fresh vs {len(remaining_soph)} sophs"
    )

    print(f"[INFO] Optimising {len(remaining_fresh)} 1-to-1 pairings...")
    duo_matches = optimize_matching(remaining_fresh, remaining_soph, fresh_prefs, soph_prefs)

    # 8. Incorporate overrides into the match lists
    override_trios_2bigs:   list[tuple[str, str, str]] = []
    override_trios_2littles: list[tuple[str, str, str]] = []
    override_duos: dict[str, str] = {}
    for ov in overrides:
        f1, f2, b1, b2 = ov["freshman_1"], ov["freshman_2"], ov["big_1"], ov["big_2"]
        if f2:
            override_trios_2littles.append((f1, f2, b1))
        elif b2:
            override_trios_2bigs.append((f1, b1, b2))
        else:
            override_duos[f1] = b1

    all_duos        = {**duo_matches, **override_duos}
    all_trios_2bigs = trios_2bigs + override_trios_2bigs
    all_trios_2lit  = trios_2littles + override_trios_2littles

    # 9. Build output and satisfaction scores
    output_df = build_output(all_duos, all_trios_2bigs, all_trios_2lit)
    sat_df    = compute_satisfaction(all_duos, all_trios_2bigs, all_trios_2lit, fresh_prefs, soph_prefs)

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
