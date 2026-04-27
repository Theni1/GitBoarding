"use client";

import { useEffect, useRef, useState } from "react"; // useRef used for repoRef
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
          <span className="text-[13px] font-medium tracking-[-0.01em] text-neutral-900">
            <span className="font-semibold">Git</span>
            <span className="opacity-70">Boarding</span>
          </span>
          <div className="flex items-center gap-7 text-[13px] text-neutral-500">
            <a
              href="https://github.com/Theni1/GitBoarding"
              target="_blank"
              rel="noreferrer"
              className="hover:text-neutral-900 transition-colors duration-200"
            >
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
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  placeholder="owner"
                  className="bg-transparent border-none outline-none text-[14px] text-black placeholder:text-black/40 font-mono tracking-tight min-w-0"
                  style={{ width: owner ? `${owner.length + 0.5}ch` : "5ch", padding: 0 }}
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
                  style={{ padding: 0, width: repo ? `${repo.length + 0.5}ch` : "4ch" }}
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
        </form>
      </main>

      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
