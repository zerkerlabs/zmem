import Card from '@/components/Card';
import CodeBlock from '@/components/CodeBlock';

const docsRun = `cd docs
npm install
npm run dev

# open http://localhost:3000/docs`;

const guides = [
  'Install',
  'Agents',
  'Memory lifecycle',
  'Receipts',
  'Handoff',
  'Benchmarks',
  'Builders',
  'Proof model',
];

export default function DocsPage() {
  return (
    <main className="bg-zbg pt-28">
      <section className="border-b border-zline pb-16">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Documentation system</p>
          <h1
            className="mt-5 max-w-[860px] font-heading font-bold leading-[0.96] text-zink"
            style={{ fontSize: 'clamp(44px, 7vw, 82px)' }}
          >
            ZMem docs for users and builders.
          </h1>
          <p className="mt-6 max-w-[680px] text-[17px] leading-relaxed text-zmuted">
            Learn how to install ZMem, connect agent tools, operate memory across sessions,
            verify receipts, restore handoffs, and measure retrieval quality.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="https://docs.zmem.sh"
              className="rounded-full bg-zlime px-6 py-3 text-cta text-[#030303] transition-colors hover:bg-[#7BC45A]"
            >
              Open docs
            </a>
            <a
              href="https://github.com/zerkerlabs/zmem"
              className="rounded-full border border-zline px-6 py-3 text-cta text-zink transition-colors hover:border-zlime hover:text-zlime"
            >
              GitHub
            </a>
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.95fr_1.05fr]">
          <Card>
            <p className="text-eyebrow text-zmuted">Local docs</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              Run the docs locally.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              The public docs live at docs.zmem.sh and can also run from the repository
              when you want to preview changes.
            </p>
          </Card>
          <CodeBlock code={docsRun} title="fumadocs" />
        </div>
      </section>

      <section className="bg-zsurface py-16">
        <div className="mx-auto max-w-[1120px] px-6">
          <p className="text-eyebrow text-zlime">Guide tree</p>
          <div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
            {guides.map((guide) => (
              <div
                key={guide}
                className="rounded border border-zline bg-[#0A0A0A] px-4 py-4 text-sm font-semibold text-zink"
              >
                {guide}
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
