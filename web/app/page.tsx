"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LandingPage() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [focused, setFocused] = useState(false);

  function parseRepo(raw: string) {
    const match = raw.trim().replace(/\/$/, "").match(/(?:github\.com\/|^)([\w.-]+)\/([\w.-]+)/);
    return match ? { owner: match[1], repo: match[2] } : null;
  }

  function handleSubmit() {
    const parsed = parseRepo(input);
    if (!parsed) return setError("Enter a GitHub URL or owner/repo");
    router.push(`/${parsed.owner}/${parsed.repo}`);
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
            {["About"].map((l) => (
              <a key={l} href="#" className="hover:text-neutral-900 transition-colors duration-200">
                {l}
              </a>
            ))}
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

        <h1 className="opacity-0 animate-[fadeUp_900ms_ease-out_forwards] [animation-delay:200ms] text-center font-semibold leading-[1.05] tracking-[-0.045em] text-[clamp(3rem,8.5vw,6.5rem)] m-0 max-w-5xl pb-1">
          <span className="bg-clip-text text-transparent bg-[linear-gradient(180deg,#1d1d1f_0%,#1d1d1f_55%,#6e6e73_100%)] pb-3 inline-block">
            Onboard onto
            <br />
            any repo faster.
          </span>
        </h1>

        {/* Input */}
        <form
          onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
          className="opacity-0 animate-[fadeUp_900ms_ease-out_forwards] [animation-delay:480ms] w-full max-w-[620px] mt-12"
        >
          <div
            className={`flex items-center gap-2 p-1.5 rounded-full border transition-all duration-300 backdrop-blur-md ${
              focused
                ? "border-black/20 bg-white shadow-[0_0_0_6px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.06)]"
                : "border-black/10 bg-white/80 shadow-[0_4px_16px_rgba(0,0,0,0.04)]"
            }`}
          >
            <div className="flex-1 flex items-center pl-5 pr-2 min-w-0">
              <span className="text-neutral-400 text-[14px] font-mono tracking-tight whitespace-nowrap select-none">
                github.com/
              </span>
              <input
                autoFocus
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setError("");
                }}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                placeholder="owner/repo"
                className="flex-1 min-w-0 bg-transparent border-none outline-none px-2 py-3 text-[14px] text-neutral-900 placeholder:text-neutral-400 font-mono tracking-tight"
              />
            </div>
            <button
              type="submit"
              className="group relative px-6 h-11 text-[13.5px] font-medium text-white bg-neutral-900 rounded-full whitespace-nowrap shrink-0 cursor-pointer transition-all duration-200 hover:bg-neutral-800 active:scale-[0.97]"
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
      `}</style>
    </div>
  );
}
