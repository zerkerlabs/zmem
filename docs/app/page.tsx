import Link from 'next/link';

const areas = [
  {
    title: 'Connect an Agent',
    href: '/docs/agents',
    body: 'Connect Codex, Claude Code, Cursor, OpenClaw, Hermes, or a generic MCP client to one local memory workspace.',
  },
  {
    title: 'Build With ZMem',
    href: '/docs/builders',
    body: 'Use the CLI, MCP server, receipts, local store, and handoff artifacts inside tools, agents, and product workflows.',
  },
  {
    title: 'Operate Memory',
    href: '/docs/memory-lifecycle',
    body: 'Understand lifecycle states, queue review, promotion, revocation, restore, and handoff across projects and sessions.',
  },
  {
    title: 'Prove and Benchmark',
    href: '/docs/receipts',
    body: 'Trace what memory influenced an answer, package evidence, and compare retrieval quality with reproducible benchmark runs.',
  },
];

const stats = [
  ['8', 'core guides'],
  ['MCP', 'agent ready'],
  ['Local', 'proof-first'],
];

export default function HomePage() {
  return (
    <main className="zmem-home">
      <div className="zmem-shell">
        <section className="zmem-hero">
          <div>
            <p className="zmem-eyebrow">ZMem documentation</p>
            <h1 className="zmem-title">Build reliable memory into AI agents.</h1>
            <p className="zmem-copy">
              Learn how to install ZMem, connect agent tools, manage memory across sessions,
              inspect provenance, hand off work, and measure retrieval quality.
            </p>
            <div className="zmem-actions">
              <Link className="zmem-button primary" href="/docs">
                Open docs
              </Link>
              <a className="zmem-button" href="https://github.com/zerkerlabs/zmem">
                GitHub
              </a>
            </div>
          </div>
          <aside className="zmem-terminal" aria-label="ZMem proof terminal preview">
            <div className="zmem-terminal-top">
              <span />
              <span />
              <span />
            </div>
            <div className="zmem-terminal-body">
              <p><span>$</span> zmem connect codex --label current-chat</p>
              <p>Workspace: <strong>ready</strong></p>
              <p>Agent: <strong>Codex</strong></p>
              <p>Session: <strong>awaiting agent attach</strong></p>
              <p className="zmem-terminal-muted">Paste the one-time instruction into this chat.</p>
            </div>
          </aside>
        </section>

        <section className="zmem-stats" aria-label="Documentation readiness">
          {stats.map(([value, label]) => (
            <div key={label}>
              <strong>{value}</strong>
              <span>{label}</span>
            </div>
          ))}
        </section>

        <section className="zmem-grid" aria-label="Documentation areas">
          {areas.map((area) => (
            <Link className="zmem-panel" href={area.href} key={area.title}>
              <h2>{area.title}</h2>
              <p>{area.body}</p>
            </Link>
          ))}
        </section>
      </div>
    </main>
  );
}
