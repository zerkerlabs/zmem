# Benchmark Lane Log

## 2026-07-10T20:57:19Z - per-conversation compact store lifecycle

- Scope: removed the full-run SQLite growth bottleneck from compact LoCoMo execution without changing normal proof-rich runs.
- Behavior: `--compact-artifacts` groups questions by `sample_id`, uses one ephemeral SQLite store at a time, preserves question order in result artifacts, and records `store_lifecycle=per-conversation-ephemeral` plus `run_database_omitted=true`.
- Real measurement: the largest official conversation (`conv-42`, `260` questions) completed pseudo-embedding in `57.29s`, roughly `272` questions/minute, and left zero SQLite files under the matrix output.
- Equivalence: all `260` correctness decisions, final answers, categories, abstention decisions, retrieved counts, and injected counts matched the earlier full pseudo-embedding artifact for `conv-42`; accuracy remained `0.6192307692`.
- Boundary: one equal-score retrieval tie changed context by two tokens without changing the answer or score. Non-compact runs retain the shared database, final snapshot, and receipt bundles exactly as before.
- Next safe slice: full isolated `pseudo-embedding-rerank`, followed by a fresh same-commit four-mode matrix and LongMemEval-S.

## 2026-07-10T20:44:24Z - v0.1.3 pseudo-embedding full run and legacy verifier hardening

- Scope: ran the first post-release full LoCoMo mode under a unique isolated target, then hardened comparison of older compact artifacts.
- Supported run: `python3.11 -m zerker_memory bench matrix locomo --dataset data/locomo/locomo_official_zmem.json --split default --out .zerker/bench --run-id locomo-v013-pseudo-embedding-py311-20260710 --mode pseudo-embedding --seed 42 --trace --compact-artifacts --summary-only`.
- Result: `1,986` questions, provisional-local accuracy `0.5966767372`, token F1 `0.5969195479`, EM `0.5966767372`, mean query tokens `536.0398`, result hash `3d31a2ee0a9ca73706dd3e64aecd53bfba5a8d06ee314487855c972ae3cc8367`, aggregate root `5adf3ecc29e5e88085040b26892d0e29031e012a4734a6fe94ea7cf9e7bf24fc`, trace SHA `65f5797fe255775e6d0516f4ed0cf4191e63a9334b517f5cfb34cb152efa8825`.
- Category accuracy: single-hop `0.6005`, multi-hop `0.0709`, temporal `0.6293`, open-domain `0.1250`, adversarial abstention `1.0000`. The run therefore preserves temporal/abstention but does not improve the hardest multi-hop/open-domain categories.
- Efficiency: `29,059` retrieved/injected memories and `1,064,575` query tokens, directionally `22.5%` and `22.7%` below the older FTS artifact. Do not attribute those deltas to mode alone because the baseline predates the current code checkpoint.
- Runtime finding: wall time was `38m57s`; throughput fell from roughly `230` questions/minute early to roughly `30`/minute near completion as the shared per-run SQLite store grew to about `900 MB`.
- Compatibility finding: the June FTS artifact retains null optional paths and names deleted receipt bundles. `bench compare` previously crashed on the null snapshot path; current code now treats omitted bundle paths as omitted and reports the remaining aggregate-root mismatch instead of crashing or silently accepting it.
- A generic `python3` attempt was stopped at `531/1,986` after discovering it resolved to unsupported Python `3.9.6`; the quarantined directory is explicitly named `.zerker/bench/locomo-v013-pseudo-embedding.incomplete-py39-20260710/` and is excluded from the scoreboard.
- Next safe slice: keep all automations paused, fix per-conversation benchmark store lifecycle/growth, then rerun same-commit FTS/FTS-multihop/pseudo-rerank evidence. `zmem-retrieval` is an alias for pseudo-rerank and should not consume a duplicate full run.

## 2026-06-23T06:05:00Z - interactive mode scoreboard

