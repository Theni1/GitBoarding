"""
Step 2: Build an import graph for each repo and compute PageRank scores per file.

Uses BigQuery public dataset (bigquery-public-data.github_repos.contents) to fetch
file contents without hitting GitHub API rate limits.

For each repo in repos.parquet:
  1. Query BigQuery for all source file contents in the repo
  2. Extract import statements with regex
  3. Resolve imports to internal files
  4. Build a directed graph and run networkx PageRank
  5. Write scores to ml/data/pagerank.parquet

Output columns: full_name, file_path, pagerank_score
"""

import os
import re
import networkx as nx
import pandas as pd
from google.cloud import bigquery
from tqdm import tqdm

REPOS_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/pagerank.parquet")

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

IMPORT_PATTERNS = [
    re.compile(r"^\s*from\s+([\w./]+)\s+import", re.MULTILINE),
    re.compile(r"^\s*import\s+([\w./]+)", re.MULTILINE),
    re.compile(r"""(?:import\s+.*?from\s+|require\s*\(\s*)['"]([^'"]+)['"]"""),
    re.compile(r'"([\w./\-]+)"'),
    re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE),
]


def extract_raw_imports(content: str) -> list[str]:
    imports = []
    for pattern in IMPORT_PATTERNS:
        imports.extend(pattern.findall(content))
    return imports


def resolve_import(raw: str, source_file: str, all_files: set[str]) -> str | None:
    candidate = raw.replace(".", "/").strip("/")
    source_dir = os.path.dirname(source_file)

    if raw.startswith("."):
        rel = os.path.normpath(os.path.join(source_dir, raw.replace(".", "/").lstrip("/")))
        candidate = rel

    for ext in ["", ".py", ".js", ".ts", ".go", ".java", "/index.js", "/index.ts"]:
        probe = candidate + ext
        if probe in all_files:
            return probe

    basename = candidate.split("/")[-1]
    for f in all_files:
        if os.path.splitext(os.path.basename(f))[0] == basename:
            return f

    return None


def compute_pagerank_for_repo(rows: list[dict]) -> list[dict]:
    source_files = [r["path"] for r in rows]
    all_files_set = set(source_files)

    G = nx.DiGraph()
    G.add_nodes_from(source_files)

    for row in rows:
        path = row["path"]
        content = row["content"] or ""
        for raw in extract_raw_imports(content):
            target = resolve_import(raw, path, all_files_set)
            if target and target != path:
                G.add_edge(path, target)

    scores = nx.pagerank(G, alpha=0.85)
    return [{"file_path": f, "pagerank_score": scores.get(f, 0.0)} for f in source_files]


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    repos_df = pd.read_parquet(REPOS_PATH)
    repo_list = repos_df["full_name"].tolist()
    print(f"Computing PageRank for {len(repo_list)} repos via BigQuery...")

    client = bigquery.Client(project="moonlit-byway-494520-k8")

    # Build extension filter for SQL
    ext_conditions = " OR ".join([f"path LIKE '%.{ext.lstrip(chr(46))}'" for ext in SOURCE_EXTENSIONS])

    # Query in batches of 10 repos — smaller batches are faster per query
    batch_size = 10
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
              AND ({ext_conditions})
              AND content IS NOT NULL
              AND LENGTH(content) < 500000
        """

        try:
            df = client.query(query).to_dataframe()
        except Exception as e:
            print(f"  Batch {i//batch_size} failed: {e}")
            continue

        for repo_name, group in df.groupby("repo_name"):
            rows = group[["path", "content"]].to_dict("records")
            if not rows:
                continue
            try:
                scores = compute_pagerank_for_repo(rows)
                for s in scores:
                    s["full_name"] = repo_name
                results.extend(scores)
            except Exception as e:
                print(f"  Skipping {repo_name}: {e}")

    out_df = pd.DataFrame(results)
    out_df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(out_df)} file scores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
