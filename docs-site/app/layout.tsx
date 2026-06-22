import type { Metadata } from 'next';
import { RootProvider } from 'fumadocs-ui/provider/next';
import 'fumadocs-ui/style.css';
import './global.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://zmem.sh'),
  title: {
    default: 'ZMem Docs',
    template: '%s | ZMem Docs',
  },
  description:
    'Documentation for ZMem, local-first memory for AI agents with receipts, handoff, benchmarks, and proof.',
  openGraph: {
    title: 'ZMem Docs',
    description:
      'Install, operate, benchmark, and verify agent memory with ZMem.',
    url: 'https://zmem.sh/docs',
    siteName: 'ZMem',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body>
        <RootProvider theme={{ defaultTheme: 'dark', forcedTheme: 'dark' }}>
          {children}
        </RootProvider>
      </body>
    </html>
  );
}
