import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';

const traceLine = `{
  "question_id": "locomo_0421",
  "retrieval_mode": "fts-multihop",
  "retrieved_count": 6,
  "receipt_id": "rec_...",
  "trace_sha256": "sha256:...",
  "ag_event_id": "evt_...",
  "ag_run_id": "run_...",
  "line_hash": "sha256:..."
}`;

const useCases = [
  {
    title: 'Agents remember across runs',
    text: 'ActiveGraph runs can be short-lived. ZMem scopes memories to the session, so a later run can recall what earlier events established.',
  },
  {
    title: 'Memory keeps causality',
    text: 'Every persisted memory can carry the ActiveGraph event that caused it, which makes source tracing concrete instead of narrative.',
  },
  {
    title: 'Benchmarks stay small',
    text: 'The runner records compact JSONL trace lines and one scored receipt instead of writing huge per-question bundles.',
  },
];

export default function ActiveGraphBlogPage() {
  return (
    <main className="bg-zbg pt-28">
      <article>
        <section className="border-b border-zline pb-20">
          <div className="mx-auto max-w-[900px] px-6">
            <p className="text-eyebrow text-zlime">Use case</p>
            <h1
              className="mt-5 font-heading font-bold leading-[0.95] text-zink"
              style={{ fontSize: 'clamp(44px, 7vw, 92px)' }}
            >
              ActiveGraph gives agents events. ZMem gives those events memory.
            </h1>
            <p className="mt-6 max-w-[720px] text-[17px] leading-relaxed text-zmuted">
              The useful primitive is not a bigger transcript. It is a causal memory loop:
              event happens, memory is written, later context is recalled, and the trace can be checked.
            </p>
          </div>
        </section>

        <section className="py-20">
          <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 md:grid-cols-3">
            {useCases.map((item) => (
              <Card key={item.title}>
                <h2 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                  {item.title}
                </h2>
                <p className="mt-4 text-sm leading-relaxed text-zmuted">{item.text}</p>
              </Card>
            ))}
          </div>
        </section>

        <section className="bg-zsurface py-20">
          <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <p className="text-eyebrow text-zlime">Why this matters</p>
              <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
                Memory should be replayable enough to trust.
              </h2>
              <p className="mt-5 text-sm leading-relaxed text-zmuted">
                A long-running agent needs more than retrieval. It needs to know where a memory
                came from, which run produced it, which retrieval mode returned it, and whether
                the trace still matches the receipt.
              </p>
              <p className="mt-4 text-sm leading-relaxed text-zmuted">
                That is the ActiveGraph fit: events provide the causal substrate, and ZMem turns
                selected events into local, scoped, verifiable memory.
              </p>
            </div>
            <CodeBlock code={traceLine} title="compact trace line" />
          </div>
        </section>

        <section className="py-20">
          <div className="mx-auto max-w-[900px] px-6">
            <p className="text-eyebrow text-zlime">Verified boundary</p>
            <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
              A real pack, with an explicit prompt boundary.
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-zmuted">
              ActiveGraph 1.9 discovers and loads the ZMem pack, resolves both runtime behaviors,
              and persists a real object event into ZMem. The explicit pre-call wrapper adds memory
              before ActiveGraph hashes and records the prompt. The installed request behavior remains
              an audit hook for the immutable request instead of pretending to rewrite it afterward.
            </p>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              The compact runner also completed a 227-question acceptance pass: 908 events, eight
              batched commits, a roughly 1 MB event database, and zero per-question receipt bundles.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="/activegraph"
                className="rounded-full bg-zlime px-6 py-3 text-cta text-[#030303] transition-colors hover:bg-[#7BC45A]"
              >
                Open integration
              </a>
              <a
                href="/changelog"
                className="rounded-full border border-zline px-6 py-3 text-cta text-zink transition-colors hover:border-zlime hover:text-zlime"
              >
                Changelog
              </a>
            </div>
          </div>
        </section>
      </article>
    </main>
  );
}
