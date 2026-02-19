"""
Randomize Rankings
==================
Randomly re-assigns the Rank1–Rank5 preference columns in freshmen.csv
and sophomores.csv, keeping all names intact.

Run:  python randomize_rankings.py
"""

import pandas as pd
import random

FRESHMEN_FILE  = "freshmen.csv"
SOPHOMORES_FILE = "sophomores.csv"
PREF_COLS = ["Rank1", "Rank2", "Rank3", "Rank4", "Rank5"]


def randomize(df: pd.DataFrame, pool: list[str]) -> pd.DataFrame:
    """Replace each row's preference columns with a random sample from pool."""
    for idx in df.index:
        picks = random.sample(pool, len(PREF_COLS))
        for col, pick in zip(PREF_COLS, picks):
            df.at[idx, col] = pick
    return df


fresh_df = pd.read_csv(FRESHMEN_FILE)
soph_df  = pd.read_csv(SOPHOMORES_FILE)

fresh_names = fresh_df["Name"].tolist()
soph_names  = soph_df["Name"].tolist()

fresh_df = randomize(fresh_df, soph_names)
soph_df  = randomize(soph_df,  fresh_names)

fresh_df.to_csv(FRESHMEN_FILE,  index=False)
soph_df.to_csv(SOPHOMORES_FILE, index=False)

print(f"Randomized {len(fresh_df)} freshmen  → {FRESHMEN_FILE}")
print(f"Randomized {len(soph_df)} sophomores → {SOPHOMORES_FILE}")
