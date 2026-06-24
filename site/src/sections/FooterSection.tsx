import { Github, Twitter } from '@/components/Icons';

const footerColumns = [
  {
    heading: 'Product',
    links: [
      { label: 'Features', href: '/#memory-loop' },
      { label: 'Install', href: '/#install' },
      { label: 'Proof Matrix', href: '/proof' },
      { label: 'Agent Pack', href: '/#memory-loop' },
    ],
  },
  {
    heading: 'Developers',
    links: [
      { label: 'Documentation', href: '/docs' },
      { label: 'GitHub', href: 'https://github.com/zerkerlabs/zmem', external: true },
      { label: 'CLI Reference', href: null },
      { label: 'MCP Tools', href: null },
    ],
  },
  {
    heading: 'Company',
    links: ['About', 'Blog', 'Status'],
  },
];

export default function FooterSection() {
  return (
    <footer className="border-t border-zline bg-[#050505]">
      <div className="mx-auto max-w-[1120px] px-6 py-12 md:px-[clamp(20px,5vw,72px)]">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {/* Brand Column */}
          <div>
            <div className="flex items-center gap-2.5">
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="text-zlime">
                <path d="M9 1.5 16.5 9 9 16.5 1.5 9 9 1.5Z" fill="none" stroke="currentColor" strokeWidth="2" />
              </svg>
              <span className="font-heading text-xl font-bold text-zlime">ZMem</span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-zmuted">
              Local agent memory. Governed injection. Portable proof.
            </p>
            <div className="mt-4 flex items-center gap-4">
              <a
                href="https://github.com/zerkerlabs/zmem"
                target="_blank"
                rel="noopener noreferrer"
                className="text-zmuted transition-colors duration-200 hover:text-zlime"
                aria-label="GitHub"
              >
                <Github size={20} />
              </a>
              <span className="text-zmuted transition-colors duration-200 hover:text-zlime cursor-default">
                <Twitter size={20} />
              </span>
            </div>
          </div>

          {/* Link Columns */}
          {footerColumns.map((col) => (
            <div key={col.heading}>
              <h4 className="text-eyebrow text-zmuted mb-4">{col.heading}</h4>
              <ul className="flex flex-col gap-2.5">
                {col.links.map((link) => {
                  const label = typeof link === 'string' ? link : link.label;
                  const href = typeof link === 'string' ? null : link.href;
                  const external = typeof link === 'string' ? false : link.external;

                  if (href) {
                    return (
                      <li key={label}>
                        <a
                          href={href}
                          target={external ? '_blank' : undefined}
                          rel={external ? 'noopener noreferrer' : undefined}
                          className="text-sm text-zdim transition-colors duration-200 hover:text-zink"
                        >
                          {label}
                        </a>
                      </li>
                    );
                  }

                  return (
                    <li key={label}>
                      <span className="text-sm text-zdim cursor-default">{label}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-zline pt-6 sm:flex-row">
          <span className="text-caption text-zdim">&copy; 2026 Zerker Labs</span>
          <span className="text-caption text-zdim">Receipts are local by default; Treeship publish is optional.</span>
        </div>
      </div>
    </footer>
  );
}
