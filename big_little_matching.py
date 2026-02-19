"""
Big-Little Matching Algorithm for Sigma Nu Fraternity
======================================================
Optimises many-to-one matching between Sophomores (Bigs) and Freshmen (Littles)
using the Hungarian algorithm to maximise total combined satisfaction.

Special handling:
- 29 Bigs, 28 Littles => one Little must form a "Trio" with 2 Bigs.
- Trio selection is optimized by mutual preference scores.
- Main matching maximises sum of both sides' satisfaction scores equally.

Input CSVs:
  sophomores.csv  — columns: Name, Rank1, Rank2, Rank3, Rank4, Rank5
  freshmen.csv    — columns: Name, Rank1, Rank2, Rank3, Rank4, Rank5
"""

import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from difflib import get_close_matches
import sys
from collections import defaultdict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PREF_COLS = ["Rank1", "Rank2", "Rank3", "Rank4", "Rank5"]
SOPHOMORES_FILE = "sophomores.csv"
FRESHMEN_FILE = "freshmen.csv"
OUTPUT_FILE = "final_matches.csv"
FUZZY_CUTOFF = 0.75   # similarity threshold for name-mismatch suggestions
MAX_RANK = len(PREF_COLS)  # 5
# Blending weight: product is primary objective, average is tiebreaker.
# α < (min_mutual_product - max_one_sided_product) / (max_one_sided_avg - min_mutual_avg)
# i.e. α < (4 - 0) / (50 - 0) ≈ 0.133  →  any mutual pair still beats any one-sided pair.
ALPHA = 0.1


def rank_to_score(rank: int | None) -> float:
    """
    Convert a choice rank to a satisfaction percentage.
      Rank 1 -> 100%, Rank 2 -> 80%, …, Rank 5 -> 20%, Unranked -> 0%
    Formula: (MAX_RANK + 1 - rank) / MAX_RANK * 100
    """
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

    # Strip whitespace inside preference cells
    for col in PREF_COLS:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

    print(f"[INFO] Loaded {len(df)} {group_name}.")
    return df.reset_index(drop=True)


def check_name_mismatches(
    prefs_df: pd.DataFrame,
    valid_names: set,
    ranker_group: str,
    ranked_group: str,
) -> dict[str, str]:
    """
    Scan every preference cell. Warn about names that don't match the
    valid roster. Suggest fuzzy corrections where possible.

    Returns a correction map  {bad_name: corrected_name}  based on
    unambiguous fuzzy matches; ambiguous or un-fixable entries stay empty.
    """
    corrections: dict[str, str] = {}
    seen_bad: set[str] = set()

    for _, row in prefs_df.iterrows():
        for col in PREF_COLS:
            name = row[col]
            if not name or name in valid_names:
                continue
            if name in seen_bad:
                continue
            seen_bad.add(name)

            matches = get_close_matches(name, valid_names, n=3, cutoff=FUZZY_CUTOFF)
            if len(matches) == 1:
                print(
                    f"[WARNING] {ranker_group} '{row['Name']}' ranked "
                    f"'{name}' in {col} — not found in {ranked_group} roster. "
                    f"Auto-correcting to '{matches[0]}'."
                )
                corrections[name] = matches[0]
            elif matches:
                print(
                    f"[WARNING] {ranker_group} '{row['Name']}' ranked "
                    f"'{name}' in {col} — not found. Possible matches: "
                    f"{matches}. Please fix manually; this entry will be ignored."
                )
            else:
                print(
                    f"[WARNING] {ranker_group} '{row['Name']}' ranked "
                    f"'{name}' in {col} — no close match found; entry ignored."
                )

    return corrections


def apply_corrections(df: pd.DataFrame, corrections: dict[str, str]) -> pd.DataFrame:
    """Replace misspelled names in preference columns with corrected versions."""
    for col in PREF_COLS:
        df[col] = df[col].replace(corrections)
    return df


