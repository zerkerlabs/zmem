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
  const isProofPage = window.location.pathname === '/proof';
  const isDocsPage = window.location.pathname === '/docs';

  return (
    <LenisProvider>
      <Navigation />
      {isProofPage ? <ProofPage /> : isDocsPage ? <DocsPage /> : <HomePage />}
      <FooterSection />
    </LenisProvider>
  );
}

export default App;
