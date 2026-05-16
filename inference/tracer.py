import os
import json
import base64
import asyncio
import httpx
import networkx as nx
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import AsyncOpenAI
from typing import AsyncGenerator

_embedder: SentenceTransformer | None = None

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
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


async def _fetch_readme(client: httpx.AsyncClient, owner: str, repo: str) -> str:
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


async def _fetch_manifests(client: httpx.AsyncClient, owner: str, repo: str) -> str:
    manifest_files = [
        "package.json", "requirements.txt", "pyproject.toml",
        "Cargo.toml", "go.mod", "Gemfile", "pom.xml",
    ]
    results = await asyncio.gather(*[
        _fetch_file_content(client, owner, repo, f) for f in manifest_files
    ])
    parts = []
    for name, content in zip(manifest_files, results):
        if content:
            parts.append(f"--- {name} ---\n{content[:1500]}")
    return "\n\n".join(parts)


OVERVIEW_PROBES = [
    "what does this repo do",
    "what is this project",
    "give me an overview",
    "what is the tech stack",
    "what technologies are used",
    "explain this codebase",
    "what is this repository",
    "summarize this project",
]

def _is_overview_query(query: str) -> bool:
    embedder = _get_embedder()
    texts = [query] + OVERVIEW_PROBES
    embeddings = embedder.encode(texts, normalize_embeddings=True)
    sims = embeddings[1:] @ embeddings[0]
    return float(np.max(sims)) >= 0.55


def _select_overview_files(G: nx.DiGraph, cluster_labels: dict[str, int]) -> list[str]:
    """One representative file per cluster — highest PageRank node."""
    clusters: dict[int, list[str]] = {}
    for node, label in cluster_labels.items():
        clusters.setdefault(label, []).append(node)

    selected = []
    for label, files in sorted(clusters.items(), key=lambda x: -len(x[1])):
        best = max(files, key=lambda n: G.nodes[n].get("pagerank", 0.0))
        selected.append(best)
        if len(selected) >= 8:
            break
    return selected


def _build_cluster_content_summaries(
    G: nx.DiGraph,
    cluster_labels: dict[str, int],
    file_contents: dict[str, str],
) -> dict[int, str]:
    """Summary per cluster: first 500 chars of the top PageRank file's content."""
    clusters: dict[int, list[str]] = {}
    for node, label in cluster_labels.items():
        clusters.setdefault(label, []).append(node)

    summaries = {}
    for label, files in clusters.items():
        best = max(files, key=lambda n: G.nodes[n].get("pagerank", 0.0))
        content = file_contents.get(best, "")
        summaries[label] = content[:500] if content else " ".join(
            os.path.basename(f) for f in files[:10]
        )
    return summaries


def _find_best_cluster(query: str, summaries: dict[int, str]) -> int:
    embedder = _get_embedder()
    labels = list(summaries.keys())
    texts = [summaries[l] for l in labels]
    embeddings = embedder.encode([query] + texts, normalize_embeddings=True)
    sims = embeddings[1:] @ embeddings[0]
    return labels[int(np.argmax(sims))]


def _find_entry_point(G: nx.DiGraph, cluster_nodes: list[str], cluster_set: set[str]) -> str:
    cross_in: dict[str, int] = {n: 0 for n in cluster_nodes}
    for node in cluster_nodes:
        for pred in G.predecessors(node):
            if pred not in cluster_set:
                cross_in[node] += 1

    if max(cross_in.values()) > 0:
        return max(cross_in, key=lambda n: cross_in[n])
    return max(cluster_nodes, key=lambda n: G.nodes[n].get("pagerank", 0.0))


def _bfs_call_chain(G: nx.DiGraph, entry: str, cluster_set: set[str], max_depth: int = 8) -> list[str]:
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


async def name_clusters(cluster_labels: dict[str, int]) -> dict[int, str]:
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
        return {int(k): v for k, v in json.loads(raw).items()}
    except Exception:
        return {label: f"Module {label}" for label in clusters}


async def chat_with_repo(
    G: nx.DiGraph,
    cluster_labels: dict[str, int],
    query: str,
    history: list[dict],
    owner: str,
    repo: str,
    repo_meta: dict,
) -> AsyncGenerator[str, None]:

    is_overview = _is_overview_query(query)

    async with httpx.AsyncClient(timeout=15.0) as client:
        if is_overview:
            focus_paths = _select_overview_files(G, cluster_labels)
            readme, manifests, *file_contents_list = await asyncio.gather(
                _fetch_readme(client, owner, repo),
                _fetch_manifests(client, owner, repo),
                *[_fetch_file_content(client, owner, repo, p) for p in focus_paths],
            )
            file_contents = dict(zip(focus_paths, file_contents_list))
        else:
            # Pre-fetch top PageRank file per cluster to build content-based summaries
            clusters: dict[int, list[str]] = {}
            for node, label in cluster_labels.items():
                clusters.setdefault(label, []).append(node)
            top_files = [
                max(files, key=lambda n: G.nodes[n].get("pagerank", 0.0))
                for files in clusters.values()
            ]
            readme, manifests, *top_contents = await asyncio.gather(
                _fetch_readme(client, owner, repo),
                _fetch_manifests(client, owner, repo),
                *[_fetch_file_content(client, owner, repo, p) for p in top_files],
            )
            top_file_contents = dict(zip(top_files, top_contents))

            summaries = _build_cluster_content_summaries(G, cluster_labels, top_file_contents)
            best_cluster = _find_best_cluster(query, summaries)
            cluster_nodes = [n for n, l in cluster_labels.items() if l == best_cluster]
            cluster_set = set(cluster_nodes)
            entry = _find_entry_point(G, cluster_nodes, cluster_set)
            focus_paths = _bfs_call_chain(G, entry, cluster_set)[:6]

            remaining = [p for p in focus_paths if p not in top_file_contents]
            extra_contents = await asyncio.gather(
                *[_fetch_file_content(client, owner, repo, p) for p in remaining]
            )
            file_contents = {**top_file_contents, **dict(zip(remaining, extra_contents))}

    cluster_map = "\n".join(
        f"  Cluster {label}: {', '.join(os.path.basename(f) for f in files[:8])}"
        for label, files in sorted(
            {l: [n for n, cl in cluster_labels.items() if cl == l] for l in set(cluster_labels.values())}.items()
        )
    )

    description = repo_meta.get("description") or ""
    language = repo_meta.get("language") or ""
    stars = repo_meta.get("stargazers_count", 0)

    repo_context = f"""Repository: {owner}/{repo}
Description: {description}
Language: {language} | Stars: {stars}

Module map:
{cluster_map}
"""
    if readme:
        repo_context += f"\nREADME:\n{readme}"
    if manifests:
        repo_context += f"\n\nManifests:\n{manifests}"

    files_xml = "\n\n".join(
        f'<file path="{path}">\n{file_contents.get(path, "")[:2500]}\n</file>'
        for path in focus_paths
        if file_contents.get(path)
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert engineer who has fully read this codebase. "
                "Answer with confidence and precision. Never hedge with words like 'likely', 'probably', 'appears to'. "
                "State facts directly. Reference specific file names and function names when relevant. "
                "Format your response in markdown. Use code blocks for code snippets."
            ),
        },
        {"role": "user", "content": f"<repo_context>\n{repo_context}\n</repo_context>\n\n<files>\n{files_xml}\n</files>"},
        *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
        {"role": "user", "content": query},
    ]

    oai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        stream = await oai_client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1024,
            stream=True,
            messages=messages,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield f"event: chunk\ndata: {json.dumps({'text': delta})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    yield "event: done\ndata: {}\n\n"