def build_preference_lists(
    df: pd.DataFrame, valid_names: set
) -> dict[str, list[str]]:
    """
    Build ordered preference lists, filtering out invalid / empty entries
    and de-duplicating while preserving order.
    """
    prefs: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        name = row["Name"]
        seen = set()
        ordered = []
        for col in PREF_COLS:
            val = row[col]
            if val and val in valid_names and val not in seen:
                ordered.append(val)
                seen.add(val)
        prefs[name] = ordered
    return prefs


# ---------------------------------------------------------------------------
# Mutual Score — used to select the best Trio candidate
# ---------------------------------------------------------------------------

def mutual_score(
    fresh: str,
    soph: str,
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
    max_rank: int = 5,
) -> float:
    """
    Combined mutual preference score (lower = more mutually preferred).

    Score = (fresh_rank_of_soph + soph_rank_of_fresh) / 2
    If either party did not rank the other, a penalty of (max_rank + 1) is used.
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

def select_trio(
    freshmen_names: list[str],
    sophomores_names: list[str],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> tuple[str, str, str]:
    """
    Find the (freshman, big1, big2) trio that minimises:
        mutual_score(fresh, big1) + mutual_score(fresh, big2)
    subject to big1 != big2.

    This ensures the Trio is the most mutually enthusiastic 3-way grouping.
    Returns (trio_freshman, primary_big, secondary_big).
    """
    best_score = float("inf")
    best_trio: tuple[str, str, str] = ("", "", "")

    for fresh in freshmen_names:
        # Rank sophomores by mutual score for this freshman
        scored = sorted(
            sophomores_names,
            key=lambda s: mutual_score(fresh, s, fresh_prefs, soph_prefs),
        )
        # Try the top-K pairs to keep complexity manageable (K=10 covers all real cases)
        top_k = scored[:10]
        for i, big1 in enumerate(top_k):
            for big2 in top_k[i + 1 :]:
                score = (
                    mutual_score(fresh, big1, fresh_prefs, soph_prefs)
                    + mutual_score(fresh, big2, fresh_prefs, soph_prefs)
                )
                if score < best_score:
                    best_score = score
                    best_trio = (fresh, big1, big2)

    return best_trio


# ---------------------------------------------------------------------------
# Optimal Matching — maximise total combined satisfaction (Hungarian algorithm)
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
      (product term prioritises mutual rankings; average term breaks ties
       when the product is 0 so non-mutual pairs are still ordered sensibly.)

    Median maximisation algorithm:
      1. Build the n×n pair-score matrix.
      2. Iterate over all distinct score values t in descending order.
         For each t, check (via a binary assignment) whether a perfect
         matching exists in which ≥ ⌈n/2⌉ pairs score ≥ t.
         The first t that passes is the highest achievable median.
      3. Re-run the assignment with a large bonus for pairs that meet the
         target, maximising the sum among equally-good medians as a tiebreaker.

    Returns: {freshman -> sophomore} mapping.
    """
    n = len(freshmen)   # == len(sophomores) after trio removal

    # Build pair-score matrix
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

    # Step 1 — find the highest achievable median threshold
    target = (n + 1) // 2          # number of pairs that must hit the threshold
    distinct = sorted(set(scores.flatten()), reverse=True)

    best_t = 0.0
    for t in distinct:
        above = (scores >= t - 1e-9).astype(float)
        ri, ci = linear_sum_assignment(-above)
        if above[ri, ci].sum() >= target:
            best_t = t
            break

    # Step 2 — assign with a large bonus for pairs that meet best_t;
    #           maximise sum among equally-good solutions as tiebreaker
    BIG = 10_000.0
    final = np.where(scores >= best_t - 1e-9, BIG + scores, scores)
    row_ind, col_ind = linear_sum_assignment(-final)
    return {freshmen[i]: sophomores[j] for i, j in zip(row_ind, col_ind)}


# ---------------------------------------------------------------------------
# Satisfaction Scoring
# ---------------------------------------------------------------------------

