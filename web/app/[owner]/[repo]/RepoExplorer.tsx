"use client";

import { useState, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import TracePanel from "@/components/TracePanel";
import CodeBlock from "@/components/CodeBlock";
import type { GraphResponse, GraphNode } from "@/lib/api";

const Graph3D = dynamic(() => import("@/components/Graph3D"), { ssr: false });

interface Props {
  data: GraphResponse;
}

type RightTab = "trace" | "file";

export default function RepoExplorer({ data }: Props) {
  const [highlightedFiles, setHighlightedFiles] = useState<string[]>([]);
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
          <a href="/" className="text-[13px] font-medium tracking-[-0.01em] text-neutral-900 hover:opacity-70 transition-opacity">
            <span className="font-semibold">Git</span>
            <span className="opacity-50">Boarding</span>
          </a>
          <span className="text-neutral-400">/</span>
          <a
            href={`https://github.com/${data.owner}/${data.repo}`}
            target="_blank"
            rel="noreferrer"
            className="text-[13px] font-mono text-neutral-900 hover:opacity-60 transition-opacity"
          >
            {data.owner}/{data.repo}
          </a>
          {data.cached && (
            <span className="text-[10px] text-neutral-400 border border-black/[0.08] px-1.5 py-0.5 rounded-md">
              cached
            </span>
          )}
        </div>
        <div className="flex items-center gap-5 text-[12px] text-neutral-900">
          {data.language && <span>{data.language}</span>}
          <span>★ {data.stars.toLocaleString()}</span>
          <span>{data.nodes.length} files</span>
          <a href="https://github.com/Theni1/GitBoarding" target="_blank" rel="noreferrer" className="hover:opacity-60 transition-opacity">
            GitHub
          </a>
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
            onNodeClick={handleNodeClick}
          />
        </div>

        {/* Draggable divider */}
        <div
          onMouseDown={onDragStart}
          className="w-1 shrink-0 cursor-col-resize bg-black/[0.06] hover:bg-black/20 active:bg-black/30 transition-colors"
        />

        {/* Right panel */}
        <div className="shrink-0 flex flex-col min-h-0 bg-white" style={{ width: panelWidth }}>

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
              Feature Tracer
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

          {/* Tab content */}
          {rightTab === "trace" ? (
            <TracePanel
              owner={data.owner}
              repo={data.repo}
              onTrace={setHighlightedFiles}
            />
          ) : (
            <FilePreview node={selectedNode} content={fileContent} loading={loadingFile} />
          )}
        </div>
      </div>
    </div>
  );
}

function FilePreview({ node, content, loading }: { node: GraphNode | null; content: string | null; loading: boolean }) {
  if (!node) return null;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* File header */}
      <div className="shrink-0 px-5 py-3 border-b border-black/[0.06]">
        <p className="text-[10px] text-neutral-400 font-mono mb-0.5">cluster {node.cluster} · {node.ext}</p>
        <p className="text-[12px] font-mono font-semibold text-neutral-900 break-all leading-snug">{node.id}</p>
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
