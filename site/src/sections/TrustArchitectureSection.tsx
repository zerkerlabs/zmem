import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import NodeNetworkBg from '@/components/NodeNetworkBg';
import Card from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';
import CodeBlock from '@/components/CodeBlock';

gsap.registerPlugin(ScrollTrigger);

const statusCards = [
  {
    status: 'built' as const,
    title: 'Local Memory',
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
    title: 'Boundary Control',
    codeTitle: 'zmem inject --agent codex --risk medium "task"',
    code: `Input:      agent + task + risk + scope
Policy:     .zerker/policy.json
Allowed:    injected memory ids
Withheld:   non-authorized candidates
Explain:    zmem why <action-id>`,
  },
  {
    status: 'built' as const,
    title: 'Receipt Layer',
    codeTitle: 'zmem verify <action-id>',
    code: `Memory root:  Merkle-backed
Action root:  receipt-backed
Local check:   zmem verify <action-id>
Bundle:        zmem bundle verify ...
Public URL:    optional Treeship publish`,
  },
];

export default function TrustArchitectureSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const heading = el.querySelector('.section-heading');
    const desc = el.querySelector('.section-desc');
    const cards = el.querySelectorAll('.trust-card');

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
    if (cards.length) {
      gsap.fromTo(cards, { opacity: 0, y: 40, scale: 0.95 },
        { opacity: 1, y: 0, scale: 1, stagger: 0.2, duration: 0.8, ease: 'power3.out',
          scrollTrigger: { trigger: cards[0], start: 'top 75%' } });
    }
  }, []);

  return (
    <section ref={sectionRef} className="relative overflow-hidden py-[160px]">
      <NodeNetworkBg seed={123} />

      <div className="relative z-[1] mx-auto max-w-[1120px] px-6">
        <h2
          className="section-heading max-w-[800px] font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          Local by default. Governed at injection. Verifiable after use.
        </h2>

        <p className="section-desc mt-6 max-w-[640px] text-[17px] leading-relaxed text-zmuted">
          ZMem does not treat retrieval as permission. It records the local memory state, applies policy before
          an agent receives memory, then leaves a receipt for what shaped the action.
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
