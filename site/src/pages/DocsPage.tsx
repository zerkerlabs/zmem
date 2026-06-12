import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';

const useCases = [
  {
    title: 'Continue Agent Work Across Sessions',
    job: 'Give a new agent the project memory it needs without dumping a giant chat transcript.',
    steps: ['Install ZMem', 'Run or connect the agent through MCP', 'Ask the agent to request approved memory before acting'],
    command: 'zmem agent install codex\nzmem status --summary-only',
  },
  {
    title: 'Review Memory Before It Becomes Trusted',
    job: 'Let agents propose useful facts while keeping humans in control of what can influence future work.',
    steps: ['Queue proposed memories', 'Promote trusted ones', 'Reject or revoke stale/unsafe ones'],
    command: 'zmem queue\nzmem promote <memory-id>\nzmem revoke <memory-id>',
  },
  {
    title: 'Explain Why An Agent Used Memory',
    job: 'Answer “what did the agent know, what did it ignore, and why was that allowed?”',
    steps: ['Run a memory-influenced action', 'Inspect the action receipt', 'Verify the local proof root'],
    command: 'zmem why <action-id>\nzmem verify <action-id>',
  },
  {
    title: 'Move Memory Between Agents And Machines',
    job: 'Package state, receipts, policy, and setup instructions so another agent can resume safely.',
    steps: ['Create a handoff', 'Move the handoff directory', 'Restore into a target workspace'],
    command: 'zmem handoff --summary-only\nzmem restore --handoff-dir .zerker/handoff',
  },
  {
    title: 'Benchmark Memory Quality With Receipts',
    job: 'Measure retrieval behavior while keeping proof of what memory influenced each answer.',
    steps: ['Run a local matrix', 'Generate the report/dashboard', 'Verify the artifacts from disk'],
    command: 'zmem bench matrix synthetic --out .zerker/bench --seed 0\nzmem bench report .zerker/bench/<run-id> --summary-only',
  },
  {
    title: 'Publish Proof When Trust Matters',
    job: 'Turn local memory receipts into shareable proof without making every user understand the proof stack.',
    steps: ['Generate a proof bundle', 'Publish through Treeship when needed', 'Share the verification URL'],
    command: 'zmem treeship publish <action-id>',
  },
];

const docLinks = [
  { label: 'GitHub repo', href: 'https://github.com/zerkerlabs/zmem' },
  { label: 'Quickstart', href: 'https://github.com/zerkerlabs/zmem/blob/main/QUICKSTART.md' },
  { label: 'Benchmark guide', href: 'https://github.com/zerkerlabs/zmem/blob/main/docs/BENCHMARK_GETTING_STARTED.md' },
  { label: 'Fixture contract', href: 'https://github.com/zerkerlabs/zmem/blob/main/docs/BENCHMARK_FIXTURE_CONTRACT.md' },
];

const installCode = `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
cd "\${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
zmem status --summary-only`;

export default function DocsPage() {
  return (
    <main className="bg-zbg pt-28">
      <section className="border-b border-zline pb-16">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">ZMem docs</p>
          <h1
            className="mt-5 max-w-[900px] font-heading font-bold leading-[0.96] text-zink"
            style={{ fontSize: 'clamp(44px, 7vw, 88px)' }}
          >
            Use cases, jobs to be done, and the commands that prove them.
          </h1>
          <p className="mt-6 max-w-[700px] text-[17px] leading-relaxed text-zmuted">
            ZMem is local-first memory for agents with policy gates, receipts, handoff, and proof.
            These are the practical workflows the product should make obvious on day one.
          </p>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.95fr_1.05fr]">
          <Card>
            <p className="text-eyebrow text-zmuted">Start here</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              Install, inspect, then connect an agent.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              The first successful setup should end with a status screen: workspace ready,
              memory proof ready, agent handoff ready, and clear launch-proof state.
            </p>
          </Card>
          <CodeBlock code={installCode} title="first run" />
        </div>
      </section>

      <section className="bg-zsurface py-16">
        <div className="mx-auto max-w-[1120px] px-6">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-eyebrow text-zlime">Jobs to be done</p>
              <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
                What users should accomplish with ZMem.
              </h2>
            </div>
            <p className="max-w-[430px] text-sm leading-relaxed text-zmuted">
              This is the content backbone for a future Fumadocs site: each job gets a guide,
              a command path, and a proof expectation.
            </p>
          </div>

          <div className="mt-10 grid grid-cols-1 gap-5 lg:grid-cols-2">
            {useCases.map((useCase) => (
              <Card key={useCase.title} className="p-6">
                <h3 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                  {useCase.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">{useCase.job}</p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {useCase.steps.map((step) => (
                    <span
                      key={step}
                      className="rounded-full border border-zline px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-zmuted"
                    >
                      {step}
                    </span>
                  ))}
                </div>
                <pre className="mt-5 overflow-x-auto rounded bg-[#0A0A0A] p-4 font-mono text-xs leading-relaxed text-[#D9E3D0]">
                  {useCase.command}
                </pre>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Documentation system</p>
          <h2 className="mt-3 max-w-[760px] font-heading text-4xl font-semibold tracking-tight text-zink">
            The current page is a bridge. Fumadocs should become the real docs home.
          </h2>
          <p className="mt-5 max-w-[760px] text-sm leading-relaxed text-zmuted">
            Keep this Vite site focused on product story, install, proof, and benchmark evidence.
            Put full docs in a Fumadocs-powered section with guides for install, agents, memory lifecycle,
            receipts, handoff, benchmarks, provider governance, and launch proof.
          </p>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {docLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded border border-zline bg-zsurface p-5 text-sm font-semibold text-zink transition-colors hover:border-zlime hover:text-zlime"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
