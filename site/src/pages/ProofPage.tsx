import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';
import StatusBadge from '@/components/StatusBadge';

const featureRows = [
  { feature: 'Local SQLite memory', status: 'built' as const, proof: 'zmem status --summary-only' },
  { feature: 'FTS retrieval baseline', status: 'built' as const, proof: 'zmem search "deploy runbook" --scope project' },
  { feature: 'Typed memory records', status: 'built' as const, proof: 'zmem remember --type semantic "fact"' },
  { feature: 'Review lifecycle', status: 'built' as const, proof: 'zmem queue / promote / reject / revoke' },
  { feature: 'Policy-scoped injection', status: 'built' as const, proof: 'zmem inject --agent codex --risk medium "task"' },
  { feature: 'Agent MCP setup', status: 'built' as const, proof: 'zmem agent install cursor --summary-only' },
  { feature: 'Manual agent pack', status: 'built' as const, proof: 'zmem agent pack --summary-only' },
  { feature: 'Action receipts', status: 'built' as const, proof: 'zmem why <action-id>' },
  { feature: 'Merkle verification', status: 'built' as const, proof: 'zmem verify <action-id>' },
  { feature: 'Handoff restore', status: 'built' as const, proof: 'zmem handoff --summary-only' },
  { feature: 'Treeship publish', status: 'built' as const, proof: 'zmem treeship publish <action-id>' },
  { feature: 'Bench harness', status: 'alpha' as const, proof: 'zmem bench ...' },
];

const gates = [
  {
    title: 'Local alpha gate',
    status: 'ready' as const,
    detail: 'Local workspace, release pack, handoff, operator packet, and receipt surfaces are generated.',
    command: 'zmem release-pack --summary-only',
  },
  {
    title: 'Clean-shell public verify',
    status: 'blocked' as const,
    detail: 'Strict publish remains blocked until the external clean-shell logs are captured.',
    command: '.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh',
  },
  {
    title: 'Launch assets',
    status: 'blocked' as const,
    detail: 'Final screenshots and GIFs must be saved under the launch-proof asset paths.',
    command: 'zmem verify-launch-assets --summary-only',
  },
  {
    title: 'Return packet',
    status: 'blocked' as const,
    detail: 'The return archive exists, but it is not acceptable until logs and assets are present.',
    command: 'zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only',
  },
];

const benchmarkRows = [
  { item: 'Synthetic matrix', status: 'verified', note: 'Current local matrix verifies with mode result hashes and aggregate Merkle roots.' },
  { item: 'LongMemEval scaffold', status: 'alpha', note: 'Local JSON/JSONL adapter with provisional deterministic scoring and proof artifacts.' },
  { item: 'LoCoMo scaffold', status: 'alpha', note: 'Local conversation-memory scaffold with comparison/report proof-hop coverage.' },
  { item: 'Metrics', status: 'alpha', note: 'Accuracy, stable wins/misses, latency, tokens, abstention, and proof verification.' },
  { item: 'Rendered reports', status: 'alpha', note: 'Matrix reports, dashboards, and public pages surface hashes and proof roots.' },
  { item: 'Public claims', status: 'gated', note: 'Official rankings wait for primary-source methods and reproducible benchmark submissions.' },
];

const statusCode = `Workspace ready: yes
Memory proof ready: yes
Manual pack ready: yes
Strict publish ready: no

Agent handoff:
  Codex: ok
  Claude Code: ok
  Cursor: ok
  OpenClaw: ok
  Hermes: ok
  Generic MCP Agent: ok`;

const proofCode = `$ zmem inject --agent codex --risk medium "continue release"
# returns action id

$ zmem why <action-id>
# shows injected memory, withheld memory, and source details

$ zmem verify <action-id>
# verifies the local receipt against the Merkle state

$ zmem treeship publish <action-id>
# optional public proof URL`;

