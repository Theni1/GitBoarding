"""
Feature flow tracer.

Given a user query ("how does auth work?"), finds the most relevant cluster
in the graph and traces the call chain through it via BFS.

Pipeline:
  1. Build a one-line text summary for each cluster (file names + entrypoints)
  2. Embed all cluster summaries + the query with sentence-transformers
  3. Pick the closest cluster via cosine similarity
  4. Find the cluster entry point (node with most incoming cross-cluster edges)
  5. BFS from entry point through the cluster subgraph → ordered call chain
  6. Fetch file contents + send to OpenAI for step-by-step explanation
"""

import os
import json
import base64
import asyncio
import httpx
import networkx as nx
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import AsyncOpenAI

_embedder: SentenceTransformer | None = None

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        # all-MiniLM-L6-v2: small (80MB), fast, good at code/tech queries
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


async def _fetch_file_content(client: httpx.AsyncClient, owner: str, repo: str, path: str) -> str:
    resp = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=_github_headers(),
    )
    if resp.status_code != 200:
        return ""
    data = resp.json()
    if data.get("encoding") != "base64":
        return ""
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _build_cluster_summaries(G: nx.DiGraph, cluster_labels: dict[str, int]) -> dict[int, str]:
    """One-line text summary per cluster: entrypoints first, then all file names."""
    clusters: dict[int, list[str]] = {}
    for node, label in cluster_labels.items():
        clusters.setdefault(label, []).append(node)

    summaries = {}
    for label, files in clusters.items():
        entrypoints = [f for f in files if G.nodes[f].get("is_entrypoint")]
        others = [f for f in files if not G.nodes[f].get("is_entrypoint")]
        ordered = entrypoints + others
        # Use just the base filenames for a readable summary
        names = [os.path.basename(f).replace("_", " ").replace("-", " ").replace(".", " ") for f in ordered[:12]]
        summaries[label] = " ".join(names)
    return summaries


def _find_best_cluster(query: str, summaries: dict[int, str]) -> int:
    """Cosine similarity between query embedding and each cluster summary."""
    embedder = _get_embedder()
    labels = list(summaries.keys())
    texts = [summaries[l] for l in labels]

    all_texts = [query] + texts
    embeddings = embedder.encode(all_texts, normalize_embeddings=True)

    query_emb = embeddings[0]
    cluster_embs = embeddings[1:]

    similarities = cluster_embs @ query_emb  # cosine sim (already normalized)
    best_idx = int(np.argmax(similarities))
    return labels[best_idx]


def _find_entry_point(G: nx.DiGraph, cluster_nodes: list[str], cluster_set: set[str]) -> str:
    """
    The entry point is the cluster node with the most incoming edges
    from OUTSIDE the cluster — it's the "front door" other code calls into.
    Falls back to the highest pagerank node if no cross-cluster edges exist.
    """
    cross_in: dict[str, int] = {n: 0 for n in cluster_nodes}
    for node in cluster_nodes:
        for pred in G.predecessors(node):
            if pred not in cluster_set:
                cross_in[node] += 1

    if max(cross_in.values()) > 0:
        return max(cross_in, key=lambda n: cross_in[n])

    # Fallback: highest pagerank in cluster
    return max(cluster_nodes, key=lambda n: G.nodes[n].get("pagerank", 0.0))


def _bfs_call_chain(G: nx.DiGraph, entry: str, cluster_set: set[str], max_depth: int = 8) -> list[str]:
    """BFS from the entry point, staying within the cluster. Returns ordered file list."""
    visited = []
    queue = [(entry, 0)]
    seen = {entry}

    while queue:
        node, depth = queue.pop(0)
        visited.append(node)
        if depth >= max_depth:
            continue
        for neighbor in G.successors(node):
            if neighbor in cluster_set and neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, depth + 1))

    return visited


async def _explain_with_openai(query: str, steps: list[dict]) -> list[dict]:
    """Send the ordered file list + contents to OpenAI for step-by-step explanation."""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    files_xml = "\n\n".join(
        f'<file path="{s["file"]}">\n{s["content"][:600]}\n</file>'
        for s in steps
        if s.get("content")
    )
    file_list = "\n".join(f"{i+1}. {s['file']}" for i, s in enumerate(steps))

    prompt = f"""A developer is asking: "{query}"

Here are the files involved in this feature, in call-chain order:
{file_list}

File contents:
<files>
{files_xml}
</files>

For each file, write exactly 1-2 sentences explaining its specific role in answering the question.
Be concrete — mention function names, what data flows through, what it calls next.

Return a JSON array only:
[{{"file": "path/to/file.py", "explanation": "..."}}, ...]"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0]

    try:
        parsed = json.loads(raw)
        explanation_map = {e["file"]: e["explanation"] for e in parsed if isinstance(e, dict)}
    except Exception:
        explanation_map = {}

    for s in steps:
        s["explanation"] = explanation_map.get(s["file"], "")

    return steps


import os as _os

async def trace_feature_flow(
    G: nx.DiGraph,
    cluster_labels: dict[str, int],
    query: str,
    owner: str,
    repo: str,
) -> dict:
    summaries = _build_cluster_summaries(G, cluster_labels)

    if not summaries:
        return {"query": query, "cluster": -1, "files": [], "steps": []}

    best_cluster = _find_best_cluster(query, summaries)

    cluster_nodes = [n for n, l in cluster_labels.items() if l == best_cluster]
    cluster_set = set(cluster_nodes)

    entry = _find_entry_point(G, cluster_nodes, cluster_set)
    call_chain = _bfs_call_chain(G, entry, cluster_set)

    # Cap at 8 files for the explanation — enough to tell the story
    call_chain = call_chain[:8]

    # Fetch file contents concurrently
    async with httpx.AsyncClient(timeout=15.0) as client:
        contents = await asyncio.gather(*[
            _fetch_file_content(client, owner, repo, path) for path in call_chain
        ])

    steps = [{"file": path, "content": content} for path, content in zip(call_chain, contents)]
    steps = await _explain_with_openai(query, steps)

    return {
        "query": query,
        "cluster": best_cluster,
        "files": call_chain,
        "steps": [{"file": s["file"], "explanation": s["explanation"]} for s in steps],
    }
