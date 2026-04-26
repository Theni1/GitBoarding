"""
Step 6: Score files by unique contributor count from codebase commit history.

For each repo in repos.parquet:
  1. Fetch all commit metadata (SHA + author) up to MAX_META cap
  2. If total commits > SAMPLE_TARGET, sample SAMPLE_TARGET uniformly across history
     to avoid recency bias on large repos
  3. Fetch file details for each sampled commit
  4. Build: file → set of unique author logins
  5. Score = unique_contributor_count (how many distinct people touched this file)
     Secondary: commit_frequency (raw appearances across sampled commits)

Why unique contributor count:
  Files touched by many different authors are structurally central — every contributor
  eventually needed to read and modify them. Commit frequency alone is noisy (lock files,
  auto-generated files commit constantly but from the same few people).

Sampling strategy (Option C hybrid):
  - ≤ SAMPLE_TARGET commits → fetch all
  - >  SAMPLE_TARGET commits → fetch metadata for up to MAX_META commits,
    then sample SAMPLE_TARGET uniformly so we get coverage across full history

Output columns: full_name, file_path, unique_contributor_count, commit_frequency
"""

import os
import time
import random
import pandas as pd
import requests
from collections import defaultdict
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
REPOS_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/commit_history.parquet")

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

SAMPLE_TARGET = 500   # max commits to fetch file details for
MAX_META = 2000       # max commit metadata pages to scan (2000 commits = 20 pages)
PER_PAGE = 100

BOT_SUBSTRINGS = {"bot", "dependabot", "renovate", "greenkeeper", "snyk", "github-actions"}


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


def is_bot(login: str) -> bool:
    login_lower = login.lower()
    return any(sub in login_lower for sub in BOT_SUBSTRINGS)


def fetch_commit_metadata(owner: str, repo: str, branch: str) -> list[dict]:
    """
    Fetch up to MAX_META commits (SHA + author login only).
    Stops early if we run out of pages.
    """
    commits = []
    page = 1
    while len(commits) < MAX_META:
        resp = gh_get(
            f"https://api.github.com/repos/{owner}/{repo}/commits",
            params={"sha": branch, "per_page": PER_PAGE, "page": page},
        )
        if resp.status_code != 200:
            break
        batch = resp.json()
        if not batch:
            break
        for c in batch:
            login = c.get("author", {}) or {}
            login = login.get("login", "") if isinstance(login, dict) else ""
            commits.append({"sha": c["sha"], "author": login})
        page += 1
        time.sleep(0.05)

    return commits


def fetch_commit_files(owner: str, repo: str, sha: str) -> list[str]:
    """Return source file paths changed in a single commit."""
    resp = gh_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}")
    if resp.status_code != 200:
        return []
    files = resp.json().get("files", [])

    # Skip bulk auto-generated commits (e.g. lockfile regeneration)
    total_changes = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
    if total_changes > 2000:
        return []

    return [
        f["filename"] for f in files
        if os.path.splitext(f.get("filename", ""))[1] in SOURCE_EXTENSIONS
    ]


def process_repo(owner: str, repo: str, branch: str) -> list[dict]:
    all_meta = fetch_commit_metadata(owner, repo, branch)

    # Filter out bot commits before sampling
    all_meta = [c for c in all_meta if not is_bot(c["author"])]

    if not all_meta:
        return []

    # Sample uniformly if we have more commits than the target
    if len(all_meta) > SAMPLE_TARGET:
        step = len(all_meta) / SAMPLE_TARGET
        sampled = [all_meta[int(i * step)] for i in range(SAMPLE_TARGET)]
    else:
        sampled = all_meta

    # file → set of unique authors, file → commit count
    author_sets: dict[str, set] = defaultdict(set)
    commit_counts: dict[str, int] = defaultdict(int)

    for commit in sampled:
        files = fetch_commit_files(owner, repo, commit["sha"])
        for fp in files:
            if commit["author"]:
                author_sets[fp].add(commit["author"])
            commit_counts[fp] += 1
        time.sleep(0.05)

    if not author_sets:
        return []

    full_name = f"{owner}/{repo}"
    return [
        {
            "full_name": full_name,
            "file_path": fp,
            "unique_contributor_count": len(authors),
            "commit_frequency": commit_counts[fp],
        }
        for fp, authors in author_sets.items()
    ]


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    random.seed(42)

    repos_df = pd.read_parquet(REPOS_PATH)
    print(f"Extracting commit history signals for {len(repos_df)} repos...")

    results = []
    for _, row in tqdm(repos_df.iterrows(), total=len(repos_df)):
        try:
            rows = process_repo(row["owner"], row["name"], row["default_branch"])
            results.extend(rows)
        except Exception as e:
            print(f"  Skipping {row['full_name']}: {e}")

    df = pd.DataFrame(results)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} file scores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