- Scope: after the official LoCoMo target collision, ran an isolated interactive mode comparison and read the existing LongMemEval oracle matrix for current retrieval guidance.
- LoCoMo pilot command: `python -m zerker_memory bench matrix locomo --dataset data/locomo/_pilot8.json --out .zerker/bench --run-id locomo-pilot8-mode-compare-20260623 --seed 42 --trace --summary-only`.
- LoCoMo pilot result: matrix verification `ok`, comparison verification `ok`, 8 questions, visible deltas `2`, stable wins `3`, stable misses `3`.
- LoCoMo pilot mode scores: `fts` accuracy `0.5`, `fts-multihop` `0.5`, `pseudo-embedding` `0.5`, `pseudo-embedding-rerank` `0.5`. `fts` remained best by latency; `fts-multihop` retrieved/injected more memory but did not improve accuracy on this slice.
- LoCoMo pilot artifacts: `.zerker/bench/locomo-pilot8-mode-compare-20260623/benchmark-matrix.json`, `benchmark-comparison.json`, `score-summary.json`, and `matrix-report.md`.
- LongMemEval matrix readout from existing `.zerker/bench/longmemeval-oracle-official-v1/`: `fts` accuracy `0.746`, `fts-multihop` `0.776`, `pseudo-embedding` `0.746`, and `pseudo-embedding-rerank` `0.746` over 500 questions.
- Product signal: current local multihop improves LongMemEval but not the LoCoMo pilot. Pseudo-embedding/rerank are not yet improving either benchmark locally, so the next L3 slice should focus on retrieval-to-answer conversion and multi-hop/open-domain evidence quality instead of only adding more candidates.

## 2026-06-23T05:45:49Z - LoCoMo fts-multihop attempt and ActiveGraph smoke

- Scope: executed the next planned LoCoMo `fts-multihop` measurement and then validated the ActiveGraph compact trace path.
- Conventional matrix command attempted: `python3 -m zerker_memory bench matrix locomo --dataset data/locomo/locomo_official_zmem.json --out .zerker/bench --run-id locomo-official-v1 --mode fts-multihop --seed 42 --summary-only`.
- Result: the matrix run failed with `sqlite3.OperationalError: attempt to write a readonly database` after partial progress. Partial artifacts were archived under `.zerker/bench/locomo-official-v1/fts-multihop.incomplete-20260623T053720Z/` with `226` question files and `226` receipt bundles.
- Coordination finding: the shared `.zerker/bench/locomo-official-v1/fts-multihop/` target was moved/archived while benchmark work was active; a second partial appeared as `.zerker/bench/locomo-official-v1/fts-multihop.incomplete-20260623Tcompact-switch/`. Treat the shared official matrix target as unsafe for manual full runs while other workers can touch it.
- Automation action: paused `zmem-benchmark-harness-swarm` so the official LoCoMo mode runs can be coordinated manually.
- ActiveGraph smoke command passed: `python3 -m zerker_memory.bench.activegraph_runner --dataset data/locomo/locomo_official_zmem.json --out .zerker/bench/activegraph-locomo-smoke --run-id activegraph-smoke-fts-multihop --retrieval-mode fts-multihop --split default --limit 5`.
- ActiveGraph smoke artifacts: `.zerker/bench/activegraph-locomo-smoke/activegraph-smoke-fts-multihop/trace.jsonl` (`5` lines), `scored_receipt.json`, `activegraph.sqlite`, and `memory.sqlite`; `find ... -name '*.bundle.json'` returned `0`.
- ActiveGraph smoke receipt: aggregate Merkle root `b827f09a31af1863b4f2317fd7def02eacaa9e188e1aaf12bde63a7e7806f6d5`, trace SHA `3916c59c2eb25f9906c57c2088bd2d812c70815a17f4fbab3bc4018d8a24fec5`, `question_count=5`, `mean_f1=0.0`, `overall_accuracy=0.0`, `public_benchmark_claim=false`.
- Next safe slice: do not run `pseudo-embedding`, `pseudo-embedding-rerank`, or `zmem-retrieval` yet. First choose either an isolated conventional output path for the full `fts-multihop` comparison or a full ActiveGraph compact trace run, then compare category deltas against the FTS baseline.

