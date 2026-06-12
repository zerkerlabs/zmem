import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const pills = [
  { label: 'Local SQLite' },
  { label: 'Agent MCP' },
  { label: 'Merkle Receipts' },
  { label: 'Open Source' },
];

export default function TrustBarSection() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const items = el.querySelectorAll('.trust-pill');
    gsap.fromTo(items,
      { opacity: 0, y: 20 },
      {
        opacity: 1, y: 0,
        stagger: 0.1,
        duration: 0.5,
        ease: 'power2.out',
        scrollTrigger: { trigger: el, start: 'top 95%' },
      }
    );
  }, []);

  return (
    <div
      ref={sectionRef}
      className="sticky top-0 z-30 border-y border-zline bg-[rgba(18,18,18,0.8)] backdrop-blur-xl py-5"
    >
      <div className="flex flex-wrap items-center justify-center gap-8 md:gap-12">
        {pills.map((pill) => (
          <div key={pill.label} className="trust-pill flex items-center gap-2.5">
            <span
              className="inline-block h-2 w-2 border border-zlime"
              style={{ transform: 'rotate(45deg)' }}
            />
            <span className="text-caption text-zmuted">{pill.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
