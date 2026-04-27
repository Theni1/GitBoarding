const INFERENCE_URL = process.env.INFERENCE_URL ?? "http://localhost:8000";

export interface FileResult {
  path: string;
  rank: number;
  score: number;
  explanation: string;
  signals: Record<string, number>;
}

export interface ArchComponent {
  id: string;
  label: string;
  type: string;
}

export interface ArchGroup {
  id: string;
  label: string;
  col: number;
  row: number;
  components: ArchComponent[];
}

export interface Architecture {
  groups: ArchGroup[];
  edges: { from: string; to: string; label?: string }[];
}

export interface PredictResponse {
  owner: string;
  repo: string;
  default_branch: string;
  stars: number;
  description: string;
  language: string;
  files: FileResult[];
  architecture: Architecture | null;
  cached: boolean;
}

export async function predict(owner: string, repo: string): Promise<PredictResponse> {
  const res = await fetch(`${INFERENCE_URL}/predict/${owner}/${repo}`, {
    next: { revalidate: 600 }, // cache for 10 min on the Next.js side too
  });

  if (res.status === 404) throw new Error("Repo not found");
  if (!res.ok) throw new Error("Inference server error");

  return res.json();
}
