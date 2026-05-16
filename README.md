# GitBoarding

Drop any GitHub repo URL and explore its codebase as an interactive 3D graph. Chat with it to understand how things work.

## What it does

**3D dependency graph** — parses imports across the whole repo to build a directed file graph. Files are clustered into logical modules using directory structure and import edges as signals, then Louvain community detection finds the natural boundaries. GPT names each cluster (Auth, API, DB, etc.). Node size reflects PageRank. Click any node to view the source.

**Repo chat** — ask anything about the codebase. Overview questions ("what is this repo?") get a broad answer drawn from every module. Specific questions ("how does auth work?") route to the most relevant cluster via semantic search, read the actual files, and stream a markdown answer. README and dependency manifests are always included for grounding. Keeps conversation history for follow-ups.

## Stack

| | |
|--|--|
| Frontend | Next.js, TypeScript, Tailwind |
| 3D graph | `3d-force-graph` (Three.js) |
| Inference | FastAPI |
| Clustering | Directory + import signal → Louvain community detection |
| Semantic search | `sentence-transformers` (overview vs specific routing) |
| LLM | GPT-4o-mini (streaming) |

## Running locally

**Inference server**
```bash
cd inference
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd web
npm install
npm run dev
```

**Env vars needed:**

`.env` (root):
```
GITHUB_TOKEN=...
OPENAI_API_KEY=...
```

`web/.env.local`:
```
INFERENCE_URL=http://localhost:8000
```
