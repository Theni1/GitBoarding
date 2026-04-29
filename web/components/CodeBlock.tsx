"use client";

import { useEffect, useState } from "react";

interface Props {
  code: string;
  filename: string;
}

function detectLang(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    ts: "typescript", tsx: "tsx", js: "javascript", jsx: "jsx",
    py: "python", go: "go", java: "java", rs: "rust",
    css: "css", json: "json", md: "markdown", yaml: "yaml", yml: "yaml",
    sh: "bash", toml: "toml", html: "html",
  };
  return map[ext] ?? "text";
}

export default function CodeBlock({ code, filename }: Props) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function highlight() {
      const { codeToHtml } = await import("shiki");
      const result = await codeToHtml(code.slice(0, 4000), {
        lang: detectLang(filename),
        theme: "light-plus",  // VS Code default light theme
      });
      if (!cancelled) setHtml(result);
    }
    highlight();
    return () => { cancelled = true; };
  }, [code, filename]);

  if (!html) {
    return (
      <pre className="text-[11px] font-mono text-neutral-700 leading-relaxed whitespace-pre-wrap break-all">
        {code.slice(0, 4000)}
      </pre>
    );
  }

  return (
    <div
      className="text-[11.5px] leading-relaxed [&>pre]:!bg-transparent [&>pre]:!p-0 [&>pre]:whitespace-pre-wrap [&>pre]:break-all"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
