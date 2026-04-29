import { NextRequest, NextResponse } from "next/server";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ owner: string; repo: string }> },
) {
  const { owner, repo } = await params;
  const path = req.nextUrl.searchParams.get("path");
  if (!path) return NextResponse.json({ error: "Missing path" }, { status: 400 });

  const token = process.env.GITHUB_TOKEN;
  const headers: Record<string, string> = { Accept: "application/vnd.github.v3+json" };
  if (token) headers["Authorization"] = `token ${token}`;

  const res = await fetch(`https://api.github.com/repos/${owner}/${repo}/contents/${path}`, { headers });
  if (!res.ok) return new NextResponse("Not found", { status: 404 });

  const data = await res.json();
  if (data.encoding !== "base64") return new NextResponse("", { status: 200 });

  const content = Buffer.from(data.content, "base64").toString("utf-8");
  return new NextResponse(content, { headers: { "Content-Type": "text/plain" } });
}
