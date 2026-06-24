# Temporal KG Lane Log

## 2026-06-24T02:59:31Z - L1 temporal-kg - Codex L1 worker

- Scope: carried the existing bi-temporal receipt subsets through `runner.build_context()` so runtime memory context preserves current/history and omitted-memory envelopes without any store/schema change.
- Files touched: `zerker_memory/runner.py`, `tests/test_runner.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: generated `zerker.memory_context.v1` payloads now include `temporal` metadata with `selection_strategy`, `selection_reason`, selected/current/history/superseded ids, current-conflict summaries, and the existing `selected_temporal_graph`, `injected_temporal_graph`, `withheld_temporal_graph`, and `budget_dropped_temporal_graph` subset envelopes from the stored receipt.
- Focused fixtures: one `Alice` vs `Alice Chen` history fixture proves runtime context keeps the superseded/current pair and leaves an unrelated `Alice` fact out of the selected temporal envelope; one omitted-subset fixture proves a denied `Status page owner is Alice Chen.` fact stays `current` in `withheld_temporal_graph` while `Incident owner was Alex.` remains injected superseded history and `Incident owner is Priya.` stays visible as a budget-dropped current envelope.
- Tests: `python3 -m unittest tests.test_runner.RunnerTest.test_build_context_preserves_current_vs_history_temporal_envelopes tests.test_runner.RunnerTest.test_build_context_preserves_temporal_omitted_subset_envelopes tests.test_runner.RunnerTest.test_build_context_separates_instructional_and_recall_memory_and_surfaces_budget_receipts -q` passed (`Ran 3 tests`); `python3 -m unittest tests.test_store -q` passed (`Ran 191 tests`); `python3 -m unittest tests.test_runner -q` passed (`Ran 82 tests`); `python3 -m zerker_memory eval` passed (`11/11`).
- Artifacts/receipts: none.
- Blockers: contradiction/abstention metadata is now forwarded into runtime context, but there is still no focused runner fixture proving a no-injection current-conflict snapshot survives into `temporal.conflict_sets` / `temporal.abstention`.
- Next safe slice: add one bounded runner-context contradiction fixture for competing current claims, or stop before any schema/query-surface work until a stricter `query_at(timestamp, status=...)` contract is needed.

## 2026-06-23T22:54:22Z - L1 temporal-kg - Codex L1 worker

- Scope: added receipt-visible temporal subset envelopes for omitted memories so `inject(...)` preserves current-vs-history metadata for `withheld` and `budget_dropped` facts without any schema change.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: `retrieval.temporal` now carries `withheld_temporal_graph` and `budget_dropped_temporal_graph` subsets derived from the shared temporal projection alongside the existing `selected_temporal_graph` and `injected_temporal_graph`. Omitted memories now keep their `learned_at`, `valid_from`, `valid_to`, `superseded_at`, `unlearned_at`, `status_at_query`, `temporal_state`, and current-conflict metadata in the stored receipt/`why(...)` payload.
- Focused fixtures: one deny-label fixture proves a current `Status page owner is Alice Chen.` fact stays visible as a withheld current envelope; one tight-budget chronology fixture proves `Incident owner was Alex.` remains injected as superseded history while `Incident owner is Priya.` is preserved as a budget-dropped current envelope.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_temporal_receipt_projection_preserves_withheld_current_subset_metadata tests.test_store.MemoryStoreTest.test_temporal_receipt_projection_preserves_budget_dropped_current_subset_metadata -q` passed (`Ran 2 tests`); `python3 -m unittest tests.test_store -q` passed (`Ran 189 tests`); `python3 -m unittest tests.test_runner -q` passed (`Ran 79 tests`); `python3 -m zerker_memory eval` passed (`11/11`).
- Artifacts/receipts: none.
- Blockers: omitted subsets are now receipt-visible, but there is still no dedicated `query_at(...)` filter surface for "only omitted at this receipt time," and runner context still exposes omission lists rather than temporal envelopes.
- Next safe slice: add one focused contradiction/history omitted-subset fixture for cross-provenance abstention, or deliberately stop before any schema work until a stricter `query_at(timestamp, status=...)` contract is needed.

