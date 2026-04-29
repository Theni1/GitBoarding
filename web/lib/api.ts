const INFERENCE_URL = process.env.INFERENCE_URL ?? "http://localhost:8000";

export interface GraphNode {
  id: string;
  ext: string;
  depth: number;
  is_entrypoint: boolean;
  pagerank: number;
  cluster: number;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphResponse {
  owner: string;
  repo: string;
  description: string;
  stars: number;
  language: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  cached: boolean;
}

export interface TraceStep {
  file: string;
  explanation: string;
}

export interface TraceResponse {
  query: string;
  cluster: number;
  files: string[];
  steps: TraceStep[];
}

export async function fetchGraph(owner: string, repo: string): Promise<GraphResponse> {
  const res = await fetch(`${INFERENCE_URL}/graph/${owner}/${repo}`, {
    next: { revalidate: 600 },
  });
  if (res.status === 404) throw new Error("Repo not found");
  if (!res.ok) throw new Error("Inference server error");
  return res.json();
}

export async function traceFeature(owner: string, repo: string, query: string): Promise<TraceResponse> {
  const res = await fetch(`${INFERENCE_URL}/trace/${owner}/${repo}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error("Trace failed");
  return res.json();
}
