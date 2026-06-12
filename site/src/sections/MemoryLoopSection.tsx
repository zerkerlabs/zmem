import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { Search, BookOpen, Shield, FileCheck } from 'lucide-react';
import NodeNetworkBg from '@/components/NodeNetworkBg';
import Card from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';

gsap.registerPlugin(ScrollTrigger);

const cards = [
  {
    icon: Search,
    iconColor: '#92D66F',
    title: 'Request',
    description: 'Before a task, an agent asks for memory scoped by agent, risk, and project boundary.',
    code: 'zmem inject --agent codex --risk medium "task"',
    status: 'built' as const,
  },
  {
    icon: BookOpen,
    iconColor: '#F0B35A',
    title: 'Propose',
    description: 'New agent-discovered facts can enter review without becoming trusted memory automatically.',
    code: 'zmem propose "new fact" --source agent',
    status: 'built' as const,
  },
  {
    icon: Shield,
    iconColor: '#92D66F',
    title: 'Govern',
    description: 'Humans can inspect the queue, promote useful memory, reject noise, or revoke derived state.',
    code: 'zmem queue --scope project',
    status: 'built' as const,
  },
  {
    icon: FileCheck,
    iconColor: '#E06F62',
    title: 'Verify',
    description: 'Every governed action can be explained and checked against the local Merkle-backed receipt trail.',
    code: 'zmem why <action-id> \u2192 zmem verify <action-id>',
    status: 'built' as const,
  },
];

export default function MemoryLoopSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const heading = el.querySelector('.section-heading');
    const desc = el.querySelector('.section-desc');
    const cardEls = el.querySelectorAll('.loop-card');

    if (heading) {
      gsap.fromTo(heading,
        { opacity: 0, y: 40 },
        { opacity: 1, y: 0, duration: 0.8, ease: 'power3.out',
          scrollTrigger: { trigger: heading, start: 'top 80%' } }
      );
    }

    if (desc) {
      gsap.fromTo(desc,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out', delay: 0.2,
          scrollTrigger: { trigger: desc, start: 'top 80%' } }
      );
    }

    if (cardEls.length) {
      gsap.fromTo(cardEls,
        { opacity: 0, y: 30, rotateX: 5 },
        {
          opacity: 1, y: 0, rotateX: 0,
          stagger: 0.15,
          duration: 0.7,
          ease: 'power3.out',
          scrollTrigger: { trigger: cardEls[0], start: 'top 75%' },
        }
      );
    }
  }, []);

  return (
    <section
      ref={sectionRef}
      id="memory-loop"
      className="relative overflow-hidden py-[160px]"
    >
      <NodeNetworkBg seed={42} />

      <div className="relative z-[1] mx-auto max-w-[1200px] px-6">
        <h2
          className="section-heading max-w-[800px] font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          Built for agents, governed for humans.
        </h2>

        <p className="section-desc mt-6 max-w-[600px] text-[17px] leading-relaxed text-zmuted">
          Agents get a small memory interface. Humans keep review, lineage, revocation, and receipts.
          The point is not more context. The point is memory an agent can use responsibly.
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
                <div className="mt-4">
                  <StatusBadge status={card.status} />
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
}
