import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import NodeNetworkBg from '@/components/NodeNetworkBg';
import Card from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';

gsap.registerPlugin(ScrollTrigger);

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
  { feature: 'Benchmark evidence', status: 'alpha' as const, shipped: 'Synthetic and long-memory adapters', proof: 'zmem bench ...' },
];

export default function ProofOfWorkSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const heading = el.querySelector('.section-heading');
    const desc = el.querySelector('.section-desc');
    const rows = el.querySelectorAll('.proof-row');

    if (heading) {
      gsap.fromTo(heading, { opacity: 0, y: 40 },
        { opacity: 1, y: 0, duration: 0.8, ease: 'power3.out',
          scrollTrigger: { trigger: heading, start: 'top 80%' } });
    }
    if (desc) {
      gsap.fromTo(desc, { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out', delay: 0.2,
          scrollTrigger: { trigger: desc, start: 'top 80%' } });
    }
    if (rows.length) {
      gsap.fromTo(rows, { opacity: 0, x: -20 },
        { opacity: 1, x: 0, stagger: 0.05, duration: 0.4, ease: 'power2.out',
          scrollTrigger: { trigger: rows[0], start: 'top 75%' } });
    }
  }, []);

  return (
    <section ref={sectionRef} id="proof" className="relative overflow-hidden py-[160px]">
      <NodeNetworkBg seed={999} />

      <div className="relative z-[1] mx-auto max-w-[1120px] px-6">
        <h2
          className="section-heading font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          What ZMem can prove today.
        </h2>

        <p className="section-desc mt-6 max-w-[640px] text-[17px] leading-relaxed text-zmuted">
          ZMem is designed so memory is not a black box. The product surfaces below map to
          local commands that create, retrieve, review, verify, and hand off agent memory.
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
          For the deeper receipt model, see{' '}
          <a href="/proof" className="text-zlime transition-colors hover:text-zink">how ZMem proof works</a>.
        </p>
      </div>
    </section>
  );
}
