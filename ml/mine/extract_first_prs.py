"""
Step 4: Score files by how often they appear in first PRs from successful contributors.

For each repo in repos.parquet:
  1. Fetch contributors (paginated)
  2. Filter out bots and anyone with <5 merged PRs (proves successful onboarding)
  3. For each qualifying contributor, find their earliest merged PR to this repo
  4. Fetch the files changed in that PR
  5. Skip trivial PRs (single file, <5 lines changed — likely a typo fix)
  6. Accumulate a mention count per file across all contributors

Output columns: full_name, file_path, first_pr_score
"""

import os
import time
import pandas as pd
import requests
from collections import defaultdict
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
REPOS_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/first_prs.parquet")

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

MIN_CONTRIBUTOR_PRS = 5   # contributor must have at least this many merged PRs
MIN_PR_CHANGES = 5        # skip PRs with fewer total line changes (typo fixes)
MAX_CONTRIBUTORS = 100    # cap per repo to control API usage
MAX_PAGES = 5             # max pages of PRs to scan per contributor

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


def get_contributors(owner: str, repo: str) -> list[str]:
    """Return list of contributor logins, capped at MAX_CONTRIBUTORS."""
    logins = []
    page = 1
    while len(logins) < MAX_CONTRIBUTORS:
        resp = gh_get(
            f"https://api.github.com/repos/{owner}/{repo}/contributors",
            params={"per_page": 100, "page": page, "anon": "false"},
        )
        if resp.status_code != 200:
            break
        items = resp.json()
        if not items:
            break
        for item in items:
            login = item.get("login", "")
            if not is_bot(login):
                logins.append(login)
        page += 1
    return logins[:MAX_CONTRIBUTORS]


def get_merged_pr_count(owner: str, repo: str, login: str) -> int:
    """Count merged PRs by this contributor using the search API."""
    resp = gh_get(
        "https://api.github.com/search/issues",
        params={
            "q": f"repo:{owner}/{repo} is:pr is:merged author:{login}",
            "per_page": 1,
        },
    )
    if resp.status_code != 200:
        return 0
    return resp.json().get("total_count", 0)


def get_first_merged_pr(owner: str, repo: str, login: str) -> dict | None:
    """
    Return the earliest merged PR by this contributor.
    Scans pages of PRs sorted oldest-first.
    """
    for page in range(1, MAX_PAGES + 1):
        resp = gh_get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            params={
                "state": "closed",
                "sort": "created",
                "direction": "asc",
                "per_page": 100,
                "page": page,
            },
        )
        if resp.status_code != 200:
            break
        prs = resp.json()
        if not prs:
            break
        for pr in prs:
            if pr.get("user", {}).get("login") == login and pr.get("merged_at"):
                return pr
    return None


def get_pr_files(owner: str, repo: str, pr_number: int) -> list[dict]:
    """Return list of file dicts from a PR (filename, additions, deletions)."""
    resp = gh_get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
        params={"per_page": 100},
    )
    if resp.status_code != 200:
        return []
    return resp.json()


def process_repo(owner: str, repo: str) -> list[dict]:
    contributors = get_contributors(owner, repo)
    file_counts: dict[str, int] = defaultdict(int)

    for login in contributors:
        # Check they have enough merged PRs to count as "successfully onboarded"
        merged_count = get_merged_pr_count(owner, repo, login)
        time.sleep(0.2)  # search API is stricter on rate limits
        if merged_count < MIN_CONTRIBUTOR_PRS:
            continue

        first_pr = get_first_merged_pr(owner, repo, login)
        time.sleep(0.1)
        if not first_pr:
            continue

        pr_files = get_pr_files(owner, repo, first_pr["number"])
        time.sleep(0.1)

        total_changes = sum(f.get("additions", 0) + f.get("deletions", 0) for f in pr_files)
        if total_changes < MIN_PR_CHANGES:
            continue  # trivial PR, skip

        for f in pr_files:
            filename = f.get("filename", "")
            ext = os.path.splitext(filename)[1]
            if ext in SOURCE_EXTENSIONS:
                file_counts[filename] += 1

    if not file_counts:
        return []

    full_name = f"{owner}/{repo}"
    return [
        {"full_name": full_name, "file_path": fp, "first_pr_score": count}
        for fp, count in file_counts.items()
    ]


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    repos_df = pd.read_parquet(REPOS_PATH)
    print(f"Extracting first-PR signals for {len(repos_df)} repos...")

    results = []
    for _, row in tqdm(repos_df.iterrows(), total=len(repos_df)):
        try:
            rows = process_repo(row["owner"], row["name"])
            results.extend(rows)
        except Exception as e:
            print(f"  Skipping {row['full_name']}: {e}")

    df = pd.DataFrame(results)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} file scores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
