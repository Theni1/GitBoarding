"use client";

import { useEffect, useRef, useMemo } from "react";
import type { Architecture } from "@/lib/api";

function toMermaid(arch: Architecture): string {
  const lines: string[] = ["flowchart LR"];

  // Subgraph per group
  for (const g of arch.groups) {
    const safeId = g.id.replace(/[^a-zA-Z0-9_]/g, "_");
    lines.push(`  subgraph ${safeId}["${g.label}"]`);
    for (const c of g.components) {
      const cid = c.id.replace(/[^a-zA-Z0-9_]/g, "_");
      lines.push(`    ${cid}["${c.label}"]`);
    }
    lines.push("  end");
  }

  // Edges
  for (const e of arch.edges) {
    const from = e.from.replace(/[^a-zA-Z0-9_]/g, "_");
    const to = e.to.replace(/[^a-zA-Z0-9_]/g, "_");
    const label = e.label ? `|"${e.label}"|` : "";
    lines.push(`  ${from} -->${label} ${to}`);
  }

  return lines.join("\n");
}

let idCounter = 0;

export default function ArchitectureDiagram({ arch }: { arch: Architecture }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const diagramId = useRef(`mermaid-${idCounter++}`);

  const spec = useMemo(() => toMermaid(arch), [arch]);

  useEffect(() => {
    if (!containerRef.current) return;

    import("mermaid").then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        theme: "neutral",
        flowchart: { curve: "basis", padding: 20 },
        themeVariables: {
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          fontSize: "14px",
          primaryColor: "#dbeafe",
          primaryBorderColor: "#93c5fd",
          primaryTextColor: "#1e3a8a",
          lineColor: "#9ca3af",
          edgeLabelBackground: "#f8fafc",
          clusterBkg: "#f8fafc",
          clusterBorder: "#d1d5db",
        },
      });

      mermaid.render(diagramId.current, spec).then(({ svg }) => {
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          // Make SVG fill width
          const svgEl = containerRef.current.querySelector("svg");
          if (svgEl) {
            svgEl.style.width = "100%";
            svgEl.style.height = "auto";
            svgEl.removeAttribute("width");
            svgEl.removeAttribute("height");
          }
        }
      });
    });
  }, [spec]);

  if (!arch.groups.length) return null;

  return (
    <div className="space-y-3">
      <p className="text-[10px] uppercase tracking-widest text-neutral-400">System architecture</p>
      <div className="rounded-2xl border border-black/[0.06] bg-[#fafafa] p-6">
        <div ref={containerRef} className="w-full" />
      </div>
    </div>
  );
}
