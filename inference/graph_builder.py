"""
Builds a directed import graph for a live repo on-demand.

Returns a networkx DiGraph where:
  - nodes are source file paths (strings)
  - edges represent imports (source imports target)
  - node attributes: file_ext, depth, is_entrypoint, pagerank (added after graph build)
"""

import os
import re
import base64
import asyncio
import httpx
import networkx as nx
from collections import defaultdict

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rs"}
ENTRYPOINTS = {
    "main.py", "app.py", "index.py", "__init__.py",
    "index.js", "index.ts", "app.js", "app.ts",
    "main.go", "main.java", "Application.java", "main.rs",
}

IMPORT_PATTERNS = [
    re.compile(r"^\s*from\s+([\w./]+)\s+import", re.MULTILINE),
    re.compile(r"^\s*import\s+([\w./]+)", re.MULTILINE),
    re.compile(r"""(?:import\s+.*?from\s+|require\s*\(\s*)['"]([^'"]+)['"]"""),
    re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE),
]

MAX_FILES = 400  # cap for speed on large repos


def _headers() -> dict:
    return {
        "Authorization": f"token {os.getenv('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github.v3+json",
    }


async def _gh_get(client: httpx.AsyncClient, url: str, params: dict = None):
    resp = await client.get(url, headers=_headers(), params=params or {})
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


async def _get_file_tree(client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> list[str]:
    data = await _gh_get(client, f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}", {"recursive": "1"})
    return [item["path"] for item in data.get("tree", []) if item.get("type") == "blob"]


async def _get_file_content(client: httpx.AsyncClient, owner: str, repo: str, path: str) -> str | None:
    data = await _gh_get(client, f"https://api.github.com/repos/{owner}/{repo}/contents/{path}")
    if not data or data.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


def _extract_imports(content: str) -> list[str]:
    imports = []
    for p in IMPORT_PATTERNS:
        matches = p.findall(content)
        imports.extend(m if isinstance(m, str) else m[0] for m in matches if m)
    return imports


def _resolve_import(raw: str, source_file: str, all_files: set[str]) -> str | None:
    source_dir = os.path.dirname(source_file)
    candidate = raw.strip("/")

    if raw.startswith("."):
        candidate = os.path.normpath(os.path.join(source_dir, raw))

    for ext in ["", ".py", ".js", ".ts", ".go", ".java", ".rs", "/index.js", "/index.ts"]:
        if candidate + ext in all_files:
            return candidate + ext

    basename = candidate.split("/")[-1]
    for f in all_files:
        if os.path.splitext(os.path.basename(f))[0] == basename:
            return f
    return None


async def build_repo_graph(owner: str, repo: str, branch: str) -> nx.DiGraph:
    async with httpx.AsyncClient(timeout=30.0) as client:
        all_paths = await _get_file_tree(client, owner, repo, branch)
        source_files = [p for p in all_paths if os.path.splitext(p)[1] in SOURCE_EXTENSIONS]

        if not source_files:
            raise ValueError(f"No source files found in {owner}/{repo}")

        if len(source_files) > MAX_FILES:
            source_files = source_files[:MAX_FILES]

        all_files_set = set(source_files)

        G = nx.DiGraph()
        for path in source_files:
            ext = os.path.splitext(path)[1]
            G.add_node(path, ext=ext, depth=path.count("/"), is_entrypoint=os.path.basename(path) in ENTRYPOINTS)

        async def parse_file(path: str):
            content = await _get_file_content(client, owner, repo, path)
            if not content:
                return
            for raw in _extract_imports(content):
                target = _resolve_import(raw, path, all_files_set)
                if target and target != path:
                    G.add_edge(path, target)

        # Parse in batches of 15 concurrently
        for i in range(0, len(source_files), 15):
            await asyncio.gather(*[parse_file(p) for p in source_files[i:i + 15]])

    # Add pagerank as a node attribute
    pagerank = nx.pagerank(G, alpha=0.85)
    nx.set_node_attributes(G, pagerank, "pagerank")

    return G
