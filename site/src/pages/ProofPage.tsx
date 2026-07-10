import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';

const featureRows = [
  { feature: 'Capture source', proof: 'zmem remember --type semantic "fact"' },
  { feature: 'Review before trust', proof: 'zmem queue / promote / reject / revoke' },
  { feature: 'Inject scoped context', proof: 'zmem inject --agent codex --risk medium "task"' },
  { feature: 'Explain influence', proof: 'zmem why <action-id>' },
  { feature: 'Verify integrity', proof: 'zmem verify <action-id>' },
  { feature: 'Export evidence', proof: 'zmem bundle <action-id>' },
  { feature: 'Attest write digests', proof: 'ZMEM_TREESHIP_AUTO_SIGN=1' },
  { feature: 'Publish public proof', proof: 'zmem treeship publish <action-id>' },
  { feature: 'Hand off state', proof: 'zmem handoff --summary-only' },
  { feature: 'ActiveGraph memory', proof: 'pack/pack.yaml' },
  { feature: 'Compact benchmark trace', proof: 'zmem-bench-locomo --dataset <file>' },
];

const proofSteps = [
  {
    title: 'A memory is written with provenance',
    detail: 'Each useful memory can carry source metadata, actor context, timestamps, and content hashes.',
    command: 'zmem remember --source <uri> "fact"',
  },
  {
    title: 'An agent receives scoped context',
    detail: 'ZMem injects approved memory and records which memories were included or withheld.',
    command: 'zmem inject --agent codex --risk medium "task"',
  },
  {
    title: 'The action gets a receipt',
    detail: 'The receipt links action, memory ids, digests, policy state, and the local Merkle root.',
    command: 'zmem why <action-id>',
  },
  {
    title: 'The proof can be shared',
    detail: 'Compact v2 bundles stay local by default and keep older v1 artifacts verifiable. Treeship can attest a digest or publish a proof URL when sharing is useful.',
    command: 'zmem treeship publish <action-id>',
  },
];

const benchmarkRows = [
  { item: 'LoCoMo adaptive route', note: '1,986 questions, 0.6108 local accuracy, 29 gains and one loss versus FTS. Matrix and comparison verify.' },
  { item: 'Always-on multi-hop', note: '0.6067 local LoCoMo accuracy. It gains 98 and loses 78 versus FTS, so it remains an explicit specialist mode.' },
  { item: 'LongMemEval', note: 'Adaptive scores 0.766 with 13 regression-free gains over FTS; always-on multi-hop reaches 0.780.' },
  { item: 'Pseudo rerank', note: 'Matches FTS on every scored LoCoMo and LongMemEval category in the current deterministic local path.' },
  { item: 'ActiveGraph compact trace', note: 'Event-sourced trace.jsonl plus scored_receipt.json, without per-question bundle files.' },
  { item: 'BEAM', note: 'Scale benchmark for 100K to 10M token memory pressure and causal traces.' },
  { item: 'Metrics', note: 'Accuracy, stable wins/misses, latency, tokens, abstention, and proof verification.' },
  { item: 'Public claims', note: 'Official rankings wait for primary-source methods and reproducible benchmark submissions.' },
];

const statusCode = `Memory store: local
Receipt mode: enabled
Merkle root: sha256:7bb4...91e2
Agent context: scoped
Write attestation: optional digest-only Treeship artifact
Proof export: compact v2 local bundle
Public proof: optional Treeship URL`;

const proofCode = `$ zmem inject --agent codex --risk medium --summary-only "continue release"
# returns action id

$ zmem why <action-id> --summary-only
# shows injected memory, withheld memory, and source details

$ zmem verify <action-id>
# verifies the local receipt against the Merkle state

$ ZMEM_TREESHIP_AUTO_SIGN=1 zmem remember --type semantic "fact"
# optional: Treeship attests only sha256:<receipt_hash>

$ zmem treeship publish <action-id>
# optional public proof URL`;

