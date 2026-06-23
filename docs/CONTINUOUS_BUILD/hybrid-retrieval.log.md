# Hybrid Retrieval Lane Log

## 2026-06-23T04:09:04Z - hybrid semantic budget rerank

- Scope: fixed a direct-current hybrid retrieval ranking bug that surfaced under tight context budgets.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `tests/test_runner.py`, `docs/CONTINUOUS_BUILD/hybrid-retrieval.log.md`, `docs/SWARM_OPERATION_TRACKER.md`, `docs/BUILD_LOG.md`, `docs/CURRENT_STATE.md`.
- Behavior changed: when `fts_semantic_backfill_v1` applies on the default local reranker path, deterministic reranking now uses each candidate's `semantic_backfill_score` instead of pure query-term counts. Receipts now expose `reranker.local_strategy`, `local_score`, `local_lexical_score`, and `hybrid_semantic_score`, so a direct semantic state fact can outrank a weaker lexical update/support anchor and stay injected under one-memory budgets.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_current_deploy_target_budget_prefers_semantic_backfill_state_over_lexical_update_anchor -q` -> passed (`Ran 1 test`); `python3 -m unittest tests.test_runner.RunnerTest.test_build_context_current_deploy_target_budget_prefers_semantic_backfill_state -q` -> passed (`Ran 1 test`); `python3 -m unittest tests.test_store -q` -> passed (`Ran 169 tests`); `python3 -m unittest tests.test_policy -q` -> passed (`Ran 7 tests`); `python3 -m unittest tests.test_runner -q` -> passed (`Ran 77 tests`); `python3 -m zerker_memory eval` -> passed (`11/11`); `git diff --check -- zerker_memory/store.py tests/test_store.py tests/test_runner.py docs/CONTINUOUS_BUILD/hybrid-retrieval.log.md docs/SWARM_OPERATION_TRACKER.md docs/BUILD_LOG.md docs/CURRENT_STATE.md` -> passed.
- Artifacts/receipts: `retrieval.reranker` now explains whether `hybrid_semantic_backfill_score_v1` or lexical term matching decided local rerank order, and `retrieval.packing.budget_dropped` now makes the displaced lexical anchor explicit in the direct-query budget path.
- Blockers: this improves the default local reranker path only; baseline ordering when reranking is explicitly disabled, plus multi-hop/graph fusion ordering, still use older ranking signals.
- Next safe slice: make baseline ranking honor the same hybrid semantic signal when reranking is explicitly disabled so candidate order stays aligned across local retrieval modes.

## 2026-06-23T02:58:51Z - hybrid backfill RRF receipt summary

- Scope: closed a narrow L3 fusion explainability gap for existing FTS + semantic backfill retrieval.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `docs/CONTINUOUS_BUILD/hybrid-retrieval.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`.
- Behavior changed: when `fts_semantic_backfill_v1` applies, `retrieval.hybrid.fusion` now records a deterministic `reciprocal_rank_fusion_v1` summary of the actual selected lexical/semantic sources, plus the considered lexical and semantic candidate rankings. Selected candidates also carry `fusion_rank`, `fusion_score`, and `fusion_sources`.
- Tests: `python3 -m unittest tests.test_store -k hybrid_semantic_backfill -q` -> passed (`Ran 2 tests`); `python3 -m unittest tests.test_store -q` -> passed (`Ran 168 tests`); `python3 -m zerker_memory eval` -> passed (`11/11`).
- Artifacts/receipts: hybrid receipts now distinguish considered candidates from selected fusion contributors, so dropped lexical decoys remain visible without being credited as selected-source evidence.
- Blockers: this is receipt metadata only; it does not yet reorder retrieval through RRF, fuse graph traversal candidates, or add hosted vector provider calls.
- Next safe slice: extend the same fusion summary to multi-hop merge receipts or add a small deterministic conflict-resolution fixture before changing ranking behavior.

## 2026-06-23T02:42:10Z - target-history selection exclusions

