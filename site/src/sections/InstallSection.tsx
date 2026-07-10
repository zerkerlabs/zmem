import { useState } from 'react';
import { Copy, Check } from '@/components/Icons';

const quickSteps = [
  {
    num: '01',
    title: 'Install ZMem',
    desc: 'Run the installer. It creates the local environment, initializes .zerker, runs doctor, and prints readiness.',
    code: 'curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash',
  },
  {
    num: '02',
    title: 'Connect an agent',
    desc: 'Install or export the MCP config for Codex, Claude Code, Cursor, OpenClaw, Hermes, or generic MCP.',
    code: 'zmem agent install cursor --summary-only',
  },
  {
    num: '03',
    title: 'Prove the setup',
    desc: 'Run the compact status check, agent smoke, or local UI before handing memory to real work.',
    code: 'zmem status --summary-only',
  },
];

export default function InstallSection() {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText('curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="install" className="bg-[#050505] py-[160px]">
      <div className="mx-auto max-w-[1120px] px-6">
        <h2
          className="section-heading text-center font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          Install locally. Verify before you trust it.
        </h2>

        <p className="section-desc mx-auto mt-6 max-w-[560px] text-center text-[17px] leading-relaxed text-zmuted">
          The installer creates the local workspace, runs the readiness checks, and generates the manual-agent pack.
          Agent config installs are explicit, so nothing is silently wired into your tools.
        </p>

        {/* Install Command */}
        <div className="cmd-block mx-auto mt-12 flex max-w-[720px] items-stretch gap-3">
          <div className="flex-1 overflow-hidden rounded-lg border border-[rgba(146,214,111,0.3)] bg-[#0A0A0A]">
            <div className="flex items-center gap-2 border-b border-zline px-4 py-2.5 bg-[#141414]">
              <span
                className="inline-block h-2 w-2 rounded-full bg-zlime"
                style={{ animation: 'statusPulse 2s ease-in-out infinite' }}
              />
              <span className="text-caption text-zmuted">install.sh</span>
            </div>
            <div className="px-6 py-7">
              <code
                className="font-mono text-[#D9E3D0]"
                style={{ fontSize: 'clamp(16px, 2.5vw, 22px)' }}
              >
                curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
              </code>
            </div>
          </div>
          <button
            onClick={handleCopy}
            className="flex h-auto w-11 flex-shrink-0 items-center justify-center rounded border border-zline bg-transparent text-zmuted transition-colors duration-200 hover:border-zlime hover:text-zlime"
            aria-label="Copy install command"
          >
            {copied ? <Check size={18} className="text-zlime" /> : <Copy size={18} />}
          </button>
        </div>

        <p className="mt-3 text-center text-caption text-zdim">
          Requires Python 3.10+. Memory stays in local SQLite files you control.
        </p>

        {/* Quick Start Steps */}
        <div className="mt-20 grid grid-cols-1 gap-6 md:grid-cols-3">
          {quickSteps.map((step) => (
            <div key={step.num} className="quick-step">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[rgba(146,214,111,0.15)]">
                <span className="font-mono text-[13px] font-bold text-zlime">{step.num}</span>
              </div>
              <h3 className="mt-4 font-heading text-2xl font-semibold tracking-tight text-zink">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-zmuted">{step.desc}</p>
              <div className="mt-4 overflow-hidden rounded bg-[#0A0A0A] border border-zline px-3.5 py-2.5">
                <code className="font-mono text-xs text-[#D9E3D0]">{step.code}</code>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
