"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const SYNONYMS = ["faster.", "quicker.", "smarter.", "easier.", "better."];
const SYNONYM_HOLD = 2200;
const SYNONYM_FADE = 350;

export default function LandingPage() {
  const router = useRouter();
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [error, setError] = useState("");
  const [focused, setFocused] = useState(false);
  const repoRef = useRef<HTMLInputElement>(null);

  const [synonymIdx, setSynonymIdx] = useState(0);
  const [synonymVisible, setSynonymVisible] = useState(true);

  // Synonym cycling
  useEffect(() => {
    const hold = setTimeout(() => {
      setSynonymVisible(false);
      setTimeout(() => {
        setSynonymIdx((i) => (i + 1) % SYNONYMS.length);
        setSynonymVisible(true);
      }, SYNONYM_FADE);
    }, SYNONYM_HOLD);
    return () => clearTimeout(hold);
  }, [synonymVisible, synonymIdx]);

  function parseGithubUrl(raw: string): { owner: string; repo: string } | null {
    const m = raw.trim().replace(/\/$/, "").match(/(?:github\.com\/)([\w.-]+)\/([\w.-]+)/);
    if (m) return { owner: m[1], repo: m[2] };
    return null;
  }

  function handleSubmit() {
    if (!owner.trim() || !repo.trim()) return setError("Enter a GitHub owner and repo");
    router.push(`/${owner.trim()}/${repo.trim()}`);
  }

  function handleOwnerKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "/" || e.key === "Tab") {
      e.preventDefault();
      repoRef.current?.focus();
    }
  }

  function handleOwnerPaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData("text");
    const parsed = parseGithubUrl(text);
    if (parsed) {
      e.preventDefault();
      setOwner(parsed.owner);
      setRepo(parsed.repo);
      setError("");
    }
  }


  return (
    <div className="relative min-h-screen flex flex-col bg-[#fbfbfd] text-neutral-900 font-sans overflow-hidden antialiased">
      {/* Stage spotlight */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-0"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 30%, rgba(255,255,255,1) 0%, rgba(245,245,247,0.7) 35%, rgba(235,235,240,0) 70%)",
        }}
      />
      {/* Subtle grain */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-multiply -z-0"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")",
        }}
      />

      {/* Floating Navbar */}
      <nav className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[min(92vw,720px)]">
        <div className="flex items-center justify-between gap-6 px-5 h-12 rounded-full border border-black/[0.08] bg-white/70 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.8)]">
          <span className="text-[15px] font-black tracking-[-0.04em] text-neutral-900">
            Git<span className="text-neutral-500">Boarding</span>
          </span>
          <div className="flex items-center gap-7 text-[13px] text-neutral-500 font-bold">
            <a
              href="https://github.com/Theni1/GitBoarding"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 font-medium hover:text-neutral-900 transition-colors duration-200"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.202 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
              </svg>
              GitHub
            </a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 pt-24 pb-32">
        <h1 className="text-center font-semibold leading-[1.05] tracking-[-0.045em] text-[clamp(3rem,8.5vw,6.5rem)] m-0 max-w-5xl text-[#1d1d1f]">
          Onboard onto<br />{"any repo "}<span
            style={{
              display: "inline-block",
              transition: `opacity ${SYNONYM_FADE}ms ease, transform ${SYNONYM_FADE}ms ease`,
              opacity: synonymVisible ? 1 : 0,
              transform: synonymVisible ? "translateY(0)" : "translateY(8px)",
            }}
          >{SYNONYMS[synonymIdx]}</span>
        </h1>

        {/* Input */}
        <form
          onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
          className="w-full max-w-[620px] mt-12"
        >
          <div
            className={`flex items-center gap-2 p-1.5 rounded-full border transition-all duration-300 backdrop-blur-md ${
              focused
                ? "border-black/20 bg-white shadow-[0_0_0_6px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.06)]"
                : "border-black/10 bg-white/80 shadow-[0_4px_16px_rgba(0,0,0,0.04)]"
            }`}
          >
            <div className="flex-1 flex items-center gap-0 pl-5 pr-2 min-w-0">
              <span className="text-black text-[14px] font-mono tracking-tight whitespace-nowrap select-none">github.com/</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-neutral-100/80 border border-black/[0.05]">
                <input
                  autoFocus
                  value={owner}
                  onChange={(e) => { setOwner(e.target.value); setError(""); }}
                  onKeyDown={handleOwnerKey}
                  onPaste={handleOwnerPaste}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  placeholder="owner"
                  className="bg-transparent border-none outline-none text-[14px] text-black placeholder:text-black/40 font-mono tracking-tight min-w-0"
                  style={{ width: owner ? `${Math.min(owner.length + 0.5, 20)}ch` : "5ch", padding: 0 }}
                />
              </span>
              <span className="text-black text-[14px] font-mono tracking-tight select-none mx-0.5">/</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-neutral-100/80 border border-black/[0.05]">
                <input
                  ref={repoRef}
                  value={repo}
                  onChange={(e) => { setRepo(e.target.value); setError(""); }}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  placeholder="repo"
                  className="bg-transparent border-none outline-none text-[14px] text-black placeholder:text-black/40 font-mono tracking-tight min-w-0"
                  style={{ padding: 0, width: repo ? `${Math.min(repo.length + 0.5, 20)}ch` : "4ch" }}
                />
              </span>
            </div>
            <button
              type="submit"
              disabled={!owner.trim() || !repo.trim()}
              className="group relative px-6 h-11 text-[13.5px] font-medium text-white bg-neutral-900 rounded-full whitespace-nowrap shrink-0 transition-all duration-200 hover:bg-neutral-800 active:scale-[0.97] disabled:opacity-30 disabled:cursor-not-allowed disabled:pointer-events-none"
            >
              <span className="inline-flex items-center gap-1.5">
                Explore
                <span className="transition-transform duration-200 group-hover:translate-x-0.5">→</span>
              </span>
            </button>
          </div>
          {error && (
            <p className="mt-3 text-center text-[12.5px] text-red-500/90">{error}</p>
          )}

          {/* Paste URL shortcut */}
          <div className="mt-5 relative">
            <div className="flex items-center gap-2 px-4 h-12 rounded-2xl border border-dashed border-black/[0.18] bg-neutral-100/60 focus-within:border-black/30 focus-within:bg-white transition-all duration-200 group">
              <svg className="shrink-0 text-neutral-400 group-focus-within:text-neutral-600 transition-colors" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.202 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
              </svg>
              <input
                placeholder="Paste a GitHub URL to auto-fill"
                className="flex-1 bg-transparent text-[13px] font-mono text-neutral-600 outline-none placeholder:text-neutral-400"
                onPaste={(e) => {
                  const text = e.clipboardData.getData("text");
                  const parsed = parseGithubUrl(text);
                  if (parsed) {
                    e.preventDefault();
                    setOwner(parsed.owner);
                    setRepo(parsed.repo);
                    setError("");
                  }
                }}
                onChange={(e) => {
                  const parsed = parseGithubUrl(e.target.value);
                  if (parsed) {
                    setOwner(parsed.owner);
                    setRepo(parsed.repo);
                    setError("");
                    e.target.value = "";
                  }
                }}
              />
              <kbd className="shrink-0 text-[10px] text-neutral-400 font-mono bg-white border border-black/[0.10] rounded px-1.5 py-0.5 shadow-[0_1px_0_rgba(0,0,0,0.05)]">⌘V</kbd>
            </div>
          </div>
        </form>
      </main>

    </div>
  );
}
