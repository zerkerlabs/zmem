# Benchmark Scoring Workflow

This page is the operator workflow for turning local LongMemEval and LoCoMo files into ZMem benchmark evidence. It complements `docs/BENCHMARK_GETTING_STARTED.md` and `docs/BENCHMARK_FIXTURE_CONTRACT.md`.

## Status

The current benchmark path is useful for product development and reproducible local evidence. It is not yet an official leaderboard submission path.

- Local synthetic, LongMemEval-style, and LoCoMo-style runs are receipt-backed and locally verifiable.
- Official dataset conversion scripts live under `scripts/bench/`.
- Downloaded datasets stay outside git, usually under `data/`.
- LLM answer generation and external LongMemEval judging are explicit opt-in paths.
- Public benchmark claims still require pinned dataset versions, reproducible commands, result bundles, and a verified scoring method.

## 1. Convert Official Files

LongMemEval:

```bash
python3 scripts/bench/longmemeval_to_zmem.py \
  --in data/longmemeval/longmemeval_oracle.json \
  --out data/longmemeval/longmemeval_oracle_zmem.json
```

LoCoMo:

```bash
python3 scripts/bench/locomo_to_zmem.py \
  --in data/locomo-repo/data/locomo10.json \
  --out data/locomo/locomo_official_zmem.json
```

The converters write ZMem-shaped JSON records. They do not download datasets and they do not change scoring status from local/provisional to official.

## 2. Run Local Provisional Evidence

Use this when you want a no-network retrieval/proof check:

```bash
zmem bench matrix longmemeval \
  --dataset data/longmemeval/longmemeval_oracle_zmem.json \
  --out .zerker/bench \
  --run-id longmemeval-local-v1 \
  --mode zmem-retrieval \
  --seed 42

zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench \
  --run-id locomo-local-v1 \
  --mode zmem-retrieval \
  --seed 42
```

Then verify and render:

```bash
zmem bench verify .zerker/bench/longmemeval-local-v1/pseudo-embedding-rerank/benchmark-result.json
zmem bench dashboard .zerker/bench/longmemeval-local-v1
zmem bench public-page .zerker/bench/longmemeval-local-v1
```

The `zmem-retrieval` mode is a stable alias for the strongest current local retrieval mode in the harness. The stored result still records the concrete mode.

## 3. Inspect Evidence Cheaply

Use this when you need a fast audit of an existing matrix without replaying every mode:

```bash
python3 scripts/bench/summarize_evidence.py .zerker/bench/longmemeval-local-v1
```

The summary reads `benchmark-matrix.json` and `benchmark-comparison.json`, recomputes their stored content hashes, reports mode proof pointers, and keeps `public_benchmark_claim` set to `false`. It is a cheap health check for persisted evidence, not a substitute for rerunning or officially scoring the benchmark.

## 4. Run Optional LLM Scoring

Only run this when you intentionally want network/API use:

```bash
export OPENAI_API_KEY=...
bash scripts/bench/run_scored_longmemeval.sh
bash scripts/bench/run_scored_locomo.sh
```

Those scripts:

- run `zmem bench matrix ... --answerer llm --trace`,
- write trace artifacts under `.zerker/bench/<run-id>/`,
- use `scripts/bench/judge_longmemeval.py` for the LongMemEval judge path,
- use `scripts/bench/score_locomo.py` for local LoCoMo token-F1 / exact-match scoring.

If `OPENAI_API_KEY` is missing, the LLM answerer fails closed.

## 5. Keep The Evidence

For every benchmark run that might become public evidence, keep:

- source dataset path and dataset hash,
- converted dataset path and conversion command,
- `benchmark-matrix.json`,
- `benchmark-comparison.json`,
- every mode's `benchmark-result.json`,
- `matrix-report.md`,
- `benchmark-dashboard.html`,
- `public-benchmarks.html`,
- optional `trace.jsonl` and `summary.json`,
- optional Treeship artifact URL once publish support is enabled.

Do not commit downloaded dataset payloads unless the dataset license and repo policy explicitly allow it.

## 6. Claim Boundary

Allowed now:

- "ZMem can produce proof-backed local benchmark evidence."
- "This run verifies from local artifacts and receipt bundles."
- "The benchmark harness tracks accuracy, recall, latency, tokens, abstention, and proof integrity."

Not allowed yet:

- "ZMem ranks X on LongMemEval."
- "ZMem beats Mem0, Zep, Letta, or another system on LoCoMo."
- "This is an official benchmark submission."
- "The LLM judged trace is a canonical score."

Move a claim from internal to public only after the dataset source, conversion command, scoring command, artifact hashes, and receipt bundle are all pinned and reproducible.
