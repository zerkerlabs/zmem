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

## 2026-06-23T06:54:59Z - L0 trust-ledger - Codex

- Scope: landed the root `revoke()` mutation receipt and snapshot export coverage without widening into descendant receipt emission or new proof-facing CLI surfaces.
- Files touched: `zerker_memory/store.py`; `tests/test_store.py`; `tests/test_snapshot.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`; `docs/SWARM_OPERATION_TRACKER.md`; `docs/CURRENT_STATE.md`; `docs/BUILD_LOG.md`.
- Behavior changed: `revoke()` now appends an ordered `zerker.memory.mutation_receipt` for the revoked root memory while preserving `memory_write_receipt(memory_id)` as the original source-provenance anchor. The new mutation receipt records actor identity, reason, previous status, resulting status/authority, revoked root+descendant ids, descendant count, prior receipt link, and prior/new Merkle roots. Descendants are still revoked without their own mutation receipts in this slice.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_revoke_persists_root_mutation_receipt_without_overwriting_original_write_provenance -q` -> passed; `python3 -m unittest tests.test_snapshot.SnapshotTest.test_snapshot_captures_revoke_mutation_write_receipt -q` -> passed; `python3 -m unittest tests.test_store -q` -> passed (173 tests); `python3 -m unittest tests.test_snapshot -q` -> passed (16 tests); `python3 -m zerker_memory eval` -> passed (11/11).
- Artifacts/receipts: snapshot export now preserves the revoke mutation receipt in the ordered root receipt chain, so revoke provenance and lineage remain independently verifiable outside the live DB. The receipt proves provenance/integrity of the revocation event, not semantic truth of the revoked claim.
- Blockers: `forget()` and lifecycle/export-only mutations still do not emit their own mutation receipts, and no read-only proof/report surface summarizes ordered mutation chains yet.
- Next safe slice: add the same bounded mutation-receipt envelope for `forget()`, or expose one read-only receipt-chain summary surface without changing existing source-provenance lookups.

## 2026-06-23T10:55:33Z - L0 trust-ledger - Codex

- Scope: landed the `forget()` mutation receipt and snapshot export coverage without widening into new proof/report read surfaces.
- Files touched: `zerker_memory/store.py`; `tests/test_store.py`; `tests/test_snapshot.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`; `docs/SWARM_OPERATION_TRACKER.md`; `docs/CURRENT_STATE.md`; `docs/BUILD_LOG.md`.
- Behavior changed: `forget()` now appends an ordered `zerker.memory.mutation_receipt` while preserving `memory_write_receipt(memory_id)` as the original source-provenance anchor. The new mutation receipt records actor identity, previous status, resulting status/authority, prior receipt link, and prior/new Merkle roots.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_forget_persists_mutation_receipt_without_overwriting_original_write_provenance -q` -> passed; `python3 -m unittest tests.test_snapshot.SnapshotTest.test_snapshot_captures_forget_mutation_write_receipt -q` -> passed; `python3 -m unittest tests.test_snapshot -q` -> passed (17 tests); `python3 -m unittest tests.test_store -q` -> passed (177 tests); `python3 -m zerker_memory eval` -> passed (11/11); `python3 scripts/release_smoke.py --summary-only` -> passed; `python3 -m zerker_memory status --summary-only` -> passed.
- Artifacts/receipts: snapshot export now preserves the forget mutation receipt in the ordered write-receipt chain, so forgotten-memory provenance and lineage remain independently verifiable outside the live DB. The receipt proves verified provenance and mutation integrity, not semantic truth of the forgotten claim.
- Blockers: lifecycle/export-only mutations still do not emit their own mutation receipts, and no read-only proof/report surface summarizes ordered mutation chains yet.
- Next safe slice: expose one read-only receipt-chain summary surface for the existing ordered mutation receipts, or define the first checkpoint/snapshot/export mutation-receipt contract before changing store behavior again.

## 2026-06-23T14:59:10Z - L0 trust-ledger - Codex

- Scope: landed the first explicit lifecycle mutation-receipt envelope for `checkpoint_session()` and `snapshot_session()` without adding a new table, CLI surface, or Treeship dependency.
- Files touched: `zerker_memory/store.py`; `tests/test_store.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`; `docs/SWARM_OPERATION_TRACKER.md`; `docs/CURRENT_STATE.md`; `docs/BUILD_LOG.md`.
- Behavior changed: `session_checkpoints()` and `session_snapshots()` now return a derived `zerker.lifecycle_receipt.v1` envelope for each persisted `SESSION_CHECKPOINTED` / `SESSION_SNAPSHOTTED` event. Each receipt is deterministically reconstructed from the durable event row plus stored payload, carries actor identity, session id, payload content digest, prior/new Merkle roots, snapshot hash, a `zerker.memory.mutation_receipt` Treeship statement, and explicit `semantic_truth_guaranteed: false` wording.
- Tests: `python3 -m unittest tests.test_store.MemoryStoreTest.test_checkpoint_session_emits_receipt_visible_roots_and_memory_type_summary tests.test_store.MemoryStoreTest.test_session_checkpoints_reads_back_persisted_checkpoint_events tests.test_store.MemoryStoreTest.test_snapshot_session_persists_snapshot_payload_and_receipt_visible_roots tests.test_store.MemoryStoreTest.test_session_snapshots_reads_back_persisted_snapshot_events_and_payloads -q` -> passed; `python3 -m unittest tests.test_snapshot.SnapshotTest.test_verify_snapshot_accepts_valid_snapshot tests.test_snapshot.SnapshotTest.test_restore_snapshot_round_trips_to_empty_store -q` -> passed; `python3 -m unittest tests.test_store -q` -> passed (182 tests); `python3 -m zerker_memory eval` -> passed (11/11).
- Artifacts/receipts: the lifecycle receipt hashes are independently recomputable from the returned payload, and the embedded Treeship statements prove verifiable lineage/integrity of the checkpoint or snapshot event only. They do not claim semantic truth of the stored memories or summaries.
- Blockers: `restore_snapshot()` still restores state without emitting its own rollback receipt, and there is still no read-only CLI/proof summary for ordered mutation or lifecycle receipt chains.
- Next safe slice: extend the same derived lifecycle receipt contract to `restore_snapshot()` so rollback/export verification has an explicit post-restore receipt without changing snapshot artifact format.