## 2026-06-23T04:22:30Z - official LoCoMo FTS baseline scored

- Scope: recorded the completed full LoCoMo official FTS run as the current baseline for retrieval and benchmark prioritization.
- Artifacts: `.zerker/bench/locomo-official-v1/fts/benchmark-result.json`, `summary.json`, `trace.jsonl`, `receipt.json`, and `scored_receipt.json`.
- Result: `scored_receipt.json` reports 1,986 questions, F1 `0.3752394031509457`, EM `0.37210473313192344`, retrieval mode `fts`, eval scope `per-conversation`, and trace SHA `67a005bf87b4bafcd2d7ce1cf8bfff97d7f430788afd0472511f738594971d0c`.
- Category readout: single-hop `0.6049` F1 / `0.6005` EM; multi-hop `0.0758` F1 / `0.0709` EM; temporal `0.6293` F1 / `0.6293` EM; open-domain `0.1369` F1 / `0.1250` EM; adversarial abstention `0.0` F1 / `0.0` EM.
- Token efficiency: mean query tokens `693.289`, mean ingest tokens `0.0`, total run tokens `1,376,872`.
- Claim boundary: `scored_receipt.json` carries `public_benchmark_claim: true` for the explicit rule-based token-F1/EM claim with no LLM judge. The sibling `receipt.json` is still a broader provisional harness receipt and has `public_benchmark_claim: false`.
- Product signal: retrieval and abstention are the bottlenecks. Multi-hop and open-domain are the largest quality gaps; temporal is comparatively strong and should be protected with regression runs; adversarial abstention needs a scoring/answering slice because the scored receipt gives it zero despite the provisional harness receipt treating abstention differently.
- Updated benchmark queue: run LongMemEval-S next because it directly tests abstention and semantic token efficiency; run LoCoMo semantic/hybrid fork-and-diff against this FTS baseline trace SHA using `ZMEM_RETRIEVAL_MODE`; add BEAM as the scale/collapse benchmark for 100K -> 10M token contexts where causal/event-chain memory should matter; then isolate multi-hop/open-domain/adversarial category slices or add category filtering to the harness if missing.
- Fastest product slice: add a deterministic answerer abstention threshold for `retrieved_count == 0` or low-confidence retrieval, then rerun LoCoMo adversarial and LongMemEval-S before deeper retrieval architecture changes.

## 2026-06-23T00:47:21Z - L6 benchmarks - matrix receipt proof surface

- Scope: enriched dataset-backed `bench matrix` trace receipts so LongMemEval and LoCoMo matrix runs keep reproducible commands, artifact hashes, proof roots, per-mode metrics, and the existing question-summary delta evidence in one machine-readable receipt.
- Files touched: `zerker_memory/bench.py`, `tests/test_bench.py`, `docs/CONTINUOUS_BUILD/benchmark.log.md`, `docs/SWARM_OPERATION_TRACKER.md`, `docs/BUILD_LOG.md`, `docs/CURRENT_STATE.md`.
- Behavior changed: `write_trace=True` matrix runs now write a richer `receipt.json` with `benchmark`, `split`, `matrix_hash`, `comparison_hash`, `artifact_hashes`, `proof_roots`, `mode_commands`, `mode_metrics`, `question_summary`, `memory_count_deltas`, and `efficiency_deltas` for local LongMemEval/LoCoMo evidence bundles.
- Tests: `python3 -m unittest tests.test_bench.BenchmarkHarnessTest.test_longmemeval_matrix_trace_receipt_preserves_summary_hashes_and_mode_commands tests.test_bench.BenchmarkHarnessTest.test_locomo_matrix_trace_receipt_preserves_summary_hashes_and_mode_commands -q` -> passed (`Ran 2 tests in 18.886s`); `python3 -m unittest tests.test_bench -q` -> passed (`Ran 137 tests in 478.450s`); `python3 -m unittest tests.test_store -q` -> passed (`Ran 165 tests in 6.051s`); `python3 -m zerker_memory eval` -> passed (`passed: 11`, `failed: 0`).
- Artifacts/receipts: temporary test matrices now prove dataset-backed receipt richness locally; no downloaded `data/` payloads, hosted judges, published reports, or generated `.zerker/launch-proof/` artifacts were committed.
- Blockers: matrix receipts are now richer, but standalone matrix-comparison and single-run comparison trace receipts still do not carry the same command/hash/proof summary surface.
- Next safe slice: extend the same receipt summary fields to standalone `benchmark-matrix-comparison.json` or comparison trace artifacts so reopened comparison-only evidence keeps parity with matrix directories.

