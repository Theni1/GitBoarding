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



from typing import AsyncGenerator


async def name_clusters(cluster_labels: dict[str, int]) -> dict[int, str]:
    """Ask GPT to name each cluster based on its file paths. Returns {cluster_id: name}."""
    clusters: dict[int, list[str]] = {}
    for path, label in cluster_labels.items():
        clusters.setdefault(label, []).append(path)

    cluster_list = "\n".join(
        f"Cluster {label}:\n" + "\n".join(f"  {p}" for p in sorted(paths)[:20])
        for label, paths in sorted(clusters.items())
    )

    prompt = (
        "You are analyzing a software repository's file structure.\n"
        "Below are groups of files detected as modules by a graph clustering algorithm.\n"
        "For each cluster, give it a short 1-3 word name that describes what that module does.\n"
        "Be specific — prefer 'Stripe Payments' over 'Payments', 'Auth Middleware' over 'Auth'.\n"
        "Return only a JSON object mapping cluster number to name, e.g. {\"0\": \"Auth\", \"1\": \"API Routes\"}\n\n"
        f"{cluster_list}"
    )

    oai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        resp = await oai_client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0]
        parsed = json.loads(raw)
        return {int(k): v for k, v in parsed.items()}
    except Exception:
        # Fall back to generic names if GPT fails
        return {label: f"Module {label}" for label in clusters}


async def _fetch_readme(client: httpx.AsyncClient, owner: str, repo: str) -> str:
    """Try common README filenames and return the first one found (capped at 3000 chars)."""
    for name in ("README.md", "readme.md", "README.txt", "README"):
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{name}",
            headers=_github_headers(),
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("encoding") == "base64":
                try:
                    return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")[:3000]
                except Exception:
                    pass
    return ""


async def chat_with_repo(
    G: nx.DiGraph,
    cluster_labels: dict[str, int],
    query: str,
    history: list[dict],
    owner: str,
    repo: str,
    repo_meta: dict,
) -> AsyncGenerator[str, None]:
    summaries = _build_cluster_summaries(G, cluster_labels)

    if not summaries:
        yield "event: error\ndata: {\"message\": \"No clusters found\"}\n\n"
        return

    # Fetch README and best-cluster file contents concurrently
    best_cluster = _find_best_cluster(query, summaries)
    cluster_nodes = [n for n, l in cluster_labels.items() if l == best_cluster]
    cluster_set = set(cluster_nodes)
    entry = _find_entry_point(G, cluster_nodes, cluster_set)
    call_chain = _bfs_call_chain(G, entry, cluster_set)[:6]

    async with httpx.AsyncClient(timeout=15.0) as client:
        readme_task = _fetch_readme(client, owner, repo)
        contents_task = asyncio.gather(*[
            _fetch_file_content(client, owner, repo, path) for path in call_chain
        ])
        readme, contents = await asyncio.gather(readme_task, contents_task)

    yield f"event: files\ndata: {json.dumps({'files': call_chain, 'cluster': best_cluster})}\n\n"

    # Build repo-level context block
    description = repo_meta.get("description") or ""
    language = repo_meta.get("language") or ""
    stars = repo_meta.get("stargazers_count", 0)
    topics = ", ".join(repo_meta.get("topics") or [])

    cluster_map = "\n".join(
        f"  Cluster {label}: {summary}" for label, summary in sorted(summaries.items())
    )

    repo_context = f"""Repository: {owner}/{repo}
Description: {description}
Language: {language} | Stars: {stars}{f' | Topics: {topics}' if topics else ''}

Module map (ML-detected clusters):
{cluster_map}
"""
    if readme:
        repo_context += f"\nREADME:\n{readme}"

    # Build specific-file context block
    files_xml = "\n\n".join(
        f'<file path="{path}">\n{content[:800]}\n</file>'
        for path, content in zip(call_chain, contents)
        if content
    )

    openai_messages = [
        {
            "role": "system",
            "content": (
                "You are an expert engineer who has fully read this codebase. "
                "Answer every question with confidence and precision — you already know the answers. "
                "Never hedge with words like 'likely', 'probably', 'appears to', 'suggests', or 'seems'. "
                "State facts directly. Reference specific file names, function names, and data flows when relevant. "
                "For overview questions, lead with what the repo does, not how the config files are set up. "
                "Keep answers concise. Do not repeat file lists back to the user."
            ),
        },
        {
            "role": "user",
            "content": f"<repo_context>\n{repo_context}\n</repo_context>",
        },
        {"role": "assistant", "content": "Got it, I have the repo context."},
        {
            "role": "user",
            "content": f"Most relevant files for this query:\n<files>\n{files_xml}\n</files>",
        },
        {"role": "assistant", "content": "Got it, I have the file contents."},
        *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
        {"role": "user", "content": query},
    ]

    oai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        stream = await oai_client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1024,
            stream=True,
            messages=openai_messages,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield f"event: chunk\ndata: {json.dumps({'text': delta})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    yield "event: done\ndata: {}\n\n"


