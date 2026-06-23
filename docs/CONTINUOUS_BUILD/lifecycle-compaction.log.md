# Lifecycle Compaction Lane Log

## 2026-06-22 - coordinator

- Scope: seeded lane for Working/Episodic/Semantic/Procedural memory, session lifecycle, checkpoints, snapshots, and context-boundary compaction.
- Files touched: lane log only.
- Behavior changed: none.
- Tests: not applicable.
- Artifacts/receipts: none.
- Blockers: worker must inventory existing session, handoff, restore, inject, and propose flows.
- Next safe slice: add a minimal checkpoint/session contract without widening setup UX.

## 2026-06-22 - procedural-vs-recall context contract

- Scope: bounded L2 slice on context-boundary packing only; did not add `start_session`, `checkpoint_session`, `snapshot_session`, or `end_session` commands.
- Files touched: `zerker_memory/store.py`, `zerker_memory/runner.py`, `tests/test_store.py`, `tests/test_runner.py`.
- Behavior changed: packing receipts now expose `memory_type_summary` for injected/withheld/budget-dropped ids by memory type, and runner context payloads now expose `memory_classes`, `memory_type_summary`, and `budget_dropped` so policy/procedural rules stay explicitly separate from episodic/semantic recall.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_packing_receipt_summarizes_instructional_recall_withheld_and_budget_dropped_types -q`, `python3 -m unittest tests.test_runner.RunnerTest.test_build_context_separates_instructional_and_recall_memory_and_surfaces_budget_receipts -q`, `python3 -m unittest tests.test_cli_onboarding tests.test_store tests.test_runner -q`, and `python3 -m zerker_memory eval`.
- Artifacts/receipts: `retrieval.packing.memory_type_summary`, context `memory_classes`, and context `budget_dropped`.
- Blockers: working memory and session lifecycle are still implicit; no receipt-visible checkpoint root or session command surface exists yet.
- Next safe slice: add one minimal checkpoint contract that writes a receipt-visible checkpoint root without widening snapshot/handoff UX.
