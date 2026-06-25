# Consolidation Fixture

This fixture is the first L4 consolidation contract. It defines hierarchy and lineage only; it does not run a daemon, call a hosted LLM, or change retrieval behavior.

## Levels

| Rank | Level id | Label | Purpose |
| --- | --- | --- | --- |
| 0 | `turn` | turn | Single agent/user exchange or tool-observation unit. |
| 1 | `session` | session | Bounded work session made from turn-level children. |
| 2 | `day` | day | Calendar-day rollup made from sessions or selected turns. |
| 3 | `week` | week | Week-level rollup made from daily or session summaries. |
| 4 | `profile_project` | profile/project | Stable project or user-profile knowledge distilled from lower-level summaries. |

`profile_project` is the machine id for the `profile/project` level so ids remain path- and JSON-pointer-friendly.

## Reversible Lineage

Every summary record in the fixture carries:

- `summary_id`: the summary memory id.
- `summary_level`: the consolidation level of the summary.
- `source_level`: the level of the source children.
- `source_child_ids`: the exact child memory or summary ids used to produce the summary.
- `lineage_kind`: `source-child-to-summary`.
- `reversible`: `true`.

The first supported traversal is deliberately small:

1. `source_child_ids_for_summary(fixture, summary_id)` returns the children that created a summary.
2. `summary_ids_for_source_child(fixture, child_id)` returns summaries that include a child.
3. `validate_consolidation_lineage_fixture(fixture)` checks ordered levels, unique summary ids, non-empty child ids, upward-only rollups, and reversible lineage flags.

This makes a summary auditable before summarization policy exists: a future consolidation job can compact noisy turns into session/day/week/profile-project summaries while still letting operators inspect or revoke the child evidence behind any summary.

## Local Job Ledger

The next shipped L4 contract is a local append-only job ledger:

- `create_consolidation_job(...)` creates a pending non-blocking job with ordered levels, unique `source_child_ids`, reversible lineage, and `hosted_llm: false`.
- `transition_consolidation_job(...)` records `running`, `completed`, `failed`, or `cancelled` state without mutating child lineage.
- `append_consolidation_job_record(path, job)` writes newline-delimited JSON records for local durability and auditability.
- `load_consolidation_job_records(path)` and `latest_consolidation_jobs(path)` reload the append-only ledger into full history or latest-state views.

Completed jobs must record `output_summary_ids`, so a future summary writer can remain reversible: operators can trace a summary id back to the exact source children that fed the job.

## Recall Planner

The fixture now also exposes a first deterministic local recall planner:

- `consolidation_recall_planner_fixture()` defines candidate rollups across `turn -> session`, `session -> day`, `day -> week`, and `week -> profile_project`.
- `plan_consolidation_jobs(...)` queues pending jobs only when the candidate has enough source children, the child set is stable, and recall still has an open gap.
- Matching `pending`, `running`, and `completed` jobs suppress duplicate planning; matching `failed` and `cancelled` jobs remain retryable.

This keeps the planner narrow and auditable: it only decides what should be queued into the existing append-only ledger, and it still does not write summary content, run a daemon, touch `store.py`, or require a hosted model.

## Local Summary Materialization

The fixture now exposes a first deterministic local summary-writer contract on top of the existing job model:

- `materialize_consolidation_summary(...)` accepts a `pending` or `running` job plus ordered `source_children` content and returns:
- a `completed` job with `output_summary_ids`, and
- a `zerker.consolidation_summary.v1` payload.
- The summary payload stays auditable and reversible: it preserves `job_id`, `scope`, `summary_level`, `source_level`, ordered `source_child_ids`, per-child `sha256:` digests, a `content_digest` for the emitted summary text, `lineage_kind`, and the inherited local summarizer metadata.
- Summary ids are deterministic for the same job signature plus source-child digests, so repeated local materialization of the same exact inputs does not require a hosted model or a mutable scheduler-global counter.

This keeps the runtime summary surface deliberately small: it produces a local-first summary payload from already-selected child evidence, but it still does not inspect the live store, persist summary records to a separate ledger, or call a hosted LLM.