## 2026-06-23T18:59:24Z - L1 temporal-kg - Codex L1 worker

- Scope: added contradiction-aware current-conflict metadata to the shared event-lineage temporal projection used by both `query_at(...)` and receipt envelopes, while keeping the slice schema-free and local-store-only.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: `_project_temporal_state(...)` now returns `resolved_current_memory_ids`, `dropped_current_memory_ids`, `abstained_current_memory_ids`, top-level `conflict_sets` / `abstention`, and per-memory `current_resolution` / `current_conflict_reasons` alongside the existing bi-temporal envelope. Inject receipts now mirror the resolved/dropped/abstained current-id subsets inside `retrieval.temporal` while reusing the same `temporal_graph`.
- Focused fixtures: one receipt test proves same-timestamp `Incident owner is Alex.` versus `Incident owner is Priya.` stays `temporal_state=current` but is marked `current_resolution=abstained` with no resolved current ids in the receipt projection; one `query_at(...)` test proves the same contradiction is explicit at a point in time without erasing the underlying current-state history.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_temporal_receipt_projection_surfaces_current_conflict_resolution_metadata tests.test_store.MemoryStoreTest.test_query_at_surfaces_current_conflict_resolution_metadata_without_erasing_current_state -q` passed (`Ran 2 tests`); `python3 -m unittest tests.test_runner -q` passed (`Ran 79 tests`); `python3 -m zerker_memory eval` passed (`11/11`); `python3 -m unittest tests.test_store -q` currently fails on unrelated existing lifecycle-compaction errors because `tests.test_store.MemoryStoreTest.test_soft_delete_session_snapshot_payload_preserves_receipt_visible_summary` and `tests.test_store.MemoryStoreTest.test_session_snapshots_reports_soft_deleted_payload_without_returning_snapshot_json` call a missing `MemoryStore.soft_delete_session_snapshot_payload`.
- Artifacts/receipts: none.
- Blockers: the required full store suite is currently red in the dirty tree on the unrelated L2 session-snapshot soft-delete contract; query-specific cross-provenance history abstention and withheld/budget-dropped temporal subset receipts are still not part of the shared projection.
- Next safe slice: either land the missing L2 session-snapshot soft-delete method outside this lane so the required broad store suite is green again, or keep L1 bounded and add receipt-visible withheld/budget-dropped temporal subsets now that contradiction metadata exists in the shared projection.

## 2026-06-23T14:54:48Z - L1 temporal-kg - Codex L1 worker

- Scope: surfaced receipt-visible temporal envelopes on `inject`/`why` by reusing the existing event-lineage `query_at(...)` projection, while keeping the slice schema-free and local-store-only.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: `retrieval.temporal` now persists `temporal_projection_at`, candidate `temporal_graph`, projected `history_memory_ids` / `current_memory_ids` / `future_memory_ids` / `superseded_memory_ids` / `unlearned_memory_ids` / `learned_memory_ids`, plus `selected_temporal_graph` and `injected_temporal_graph` subsets carrying `learned_at`, `valid_from`, `valid_to`, `superseded_at`, `unlearned_at`, `status_at_query`, and `temporal_state`. `why(action_id)` now returns the same receipt-visible envelope data because it reads the persisted retrieval payload back unchanged.
- Focused fixtures: one receipt test proves `Status page owner is Alice.` becomes a superseded history envelope while `Status page owner is Alice Chen.` stays current and an unrelated `Alice` fact stays out of the receipt; another proves a promoted `Release checklist owner is Alice Chen.` memory preserves distinct `learned_at` and `valid_from` timestamps inside the inject receipt.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_temporal_contract_current_vs_history_keeps_identity_disambiguation tests.test_store.MemoryStoreTest.test_temporal_receipt_projection_preserves_learned_vs_valid_time_for_promoted_memory -q` passed (`Ran 2 tests`); `python3 -m unittest tests.test_store -q` passed (`Ran 182 tests`); `python3 -m unittest tests.test_runner -q` passed (`Ran 79 tests`); `python3 -m zerker_memory eval` passed (`11/11`).
- Artifacts/receipts: none.
- Blockers: contradiction-aware abstention and cross-provenance competing facts still rely on the existing conflict-set receipt path rather than an explicit bi-temporal contradiction envelope; withheld/budget-dropped memories still do not have dedicated temporal subset receipts.
- Next safe slice: add contradiction-aware abstention metadata to the shared temporal projection without widening into schema changes, or decide whether withheld/budget-dropped temporal subsets should be the next receipt-focused temporal contract.