export default function ProofPage() {
  return (
    <main className="bg-zbg pt-28">
      <section className="border-b border-zline pb-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">ZMem proof page</p>
          <h1
            className="mt-5 max-w-[860px] font-heading font-bold leading-[0.95] text-zink"
            style={{ fontSize: 'clamp(44px, 7vw, 96px)' }}
          >
            What exists, what is proven, and what is still gated.
          </h1>
          <p className="mt-6 max-w-[680px] text-[17px] leading-relaxed text-zmuted">
            This page is the compact public map of ZMem alpha readiness. It separates built product
            surfaces from launch evidence, and keeps every claim tied to a command or explicit gate.
          </p>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <p className="text-eyebrow text-zmuted">Current state</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              Local product ready. Strict public publish still gated.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              The repo can run local memory, agent setup, handoff, receipts, and release-pack generation.
              The remaining launch gate is external evidence: clean-shell public verify logs and final assets.
            </p>
          </Card>
          <CodeBlock code={statusCode} title="zmem status --summary-only" />
        </div>
      </section>

      <section className="bg-zsurface py-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-eyebrow text-zlime">Feature matrix</p>
              <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
                Built surfaces mapped to commands.
              </h2>
            </div>
            <p className="max-w-[420px] text-sm leading-relaxed text-zmuted">
              A feature counts here only when it has a concrete local command or generated artifact.
            </p>
          </div>

          <Card className="mt-10 overflow-hidden p-0">
            <div className="hidden border-b border-zline px-6 py-4 md:grid md:grid-cols-[40%_18%_42%]">
              <span className="text-eyebrow text-zmuted">Feature</span>
              <span className="text-eyebrow text-zmuted">Status</span>
              <span className="text-eyebrow text-zmuted">Proof command</span>
            </div>
            {featureRows.map((row) => (
              <div
                key={row.feature}
                className="border-b border-[rgba(42,42,42,0.55)] px-6 py-4 md:grid md:grid-cols-[40%_18%_42%] md:items-center"
              >
                <span className="text-sm text-zink">{row.feature}</span>
                <div className="mt-2 md:mt-0">
                  <StatusBadge status={row.status} />
                </div>
                <code className="mt-2 block font-mono text-[11px] text-[#D9E3D0] md:mt-0">{row.proof}</code>
              </div>
            ))}
          </Card>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Launch gates</p>
          <h2 className="mt-3 max-w-[760px] font-heading text-4xl font-semibold tracking-tight text-zink">
            The alpha does not pretend external proof already happened.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2">
            {gates.map((gate) => (
              <Card key={gate.title}>
                <div className="flex items-start justify-between gap-4">
                  <h3 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                    {gate.title}
                  </h3>
                  <StatusBadge status={gate.status} />
                </div>
                <p className="mt-4 text-sm leading-relaxed text-zmuted">{gate.detail}</p>
                <code className="mt-5 block rounded bg-[#0A0A0A] px-3.5 py-2.5 font-mono text-[11px] text-[#D9E3D0]">
                  {gate.command}
                </code>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-zsurface py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-eyebrow text-zlime">Proof primitive</p>
            <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
              Receipts show what memory shaped an action.
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-zmuted">
              ZMem records injected and withheld memory, source metadata, local Merkle roots, and action
              receipts. Treeship is the optional public proof layer when a local receipt needs a shareable URL.
            </p>
          </div>
          <CodeBlock code={proofCode} title="memory receipt flow" />
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Benchmark roadmap</p>
          <h2 className="mt-3 max-w-[760px] font-heading text-4xl font-semibold tracking-tight text-zink">
            Retrieval quality will be measured separately from proof quality.
          </h2>
          <p className="mt-5 max-w-[680px] text-sm leading-relaxed text-zmuted">
            ZMem should compete with open-source memory systems on retrieval while keeping its unique
            differentiator: verifiable memory use. The benchmark harness is the next proof-bearing layer.
          </p>
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {benchmarkRows.map((row) => (
              <Card key={row.item} className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-heading text-xl font-semibold tracking-tight text-zink">{row.item}</h3>
                  <span className="rounded-full border border-zline px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-zmuted">
                    {row.status}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">{row.note}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
