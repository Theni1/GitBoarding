import { NextRequest, NextResponse } from "next/server";

const INFERENCE_URL = process.env.INFERENCE_URL ?? "http://localhost:8000";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ owner: string; repo: string }> },
) {
  const { owner, repo } = await params;
  const body = await req.json();

  const res = await fetch(`${INFERENCE_URL}/trace/${owner}/${repo}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) return NextResponse.json({ error: "Trace failed" }, { status: res.status });
  return NextResponse.json(await res.json());
}
