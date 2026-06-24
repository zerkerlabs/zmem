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

## 2026-06-23 - session checkpoint root contract

- Scope: bounded L2 slice on store-level lifecycle checkpoints only; did not add `start_session`, `snapshot_session`, or `end_session` commands.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`.
- Behavior changed: `checkpoint_session` now persists `SESSION_CHECKPOINTED` events with session id, scope, snapshot hash/root summary, active-memory tree root, and memory-type-separated active ids/counts. `session_checkpoints` now reads those persisted checkpoint receipts back with receipt-visible prior/current Merkle roots.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_checkpoint_session_emits_receipt_visible_roots_and_memory_type_summary -q` and `python3 -m unittest tests.test_store.MemoryStoreTest.test_session_checkpoints_reads_back_persisted_checkpoint_events -q` passed. `python3 -m unittest tests.test_cli_onboarding tests.test_store tests.test_runner -q` failed on unrelated existing `tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts` and `tests.test_store.MemoryStoreTest.test_revoke_persists_root_mutation_receipt_without_overwriting_original_write_provenance`. `python3 -m zerker_memory eval` passed.
- Artifacts/receipts: `zerker.session_checkpoint.v1`, `SESSION_CHECKPOINTED` event payloads, `checkpoint_merkle_root`, `snapshot.snapshot_hash`, `snapshot.snapshot_merkle_root`, `memory_tree.root`, and `memory_type_summary.active_ids_by_type`.
- Blockers: no first-class `start_session`, `snapshot_session`, or `end_session` command surface yet. Broad verification is currently blocked outside this slice by the dirty `zerker_memory/cli.py` finalize-script string mismatch and missing revoke mutation receipt behavior.
- Next safe slice: add `snapshot_session` or a thin read-only CLI surface for `session_checkpoints` after the unrelated red-suite failures are isolated.

## 2026-06-23 - session snapshot payload contract

- Scope: bounded L2 slice on store-level lifecycle snapshots only; did not add `start_session`, `checkpoint_session` CLI wrappers, or `end_session` commands.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`.
- Behavior changed: `snapshot_session` now persists `SESSION_SNAPSHOTTED` events plus durable `session_snapshot_payloads` rows keyed by `session_snapshot_id` and `snapshot_hash`. `session_snapshots` now reads those persisted snapshot receipts back with receipt-visible prior/current Merkle roots, active-memory tree summary, memory-type-separated active ids/counts, and the stored pre-event full snapshot payload.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_snapshot_session_persists_snapshot_payload_and_receipt_visible_roots tests.test_store.MemoryStoreTest.test_session_snapshots_reads_back_persisted_snapshot_events_and_payloads -q` passed. `python3 -m unittest tests.test_cli_onboarding tests.test_store tests.test_runner -q` failed only on unrelated existing `tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts`. `python3 -m zerker_memory eval` passed.
- Artifacts/receipts: `zerker.session_snapshot.v1`, `SESSION_SNAPSHOTTED` event payloads, `session_snapshot_merkle_root`, `snapshot_hash`, and `session_snapshot_payloads.snapshot_json`.
- Blockers: no CLI surface yet for `snapshot_session`/`session_snapshots`, and no retention or export/restore policy exists yet for stored session snapshot payloads.
- Next safe slice: add a thin read-only CLI surface for `session_snapshots`, or add explicit retention metadata/soft-delete rules for stored session snapshot payloads without widening `start_session` or `end_session`.

## 2026-06-23 - session snapshot payload retention tombstones

