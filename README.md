# GitBoarding

Paste any GitHub repo URL and get an interactive 3D map of the entire codebase. Ask how any feature works and watch the relevant files light up with a step-by-step explanation.

## Features

### 3D Dependency Graph
Every file in the repo is a node. Every import between files is an edge. An ML pipeline (GraphSAGE mean aggregation + Louvain community detection) clusters files into logical modules — Auth, Database, API, UI, etc. — with no labeled training data. Each cluster gets a color and physically groups together in 3D space. Node size reflects PageRank (how many things import it). Click any node to view its source code with VS Code syntax highlighting.

### Feature Flow Tracer
Type a question like "how does authentication work?" into the chat panel. The tracer embeds your query with `sentence-transformers`, finds the closest cluster via cosine similarity, traces the call chain through that cluster via BFS (entry point → imports → leaf files), highlights those nodes in the 3D graph, and returns a step-by-step explanation from GPT-4o-mini.

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| 3D graph | `3d-force-graph` (Three.js) |
| Inference API | FastAPI (Python) |
| Graph construction | NetworkX + regex import parsing |
| ML — clustering | 2-layer mean aggregation (GraphSAGE) + Louvain community detection |
| ML — semantic search | `sentence-transformers` (all-MiniLM-L6-v2) |
| Explanations | OpenAI GPT-4o-mini |
| GitHub data | GitHub REST API |

## How the ML Works

1. **Graph construction** — fetch the repo's file tree, parse imports from each source file, build a directed `networkx` graph (nodes = files, edges = imports), compute PageRank
2. **GraphSAGE embeddings** — run 2-layer mean aggregation over the import graph. Each node's embedding becomes the mean of its neighbors' features (pagerank, depth, file extension, is_entrypoint), repeated twice. Captures 2-hop neighborhood structure with no learned weights
3. **Louvain clustering** — build a cosine similarity graph from the embeddings, run Louvain community detection to find natural module boundaries
4. **Semantic query matching** — build a one-line text summary per cluster from its file names, embed with `sentence-transformers`, match the user's query via cosine similarity
5. **BFS call-chain tracing** — find the cluster entry point (node with most incoming cross-cluster edges), BFS through the subgraph to produce an ordered call chain

## Project Structure

```
gitboarding/
├── web/                        # Next.js frontend
│   ├── app/
│   │   ├── page.tsx            # Landing page
│   │   └── [owner]/[repo]/     # Repo explorer page
│   ├── components/
│   │   ├── Graph3D.tsx         # 3D force graph (Three.js)
│   │   ├── TracePanel.tsx      # Feature flow chat panel
│   │   └── CodeBlock.tsx       # Syntax-highlighted file viewer
│   └── lib/api.ts              # Typed fetch wrappers
└── inference/                  # FastAPI ML server
    ├── main.py                 # /graph and /trace endpoints
    ├── graph_builder.py        # GitHub API → networkx DiGraph
    ├── clustering.py           # GraphSAGE + Louvain clustering
    └── tracer.py               # BFS call chain + GPT-4o-mini
```

## Running Locally

### Prerequisites
- Node.js 18+
- Python 3.11+
- GitHub personal access token
- OpenAI API key

### 1. Clone the repo

```bash
git clone https://github.com/Theni1/GitBoarding.git
cd GitBoarding
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env`:
```
GITHUB_TOKEN=your_github_token
OPENAI_API_KEY=your_openai_key
```

### 3. Start the inference server

```bash
cd inference
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

First run will download the `sentence-transformers` model (~80MB).

### 4. Start the frontend

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), paste a GitHub repo URL and explore.

## Environment Variables

| Variable | Where | Description |
|----------|-------|-------------|
| `GITHUB_TOKEN` | `.env` (root) | GitHub personal access token — increases API rate limits |
| `OPENAI_API_KEY` | `.env` (root) | OpenAI API key for GPT-4o-mini explanations |
| `INFERENCE_URL` | `web/.env.local` | URL of the FastAPI server (default: `http://localhost:8000`) |
