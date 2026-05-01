export default function Loading() {
  return (
    <div className="relative min-h-screen flex flex-col bg-[#fbfbfd] text-neutral-900 font-sans antialiased overflow-hidden">
      {/* Spotlight — same as home */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-0"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 30%, rgba(255,255,255,1) 0%, rgba(245,245,247,0.7) 35%, rgba(235,235,240,0) 70%)",
        }}
      />
      {/* Grain — same as home */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-multiply -z-0"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")",
        }}
      />

      {/* Navbar — identical to home */}
      <nav className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[min(92vw,720px)]">
        <div className="flex items-center justify-between gap-6 px-5 h-12 rounded-full border border-black/[0.08] bg-white/70 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.8)]">
          <a href="/" className="text-[15px] font-black tracking-[-0.04em] text-neutral-900">
            Git<span className="text-neutral-500">Boarding</span>
          </a>
          <div className="flex items-center gap-7 text-[13px]">
            <a
              href="https://github.com/Theni1/GitBoarding"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 font-medium text-neutral-600 hover:text-neutral-900 transition-colors duration-200"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.202 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
              </svg>
              GitHub
            </a>
          </div>
        </div>
      </nav>

      {/* Centered loading — mirrors home page hero layout */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 pb-16">
        <div className="flex flex-col items-center gap-6">
          {/* Animated bars — minimal, Apple-style */}
          <div className="flex items-end gap-[3px] h-6">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="w-[3px] rounded-full bg-neutral-300"
                style={{ animation: `loadbar 1.1s ease-in-out ${i * 0.1}s infinite` }}
              />
            ))}
          </div>
          <p className="text-[13px] tracking-wide text-neutral-400">
            Analysing repository
          </p>
        </div>
      </main>

      <style>{`
        @keyframes loadbar {
          0%, 100% { height: 6px; opacity: 0.4; }
          50% { height: 20px; opacity: 1; }
        }
      `}</style>
    </div>
  );
}
