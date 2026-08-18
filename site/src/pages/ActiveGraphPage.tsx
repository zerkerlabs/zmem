import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';

const packManifest = `name: zmem
version: "0.1.15"
entry_point: zerker_memory.pack:pack
behaviors:
  - zmem.persist
  - zmem.recall
benchmark_stages:
  - zmem.bench.question_started
  - zmem.bench.memory_retrieved
  - zmem.bench.answer_generated
  - zmem.bench.question_completed`;

const installCommands = `python -m pip install -e '.[activegraph]'
activegraph pack list
python scripts/verify_activegraph_pack.py --summary-only
python examples/activegraph_host.py --summary-only`;

const benchmarkCommands = `RUN_ID="activegraph-$(date -u +%Y%m%dT%H%M%SZ)"

zmem-bench-locomo \\
  --dataset data/locomo/locomo_official_zmem.json \\
  --split default \\
  --out ".zerker/bench/activegraph/\${RUN_ID}" \\
  --run-id "\${RUN_ID}" \\
  --retrieval-mode fts-adaptive \\
  --event-batch-size 128 \\
  --limit 5`;

const envVars = `ZMEM_RETRIEVAL_MODE=fts
ZMEM_TREESHIP_ENABLED=false`;

const precallCode = `from pathlib import Path

from zerker_memory.integrations.activegraph import enable_precall_recall

enable_precall_recall(
    answer_question,
    db_path=Path(".zerker/memory.sqlite"),
    retrieval_mode="fts",
)

runtime = Runtime(
    graph,
    behaviors=[answer_question],
    llm_provider=provider,
)`;

const behaviorRows = [
  {
    name: 'zmem.persist',
    detail: 'Persists ActiveGraph events into ZMem with the source event id attached.',
  },
  {
    name: 'zmem.recall',
    detail: 'The explicit pre-call wrapper adds approved memory before prompt hashing. The installed behavior records the immutable request as an audit hook.',
  },
  {
    name: 'compact bench runner',
    detail: 'Writes trace.jsonl and scored_receipt.json instead of per-question bundles.',
  },
  {
    name: 'pack install check',
    detail: 'A runnable two-run host verifies loading, persistence, pre-call memory, and exact recorded-versus-sent prompt equality without an API key.',
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

      <section className="border-t border-zline py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[0.85fr_1.15fr]">
          <div>
            <p className="text-eyebrow text-zlime">Before the model call</p>
            <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
              Recall memory before ActiveGraph records the prompt.
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-zmuted">
              Wrap a host LLM behavior once. ZMem adds scoped memory before ActiveGraph hashes the
              prompt, emits its request event, and calls the provider. The verifier confirms the
              recorded prompt is the same prompt the provider receives.
            </p>
          </div>
          <CodeBlock code={precallCode} title="host pre-call recall" />
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
              expose approved context before model calls, and run benchmarks as compact event traces.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {behaviorRows.map((row) => (
              <Card key={row.name} className="p-5">
                <h3 className="font-heading text-xl font-semibold tracking-tight text-zink">
                  {row.name}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">{row.detail}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-zsurface py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="grid gap-6">
            <Card>
              <p className="text-eyebrow text-zmuted">Pack shape</p>
              <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
                The pack is behavior-first.
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-zmuted">
                Behaviors listen for ActiveGraph events, call the real ZMem store, preserve the
                causal event pointer, and can optionally attach Treeship digest attestations to
                memory-write receipts without sending raw memory content to Treeship.
              </p>
            </Card>
            <CodeBlock code={installCommands} title="verify the installed pack" />
          </div>
          <CodeBlock code={packManifest} title="pack/pack.yaml" />
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-eyebrow text-zlime">Benchmark integration</p>
            <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
              Preserve the selected route as a compact causal trace.
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-zmuted">
              The standard matrices now show where adaptive and always-on multi-hop differ. ActiveGraph
              can preserve the chosen retrieval run as a replayable event chain without producing a
              large receipt bundle for every question.
            </p>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              A 227-question acceptance run wrote 908 events in eight commits, produced no receipt
              bundles, and kept its event database to about 1 MB.
            </p>
            <CodeBlock code={envVars} title="runtime knobs" className="mt-6" />
          </div>
          <CodeBlock code={benchmarkCommands} title="LoCoMo fork-and-diff" />
        </div>
      </section>
    </main>
  );
}
