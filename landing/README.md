# Landing Page

Open directly:

```bash
open landing/index.html
```

Or serve locally:

```bash
python3 -m http.server 8765 --directory landing
```

Regenerate the public benchmark evidence page from a benchmark matrix:

```bash
zmem bench public-page .zerker/bench/synthetic-local --out landing/benchmarks.html
```

## QA Checklist

- Hero headline is visible above the fold.
- Animated memory graph renders.
- Proof panel is visible without scrolling too far.
- Benchmarks page opens and clearly labels provisional/local evidence.
- Mobile layout stacks cards cleanly.
- No text overlaps at 390px, 768px, 1440px.
- Install command is readable.
- Persona section speaks to builders, startups, and enterprise.
- Page does not rely on external assets or network.
