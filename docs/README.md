# ZMem Docs Site

This is the Fumadocs-powered documentation home for ZMem.

The root `site/` app stays focused on the product story, install path, proof surface, and benchmark evidence. This app owns the public long-form docs for installation, agents, builders, memory lifecycle, receipts, handoff, and benchmarks.

Benchmark operators should start with `BENCHMARK_GETTING_STARTED.md`, then use `BENCHMARK_SCORING_WORKFLOW.md` for official dataset conversion and optional scored runs.

Release and automation operators should keep `ZMEM_PROGRESS_TRACKER.md` open. It is the compact lane-by-lane board for what has shipped, what remains, and which automations can pause after acceptance.

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

Deploy this directory as the `zmem-docs` Vercel project root and serve it behind `docs.zmem.sh`.
