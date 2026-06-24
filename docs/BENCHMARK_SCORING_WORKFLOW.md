# Benchmark Scoring Workflow

This page is the operator workflow for turning local LongMemEval and LoCoMo files into ZMem benchmark evidence. It complements `docs/BENCHMARK_GETTING_STARTED.md` and `docs/BENCHMARK_FIXTURE_CONTRACT.md`.

## Status

The current benchmark path is useful for product development and reproducible local evidence. It is not yet an official leaderboard submission path.

- Local synthetic, LongMemEval-style, and LoCoMo-style runs are receipt-backed and locally verifiable.
- Official dataset conversion scripts live under `scripts/bench/`.
- Downloaded datasets stay outside git, usually under `data/`.
- LLM answer generation and external LongMemEval judging are explicit opt-in paths.
- Public benchmark claims still require pinned dataset versions, reproducible commands, result bundles, and a verified scoring method.

Current official LoCoMo local baseline:

- Run directory: `.zerker/bench/locomo-official-v1/fts/`.
- Scored receipt: `scored_receipt.json`.
- Result: F1 `0.3752394031509457`, EM `0.37210473313192344`, 1,986 questions, retrieval mode `fts`, eval scope `per-conversation`.
- Trace SHA: `67a005bf87b4bafcd2d7ce1cf8bfff97d7f430788afd0472511f738594971d0c`.
- Claim boundary: `scored_receipt.json` carries the public rule-based token-F1/EM claim with no LLM judge; `receipt.json` remains a broader provisional harness receipt.

Next comparison queue:

- Run LoCoMo `fts-multihop` next with `bench matrix --mode`; it directly tests the largest weakness from the FTS baseline.
- Then run `pseudo-embedding`, `pseudo-embedding-rerank`, and `zmem-retrieval` under the same `locomo-official-v1` matrix run id.
- Run LongMemEval-S after the first LoCoMo mode deltas. It directly tests abstention and token efficiency, which are the current gaps surfaced by LoCoMo adversarial scoring.
- Add BEAM as the scale benchmark for 100K -> 10M token contexts. Treat it as a planned runner until dataset source, command, hashes, and receipt bundle are pinned.
- Read multi-hop, temporal, open-domain, and adversarial deltas from the existing category summaries and dashboard first; if full runs are too expensive, add category filtering before more category-only sweeps.
- Add a deterministic answerer abstention threshold for `retrieved_count == 0` or low-confidence retrieval, then verify on LoCoMo adversarial and LongMemEval-S.

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
zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench \
  --run-id locomo-official-v1 \
  --mode fts-multihop \
  --seed 42

zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench \
  --run-id locomo-official-v1 \
  --mode pseudo-embedding \
  --seed 42

zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench \
  --run-id locomo-official-v1 \
  --mode pseudo-embedding-rerank \
  --seed 42

zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench \
  --run-id locomo-official-v1 \
  --mode zmem-retrieval \
  --seed 42
```

Then render the comparison:

```bash
zmem bench report .zerker/bench/locomo-official-v1 --summary-only
zmem bench dashboard .zerker/bench/locomo-official-v1
zmem bench public-page .zerker/bench/locomo-official-v1
zmem bench verify .zerker/bench/locomo-official-v1/benchmark-matrix.json --summary-only
```

For LongMemEval:

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

For compact ActiveGraph traces, smoke first:

```bash
zmem-bench-locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench/activegraph-locomo-smoke \
  --run-id activegraph-smoke-fts-multihop \
  --retrieval-mode fts-multihop \
  --split default \
  --limit 5
```

Use ActiveGraph for long storage-safe traces after the matrix identifies which modes are worth preserving. It writes compact `trace.jsonl` and `scored_receipt.json` instead of per-question receipt bundles.

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
