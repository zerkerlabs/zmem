# Consolidation Unwind Fixture

This fixture adds one narrow L4 contract on top of the existing local job and summary ledgers: a read-only unwind plan for reversible summary repair.

## Goal

When a leaf child changes or a nested summary becomes suspect, operators need more than raw lineage:

- which summaries are directly impacted,
- which higher-level summaries depend on them,
- what order to review or rematerialize them in, and
- whether any impacted summary is already audit-blocked.

The unwind plan stays local-first and non-blocking. It does not mutate the store, run a daemon, or require a hosted model.

## Contract

[`/Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted/zerker_memory/consolidation_unwind.py`](/Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted/zerker_memory/consolidation_unwind.py) exposes:

- `consolidation_unwind_plan(job_ledger_path, summary_ledger_path, child_id)`
- `consolidation_retry_guidance(job_ledger_path, summary_ledger_path, child_id)`

It composes the existing L4 surfaces:

- `consolidation_summary_reverse_lineage_report(...)`
- `consolidation_summary_lineage_report(...)` when `child_id` is itself a nested summary
- `consolidation_audit_report(...)`

## Output

The returned `zerker.consolidation_unwind_plan.v1` payload keeps the plan actionable and auditable:

- `child_kind`: `source_child`, `nested_summary`, or `orphan_child`
- `direct_summary_ids`: the first summaries that depend on the child
- `impacted_summary_ids`: impacted summaries sorted bottom-up for safe repair order
- `root_summary_ids`: highest-level summaries affected by the change
- `blocked_summary_ids`: impacted summaries whose latest audit state is not `verified`, or that participate in a cycle
- `blocked_child_summary_ids`: nested-child lineage blockers such as missing nested summaries or cycles
- `steps`: one step per impacted summary with `audit_status`, `action`, dependency ids, and direct/root flags

The action contract is intentionally small:

- `review-and-rematerialize` when the impacted summary is audit-verified
- `review-before-rematerialize` when the impacted summary is already mismatched, missing, or otherwise blocked

## Retry Guidance

The unwind fixture now also exposes a read-only retry helper for operators who need to decide what can be recreated immediately and what must wait:

- `consolidation_retry_guidance(...)` builds on the unwind plan and classifies each impacted summary as either immediately retryable or blocked by prerequisite repair.
- `ready_summary_ids` lists summaries that can be recreated locally now without touching `store.py`, a daemon, or a hosted model.
- `child_retry_action` makes the starting condition explicit:
  - `repair-source-child-first` for a changed leaf child,
  - `repair-child-summary-first` for a nested summary that must be rematerialized before its parents, or
  - `no-dependent-summaries` when no persisted summaries currently depend on the child.
- Each step adds `retryable_now`, `retry_action`, `blocked_by_summary_ids`, and `blocking_reasons`.

The retry actions stay deliberately local and narrow:

- `rematerialize-local-summary` for an audit-verified summary with no unmet dependencies
- `recreate-missing-summary` when a completed job has no latest summary record but its source lineage is still intact
- `wait-for-dependent-summary-repair` or `wait-for-child-summary-repair` when parent summaries must not be recreated yet
- `review-mismatched-summary`, `review-unexpected-summary`, or `break-cycle-before-retry` when audit or lineage state is already unsafe

## Current Boundary

This is still a read-only planning layer. It does not:

- write repaired summaries,
- invalidate live store rows,
- queue background jobs,
- add hosted summarization, or
- change `zerker_memory/store.py` or `zerker_memory/bench.py`.

The next safe slice after this contract is to expose the same unwind plan through a read-only store or CLI surface once those overlapping files are safe to touch.
