"""
Step 5: Score files by unique contributor count from commit history via BigQuery.

Queries bigquery-public-data.github_repos.commits for file-level commit data.

Output columns: full_name, file_path, unique_contributor_count, commit_frequency
"""

import os
import pandas as pd
from google.cloud import bigquery
from tqdm import tqdm

REPOS_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/commit_history.parquet")

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

BOT_SUBSTRINGS = {"bot", "dependabot", "renovate", "greenkeeper", "snyk", "github-actions"}


def is_bot(login: str) -> bool:
    login_lower = login.lower()
    return any(sub in login_lower for sub in BOT_SUBSTRINGS)


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Only query repos we already have pagerank data for
    pagerank_df = pd.read_parquet(os.path.join(os.path.dirname(__file__), "../data/pagerank.parquet"))
    repo_list = pagerank_df["full_name"].unique().tolist()

    print(f"Extracting commit history for {len(repo_list)} repos via BigQuery...")
    client = bigquery.Client()

    ext_conditions = " OR ".join([f"diff.new_path LIKE '%.{ext.lstrip(chr(46))}'" for ext in SOURCE_EXTENSIONS])

    batch_size = 50
    results = []

    for i in tqdm(range(0, len(repo_list), batch_size)):
        batch = repo_list[i:i + batch_size]
        repo_filter = ", ".join([f"'{r}'" for r in batch])

        query = f"""
            SELECT
              repo_name,
              author.name AS author,
              diff.new_path AS file_path
            FROM `bigquery-public-data.github_repos.commits`,
              UNNEST(difference) AS diff
            WHERE repo_name IN ({repo_filter})
              AND ({ext_conditions})
              AND diff.new_path IS NOT NULL
        """

        try:
            df = client.query(query).to_dataframe()
        except Exception as e:
            print(f"  Batch {i//batch_size} failed: {e}")
            continue

        # Filter bots
        df = df[~df["author"].str.lower().apply(lambda a: any(b in a for b in BOT_SUBSTRINGS))]

        for (repo_name, file_path), group in df.groupby(["repo_name", "file_path"]):
            unique_authors = group["author"].nunique()
            commit_freq = len(group)
            results.append({
                "full_name": repo_name,
                "file_path": file_path,
                "unique_contributor_count": unique_authors,
                "commit_frequency": commit_freq,
            })

    out_df = pd.DataFrame(results)
    out_df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(out_df)} file scores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
