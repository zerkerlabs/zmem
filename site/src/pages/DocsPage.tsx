import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';

const docsBase = 'https://docs.zmem.sh/docs';

const docsRun = `cd docs
npm install
npm run dev

# open http://localhost:3000/docs`;

const quickStart = `# install and inspect
curl -fsSL https://zmem.sh/install.sh | bash
zmem status --summary-only

# connect an agent
zmem agent pack --summary-only
zmem ui

# prove what shaped an action
zmem why <action-id>`;

const primaryGuides = [
  {
    label: 'Start here',
    title: 'Install ZMem',
    href: `${docsBase}/install`,
    detail: 'Install locally, confirm the CLI, run the first status checks, and keep the setup reproducible.',
    command: 'zmem status --summary-only',
  },
  {
    label: 'Agent setup',
    title: 'Connect Codex, Claude Code, Cursor, Hermes, and MCP tools',
    href: `${docsBase}/agents`,
    detail: 'Give agents a simple memory API without making every chat invent its own continuity layer.',
    command: 'zmem agent pack --summary-only',
  },
  {
    label: 'Daily use',
    title: 'Review and operate memory',
    href: `${docsBase}/memory-lifecycle`,
    detail: 'Promote, reject, revoke, snapshot, and inspect the memories agents are allowed to reuse.',
    command: 'zmem ui',
  },
  {
    label: 'Proof',
    title: 'Verify receipts',
    href: `${docsBase}/receipts`,
    detail: 'See which memories were returned, which were withheld, and the receipt that anchors the set.',
    command: 'zmem why <action-id>',
  },
];

const operatorPaths = [
  {
    title: 'I want to use it with my agents',
    links: [
      { label: 'Install guide', href: `${docsBase}/install` },
      { label: 'Agent setup', href: `${docsBase}/agents` },
      { label: 'Builder API', href: `${docsBase}/builders` },
    ],
  },
  {
    title: 'I want to understand trust and provenance',
    links: [
      { label: 'Memory lifecycle', href: `${docsBase}/memory-lifecycle` },
      { label: 'Receipt model', href: `${docsBase}/receipts` },
      { label: 'Handoff and restore', href: `${docsBase}/handoff` },
    ],
  },
  {
    title: 'I want to evaluate retrieval quality',
    links: [
      { label: 'Benchmarks', href: `${docsBase}/benchmarks` },
      { label: 'ActiveGraph traces', href: `${docsBase}/activegraph` },
      { label: 'Proof page', href: '/proof' },
    ],
  },
];

const docsMap = [
  {
    group: 'Start',
    items: [
      { label: 'Docs home', href: docsBase },
      { label: 'Install', href: `${docsBase}/install` },
      { label: 'Agents', href: `${docsBase}/agents` },
    ],
  },
  {
    group: 'Operate',
    items: [
      { label: 'Builders', href: `${docsBase}/builders` },
      { label: 'Memory lifecycle', href: `${docsBase}/memory-lifecycle` },
      { label: 'Handoff', href: `${docsBase}/handoff` },
    ],
  },
  {
    group: 'Prove',
    items: [
      { label: 'Receipts', href: `${docsBase}/receipts` },
      { label: 'Benchmarks', href: `${docsBase}/benchmarks` },
      { label: 'Public proof', href: '/proof' },
    ],
  },
  {
    group: 'Extend',
    items: [
      { label: 'ActiveGraph', href: `${docsBase}/activegraph` },
      { label: 'Changelog', href: '/changelog' },
      { label: 'GitHub', href: 'https://github.com/zerkerlabs/zmem' },
    ],
  },
];

