"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { GraphNode, GraphEdge } from "@/lib/api";

// Cluster → color palette (up to 12 clusters)
const CLUSTER_COLORS = [
  "#6366f1", // indigo
  "#f59e0b", // amber
  "#10b981", // emerald
  "#ef4444", // red
  "#3b82f6", // blue
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f97316", // orange
  "#84cc16", // lime
  "#06b6d4", // cyan
  "#a855f7", // purple
];

function clusterColor(cluster: number): string {
  return CLUSTER_COLORS[cluster % CLUSTER_COLORS.length];
}

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedFiles?: string[];
  selectedNodeId?: string | null;
  clusterNames?: Record<number, string>;
  onNodeClick?: (node: GraphNode) => void;
}

export default function Graph3D({ nodes, edges, highlightedFiles = [], selectedNodeId, clusterNames = {}, onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const hoveredNodeRef = useRef<GraphNode | null>(null);
  const onNodeClickRef = useRef(onNodeClick);
  const highlightSet = new Set(highlightedFiles);

  // Keep refs in sync so the mouseup handler always has the latest values
  useEffect(() => { hoveredNodeRef.current = hoveredNode; }, [hoveredNode]);
  useEffect(() => { onNodeClickRef.current = onNodeClick; }, [onNodeClick]);

  const initGraph = useCallback(async () => {
    if (!containerRef.current || graphRef.current) return;

    const { default: ForceGraph3D } = await import("3d-force-graph");

    const graphData = {
      nodes: nodes.map((n) => ({
        ...n,
        name: n.id,
        val: Math.max(1, n.pagerank * 400),  // node size from pagerank
      })),
      links: edges.map((e) => ({ source: e.source, target: e.target })),
    };

    const graph = new (ForceGraph3D as any)()(containerRef.current)
      .graphData(graphData)
      .backgroundColor("#f5f5f7")
      .nodeLabel((node: any) => node.id)
      .nodeColor((node: any) => {
        if (node.id === selectedNodeId) return "#ffffff";
        if (highlightSet.size > 0) {
          return highlightSet.has(node.id) ? clusterColor(node.cluster) : "#d1d5db";
        }
        return clusterColor(node.cluster);
      })
      .nodeOpacity(0.9)
      .nodeVal((node: any) => node.id === selectedNodeId ? node.val * 2.5 : node.val)
      .linkColor(() => "#00000070")
      .linkWidth(1.5)
      .linkDirectionalArrowLength(3)
      .linkDirectionalArrowRelPos(1)
      .linkDirectionalParticles((link: any) => {
        if (highlightSet.size === 0) return 0;
        const src = typeof link.source === "object" ? link.source.id : link.source;
        const tgt = typeof link.target === "object" ? link.target.id : link.target;
        return highlightSet.has(src) && highlightSet.has(tgt) ? 3 : 0;
      })
      .linkDirectionalParticleColor(() => "#6366f1")
      .linkDirectionalParticleWidth(2)
      .showNavInfo(false)
      .enableNodeDrag(false)
      // onNodeClick intentionally omitted — handled via mousedown/mouseup below
      // to avoid the library swallowing clicks that involve tiny orbit motion
      .onNodeHover((node: any) => {
        setHoveredNode(node ?? null);
        if (containerRef.current) {
          containerRef.current.style.cursor = node ? "pointer" : "default";
        }
      });

    // Slow down the simulation so it settles nicely
    graph.d3Force("charge")?.strength(-80);

    // Fire onNodeClick if the mouse barely moved — catches clicks that 3d-force-graph
    // drops because it mistook a tiny orbit motion for a drag.
    let downX = 0, downY = 0;
    const onMouseDown = (e: MouseEvent) => { downX = e.clientX; downY = e.clientY; };
    const onMouseUp = (e: MouseEvent) => {
      const dx = e.clientX - downX, dy = e.clientY - downY;
      if (Math.hypot(dx, dy) < 5 && hoveredNodeRef.current) {
        onNodeClickRef.current?.(hoveredNodeRef.current);
      }
    };
    containerRef.current.addEventListener("mousedown", onMouseDown);
    containerRef.current.addEventListener("mouseup", onMouseUp);

    graphRef.current = graph;
    graphRef.current._clickCleanup = () => {
      containerRef.current?.removeEventListener("mousedown", onMouseDown);
      containerRef.current?.removeEventListener("mouseup", onMouseUp);
    };
  }, [nodes, edges]);  // intentionally exclude highlightedFiles — updated via effect below

  useEffect(() => {
    initGraph();
    return () => {
      graphRef.current?._clickCleanup?.();
      graphRef.current?._destructor?.();
      graphRef.current = null;
    };
  }, [initGraph]);

  // Update node colors/sizes when highlighted files or selected node changes
  useEffect(() => {
    if (!graphRef.current) return;
    graphRef.current
      .nodeColor((node: any) => {
        if (node.id === selectedNodeId) return "#ffffff";
        if (highlightSet.size > 0) {
          return highlightSet.has(node.id) ? clusterColor(node.cluster) : "#d1d5db";
        }
        return clusterColor(node.cluster);
      })
      .nodeVal((node: any) => node.id === selectedNodeId ? node.val * 2.5 : node.val)
      .linkDirectionalParticles((link: any) => {
        if (highlightSet.size === 0) return 0;
        const src = typeof link.source === "object" ? link.source.id : link.source;
        const tgt = typeof link.target === "object" ? link.target.id : link.target;
        return highlightSet.has(src) && highlightSet.has(tgt) ? 3 : 0;
      });
  }, [highlightedFiles, selectedNodeId]);

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(() => {
      if (graphRef.current && containerRef.current) {
        graphRef.current.width(containerRef.current.clientWidth);
        graphRef.current.height(containerRef.current.clientHeight);
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {/* Cluster legend */}
      <ClusterLegend nodes={nodes} clusterNames={clusterNames} />

      {/* Hovered node tooltip */}
      {hoveredNode && (
        <div className="absolute bottom-4 left-4 max-w-xs bg-white/90 backdrop-blur border border-black/[0.08] rounded-2xl px-4 py-3 pointer-events-none shadow-[0_4px_16px_rgba(0,0,0,0.08)]">
          <p className="text-[10px] text-neutral-400 mb-0.5 flex items-center gap-1.5">
            <span
              className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: clusterColor(hoveredNode.cluster) }}
            />
            {clusterNames[hoveredNode.cluster] ?? `Cluster ${hoveredNode.cluster}`}
            <span className="text-neutral-300">·</span>
            {hoveredNode.ext}
          </p>
          <p className="text-[12px] font-mono text-neutral-800 break-all leading-snug">
            {hoveredNode.id}
          </p>
        </div>
      )}
    </div>
  );
}

function ClusterLegend({ nodes, clusterNames }: { nodes: GraphNode[]; clusterNames: Record<number, string> }) {
  const clusterMap = new Map<number, GraphNode[]>();
  for (const n of nodes) {
    if (!clusterMap.has(n.cluster)) clusterMap.set(n.cluster, []);
    clusterMap.get(n.cluster)!.push(n);
  }
  const clusters = [...clusterMap.entries()].sort((a, b) => a[0] - b[0]);

  return (
    <div className="absolute top-4 left-4 flex flex-col gap-1.5 bg-white/80 backdrop-blur border border-black/[0.06] rounded-2xl px-3 py-2.5 shadow-[0_2px_8px_rgba(0,0,0,0.06)]">
      {clusters.map(([cluster, clusterNodes]) => (
        <div key={cluster} className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: clusterColor(cluster) }}
          />
          <span className="text-[11px] text-neutral-700 font-medium">{clusterNames[cluster] ?? `Cluster ${cluster}`}</span>
          <span className="text-[10px] text-neutral-400">{clusterNodes.length}</span>
        </div>
      ))}
    </div>
  );
}