def compute_satisfaction(
    matches: dict[str, str],
    trio_fresh: str,
    trio_bigs: tuple[str, str],
    fresh_prefs: dict[str, list[str]],
    soph_prefs: dict[str, list[str]],
) -> pd.DataFrame:
    """
    One row per freshman. Columns:
      Freshman, Big_1, Big_2, Freshman_Score, Big_1_Score, Big_2_Score
    Regular pairs have Big_2 / Big_2_Score blank. Trio freshman scores are
    averaged across both bigs for Freshman_Score.
    """
    rows = []

    # --- Regular pairings ---
    for fresh, soph in matches.items():
        fp = fresh_prefs.get(fresh, [])
        sp = soph_prefs.get(soph, [])
        r_fresh = fp.index(soph) + 1 if soph in fp else None
        r_soph  = sp.index(fresh) + 1 if fresh in sp else None
        fs = rank_to_score(r_fresh)
        bs = rank_to_score(r_soph)
        rows.append({
            "Freshman":       fresh,
            "Big_1":          soph,
            "Big_2":          "",
            "Freshman_Score": fs,
            "Big_1_Score":    bs,
            "Big_2_Score":    None,
            "Pair_Score":     fs * bs / 100 + ALPHA * (fs + bs) / 2,
        })

    # --- Trio pairing (one averaged row) ---
    if trio_fresh:
        big1, big2 = trio_bigs
        fp  = fresh_prefs.get(trio_fresh, [])
        sp1 = soph_prefs.get(big1, [])
        sp2 = soph_prefs.get(big2, [])

        r_f1 = fp.index(big1) + 1 if big1 in fp else None
        r_f2 = fp.index(big2) + 1 if big2 in fp else None
        r_b1 = sp1.index(trio_fresh) + 1 if trio_fresh in sp1 else None
        r_b2 = sp2.index(trio_fresh) + 1 if trio_fresh in sp2 else None

        fs  = (rank_to_score(r_f1) + rank_to_score(r_f2)) / 2
        b1s = rank_to_score(r_b1)
        b2s = rank_to_score(r_b2)
        rows.append({
            "Freshman":       trio_fresh,
            "Big_1":          big1,
            "Big_2":          big2,
            "Freshman_Score": fs,
            "Big_1_Score":    b1s,
            "Big_2_Score":    b2s,
            "Pair_Score":     fs * b1s * b2s / 10000 + ALPHA * (fs + b1s + b2s) / 3,
        })

    return pd.DataFrame(rows).sort_values("Freshman").reset_index(drop=True)


