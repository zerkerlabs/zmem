import { Search, BookOpen, Shield, FileCheck } from '@/components/Icons';
import NodeNetworkBg from '@/components/NodeNetworkBg';
import Card from '@/components/Card';

const cards = [
  {
    icon: Search,
    iconColor: '#92D66F',
    title: 'Request',
    description: 'Before a task, an agent asks for memory scoped by agent, risk, and project boundary.',
    code: 'zmem inject --agent codex --risk medium "task"',
  },
  {
    icon: BookOpen,
    iconColor: '#F0B35A',
    title: 'Propose',
    description: 'New agent-discovered facts can enter review without becoming trusted memory automatically.',
    code: 'zmem propose "new fact" --source agent',
  },
  {
    icon: Shield,
    iconColor: '#92D66F',
    title: 'Promote',
    description: 'Humans or policies can promote useful memory, reject noise, quarantine risk, or revoke stale state.',
    code: 'zmem queue --scope project',
  },
  {
    icon: FileCheck,
    iconColor: '#E06F62',
    title: 'Inject',
    description: 'Only admissible memory reaches the agent. The receipt records what was injected and withheld.',
    code: 'zmem why <action-id>',
  },
];

export default function MemoryLoopSection() {
  return (
    <section
      id="memory-loop"
      className="relative overflow-hidden py-[160px]"
    >
      <NodeNetworkBg seed={42} />

      <div className="relative z-[1] mx-auto max-w-[1200px] px-6">
        <h2
          className="section-heading max-w-[800px] font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          Retrieval is not permission.
        </h2>

        <p className="section-desc mt-6 max-w-[640px] text-[17px] leading-relaxed text-zmuted">
          Agents can already retrieve context. ZMem makes memory admissible:
          source, scope, status, authority, review, and a receipt for why it was
          allowed to shape action.
        </p>

        <div
          className="mt-16 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4"
          style={{ perspective: '600px' }}
        >
          {cards.map((card) => {
            const Icon = card.icon;
            return (
              <Card key={card.title} className="loop-card">
                <Icon size={24} style={{ color: card.iconColor }} className="mb-4" />
                <h3 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                  {card.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">
                  {card.description}
                </p>
                <div className="mt-4 overflow-hidden rounded bg-[#0A0A0A] px-3.5 py-2.5">
                  <code className="font-mono text-xs text-[#D9E3D0]">{card.code}</code>
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
}
