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
- `plan_consolidation_jobs(...)` queues pending jobs only when the candidate has enough source children, the child set is stable, higher-level source summaries are already materialized, and recall still has an open gap.
- Matching `pending`, `running`, and `completed` jobs suppress duplicate planning; matching `failed` and `cancelled` jobs remain retryable.

This keeps the planner narrow and auditable: it only decides what should be queued into the existing append-only ledger, and it still does not write summary content, run a daemon, touch `store.py`, or require a hosted model. The extra materialization gate prevents higher-level day/week/profile-project jobs from piling up before the lower-level summary evidence they name actually exists.

## Recall Planner Report

The fixture now also exposes a read-only planner report for auditability before any background scheduler exists:

- `consolidation_recall_plan_report(...)` evaluates the same candidate set and matching-job rules as `plan_consolidation_jobs(...)`, but returns explicit per-candidate decisions instead of only the queued jobs.
- Each record preserves the candidate's scope, levels, ordered `source_child_ids`, trigger inputs, `decision`, and `decision_reason`, plus the latest matching job summary when one already exists.
- Higher-level candidates can now stop explicitly at `source-summaries-not-materialized`, so planners can distinguish "not enough stable evidence yet" from "the required lower-level summaries have not been emitted yet."
- Terminal `failed` and `cancelled` jobs stay explicitly retryable through `retrying_terminal_job: true`; `pending`, `running`, and `completed` matches stay visible as skip reasons instead of silent suppression.

This keeps the non-blocking consolidation path explainable and reversible without widening into `store.py`, a daemon loop, or hosted summarization: operators can now see why a candidate was queued, skipped for instability, blocked on missing lower-level summaries, skipped for no recall gap, or held back by an already-active/completed matching job.

## Ledger-Backed Recall Planner Report

The fixture now also exposes a persisted-state recall-planner audit for non-turn rollups:

- `consolidation_recall_plan_ledger_report(...)` reuses the existing append-only job ledger, summary ledger, and summary-audit report to derive whether non-`turn` source summaries are actually materialized and verified locally.
- Each planner record now keeps ordered `source_summary_dependencies`, `materialized_source_summary_ids`, `missing_source_summary_ids`, `verified_source_summary_ids`, `unverified_source_summary_ids`, `source_summary_audit_statuses`, and `source_summary_gate_reason` beside the existing queued-vs-skipped planner decision.
- When a persisted lower-level summary row exists, its dependency record now also carries the row's claimed `materialized_job_id`, `materialized_created_at`, and the expected producer `job_completed_at`, so operators can compare the expected producer job and the actual persisted summary timing without re-reading the raw JSONL rows.
- Ready `session -> day` or `day -> week` candidates only stay queueable when every required lower-level summary is both present in the local summary ledger and `verified` by the existing audit contract; mismatched local summaries stay visible as unverified dependency blockers instead of being treated as acceptable evidence.

This keeps higher-level consolidation local-first, reversible, and non-blocking without widening into `store.py`, a daemon loop, or hosted summarization: the same recall-planner report can now explain whether a day/week candidate is blocked because a required lower-level summary is missing entirely, exists but is audit-mismatched, or is fully verified and safe to queue.

## Profile/Project Aggregation Fixture

The fixture now also exposes the first deterministic local profile/project aggregation contract for scattered higher-level facts:

- `consolidation_profile_aggregation_fixture()` defines a small set of week-level claims about the same person or project across multiple summaries.
- `consolidation_profile_aggregation_report(...)` groups those claims by subject, de-duplicates repeated source summary ids and repeated facets, and reports which subjects are ready to feed a `week -> profile_project` rollup versus which should still be skipped.
- `merge_profile_aggregation_candidates_into_recall_planner(...)` lifts only the ready `candidate` payloads from that report into the existing recall-planner fixture, while staying idempotent when the same ready candidates are merged again.
- `consolidation_profile_aggregation_planner_report(...)` joins the same subject-level aggregation records to the existing planner decisions, so operators can see whether each ready profile/project candidate would queue now, stay blocked by an active job, or retry after a terminal job without reading two separate reports.
- `consolidation_profile_aggregation_planner_ledger_report(...)` keeps the same joined report local-first but now derives higher-level `source_children_materialized` gating from the persisted summary ledger and matching job history from the append-only job ledger.
- Ledger-backed records now also expose ordered `source_summary_dependencies`, so each required lower-level summary keeps its own `gate_status`, `audit_status`, latest job identity, `job_completed_at`, `materialized_created_at`, recorded `source_child_ids`, persisted `source_child_digests`, expected/materialized/missing `output_summary_ids`, and any persisted `mismatch_reasons` visible inside the higher-level blocked-vs-ready audit.
- Ready records emit planner-shaped `candidate` payloads with `summary_level=profile_project`, `source_level=week`, ordered `source_child_ids`, and a local `profile-fact-aggregation` trigger.
- Skipped records stay explicit with deterministic reasons such as `insufficient-source-summaries` or `no-open-recall-gap`, so profile/project consolidation does not become a noisy catch-all for every one-off mention.
- Ledger-backed records also expose `materialized_source_summary_ids`, `missing_source_summary_ids`, `verified_source_summary_ids`, `unverified_source_summary_ids`, `source_summary_audit_statuses`, and `source_summary_gate_reason`, so operators can see which week summaries already exist locally, which are still missing, and which exist but are audit-mismatched before a profile/project rollup is allowed to queue.

