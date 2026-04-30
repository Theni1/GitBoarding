export default function Loading() {
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

      {/* Navbar skeleton */}
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

          {/* Repo title skeleton */}
          <div className="space-y-3">
            <div className="h-9 w-56 bg-neutral-100 rounded-xl animate-pulse" />
          </div>

          {/* Search bar skeleton */}
          <div className="h-12 w-full bg-neutral-100 rounded-full animate-pulse" />

          {/* Analyzing indicator */}
          <div className="flex flex-col items-center gap-5 py-10">
            {/* Animated dots */}
            <div className="flex items-center gap-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-neutral-400"
                  style={{
                    animation: `wave 1.2s ease-in-out ${i * 0.12}s infinite`,
                  }}
                />
              ))}
            </div>
            <p className="text-[13px] text-black tracking-wide">
              Analysing repository…
            </p>
          </div>

          {/* File list skeleton */}
          <div className="space-y-2.5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-14 bg-white rounded-2xl border border-black/[0.06] animate-pulse"
                style={{ opacity: 1 - i * 0.12 }}
              />
            ))}
          </div>
        </div>
      </main>

      <style>{`
        @keyframes wave {
          0%, 100% { transform: translateY(0); opacity: 0.4; }
          50% { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
