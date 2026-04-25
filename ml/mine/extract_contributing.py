"""
Step 3: Extract file mentions from CONTRIBUTING.md per repo.

For each repo in repos.parquet:
  1. Fetch CONTRIBUTING.md (try common filenames/locations)
  2. Extract candidate file references (words that look like paths)
  3. Fuzzy-match them against the actual repo file tree
  4. Score each file by how many times it was mentioned

Output columns: full_name, file_path, contributing_score
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
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/contributing.parquet")

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

# Common locations for CONTRIBUTING docs
CONTRIBUTING_CANDIDATES = [
    "CONTRIBUTING.md",
    "contributing.md",
    "CONTRIBUTING.rst",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
]

# Matches backtick-quoted tokens and bare words that look like file paths
PATH_PATTERN = re.compile(
    r"`([^`]{3,60})`"            # `src/foo.py`
    r"|(\w[\w/.\-]{2,59}\.\w+)"  # bare: src/foo.py
)


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


def fetch_contributing(owner: str, repo: str) -> str | None:
    for candidate in CONTRIBUTING_CANDIDATES:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{candidate}"
        resp = gh_get(url)
        if resp.status_code == 200:
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
    for m in PATH_PATTERN.finditer(text):
        val = m.group(1) or m.group(2)
        if val:
            candidates.append(val.strip())
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

        # Exact full-path match first
        if candidate in source_files:
            counts[candidate] += 1
            continue

        # Fuzzy match on basename
        result = process.extractOne(candidate_base, basenames, scorer=fuzz.ratio, score_cutoff=threshold)
        if result:
            _, _, idx = result
            counts[source_files[idx]] += 1

    return counts


def process_repo(owner: str, repo: str, branch: str) -> list[dict]:
    contributing_text = fetch_contributing(owner, repo)
    if not contributing_text:
        return []

    all_paths = get_file_tree(owner, repo, branch)
    source_files = [p for p in all_paths if os.path.splitext(p)[1] in SOURCE_EXTENSIONS]
    if not source_files:
        return []

    candidates = extract_path_candidates(contributing_text)
    counts = match_to_files(candidates, source_files)
    if not counts:
        return []

    full_name = f"{owner}/{repo}"
    return [
        {"full_name": full_name, "file_path": fp, "contributing_score": count}
        for fp, count in counts.items()
    ]


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    repos_df = pd.read_parquet(REPOS_PATH)
    print(f"Extracting CONTRIBUTING.md mentions for {len(repos_df)} repos...")

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
