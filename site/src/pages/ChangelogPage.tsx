import Card from '@/components/Card';

const updates = [
  {
    title: 'Compact receipt bundles',
    detail: 'V2 keeps the complete event log committed by its Merkle root while carrying only the supporting write-event witnesses needed for portable verification. Existing v1 bundles still verify.',
  },
  {
    title: 'v0.1.3 release checkpoint',
    detail: 'Agent capability boundaries, compact proof bundles, daily-use summaries, and the public site and docs hardening are packaged as the current alpha release.',
  },
  {
    title: 'Agent-first memory workflow',
    detail: 'Homepage, docs, and release copy now explain ZMem as local memory agents can use across runs, with review, scoped use, and receipts.',
  },
  {
    title: 'Trust ledger hardening',
    detail: 'Mutation, bundle, export, and restore receipts are more explicit about what changed and what can be verified locally.',
  },
  {
    title: 'Retrieval explanation improvements',
    detail: 'Receipts now expose more of the support-chain, stale/current, withheld, and budget-dropped reasoning behind agent context.',
  },
  {
    title: 'Workspace provenance',
    detail: 'Connected-agent, source, conflict, parent-action, and restore-continuity views make multi-agent memory easier to inspect.',
  },
  {
    title: 'Benchmark boundary',
    detail: 'LoCoMo and LongMemEval evidence exists, but public ranking claims wait for isolated reruns and official-method alignment.',
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
            What ZMem is shipping.
          </h1>
          <p className="mt-6 max-w-[700px] text-[17px] leading-relaxed text-zmuted">
            The current release is live. This page also tracks the next verified product
            improvements before they become a tagged release.
          </p>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-[1120px] px-6">
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {updates.map((update) => (
              <Card key={update.title}>
                <h2 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                  {update.title}
                </h2>
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
