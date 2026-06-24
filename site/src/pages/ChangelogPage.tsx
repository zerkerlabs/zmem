import Card from '@/components/Card';
import StatusBadge from '@/components/StatusBadge';

const updates = [
  {
    title: 'ActiveGraph source pack',
    status: 'built' as const,
    detail: 'Pack manifest, behavior handlers, and entry point for cross-run ActiveGraph memory.',
  },
  {
    title: 'Compact benchmark runner',
    status: 'built' as const,
    detail: 'Event-sourced LoCoMo runner writes trace.jsonl and scored_receipt.json, avoiding per-question receipt bundles.',
  },
  {
    title: 'Official LoCoMo FTS baseline',
    status: 'ready' as const,
    detail: '1,986-question rule-scored run recorded at F1 0.3752 and EM 0.3721 with a public-claim receipt.',
  },
  {
    title: 'Retrieval fork-and-diff queue',
    status: 'alpha' as const,
    detail: 'fts-multihop and pseudo-embedding-rerank are queued to test depth and reranking against the same dataset.',
  },
  {
    title: 'Causal memory receipts',
    status: 'built' as const,
    detail: 'Memory writes can carry caused_by_event so agent memory points back to the event that produced it.',
  },
  {
    title: 'ActiveGraph install smoke',
    status: 'pending' as const,
    detail: 'The source integration is present; real pack-loader smoke is still pending in a networked environment.',
  },
];

export default function ChangelogPage() {
  return (
    <main className="bg-zbg pt-28">
      <section className="border-b border-zline pb-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Changelog</p>
          <h1
            className="mt-5 max-w-[900px] font-heading font-bold leading-[0.95] text-zink"
            style={{ fontSize: 'clamp(44px, 7vw, 92px)' }}
          >
            What changed in the frontier build.
          </h1>
          <p className="mt-6 max-w-[700px] text-[17px] leading-relaxed text-zmuted">
            ZMem now has a clearer benchmark story, an ActiveGraph integration path,
            and public-facing documentation for the next retrieval comparisons.
          </p>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {updates.map((update) => (
              <Card key={update.title}>
                <div className="flex items-start justify-between gap-4">
                  <h2 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                    {update.title}
                  </h2>
                  <StatusBadge status={update.status} />
                </div>
                <p className="mt-4 text-sm leading-relaxed text-zmuted">{update.detail}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-zsurface py-20">
        <div className="mx-auto max-w-[900px] px-6">
          <p className="text-eyebrow text-zlime">Current benchmark fact</p>
          <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
            FTS baseline is useful, but it exposed the next problem.
          </h2>
          <p className="mt-5 text-sm leading-relaxed text-zmuted">
            The official LoCoMo FTS run scored strongest on single-hop and temporal queries,
            while multi-hop, open-domain, and adversarial abstention stayed weak. That is why
            the next runs focus on fts-multihop, pseudo embedding rerank, LongMemEval-S, and BEAM.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="/activegraph"
              className="rounded-full bg-zlime px-6 py-3 text-cta text-[#030303] transition-colors hover:bg-[#7BC45A]"
            >
              ActiveGraph docs
            </a>
            <a
              href="/proof"
              className="rounded-full border border-zline px-6 py-3 text-cta text-zink transition-colors hover:border-zlime hover:text-zlime"
            >
              Proof page
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