export default function DocsPage() {
  return (
    <main className="bg-zbg pt-28">
      <section className="border-b border-zline pb-16">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-8 px-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-end">
          <div>
            <p className="text-eyebrow text-zlime">Documentation</p>
            <h1
              className="mt-5 max-w-[820px] font-heading font-bold leading-[0.96] text-zink"
              style={{ fontSize: 'clamp(42px, 7vw, 82px)' }}
            >
              Get agents connected to governed memory.
            </h1>
            <p className="mt-6 max-w-[650px] text-[17px] leading-relaxed text-zmuted">
              Install ZMem, connect your agent runtime, review what memory is allowed back
              into context, and verify the receipt when it matters.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href={`${docsBase}/install`}
                className="rounded-full bg-zlime px-6 py-3 text-cta text-[#030303] transition-colors hover:bg-[#7BC45A]"
              >
                Install guide
              </a>
              <a
                href={`${docsBase}/agents`}
                className="rounded-full border border-zline px-6 py-3 text-cta text-zink transition-colors hover:border-zlime hover:text-zlime"
              >
                Agent setup
              </a>
              <a
                href={docsBase}
                className="rounded-full border border-zline px-6 py-3 text-cta text-zink transition-colors hover:border-zlime hover:text-zlime"
              >
                Docs home
              </a>
            </div>
          </div>
          <div className="rounded-lg border border-zline bg-zsurface p-5">
            <p className="text-eyebrow text-zmuted">Fast path</p>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {[
                ['1', 'Install locally'],
                ['2', 'Connect agent'],
                ['3', 'Review memory'],
                ['4', 'Verify receipt'],
              ].map(([step, label]) => (
                <div key={step} className="rounded-md border border-zline bg-[#0A0A0A] p-4">
                  <span className="font-mono text-xs text-zlime">{step}</span>
                  <p className="mt-2 text-sm font-semibold text-zink">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto max-w-[1120px] px-6">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-eyebrow text-zlime">Most used guides</p>
              <h2 className="mt-3 max-w-[680px] font-heading text-4xl font-semibold tracking-tight text-zink md:text-5xl">
                The docs you should not have to hunt for.
              </h2>
            </div>
            <a
              href={docsBase}
              className="w-fit rounded-full border border-zline px-5 py-2.5 text-sm font-semibold text-zink transition-colors hover:border-zlime hover:text-zlime"
            >
              Open full docs
            </a>
          </div>
          <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-2">
            {primaryGuides.map((guide) => (
              <Card key={guide.title} className="p-5">
                <p className="text-eyebrow text-zlime">{guide.label}</p>
                <h3 className="mt-3 font-heading text-2xl font-semibold tracking-tight text-zink">
                  {guide.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-zmuted">{guide.detail}</p>
                <div className="mt-5 rounded-md border border-zline bg-[#0A0A0A] px-4 py-3 font-mono text-[13px] text-[#D9E3D0]">
                  {guide.command}
                </div>
                <a href={guide.href} className="mt-5 inline-block text-sm font-semibold text-zlime">
                  Open guide
                </a>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-zline py-16">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.92fr_1.08fr]">
          <Card>
            <p className="text-eyebrow text-zmuted">Copy-paste path</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              Use the few commands that matter first.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              The full docs are there when you need depth. This page should get an agent
              connected, visible, and provable without three clicks of searching.
            </p>
          </Card>
          <CodeBlock code={quickStart} title="zmem quick start" highlightedLines={[0, 4, 8]} />
        </div>
      </section>

      <section className="bg-zsurface py-16">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Choose your path</p>
          <div className="mt-8 grid grid-cols-1 gap-5 lg:grid-cols-3">
            {operatorPaths.map((path) => (
              <Card key={path.title} className="p-5">
                <h2 className="font-heading text-2xl font-semibold tracking-tight text-zink">
                  {path.title}
                </h2>
                <div className="mt-5 flex flex-col gap-3">
                  {path.links.map((link) => (
                    <a
                      key={link.label}
                      href={link.href}
                      className="rounded-md border border-zline bg-[#0A0A0A] px-4 py-3 text-sm font-semibold text-zink transition-colors hover:border-zlime hover:text-zlime"
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.86fr_1.14fr]">
          <div>
            <p className="text-eyebrow text-zlime">Docs map</p>
            <h2 className="mt-3 font-heading text-4xl font-semibold tracking-tight text-zink">
              Direct routes to every core page.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              ZMem has product docs, proof docs, benchmark docs, and integration docs.
              They should all be one click from here.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {docsMap.map((section) => (
              <div key={section.group} className="rounded-lg border border-zline bg-zsurface p-5">
                <h3 className="font-heading text-xl font-semibold tracking-tight text-zink">
                  {section.group}
                </h3>
                <div className="mt-4 flex flex-col gap-2">
                  {section.items.map((item) => (
                    <a
                      key={item.label}
                      href={item.href}
                      className="text-sm text-zmuted transition-colors hover:text-zlime"
                    >
                      {item.label}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-zline py-16">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.95fr_1.05fr]">
          <Card>
            <p className="text-eyebrow text-zmuted">Local docs development</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              Preview the docs repo before publishing.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              The public docs live at docs.zmem.sh. The source docs can run locally
              from the repository when you want to check edits before deployment.
            </p>
          </Card>
          <CodeBlock code={docsRun} title="fumadocs" />
        </div>
      </section>
    </main>
  );
}
