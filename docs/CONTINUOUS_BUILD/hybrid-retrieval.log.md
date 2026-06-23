# Hybrid Retrieval Lane Log

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
