# Temporal KG Lane Log

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
