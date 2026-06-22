import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <>
          <span className="zmem-mark" aria-hidden="true" />
          ZMem
        </>
      ),
    },
    githubUrl: 'https://github.com/zerkerlabs/zmem',
    links: [
      {
        text: 'Product',
        url: 'https://zmem.sh',
      },
      {
        text: 'Benchmarks',
        url: '/docs/benchmarks',
      },
      {
        text: 'GitHub',
        url: 'https://github.com/zerkerlabs/zmem',
        external: true,
      },
    ],
  };
}
