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

## Current Boundary

The fixture in [`/Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted/zerker_memory/consolidation.py`](/Users/zzo/Documents/Codex/2026-05-25/files-mentioned-by-the-user-trusted/zerker_memory/consolidation.py) now also exposes the first local job ledger contract, still with `hosted_llm: false` and `model_id: null`. The next implementation slice should add recall-planner fixtures or a minimal runtime summary writer on top of this ledger, without adding hosted summarization as a hard dependency.
