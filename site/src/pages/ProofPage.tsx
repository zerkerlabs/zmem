import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';

const featureRows = [
  { feature: 'Capture source', proof: 'zmem remember --type semantic "fact"' },
  { feature: 'Review before trust', proof: 'zmem queue / promote / reject / revoke' },
  { feature: 'Inject scoped context', proof: 'zmem inject --agent codex --risk medium "task"' },
  { feature: 'Explain influence', proof: 'zmem why <action-id>' },
  { feature: 'Verify integrity', proof: 'zmem verify <action-id>' },
  { feature: 'Export evidence', proof: 'zmem bundle <action-id>' },
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
    detail: 'Local bundles stay private by default; Treeship publishing is optional when a public URL is useful.',
    command: 'zmem treeship publish <action-id>',
  },
];

const benchmarkRows = [
  { item: 'LoCoMo FTS official run', note: '1,986 questions, F1 0.3752, EM 0.3721, trace sha256 67a005bf...971d0c.' },
  { item: 'ActiveGraph compact trace', note: 'Event-sourced trace.jsonl plus scored_receipt.json, without per-question bundle files.' },
  { item: 'LoCoMo fts-multihop', note: 'Tests whether retrieval decomposition moves multi-hop and open-domain categories.' },
  { item: 'LoCoMo rerank', note: 'Tests whether pseudo embedding rerank improves retrieval depth against the same dataset.' },
  { item: 'LongMemEval-S', note: 'Highest-priority abstention and token-efficiency benchmark after LoCoMo deltas.' },
  { item: 'BEAM', note: 'Scale benchmark for 100K to 10M token memory pressure and causal traces.' },
  { item: 'Metrics', note: 'Accuracy, stable wins/misses, latency, tokens, abstention, and proof verification.' },
  { item: 'Public claims', note: 'Official rankings wait for primary-source methods and reproducible benchmark submissions.' },
];

const statusCode = `Memory store: local
Receipt mode: enabled
Merkle root: sha256:7bb4...91e2
Agent context: scoped
Proof export: local bundle
Public proof: optional Treeship URL`;

const proofCode = `$ zmem inject --agent codex --risk medium "continue release"
# returns action id

$ zmem why <action-id>
# shows injected memory, withheld memory, and source details

$ zmem verify <action-id>
# verifies the local receipt against the Merkle state

$ zmem treeship publish <action-id>
# optional public proof URL`;

const locomoNextRuns = `zmem bench run locomo \\
  --dataset data/locomo/locomo_official_zmem.json \\
  --split default \\
  --out .zerker/bench/locomo-official-v1 \\
  --seed 42 \\
  --run-id fts-multihop \\
  --retrieval-mode fts-multihop

zmem bench run locomo \\
  --dataset data/locomo/locomo_official_zmem.json \\
  --split default \\
  --out .zerker/bench/locomo-official-v1 \\
  --seed 42 \\
  --run-id pseudo-embedding-rerank \\
  --retrieval-mode pseudo-embedding-rerank`;

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
              a receipt bundle or optional Treeship proof URL can show what influenced the agent.
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
                <h3 className="font-heading text-xl font-semibold tracking-tight text-zink">{row.item}</h3>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">{row.note}</p>
              </Card>
            ))}
          </div>
          <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-[0.9fr_1.1fr]">
            <Card>
              <p className="text-eyebrow text-zmuted">Next run order</p>
              <h3 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
                Depth first, then rerank.
              </h3>
              <p className="mt-4 text-sm leading-relaxed text-zmuted">
                The FTS baseline says retrieval depth is the bottleneck. Run fts-multihop first,
                then pseudo embedding rerank, so the delta explains whether decomposition or
                reranking moves the weak categories.
              </p>
            </Card>
            <CodeBlock code={locomoNextRuns} title="next LoCoMo runs" />
          </div>
        </div>
      </section>
    </main>
  );
}
