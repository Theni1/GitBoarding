"use client";

import { useState } from "react";
import type { FileResult } from "@/lib/api";

const SIGNAL_LABELS: Record<string, string> = {
  pagerank:             "PageRank",
  contributing:        "CONTRIBUTING.md",
  first_pr:            "First-PR frequency",
  readme:              "README mentions",
  unique_contributors: "Unique contributors",
  commit_frequency:    "Commit frequency",
};

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 bg-[var(--border)] rounded-full overflow-hidden">
        <div className="h-full bg-[var(--green)] rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-[var(--muted)]">{pct}</span>
    </div>
  );
}

export default function FilePath({ file, isTop }: { file: FileResult; isTop?: boolean }) {
  const [open, setOpen] = useState(false);
  const parts = file.path.split("/");
  const filename = parts.pop()!;
  const dir = parts.join("/");

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-colors ${
        isTop ? "border-[var(--green)]/40 bg-[var(--surface)]" : "border-[var(--border)] bg-[var(--surface)]"
      }`}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-white/5 transition-colors"
      >
        {/* Rank */}
        <span className={`text-xs font-bold w-5 shrink-0 ${isTop ? "text-[var(--green)]" : "text-[var(--muted)]"}`}>
          {file.rank}
        </span>

        {/* Score bar */}
        <div className="h-1.5 w-20 bg-[var(--border)] rounded-full overflow-hidden shrink-0">
          <div className="h-full bg-[var(--green)] rounded-full" style={{ width: `${Math.round(file.score * 100)}%` }} />
        </div>

        {/* Path */}
        <div className="flex-1 min-w-0">
          {dir && <span className="text-[var(--muted)] text-xs">{dir}/</span>}
          <span className="text-white text-xs font-medium">{filename}</span>
        </div>

        <span className="text-[var(--muted)] text-xs shrink-0">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-[var(--border)] space-y-4">
          {file.explanation && (
            <p className="text-sm text-[var(--text)] leading-relaxed">{file.explanation}</p>
          )}
          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Signal breakdown</p>
            {Object.entries(file.signals).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between gap-4">
                <span className="text-xs text-[var(--muted)] w-44 shrink-0">{SIGNAL_LABELS[key] ?? key}</span>
                <ScoreBar value={val} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
