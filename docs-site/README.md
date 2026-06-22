# ZMem Docs Site

This is the Fumadocs-powered documentation home for ZMem.

The root `site/` app stays focused on the product story, install path, proof surface, and benchmark evidence. This app owns the long-form docs for installation, agents, memory lifecycle, receipts, handoff, benchmarks, provider governance, and launch proof.

## Local Development

```bash
npm install
npm run dev
```

Open `http://localhost:3000/docs`.

## Build

```bash
npm run build
```

## Deployment

Deploy this directory as a separate Vercel project or route it behind a docs subdomain/path. Use `docs-site` as the project root.

