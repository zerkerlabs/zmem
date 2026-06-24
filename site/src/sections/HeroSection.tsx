import { useCallback } from 'react';
import { Github } from '@/components/Icons';
import NodeNetworkBg from '@/components/NodeNetworkBg';
import { useLenisInstance } from '@/hooks/useLenis';

function WireframeLandscape() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-[#030303]">
      <NodeNetworkBg seed={11} />
      <div className="absolute inset-x-[-10%] bottom-[-18%] h-[58%] opacity-55">
        <div className="h-full w-full bg-[linear-gradient(rgba(255,255,255,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.12)_1px,transparent_1px)] bg-[length:42px_42px] [transform:perspective(520px)_rotateX(62deg)] [transform-origin:50%_100%]" />
      </div>
      <div className="absolute left-1/2 top-[28%] h-[42vw] max-h-[480px] w-[72vw] max-w-[860px] -translate-x-1/2 rounded-[50%] border border-white/10 bg-[radial-gradient(ellipse_at_center,rgba(146,214,111,0.18),rgba(255,255,255,0.08)_32%,transparent_68%)] blur-[1px]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(12,12,12,0.06)_0%,rgba(3,3,3,0.44)_55%,rgba(3,3,3,0.88)_100%)]" />
    </div>
  );
}

function KineticHeadline({ text, delay = 0.5 }: { text: string; delay?: number }) {
  const words = text.split(' ');

  return (
    <h1
      className="font-heading text-[46px] font-bold leading-[0.95] text-zink sm:text-[70px] lg:text-[92px] xl:text-[104px]"
      style={{
        perspective: '400px',
        textShadow: '0 8px 28px rgba(0,0,0,0.75)',
      }}
    >
      {words.map((word, i) => (
        <span
          key={i}
          className="inline-block whitespace-nowrap"
          style={{
            transformOrigin: 'bottom center',
            animation: `kineticReveal 0.7s ${delay + i * 0.08}s cubic-bezier(0.34, 1.56, 0.64, 1) forwards`,
            opacity: 0,
          }}
        >
          {word}{i < words.length - 1 ? '\u00A0' : ''}
        </span>
      ))}
    </h1>
  );
}

export default function HeroSection() {
  const lenis = useLenisInstance();

  const scrollTo = useCallback((id: string) => {
    if (lenis) {
      lenis.scrollTo(id);
    } else {
      const el = document.querySelector(id);
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lenis]);

  return (
    <section id="hero" className="relative min-h-screen overflow-hidden bg-zbg supports-[height:100svh]:min-h-[100svh]">
      <WireframeLandscape />

      <div className="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0.18)_0%,rgba(0,0,0,0.38)_58%,rgba(0,0,0,0.72)_100%)]" />

      <div
        id="hero-content"
        className="relative z-[2] flex min-h-screen flex-col items-center justify-center px-6 text-center supports-[height:100svh]:min-h-[100svh]"
      >
        <div className="max-w-[900px]">
          <p
            className="mb-6 text-eyebrow text-zlime"
            style={{ animation: 'fadeSlideUp 0.6s 0.3s ease-out forwards', opacity: 0 }}
          >
            Open-source local memory for agents
          </p>

          <KineticHeadline text="Agent memory you can verify." delay={0.5} />

          <p
            className="mx-auto mt-6 max-w-[640px] text-[17px] leading-relaxed text-[#D8D8D8] max-sm:hidden"
            style={{ animation: 'fadeSlideUp 0.6s 0.8s ease-out forwards', opacity: 0, textShadow: '0 4px 18px rgba(0,0,0,0.9)' }}
          >
            Local-first memory for AI agents. Request approved memories, propose new facts,
            and verify what actually shaped the next action.
          </p>

          <p
            className="mx-auto mt-6 max-w-[320px] text-[17px] leading-relaxed text-[#D8D8D8] sm:hidden"
            style={{ animation: 'fadeSlideUp 0.6s 0.8s ease-out forwards', opacity: 0, textShadow: '0 4px 18px rgba(0,0,0,0.9)' }}
          >
            Local memory for agents. Receipts for what shaped the work.
          </p>

          <p
            className="mx-auto mt-4 hidden max-w-[600px] text-[14px] leading-relaxed text-[#AFAFAF] sm:block"
            style={{ animation: 'fadeSlideUp 0.6s 0.9s ease-out forwards', opacity: 0, textShadow: '0 4px 18px rgba(0,0,0,0.9)' }}
          >
            Receipts show what was used, what was withheld, and the Merkle root behind the action.
            Treeship can publish a public proof URL when needed.
          </p>

          <div
            className="mt-10 flex flex-wrap items-center justify-center gap-4"
            style={{ animation: 'fadeSlideUp 0.5s 1.0s ease-out forwards', opacity: 0 }}
          >
            <button
              onClick={() => scrollTo('#install')}
              className="rounded-full bg-zlime px-8 py-3.5 text-cta text-[#030303] transition-all duration-150 hover:scale-[1.03] hover:bg-[#7BC45A] hover:shadow-[0_0_24px_rgba(146,214,111,0.3)]"
            >
              Install ZMem
            </button>
            <button
              onClick={() => { window.location.href = '/proof'; }}
              className="rounded-full border border-zline bg-transparent px-8 py-3.5 text-cta text-zink transition-all duration-150 hover:border-zlime hover:text-zlime"
            >
              View Proof Matrix
            </button>
            <a
              href="https://github.com/zerkerlabs/zmem"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-zline bg-transparent px-8 py-3.5 text-cta text-zink transition-all duration-150 hover:border-zlime hover:text-zlime"
            >
              <Github size={16} />
              GitHub
            </a>
          </div>
        </div>

        <div
          className="absolute bottom-10 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2"
          style={{ animation: 'scrollIndicatorFade 0.5s 3s ease-out forwards' }}
        >
          <div className="relative h-10 w-px bg-zmuted">
            <div
              className="absolute left-1/2 top-0 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-zlime"
              style={{ animation: 'scrollPulseDot 2s ease-in-out infinite' }}
            />
          </div>
          <span className="text-caption text-zdim">Scroll</span>
        </div>
      </div>
    </section>
  );
}
