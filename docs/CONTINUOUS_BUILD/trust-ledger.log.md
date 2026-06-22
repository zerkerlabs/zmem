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
