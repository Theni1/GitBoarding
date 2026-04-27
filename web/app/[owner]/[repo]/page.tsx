import { predict } from "@/lib/api";
import OnboardingPath from "@/components/OnboardingPath";
import SearchBar from "@/components/SearchBar";
import ArchitectureDiagram from "@/components/ArchitectureDiagram";
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
    <div className="relative min-h-screen flex flex-col bg-[#fbfbfd] text-neutral-900 font-sans antialiased">
      {/* Spotlight */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-0"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 30%, rgba(255,255,255,1) 0%, rgba(245,245,247,0.7) 35%, rgba(235,235,240,0) 70%)",
        }}
      />
      {/* Grain */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-multiply -z-0"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")",
        }}
      />

      {/* Navbar */}
      <nav className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[min(92vw,720px)]">
        <div className="flex items-center justify-between gap-6 px-5 h-12 rounded-full border border-black/[0.08] bg-white/70 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.8)]">
          <a href="/" className="text-[13px] font-medium tracking-[-0.01em] text-neutral-900">
            <span className="font-semibold">Git</span>
            <span className="opacity-70">Boarding</span>
          </a>
          <div className="flex items-center gap-7 text-[13px] text-neutral-500">
            <a href="/about" className="hover:text-neutral-900 transition-colors duration-200">About</a>
            <a href="https://github.com/Theni1/GitBoarding" target="_blank" rel="noreferrer" className="hover:text-neutral-900 transition-colors duration-200">GitHub</a>
          </div>
        </div>
      </nav>

      <main className="relative z-10 flex-1 flex flex-col items-center px-6 pt-32 pb-24">
        <div className="w-full max-w-2xl space-y-8">

          {/* Repo header */}
          <div className="space-y-3">
            <div className="flex items-center gap-2.5 flex-wrap">
              {data.cached && (
                <>
                  <span className="text-[12px] text-neutral-400">·</span>
                  <span className="text-[12px] text-neutral-400">cached</span>
                </>
              )}
            </div>

            <h1 className="text-[clamp(1.6rem,4vw,2.4rem)] font-semibold tracking-[-0.035em] text-[#1d1d1f] leading-tight">
              <a href={githubUrl} target="_blank" rel="noreferrer" className="hover:opacity-70 transition-opacity duration-200">
                {owner}<span className="text-neutral-400 font-light">/</span>{repo}
              </a>
            </h1>
          </div>

          {/* Search another repo */}
          <SearchBar />

          {/* Architecture diagram */}
          {data.architecture && data.architecture.groups.length > 0 && (
            <ArchitectureDiagram arch={data.architecture} />
          )}

          {/* Hint */}
          <p className="text-[12px] text-neutral-400 leading-relaxed border border-black/[0.06] rounded-xl px-4 py-3 bg-white/60 backdrop-blur-sm">
            Read these files in order. Click any file to see why it matters and how each signal contributed.
          </p>

          {/* Ranked path */}
          <OnboardingPath files={data.files} />
        </div>
      </main>
    </div>
  );
}