## 2026-06-22 - coordinator

- Scope: seeded lane for bi-temporal graph memory, point-in-time queries, supersession, and entity disambiguation.
- Files touched: lane log only.
- Behavior changed: none.
- Tests: not applicable.
- Artifacts/receipts: none.
- Blockers: worker must map existing temporal metadata before schema changes.
- Next safe slice: document current temporal fields and add a focused `query_at` contract test.

## 2026-06-22T18:49:55Z - L1 temporal-kg - Codex L1 worker

- Scope: mapped the existing temporal memory surface and added a narrow current-vs-history contract fixture before any schema migration.
- Files touched: `tests/test_store.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`.
- Behavior changed: no runtime behavior changed; the new test locks existing retrieval behavior for an `Alice` -> `Alice Chen` supersession while keeping an unrelated `Alice` memory out of both current and history receipts.
- Existing temporal inventory: persisted memory fields are `created_at`, `updated_at`, `expires_at`, `status`, and `parents_json`; event, retrieval, and write receipts also carry `created_at`. Retrieval derives `temporal_state` as `current`, `superseded`, `expired`, or `revoked`, marks `superseded_by_candidate`, and records `selected_current_ids`, `selected_superseded_ids`, `stale_ids`, conflict sets, and injection order under `retrieval["temporal"]`. There are no explicit persisted `valid_from`, `valid_to`, `learned_at`, `superseded_at`, `unlearned_at`, or `query_at(timestamp)` API fields yet.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_temporal_contract_current_vs_history_keeps_identity_disambiguation -q` passed; `python3 -m unittest tests.test_store -q` passed (`Ran 158 tests`).
- Artifacts/receipts: none.
- Blockers: explicit bi-temporal graph memory still needs schema/API design; current implementation is retrieval-time lifecycle resolution over timestamps, parents, status, and receipts, not durable valid-time/transaction-time graph edges.
- Next safe slice: add the first failing `query_at(timestamp)` contract around the same supersession fixture, then implement the smallest local-store point-in-time API using existing `created_at`/`updated_at` and parent lineage before adding new graph tables.

## 2026-06-22T22:55:26Z - L1 temporal-kg - Codex L1 worker

- Scope: shipped the first local `query_at(timestamp)` projection for explicit bi-temporal envelopes using existing event history plus parent lineage, without any schema migration.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: `MemoryStore.query_at(...)` now returns derived `learned_at`, `valid_from`, `valid_to`, `superseded_at`, `unlearned_at`, `status_at_query`, and point-in-time temporal state (`current`, `superseded`, `learned`, `future`) for a scope-local snapshot, with optional lexical narrowing plus parent/child lineage closure.
- Focused fixtures: one test proves quarantined memory can be `learned` before promotion and `current` after promotion because `learned_at` and `valid_from` differ; another proves `Status page owner is Alice` becomes superseded by `Status page owner is Alice Chen` on `2024-02-01T00:00:00Z` while an unrelated `Alice` memory stays separate across both snapshots.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_query_at_projects_learned_and_valid_time_from_existing_events tests.test_store.MemoryStoreTest.test_query_at_projects_parent_supersession_without_merging_unrelated_alice_identity -q` passed (`Ran 2 tests`); `python3 -m unittest tests.test_store -q` passed (`Ran 163 tests`); `python3 -m unittest tests.test_runner -q` passed (`Ran 74 tests`); `python3 -m zerker_memory eval` passed (`11/11`).
- Artifacts/receipts: none.
- Blockers: the projection currently uses event status transitions plus parent lineage only; explicit same-subject update/restatement supersession and receipt-visible point-in-time metadata are still deferred.
- Next safe slice: port the existing explicit-update and same-provenance restatement supersession rules from retrieval receipts into `query_at`, then decide whether `inject`/`why` should expose the same derived temporal envelopes.

