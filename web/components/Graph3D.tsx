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
      .backgroundColor("#f5f5f7")
      .nodeLabel((node: any) => node.id)
      .nodeColor((node: any) => {
        if (highlightSet.size > 0) {
          return highlightSet.has(node.id)
            ? clusterColor(node.cluster)
            : "#d1d5db";
        }
        return clusterColor(node.cluster);
      })
      .nodeOpacity(0.9)
      .nodeVal((node: any) => node.val)
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
          return highlightSet.has(node.id) ? clusterColor(node.cluster) : "#d1d5db";
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
        <div className="absolute bottom-4 left-4 max-w-xs bg-white/90 backdrop-blur border border-black/[0.08] rounded-2xl px-4 py-3 pointer-events-none shadow-[0_4px_16px_rgba(0,0,0,0.08)]">
          <p className="text-[10px] font-mono text-neutral-400 mb-0.5">
            cluster {hoveredNode.cluster} · {hoveredNode.ext}
          </p>
          <p className="text-[12px] font-mono text-neutral-800 break-all leading-snug">
            {hoveredNode.id}
          </p>
          <p className="text-[10px] text-neutral-400 mt-1">
            pagerank {hoveredNode.pagerank.toFixed(4)}
          </p>
        </div>
      )}
    </div>
  );
}

// Keyword → human label (checked against directory and file names)
const LABEL_RULES: [RegExp, string][] = [
  [/auth|login|logout|session|jwt|oauth|signin|signup/i, "Auth"],
  [/db|database|prisma|drizzle|mongoose|sequelize|knex|supabase/i, "Database"],
  [/api|routes?|endpoints?|handlers?|controllers?/i, "API"],
  [/component|widget|ui|view|screen/i, "UI Components"],
  [/util|helper|lib|shared|common|tool/i, "Utilities"],
  [/store|state|redux|zustand|context|provider/i, "State"],
  [/model|schema|entity|type|interface/i, "Models"],
  [/service|client|sdk|integration/i, "Services"],
  [/test|spec|mock|fixture/i, "Tests"],
  [/config|setting|env|constant/i, "Config"],
  [/middleware|guard|interceptor/i, "Middleware"],
  [/hook|use[A-Z]/i, "Hooks"],
  [/page|layout|app/i, "Pages"],
  [/script|job|task|worker|queue/i, "Jobs"],
];

function clusterName(clusterNodes: GraphNode[]): string {
  const paths = clusterNodes.map((n) => n.id).join(" ");

  for (const [pattern, label] of LABEL_RULES) {
    if (pattern.test(paths)) return label;
  }

  // Fall back to the most common top-level directory in the cluster
  const dirs = clusterNodes
    .map((n) => n.id.split("/")[0])
    .filter(Boolean);
  const freq = new Map<string, number>();
  for (const d of dirs) freq.set(d, (freq.get(d) ?? 0) + 1);
  const top = [...freq.entries()].sort((a, b) => b[1] - a[1])[0];
  if (top) return top[0].charAt(0).toUpperCase() + top[0].slice(1);

  return `Cluster ${clusterNodes[0]?.cluster ?? ""}`;
}

function ClusterLegend({ nodes, highlightSet }: { nodes: GraphNode[]; highlightSet: Set<string> }) {
  // Group nodes by cluster
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
          <span className="text-[11px] text-neutral-700 font-medium">{clusterName(clusterNodes)}</span>
          <span className="text-[10px] text-neutral-400">{clusterNodes.length}</span>
        </div>
      ))}
    </div>
  );
}
