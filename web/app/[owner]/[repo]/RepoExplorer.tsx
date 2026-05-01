"use client";

import { useState, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import ChatPanel from "@/components/ChatPanel";
import CodeBlock from "@/components/CodeBlock";
import type { GraphResponse, GraphNode } from "@/lib/api";

const Graph3D = dynamic(() => import("@/components/Graph3D"), { ssr: false });

const LANGUAGE_COLORS: Record<string, string> = {
  TypeScript: "#3178c6", JavaScript: "#f1e05a", Python: "#3572A5",
  Go: "#00ADD8", Rust: "#dea584", Java: "#b07219", Ruby: "#701516",
  "C++": "#f34b7d", C: "#555555", "C#": "#178600", Swift: "#F05138",
  Kotlin: "#A97BFF", Dart: "#00B4AB", PHP: "#4F5D95", Scala: "#c22d40",
  Shell: "#89e051", Vue: "#41b883", Svelte: "#ff3e00", CSS: "#563d7c",
  HTML: "#e34c26",
};

interface Props {
  data: GraphResponse;
}

type RightTab = "trace" | "file";

export default function RepoExplorer({ data }: Props) {
  const [highlightedFiles] = useState<string[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [rightTab, setRightTab] = useState<RightTab>("trace");
  const [panelWidth, setPanelWidth] = useState(380);
  const dragging = useRef(false);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const newWidth = window.innerWidth - ev.clientX;
      setPanelWidth(Math.min(700, Math.max(280, newWidth)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  async function handleNodeClick(node: GraphNode) {
    setSelectedNode(node);
    setFileContent(null);
    setLoadingFile(true);
    setRightTab("file");
    try {
      const res = await fetch(`/api/file/${data.owner}/${data.repo}?path=${encodeURIComponent(node.id)}`);
      if (res.ok) setFileContent(await res.text());
    } catch {}
    setLoadingFile(false);
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-[#fbfbfd] overflow-hidden font-sans antialiased">

      {/* Navbar */}
      <nav className="shrink-0 flex items-center justify-between px-6 h-14 border-b border-black/[0.06] bg-white/70 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <a href="/" className="text-[15px] font-black tracking-[-0.04em] text-neutral-900 hover:opacity-70 transition-opacity">
            Git<span className="text-neutral-500">Boarding</span>
          </a>
          <span className="text-neutral-300">/</span>
          <a
            href={`https://github.com/${data.owner}/${data.repo}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-[13px] font-mono text-neutral-900 border border-black/[0.08] rounded-lg px-2.5 py-1 hover:border-black/20 hover:bg-neutral-50 transition-all"
          >
            {data.owner}/{data.repo}
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-40">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3"/>
            </svg>
          </a>
          {data.cached && (
            <span className="text-[10px] text-neutral-400 border border-black/[0.08] px-1.5 py-0.5 rounded-md">
              cached
            </span>
          )}
        </div>
        <div className="flex items-center gap-5 text-[12px] text-neutral-900">
          {data.language && (
            <span className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: LANGUAGE_COLORS[data.language] ?? "#8b8b8b" }}
              />
              {data.language}
            </span>
          )}
          <span><span className="text-amber-400">★</span> {data.stars.toLocaleString()}</span>
          <span>{data.nodes.length} files</span>
        </div>
      </nav>

      {/* Main */}
      <div className="flex-1 flex min-h-0">

        {/* 3D Graph */}
        <div className="flex-1 relative min-w-0 overflow-hidden">
          <Graph3D
            nodes={data.nodes}
            edges={data.edges}
            highlightedFiles={highlightedFiles}
            selectedNodeId={selectedNode?.id ?? null}
            clusterNames={data.cluster_names}
            onNodeClick={handleNodeClick}
          />
        </div>

        {/* Draggable divider */}
        <div
          onMouseDown={onDragStart}
          className="w-1 shrink-0 cursor-col-resize bg-black/[0.06] hover:bg-black/20 active:bg-black/30 transition-colors"
        />

        {/* Right panel */}
        <div className="shrink-0 flex flex-col min-h-0 bg-[#fbfbfd]" style={{ width: panelWidth }}>

          {/* Tabs */}
          <div className="shrink-0 flex border-b border-black/[0.06]">
            <button
              onClick={() => setRightTab("trace")}
              className={`flex-1 py-3 text-[12px] font-medium transition-colors ${
                rightTab === "trace"
                  ? "text-neutral-900 border-b-2 border-neutral-900 -mb-px"
                  : "text-neutral-400 hover:text-neutral-700"
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => setRightTab("file")}
              disabled={!selectedNode}
              className={`flex-1 py-3 text-[12px] font-medium transition-colors disabled:opacity-30 ${
                rightTab === "file"
                  ? "text-neutral-900 border-b-2 border-neutral-900 -mb-px"
                  : "text-neutral-400 hover:text-neutral-700"
              }`}
            >
              {selectedNode ? "File" : "File (click a node)"}
            </button>
          </div>

          {/* Tab content — both always mounted, visibility toggled to preserve state */}
          <div className={rightTab === "trace" ? "flex flex-col flex-1 min-h-0" : "hidden"}>
            <ChatPanel
              owner={data.owner}
              repo={data.repo}
            />
          </div>
          <div className={rightTab === "file" ? "flex flex-col flex-1 min-h-0" : "hidden"}>
            <FilePreview node={selectedNode} content={fileContent} loading={loadingFile} owner={data.owner} repo={data.repo} />
          </div>
        </div>
      </div>
    </div>
  );
}

function FilePreview({ node, content, loading, owner, repo }: { node: GraphNode | null; content: string | null; loading: boolean; owner: string; repo: string }) {
  if (!node) return null;

  const githubUrl = `https://github.com/${owner}/${repo}/blob/main/${node.id}`;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* File header */}
      <div className="shrink-0 px-5 py-3 border-b border-black/[0.06]">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[12px] font-mono font-semibold text-neutral-900 break-all leading-snug">{node.id}</p>
          <a
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
            title="Open on GitHub"
            className="shrink-0 flex items-center gap-1 text-[11px] font-medium text-neutral-500 hover:text-neutral-900 border border-black/[0.08] hover:border-black/20 rounded-md px-2 py-0.5 transition-all mt-0.5"
          >
            GitHub
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3"/>
            </svg>
          </a>
        </div>
      </div>

      {/* File content */}
      <div className="flex-1 overflow-y-auto p-4 min-h-0">
        {loading ? (
          <p className="text-[12px] text-neutral-400">Loading…</p>
        ) : content ? (
          <>
            <CodeBlock code={content} filename={node.id} />
            {content.length > 4000 && (
              <p className="text-[11px] text-neutral-400 mt-4">… (truncated at 4000 chars)</p>
            )}
          </>
        ) : (
          <p className="text-[12px] text-neutral-400">Could not load file content.</p>
        )}
      </div>
    </div>
  );
}
