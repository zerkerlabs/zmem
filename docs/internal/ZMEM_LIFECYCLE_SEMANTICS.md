# ZMem Lifecycle Semantics

Last updated: 2026-06-23

This file records the current product semantics for memory lifecycle states. It is intentionally narrower than the product roadmap: it describes what the current code and tests prove today, and marks proof gaps explicitly.

## Status Matrix

| State/action | What it means today | Normal retrieval/injection behavior | Provenance/audit behavior | Current proof status |
| --- | --- | --- | --- | --- |
| `active` | Memory is eligible to influence actions when policy allows it. Human/system memories usually start here. | Search and inject can use it within matching scope, plus `global` memories are visible to scoped queries. | Original write receipt and event are recorded. | Covered by store, eval, receipt, and CTO smoke tests. |
| `proposed` | Memory is waiting for review. | Withheld from normal influence. | Write receipt and proposal event are recorded. | Supported by status model; less common than `quarantined` in current defaults. |
| `quarantined` | Memory exists but is inactive until review. Agent, document, import, and non-human policy memories default here. | Search can include it only when explicitly requested; inject records withholding instead of influence. | Write receipt and proposal event are recorded. | Covered by policy, provider, MCP, eval, and CTO smoke tests. |
| `promote` | Reviewer moves memory to `active` and raises trust/authority according to type. | Promoted memory can influence future actions when policy allows. | Original write receipt remains canonical; an ordered mutation receipt is appended. | Covered by store and snapshot tests. |
| `reject` | Reviewer marks proposed/quarantined/stale memory as not accepted. | Rejected memory is not returned by normal search or injection. | Original write receipt remains canonical; an ordered mutation receipt is appended with reason and previous status. | Covered by store tests. |
| `revoke` | Reviewer marks a memory and descendants as revoked because the source is unsafe, wrong, or tainted. | Revoked source and descendants are excluded from normal influence. | Revocation event is recorded for the root and lists affected descendants. Dedicated mutation receipts for revoke remain future trust-ledger work. | Covered by eval and store lineage behavior; mutation-receipt gap remains open. |
| `forget` | Reviewer marks a memory as forgotten while preserving an audit event. This is not physical deletion. | Forgotten memory is excluded from normal search/injection, even when quarantined/proposed memories are included. | Forget event is recorded with the memory content hash. Dedicated mutation receipt remains future trust-ledger work. | Covered by CTO smoke and focused store test; mutation-receipt gap remains open. |

## Current Guarantees

- Normal retrieval considers `active` memories by default.
- `include_quarantined=True` expands candidates to `active`, `quarantined`, and `proposed`; it does not include `deprecated`, `revoked`, or `forgotten`.
- Scoped retrieval uses exact scope match plus `global`; a query for one project/thread/session-style scope should not retrieve another scope's memory.
- Injection is narrower than search: retrieved candidates still pass policy gates before influencing an action.
- Receipts prove provenance, integrity, mutation lineage where emitted, and action influence. They do not prove semantic truth.

## Known Gaps

- `revoke()` and `forget()` do not yet append dedicated mutation receipts like `promote()` and `reject()` do.
- Scope boundaries are represented as strings today. Product-level guarantees for user, project, workspace, thread, and session should become explicit before claiming fine-grained isolation beyond tested scope strings.
- `forget` is logical forgetting, not cryptographic erasure or physical deletion.
- Runtime consolidation/dedupe semantics are still fixture-backed, not a full lifecycle job guarantee.

## Verification

Fast checks:

```bash
python3 -m zerker_memory cto-smoke
python3 -m unittest tests.test_store.MemoryStoreTest.test_scope_search_inject_isolates_project_thread_and_session_values tests.test_store.MemoryStoreTest.test_forget_hides_memory_without_deleting_audit_event -q
```

Broader checks:

```bash
python3 -m unittest tests.test_store -q
python3 -m zerker_memory eval
```