## 2026-06-22T23:59:19Z - L6 benchmarks - cheap evidence summary

- Scope: added a fast fixture-backed summary path for persisted benchmark matrix evidence so future agents can inspect hashes and mode proof pointers without replaying the full matrix.
- Files touched: `scripts/bench/summarize_evidence.py`, `tests/test_bench_scripts.py`, `docs/BENCHMARK_SCORING_WORKFLOW.md`, `docs/CONTINUOUS_BUILD/benchmark.log.md`.
- Behavior changed: `python3 scripts/bench/summarize_evidence.py <matrix-dir|benchmark-matrix.json>` now reads `benchmark-matrix.json` plus sibling `benchmark-comparison.json`, recomputes their stored content hashes, reports file hashes, mode summaries, question summary, and keeps `public_benchmark_claim` false.
- Tests: `python3 -m unittest tests.test_bench_scripts -q` -> passed (`Ran 6 tests`); `python3 scripts/bench/summarize_evidence.py .zerker/bench/current-synthetic-20260612 --compact` -> passed read-only with `ok: true`.
- Artifacts/receipts: none; the test builds a temporary fixture and no downloaded `data/` or `.zerker` runtime outputs are committed.
- Blockers: this is a persisted-artifact health check only; official LoCoMo/LongMemEval claims still require pinned dataset versions, reproducible conversion/scoring commands, result bundles, and verified scoring.
- Next safe slice: add the same cheap summary path for standalone `benchmark-comparison.json` artifacts if agents need to inspect comparison-only evidence without opening full dashboards.

## 2026-06-22T22:59:00Z - L6 benchmarks - scoring workflow documented

- Scope: documented the operator workflow for converting official LongMemEval/LoCoMo files, running local proof-backed benchmark evidence, and opting into LLM/scored paths.
- Files touched: `docs/BENCHMARK_SCORING_WORKFLOW.md`, `docs/BENCHMARK_GETTING_STARTED.md`, `docs/README.md`, `docs/CONTINUOUS_BUILD/benchmark.log.md`, `docs/BUILD_LOG.md`, `docs/CURRENT_STATE.md`.
- Behavior changed: none; documentation only.
- Tests: `git diff --check`.
- Artifacts/receipts: none.
- Blockers: public benchmark claims still require pinned dataset versions, reproducible commands, result bundles, and verified scoring.
- Next safe slice: add a tiny fixture-backed command smoke for the documented `--mode zmem-retrieval` path if the benchmark swarm needs a faster guard than the full `tests.test_bench` suite.

## 2026-06-22T21:48:00Z - L6 benchmarks - external scoring scripts cleaned