## Local Summary Ledger

The fixture now also exposes the first append-only persistence contract for emitted summaries:

- `append_consolidation_summary_record(path, job, summary)` writes a completed job's `zerker.consolidation_summary.v1` payload into a local JSONL ledger only after validating that the job and summary still agree on `job_id`, `output_summary_ids`, ordered `source_child_ids`, levels, reversibility, and `hosted_llm: false`.
- `load_consolidation_summary_records(path)` reloads the append-only summary ledger into ordered history.
- `latest_consolidation_summaries(path)` returns the latest ledger view keyed by `summary_id`.

This keeps summary persistence reversible and auditable without widening the system boundary: it still does not inspect the live store, run a daemon, or require hosted summarization, but emitted summaries no longer have to remain purely in-memory values.

## Local Ledger Audit Report

The fixture now also exposes a read-only audit view over the existing append-only ledgers:

- `consolidation_audit_report(job_ledger_path, summary_ledger_path)` joins the latest job state per `job_id` with the latest emitted summary record per `summary_id`.
- Each audit record preserves the job's scope, levels, ordered `source_child_ids`, expected `output_summary_ids`, materialized summary ids, and a compact emitted-summary digest view.
- The audit status is explicit and local-first:
  - `verified` when a completed job's expected outputs match the persisted summary ledger.
  - `missing-summary` when a completed job expects a summary that is not yet materialized in the ledger.
  - `mismatch` when persisted summary metadata no longer matches the completed job contract.
  - `not-materialized` or `unexpected-summary` for non-completed jobs, depending on whether summary records already exist.

This keeps the L4 surface reversible and auditable without widening into `store.py`, SQLite migrations, a daemon loop, or hosted summarization: operators can now inspect whether a completed local consolidation job still has the exact persisted summary output it claims to have produced.

## Transitive Summary Lineage Report

The fixture now also exposes a read-only recursive lineage view over the persisted summary ledger:

- `consolidation_summary_lineage_report(summary_ledger_path, summary_id)` expands a stored summary through any nested child summaries already present in the local ledger.
- The report preserves the root summary's `summary_level`, `source_level`, `lineage_kind`, and reversibility contract while also collecting ordered transitive `leaf_source_child_ids`, ordered transitive `summary_id` ancestry, any `missing_summary_ids`, and any `cycle_summary_ids`.
- Each nested node stays explicit about whether a child is a leaf source child, a nested summary, a missing summary, or a cycle marker.

This keeps reversibility local-first and inspectable without widening into `store.py`, a daemon, or hosted summarization: operators can now unwind a day/week/profile-project summary back to the exact persisted lower-level summaries and leaf child ids that still support it.

## Reverse Summary Lineage Report

The fixture now also exposes the matching child-to-summary impact view over the persisted summary ledger:

- `consolidation_summary_reverse_lineage_report(summary_ledger_path, child_id)` starts from either a leaf source child id or a nested summary id and walks upward through any persisted parent summaries already present in the local ledger.
- The report preserves direct `summary_id` parents, ordered transitive `summary_id` ancestry, root impacted summaries, and explicit path arrays that show which higher-level summaries would need review or unwind if a child were revoked or rewritten.
- Recursive cycles are still surfaced explicitly through `cycle_summary_ids` instead of silently looping.

This keeps the L4 surface reversible in both directions without widening into `store.py`, a daemon, or hosted summarization: operators can now ask not only "what evidence supports this summary?" but also "which summaries depend on this child?"

## Current Boundary

The fixture in [`/Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted/zerker_memory/consolidation.py`](/Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted/zerker_memory/consolidation.py) now exposes ordered levels, reversible lineage, the local job ledger, the recall-planner contract, a deterministic local summary materializer, an append-only summary ledger, a read-only ledger audit report, a transitive summary-lineage report, and a reverse child-to-summary lineage report, still with `hosted_llm: false` and `model_id: null`. The next implementation slice should source consolidation candidates from the live store or expose this audit/report surface through a read-only store or CLI path, without adding hosted summarization as a hard dependency.
