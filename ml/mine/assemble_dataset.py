"""
Step 7: Join all signal parquets into one training-ready dataset.

Reads:
  - ml/data/pagerank.parquet        (full_name, file_path, pagerank_score)
  - ml/data/contributing.parquet    (full_name, file_path, contributing_score)
  - ml/data/first_prs.parquet       (full_name, file_path, first_pr_score)
  - ml/data/readme.parquet          (full_name, file_path, readme_score)
  - ml/data/commit_history.parquet  (full_name, file_path, unique_contributor_count, commit_frequency)
  - ml/data/repos.parquet           (full_name, default_branch, ...)

Outputs:
  - ml/data/dataset.parquet

One row per (full_name, file_path) with:
  - 5 normalized signal scores         [0, 1] within each repo
  - 3 structural features              file_depth, file_ext_id, is_entrypoint
  - 1 consensus label                  important = 1 if ≥2 signals agree
"""

import os
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
OUTPUT_PATH = os.path.join(DATA_DIR, "dataset.parquet")

# Signals and their column names in source parquets
SIGNALS = [
    ("pagerank.parquet",       "pagerank_score"),
    ("contributing.parquet",   "contributing_score"),
    ("first_prs.parquet",      "first_pr_score"),
    ("readme.parquet",         "readme_score"),
    ("commit_history.parquet", "unique_contributor_count"),
    ("commit_history.parquet", "commit_frequency"),
]

# A signal "fires" for a file if its normalized score is above this threshold
SIGNAL_THRESHOLD = 0.3

# File must have >= this many signals fire to be labeled important
MIN_SIGNALS_FOR_LABEL = 2

# Common entrypoint filenames — structural prior the GNN can learn from
ENTRYPOINTS = {
    "main.py", "app.py", "index.py", "__init__.py",
    "index.js", "index.ts", "app.js", "app.ts",
    "main.go", "main.java", "Application.java",
}

EXTENSION_MAP = {
    ".py": 0, ".js": 1, ".ts": 2, ".jsx": 3,
    ".tsx": 4, ".go": 5, ".java": 6,
}


def load_signal(filename: str, score_col: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"  Warning: {filename} not found, filling with zeros")
        return pd.DataFrame(columns=["full_name", "file_path", score_col])
    df = pd.read_parquet(path)[["full_name", "file_path", score_col]]
    return df


def normalize_within_repo(df: pd.DataFrame, col: str) -> pd.Series:
    """Min-max normalize col to [0,1] within each repo so scores are comparable across repos."""
    def _norm(group):
        mn, mx = group[col].min(), group[col].max()
        if mx == mn:
            return pd.Series(0.0, index=group.index)
        return (group[col] - mn) / (mx - mn)
    return df.groupby("full_name", group_keys=False).apply(_norm)


def add_structural_features(df: pd.DataFrame) -> pd.DataFrame:
    df["file_depth"] = df["file_path"].str.count("/")
    df["file_ext"] = df["file_path"].apply(lambda p: os.path.splitext(p)[1].lower())
    df["file_ext_id"] = df["file_ext"].map(EXTENSION_MAP).fillna(-1).astype(int)
    df["is_entrypoint"] = df["file_path"].apply(
        lambda p: int(os.path.basename(p) in ENTRYPOINTS)
    )
    return df.drop(columns=["file_ext"])


def build_consensus_label(df: pd.DataFrame, norm_signal_cols: list[str]) -> pd.Series:
    """
    Label a file as important (1) if at least MIN_SIGNALS_FOR_LABEL of its
    normalized signal scores exceed SIGNAL_THRESHOLD.
    Files where multiple independent signals agree are high-confidence positives.
    """
    fires = (df[norm_signal_cols] > SIGNAL_THRESHOLD).sum(axis=1)
    return (fires >= MIN_SIGNALS_FOR_LABEL).astype(int)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # pagerank is our anchor — it covers every source file we parsed
    print("Loading pagerank (anchor)...")
    base = load_signal("pagerank.parquet", "pagerank_score")
    if base.empty:
        raise RuntimeError("pagerank.parquet is required but missing. Run compute_pagerank.py first.")

    # Left-join each additional signal onto the base
    signal_cols = ["pagerank_score"]
    seen_files = set()  # track (filename, col) pairs to avoid double-loading commit_history

    for filename, score_col in SIGNALS[1:]:
        key = (filename, score_col)
        if key in seen_files:
            continue
        seen_files.add(key)

        # commit_history has two columns — load both at once
        if filename == "commit_history.parquet":
            path = os.path.join(DATA_DIR, filename)
            if os.path.exists(path):
                ch = pd.read_parquet(path)[["full_name", "file_path", "unique_contributor_count", "commit_frequency"]]
                base = base.merge(ch, on=["full_name", "file_path"], how="left")
                signal_cols += ["unique_contributor_count", "commit_frequency"]
            else:
                print(f"  Warning: {filename} not found, filling with zeros")
                base["unique_contributor_count"] = 0.0
                base["commit_frequency"] = 0.0
                signal_cols += ["unique_contributor_count", "commit_frequency"]
            seen_files.add(("commit_history.parquet", "commit_frequency"))
        else:
            sig = load_signal(filename, score_col)
            base = base.merge(sig, on=["full_name", "file_path"], how="left")
            signal_cols.append(score_col)

    base[signal_cols] = base[signal_cols].fillna(0.0)

    print(f"Loaded {len(base):,} file rows across {base['full_name'].nunique():,} repos")

    # Normalize each signal within its repo
    print("Normalizing signals within repos...")
    norm_cols = []
    for col in signal_cols:
        norm_col = f"{col}_norm"
        base[norm_col] = normalize_within_repo(base, col)
        norm_cols.append(norm_col)

    # Structural features
    print("Adding structural features...")
    base = add_structural_features(base)

    # Consensus label
    print("Building consensus labels...")
    base["important"] = build_consensus_label(base, norm_cols)

    label_rate = base["important"].mean()
    print(f"  Label rate: {label_rate:.1%} of files marked important")

    if label_rate < 0.02 or label_rate > 0.5:
        print(f"  Warning: label rate {label_rate:.1%} looks off — check signal thresholds")

    # Drop raw (un-normalized) signal cols to keep the dataset clean
    # The GNN uses normalized scores; raw values are in the source parquets if needed
    base = base.drop(columns=signal_cols)

    base.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved dataset with {len(base):,} rows and {len(base.columns)} columns to {OUTPUT_PATH}")
    print(f"Columns: {list(base.columns)}")


if __name__ == "__main__":
    main()
