import { LenisProvider } from '@/hooks/useLenis';
import Navigation from '@/components/Navigation';
import HeroSection from '@/sections/HeroSection';
import TrustBarSection from '@/sections/TrustBarSection';
import MemoryLoopSection from '@/sections/MemoryLoopSection';
import AgentContinuitySection from '@/sections/AgentContinuitySection';
import TrustArchitectureSection from '@/sections/TrustArchitectureSection';
import InstallSection from '@/sections/InstallSection';
import ProofOfWorkSection from '@/sections/ProofOfWorkSection';
import FooterSection from '@/sections/FooterSection';
import ProofPage from '@/pages/ProofPage';
import DocsPage from '@/pages/DocsPage';
import ActiveGraphPage from '@/pages/ActiveGraphPage';
import ActiveGraphBlogPage from '@/pages/ActiveGraphBlogPage';
import ChangelogPage from '@/pages/ChangelogPage';

function HomePage() {
  return (
    <main>
      <HeroSection />
      <TrustBarSection />
      <MemoryLoopSection />
      <AgentContinuitySection />
      <TrustArchitectureSection />
      <InstallSection />
      <ProofOfWorkSection />
    </main>
  );
}

function App() {
  const path = window.location.pathname;
  const isProofPage = path === '/proof';
  const isDocsPage = path === '/docs';
  const isActiveGraphPage = path === '/activegraph';
  const isActiveGraphBlogPage = path === '/blog/activegraph-memory';
  const isChangelogPage = path === '/changelog';

  return (
    <LenisProvider>
      <Navigation />
      {isProofPage ? (
        <ProofPage />
      ) : isDocsPage ? (
        <DocsPage />
      ) : isActiveGraphPage ? (
        <ActiveGraphPage />
      ) : isActiveGraphBlogPage ? (
        <ActiveGraphBlogPage />
      ) : isChangelogPage ? (
        <ChangelogPage />
      ) : (
        <HomePage />
      )}
      <FooterSection />
    </LenisProvider>
  );
}

export default App;
