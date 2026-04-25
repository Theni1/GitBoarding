"""
Step 1: Find popular repos with enough contributor history to be useful training data.
Writes a list of repo names to ml/data/repos.parquet
"""

import os
import re
import time
import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")

LANGUAGES = ["Python", "JavaScript", "TypeScript", "Go", "Java"]
MIN_CONTRIBUTORS = 50
MIN_STARS = 100
REPOS_PER_LANGUAGE = 200


def search_repos(language: str, page: int) -> list:
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"language:{language} stars:>{MIN_STARS}",
        "sort": "stars",
        "order": "desc",
        "per_page": 100,
        "page": page,
    }
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 403:
        reset = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait = max(reset - time.time(), 0) + 5
        print(f"Rate limited. Waiting {wait:.0f}s...")
        time.sleep(wait)
        return search_repos(language, page)
    response.raise_for_status()
    return response.json().get("items", [])


def get_contributor_count(owner: str, repo: str) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    response = requests.get(url, headers=HEADERS, params={"per_page": 1, "anon": "false"})
    if response.status_code != 200:
        return 0
    link = response.headers.get("Link", "")
    if 'rel="last"' in link:
        match = re.search(r'page=(\d+)>; rel="last"', link)
        return int(match.group(1)) if match else 1
    return len(response.json())


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    all_repos = []

    for language in LANGUAGES:
        print(f"\nMining {language} repos...")
        collected = []
        page = 1

        with tqdm(total=REPOS_PER_LANGUAGE) as pbar:
            while len(collected) < REPOS_PER_LANGUAGE:
                items = search_repos(language, page)
                if not items:
                    break

                for item in items:
                    owner, name = item["full_name"].split("/")
                    contributor_count = get_contributor_count(owner, name)

                    if contributor_count >= MIN_CONTRIBUTORS:
                        collected.append({
                            "full_name": item["full_name"],
                            "owner": owner,
                            "name": name,
                            "language": language,
                            "stars": item["stargazers_count"],
                            "contributor_count": contributor_count,
                            "default_branch": item["default_branch"],
                        })
                        pbar.update(1)

                    if len(collected) >= REPOS_PER_LANGUAGE:
                        break

                    time.sleep(0.1)

                page += 1

        print(f"  Collected {len(collected)} {language} repos")
        all_repos.extend(collected)

    df = pd.DataFrame(all_repos)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} repos to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