const locomoAdaptiveRun = `RUN_ID="locomo-adaptive-$(date -u +%Y%m%dT%H%M%SZ)"

zmem bench matrix locomo \\
  --dataset data/locomo/locomo_official_zmem.json \\
  --split default \\
  --out .zerker/bench/runs \\
  --seed 42 \\
  --run-id "$RUN_ID" \\
  --mode fts-adaptive \\
  --trace \\
  --compact-artifacts \\
  --summary-only

zmem bench verify \\
  ".zerker/bench/runs/$RUN_ID/benchmark-matrix.json" \\
  --summary-only`;

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
            Proof for memory-influenced agent actions.
          </h1>
          <p className="mt-6 max-w-[680px] text-[17px] leading-relaxed text-zmuted">
            ZMem records where memory came from, what an agent saw, what was withheld, and how that
            memory shaped an action. The point is simple: useful memory should be inspectable.
          </p>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <Card>
              <p className="text-eyebrow text-zmuted">Current state</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              Local-first by default. Shareable when needed.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              ZMem keeps memory and receipts on the user's machine first. When a team needs evidence,
              ZMem can share a compact receipt bundle, publish a proof URL, or ask Treeship to attest
              only the write-receipt digest.
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
                The proof path is made of product actions.
              </h2>
            </div>
            <p className="max-w-[420px] text-sm leading-relaxed text-zmuted">
              These commands let an operator or agent capture, inspect, verify, and share memory evidence.
            </p>
          </div>

          <Card className="mt-10 overflow-hidden p-0">
            <div className="hidden border-b border-zline px-6 py-4 md:grid md:grid-cols-[42%_58%]">
              <span className="text-eyebrow text-zmuted">Feature</span>
              <span className="text-eyebrow text-zmuted">Proof command</span>
            </div>
            {featureRows.map((row) => (
              <div
                key={row.feature}
                className="border-b border-[rgba(42,42,42,0.55)] px-6 py-4 md:grid md:grid-cols-[42%_58%] md:items-center"
              >
                <span className="text-sm text-zink">{row.feature}</span>
                <code className="mt-2 block font-mono text-[11px] text-[#D9E3D0] md:mt-0">{row.proof}</code>
              </div>
            ))}
          </Card>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Receipt lifecycle</p>
          <h2 className="mt-3 max-w-[760px] font-heading text-4xl font-semibold tracking-tight text-zink">
            From remembered fact to verifiable action.
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2">
            {proofSteps.map((step) => (
              <Card key={step.title}>
                <h3 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                  {step.title}
                </h3>
                <p className="mt-4 text-sm leading-relaxed text-zmuted">{step.detail}</p>
                <code className="mt-5 block rounded bg-[#0A0A0A] px-3.5 py-2.5 font-mono text-[11px] text-[#D9E3D0]">
                  {step.command}
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
              receipts. Treeship is optional: it can sign the compact digest for write-time attribution,
              or publish a public proof URL when a local receipt needs to travel.
            </p>
          </div>
          <CodeBlock code={proofCode} title="memory receipt flow" />
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Benchmark evidence</p>
          <h2 className="mt-3 max-w-[760px] font-heading text-4xl font-semibold tracking-tight text-zink">
            Retrieval quality is measured separately from proof quality.
          </h2>
          <p className="mt-5 max-w-[680px] text-sm leading-relaxed text-zmuted">
            ZMem measures accuracy, regressions, latency, tokens, abstention, and proof verification.
            The current numbers are local provisional evidence, not official leaderboard claims.
          </p>
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {benchmarkRows.map((row) => (
              <Card key={row.item} className="p-5">
                <h3 className="font-heading text-xl font-semibold tracking-tight text-zink">{row.item}</h3>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">{row.note}</p>
              </Card>
            ))}
          </div>
          <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-[0.9fr_1.1fr]">
            <Card>
              <p className="text-eyebrow text-zmuted">Routing decision</p>
              <h3 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
                Escalate only when the query needs it.
              </h3>
              <p className="mt-4 text-sm leading-relaxed text-zmuted">
                Always-on decomposition finds more individual answers but creates too many regressions.
                The adaptive route keeps ordinary queries on their base route and records why a compound query was
                escalated or suppressed.
              </p>
            </Card>
            <CodeBlock code={locomoAdaptiveRun} title="reproduce adaptive LoCoMo" />
          </div>
        </div>
      </section>
    </main>
  );
}
