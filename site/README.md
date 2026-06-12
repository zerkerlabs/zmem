# ZMem Site

Production landing site for ZMem at `zmem.sh`.

## Local preview

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 8778
```

## Build

```bash
npm run build
```

The static output is written to `dist/`.

## Pages

- `/` is the landing page.
- `/proof` is the product proof/status page: feature matrix, launch gates, benchmark roadmap, and Treeship proof flow.

## Deploy

Recommended Vercel settings:

- Root directory: `site`
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`

Connect `zmem.sh` to the deployed project after DNS is ready.