- Scope: bounded L2 slice on retention/soft-delete for stored session snapshot payloads only; did not add `start_session`, `checkpoint_session`, or `end_session` commands.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`.
- Behavior changed: `soft_delete_session_snapshot_payload(...)` now marks durable `session_snapshot_payloads` rows with retention metadata, appends receipt-visible `SESSION_SNAPSHOT_PAYLOAD_SOFT_DELETED` events, and makes `session_snapshots()` return `payload_status` plus a retention tombstone instead of the full snapshot payload once a snapshot has been soft-deleted.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_soft_delete_session_snapshot_payload_preserves_receipt_visible_summary tests.test_store.MemoryStoreTest.test_session_snapshots_reports_soft_deleted_payload_without_returning_snapshot_json tests.test_store.MemoryStoreTest.test_snapshot_session_persists_snapshot_payload_and_receipt_visible_roots tests.test_store.MemoryStoreTest.test_session_snapshots_reads_back_persisted_snapshot_events_and_payloads -q` passed; `python3 -m unittest tests.test_store tests.test_runner` passed (`Ran 265 tests`); `python3 -m unittest tests.test_cli_onboarding tests.test_store tests.test_runner` failed only on unrelated existing `tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts`; `python3 -m zerker_memory eval` passed.
- Artifacts/receipts: `zerker.session_snapshot_retention.v1`, `SESSION_SNAPSHOT_PAYLOAD_SOFT_DELETED`, `payload_status`, `retention.deleted_event_hash`, and `retention.soft_delete_merkle_root`.
- Blockers: no read-only CLI/report surface summarizes snapshot retention state yet, and no automatic retention/pruning policy exists beyond the new explicit soft-delete API.
- Next safe slice: add a thin read-only CLI summary for `session_snapshots` retention state, or add one bounded retention-pruning policy without widening `start_session` or `end_session`.

## 2026-06-24 - session lifecycle read-only CLI summary

- Scope: bounded L2 slice on read-only lifecycle/session inspection only; did not add `start_session`, `checkpoint_session`, `snapshot_session`, or `end_session` write commands.
- Files touched: `zerker_memory/cli.py`, `tests/test_cli_onboarding.py`.
- Behavior changed: `zmem session checkpoints` and `zmem session snapshots` now expose persisted lifecycle state through JSON or `--summary-only` terminal summaries. The summaries surface checkpoint roots, snapshot roots/hashes, active memory-type counts, snapshot payload availability, and soft-delete retention tombstones without widening any lifecycle mutation path.
- Tests: focused CLI/store/runner lifecycle cluster passed (`python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_build_parser_parses_session_snapshot_summary_only tests.test_cli_onboarding.CliOnboardingTest.test_session_checkpoints_summary_surfaces_checkpoint_root_and_memory_type_counts tests.test_cli_onboarding.CliOnboardingTest.test_session_snapshots_summary_surfaces_soft_deleted_retention_state tests.test_store.MemoryStoreTest.test_checkpoint_session_emits_receipt_visible_roots_and_memory_type_summary tests.test_store.MemoryStoreTest.test_session_checkpoints_reads_back_persisted_checkpoint_events tests.test_store.MemoryStoreTest.test_snapshot_session_persists_snapshot_payload_and_receipt_visible_roots tests.test_store.MemoryStoreTest.test_session_snapshots_reports_soft_deleted_payload_without_returning_snapshot_json tests.test_runner.RunnerTest.test_build_context_separates_instructional_and_recall_memory_and_surfaces_budget_receipts -q`); broad `python3 -m unittest tests.test_cli_onboarding tests.test_store tests.test_runner -q` passed (`Ran 384 tests`); `python3 -m zerker_memory eval` passed (`11/11`).
- Artifacts/receipts: read-only summaries for `checkpoint_merkle_root`, `session_snapshot_merkle_root`, `snapshot_hash`, `payload_status`, and `retention.soft_delete_merkle_root`.
- Blockers: there is still no CLI write surface for `checkpoint_session` / `snapshot_session`, and no automatic retention-pruning policy exists beyond explicit soft-delete.
- Next safe slice: add one thin `zmem session checkpoint` write wrapper around the existing store contract, or add one bounded retention-pruning policy without widening `start_session` or `end_session`.