- Scope: reviewed and tested local benchmark adapter/scoring scripts without committing downloaded datasets or runtime outputs.
- Files touched: `zerker_memory/bench.py`, `scripts/bench/`, `tests/test_bench.py`, `tests/test_bench_scripts.py`, `docs/CONTINUOUS_BUILD/benchmark.log.md`, `docs/BUILD_LOG.md`, `docs/CURRENT_STATE.md`.
- Behavior changed: adds script-level support for converting official LongMemEval/LoCoMo records into ZMem benchmark records, local LoCoMo token-F1/exact-match scoring, optional OpenAI-backed answer generation, and optional LongMemEval judge integration. Official benchmark runs now scope memories by LongMemEval session / LoCoMo sample so multiple questions from one conversation reuse the same history instead of duplicating it per question. The network/LLM paths remain explicit and guarded by `OPENAI_API_KEY` or repository availability.
- Tests: `python3 -m unittest tests.test_bench_scripts -q` -> passed (`Ran 5 tests`); `python3 -m unittest tests.test_bench.BenchmarkHarnessTest.test_longmemeval_shared_session_reuses_history_memory tests.test_bench.BenchmarkHarnessTest.test_locomo_shared_sample_reuses_history_memory -q` -> passed (`Ran 2 tests`); `python3 -m unittest tests.test_bench -q` -> passed (`Ran 132 tests`).
- Artifacts/receipts: no dataset payloads or scored receipts committed.
- Blockers: official datasets under `data/` are still local-only/untracked; public benchmark claims still require reproducible commands, pinned dataset hashes, and receipt bundles.
- Next safe slice: add docs for the exact local benchmark scoring workflow and keep fixture-sized data in tests rather than committing downloaded datasets.

## 2026-06-22 - coordinator

- Scope: seeded lane for LongMemEval/LoCoMo adapters, isolated DBs, benchmark receipts, reproducible matrix comparisons, and public result summaries.
- Files touched: lane log only.
- Behavior changed: none.
- Tests: not applicable.
- Artifacts/receipts: none.
- Blockers: existing benchmark automation is active; future slices must coordinate through this log.
- Next safe slice: update the benchmark automation prompt to write here.

## 2026-06-22T20:37:45Z - zmem-benchmark-harness-swarm

- Scope: lifted question-level memory-count and efficiency deltas into matrix artifact summaries so fresh `bench matrix --summary-only` runs expose retrieval tradeoffs without opening report or dashboard artifacts.
- Files touched: `zerker_memory/bench.py`, `zerker_memory/cli.py`, `tests/test_bench.py`.
- Behavior changed: `zerker.benchmark_matrix.v1` summaries now preserve `memory_count_deltas` plus `efficiency_deltas`, and the direct matrix CLI summary prints those deltas alongside the existing question-summary, budget-context, and proof-hop lines.
- Tests: `python3 -m unittest tests.test_bench.BenchmarkHarnessTest.test_cli_bench_matrix_summary_only_surfaces_latest_matrix_status -q` (`Ran 1 test in 0.677s`, `OK`), `python3 -m unittest tests.test_bench -q` (`Ran 132 tests in 199.220s`, `OK`), `python3 -m unittest tests.test_store -q` (`Ran 160 tests in 6.813s`, `OK`), `python3 -m zerker_memory eval` (`passed: 11`, `failed: 0`), `python3 scripts/release_smoke.py --summary-only` (`Release smoke summary checks completed.`), and `python3 -m zerker_memory status --summary-only` (`Workspace ready: yes`, `Doctor: ok`, `Strict publish ready: no`).
- Artifacts/receipts: none; this slice only changed local summary surfaces.
- Blockers: local matrix summaries now show count and efficiency tradeoffs, but the synthetic regression is still the only matrix-summary-only guardrail. Phase 1 launch proof remains externally blocked and unchanged at `0/6` clean-shell public-verify logs plus `0/8` launch assets; no Phase 1 launch-proof, installer, release-pack, prelaunch, public site copy, or generated `.zerker/launch-proof/` artifacts were edited by hand in this run.
- Next safe slice: add the same `bench matrix --summary-only` delta-summary regression for a local LongMemEval or LoCoMo fixture so the richer first-pass matrix CLI stays locked beyond the synthetic path.
