"use client";

import { useState } from "react";
import type { FileResult } from "@/lib/api";

const SIGNAL_LABELS: Record<string, string> = {
  pagerank:             "PageRank",
  contributing:        "CONTRIBUTING.md",
  readme:              "README mentions",
  unique_contributors: "Unique contributors",
  commit_frequency:    "Commit frequency",
};

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-24 bg-neutral-200 rounded-full overflow-hidden">
        <div className="h-full bg-neutral-800 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-neutral-400 tabular-nums">{pct}</span>
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
      className={`rounded-2xl overflow-hidden transition-all duration-200 border ${
        isTop
          ? "border-black/[0.12] bg-white shadow-[0_4px_20px_rgba(0,0,0,0.06)]"
          : "border-black/[0.06] bg-white/70 shadow-[0_2px_8px_rgba(0,0,0,0.03)]"
      }`}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-black/[0.02] transition-colors duration-150"
      >
        {/* Rank */}
        <span className={`text-[13px] font-semibold w-5 shrink-0 tabular-nums ${isTop ? "text-neutral-900" : "text-neutral-400"}`}>
          {file.rank}
        </span>

        {/* Score bar */}
        <div className="h-1 w-16 bg-neutral-100 rounded-full overflow-hidden shrink-0">
          <div
            className="h-full rounded-full bg-neutral-800"
            style={{ width: `${Math.round(file.score * 100)}%` }}
          />
        </div>

        {/* Path */}
        <div className="flex-1 min-w-0 font-mono">
          {dir && <span className="text-neutral-400 text-[12px]">{dir}/</span>}
          <span className={`text-[12px] font-medium ${isTop ? "text-neutral-900" : "text-neutral-700"}`}>{filename}</span>
        </div>

        <span className="text-neutral-300 text-[10px] shrink-0">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-5 pb-5 pt-3 border-t border-black/[0.05] space-y-4">
          {file.explanation && (
            <p className="text-[13px] text-neutral-600 leading-relaxed">{file.explanation}</p>
          )}
          <div className="space-y-2.5">
            <p className="text-[10px] uppercase tracking-widest text-neutral-400">Signal breakdown</p>
            {Object.entries(file.signals).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between gap-4">
                <span className="text-[12px] text-neutral-500 w-44 shrink-0">{SIGNAL_LABELS[key] ?? key}</span>
                <ScoreBar value={val} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
