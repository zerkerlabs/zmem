import CodeBlock from '@/components/CodeBlock';

const steps = [
  {
    num: '01',
    title: 'Install an agent preset',
    desc: 'Write or export the MCP config for Codex, Claude Code, Cursor, OpenClaw, Hermes, or a generic MCP client.',
  },
  {
    num: '02',
    title: 'Generate the manual pack',
    desc: 'Produce the shared prompt, config exports, checklists, and one-file manual-agent pack for handoff.',
  },
  {
    num: '03',
    title: 'Restore with proof',
    desc: 'Package a memory snapshot, restore guide, receipt bundle, and agent prompt so another agent can continue from the same governed state.',
  },
];

const terminalCode = `$ zmem agent install cursor --summary-only
Config: .zerker/agents/cursor-mcp.json
Checklist: .zerker/agents/cursor-checklist.md

$ zmem agent pack --summary-only
Manual agent pack ready
Pack: .zerker/agents/manual-agent-pack.md

$ zmem handoff --summary-only
Snapshot verify: ok
Bundle verify: ok
Handoff package ready

$ zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff --summary-only
Restore: ok`;

const consolePanels = [
  {
    title: 'Connected agents',
    command: 'zmem status --summary-only',
    rows: [
      ['Codex', 'installed'],
      ['Claude Code', 'installed'],
      ['Cursor', 'exported'],
      ['Hermes', 'pack ready'],
      ['Generic MCP', 'pack ready'],
    ],
  },
  {
    title: 'Memory provenance',
    command: 'zmem inspect <memory-id>',
    rows: [
      ['source', 'human / system / tool / agent'],
      ['status', 'active / proposed / revoked'],
      ['scope', 'project / user / policy'],
      ['lineage', 'parents + descendants'],
    ],
  },
  {
    title: 'Action trace',
    command: 'zmem why <action-id>',
    rows: [
      ['agent', 'who requested memory'],
      ['injected', 'what reached context'],
      ['withheld', 'what stayed out'],
      ['receipt', 'local verify + optional publish'],
    ],
  },
];

export default function AgentContinuitySection() {
  return (
    <section
      id="agents"
      className="bg-zsurface py-[160px]"
    >
      <div className="mx-auto max-w-[1120px] px-6">
        <h2
          className="section-heading text-center font-heading font-bold text-zink"
          style={{ fontSize: 'clamp(36px, 5vw, 64px)', letterSpacing: '-0.03em', lineHeight: 1.0 }}
        >
          Move governed memory between agents.
        </h2>

        <p className="section-desc mx-auto mt-6 max-w-[640px] text-center text-[17px] leading-relaxed text-zmuted">
          Package approved memory, policy, prompts, snapshots, and receipts so the next
          agent starts from governed state instead of a pasted transcript. Shared recall
          is not shared authority.
        </p>

        <div className="mt-12 rounded-lg border border-zline bg-[#0A0A0A] p-5">
          <div className="flex flex-col justify-between gap-3 border-b border-zline pb-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-eyebrow text-zlime">Agent memory console</p>
              <h3 className="mt-2 font-heading text-3xl font-semibold tracking-tight text-zink">
                See who is connected, where memory came from, and what used it.
              </h3>
            </div>
            <code className="font-mono text-xs text-[#D9E3D0]">zmem ui</code>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
            {consolePanels.map((panel) => (
              <div key={panel.title} className="console-panel rounded-md border border-zline bg-zsurface p-4">
                <div className="flex items-start justify-between gap-3">
                  <h4 className="font-heading text-xl font-semibold tracking-tight text-zink">
                    {panel.title}
                  </h4>
                  <span className="rounded-full border border-[rgba(146,214,111,0.25)] px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-zlime">
                    local
                  </span>
                </div>
                <code className="mt-2 block font-mono text-[11px] text-zmuted">{panel.command}</code>
                <div className="mt-4 flex flex-col gap-2">
                  {panel.rows.map(([label, value]) => (
                    <div key={label} className="flex items-center justify-between gap-4 border-t border-[rgba(42,42,42,0.65)] pt-2">
                      <span className="text-caption text-zdim">{label}</span>
                      <span className="text-right text-xs text-zmuted">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div id="handoff" className="mt-16 grid grid-cols-1 gap-10 md:grid-cols-2">
          {/* Left: Steps */}
          <div className="relative flex flex-col gap-6">
            {/* Vertical connecting line */}
            <div className="absolute left-[14px] top-8 bottom-8 w-px bg-zline" />

            {steps.map((step) => (
              <div key={step.num} className="step-card relative flex items-start gap-5">
                {/* Number badge */}
                <div className="relative z-10 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-[rgba(146,214,111,0.15)]">
                  <span className="font-mono text-[13px] font-bold text-zlime">{step.num}</span>
                </div>
                <div>
                  <h3 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                    {step.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-zmuted">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Right: Terminal */}
          <div className="terminal-block">
            <CodeBlock code={terminalCode} title="zmem handoff --summary-only" />
          </div>
        </div>
      </div>
    </section>
  );
}