def print_satisfaction_summary(sat_df: pd.DataFrame) -> None:
    """Print a formatted satisfaction breakdown."""
    print("\n" + "=" * 58)
    print("  SATISFACTION SUMMARY")
    print("=" * 58)

    score_labels = {rank_to_score(r): f"{rank_to_score(r):.0f}%" for r in range(1, MAX_RANK + 1)}
    score_labels[0.0] = "0% (Unranked)"

    def show_dist(scores: pd.Series, label: str) -> None:
        print(f"\n  {label} ({len(scores)} people):")
        for score, cnt in scores.value_counts().sort_index(ascending=False).items():
            lbl = score_labels.get(score, f"{score:.0f}%")
            print(f"    {lbl:15s} : {cnt:>3} person(s)")
        print(f"    Average score : {scores.mean():.1f}%")

    show_dist(sat_df["Pair_Score"], "Pair scores")
    show_dist(sat_df["Freshman_Score"], "Freshmen")
    show_dist(
        pd.concat([sat_df["Big_1_Score"], sat_df["Big_2_Score"].dropna()]).reset_index(drop=True),
        "Sophomores",
    )

    pair_scores = sat_df["Pair_Score"].sort_values().reset_index(drop=True)
    median = pair_scores.iloc[len(pair_scores) // 2]
    print(f"\n  Median pair score : {median:.1f}")
    print(f"  Average pair score: {pair_scores.mean():.1f}")
    print("=" * 58 + "\n")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_output(
    matches: dict[str, str],
    trio_fresh: str,
    trio_bigs: tuple[str, str],
) -> pd.DataFrame:
    """Construct a clean output DataFrame of all pairings."""
    rows = []
    for fresh, soph in matches.items():
        rows.append({"Freshman": fresh, "Big_1": soph, "Big_2": "", "Trio": False})

    if trio_fresh:
        rows.append({
            "Freshman": trio_fresh,
            "Big_1": trio_bigs[0],
            "Big_2": trio_bigs[1],
            "Trio": True,
        })

    df = pd.DataFrame(rows).sort_values("Freshman").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n====================================================")
    print("   Sigma Nu Big-Little Matching Algorithm")
    print("====================================================\n")

    # 1. Load data
    sophs_df = load_and_validate(SOPHOMORES_FILE, "Sophomores")
    fresh_df = load_and_validate(FRESHMEN_FILE, "Freshmen")

    soph_names = set(sophs_df["Name"])
    fresh_names = set(fresh_df["Name"])

    # 2. Detect and correct name mismatches
    print("\n[INFO] Checking for name mismatches in Freshman rankings...")
    fresh_corrections = check_name_mismatches(
        fresh_df, soph_names, "Freshman", "Sophomore"
    )
    fresh_df = apply_corrections(fresh_df, fresh_corrections)

    print("[INFO] Checking for name mismatches in Sophomore rankings...")
    soph_corrections = check_name_mismatches(
        sophs_df, fresh_names, "Sophomore", "Freshman"
    )
    sophs_df = apply_corrections(sophs_df, soph_corrections)

    # 3. Build preference lists
    fresh_prefs = build_preference_lists(fresh_df, soph_names)
    soph_prefs = build_preference_lists(sophs_df, fresh_names)

    freshmen_list = list(fresh_names)
    sophomores_list = list(soph_names)

    # 4. Select Trio (the one Little who gets two Bigs)
    print("\n[INFO] Identifying optimal Trio (2-Big, 1-Little pairing)...")
    trio_fresh, trio_big1, trio_big2 = select_trio(
        freshmen_list, sophomores_list, fresh_prefs, soph_prefs
    )
    print(
        f"[INFO] Trio selected: Freshman '{trio_fresh}' "
        f"matched with '{trio_big1}' and '{trio_big2}'."
    )

    # 5. Remove trio members from the main 1-to-1 pool
    remaining_freshmen = [f for f in freshmen_list if f != trio_fresh]
    remaining_sophs = [s for s in sophomores_list if s not in {trio_big1, trio_big2}]

    # Sanity check: should be equal now (27 each)
    assert len(remaining_freshmen) == len(remaining_sophs), (
        f"Size mismatch after Trio removal: "
        f"{len(remaining_freshmen)} freshmen vs {len(remaining_sophs)} sophs"
    )

    # 6. Optimise matching to maximise total combined satisfaction
    print("[INFO] Optimising matching to maximise total satisfaction...")
    gs_matches = optimize_matching(
        remaining_freshmen, remaining_sophs, fresh_prefs, soph_prefs
    )

    # 7. Build output & satisfaction
    output_df = build_output(gs_matches, trio_fresh, (trio_big1, trio_big2))
    sat_df = compute_satisfaction(
        gs_matches, trio_fresh, (trio_big1, trio_big2), fresh_prefs, soph_prefs
    )

    # 8. Print results
    print("\n[RESULTS] Final Pairings:")
    print(output_df.to_string(index=False))
    print_satisfaction_summary(sat_df)

    # 9. Save outputs
    output_df.to_csv(OUTPUT_FILE, index=False)
    sat_df.to_csv("satisfaction_scores.csv", index=False)
    print(f"[INFO] Saved pairings to '{OUTPUT_FILE}'")
    print("[INFO] Saved satisfaction scores to 'satisfaction_scores.csv'\n")


if __name__ == "__main__":
    main()
