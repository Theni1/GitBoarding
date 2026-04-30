import Link from "next/link";

export default function RepoNotFound() {
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
          <Link href="/" className="text-[13px] font-medium tracking-[-0.01em] text-neutral-900">
            <span className="font-semibold">Git</span>
            <span className="opacity-70">Boarding</span>
          </Link>
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

      {/* Content */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 pt-24 pb-32 text-center">
        <h1 className="font-semibold leading-[1.05] tracking-[-0.04em] text-[clamp(2rem,6vw,4rem)] text-[#1d1d1f] mb-4">
          Repository not found
        </h1>
        <p className="text-[15px] text-[#1d1d1f] opacity-80 max-w-sm mb-9 leading-relaxed tracking-[-0.01em]">
          This repo doesn&apos;t exist on GitHub, or it&apos;s set to private.
          Double check the owner and repo name and try again.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 px-6 h-11 text-[13.5px] font-medium text-white bg-neutral-900 rounded-full transition-all duration-200 hover:bg-neutral-800 active:scale-[0.97]"
        >
          ← Try another repo
        </Link>
      </main>
    </div>
  );
}
