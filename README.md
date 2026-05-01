# GitBoarding

Drop any GitHub repo URL and explore its codebase as an interactive 3D graph. Chat with it to understand how things work.

## What it does

**3D dependency graph** — parses imports across the whole repo to build a directed file graph. GraphSAGE embeddings + Louvain clustering group files into logical modules. GPT names each cluster (Auth, API, DB, etc.). Node size reflects PageRank. Click any node to view the source.

**Repo chat** — ask anything about the codebase. Finds the most relevant cluster via semantic search, reads the actual files and README, and streams an answer. Keeps conversation history for follow-ups.

## Stack

| | |
|--|--|
| Frontend | Next.js 14, TypeScript, Tailwind |
| 3D graph | `3d-force-graph` (Three.js) |
| Inference | FastAPI |
| Clustering | GraphSAGE + Louvain community detection |
| Semantic search | `sentence-transformers` |
| LLM | GPT-4o-mini |

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
