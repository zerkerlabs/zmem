# Trust Ledger Lane Log

## 2026-06-22 - coordinator

- Scope: seeded lane for memory receipt, Merkle lineage, rollback/export, and Treeship proof integration.
- Files touched: lane log only.
- Behavior changed: none.
- Tests: not applicable.
- Artifacts/receipts: none.
- Blockers: worker must first inventory existing mutation paths and receipt fields.
- Next safe slice: add a failing or clarifying test for receipt emission on one non-add mutation.

## 2026-06-22T18:50:00Z - L0 trust-ledger - Codex

- Scope: inventoried durable mutation paths and strengthened receipt-adjacent lineage coverage for one non-add mutation without changing store behavior.
- Files touched: `tests/test_snapshot.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`.
- Behavior changed: none. Existing durable mutations observed: `remember`/`import_external` create memory rows, Merkle events, and `memory_write_receipts`; `promote`, `reject`, `revoke`, and `forget` update memory status/authority and append Merkle events; `inject` creates action receipts; `snapshot`/`restore_snapshot` export and restore memories, events, action receipts, and write receipts.
- Tests: `python3 -m unittest tests.test_snapshot` -> passed, 14 tests.
- Artifacts/receipts: strengthened `test_snapshot_captures_promote_event_lineage` proves a `PROMOTED` event is snapshot-visible, chained via `prev_event_hash`, and reflected in the snapshot Merkle root.
- Blockers: non-add transitions still do not create their own `memory_write_receipts`; this slice only locks the existing event-ledger coverage.
- Next safe slice: define the minimal transition receipt envelope for `promote` or `revoke`, then add a focused failing test before touching `zerker_memory/store.py`.

## 2026-06-22T22:54:56Z - L0 trust-ledger - Codex

- Scope: landed the first durable non-add mutation receipt for `promote` without turning Treeship into a user-facing dependency.
- Files touched: `zerker_memory/store.py`; `tests/test_store.py`; `tests/test_snapshot.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`; `docs/CURRENT_STATE.md`; `docs/BUILD_LOG.md`; `docs/SWARM_OPERATION_TRACKER.md`.
- Behavior changed: `promote()` now appends a second ordered `memory_write_receipt` for the mutation itself; `memory_write_receipt(memory_id)` stays pinned to the original source-provenance receipt for existing bundle/why/workspace surfaces, and new `memory_write_receipts(memory_id)` exposes the full event-ordered receipt chain.
- Artifacts/receipts: the new promote mutation receipt carries actor identity, content digest, prior receipt link, prior Merkle root, new Merkle root, and event hash in its embedded Treeship statement; this proves mutation provenance and integrity, not semantic truth of the promoted claim.
- Snapshot/export: snapshot write receipts are now exported in event order, so the original provenance receipt and the promote mutation receipt remain independently restorable and verifiable.
- Tests: `python3 -m unittest tests.test_snapshot.SnapshotTest.test_snapshot_captures_promote_mutation_write_receipt tests.test_snapshot.SnapshotTest.test_snapshot_captures_promote_event_lineage -q` -> passed; `python3 -m unittest tests.test_store.MemoryStoreTest.test_promote_persists_mutation_receipt_without_overwriting_original_write_provenance -q` -> passed; `python3 -m unittest tests.test_snapshot -q` -> passed (15 tests); `python3 -m unittest tests.test_store -q` -> passed (161 tests); `python3 -m zerker_memory eval` -> passed (11/11); `python3 scripts/release_smoke.py --summary-only` -> passed; `python3 -m zerker_memory status --summary-only` -> passed.
- Blockers: `reject`, `revoke`, `forget`, and lifecycle/export-only mutations still do not emit their own mutation receipts, and no CLI/report surface summarizes the ordered receipt chain yet.
- Next safe slice: add the same explicit mutation-receipt envelope for `reject` or `revoke`, then extend one proof-facing surface to display ordered mutation receipts without changing current source-provenance semantics.

## 2026-06-22T23:20:00Z - L0 trust-ledger - Codex

- Scope: advanced non-add mutation receipt coverage by adding the ordered mutation receipt for `reject()`.
- Files touched: `zerker_memory/store.py`; `tests/test_store.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`.
- Behavior changed: `reject()` now appends a `zerker.memory.mutation_receipt` after the original source-provenance write receipt, carrying actor identity, rejection reason, previous status, resulting status/authority, prior receipt link, prior Merkle root, new Merkle root, and event hash. `memory_write_receipt(memory_id)` still returns the original provenance receipt; `memory_write_receipts(memory_id)` exposes the ordered chain. Receipts prove provenance/integrity of the rejection event, not semantic truth.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_reject_persists_mutation_receipt_without_overwriting_original_write_provenance -q` -> passed; `python3 -m unittest tests.test_store.MemoryStoreTest.test_promote_persists_mutation_receipt_without_overwriting_original_write_provenance tests.test_store.MemoryStoreTest.test_queue_and_reject_memory -q` -> passed; `python3 -m unittest tests.test_snapshot -q` -> passed (15 tests); `python3 -m unittest tests.test_store -q` -> passed (164 tests).
- Artifacts/receipts: new focused test verifies the reject mutation receipt is ordered after the original receipt, preserves the original receipt lookup, links to the prior receipt hash/id, and avoids semantic-truth language.
- Blockers: `revoke()` and `forget()` still do not emit mutation receipts; proof-facing CLI/report summaries for ordered write receipt chains remain absent.
- Next safe slice: add mutation receipt coverage for `revoke()` root events, including affected descendant ids, without attempting per-descendant receipts unless a separate test defines that behavior.