## 2026-06-23T19:04:20Z - L0 trust-ledger - Codex

- Scope: landed the first explicit rollback/export receipt for `restore_snapshot()` without adding a new table, appending a restore event, or changing snapshot artifact format.
- Files touched: `zerker_memory/store.py`; `tests/test_snapshot.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`; `docs/SWARM_OPERATION_TRACKER.md`; `docs/CURRENT_STATE.md`; `docs/BUILD_LOG.md`.
- Behavior changed: `restore_snapshot(snapshot, *, actor_id=\"snapshot_restore\")` now returns a derived `zerker.lifecycle_receipt.v1` receipt in its result payload. The receipt carries actor identity, snapshot hash, payload content digest, prior/new Merkle roots, optional `treeship_artifact_id: null`, and an embedded `zerker.memory.mutation_receipt` statement with `semantic_truth_guaranteed: false`. No restore event is appended, so the restored store Merkle root still matches the imported snapshot Merkle root exactly.
- Artifacts/receipts: the restore receipt is independently recomputable from the returned receipt payload plus the verified source snapshot summary. It proves verified provenance/integrity of the restore operation and imported snapshot lineage, not semantic truth of the restored memories.
- Tests: `python3 -m unittest tests.test_snapshot.SnapshotTest.test_restore_snapshot_returns_deterministic_restore_receipt_without_changing_snapshot_root tests.test_snapshot.SnapshotTest.test_restore_snapshot_round_trips_to_empty_store -q` -> passed; `python3 -m unittest tests.test_snapshot -q` -> passed (18 tests); `python3 -m unittest tests.test_store -q` -> passed (186 tests); `python3 -m zerker_memory eval` -> passed (11/11); `python3 scripts/release_smoke.py --summary-only` -> passed; `python3 -m zerker_memory status --summary-only` -> passed.
- Blockers: the restore receipt is returned but not yet summarized by any read-only CLI/proof surface, and export/handoff restore flows still rely on callers to surface the returned receipt explicitly.
- Next safe slice: expose one read-only receipt-chain or restore-summary surface that shows the returned lifecycle/rollback receipt without changing `memory_write_receipt(memory_id)` provenance-anchor semantics.

## 2026-06-23T23:02:26Z - L0 trust-ledger - Codex

- Scope: added one shared read-only verifier for existing lifecycle receipts so rollback/export and persisted session snapshot receipts can be checked independently without changing receipt formats or adding a Treeship dependency.
- Files touched: `zerker_memory/store.py`; `tests/test_store.py`; `tests/test_snapshot.py`; `docs/CONTINUOUS_BUILD/trust-ledger.log.md`; `docs/SWARM_OPERATION_TRACKER.md`; `docs/CURRENT_STATE.md`; `docs/BUILD_LOG.md`.
- Behavior changed: `MemoryStore.verify_lifecycle_receipt(receipt, *, source_snapshot=None)` now verifies `zerker.lifecycle_receipt.v1` payloads by recomputing `receipt_hash`, `content_digest`, and embedded Treeship statement consistency, plus optional snapshot-hash/root/count linkage when a source snapshot is supplied. This covers the derived `restore_snapshot()` rollback receipt and persisted `snapshot_session()` receipts without appending events or altering storage.
- Artifacts/receipts: lifecycle receipts are now independently checkable through a shared API instead of only via ad hoc test-side hash recomputation. Verification proves provenance/integrity and snapshot lineage consistency only; `semantic_truth_guaranteed` remains explicitly false.
- Tests: `python3 -m unittest tests.test_snapshot.SnapshotTest.test_verify_lifecycle_receipt_accepts_restore_snapshot_receipt_with_source_snapshot tests.test_snapshot.SnapshotTest.test_verify_lifecycle_receipt_reports_tampered_restore_receipt -q` -> passed; `python3 -m unittest tests.test_store.MemoryStoreTest.test_verify_lifecycle_receipt_accepts_persisted_session_snapshot_receipt -q` -> passed; `python3 -m unittest tests.test_snapshot -q` -> passed (20 tests); `python3 -m unittest tests.test_store -q` -> passed (190 tests); `python3 -m zerker_memory eval` -> passed (11/11).
- Blockers: the new verifier is still store-level only, so there is still no CLI/proof summary surface for restore receipts or ordered lifecycle/mutation receipt chains.
- Next safe slice: expose one read-only restore/receipt summary surface on top of `verify_lifecycle_receipt(...)` without changing `memory_write_receipt(memory_id)` provenance-anchor semantics.