## 2026-06-23T06:53:18Z - L1 temporal-kg - Codex L1 worker

- Scope: extended `query_at(timestamp)` so explicit same-subject update memories can supersede older facts without parent links, while keeping the slice local-store-only and schema-free.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: point-in-time temporal envelopes now apply the existing lexical explicit-update rule inside `query_at`, using existing event sequence order as the deterministic tiebreaker when `valid_from` timestamps match. Older facts now move to `superseded` with derived `superseded_at`, `valid_to`, and `superseded_by_ids` even when no parent edge exists.
- Focused fixture: `Deploy target is Staging.` versus `Deploy target changed to Production.` at the same timestamp now resolves to only the update memory in `current_memory_ids`, with the older fact preserved in history as superseded.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_query_at_explicit_update_supersedes_older_same_subject_memory_without_parent_link -q` passed (`Ran 1 test`); `python3 -m unittest tests.test_store.MemoryStoreTest.test_query_at_projects_learned_and_valid_time_from_existing_events tests.test_store.MemoryStoreTest.test_query_at_projects_parent_supersession_without_merging_unrelated_alice_identity tests.test_store.MemoryStoreTest.test_query_at_explicit_update_supersedes_older_same_subject_memory_without_parent_link -q` passed (`Ran 3 tests`); `python3 -m unittest tests.test_store -q` passed (`Ran 173 tests`); `python3 -m unittest tests.test_runner -q` passed (`Ran 77 tests`); `python3 -m zerker_memory eval` passed (`11/11`).
- Artifacts/receipts: none.
- Blockers: `query_at` still does not project same-provenance subject-lookup restatement supersession or receipt-surface point-in-time metadata, so retrieval receipts remain the richer path for those explanations.
- Next safe slice: port same-provenance restatement supersession into `query_at`, then decide whether `inject`/`why` should expose the same derived temporal envelopes directly.

## 2026-06-23T10:52:17Z - L1 temporal-kg - Codex L1 worker

- Scope: extended `query_at(timestamp)` so same-provenance plain restatements can supersede older facts without parent links or explicit update phrasing, while keeping the slice local-store-only and schema-free.
- Files touched: `zerker_memory/store.py`, `tests/test_store.py`, `docs/CONTINUOUS_BUILD/temporal-kg.log.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: point-in-time temporal envelopes now apply the existing lexical subject/relation grouping for same-provenance restatements inside `query_at`. Within one group, the latest `valid_from` wins; equal `valid_from` falls back to existing event sequence order as the local deterministic serial. Older facts now move to `superseded` with derived `superseded_at`, `valid_to`, and `superseded_by_ids` even when no parent edge exists.
- Focused fixture: `Incident owner is Alice.` is superseded by `Incident owner is Alice Chen.` on `2024-02-15T00:00:00Z`, while unrelated `Runbook owner is Alice.` stays current across the same snapshots.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_query_at_same_provenance_restatement_supersedes_older_subject_fact_without_parent_link tests.test_store.MemoryStoreTest.test_query_at_explicit_update_supersedes_older_same_subject_memory_without_parent_link tests.test_store.MemoryStoreTest.test_query_at_projects_parent_supersession_without_merging_unrelated_alice_identity -q` passed (`Ran 3 tests`); `python3 -m unittest tests.test_store -q` passed (`Ran 176 tests`); `python3 -m unittest tests.test_runner -q` passed (`Ran 78 tests`); `python3 -m zerker_memory eval` passed (`11/11`).
- Artifacts/receipts: none.
- Blockers: `query_at` still does not surface contradiction-aware abstention or receipt-visible current-vs-history temporal envelopes on `inject`/`why`, so retrieval receipts remain the richer explanation path for those cases.
- Next safe slice: expose the same derived temporal envelopes directly in `inject`/`why` receipts before widening into contradiction handling or schema changes.
