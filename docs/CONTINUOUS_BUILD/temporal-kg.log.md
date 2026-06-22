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
