"""
FastAPI inference server.

Endpoints:
  GET /predict/{owner}/{repo}   — returns ranked onboarding path + explanations
  GET /health                   — health check

The frontend calls /predict and gets back everything needed to render the
onboarding page in one shot.

Run locally:
  uvicorn main:app --reload --port 8000

Environment variables:
  GITHUB_TOKEN      — required, GitHub personal access token
  ANTHROPIC_API_KEY — required, Anthropic API key
  CHECKPOINT_PATH   — optional, defaults to ../ml/checkpoints/best.pt
"""

import os
import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph_builder import build_repo_graph
from model import load_model, rank_files
from narrate import explain_files, analyze_architecture, TOP_N

# ── In-memory cache ───────────────────────────────────────────────────────────
# Keyed by repo SHA so results invalidate automatically when the repo updates.
# For production, swap this for Redis.

_cache: dict[str, dict] = {}
CACHE_TTL = 60 * 10  # 10 minutes


def _cache_get(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


# ── App setup ─────────────────────────────────────────────────────────────────

_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    print("Loading model checkpoint...")
    _model = load_model()
    print("Model ready.")
    yield


app = FastAPI(title="GitBoarding Inference API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

def _github_headers() -> dict:
    return {
        "Authorization": f"token {os.getenv('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github.v3+json",
    }


# ── Response schema ───────────────────────────────────────────────────────────

class FileResult(BaseModel):
    path: str
    rank: int
    score: float
    explanation: str
    signals: dict[str, float]


class Architecture(BaseModel):
    groups: list[dict]
    edges: list[dict]


class PredictResponse(BaseModel):
    owner: str
    repo: str
    default_branch: str
    stars: int
    description: str
    language: str
    files: list[FileResult]
    architecture: Architecture | None
    cached: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_repo_meta(owner: str, repo: str) -> dict:
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


CONFIG_FILES = [
    "package.json", "requirements.txt", "pyproject.toml", "go.mod", "Cargo.toml",
    "Gemfile", "pom.xml", "build.gradle", "Dockerfile", "docker-compose.yml",
    "docker-compose.yaml", ".env.example", "serverless.yml", "netlify.toml",
    "vercel.json", "next.config.js", "next.config.ts", "vite.config.ts",
    "angular.json", "nuxt.config.ts",
]

async def fetch_config_files(owner: str, repo: str) -> dict[str, str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        async def try_fetch(path: str) -> tuple[str, str]:
            content = await fetch_file_content(owner, repo, path)
            return path, content
        results = await asyncio.gather(*[try_fetch(p) for p in CONFIG_FILES])
    return {path: content for path, content in results if content}


async def fetch_file_content(owner: str, repo: str, path: str) -> str:
    """Fetch raw file content for Claude narration."""
    import base64
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            headers=_github_headers(),
        )
    if resp.status_code != 200:
        return ""
    data = resp.json()
    if data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


# ── Main endpoint ─────────────────────────────────────────────────────────────

@app.get("/predict/{owner}/{repo}", response_model=PredictResponse)
async def predict(owner: str, repo: str):
    # Fetch repo metadata (needed for branch, stars, description)
    meta = await get_repo_meta(owner, repo)
    branch = meta.get("default_branch", "main")
    cache_key = f"{owner}/{repo}@{meta.get('pushed_at', '')}"

    cached_result = _cache_get(cache_key)
    if cached_result:
        return {**cached_result, "cached": True}

    # Build graph and run GNN
    try:
        graph = await build_repo_graph(owner, repo, branch)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    ranked_indices = rank_files(_model, graph.x, graph.edge_index)

    # Take top-N, fetch their contents for Claude
    top_indices = ranked_indices[:TOP_N]
    top_paths = [graph.file_paths[i] for i in top_indices]

    contents = await asyncio.gather(*[
        fetch_file_content(owner, repo, path) for path in top_paths
    ])

    # Build signal breakdown per file (from feature vector)
    SIGNAL_NAMES = [
        "pagerank", "contributing", "readme",
        "unique_contributors", "commit_frequency",
    ]

    ranked_files_input = []
    for i, (idx, path, content) in enumerate(zip(top_indices, top_paths, contents)):
        features = graph.x[idx].tolist()
        signals = {name: round(features[j], 3) for j, name in enumerate(SIGNAL_NAMES)}
        ranked_files_input.append({"path": path, "content": content, "signals": signals})

    # Run file explanations + architecture analysis in parallel
    config_files = await fetch_config_files(owner, repo)
    explained, arch = await asyncio.gather(
        explain_files(f"{owner}/{repo}", ranked_files_input),
        analyze_architecture(f"{owner}/{repo}", config_files),
    )

    import torch
    with torch.no_grad():
        all_scores = _model(graph.x, graph.edge_index).tolist()

    files = [
        FileResult(
            path=f["path"],
            rank=i + 1,
            score=round(all_scores[top_indices[i]], 4),
            explanation=f.get("explanation", ""),
            signals=f["signals"],
        )
        for i, f in enumerate(explained)
    ]

    result = {
        "owner": owner,
        "repo": repo,
        "default_branch": branch,
        "stars": meta.get("stargazers_count", 0),
        "description": meta.get("description", "") or "",
        "language": meta.get("language", "") or "",
        "files": [f.model_dump() for f in files],
        "architecture": arch,
    }

    _cache_set(cache_key, result)
    return {**result, "cached": False}


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": _model is not None}
