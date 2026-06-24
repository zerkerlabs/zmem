import NodeNetworkBg from '@/components/NodeNetworkBg';
import Card from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';

const tableRows = [
  { feature: 'Local memory store', status: 'built' as const, shipped: 'Private SQLite state per workspace', proof: 'zmem status --summary-only' },
  { feature: 'Hybrid-ready retrieval', status: 'built' as const, shipped: 'FTS baseline with benchmark hooks', proof: 'zmem search "query" --scope project' },
  { feature: 'Typed memory records', status: 'built' as const, shipped: 'Semantic, episodic, policy, and task memory', proof: 'zmem remember --type semantic "fact"' },
  { feature: 'Review lifecycle', status: 'built' as const, shipped: 'Queue, promote, revoke, restore', proof: 'zmem queue --scope project' },
  { feature: 'Agent context injection', status: 'built' as const, shipped: 'Scoped context for Codex and MCP clients', proof: 'zmem inject --agent codex --risk medium "task"' },
  { feature: 'MCP server', status: 'built' as const, shipped: 'Agent-readable tools over local memory', proof: 'python3 -m zerker_memory mcp' },
  { feature: 'Agent setup packs', status: 'built' as const, shipped: 'Codex, Claude Code, Cursor, and generic MCP setup', proof: 'zmem agent pack --summary-only' },
  { feature: 'Memory receipts', status: 'built' as const, shipped: 'Records what memory shaped an action', proof: 'zmem why <action-id>' },
  { feature: 'Merkle verification', status: 'built' as const, shipped: 'Tamper-evident local proof roots', proof: 'zmem verify <action-id>' },
  { feature: 'Portable handoff', status: 'built' as const, shipped: 'Move memory state between sessions or machines', proof: 'zmem handoff --summary-only' },
  { feature: 'Treeship export', status: 'built' as const, shipped: 'Optional public proof URL', proof: 'zmem treeship publish <action-id>' },
  { feature: 'ActiveGraph pack', status: 'built' as const, shipped: 'Cross-run memory with causal event ids', proof: 'pack/pack.yaml' },
  { feature: 'Compact benchmark traces', status: 'built' as const, shipped: 'trace.jsonl plus scored_receipt.json', proof: 'zmem-bench-locomo --dataset <file>' },
  { feature: 'LoCoMo FTS baseline', status: 'ready' as const, shipped: '1,986 questions scored with public receipt', proof: '.zerker/bench/locomo-official-v1/fts' },
  { feature: 'Benchmark evidence', status: 'alpha' as const, shipped: 'LongMemEval, LoCoMo, and BEAM queue', proof: 'zmem bench run locomo ...' },
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

        <Card className="mt-16 overflow-hidden p-0">
          {/* Table Header */}
          <div className="hidden border-b border-zline px-6 py-4 md:grid md:grid-cols-[35%_15%_20%_30%]">
            <span className="text-eyebrow text-zmuted">Feature</span>
            <span className="text-eyebrow text-zmuted">Status</span>
            <span className="text-eyebrow text-zmuted">What it means</span>
            <span className="text-eyebrow text-zmuted">Try it</span>
          </div>

          {/* Table Rows */}
          {tableRows.map((row, i) => (
            <div
              key={i}
              className="proof-row border-b border-[rgba(42,42,42,0.5)] px-6 py-3.5 transition-colors duration-200 hover:bg-[rgba(146,214,111,0.03)] md:grid md:grid-cols-[35%_15%_20%_30%] md:items-center"
            >
              <span className="text-sm text-zink">{row.feature}</span>
              <div className="mt-1 md:mt-0">
                <StatusBadge status={row.status} />
              </div>
              <span className="mt-1 hidden text-caption text-zmuted md:block">{row.shipped}</span>
              <code className="mt-1 hidden font-mono text-[11px] text-[#D9E3D0] md:block">{row.proof}</code>
            </div>
          ))}
        </Card>

        <p className="mt-6 text-sm text-zdim">
          Memory transitions should leave receipts. For the deeper model, see{' '}
          <a href="/proof" className="text-zlime transition-colors hover:text-zink">how ZMem proof works</a>.
        </p>
      </div>
    </section>
  );
}
