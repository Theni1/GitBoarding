"""
Builds a graph + feature matrix for a live repo on-demand.

At inference time we can't read from the pre-mined parquets — the user
is asking about an arbitrary repo we've never seen. So we recompute the
signals on the fly, fast enough for a web request (~2-5s for a typical repo).

What we skip vs the mining pipeline:
  - first_pr_score     (too slow — requires scanning all contributor PRs)
  - contributing_score (fetched but not fuzzy-matched — just binary presence)

What we compute:
  - pagerank_score     (import graph, same regex approach as compute_pagerank.py)
  - readme_score       (README mentions)
  - unique_contributor_count + commit_frequency (sampled commit history)
  - structural features: file_depth, file_ext_id, is_entrypoint

Returns a RepoGraph dataclass with everything the model.py loader needs.
"""

import os
import re
import time
import base64
import asyncio
import httpx
import networkx as nx
import torch
from dataclasses import dataclass, field
from collections import defaultdict

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}
EXTENSION_MAP = {".py": 0, ".js": 1, ".ts": 2, ".jsx": 3, ".tsx": 4, ".go": 5, ".java": 6}
ENTRYPOINTS = {
    "main.py", "app.py", "index.py", "__init__.py",
    "index.js", "index.ts", "app.js", "app.ts",
    "main.go", "main.java", "Application.java",
}

IMPORT_PATTERNS = [
    re.compile(r"^\s*from\s+([\w./]+)\s+import", re.MULTILINE),
    re.compile(r"^\s*import\s+([\w./]+)", re.MULTILINE),
    re.compile(r"""(?:import\s+.*?from\s+|require\s*\(\s*)['"]([^'"]+)['"]"""),
    re.compile(r'"([\w./\-]+)"'),
    re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE),
]

PATH_PATTERN = re.compile(
    r"`([^`]{3,60})`"
    r"|(\w[\w/.\-]{2,59}\.\w+)"
)
TREE_LINE_PATTERN = re.compile(r"[├└│\s\-]+(\S+\.\w+)")

BOT_SUBSTRINGS = {"bot", "dependabot", "renovate", "greenkeeper", "snyk", "github-actions"}

COMMIT_SAMPLE = 200  # fewer than mining — this needs to be fast
MAX_COMMIT_META = 500


@dataclass
class RepoGraph:
    file_paths: list[str]
    x: torch.Tensor          # [num_files, num_features]
    edge_index: torch.Tensor # [2, num_edges]


async def gh_get(client: httpx.AsyncClient, url: str, params: dict = None) -> dict | list:
    resp = await client.get(url, headers=HEADERS, params=params)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


