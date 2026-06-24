const pills = [
  { label: 'Codex' },
  { label: 'Claude Code' },
  { label: 'Cursor' },
  { label: 'OpenClaw' },
  { label: 'Generic MCP' },
  { label: 'CLI' },
];

export default function TrustBarSection() {
  return (
    <div
      className="sticky top-0 z-30 border-y border-zline bg-[rgba(18,18,18,0.8)] backdrop-blur-xl py-5"
    >
      <div className="flex flex-wrap items-center justify-center gap-6 px-5 md:gap-10">
        <span className="text-caption text-zdim">Works with</span>
        {pills.map((pill) => (
          <div key={pill.label} className="trust-pill flex items-center gap-2.5">
            <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className="text-zlime">
              <path d="M5 1 9 5 5 9 1 5 5 1Z" fill="none" stroke="currentColor" strokeWidth="1.2" />
            </svg>
            <span className="text-caption text-zmuted">{pill.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
