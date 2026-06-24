import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';
import StatusBadge from '@/components/StatusBadge';

const packManifest = `name: zmem
version: "0.1.0"
entry_point: zerker_memory.integrations.activegraph
behaviors:
  - zmem.persist
  - zmem.recall
  - zmem.bench.question_started
  - zmem.bench.memory_retrieved
  - zmem.bench.answer_generated
  - zmem.bench.question_completed`;

const benchmarkCommands = `zmem bench run locomo \\
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

const envVars = `ZMEM_RETRIEVAL_MODE=fts
ZMEM_TREESHIP_ENABLED=false`;

const behaviorRows = [
  {
    name: 'zmem.persist',
    status: 'built' as const,
    detail: 'Persists ActiveGraph events into ZMem with the source event id attached.',
  },
  {
    name: 'zmem.recall',
    status: 'built' as const,
    detail: 'Injects approved memory into LLM requests, controlled by ZMEM_RETRIEVAL_MODE.',
  },
  {
    name: 'compact bench runner',
    status: 'built' as const,
    detail: 'Writes trace.jsonl and scored_receipt.json instead of per-question bundles.',
  },
  {
    name: 'real loader smoke',
    status: 'pending' as const,
    detail: 'Source-level pack is built. ActiveGraph loader install smoke waits for a networked environment.',
  },
];

export default function ActiveGraphPage() {
  return (
    <main className="bg-zbg pt-28">
      <section className="border-b border-zline pb-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">ActiveGraph integration</p>
          <h1
            className="mt-5 max-w-[900px] font-heading font-bold leading-[0.95] text-zink"
            style={{ fontSize: 'clamp(44px, 7vw, 92px)' }}
          >
            Event-driven agents with memory across runs.
          </h1>
          <p className="mt-6 max-w-[700px] text-[17px] leading-relaxed text-zmuted">
            ActiveGraph gives agents an event chain. ZMem uses that chain to persist memory,
            recall approved context, and produce compact benchmark traces that can be replayed.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="/blog/activegraph-memory"
              className="rounded-full bg-zlime px-6 py-3 text-cta text-[#030303] transition-colors hover:bg-[#7BC45A]"
            >
              Read use case
            </a>
            <a
              href="/proof"
              className="rounded-full border border-zline px-6 py-3 text-cta text-zink transition-colors hover:border-zlime hover:text-zlime"
            >
              Proof matrix
            </a>
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-eyebrow text-zlime">What ships</p>
            <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
              Two practical uses, one event log.
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-zmuted">
              The integration is intentionally small: persist memories from ActiveGraph events,
              recall memories before LLM calls, and run benchmarks as compact event traces.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {behaviorRows.map((row) => (
              <Card key={row.name} className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-heading text-xl font-semibold tracking-tight text-zink">
                    {row.name}
                  </h3>
                  <StatusBadge status={row.status} />
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">{row.detail}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-zsurface py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[0.95fr_1.05fr]">
          <Card>
            <p className="text-eyebrow text-zmuted">Pack shape</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              The pack is behavior-first.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              Behaviors listen for ActiveGraph events, call the real ZMem store, preserve the
              causal event pointer, and optionally emit Treeship memory read/write artifacts.
            </p>
          </Card>
          <CodeBlock code={packManifest} title="pack/pack.yaml" />
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-eyebrow text-zlime">Next benchmark runs</p>
            <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
              Test retrieval depth before adding more ingestion machinery.
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-zmuted">
              The official FTS LoCoMo run showed the bottleneck clearly: multi-hop and open-domain
              retrieval are the weak categories. Run multihop first, then pseudo embedding rerank,
              so the delta tells us whether decomposition or reranking is moving the score.
            </p>
            <CodeBlock code={envVars} title="runtime knobs" className="mt-6" />
          </div>
          <CodeBlock code={benchmarkCommands} title="LoCoMo fork-and-diff" />
        </div>
      </section>
    </main>
  );
}