This keeps profile consolidation local-first and reversible without widening into `store.py`, live memory extraction, or hosted summarization: the system can now describe how scattered week summaries about the same person or project collapse into one auditable higher-level candidate, feed only those ready candidates into the existing non-blocking planner, explain the resulting queue-vs-blocked planner outcome per subject, prove when missing or audit-mismatched lower-level summary records in the append-only local ledger are the only reason a higher-level rollup stays blocked, and show either the materialized summary lineage or the still-missing lower-level job/output contract that each blocking week summary depends on.

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

- `consolidation_audit_report(job_ledger_path, summary_ledger_path)` joins the latest job state per `job_id` with the latest emitted summary record per `summary_id`, and still pulls an expected summary into the audit if that row exists under the right `summary_id` but a tampered `job_id`.
- Each audit record preserves the job's scope, levels, ordered `source_child_ids`, expected `output_summary_ids`, materialized summary ids, the job's `completed_at`, the job's `non_blocking` and `reversible` contract, and a compact emitted-summary digest view that now includes each persisted summary row's claimed `job_id` plus `created_at`.
- Mismatched materialized summaries now also keep explicit per-summary `mismatch_reasons`, so operators can tell whether a blocked dependency drifted on `job_id`, `source_child_count`, `content_digest`, impossible `created_at` timing versus the completed producer job, non-blocking/reversible flags, or hosted-LLM policy without re-deriving the audit by hand.
- The audit status is explicit and local-first:
  - `verified` when a completed job's expected outputs match the persisted summary ledger.
  - `missing-summary` when a completed job expects a summary that is not yet materialized in the ledger.
  - `mismatch` when persisted summary metadata no longer matches the completed job contract, including `job_id` drift, `source_child_count` drift, incomplete or malformed `source_child_digests`, a tampered or malformed `content_digest`, `created_at` earlier than the completed producer job, `non_blocking != true`, `reversible != true`, or `summarizer.hosted_llm == true`.
  - `not-materialized` or `unexpected-summary` for non-completed jobs, depending on whether summary records already exist.

This keeps the L4 surface reversible and auditable without widening into `store.py`, SQLite migrations, a daemon loop, or hosted summarization: operators can now inspect whether a completed local consolidation job still has the exact persisted summary output it claims to have produced.

## Transitive Summary Lineage Report

The fixture now also exposes a read-only recursive lineage view over the persisted summary ledger:

- `consolidation_summary_lineage_report(summary_ledger_path, summary_id)` expands a stored summary through any nested child summaries already present in the local ledger.
- The report preserves the root summary's `summary_level`, `source_level`, `lineage_kind`, and reversibility contract while also collecting ordered transitive `leaf_source_child_ids`, ordered transitive `summary_id` ancestry, any `missing_summary_ids`, and any `cycle_summary_ids`.
- Each summary node now also carries the persisted `job_id`, `created_at`, `summarizer`, `non_blocking`, `reversible`, and `source_child_digests` map for that exact summary record, so a transitive unwind can keep the producer identity, local-only summarizer contract, local materialization timestamp, required local execution contract, child ids, and recorded child-content digests together without re-reading raw JSONL.
- Each nested node stays explicit about whether a child is a leaf source child, a nested summary, a missing summary, or a cycle marker.

This keeps reversibility local-first and inspectable without widening into `store.py`, a daemon, or hosted summarization: operators can now unwind a day/week/profile-project summary back to the exact persisted lower-level summaries and leaf child ids that still support it.

## Reverse Summary Lineage Report

The fixture now also exposes the matching child-to-summary impact view over the persisted summary ledger:

- `consolidation_summary_reverse_lineage_report(summary_ledger_path, child_id)` starts from either a leaf source child id or a nested summary id and walks upward through any persisted parent summaries already present in the local ledger.
- The report preserves direct `summary_id` parents, ordered transitive `summary_id` ancestry, root impacted summaries, and explicit path arrays that show which higher-level summaries would need review or unwind if a child were revoked or rewritten.
- Each reverse-lineage path now also carries ordered `summary_nodes`, so the same impacted-summary walk keeps each persisted node's `job_id`, `created_at`, `summarizer`, `non_blocking`, `reversible`, `source_child_ids`, `source_child_digests`, and `content_digest` visible without reopening raw JSONL.
- Recursive cycles are still surfaced explicitly through `cycle_summary_ids` instead of silently looping.

This keeps the L4 surface reversible in both directions without widening into `store.py`, a daemon, or hosted summarization: operators can now ask not only "what evidence supports this summary?" but also "which summaries depend on this child?"

## Live Review-Gated Materialization

The live CLI now connects the fixture contracts to one exact verified source set:

- `zmem consolidation preview` produces a content-free source report plus a stable source identity and an artifact-specific confirmation identity.
- `zmem consolidation materialize` requires that confirmation identity and one candidate id, revalidates the source set under a locked query-only SQLite snapshot, and writes one deterministic summary to private job and summary ledgers.
- The completed job commits the summary content digest plus the exact preview, source digests, review assertion, and quarantined admission contract.
- Local writers serialize, exact replay appends nothing, and verified pending or summary-only interruption states resume to one completed transition.
- `zmem consolidation audit` fails on pending or malformed job history, missing/orphan/duplicate summaries, changed content, or broken source, preview, review, and admission bindings.

The summary ledger contains local summary text and is private. The result artifact does not. No canonical memory row is created, so materialization does not change retrieval or make the summary trusted, authoritative, or semantically true.

## Current Boundary

The L4 surface now reaches from verified live-source discovery through one explicitly confirmed, reversible private materialization and ledger audit. It still does not admit summaries into canonical memory, schedule periodic consolidation, or claim semantic fidelity. The next implementation slice is operator UX to inspect and explicitly admit or discard quarantined summaries before any scheduler or higher-level live rollup is considered.
