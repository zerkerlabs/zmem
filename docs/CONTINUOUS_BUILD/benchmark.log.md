# Benchmark Lane Log

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
