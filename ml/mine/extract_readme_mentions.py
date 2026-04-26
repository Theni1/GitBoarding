"""
Step 5: Extract file mentions from README.md per repo.

Same approach as extract_contributing.py but for README files.
READMEs often call out key files in code blocks, architecture sections,
and "project structure" trees — those are strong curation signals.

For each repo in repos.parquet:
  1. Fetch README (GitHub API returns the default README regardless of filename)
  2. Extract candidate file references (backtick-quoted + bare path-like tokens)
  3. Also parse ASCII directory trees (lines like "│   ├── foo.py")
  4. Fuzzy-match candidates against actual repo file tree
  5. Score each file by mention count

Output columns: full_name, file_path, readme_score
"""

import os
import re
import time
import base64
import pandas as pd
import requests
from collections import defaultdict
from dotenv import load_dotenv
from rapidfuzz import process, fuzz
from tqdm import tqdm

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
REPOS_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/readme.parquet")

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

# Backtick-quoted or bare path-like tokens
PATH_PATTERN = re.compile(
    r"`([^`]{3,60})`"            # `src/foo.py`
    r"|(\w[\w/.\-]{2,59}\.\w+)"  # bare: src/foo.py
)

# ASCII directory tree lines: "├── foo.py" or "│   └── bar.ts"
TREE_LINE_PATTERN = re.compile(r"[├└│\s\-]+(\S+\.\w+)")


def gh_get(url: str, params: dict = None) -> requests.Response:
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 0) + 5
            print(f"  Rate limited. Waiting {wait:.0f}s...")
            time.sleep(wait)
            continue
        return resp


def fetch_readme(owner: str, repo: str) -> str | None:
    """GitHub's /readme endpoint returns the repo's default README regardless of filename."""
    resp = gh_get(f"https://api.github.com/repos/{owner}/{repo}/readme")
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            return None
    return None


def get_file_tree(owner: str, repo: str, branch: str) -> list[str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
    resp = gh_get(url, params={"recursive": "1"})
    if resp.status_code != 200:
        return []
    return [item["path"] for item in resp.json().get("tree", []) if item["type"] == "blob"]


def extract_path_candidates(text: str) -> list[str]:
    candidates = []

    # Standard inline references
    for m in PATH_PATTERN.finditer(text):
        val = m.group(1) or m.group(2)
        if val:
            candidates.append(val.strip())

    # ASCII directory tree lines (common in READMEs)
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


def process_repo(owner: str, repo: str, branch: str) -> list[dict]:
    readme_text = fetch_readme(owner, repo)
    if not readme_text:
        return []

    all_paths = get_file_tree(owner, repo, branch)
    source_files = [p for p in all_paths if os.path.splitext(p)[1] in SOURCE_EXTENSIONS]
    if not source_files:
        return []

    candidates = extract_path_candidates(readme_text)
    counts = match_to_files(candidates, source_files)
    if not counts:
        return []

    full_name = f"{owner}/{repo}"
    return [
        {"full_name": full_name, "file_path": fp, "readme_score": count}
        for fp, count in counts.items()
    ]


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    repos_df = pd.read_parquet(REPOS_PATH)
    print(f"Extracting README mentions for {len(repos_df)} repos...")

    results = []
    for _, row in tqdm(repos_df.iterrows(), total=len(repos_df)):
        try:
            rows = process_repo(row["owner"], row["name"], row["default_branch"])
            results.extend(rows)
        except Exception as e:
            print(f"  Skipping {row['full_name']}: {e}")
        time.sleep(0.1)

    df = pd.DataFrame(results)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} file scores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