async def get_file_tree(client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> list[str]:
    data = await gh_get(client, f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}", {"recursive": "1"})
    return [item["path"] for item in data.get("tree", []) if item.get("type") == "blob"]


async def get_file_content(client: httpx.AsyncClient, owner: str, repo: str, path: str) -> str | None:
    data = await gh_get(client, f"https://api.github.com/repos/{owner}/{repo}/contents/{path}")
    if not data or data.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_raw_imports(content: str) -> list[str]:
    imports = []
    for p in IMPORT_PATTERNS:
        imports.extend(p.findall(content))
    return imports


def resolve_import(raw: str, source_file: str, all_files: set[str]) -> str | None:
    candidate = raw.replace(".", "/").strip("/")
    source_dir = os.path.dirname(source_file)
    if raw.startswith("."):
        candidate = os.path.normpath(os.path.join(source_dir, raw.replace(".", "/").lstrip("/")))
    for ext in ["", ".py", ".js", ".ts", ".go", ".java", "/index.js", "/index.ts"]:
        if candidate + ext in all_files:
            return candidate + ext
    basename = candidate.split("/")[-1]
    for f in all_files:
        if os.path.splitext(os.path.basename(f))[0] == basename:
            return f
    return None


async def compute_pagerank(client: httpx.AsyncClient, owner: str, repo: str, source_files: list[str]) -> dict[str, float]:
    all_files_set = set(source_files)
    files_to_parse = source_files[:150]  # cap for speed

    G = nx.DiGraph()
    G.add_nodes_from(source_files)

    # Fetch files concurrently in small batches
    async def fetch_and_add_edges(path: str):
        content = await get_file_content(client, owner, repo, path)
        if not content:
            return
        for raw in extract_raw_imports(content):
            target = resolve_import(raw, path, all_files_set)
            if target and target != path:
                G.add_edge(path, target)

    for i in range(0, len(files_to_parse), 10):
        batch = files_to_parse[i:i + 10]
        await asyncio.gather(*[fetch_and_add_edges(p) for p in batch])

    return nx.pagerank(G, alpha=0.85)


async def compute_readme_scores(client: httpx.AsyncClient, owner: str, repo: str, source_files: list[str]) -> dict[str, float]:
    from rapidfuzz import process, fuzz

    data = await gh_get(client, f"https://api.github.com/repos/{owner}/{repo}/readme")
    if not data or data.get("encoding") != "base64":
        return {}
    try:
        text = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return {}

    candidates = []
    for m in PATH_PATTERN.finditer(text):
        val = m.group(1) or m.group(2)
        if val:
            candidates.append(val.strip())
    for m in TREE_LINE_PATTERN.finditer(text):
        candidates.append(m.group(1).strip())

    basenames = [os.path.basename(f) for f in source_files]
    counts: dict[str, float] = defaultdict(float)
    for candidate in candidates:
        cb = os.path.basename(candidate)
        if os.path.splitext(cb)[1] not in SOURCE_EXTENSIONS:
            continue
        if candidate in source_files:
            counts[candidate] += 1.0
            continue
        result = process.extractOne(cb, basenames, scorer=fuzz.ratio, score_cutoff=80)
        if result:
            _, _, idx = result
            counts[source_files[idx]] += 1.0
    return counts


async def compute_commit_signals(client: httpx.AsyncClient, owner: str, repo: str, branch: str, source_files: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    # Fetch commit metadata
    commits = []
    page = 1
    while len(commits) < MAX_COMMIT_META:
        data = await gh_get(client, f"https://api.github.com/repos/{owner}/{repo}/commits",
                            {"sha": branch, "per_page": 100, "page": page})
        if not data:
            break
        batch = data if isinstance(data, list) else []
        if not batch:
            break
        for c in batch:
            login = (c.get("author") or {}).get("login", "")
            if not any(b in login.lower() for b in BOT_SUBSTRINGS):
                commits.append({"sha": c["sha"], "author": login})
        page += 1

    if len(commits) > COMMIT_SAMPLE:
        step = len(commits) / COMMIT_SAMPLE
        commits = [commits[int(i * step)] for i in range(COMMIT_SAMPLE)]

    source_set = set(source_files)
    author_sets: dict[str, set] = defaultdict(set)
    freq: dict[str, int] = defaultdict(int)

    async def process_commit(c: dict):
        data = await gh_get(client, f"https://api.github.com/repos/{owner}/{repo}/commits/{c['sha']}")
        files = data.get("files", []) if isinstance(data, dict) else []
        total = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
        if total > 2000:
            return
        for f in files:
            fp = f.get("filename", "")
            if fp in source_set:
                if c["author"]:
                    author_sets[fp].add(c["author"])
                freq[fp] += 1

    for i in range(0, len(commits), 5):
        await asyncio.gather(*[process_commit(c) for c in commits[i:i + 5]])

    return {fp: len(authors) for fp, authors in author_sets.items()}, dict(freq)


def normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    mn, mx = min(values.values()), max(values.values())
    if mx == mn:
        return {k: 0.0 for k in values}
    return {k: (v - mn) / (mx - mn) for k, v in values.items()}


def build_edges(file_paths: list[str]) -> torch.Tensor:
    path_to_idx = {p: i for i, p in enumerate(file_paths)}
    dir_to_files: dict[str, list[int]] = defaultdict(list)
    for path, idx in path_to_idx.items():
        dir_to_files[os.path.dirname(path)].append(idx)

    edges = []
    for siblings in dir_to_files.values():
        if len(siblings) < 2:
            continue
        anchor = siblings[0]
        for s in siblings[1:]:
            edges += [[s, anchor], [anchor, s]]

    if not edges:
        loops = [[i, i] for i in range(len(file_paths))]
        return torch.tensor(loops, dtype=torch.long).t().contiguous()
    return torch.tensor(edges, dtype=torch.long).t().contiguous()


async def build_repo_graph(owner: str, repo: str, branch: str = "main") -> RepoGraph:
    async with httpx.AsyncClient(timeout=30.0) as client:
        all_paths = await get_file_tree(client, owner, repo, branch)
        source_files = [p for p in all_paths if os.path.splitext(p)[1] in SOURCE_EXTENSIONS]

        if not source_files:
            raise ValueError(f"No source files found in {owner}/{repo}")

        # Cap for inference speed
        if len(source_files) > 300:
            source_files = source_files[:300]

        # Run signal computations concurrently
        pagerank_raw, readme_raw, (contrib_raw, freq_raw) = await asyncio.gather(
            compute_pagerank(client, owner, repo, source_files),
            compute_readme_scores(client, owner, repo, source_files),
            compute_commit_signals(client, owner, repo, branch, source_files),
        )

    pagerank_norm  = normalize(pagerank_raw)
    readme_norm    = normalize(readme_raw)
    contrib_norm   = normalize(contrib_raw)
    freq_norm      = normalize(freq_raw)

    features = []
    for path in source_files:
        ext = os.path.splitext(path)[1].lower()
        row = [
            pagerank_norm.get(path, 0.0),
            0.0,  # contributing_score_norm — not computed at inference
            0.0,  # first_pr_score_norm — not computed at inference
            readme_norm.get(path, 0.0),
            contrib_norm.get(path, 0.0),
            freq_norm.get(path, 0.0),
            float(path.count("/")),                          # file_depth
            float(EXTENSION_MAP.get(ext, -1)),               # file_ext_id
            float(os.path.basename(path) in ENTRYPOINTS),   # is_entrypoint
        ]
        features.append(row)

    x = torch.tensor(features, dtype=torch.float)
    edge_index = build_edges(source_files)

    return RepoGraph(file_paths=source_files, x=x, edge_index=edge_index)
