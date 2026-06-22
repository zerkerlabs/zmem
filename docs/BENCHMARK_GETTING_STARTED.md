# Benchmark Getting Started

Use this path to produce ZMem benchmark artifacts without making unsupported public claims.

## 1. Run The Local Synthetic Matrix

This is the fastest proof that the benchmark harness, retrieval modes, receipts, hashes, and dashboards work.

```bash
zmem bench matrix synthetic \
  --out .zerker/bench \
  --seed 0 \
  --run-id synthetic-local
```

This writes:

```text
.zerker/bench/synthetic-local/
  benchmark-matrix.json
  benchmark-comparison.json
  matrix-report.md
  fts/
  fts-multihop/
  pseudo-embedding/
  pseudo-embedding-rerank/
```

Then generate the two HTML surfaces:

```bash
zmem bench dashboard .zerker/bench/synthetic-local
zmem bench public-page .zerker/bench/synthetic-local
```

Use `benchmark-dashboard.html` for engineering tracking. Use `public-benchmarks.html` for a public-facing evidence page.

## 2. Verify The Evidence

Verify individual runs:

```bash
zmem bench verify .zerker/bench/synthetic-local/fts/benchmark-result.json
zmem bench verify .zerker/bench/synthetic-local/fts-multihop/benchmark-result.json
```

The matrix already records comparison and matrix hashes. The public page should show the same hashes.

## 3. Run Local LongMemEval/LoCoMo-Style Fixtures

Adapt local dataset files to the contract in `docs/BENCHMARK_FIXTURE_CONTRACT.md`, then run:

```bash
zmem bench matrix longmemeval \
  --dataset /path/to/local-longmemeval.jsonl \
  --split dev \
  --out .zerker/bench \
  --seed 0 \
  --run-id longmemeval-dev-local

zmem bench dashboard .zerker/bench/longmemeval-dev-local
zmem bench public-page .zerker/bench/longmemeval-dev-local
```

For LoCoMo-style data:

```bash
zmem bench matrix locomo \
  --dataset /path/to/local-locomo.jsonl \
  --split dev \
  --out .zerker/bench \
  --seed 0 \
  --run-id locomo-dev-local

zmem bench dashboard .zerker/bench/locomo-dev-local
zmem bench public-page .zerker/bench/locomo-dev-local
```

## 4. Public Claim Rules

Allowed public language before official benchmark submissions:

- "ZMem publishes proof-backed local benchmark evidence."
- "This matrix is reproducible from the attached artifact hashes and receipts."
- "This local scaffold tracks retrieval accuracy, latency, tokens, and proof verification."

Do not claim:

- official LongMemEval or LoCoMo ranking,
- superiority over Mem0, Zep, Letta, or another memory product,
- canonical leaderboard score,
- production frontier ranking.

Those claims require official dataset rules, pinned versions, primary-source methodology, and a reproducible public artifact bundle.

## 5. What To Track

Track these for every run:

- accuracy and category accuracy,
- recall/precision evidence when ground truth support exists,
- p50/p95/p99 retrieval latency,
- total tokens and injected context tokens,
- retrieved, injected, withheld, and budget-dropped memory counts,
- verification status,
- matrix hash,
- comparison hash,
- optional Treeship proof URL once public proof publishing is enabled.
