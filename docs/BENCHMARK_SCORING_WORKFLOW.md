# Benchmark Scoring Workflow

This page is the operator workflow for turning local LongMemEval and LoCoMo files into ZMem benchmark evidence. It complements `docs/BENCHMARK_GETTING_STARTED.md` and `docs/BENCHMARK_FIXTURE_CONTRACT.md`.

## Status

The current benchmark path is useful for product development and reproducible local evidence. It is not yet an official leaderboard submission path.

- Local synthetic, LongMemEval-style, and LoCoMo-style runs are receipt-backed and locally verifiable.
- Official dataset conversion scripts live under `scripts/bench/`.
- Downloaded datasets stay outside git, usually under `data/`.
- LLM answer generation and external LongMemEval judging are explicit opt-in paths.
- Public benchmark claims still require pinned dataset versions, reproducible commands, result bundles, and a verified scoring method.

Current verified local evidence:

- LoCoMo four-mode matrix: `1,986` questions, multihop accuracy `0.6067`, other modes `0.5967`, matrix hash `9f8b77ca...`, comparison hash `18cdca15...`.
- LongMemEval four-mode matrix: `500` questions, multihop accuracy `0.780`, other modes `0.740`, matrix hash `e5dd8b06...`, comparison hash `a69090df...`.
- The bounded v0.1.4 morphology follow-up passed the stable cohort at `158/227` versus `156/227`, with two gains and zero losses. Full adaptive LoCoMo then reached `0.6133` with five gains and zero losses against the deterministic adaptive checkpoint; LongMemEval reached `0.772` with three gains and zero losses.
- The bounded completion-support follow-up reached `159/227` and full adaptive LoCoMo `1,219/1,986` (`0.6138`) with one additional gain and zero losses. LongMemEval remained `386/500`.
- The bounded transcript-neighbor follow-up reached `160/227` and full adaptive LoCoMo `1,220/1,986` (`0.6143`) with one additional multi-hop gain, zero losses, and exactly one changed retrieval context. LongMemEval remained retrieval-identical at `386/500`.
- The official BEAM 100K adapter smoke covered `188` messages, `63,411` observed whitespace tokens, `20` questions across all ten categories, and `53/53` resolved source references. It is scale/evidence instrumentation, not the official model-judged BEAM score.
- The isolated official-layout BEAM 500K conversation covered `796` messages, `247,175` observed whitespace tokens, `20` questions, and `83/83` resolved source references. Its `0.30` local evidence recall remains diagnostic rather than an official score.
- The ActiveGraph 227-question acceptance run wrote `908` replayable events in eight batched commits, a roughly `1 MB` event database, and zero per-question receipt bundles.
- Both matrices and comparisons verify locally. They use the provisional local retrieval-recall scorer and are not leaderboard submissions.
- The historical LoCoMo rule-based token-F1/EM artifact remains `0.3752394032` F1 and `0.3721047331` EM over `1,986` questions with trace SHA `67a005bf...`; do not compare it numerically with the current accuracy matrices.

Next comparison queue:

- Use the landed transcript-neighbor checkpoint as the baseline, then select another bounded multi-hop/open-domain retrieval improvement from the remaining adaptive stable misses under the same zero-regression gate.
- Expand BEAM from the verified 100K and 500K evidence into isolated 1M and 10M runs before making any scale-quality claim.
- Use the `114` adaptive LongMemEval misses and low LoCoMo multi-hop/open-domain scores to select the next retrieval-quality slice.

## 1. Convert Official Files

LongMemEval:

```bash
python3 scripts/bench/longmemeval_to_zmem.py \
  --in /path/to/longmemeval_oracle.json \
  --out data/longmemeval/longmemeval_oracle_zmem.json
```

LoCoMo:

```bash
python3 scripts/bench/locomo_to_zmem.py \
  --in /path/to/locomo10.json \
  --out data/locomo/locomo_official_zmem.json
```

The converters write ZMem-shaped JSON records. They do not download datasets and they do not change scoring status from local/provisional to official.

## 2. Run Local Provisional Evidence

Use this when you want a no-network retrieval/proof check. Prefer one unique sequential matrix so no other process can archive an active mode directory:

```bash
RUN_ID="locomo-matrix-$(date -u +%Y%m%dT%H%M%SZ)"

zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench/runs \
  --run-id "$RUN_ID" \
  --seed 42 \
  --trace \
  --compact-artifacts \
  --summary-only
```

`zmem-retrieval` remains a compatibility alias for `pseudo-embedding-rerank`; do not run both as separate full measurements. Use explicit `--mode fts-adaptive` to measure store auto-routing.

For LoCoMo, compact mode processes one conversation store at a time and omits the run database. Use a non-compact run only when you specifically need the retained SQLite state, final snapshot, and per-question receipt bundles.

A matrix restricted with `--mode` carries one verified result and zero comparison deltas; it does not duplicate that result as a synthetic baseline.

Then render the comparison:

```bash
zmem bench report ".zerker/bench/runs/$RUN_ID" --summary-only
zmem bench dashboard ".zerker/bench/runs/$RUN_ID"
zmem bench public-page ".zerker/bench/runs/$RUN_ID"
zmem bench verify ".zerker/bench/runs/$RUN_ID/benchmark-matrix.json" --summary-only
```

For LongMemEval:

```bash
zmem bench matrix longmemeval \
  --dataset data/longmemeval/longmemeval_oracle_zmem.json \
  --out .zerker/bench/runs \
  --run-id "longmemeval-matrix-$(date -u +%Y%m%dT%H%M%SZ)" \
  --seed 42 \
  --trace \
  --compact-artifacts \
  --summary-only
```

Compact LongMemEval uses one ephemeral store per session and writes no run database or per-question bundle. Use a noncompact run only when retained proof artifacts are required.

Then verify and render:

```bash
zmem bench verify .zerker/bench/longmemeval-local-v1/pseudo-embedding-rerank/benchmark-result.json
zmem bench dashboard .zerker/bench/longmemeval-local-v1
zmem bench public-page .zerker/bench/longmemeval-local-v1
```

The `zmem-retrieval` mode is a compatibility alias for pseudo-rerank. The measured product-routing path is explicit as `fts-adaptive`, and the stored result records that concrete mode.

For compact ActiveGraph traces, smoke first:

```bash
zmem-bench-locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench/activegraph-locomo-smoke \
  --run-id activegraph-smoke-adaptive \
  --retrieval-mode fts-adaptive \
  --split default \
  --event-batch-size 128 \
  --limit 5
```

Use ActiveGraph for long storage-safe traces after the matrix identifies which modes are worth preserving. It writes compact `trace.jsonl` and `scored_receipt.json` instead of per-question receipt bundles. The real ActiveGraph 1.9 pack loader and the full 227-question batched acceptance path both pass.

For BEAM scale evidence, point ZMem at a local official bucket or conversation directory:

```bash
RUN_ID="beam-100k-$(date -u +%Y%m%dT%H%M%SZ)"

zmem bench run beam \
  --dataset /path/to/BEAM/chats/100K \
  --split 100K \
  --out .zerker/bench/runs \
  --run-id "$RUN_ID" \
  --retrieval-mode fts-adaptive \
  --context-budget-tokens 4096 \
  --trace \
  --compact-artifacts

zmem bench verify \
  ".zerker/bench/runs/$RUN_ID/benchmark-result.json" \
  --summary-only
```

BEAM runs hash every source chat/probing file and report source-reference coverage. Keep `public_benchmark_claim: false`: this adapter measures local evidence recall and proof integrity, not BEAM's official model-judged answer score.

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
