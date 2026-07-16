import Card from '@/components/Card';

const updates = [
  {
    title: 'Bounded transcript-neighbor support',
    detail: 'An exact-event-head, same-speaker, earlier-turn bridge recovered one multi-hop LoCoMo answer. It changed one retrieval context across 1,986 questions and introduced zero regressions.',
  },
  {
    title: 'A clearer agent-memory promise',
    detail: 'The homepage now leads with “Agent memory you can trust” and immediately explains the persistent local memory, review, revocation, and verification controls behind that promise.',
  },
  {
    title: 'Bounded completion support',
    detail: 'One narrow subject-and-object anchored completion bridge gained one LoCoMo answer with zero regressions on both the stable cohort and the full 1,986-question run.',
  },
  {
    title: 'ActiveGraph pre-call recall verified',
    detail: 'A host LLM behavior can now add scoped ZMem memory before ActiveGraph hashes and records the prompt. Runtime verification proves the recorded and provider-bound prompts match.',
  },
  {
    title: 'BEAM 500K scale evidence',
    detail: 'The first isolated 500K conversation run covered 796 messages, 247,175 observed tokens, 20 questions, and 83 of 83 source references. It remains a local evidence diagnostic, not an official answer score.',
  },
  {
    title: 'v0.1.4 retrieval and scale release',
    detail: 'Bounded regular-inflection matching, a BEAM scale runner, and a real ActiveGraph pack and batched trace path now ship together.',
  },
  {
    title: 'Zero-regression morphology gate',
    detail: 'The stable 227-question cohort gained two answers and lost none. Full local runs then gained five LoCoMo answers and three LongMemEval answers with zero regressions.',
  },
  {
    title: 'ActiveGraph pack verified',
    detail: 'ActiveGraph 1.9 discovers and loads ZMem, persists real events, and records compact causal benchmark traces. A 227-question run produced 908 events in eight batched commits with zero receipt bundles.',
  },
  {
    title: 'BEAM scale harness',
    detail: 'ZMem now reads the official BEAM directory layout from 100K through 10M, resolves nested source ids, and commits compact per-question evidence. The first 100K smoke covered all ten categories.',
  },
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
    detail: 'Verified local LoCoMo and LongMemEval matrices now cover FTS, always-on multi-hop, pseudo modes, and adaptive routing. They are reproducible product evidence, not official leaderboard rankings.',
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
            Adaptive routing leads the local LoCoMo comparison.
          </h2>
          <p className="mt-5 text-sm leading-relaxed text-zmuted">
            In ZMem's latest verified local provisional run, adaptive routing answered 1,220 of
            1,986 questions correctly, or 0.6143 accuracy. Bounded transcript-neighbor support added
            one answer with no regressions against the completion-support checkpoint. LongMemEval
            held at 0.772 with no retrieval changes.
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
