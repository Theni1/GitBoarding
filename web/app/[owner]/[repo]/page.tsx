import { predict } from "@/lib/api";
import OnboardingPath from "@/components/OnboardingPath";
import SearchBar from "@/components/SearchBar";
import { notFound } from "next/navigation";

interface Props {
  params: Promise<{ owner: string; repo: string }>;
}

export default async function OnboardingPage({ params }: Props) {
  const { owner, repo } = await params;

  let data;
  try {
    data = await predict(owner, repo);
  } catch (e: any) {
    if (e.message === "Repo not found") notFound();
    throw e;
  }

  const githubUrl = `https://github.com/${owner}/${repo}`;

  return (
    <div className="max-w-2xl mx-auto px-6 py-12 space-y-10">

      {/* Nav */}
      <div className="flex items-center justify-between">
        <a href="/" className="text-xs text-[var(--muted)] hover:text-white transition-colors">
          ← GitBoarding
        </a>
        <SearchBar />
      </div>

      {/* Hero */}
      <div className="space-y-2">
        <div className="flex items-center gap-3 text-xs text-[var(--muted)]">
          <span className="text-[var(--green)] uppercase tracking-widest">Predicted path</span>
          <span>·</span>
          <span>{data.language}</span>
          <span>·</span>
          <span>★ {data.stars.toLocaleString()}</span>
          {data.cached && <span className="text-[var(--muted)]">· cached</span>}
        </div>
        <h1 className="text-2xl font-bold text-white">
          <a href={githubUrl} target="_blank" rel="noreferrer" className="hover:text-[var(--green)] transition-colors">
            {owner}/{repo}
          </a>
        </h1>
        {data.description && (
          <p className="text-sm text-[var(--muted)] leading-relaxed">{data.description}</p>
        )}
      </div>

      {/* Instructions */}
      <div className="text-xs text-[var(--muted)] border border-[var(--border)] rounded-lg px-4 py-3 leading-relaxed">
        Read these files in order. Click any file to see why it matters and which signals pushed it up.
      </div>

      {/* Ranked path */}
      <OnboardingPath files={data.files} />

      {/* Footer */}
      <p className="text-[10px] text-[var(--muted)] text-center pt-4">
        Ranked by a GNN trained on {" "}
        <span className="text-white">contributor first-PR patterns, PageRank, README mentions, and commit history</span>
        {" "} across 1000+ repos.
      </p>
    </div>
  );
}
