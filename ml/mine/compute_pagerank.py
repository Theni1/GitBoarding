"""
Step 2: Build an import graph for each repo and compute PageRank scores per file.

For each repo in repos.parquet:
  1. Fetch the full file tree via GitHub API
  2. For each source file, fetch its content and extract import statements (regex)
  3. Resolve imports to internal files (same repo)
  4. Build a directed graph: file A → file B means A imports B
  5. Run networkx PageRank
  6. Write scores to ml/data/pagerank.parquet

Output columns: full_name, file_path, pagerank_score
"""

import os
import re
import time
import base64
import networkx as nx
import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
REPOS_PATH = os.path.join(os.path.dirname(__file__), "../data/repos.parquet")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../data/pagerank.parquet")

# File extensions we care about per language
SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}

# Regex patterns to extract import paths per language
# Each pattern captures the raw import string (not yet resolved to a file)
IMPORT_PATTERNS = [
    # Python: from .foo.bar import X  or  import foo.bar
    re.compile(r"^\s*from\s+([\w./]+)\s+import", re.MULTILINE),
    re.compile(r"^\s*import\s+([\w./]+)", re.MULTILINE),
    # JS/TS: import ... from './foo'  or  require('./foo')
    re.compile(r"""(?:import\s+.*?from\s+|require\s*\(\s*)['"]([^'"]+)['"]"""),
    # Go: import "path/to/pkg" or import ( "path" )
    re.compile(r'"([\w./\-]+)"'),
    # Java: import com.example.Foo;
    re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE),
]


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


def get_file_tree(owner: str, repo: str, branch: str) -> list[str]:
    """Return list of all file paths in the repo (recursive tree)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
    resp = gh_get(url, params={"recursive": "1"})
    if resp.status_code != 200:
        return []
    tree = resp.json().get("tree", [])
    return [item["path"] for item in tree if item["type"] == "blob"]


def get_file_content(owner: str, repo: str, path: str) -> str | None:
    """Fetch decoded text content of a single file. Returns None on failure."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = gh_get(url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_raw_imports(content: str) -> list[str]:
    imports = []
    for pattern in IMPORT_PATTERNS:
        imports.extend(pattern.findall(content))
    return imports


def resolve_import(raw: str, source_file: str, all_files: set[str]) -> str | None:
    """
    Try to map a raw import string to an actual file path in the repo.
    Returns the matched file path or None.
    """
    # Normalise: replace dots with slashes, strip leading slashes
    candidate = raw.replace(".", "/").strip("/")
    source_dir = os.path.dirname(source_file)

    # Try relative resolution first (e.g. ./utils or ../models)
    if raw.startswith("."):
        rel = os.path.normpath(os.path.join(source_dir, raw.replace(".", "/").lstrip("/")))
        candidate = rel

    for ext in ["", ".py", ".js", ".ts", ".go", ".java", "/index.js", "/index.ts"]:
        probe = candidate + ext
        if probe in all_files:
            return probe

    # Last resort: basename match (catches Java-style imports)
    basename = candidate.split("/")[-1]
    for f in all_files:
        if os.path.splitext(os.path.basename(f))[0] == basename:
            return f

    return None


def compute_pagerank_for_repo(owner: str, repo: str, branch: str) -> list[dict]:
    all_paths = get_file_tree(owner, repo, branch)
    source_files = [p for p in all_paths if os.path.splitext(p)[1] in SOURCE_EXTENSIONS]

    if not source_files:
        return []

    # Cap to avoid burning rate limit on massive monorepos
    if len(source_files) > 500:
        source_files = source_files[:500]

    all_files_set = set(source_files)
    G = nx.DiGraph()
    G.add_nodes_from(source_files)

    for path in source_files:
        content = get_file_content(owner, repo, path)
        if not content:
            continue
        for raw in extract_raw_imports(content):
            target = resolve_import(raw, path, all_files_set)
            if target and target != path:
                G.add_edge(path, target)
        time.sleep(0.05)  # be polite to the API

    scores = nx.pagerank(G, alpha=0.85)
    full_name = f"{owner}/{repo}"
    return [{"full_name": full_name, "file_path": f, "pagerank_score": scores.get(f, 0.0)} for f in source_files]


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    repos_df = pd.read_parquet(REPOS_PATH)
    print(f"Computing PageRank for {len(repos_df)} repos...")

    results = []
    for _, row in tqdm(repos_df.iterrows(), total=len(repos_df)):
        try:
            rows = compute_pagerank_for_repo(row["owner"], row["name"], row["default_branch"])
            results.extend(rows)
        except Exception as e:
            print(f"  Skipping {row['full_name']}: {e}")

    df = pd.DataFrame(results)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} file scores to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
