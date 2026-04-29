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
  highlightedFiles?: string[];  // files to pulse from a trace
  onNodeClick?: (node: GraphNode) => void;
}

export default function Graph3D({ nodes, edges, highlightedFiles = [], onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const highlightSet = new Set(highlightedFiles);

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
      .backgroundColor("#0a0a0f")
      .nodeLabel((node: any) => node.id)
      .nodeColor((node: any) => {
        if (highlightSet.size > 0) {
          return highlightSet.has(node.id)
            ? clusterColor(node.cluster)
            : "#1e1e2e";
        }
        return clusterColor(node.cluster);
      })
      .nodeOpacity(0.95)
      .nodeVal((node: any) => node.val)
      .linkColor(() => "#ffffff18")
      .linkWidth(0.5)
      .linkDirectionalArrowLength(3)
      .linkDirectionalArrowRelPos(1)
      .linkDirectionalParticles((link: any) => {
        if (highlightSet.size === 0) return 0;
        const src = typeof link.source === "object" ? link.source.id : link.source;
        const tgt = typeof link.target === "object" ? link.target.id : link.target;
        return highlightSet.has(src) && highlightSet.has(tgt) ? 3 : 0;
      })
      .linkDirectionalParticleColor(() => "#a78bfa")
      .linkDirectionalParticleWidth(1.5)
      .onNodeClick((node: any) => {
        onNodeClick?.(node as GraphNode);
        // Fly camera to clicked node
        const distance = 80;
        const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
        graph.cameraPosition(
          { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
          node,
          800,
        );
      })
      .onNodeHover((node: any) => {
        setHoveredNode(node ?? null);
        if (containerRef.current) {
          containerRef.current.style.cursor = node ? "pointer" : "default";
        }
      });

    // Slow down the simulation so it settles nicely
    graph.d3Force("charge")?.strength(-80);

    graphRef.current = graph;
  }, [nodes, edges]);  // intentionally exclude highlightedFiles — updated via effect below

  useEffect(() => {
    initGraph();
    return () => {
      graphRef.current?._destructor?.();
      graphRef.current = null;
    };
  }, [initGraph]);

  // Update node colors when highlighted files change without rebuilding the graph
  useEffect(() => {
    if (!graphRef.current) return;
    graphRef.current
      .nodeColor((node: any) => {
        if (highlightSet.size > 0) {
          return highlightSet.has(node.id) ? clusterColor(node.cluster) : "#1e1e2e";
        }
        return clusterColor(node.cluster);
      })
      .linkDirectionalParticles((link: any) => {
        if (highlightSet.size === 0) return 0;
        const src = typeof link.source === "object" ? link.source.id : link.source;
        const tgt = typeof link.target === "object" ? link.target.id : link.target;
        return highlightSet.has(src) && highlightSet.has(tgt) ? 3 : 0;
      });
  }, [highlightedFiles]);

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
      <ClusterLegend nodes={nodes} highlightSet={highlightSet} />

      {/* Hovered node tooltip */}
      {hoveredNode && (
        <div className="absolute bottom-4 left-4 max-w-xs bg-black/80 backdrop-blur border border-white/10 rounded-xl px-4 py-3 pointer-events-none">
          <p className="text-[11px] font-mono text-white/50 mb-0.5">
            cluster {hoveredNode.cluster} · {hoveredNode.ext}
          </p>
          <p className="text-[13px] font-mono text-white break-all leading-snug">
            {hoveredNode.id}
          </p>
          <p className="text-[11px] text-white/40 mt-1">
            pagerank {hoveredNode.pagerank.toFixed(4)}
          </p>
        </div>
      )}
    </div>
  );
}

function ClusterLegend({ nodes, highlightSet }: { nodes: GraphNode[]; highlightSet: Set<string> }) {
  const clusters = Array.from(new Map(nodes.map((n) => [n.cluster, n])).entries())
    .sort((a, b) => a[0] - b[0]);

  return (
    <div className="absolute top-4 right-4 flex flex-col gap-1.5">
      {clusters.map(([cluster]) => (
        <div key={cluster} className="flex items-center gap-2">
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ background: clusterColor(cluster) }}
          />
          <span className="text-[11px] text-white/50 font-mono">cluster {cluster}</span>
        </div>
      ))}
    </div>
  );
}
