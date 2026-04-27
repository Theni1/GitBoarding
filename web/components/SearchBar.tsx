"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SearchBar() {
  const router = useRouter();
  const [input, setInput] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cleaned = input.trim().replace(/\/$/, "");
    const match = cleaned.match(/(?:github\.com\/|^)([\w.-]+)\/([\w.-]+)/);
    if (match) router.push(`/${match[1]}/${match[2]}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-0 p-1.5 rounded-full border border-black/[0.08] bg-white/80 backdrop-blur-md shadow-[0_2px_12px_rgba(0,0,0,0.04)] focus-within:border-black/20 focus-within:shadow-[0_0_0_4px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.06)] transition-all duration-200"
    >
      <span className="pl-4 text-[13px] font-mono text-neutral-400 select-none whitespace-nowrap">github.com/</span>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="owner/repo"
        className="flex-1 bg-transparent px-2 py-1 text-[13px] font-mono text-neutral-900 outline-none placeholder:text-neutral-300 min-w-0"
      />
      <button
        type="submit"
        className="px-5 h-9 text-[13px] font-medium text-white bg-neutral-900 rounded-full whitespace-nowrap shrink-0 hover:bg-neutral-800 active:scale-[0.97] transition-all duration-200"
      >
        →
      </button>
    </form>
  );
}
