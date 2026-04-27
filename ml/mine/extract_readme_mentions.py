"""
Step 3: Extract file mentions from README.md per repo via BigQuery.

Queries bigquery-public-data.github_repos.contents for README files,
extracts file references, and fuzzy-matches them against repo file trees.

Output columns: full_name, file_path, readme_score
"""

import os
import re
import pandas as pd
from collections import defaultdict
from google.cloud import bigquery
from rapidfuzz import process, fuzz
from tqdm import tqdm

REPOS_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/readme.parquet")
PAGERANK_PATH = os.path.join(os.path.dirname(__file__), "../data/pagerank.parquet")

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

PATH_PATTERN = re.compile(
    r"`([^`]{3,60})`"
    r"|(\w[\w/.\-]{2,59}\.\w+)"
)
TREE_LINE_PATTERN = re.compile(r"[├└│\s\-]+(\S+\.\w+)")


def extract_path_candidates(text: str) -> list[str]:
    candidates = []
    for m in PATH_PATTERN.finditer(text):
        val = m.group(1) or m.group(2)
        if val:
            candidates.append(val.strip())
    for m in TREE_LINE_PATTERN.finditer(text):
        candidates.append(m.group(1).strip())
    return candidates


def match_to_files(candidates: list[str], source_files: list[str], threshold: int = 80) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    if not source_files:
        return counts
    basenames = [os.path.basename(f) for f in source_files]
    for candidate in candidates:
        candidate_base = os.path.basename(candidate)
        if os.path.splitext(candidate_base)[1] not in SOURCE_EXTENSIONS:
            continue
        if candidate in source_files:
            counts[candidate] += 1
            continue
        result = process.extractOne(candidate_base, basenames, scorer=fuzz.ratio, score_cutoff=threshold)
        if result:
            _, _, idx = result
            counts[source_files[idx]] += 1
    return counts


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Only query repos we already have pagerank data for
    pagerank_df = pd.read_parquet(PAGERANK_PATH)
    repo_list = pagerank_df["full_name"].unique().tolist()

    # Use pagerank file tree as our known source files per repo
    pagerank_df = pd.read_parquet(PAGERANK_PATH)
    file_map = pagerank_df.groupby("full_name")["file_path"].apply(list).to_dict()

    print(f"Extracting README mentions for {len(repo_list)} repos via BigQuery...")
    client = bigquery.Client()

    batch_size = 50
    results = []

    for i in tqdm(range(0, len(repo_list), batch_size)):
        batch = repo_list[i:i + batch_size]
        repo_filter = ", ".join([f"'{r}'" for r in batch])

        query = f"""
            SELECT repo_name, path, content
            FROM `bigquery-public-data.github_repos.contents`
            JOIN `bigquery-public-data.github_repos.files`
              ON `bigquery-public-data.github_repos.contents`.id = `bigquery-public-data.github_repos.files`.id
            WHERE repo_name IN ({repo_filter})
              AND LOWER(path) LIKE '%readme%'
              AND content IS NOT NULL
        """

        try:
            df = client.query(query).to_dataframe()
        except Exception as e:
            print(f"  Batch {i//batch_size} failed: {e}")
            continue

        for repo_name, group in df.groupby("repo_name"):
            source_files = file_map.get(repo_name, [])
            if not source_files:
                continue
            readme_text = " ".join(group["content"].dropna().tolist())
            candidates = extract_path_candidates(readme_text)
            counts = match_to_files(candidates, source_files)
            for fp, count in counts.items():
                results.append({"full_name": repo_name, "file_path": fp, "readme_score": count})

    out_df = pd.DataFrame(results)
    out_df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(out_df)} file scores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
