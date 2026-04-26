export default function Loading() {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16 space-y-8 animate-pulse">
      <div className="space-y-3">
        <div className="h-3 w-32 bg-[var(--border)] rounded" />
        <div className="h-7 w-64 bg-[var(--border)] rounded" />
        <div className="h-3 w-96 bg-[var(--border)] rounded" />
      </div>
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-12 bg-[var(--surface)] border border-[var(--border)] rounded-lg" />
        ))}
      </div>
    </div>
  );
}
