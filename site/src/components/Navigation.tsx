import { useEffect, useState } from 'react';
import { useLenisInstance } from '@/hooks/useLenis';
import { Menu, X } from 'lucide-react';

type NavLink = {
  label: string;
  target: string;
  external?: boolean;
};

export default function Navigation() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const lenis = useLenisInstance();

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 100);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollTo = (id: string) => {
    setMobileOpen(false);
    if (id.startsWith('/')) {
      window.location.href = id;
      return;
    }
    if (window.location.pathname !== '/') {
      window.location.href = `/${id}`;
      return;
    }
    if (lenis) {
      lenis.scrollTo(id);
    } else {
      const target = document.querySelector(id);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
      } else {
        window.location.href = '/';
      }
    }
  };

  const navLinks: NavLink[] = [
    { label: 'Product', target: '#memory-loop' },
    { label: 'Proof', target: '/proof' },
    { label: 'Install', target: '#install' },
    { label: 'Docs', target: '/docs' },
  ];

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-5 py-5 transition-all duration-300 md:px-[clamp(20px,5vw,72px)] md:py-5 ${
          scrolled
            ? 'bg-[rgba(3,3,3,0.85)] backdrop-blur-xl'
            : 'bg-transparent'
        }`}
      >
        {/* Brand */}
        <button
          onClick={() => scrollTo('#hero')}
          className="flex items-center gap-2.5"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            aria-hidden="true"
            className="text-zlime"
            style={{ animation: 'pulse 3s ease-in-out infinite' }}
          >
            <path d="M9 1.5 16.5 9 9 16.5 1.5 9 9 1.5Z" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
          <span className="font-heading text-xl font-bold text-zlime">ZMem</span>
        </button>

        {/* Desktop Links */}
        <div className="hidden items-center gap-6 md:flex">
          {navLinks.map((link) =>
            link.external ? (
              <a
                key={link.label}
                href={link.target}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-zmuted transition-colors duration-200 hover:text-zink border-b border-transparent hover:border-zlime pb-0.5"
              >
                {link.label}
              </a>
            ) : (
              <button
                key={link.label}
                onClick={() => scrollTo(link.target)}
                className="text-sm text-zmuted transition-colors duration-200 hover:text-zink border-b border-transparent hover:border-zlime pb-0.5"
              >
                {link.label}
              </button>
            )
          )}
          <button
            onClick={() => scrollTo('#install')}
            className="rounded-full bg-zlime px-6 py-2.5 text-cta text-[#030303] transition-all duration-150 hover:bg-[#7BC45A] hover:scale-[1.02]"
          >
            Install
          </button>
        </div>

        {/* Mobile Hamburger */}
        <button
          className="text-zink md:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </nav>

      {/* Mobile Menu Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex flex-col items-center justify-center gap-8 bg-zbg md:hidden">
          {navLinks.map((link) =>
            link.external ? (
              <a
                key={link.label}
                href={link.target}
                target="_blank"
                rel="noopener noreferrer"
                className="font-heading text-2xl font-semibold text-zink"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </a>
            ) : (
              <button
                key={link.label}
                onClick={() => scrollTo(link.target)}
                className="font-heading text-2xl font-semibold text-zink"
              >
                {link.label}
              </button>
            )
          )}
          <button
            onClick={() => scrollTo('#install')}
            className="mt-4 rounded-full bg-zlime px-8 py-3 text-cta text-[#030303]"
          >
            Install ZMem
          </button>
        </div>
      )}
    </>
  );
}
