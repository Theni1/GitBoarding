"use client";

import { useState, useRef, useEffect } from "react";
import type { TraceStep } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  steps?: TraceStep[];
  files?: string[];
  cluster?: number;
}

interface Props {
  owner: string;
  repo: string;
  onTrace: (files: string[]) => void;  // tells parent to highlight these nodes
}

export default function TracePanel({ owner, repo, onTrace }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setLoading(true);

    try {
      const res = await fetch(`/api/trace/${owner}/${repo}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) throw new Error("Trace failed");
      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Found ${data.files.length} files in cluster ${data.cluster}`,
          steps: data.steps,
          files: data.files,
          cluster: data.cluster,
        },
      ]);

      onTrace(data.files);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#0d0d14] border-l border-white/[0.06]">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/[0.06]">
        <p className="text-[13px] font-medium text-white/80">Feature Tracer</p>
        <p className="text-[11px] text-white/30 mt-0.5">Ask how any feature works</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col gap-2 mt-4">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => setInput(q)}
                className="text-left text-[12px] text-white/30 hover:text-white/60 px-3 py-2 rounded-lg border border-white/[0.06] hover:border-white/20 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={msg.role === "user" ? "flex justify-end" : "flex justify-start"}>
            {msg.role === "user" ? (
              <div className="max-w-[80%] bg-indigo-600/80 text-white text-[13px] px-4 py-2.5 rounded-2xl rounded-tr-sm">
                {msg.content}
              </div>
            ) : (
              <div className="w-full space-y-3">
                {msg.steps && msg.steps.length > 0 ? (
                  <StepList steps={msg.steps} />
                ) : (
                  <div className="text-[13px] text-white/50 px-1">{msg.content}</div>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 px-4 py-3 rounded-2xl bg-white/[0.04] border border-white/[0.06]">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-4 py-4 border-t border-white/[0.06]">
        <div className="flex items-center gap-2 bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 focus-within:border-indigo-500/50 transition-colors">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="How does authentication work?"
            className="flex-1 bg-transparent text-[13px] text-white placeholder:text-white/20 outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="text-indigo-400 hover:text-indigo-300 disabled:text-white/10 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M22 2L11 13M22 2L15 22 11 13 2 9l20-7z"/>
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}

function StepList({ steps }: { steps: TraceStep[] }) {
  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <div
          key={step.file}
          className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3 space-y-1.5"
        >
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-indigo-400/70 bg-indigo-400/10 px-1.5 py-0.5 rounded-md">
              {i + 1}
            </span>
            <span className="text-[12px] font-mono text-white/70 truncate">{step.file}</span>
          </div>
          {step.explanation && (
            <p className="text-[12px] text-white/40 leading-relaxed pl-7">{step.explanation}</p>
          )}
        </div>
      ))}
    </div>
  );
}

const EXAMPLE_QUERIES = [
  "How does authentication work?",
  "How does the database layer work?",
  "How are API requests handled?",
  "How does routing work?",
];
