import NodeNetworkBg from '@/components/NodeNetworkBg';
import Card from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';
import CodeBlock from '@/components/CodeBlock';

const statusCards = [
  {
    status: 'built' as const,
    title: 'Native Memory',
    codeTitle: 'zmem status --summary-only',
    code: `Workspace ready: yes
DB:        .zerker/memory.sqlite
Search:    SQLite + FTS
Types:     semantic / episodic / procedural / policy
Queue:     proposed + quarantined
Status:    active / rejected / revoked`,
  },
  {
    status: 'built' as const,
    title: 'Authority Gate',
    codeTitle: 'zmem inject --agent codex --risk medium "task"',
    code: `Input:      agent + task + risk + scope
Policy:     .zerker/policy.json
Allowed:    injected memory ids
Withheld:   non-authorized candidates
Explain:    zmem why <action-id>`,
  },
  {
    status: 'built' as const,
    title: 'Provider Overlay',
    codeTitle: 'zmem provider import "query" --provider mem0',
    code: `Candidates:  external memory/search
Import:      quarantine first
Review:      promote / reject / revoke
Inject:      policy-gated local context
Proof:       zmem why <action-id>`,
  },
];

export default function TrustArchitectureSection() {
  return (
    <section className="relative overflow-hidden py-[160px]">
      <NodeNetworkBg seed={123} />

      <div className="relative z-[1] mx-auto max-w-[1120px] px-6">
        <h2
          className="section-heading max-w-[800px] font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          Use ZMem alone, or as the memory gate for your stack.
        </h2>

        <p className="section-desc mt-6 max-w-[640px] text-[17px] leading-relaxed text-zmuted">
          ZMem ships with its own local memory system: typed memories, lifecycle states,
          review queues, policy-gated injection, lineage, revocation, snapshots, restore,
          and receipts. If you already use a memory or retrieval provider, ZMem can govern
          what crosses from candidate context into admissible agent memory.
        </p>

        <div className="mt-16 grid grid-cols-1 gap-5 md:grid-cols-3">
          {statusCards.map((card) => (
            <Card key={card.title} className="trust-card p-0 overflow-hidden">
              <div className="p-6 pb-0">
                <div className="mb-3">
                  <StatusBadge status={card.status} />
                </div>
                <h3 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                  {card.title}
                </h3>
              </div>
              <div className="mt-4">
                <CodeBlock code={card.code} title={card.codeTitle} />
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