- Scope: closed the next L3 explainability gap for no-superseded target-history prompts.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `tests/test_runner.py`, `docs/CONTINUOUS_BUILD/hybrid-retrieval.log.md`.
- Behavior changed: `retrieval.temporal.selection_exclusions` now records current anchors that were retrieved but not selected by `target_history_support_preferred_v1`, and each excluded candidate carries `temporal_selection_exclusion` plus `temporal_selection_exclusion_reason`.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_before_target_history_prefers_explicit_support_pair_over_generic_current_anchor tests.test_runner.RunnerTest.test_before_target_history_context_prefers_explicit_support_pair_over_generic_current_anchor -q` -> passed (`Ran 2 tests`); `python3 -m unittest tests.test_store -q` -> passed (`Ran 168 tests`); `python3 -m unittest tests.test_runner -q` -> passed (`Ran 76 tests`); `python3 -m zerker_memory eval` -> passed (`11/11`).
- Artifacts/receipts: generic anchors such as `Blue Finch changed after freeze.` can still appear in `retrieved_memory_ids`, but receipts now mark them as `target-history-current-anchor-not-selected` with the selected support/current pair ids.
- Blockers: this labels no-superseded target-history selection exclusions only; other temporal strategies still expose non-selection mostly through rank/selection fields rather than dedicated exclusion objects.
- Next safe slice: decide whether to generalize `selection_exclusions` to relation-history and chronology strategies, or switch to L2 checkpoint/root contracts if lifecycle remains the higher-priority lane.

## 2026-06-22 - coordinator

- Scope: seeded lane for BM25/FTS, dense providers, graph candidates, RRF, context packing, and receipt-visible retrieval decisions.
- Files touched: lane log only.
- Behavior changed: none.
- Tests: not applicable.
- Artifacts/receipts: none.
- Blockers: existing retrieval automation is active; future slices must avoid overlapping unmerged work.
- Next safe slice: make the next retrieval automation write here and to the orchestrator.

## 2026-06-22 - support-chain reservation

- Scope: extended L3 context packing from stale/current pair reservation to explicit stale/current/support chain reservation for history, update-history, and chronology relation prompts.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `tests/test_runner.py`.
- Behavior changed: packing now reserves `selected_current_anchor_id` plus explicit support anchors from temporal receipts; chronology relation prompts now emit `chronology_relation_support_chain_v1`; when the chain fits, older stale states are budget-dropped before the selected support anchor.
- Tests: `python3 -m unittest tests.test_store -q`, `python3 -m unittest tests.test_policy -q`, `python3 -m unittest tests.test_runner -q`, `python3 -m zerker_memory eval`.
- Artifacts/receipts: `retrieval.packing.reservation.requested_ids`/`applied_ids`, `candidate_priorities[].reserved_by_strategy`, and `budget_dropped[].reserved_by_strategy` now show support-chain reservation decisions directly.
- Blockers: `target_history_support_preferred_v1` still lacks the same budget reservation, so target-history stale/current/support chains can still lose support under pressure.
- Next safe slice: extend the same explicit support-chain reservation to target-history prompts while keeping budget-dropped receipts explicit.

## 2026-06-22T21:22:00Z - L3 hybrid-retrieval - live coordinator verification

- Scope: verified the latest retrieval drop as part of the accumulated live-session dirty tree.
- Files touched: lane log only.
- Behavior changed: none in this coordinator entry.
- Tests: `python3 -m unittest tests.test_bench tests.test_store tests.test_runner tests.test_policy tests.test_workspaces tests.test_cli_onboarding tests.test_snapshot tests.test_consolidation -q` -> passed (`Ran 503 tests`); `python3 -m zerker_memory eval` -> passed (`11/11`).
- Artifacts/receipts: no new external artifacts.
- Blockers: the working tree now contains multiple verified lanes plus generated/runtime folders. Checkpoint or split reviewed work before adding another broad retrieval slice.
- Next safe slice: checkpoint the reviewed support-chain reservation, then extend target-history support reservation in a fresh narrow L3 run.

## 2026-06-23T00:08:02Z - target-history support pair selection

- Scope: fixed the no-superseded target-history path so `before ... moved to ...` queries keep the explicit support/current pair even when a generic current anchor is also retrieved.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `tests/test_runner.py`.
- Behavior changed: `target_history_support_preferred_v1` now accepts larger current candidate sets, prefers the explicit history-cued support memory over generic current anchors, surfaces `selected_target_current_id` plus `selected_target_support_ids` in temporal receipts, and marks the pair through `packing.reservation.strategy = target_history_support_chain_v1` when it fits the budget.
- Tests: `python3 -m unittest tests.test_store -q`, `python3 -m unittest tests.test_policy -q`, `python3 -m unittest tests.test_runner -q`, `python3 -m zerker_memory eval`.
- Artifacts/receipts: target-history receipts now show the chosen support/current pair explicitly; generic current anchors can still appear in `retrieved_memory_ids` without being injected.
- Blockers: extra target-history current anchors are now excluded deterministically, but temporal receipts still do not label those excluded anchors with a dedicated withheld reason.
- Next safe slice: add receipt-visible exclusion metadata for extra target-history current anchors so generic notes are explicitly marked as retrieved-but-not-selected.
