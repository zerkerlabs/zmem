# Benchmark Lane Log

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
