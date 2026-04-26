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
    <form onSubmit={handleSubmit} className="flex items-center border border-[var(--border)] rounded-lg overflow-hidden bg-[var(--surface)] focus-within:border-[var(--green)] transition-colors max-w-sm">
      <span className="pl-3 text-[var(--muted)] text-xs select-none">github.com/</span>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="owner/repo"
        className="flex-1 bg-transparent px-2 py-2 text-xs text-white outline-none placeholder:text-[var(--muted)]"
      />
      <button type="submit" className="px-3 py-2 text-xs text-black bg-[var(--green)] hover:brightness-90 transition-all">
        →
      </button>
    </form>
  );
}
