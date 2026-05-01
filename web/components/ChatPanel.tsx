"use client";

import { useState, useRef, useEffect } from "react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  files?: string[];
  streaming?: boolean;
}

interface Props {
  owner: string;
  repo: string;
}

export default function ChatPanel({ owner, repo }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const query = input.trim();
    if (!query || streaming) return;

    setInput("");
    const history = messages.slice(-6).map(({ role, content }) => ({ role, content }));

    setMessages((prev) => [
      ...prev,
      { role: "user", content: query },
      { role: "assistant", content: "", streaming: true },
    ]);
    setStreaming(true);

    try {
      const res = await fetch(`/api/chat/${owner}/${repo}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, history }),
      });

      if (!res.ok || !res.body) throw new Error("Chat failed");

      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let currentEvent = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += value;
        const lines = buffer.split("\n");
        buffer = lines.pop()!;

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const payload = JSON.parse(line.slice(6));
            if (currentEvent === "files") {
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { ...next[next.length - 1], files: payload.files };
                return next;
              });
            } else if (currentEvent === "chunk") {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, content: last.content + payload.text };
                return next;
              });
            } else if (currentEvent === "done" || currentEvent === "error") {
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { ...next[next.length - 1], streaming: false };
                return next;
              });
            }
            currentEvent = "";
          }
        }
      }
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", content: "Something went wrong. Try again.", streaming: false };
        return next;
      });
    } finally {
      setStreaming(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#fbfbfd]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5 min-h-0">

        {messages.map((msg, i) => (
          <div key={i} className={msg.role === "user" ? "flex justify-end" : "flex justify-start"}>
            {msg.role === "user" ? (
              <div className="max-w-[82%] bg-neutral-900 text-white text-[13px] leading-relaxed px-4 py-2.5 rounded-[18px] rounded-tr-[5px] shadow-[0_1px_4px_rgba(0,0,0,0.12)]">
                {msg.content}
              </div>
            ) : (
              <div className="w-full space-y-3">
                {msg.streaming && msg.content === "" ? (
                  <div className="flex items-center gap-[3px] py-1">
                    {[0, 1, 2].map((j) => (
                      <span
                        key={j}
                        className="block rounded-full bg-neutral-400"
                        style={{
                          width: 6, height: 6,
                          animation: `typingpulse 1.2s cubic-bezier(0.4,0,0.6,1) ${j * 0.15}s infinite`,
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-[13px] text-neutral-900 leading-[1.65] whitespace-pre-wrap">
                    {msg.content}
                    {msg.streaming && (
                      <span className="inline-block w-[2px] h-[13px] bg-neutral-300 ml-0.5 align-middle animate-pulse" />
                    )}
                  </p>
                )}
              </div>
            )}
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-4 pt-2">
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-2 bg-white border border-black/[0.08] rounded-full px-5 py-3 shadow-[0_2px_12px_rgba(0,0,0,0.06)] focus-within:border-black/20 focus-within:shadow-[0_2px_16px_rgba(0,0,0,0.09)] transition-all duration-200"
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about this repo…"
            className="flex-1 bg-transparent text-[13px] text-neutral-800 placeholder:text-neutral-400 outline-none tracking-[-0.01em]"
          />
          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-neutral-900 text-white disabled:opacity-25 hover:bg-neutral-700 active:scale-95 transition-all duration-150"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M22 2L11 13M22 2L15 22 11 13 2 9l20-7z"/>
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
