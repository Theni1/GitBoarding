"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import TracePanel from "@/components/TracePanel";
import type { GraphResponse } from "@/lib/api";

// 3d-force-graph uses browser APIs — must be client-only
const Graph3D = dynamic(() => import("@/components/Graph3D"), { ssr: false });

interface Props {
  data: GraphResponse;
}

export default function RepoExplorer({ data }: Props) {
  const [highlightedFiles, setHighlightedFiles] = useState<string[]>([]);

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0a0a0f] overflow-hidden">

      {/* Navbar */}
      <nav className="shrink-0 flex items-center justify-between px-6 h-12 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <a href="/" className="text-[13px] font-medium text-white/80 hover:text-white transition-colors">
            <span className="font-semibold">Git</span>
            <span className="opacity-50">Boarding</span>
          </a>
          <span className="text-white/20">/</span>
          <a
            href={`https://github.com/${data.owner}/${data.repo}`}
            target="_blank"
            rel="noreferrer"
            className="text-[13px] font-mono text-white/60 hover:text-white transition-colors"
          >
            {data.owner}/{data.repo}
          </a>
          {data.cached && (
            <span className="text-[10px] text-white/20 border border-white/10 px-1.5 py-0.5 rounded-md">
              cached
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 text-[12px] text-white/30">
          {data.language && <span>{data.language}</span>}
          <span>★ {data.stars.toLocaleString()}</span>
          <span>{data.nodes.length} files</span>
        </div>
      </nav>

      {/* Main: graph left, chat right */}
      <div className="flex-1 flex min-h-0">

        {/* 3D Graph */}
        <div className="flex-1 relative min-w-0">
          <Graph3D
            nodes={data.nodes}
            edges={data.edges}
            highlightedFiles={highlightedFiles}
          />

          {/* Repo description overlay */}
          {data.description && (
            <div className="absolute bottom-4 right-4 max-w-xs bg-black/60 backdrop-blur border border-white/[0.06] rounded-xl px-4 py-3 pointer-events-none">
              <p className="text-[11px] text-white/40 leading-relaxed">{data.description}</p>
            </div>
          )}
        </div>

        {/* Trace panel */}
        <div className="w-[380px] shrink-0 flex flex-col min-h-0">
          <TracePanel
            owner={data.owner}
            repo={data.repo}
            onTrace={setHighlightedFiles}
          />
        </div>
      </div>
    </div>
  );
}
