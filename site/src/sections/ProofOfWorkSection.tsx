import NodeNetworkBg from '@/components/NodeNetworkBg';
import Card from '@/components/Card';

const readyNowRows = [
  { feature: 'Local memory store', detail: 'Local SQLite state per workspace', proof: 'zmem status --summary-only' },
  { feature: 'Typed memory records', detail: 'Semantic, episodic, procedural, and policy memory', proof: 'zmem remember --type semantic "fact"' },
  { feature: 'Review lifecycle', detail: 'Queue, promote, reject, revoke, restore', proof: 'zmem queue --scope project' },
  { feature: 'Agent context use', detail: 'Scoped memory for Codex and MCP clients', proof: 'zmem inject --agent codex --risk medium "task"' },
  { feature: 'Memory receipts', detail: 'Shows what reached context and what stayed out', proof: 'zmem why <action-id> --summary-only' },
  { feature: 'Portable handoff', detail: 'Move memory state between agents or machines', proof: 'zmem handoff --summary-only' },
  { feature: 'Agent setup packs', detail: 'Codex, Claude Code, Cursor, Hermes, and generic MCP', proof: 'zmem agent pack --summary-only' },
  { feature: 'Optional Treeship proof', detail: 'Digest-only write attestation and public proof URLs', proof: 'ZMEM_TREESHIP_AUTO_SIGN=1' },
];

export default function ProofOfWorkSection() {
  return (
    <section id="proof" className="relative overflow-hidden py-[160px]">
      <NodeNetworkBg seed={999} />

      <div className="relative z-[1] mx-auto max-w-[1120px] px-6">
        <h2
          className="section-heading font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          Verify what influenced the agent.
        </h2>

        <p className="section-desc mt-6 max-w-[640px] text-[17px] leading-relaxed text-zmuted">
          ZMem records what was injected, withheld, promoted, revoked, restored, or handed off.
          Receipts prove memory state transitions and influence, not semantic truth. Each surface
          below maps to a local command or artifact in the repo.
        </p>

        <div className="mt-16">
          <Card className="overflow-hidden p-0">
            <div className="border-b border-zline px-6 py-5">
              <p className="text-eyebrow text-zlime">Ready now</p>
              <h3 className="mt-2 font-heading text-2xl font-semibold tracking-tight text-zink">
                The product surface agents can use today.
              </h3>
            </div>
            {readyNowRows.map((row) => (
              <div key={row.feature} className="border-b border-[rgba(42,42,42,0.5)] px-6 py-4">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-[32%_34%_34%] md:items-center">
                  <span className="text-sm font-semibold text-zink">{row.feature}</span>
                  <span className="text-sm leading-relaxed text-zmuted">{row.detail}</span>
                  <code className="break-words font-mono text-[11px] text-[#D9E3D0]">{row.proof}</code>
                </div>
              </div>
            ))}
          </Card>
        </div>

        <p className="mt-6 text-sm text-zdim">
          Memory transitions should leave receipts. For the deeper model, see{' '}
          <a href="/proof" className="text-zlime transition-colors hover:text-zink">how ZMem proof works</a>
          {' '}or review the <a href="/changelog" className="text-zlime transition-colors hover:text-zink">release history</a>.
        </p>
      </div>
    </section>
  );
}
