"""
GitBoarding inference API.

Endpoints:
  GET  /health
  GET  /graph/{owner}/{repo}   — full import graph with cluster labels + pagerank
  POST /trace/{owner}/{repo}   — feature flow tracing (query → highlighted files + explanation)

Run locally:
  uvicorn main:app --reload --port 8000

Environment variables:
  GITHUB_TOKEN      — GitHub personal access token
  OPENAI_API_KEY    — OpenAI API key
"""

import os
import time
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph_builder import build_repo_graph

_cache: dict[str, dict] = {}
CACHE_TTL = 60 * 10  # 10 minutes


def _cache_get(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


app = FastAPI(title="GitBoarding Inference API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


async def _get_repo_meta(owner: str, repo: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=_github_headers(),
        )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Repo {owner}/{repo} not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="GitHub API error")
    return resp.json()


# ── Response schemas ──────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str           # file path
    ext: str
    depth: int
    is_entrypoint: bool
    pagerank: float
    cluster: int      # ML cluster label

class GraphEdge(BaseModel):
    source: str
    target: str

class GraphResponse(BaseModel):
    owner: str
    repo: str
    description: str
    stars: int
    language: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    cluster_names: dict[int, str] = {}
    cached: bool


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: list[ChatMessage] = []

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/graph/{owner}/{repo}", response_model=GraphResponse)
async def get_graph(owner: str, repo: str):
    meta = await _get_repo_meta(owner, repo)
    branch = meta.get("default_branch", "main")
    cache_key = f"graph:{owner}/{repo}@{meta.get('pushed_at', '')}"

    cached = _cache_get(cache_key)
    if cached:
        return {**cached, "cached": True}

    try:
        G = await build_repo_graph(owner, repo, branch)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    from clustering import cluster_graph
    from tracer import name_clusters

    cluster_labels = cluster_graph(G)
    cluster_names = await name_clusters(cluster_labels)

    nodes = [
        GraphNode(
            id=path,
            ext=data.get("ext", ""),
            depth=data.get("depth", 0),
            is_entrypoint=data.get("is_entrypoint", False),
            pagerank=round(data.get("pagerank", 0.0), 5),
            cluster=cluster_labels.get(path, 0),
        )
        for path, data in G.nodes(data=True)
    ]
    edges = [GraphEdge(source=u, target=v) for u, v in G.edges()]

    result = {
        "owner": owner,
        "repo": repo,
        "description": meta.get("description", "") or "",
        "stars": meta.get("stargazers_count", 0),
        "language": meta.get("language", "") or "",
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
        "cluster_names": cluster_names,
    }
    _cache_set(cache_key, result)
    return {**result, "cached": False}



@app.post("/chat/{owner}/{repo}")
async def chat_repo(owner: str, repo: str, body: ChatRequest):
    from fastapi.responses import StreamingResponse

    meta = await _get_repo_meta(owner, repo)
    branch = meta.get("default_branch", "main")

    try:
        G = await build_repo_graph(owner, repo, branch)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    from clustering import cluster_graph
    from tracer import chat_with_repo

    cluster_labels = cluster_graph(G)
    history = [{"role": m.role, "content": m.content} for m in body.history]

    return StreamingResponse(
        chat_with_repo(G, cluster_labels, body.query, history, owner, repo, meta),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
