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
  'Provider governance',
  'Launch proof',
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
            The real docs home now lives in Fumadocs.
          </h1>
          <p className="mt-6 max-w-[680px] text-[17px] leading-relaxed text-zmuted">
            This Vite page stays as the product bridge. The full guide tree is a separate
            Next/Fumadocs app in <span className="font-mono text-zink">docs/</span>.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="https://github.com/zerkerlabs/zmem"
              className="rounded-full bg-zlime px-6 py-3 text-cta text-[#030303] transition-colors hover:bg-[#7BC45A]"
            >
              GitHub
            </a>
            <a
              href="https://github.com/zerkerlabs/zmem/blob/main/QUICKSTART.md"
              className="rounded-full border border-zline px-6 py-3 text-cta text-zink transition-colors hover:border-zlime hover:text-zlime"
            >
              Quickstart
            </a>
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto grid max-w-[1120px] grid-cols-1 gap-6 px-6 lg:grid-cols-[0.95fr_1.05fr]">
          <Card>
            <p className="text-eyebrow text-zmuted">Local docs</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-zink">
              Run the docs app beside the product site.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-zmuted">
              Deploy <span className="font-mono text-zink">docs/</span> as the docs
              project behind docs.zmem.sh.
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
