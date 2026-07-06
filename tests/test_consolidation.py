import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from zerker_memory.consolidation import (
    CONSOLIDATION_AUDIT_RECORD_SCHEMA,
    CONSOLIDATION_AUDIT_REPORT_SCHEMA,
    CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA,
    CONSOLIDATION_LINEAGE_KIND,
    CONSOLIDATION_LINEAGE_REPORT_SCHEMA,
    CONSOLIDATION_PROFILE_AGGREGATION_REPORT_SCHEMA,
    CONSOLIDATION_PROFILE_PLANNER_LEDGER_REPORT_SCHEMA,
    CONSOLIDATION_PROFILE_PLANNER_REPORT_SCHEMA,
    CONSOLIDATION_RECALL_PLAN_LEDGER_REPORT_SCHEMA,
    CONSOLIDATION_RECALL_PLAN_REPORT_SCHEMA,
    CONSOLIDATION_REVERSE_LINEAGE_REPORT_SCHEMA,
    CONSOLIDATION_SUMMARY_SCHEMA,
    append_consolidation_job_record,
    append_consolidation_summary_record,
    consolidation_audit_report,
    consolidation_profile_aggregation_fixture,
    consolidation_profile_aggregation_planner_ledger_report,
    consolidation_profile_aggregation_planner_report,
    consolidation_profile_aggregation_report,
    consolidation_recall_plan_ledger_report,
    consolidation_summary_reverse_lineage_report,
    consolidation_summary_lineage_report,
    create_consolidation_job,
    consolidation_levels,
    consolidation_lineage_fixture,
    consolidation_recall_planner_fixture,
    consolidation_recall_plan_report,
    latest_consolidation_jobs,
    latest_consolidation_summaries,
    load_consolidation_job_records,
    load_consolidation_summary_records,
    materialize_consolidation_summary,
    merge_profile_aggregation_candidates_into_recall_planner,
    plan_consolidation_jobs,
    source_child_ids_for_summary,
    summary_ids_for_source_child,
    transition_consolidation_job,
    validate_consolidation_lineage_fixture,
)


class ConsolidationFixtureTest(unittest.TestCase):
    def _append_materialized_summary(
        self,
        *,
        job_ledger_path: Path,
        summary_ledger_path: Path,
        summary_id: str,
        summary_level: str,
        source_level: str,
        source_child_ids: list[str],
        created_at: str,
        completed_at: str,
    ) -> None:
        pending = create_consolidation_job(
            scope=summary_id.replace("summary:", "project:"),
            summary_level=summary_level,
            source_level=source_level,
            source_child_ids=source_child_ids,
            created_at=created_at,
            job_id=f"consolidation-job:{summary_id}",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at=completed_at,
            summary_id=summary_id,
            source_children=[
                {"child_id": child_id, "content": f"{summary_id} source {index + 1}."}
                for index, child_id in enumerate(source_child_ids)
            ],
        )
        append_consolidation_job_record(job_ledger_path, pending)
        append_consolidation_job_record(job_ledger_path, completed)
        append_consolidation_summary_record(summary_ledger_path, completed, summary)

    def _append_materialized_week_summary(
        self,
        *,
        job_ledger_path: Path,
        summary_ledger_path: Path,
        summary_id: str,
        created_at: str,
        completed_at: str,
    ) -> None:
        pending = create_consolidation_job(
            scope=summary_id.replace("summary:", "project:"),
            summary_level="week",
            source_level="day",
            source_child_ids=[
                f"{summary_id}:child:one",
                f"{summary_id}:child:two",
            ],
            created_at=created_at,
            job_id=f"consolidation-job:{summary_id}",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at=completed_at,
            summary_id=summary_id,
            source_children=[
                {"child_id": f"{summary_id}:child:one", "content": f"{summary_id} child one."},
                {"child_id": f"{summary_id}:child:two", "content": f"{summary_id} child two."},
            ],
        )
        append_consolidation_job_record(job_ledger_path, pending)
        append_consolidation_job_record(job_ledger_path, completed)
        append_consolidation_summary_record(summary_ledger_path, completed, summary)

    def test_levels_define_ordered_hierarchical_contract(self):
        levels = consolidation_levels()

        self.assertEqual(
            [level["id"] for level in levels],
            ["turn", "session", "day", "week", "profile_project"],
        )
        self.assertEqual([level["rank"] for level in levels], [0, 1, 2, 3, 4])
        self.assertEqual(levels[-1]["label"], "profile/project")

    def test_lineage_fixture_is_reversible_from_summary_to_sources(self):
        fixture = consolidation_lineage_fixture()
        summary_id = "summary:session:2026-06-22:payments-routing"

        self.assertEqual(fixture["schema"], CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA)
        self.assertTrue(validate_consolidation_lineage_fixture(fixture))
        self.assertEqual(
            source_child_ids_for_summary(fixture, summary_id),
            ["memory:turn:001", "memory:turn:002", "memory:turn:003"],
        )
        self.assertEqual(summary_ids_for_source_child(fixture, "memory:turn:002"), [summary_id])
        self.assertIn(
            "summary:day:2026-06-22:zmem-launch",
            summary_ids_for_source_child(fixture, summary_id),
        )

    def test_fixture_has_no_hosted_summarizer_dependency(self):
        fixture = consolidation_lineage_fixture()

        self.assertEqual(
            {summary["lineage_kind"] for summary in fixture["summaries"]},
            {CONSOLIDATION_LINEAGE_KIND},
        )
        self.assertEqual(fixture["summarizer"]["kind"], "deterministic-fixture")
        self.assertFalse(fixture["summarizer"]["hosted_llm"])
        self.assertIsNone(fixture["summarizer"]["model_id"])

    def test_job_record_starts_pending_non_blocking_and_reversible(self):
        job = create_consolidation_job(
            scope="project:zmem",
            summary_level="session",
            source_level="turn",
            source_child_ids=["memory:turn:001", "memory:turn:002"],
            created_at="2026-06-22T19:00:00Z",
            job_id="consolidation-job:test",
        )

        self.assertEqual(job.status, "pending")
        self.assertTrue(job.non_blocking)
        self.assertTrue(job.reversible)
        self.assertEqual(job.lineage_kind, CONSOLIDATION_LINEAGE_KIND)
        self.assertEqual(job.output_summary_ids, ())
        self.assertFalse(job.summarizer["hosted_llm"])
        self.assertIsNone(job.summarizer["model_id"])

    def test_completed_job_records_output_summary_ids(self):
        pending = create_consolidation_job(
            scope="project:zmem",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:one", "summary:session:two"],
            created_at="2026-06-22T19:00:00Z",
            job_id="consolidation-job:complete",
        )

        running = transition_consolidation_job(
            pending,
            status="running",
            updated_at="2026-06-22T19:05:00Z",
        )
        completed = transition_consolidation_job(
            running,
            status="completed",
            updated_at="2026-06-22T19:06:00Z",
            output_summary_ids=["summary:day:2026-06-22:zmem"],
        )

        self.assertEqual(running.started_at, "2026-06-22T19:05:00Z")
        self.assertEqual(completed.completed_at, "2026-06-22T19:06:00Z")
        self.assertEqual(completed.output_summary_ids, ("summary:day:2026-06-22:zmem",))

    def test_job_records_persist_in_append_only_local_ledger(self):
        pending = create_consolidation_job(
            scope="project:zmem",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:one", "summary:session:two"],
            created_at="2026-06-22T19:00:00Z",
            job_id="consolidation-job:ledger",
        )
        completed = transition_consolidation_job(
            pending,
            status="completed",
            updated_at="2026-06-22T19:07:00Z",
            output_summary_ids=["summary:day:2026-06-22:zmem"],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            append_consolidation_job_record(ledger_path, pending)
            append_consolidation_job_record(ledger_path, completed)

            records = load_consolidation_job_records(ledger_path)
            latest = latest_consolidation_jobs(ledger_path)

        self.assertEqual([record.status for record in records], ["pending", "completed"])
        self.assertEqual(
            latest["consolidation-job:ledger"].output_summary_ids,
            ("summary:day:2026-06-22:zmem",),
        )

    def test_recall_planner_fixture_queues_only_ready_candidates(self):
        fixture = consolidation_recall_planner_fixture()

        planned_jobs = plan_consolidation_jobs(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
        )

        self.assertEqual(
            [job.job_id for job in planned_jobs],
            [
                "consolidation-job:planned:candidate:session:2026-06-23:zmem-alpha",
                "consolidation-job:planned:candidate:day:2026-06-23:zmem",
            ],
        )
        self.assertEqual(
            [(job.source_level, job.summary_level) for job in planned_jobs],
            [("turn", "session"), ("session", "day")],
        )
        self.assertTrue(all(job.non_blocking for job in planned_jobs))
        self.assertTrue(all(job.reversible for job in planned_jobs))
        self.assertTrue(all(not job.summarizer["hosted_llm"] for job in planned_jobs))

    def test_recall_plan_report_explains_queued_and_skipped_candidates(self):
        fixture = consolidation_recall_planner_fixture()

        report = consolidation_recall_plan_report(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
        )

        self.assertEqual(report["schema"], CONSOLIDATION_RECALL_PLAN_REPORT_SCHEMA)
        self.assertEqual(report["candidate_count"], 4)
        self.assertEqual(report["queued_job_count"], 2)
        self.assertEqual(report["skipped_candidate_count"], 2)
        self.assertEqual(
            [job["job_id"] for job in report["planned_jobs"]],
            [
                "consolidation-job:planned:candidate:session:2026-06-23:zmem-alpha",
                "consolidation-job:planned:candidate:day:2026-06-23:zmem",
            ],
        )
        record_by_candidate_id = {
            record["candidate_id"]: record for record in report["records"]
        }
        self.assertEqual(
            record_by_candidate_id["candidate:session:2026-06-23:zmem-alpha"]["decision_reason"],
            "ready",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:day:2026-06-23:zmem"]["planned_job_id"],
            "consolidation-job:planned:candidate:day:2026-06-23:zmem",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:week:2026-w26:zmem"]["decision_reason"],
            "source-children-not-stable",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:profile-project:zmem"]["decision_reason"],
            "no-open-recall-gap",
        )

    def test_recall_planner_skips_candidates_with_active_or_completed_matching_jobs(self):
        fixture = consolidation_recall_planner_fixture()
        existing_jobs = [
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102", "memory:turn:103"],
                created_at="2026-06-23T03:00:00Z",
                job_id="consolidation-job:existing-session",
            ),
            transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/day:2026-06-23",
                    summary_level="day",
                    source_level="session",
                    source_child_ids=[
                        "summary:session:2026-06-23:zmem-alpha",
                        "summary:session:2026-06-23:zmem-beta",
                    ],
                    created_at="2026-06-23T03:00:00Z",
                    job_id="consolidation-job:existing-day",
                ),
                status="completed",
                updated_at="2026-06-23T03:10:00Z",
                output_summary_ids=["summary:day:2026-06-23:zmem"],
            ),
        ]

        planned_jobs = plan_consolidation_jobs(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
            existing_jobs=existing_jobs,
        )

        self.assertEqual(planned_jobs, [])

    def test_recall_plan_report_surfaces_existing_job_skip_reasons(self):
        fixture = consolidation_recall_planner_fixture()
        existing_jobs = [
            transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/session:alpha",
                    summary_level="session",
                    source_level="turn",
                    source_child_ids=["memory:turn:101", "memory:turn:102", "memory:turn:103"],
                    created_at="2026-06-23T03:00:00Z",
                    job_id="consolidation-job:running-session",
                ),
                status="running",
                updated_at="2026-06-23T03:05:00Z",
            ),
            transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/day:2026-06-23",
                    summary_level="day",
                    source_level="session",
                    source_child_ids=[
                        "summary:session:2026-06-23:zmem-alpha",
                        "summary:session:2026-06-23:zmem-beta",
                    ],
                    created_at="2026-06-23T03:00:00Z",
                    job_id="consolidation-job:completed-day",
                ),
                status="completed",
                updated_at="2026-06-23T03:10:00Z",
                output_summary_ids=["summary:day:2026-06-23:zmem"],
            ),
        ]

        report = consolidation_recall_plan_report(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
            existing_jobs=existing_jobs,
        )

        record_by_candidate_id = {
            record["candidate_id"]: record for record in report["records"]
        }
        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(
            record_by_candidate_id["candidate:session:2026-06-23:zmem-alpha"]["decision_reason"],
            "existing-running-job",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:session:2026-06-23:zmem-alpha"]["latest_matching_job"]["job_id"],
            "consolidation-job:running-session",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:day:2026-06-23:zmem"]["decision_reason"],
            "existing-completed-job",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:day:2026-06-23:zmem"]["latest_matching_job"]["output_summary_ids"],
            ["summary:day:2026-06-23:zmem"],
        )

    def test_recall_planner_allows_retry_after_failed_matching_job(self):
        fixture = consolidation_recall_planner_fixture()
        failed_job = transition_consolidation_job(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102", "memory:turn:103"],
                created_at="2026-06-23T03:00:00Z",
                job_id="consolidation-job:failed-session",
            ),
            status="failed",
            updated_at="2026-06-23T03:10:00Z",
            error="local summarizer unavailable",
        )

        planned_jobs = plan_consolidation_jobs(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
            existing_jobs=[failed_job],
        )

        self.assertEqual(
            [job.job_id for job in planned_jobs],
            [
                "consolidation-job:planned:candidate:session:2026-06-23:zmem-alpha",
                "consolidation-job:planned:candidate:day:2026-06-23:zmem",
            ],
        )

    def test_recall_plan_report_marks_failed_and_cancelled_jobs_retryable(self):
        fixture = consolidation_recall_planner_fixture()
        existing_jobs = [
            transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/session:alpha",
                    summary_level="session",
                    source_level="turn",
                    source_child_ids=["memory:turn:101", "memory:turn:102", "memory:turn:103"],
                    created_at="2026-06-23T03:00:00Z",
                    job_id="consolidation-job:failed-session",
                ),
                status="failed",
                updated_at="2026-06-23T03:10:00Z",
                error="local summarizer unavailable",
            ),
            transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/day:2026-06-23",
                    summary_level="day",
                    source_level="session",
                    source_child_ids=[
                        "summary:session:2026-06-23:zmem-alpha",
                        "summary:session:2026-06-23:zmem-beta",
                    ],
                    created_at="2026-06-23T03:00:00Z",
                    job_id="consolidation-job:cancelled-day",
                ),
                status="cancelled",
                updated_at="2026-06-23T03:11:00Z",
                error="operator cancelled",
            ),
        ]

        report = consolidation_recall_plan_report(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
            existing_jobs=existing_jobs,
        )

        record_by_candidate_id = {
            record["candidate_id"]: record for record in report["records"]
        }
        self.assertEqual(report["queued_job_count"], 2)
        self.assertTrue(
            record_by_candidate_id["candidate:session:2026-06-23:zmem-alpha"]["retrying_terminal_job"]
        )
        self.assertEqual(
            record_by_candidate_id["candidate:session:2026-06-23:zmem-alpha"]["decision_reason"],
            "retry-after-failed-job",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:day:2026-06-23:zmem"]["decision_reason"],
            "retry-after-cancelled-job",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:day:2026-06-23:zmem"]["latest_matching_job"]["status"],
            "cancelled",
        )

    def test_recall_planner_skips_non_turn_candidate_until_source_summaries_materialize(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            {
                "candidate_id": "candidate:week:2026-w27:zmem",
                "scope": "project:zmem/week:2026-w27",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:day:2026-06-24:zmem",
                    "summary:day:2026-06-25:zmem",
                ],
                "trigger": {
                    "kind": "child-count-stability-recall-gap",
                    "min_source_children": 2,
                    "source_children_stable": True,
                    "source_children_materialized": False,
                    "has_open_recall_gap": True,
                },
            }
        ]

        planned_jobs = plan_consolidation_jobs(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
        )

        self.assertEqual(planned_jobs, [])

    def test_recall_plan_report_marks_non_turn_candidate_as_waiting_for_materialized_source_summaries(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            {
                "candidate_id": "candidate:profile-project:zmem",
                "scope": "project:zmem/profile-project",
                "summary_level": "profile_project",
                "source_level": "week",
                "source_child_ids": [
                    "summary:week:2026-w26:zmem",
                    "summary:week:2026-w27:zmem",
                ],
                "trigger": {
                    "kind": "child-count-stability-recall-gap",
                    "min_source_children": 2,
                    "source_children_stable": True,
                    "source_children_materialized": False,
                    "has_open_recall_gap": True,
                },
            }
        ]

        report = consolidation_recall_plan_report(
            fixture,
            planned_at="2026-06-23T03:30:00Z",
        )

        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        self.assertEqual(report["records"][0]["decision_reason"], "source-summaries-not-materialized")
        self.assertFalse(report["records"][0]["trigger"]["source_children_materialized"])

    def test_recall_plan_ledger_report_queues_day_candidate_after_session_summaries_verify(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            candidate
            for candidate in fixture["candidates"]
            if candidate["candidate_id"] == "candidate:day:2026-06-23:zmem"
        ]

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-27T13:00:00Z",
                completed_at="2026-06-27T13:05:00Z",
            )
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-beta",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:201", "memory:turn:202"],
                created_at="2026-06-27T13:06:00Z",
                completed_at="2026-06-27T13:10:00Z",
            )

            report = consolidation_recall_plan_ledger_report(
                fixture,
                planned_at="2026-06-27T13:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["schema"], CONSOLIDATION_RECALL_PLAN_LEDGER_REPORT_SCHEMA)
        self.assertEqual(report["job_history_count"], 4)
        self.assertEqual(report["materialized_summary_count"], 2)
        self.assertEqual(report["queued_job_count"], 1)
        self.assertEqual(report["skipped_candidate_count"], 0)
        self.assertEqual(
            [job["job_id"] for job in report["planned_jobs"]],
            ["consolidation-job:planned:candidate:day:2026-06-23:zmem"],
        )
        record = report["records"][0]
        self.assertEqual(record["decision"], "queued")
        self.assertEqual(record["decision_reason"], "ready")
        self.assertEqual(
            record["materialized_source_summary_ids"],
            [
                "summary:session:2026-06-23:zmem-alpha",
                "summary:session:2026-06-23:zmem-beta",
            ],
        )
        self.assertEqual(record["missing_source_summary_ids"], [])
        self.assertEqual(
            record["verified_source_summary_ids"],
            [
                "summary:session:2026-06-23:zmem-alpha",
                "summary:session:2026-06-23:zmem-beta",
            ],
        )
        self.assertEqual(record["unverified_source_summary_ids"], [])
        self.assertEqual(
            record["source_summary_audit_statuses"],
            {
                "summary:session:2026-06-23:zmem-alpha": "verified",
                "summary:session:2026-06-23:zmem-beta": "verified",
            },
        )
        self.assertEqual(record["source_summary_gate_reason"], "all-source-summaries-verified")
        self.assertEqual(
            [dependency["gate_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "verified"],
        )

    def test_recall_plan_ledger_report_blocks_week_candidate_when_day_summary_is_unverified(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            {
                "candidate_id": "candidate:week:2026-w26:zmem",
                "scope": "project:zmem/week:2026-w26",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:day:2026-06-22:zmem",
                    "summary:day:2026-06-23:zmem",
                ],
                "trigger": {
                    "kind": "child-count-stability-recall-gap",
                    "min_source_children": 2,
                    "source_children_stable": True,
                    "source_children_materialized": True,
                    "has_open_recall_gap": True,
                },
            }
        ]

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:day:2026-06-22:zmem",
                summary_level="day",
                source_level="session",
                source_child_ids=["summary:session:2026-06-22:alpha", "summary:session:2026-06-22:beta"],
                created_at="2026-06-27T13:00:00Z",
                completed_at="2026-06-27T13:05:00Z",
            )
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:day:2026-06-23:zmem",
                summary_level="day",
                source_level="session",
                source_child_ids=["summary:session:2026-06-23:alpha", "summary:session:2026-06-23:beta"],
                created_at="2026-06-27T13:06:00Z",
                completed_at="2026-06-27T13:10:00Z",
            )
            tampered_day_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:day:2026-06-23:zmem",
                "job_id": "consolidation-job:summary:day:2026-06-23:zmem",
                "scope": "project:day:2026-06-23:zmem",
                "summary_level": "day",
                "source_level": "session",
                "source_child_ids": ["summary:session:2026-06-23:alpha"],
                "source_child_count": 1,
                "source_child_digests": {"summary:session:2026-06-23:alpha": "sha256:tampered"},
                "summary_text": "[summary:session:2026-06-23:alpha] tampered day rollup.",
                "content_digest": "sha256:tampered-day",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T13:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_day_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_recall_plan_ledger_report(
                fixture,
                planned_at="2026-06-27T13:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["schema"], CONSOLIDATION_RECALL_PLAN_LEDGER_REPORT_SCHEMA)
        self.assertEqual(report["job_history_count"], 4)
        self.assertEqual(report["materialized_summary_count"], 2)
        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        record = report["records"][0]
        self.assertEqual(record["decision"], "skipped")
        self.assertEqual(record["decision_reason"], "source-summaries-not-materialized")
        self.assertEqual(record["verified_source_summary_ids"], ["summary:day:2026-06-22:zmem"])
        self.assertEqual(record["unverified_source_summary_ids"], ["summary:day:2026-06-23:zmem"])
        self.assertEqual(
            record["source_summary_audit_statuses"],
            {
                "summary:day:2026-06-22:zmem": "verified",
                "summary:day:2026-06-23:zmem": "mismatch",
            },
        )
        self.assertEqual(record["source_summary_gate_reason"], "unverified-source-summaries")
        self.assertEqual(
            [dependency["gate_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "unverified"],
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["source_child_digests"],
            {"summary:session:2026-06-23:alpha": "sha256:tampered"},
        )

    def test_recall_plan_ledger_report_blocks_day_candidate_when_session_summary_child_count_is_tampered(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            candidate
            for candidate in fixture["candidates"]
            if candidate["candidate_id"] == "candidate:day:2026-06-23:zmem"
        ]

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-27T13:00:00Z",
                completed_at="2026-06-27T13:05:00Z",
            )
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-beta",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:201", "memory:turn:202"],
                created_at="2026-06-27T13:06:00Z",
                completed_at="2026-06-27T13:10:00Z",
            )
            tampered_session_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:session:2026-06-23:zmem-beta",
                "job_id": "consolidation-job:summary:session:2026-06-23:zmem-beta",
                "scope": "project:session:2026-06-23:zmem-beta",
                "summary_level": "session",
                "source_level": "turn",
                "source_child_ids": ["memory:turn:201", "memory:turn:202"],
                "source_child_count": 1,
                "source_child_digests": {
                    "memory:turn:201": "sha256:turn-201",
                    "memory:turn:202": "sha256:turn-202",
                },
                "summary_text": "[memory:turn:201] one.\n[memory:turn:202] two.",
                "content_digest": "sha256:tampered-session-count",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T13:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_session_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_recall_plan_ledger_report(
                fixture,
                planned_at="2026-06-27T13:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        record = report["records"][0]
        self.assertEqual(record["decision"], "skipped")
        self.assertEqual(record["decision_reason"], "source-summaries-not-materialized")
        self.assertEqual(
            record["verified_source_summary_ids"],
            ["summary:session:2026-06-23:zmem-alpha"],
        )
        self.assertEqual(
            record["unverified_source_summary_ids"],
            ["summary:session:2026-06-23:zmem-beta"],
        )
        self.assertEqual(
            record["source_summary_audit_statuses"],
            {
                "summary:session:2026-06-23:zmem-alpha": "verified",
                "summary:session:2026-06-23:zmem-beta": "mismatch",
            },
        )
        self.assertEqual(record["source_summary_gate_reason"], "unverified-source-summaries")
        self.assertEqual(
            [dependency["gate_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "unverified"],
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["source_child_digests"],
            {
                "memory:turn:201": "sha256:turn-201",
                "memory:turn:202": "sha256:turn-202",
            },
        )
        self.assertEqual(record["source_summary_dependencies"][1]["source_child_count"], 1)
        self.assertEqual(
            [dependency["audit_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "mismatch"],
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["summary_scope_mismatches"],
            ["summary:session:2026-06-23:zmem-beta"],
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["mismatch_reasons"],
            ["source-child-count-mismatch", "content-digest-mismatch"],
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["source_child_digests"],
            {
                "memory:turn:201": "sha256:turn-201",
                "memory:turn:202": "sha256:turn-202",
            },
        )

    def test_recall_plan_ledger_report_blocks_day_candidate_when_session_summary_digests_are_tampered(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            candidate
            for candidate in fixture["candidates"]
            if candidate["candidate_id"] == "candidate:day:2026-06-23:zmem"
        ]

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-27T13:00:00Z",
                completed_at="2026-06-27T13:05:00Z",
            )
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-beta",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:201", "memory:turn:202"],
                created_at="2026-06-27T13:06:00Z",
                completed_at="2026-06-27T13:10:00Z",
            )
            tampered_session_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:session:2026-06-23:zmem-beta",
                "job_id": "consolidation-job:summary:session:2026-06-23:zmem-beta",
                "scope": "project:session:2026-06-23:zmem-beta",
                "summary_level": "session",
                "source_level": "turn",
                "source_child_ids": ["memory:turn:201", "memory:turn:202"],
                "source_child_count": 2,
                "source_child_digests": {
                    "memory:turn:201": "sha256:turn-201",
                },
                "summary_text": "[memory:turn:201] one.\n[memory:turn:202] two.",
                "content_digest": "sha256:tampered-session-digests",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T13:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_session_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_recall_plan_ledger_report(
                fixture,
                planned_at="2026-06-27T13:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        record = report["records"][0]
        self.assertEqual(record["decision"], "skipped")
        self.assertEqual(record["decision_reason"], "source-summaries-not-materialized")
        self.assertEqual(
            record["verified_source_summary_ids"],
            ["summary:session:2026-06-23:zmem-alpha"],
        )
        self.assertEqual(
            record["unverified_source_summary_ids"],
            ["summary:session:2026-06-23:zmem-beta"],
        )
        self.assertEqual(
            record["source_summary_audit_statuses"],
            {
                "summary:session:2026-06-23:zmem-alpha": "verified",
                "summary:session:2026-06-23:zmem-beta": "mismatch",
            },
        )
        self.assertEqual(record["source_summary_gate_reason"], "unverified-source-summaries")
        self.assertEqual(
            [dependency["gate_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "unverified"],
        )

    def test_recall_plan_ledger_report_blocks_day_candidate_when_session_summary_content_digest_is_tampered(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            candidate
            for candidate in fixture["candidates"]
            if candidate["candidate_id"] == "candidate:day:2026-06-23:zmem"
        ]

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-27T13:00:00Z",
                completed_at="2026-06-27T13:05:00Z",
            )
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-beta",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:201", "memory:turn:202"],
                created_at="2026-06-27T13:06:00Z",
                completed_at="2026-06-27T13:10:00Z",
            )
            tampered_content_digest_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:session:2026-06-23:zmem-beta",
                "job_id": "consolidation-job:summary:session:2026-06-23:zmem-beta",
                "scope": "project:session:2026-06-23:zmem-beta",
                "summary_level": "session",
                "source_level": "turn",
                "source_child_ids": ["memory:turn:201", "memory:turn:202"],
                "source_child_count": 2,
                "source_child_digests": {
                    "memory:turn:201": "sha256:47fcb3ec6db8e5c2d985962d787ed1f151987b77af574f0f85afc8f4b5f6c6bc",
                    "memory:turn:202": "sha256:96671d7b3baf501e0e0c5b2a7fda0f456f2b0679b3bb8d5abb8205f8f737e9ac",
                },
                "summary_text": "[memory:turn:201] summary:session:2026-06-23:zmem-beta source 1. [memory:turn:202] summary:session:2026-06-23:zmem-beta source 2.",
                "content_digest": "sha256:tampered-session-content-digest",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T13:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_content_digest_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_recall_plan_ledger_report(
                fixture,
                planned_at="2026-06-27T13:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        record = report["records"][0]
        self.assertEqual(record["decision"], "skipped")
        self.assertEqual(record["decision_reason"], "source-summaries-not-materialized")
        self.assertEqual(record["verified_source_summary_ids"], ["summary:session:2026-06-23:zmem-alpha"])
        self.assertEqual(record["unverified_source_summary_ids"], ["summary:session:2026-06-23:zmem-beta"])
        self.assertEqual(
            record["source_summary_audit_statuses"],
            {
                "summary:session:2026-06-23:zmem-alpha": "verified",
                "summary:session:2026-06-23:zmem-beta": "mismatch",
            },
        )
        self.assertEqual(record["source_summary_gate_reason"], "unverified-source-summaries")
        self.assertEqual(
            [dependency["gate_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "unverified"],
        )
        self.assertEqual(
            [dependency["audit_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "mismatch"],
        )

    def test_recall_plan_ledger_report_blocks_day_candidate_when_session_summary_job_id_is_tampered(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            candidate
            for candidate in fixture["candidates"]
            if candidate["candidate_id"] == "candidate:day:2026-06-23:zmem"
        ]

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-27T13:00:00Z",
                completed_at="2026-06-27T13:05:00Z",
            )
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-beta",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:201", "memory:turn:202"],
                created_at="2026-06-27T13:06:00Z",
                completed_at="2026-06-27T13:10:00Z",
            )
            tampered_job_id_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:session:2026-06-23:zmem-beta",
                "job_id": "consolidation-job:summary:session:2026-06-23:zmem-beta:tampered",
                "scope": "project:session:2026-06-23:zmem-beta",
                "summary_level": "session",
                "source_level": "turn",
                "source_child_ids": ["memory:turn:201", "memory:turn:202"],
                "source_child_count": 2,
                "source_child_digests": {
                    "memory:turn:201": "sha256:47fcb3ec6db8e5c2d985962d787ed1f151987b77af574f0f85afc8f4b5f6c6bc",
                    "memory:turn:202": "sha256:96671d7b3baf501e0e0c5b2a7fda0f456f2b0679b3bb8d5abb8205f8f737e9ac",
                },
                "summary_text": "[memory:turn:201] summary:session:2026-06-23:zmem-beta source 1. [memory:turn:202] summary:session:2026-06-23:zmem-beta source 2.",
                "content_digest": "sha256:f5b05bccf93a2c52cbf98870f4f70c7f8ba1f90d45f03fc1319b557382cf37d1",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T13:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_job_id_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_recall_plan_ledger_report(
                fixture,
                planned_at="2026-06-27T13:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        record = report["records"][0]
        self.assertEqual(record["decision"], "skipped")
        self.assertEqual(record["decision_reason"], "source-summaries-not-materialized")
        self.assertEqual(record["verified_source_summary_ids"], ["summary:session:2026-06-23:zmem-alpha"])
        self.assertEqual(record["unverified_source_summary_ids"], ["summary:session:2026-06-23:zmem-beta"])
        self.assertEqual(
            record["source_summary_audit_statuses"],
            {
                "summary:session:2026-06-23:zmem-alpha": "verified",
                "summary:session:2026-06-23:zmem-beta": "mismatch",
            },
        )
        self.assertEqual(record["source_summary_gate_reason"], "unverified-source-summaries")
        self.assertEqual(
            [dependency["gate_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "unverified"],
        )
        self.assertEqual(
            [dependency["audit_status"] for dependency in record["source_summary_dependencies"]],
            ["verified", "mismatch"],
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["job_id"],
            "consolidation-job:summary:session:2026-06-23:zmem-beta",
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["materialized_job_id"],
            "consolidation-job:summary:session:2026-06-23:zmem-beta:tampered",
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["source_child_ids"],
            ["memory:turn:201", "memory:turn:202"],
        )

    def test_recall_plan_ledger_report_blocks_day_candidate_when_session_summary_created_before_completed_job(self):
        fixture = consolidation_recall_planner_fixture()
        fixture["candidates"] = [
            candidate
            for candidate in fixture["candidates"]
            if candidate["candidate_id"] == "candidate:day:2026-06-23:zmem"
        ]

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-27T13:00:00Z",
                completed_at="2026-06-27T13:05:00Z",
            )
            self._append_materialized_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:session:2026-06-23:zmem-beta",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:201", "memory:turn:202"],
                created_at="2026-06-27T13:06:00Z",
                completed_at="2026-06-27T13:10:00Z",
            )
            tampered_created_at_summary = dict(
                latest_consolidation_summaries(summary_ledger_path)["summary:session:2026-06-23:zmem-beta"]
            )
            tampered_created_at_summary["created_at"] = "2026-06-27T13:09:59Z"
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_created_at_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_recall_plan_ledger_report(
                fixture,
                planned_at="2026-06-27T13:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["queued_job_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        record = report["records"][0]
        self.assertEqual(record["decision"], "skipped")
        self.assertEqual(record["decision_reason"], "source-summaries-not-materialized")
        self.assertEqual(record["verified_source_summary_ids"], ["summary:session:2026-06-23:zmem-alpha"])
        self.assertEqual(record["unverified_source_summary_ids"], ["summary:session:2026-06-23:zmem-beta"])
        self.assertEqual(
            record["source_summary_audit_statuses"],
            {
                "summary:session:2026-06-23:zmem-alpha": "verified",
                "summary:session:2026-06-23:zmem-beta": "mismatch",
            },
        )
        self.assertEqual(record["source_summary_gate_reason"], "unverified-source-summaries")
        self.assertEqual(
            record["source_summary_dependencies"][1]["mismatch_reasons"],
            ["created-at-before-job-completed"],
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["materialized_created_at"],
            "2026-06-27T13:09:59Z",
        )
        self.assertEqual(
            record["source_summary_dependencies"][1]["job_completed_at"],
            "2026-06-27T13:10:00Z",
        )

    def test_profile_aggregation_report_groups_scattered_week_facts_into_ready_profile_candidates(self):
        fixture = consolidation_profile_aggregation_fixture()

        report = consolidation_profile_aggregation_report(fixture)

        self.assertEqual(report["schema"], CONSOLIDATION_PROFILE_AGGREGATION_REPORT_SCHEMA)
        self.assertEqual(report["record_count"], 3)
        self.assertEqual(report["ready_candidate_count"], 2)
        self.assertEqual(report["skipped_candidate_count"], 1)
        self.assertEqual(
            [candidate["candidate_id"] for candidate in report["ready_candidates"]],
            [
                "candidate:profile-project:person:mallory",
                "candidate:profile-project:project:zmem",
            ],
        )
        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        mallory = record_by_subject["person:mallory"]
        self.assertEqual(mallory["decision_reason"], "ready")
        self.assertEqual(
            mallory["source_summary_ids"],
            ["summary:week:2026-w25:zmem", "summary:week:2026-w26:zmem"],
        )
        self.assertEqual(mallory["facet_ids"], ["deploy-owner", "rollback-contact"])
        self.assertEqual(mallory["claim_count"], 3)
        self.assertEqual(mallory["candidate"]["summary_level"], "profile_project")
        self.assertEqual(mallory["candidate"]["source_level"], "week")
        self.assertEqual(
            mallory["candidate"]["source_child_ids"],
            ["summary:week:2026-w25:zmem", "summary:week:2026-w26:zmem"],
        )
        project = record_by_subject["project:zmem"]
        self.assertEqual(project["decision_reason"], "ready")
        self.assertEqual(project["facet_ids"], ["benchmark-status", "proof-wedge"])
        self.assertEqual(project["source_summary_count"], 2)
        self.assertEqual(project["candidate"]["trigger"]["kind"], "profile-fact-aggregation")
        self.assertTrue(project["candidate"]["trigger"]["has_open_recall_gap"])

    def test_profile_aggregation_report_marks_closed_gap_or_thin_support_subjects_as_skipped(self):
        fixture = consolidation_profile_aggregation_fixture()
        for target in fixture["targets"]:
            if target["subject_id"] == "project:zmem":
                target["has_open_recall_gap"] = False

        report = consolidation_profile_aggregation_report(fixture)

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(report["ready_candidate_count"], 1)
        self.assertEqual(record_by_subject["project:zmem"]["decision_reason"], "no-open-recall-gap")
        self.assertIsNone(record_by_subject["project:zmem"]["candidate"])
        self.assertEqual(
            record_by_subject["person:ada"]["decision_reason"],
            "insufficient-source-summaries",
        )
        self.assertIsNone(record_by_subject["person:ada"]["candidate"])

    def test_ready_profile_aggregation_candidates_merge_into_recall_planner_and_queue(self):
        planner_fixture = consolidation_recall_planner_fixture()
        aggregation_report = consolidation_profile_aggregation_report(consolidation_profile_aggregation_fixture())

        merged_fixture = merge_profile_aggregation_candidates_into_recall_planner(
            planner_fixture,
            aggregation_report,
        )
        planned_jobs = plan_consolidation_jobs(
            merged_fixture,
            planned_at="2026-06-27T09:10:00Z",
        )
        report = consolidation_recall_plan_report(
            merged_fixture,
            planned_at="2026-06-27T09:10:00Z",
        )

        self.assertEqual(len(merged_fixture["candidates"]), 6)
        self.assertEqual(
            [job.job_id for job in planned_jobs],
            [
                "consolidation-job:planned:candidate:session:2026-06-23:zmem-alpha",
                "consolidation-job:planned:candidate:day:2026-06-23:zmem",
                "consolidation-job:planned:candidate:profile-project:person:mallory",
                "consolidation-job:planned:candidate:profile-project:project:zmem",
            ],
        )
        self.assertEqual(report["candidate_count"], 6)
        self.assertEqual(report["queued_job_count"], 4)
        record_by_candidate_id = {
            record["candidate_id"]: record for record in report["records"]
        }
        self.assertEqual(
            record_by_candidate_id["candidate:profile-project:person:mallory"]["decision_reason"],
            "ready",
        )
        self.assertEqual(
            record_by_candidate_id["candidate:profile-project:project:zmem"]["planned_job_id"],
            "consolidation-job:planned:candidate:profile-project:project:zmem",
        )
        self.assertNotIn("candidate:profile-project:person:ada", record_by_candidate_id)

    def test_profile_aggregation_merge_is_idempotent_for_existing_ready_candidates(self):
        planner_fixture = consolidation_recall_planner_fixture()
        aggregation_report = consolidation_profile_aggregation_report(consolidation_profile_aggregation_fixture())

        merged_once = merge_profile_aggregation_candidates_into_recall_planner(
            planner_fixture,
            aggregation_report,
        )
        merged_twice = merge_profile_aggregation_candidates_into_recall_planner(
            merged_once,
            aggregation_report,
        )

        self.assertEqual(
            [candidate["candidate_id"] for candidate in merged_once["candidates"]],
            [candidate["candidate_id"] for candidate in merged_twice["candidates"]],
        )

    def test_profile_aggregation_planner_report_joins_subjects_to_profile_queue_decisions(self):
        report = consolidation_profile_aggregation_planner_report(
            consolidation_recall_planner_fixture(),
            consolidation_profile_aggregation_fixture(),
            planned_at="2026-06-27T12:30:00Z",
        )

        self.assertEqual(report["schema"], CONSOLIDATION_PROFILE_PLANNER_REPORT_SCHEMA)
        self.assertEqual(report["record_count"], 3)
        self.assertEqual(report["ready_candidate_count"], 2)
        self.assertEqual(report["queued_candidate_count"], 2)
        self.assertEqual(report["blocked_ready_candidate_count"], 0)
        self.assertEqual(report["skipped_candidate_count"], 1)
        self.assertEqual(
            [job["job_id"] for job in report["planned_jobs"]],
            [
                "consolidation-job:planned:candidate:profile-project:person:mallory",
                "consolidation-job:planned:candidate:profile-project:project:zmem",
            ],
        )

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision"], "queued")
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision_reason"], "ready")
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_planned_job_id"],
            "consolidation-job:planned:candidate:profile-project:person:mallory",
        )
        self.assertEqual(record_by_subject["person:ada"]["decision_reason"], "insufficient-source-summaries")
        self.assertEqual(record_by_subject["person:ada"]["planner_decision"], "not-applicable")
        self.assertEqual(record_by_subject["person:ada"]["planner_decision_reason"], "aggregation-not-ready")
        self.assertIsNone(record_by_subject["person:ada"]["planner_latest_matching_job"])

    def test_profile_aggregation_planner_report_surfaces_existing_job_state_for_ready_subjects(self):
        existing_jobs = [
            transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/profile-project/person:mallory",
                    summary_level="profile_project",
                    source_level="week",
                    source_child_ids=[
                        "summary:week:2026-w25:zmem",
                        "summary:week:2026-w26:zmem",
                    ],
                    created_at="2026-06-27T12:00:00Z",
                    job_id="consolidation-job:running-profile-person",
                ),
                status="running",
                updated_at="2026-06-27T12:05:00Z",
            ),
            transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/profile-project/project:zmem",
                    summary_level="profile_project",
                    source_level="week",
                    source_child_ids=[
                        "summary:week:2026-w25:zmem",
                        "summary:week:2026-w26:zmem",
                    ],
                    created_at="2026-06-27T12:00:00Z",
                    job_id="consolidation-job:failed-profile-project",
                ),
                status="failed",
                updated_at="2026-06-27T12:06:00Z",
                error="local summary write deferred",
            ),
        ]

        report = consolidation_profile_aggregation_planner_report(
            consolidation_recall_planner_fixture(),
            consolidation_profile_aggregation_fixture(),
            planned_at="2026-06-27T12:30:00Z",
            existing_jobs=existing_jobs,
        )

        self.assertEqual(report["queued_candidate_count"], 1)
        self.assertEqual(report["blocked_ready_candidate_count"], 1)
        self.assertEqual(
            [job["job_id"] for job in report["planned_jobs"]],
            ["consolidation-job:planned:candidate:profile-project:project:zmem"],
        )

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "existing-running-job",
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_latest_matching_job"]["job_id"],
            "consolidation-job:running-profile-person",
        )
        self.assertEqual(record_by_subject["project:zmem"]["planner_decision"], "queued")
        self.assertEqual(
            record_by_subject["project:zmem"]["planner_decision_reason"],
            "retry-after-failed-job",
        )
        self.assertTrue(record_by_subject["project:zmem"]["planner_retrying_terminal_job"])

    def test_profile_aggregation_planner_ledger_report_blocks_ready_subjects_until_week_summaries_materialize(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["schema"], CONSOLIDATION_PROFILE_PLANNER_LEDGER_REPORT_SCHEMA)
        self.assertEqual(report["job_history_count"], 2)
        self.assertEqual(report["materialized_summary_count"], 1)
        self.assertEqual(report["queued_candidate_count"], 0)
        self.assertEqual(report["blocked_ready_candidate_count"], 2)

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(
            record_by_subject["person:mallory"]["materialized_source_summary_ids"],
            ["summary:week:2026-w25:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["missing_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )
        dependencies = record_by_subject["person:mallory"]["source_summary_dependencies"]
        self.assertEqual(len(dependencies), 2)
        self.assertEqual(
            dependencies[0],
            {
                "summary_id": "summary:week:2026-w25:zmem",
                "materialized": True,
                "gate_status": "verified",
                "audit_status": "verified",
                "job_id": "consolidation-job:summary:week:2026-w25:zmem",
                "job_status": "completed",
                "job_completed_at": "2026-06-27T12:05:00Z",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:week:2026-w25:zmem:child:one",
                    "summary:week:2026-w25:zmem:child:two",
                ],
                "source_child_count": 2,
                "non_blocking": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "reversible": True,
                "expected_output_summary_ids": ["summary:week:2026-w25:zmem"],
                "materialized_summary_ids": ["summary:week:2026-w25:zmem"],
                "missing_output_summary_ids": [],
                "unexpected_output_summary_ids": [],
                "materialized_job_id": "consolidation-job:summary:week:2026-w25:zmem",
                "materialized_created_at": "2026-06-27T12:05:00Z",
                "source_child_digests": dependencies[0]["source_child_digests"],
                "content_digest": dependencies[0]["content_digest"],
            },
        )
        self.assertEqual(
            sorted(dependencies[0]["source_child_digests"]),
            [
                "summary:week:2026-w25:zmem:child:one",
                "summary:week:2026-w25:zmem:child:two",
            ],
        )
        self.assertTrue(dependencies[0]["content_digest"].startswith("sha256:"))
        self.assertEqual(
            dependencies[1],
            {
                "summary_id": "summary:week:2026-w26:zmem",
                "materialized": False,
                "gate_status": "missing",
                "audit_status": "missing",
                "job_id": None,
                "job_status": None,
                "job_completed_at": None,
                "summary_level": None,
                "source_level": None,
                "source_child_ids": [],
                "source_child_count": 0,
                "non_blocking": None,
                "lineage_kind": None,
                "reversible": None,
                "expected_output_summary_ids": [],
                "materialized_summary_ids": [],
                "missing_output_summary_ids": [],
                "unexpected_output_summary_ids": [],
                "content_digest": None,
            },
        )
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "source-summaries-not-materialized",
        )
        self.assertEqual(record_by_subject["project:zmem"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["project:zmem"]["missing_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )
        self.assertEqual(record_by_subject["person:ada"]["planner_decision"], "not-applicable")

    def test_profile_aggregation_planner_ledger_report_surfaces_missing_completed_week_summary_job_contract(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )
            pending = create_consolidation_job(
                scope="project:week:2026-w26:zmem",
                summary_level="week",
                source_level="day",
                source_child_ids=[
                    "summary:week:2026-w26:zmem:child:one",
                    "summary:week:2026-w26:zmem:child:two",
                ],
                created_at="2026-06-27T12:06:00Z",
                job_id="consolidation-job:summary:week:2026-w26:zmem",
            )
            completed, _ = materialize_consolidation_summary(
                pending,
                completed_at="2026-06-27T12:10:00Z",
                summary_id="summary:week:2026-w26:zmem",
                source_children=[
                    {"child_id": "summary:week:2026-w26:zmem:child:one", "content": "week 26 child one."},
                    {"child_id": "summary:week:2026-w26:zmem:child:two", "content": "week 26 child two."},
                ],
            )
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["schema"], CONSOLIDATION_PROFILE_PLANNER_LEDGER_REPORT_SCHEMA)
        self.assertEqual(report["job_history_count"], 4)
        self.assertEqual(report["materialized_summary_count"], 1)
        self.assertEqual(report["queued_candidate_count"], 0)
        self.assertEqual(report["blocked_ready_candidate_count"], 2)

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(
            record_by_subject["person:mallory"]["missing_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )
        dependencies = record_by_subject["person:mallory"]["source_summary_dependencies"]
        self.assertEqual(len(dependencies), 2)
        self.assertEqual(
            dependencies[1],
            {
                "summary_id": "summary:week:2026-w26:zmem",
                "materialized": False,
                "gate_status": "missing",
                "audit_status": "missing-summary",
                "job_id": "consolidation-job:summary:week:2026-w26:zmem",
                "job_status": "completed",
                "job_completed_at": "2026-06-27T12:10:00Z",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:week:2026-w26:zmem:child:one",
                    "summary:week:2026-w26:zmem:child:two",
                ],
                "source_child_count": 2,
                "non_blocking": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "reversible": True,
                "expected_output_summary_ids": ["summary:week:2026-w26:zmem"],
                "materialized_summary_ids": [],
                "missing_output_summary_ids": ["summary:week:2026-w26:zmem"],
                "unexpected_output_summary_ids": [],
                "content_digest": None,
            },
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "source-summaries-not-materialized",
        )

    def test_profile_aggregation_planner_ledger_report_blocks_unverified_week_summaries(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w26:zmem",
                created_at="2026-06-27T12:06:00Z",
                completed_at="2026-06-27T12:10:00Z",
            )
            tampered_week_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:week:2026-w26:zmem",
                "job_id": "consolidation-job:summary:week:2026-w26:zmem",
                "scope": "project:week:2026-w26:zmem",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": ["summary:week:2026-w26:zmem:child:one"],
                "source_child_count": 1,
                "source_child_digests": {"summary:week:2026-w26:zmem:child:one": "sha256:tampered"},
                "summary_text": "[summary:week:2026-w26:zmem:child:one] tampered week rollup.",
                "content_digest": "sha256:tampered-week",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T12:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_week_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["schema"], CONSOLIDATION_PROFILE_PLANNER_LEDGER_REPORT_SCHEMA)
        self.assertEqual(report["job_history_count"], 4)
        self.assertEqual(report["materialized_summary_count"], 2)
        self.assertEqual(report["queued_candidate_count"], 0)
        self.assertEqual(report["blocked_ready_candidate_count"], 2)

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(
            record_by_subject["person:mallory"]["materialized_source_summary_ids"],
            ["summary:week:2026-w25:zmem", "summary:week:2026-w26:zmem"],
        )
        self.assertEqual(record_by_subject["person:mallory"]["missing_source_summary_ids"], [])
        self.assertEqual(
            record_by_subject["person:mallory"]["verified_source_summary_ids"],
            ["summary:week:2026-w25:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["unverified_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_audit_statuses"],
            {
                "summary:week:2026-w25:zmem": "verified",
                "summary:week:2026-w26:zmem": "mismatch",
            },
        )
        dependencies = record_by_subject["person:mallory"]["source_summary_dependencies"]
        self.assertEqual(len(dependencies), 2)
        self.assertEqual(
            dependencies[0],
            {
                "summary_id": "summary:week:2026-w25:zmem",
                "materialized": True,
                "gate_status": "verified",
                "audit_status": "verified",
                "job_id": "consolidation-job:summary:week:2026-w25:zmem",
                "job_status": "completed",
                "job_completed_at": "2026-06-27T12:05:00Z",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:week:2026-w25:zmem:child:one",
                    "summary:week:2026-w25:zmem:child:two",
                ],
                "source_child_count": 2,
                "non_blocking": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "reversible": True,
                "expected_output_summary_ids": ["summary:week:2026-w25:zmem"],
                "materialized_summary_ids": ["summary:week:2026-w25:zmem"],
                "missing_output_summary_ids": [],
                "unexpected_output_summary_ids": [],
                "materialized_job_id": "consolidation-job:summary:week:2026-w25:zmem",
                "materialized_created_at": "2026-06-27T12:05:00Z",
                "source_child_digests": dependencies[0]["source_child_digests"],
                "content_digest": dependencies[0]["content_digest"],
            },
        )
        self.assertEqual(
            sorted(dependencies[0]["source_child_digests"]),
            [
                "summary:week:2026-w25:zmem:child:one",
                "summary:week:2026-w25:zmem:child:two",
            ],
        )
        self.assertTrue(dependencies[0]["content_digest"].startswith("sha256:"))
        self.assertEqual(
            dependencies[1],
            {
                "summary_id": "summary:week:2026-w26:zmem",
                "materialized": True,
                "gate_status": "unverified",
                "audit_status": "mismatch",
                "job_id": "consolidation-job:summary:week:2026-w26:zmem",
                "job_status": "completed",
                "job_completed_at": "2026-06-27T12:10:00Z",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": ["summary:week:2026-w26:zmem:child:one"],
                "source_child_count": 1,
                "non_blocking": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "reversible": True,
                "expected_output_summary_ids": ["summary:week:2026-w26:zmem"],
                "materialized_summary_ids": ["summary:week:2026-w26:zmem"],
                "missing_output_summary_ids": [],
                "unexpected_output_summary_ids": [],
                "materialized_job_id": "consolidation-job:summary:week:2026-w26:zmem",
                "materialized_created_at": "2026-06-27T12:10:00Z",
                "source_child_digests": {"summary:week:2026-w26:zmem:child:one": "sha256:tampered"},
                "content_digest": "sha256:tampered-week",
                "mismatch_reasons": [
                    "source-child-ids-mismatch",
                    "source-child-count-mismatch",
                    "source-child-digests-mismatch",
                    "content-digest-mismatch",
                ],
                "summary_scope_mismatches": ["summary:week:2026-w26:zmem"],
            },
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_gate_reason"],
            "unverified-source-summaries",
        )
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "source-summaries-not-materialized",
        )
        self.assertEqual(record_by_subject["project:zmem"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["project:zmem"]["unverified_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )

    def test_profile_aggregation_planner_ledger_report_blocks_irreversible_week_summaries(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w26:zmem",
                created_at="2026-06-27T12:06:00Z",
                completed_at="2026-06-27T12:10:00Z",
            )
            irreversible_week_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:week:2026-w26:zmem",
                "job_id": "consolidation-job:summary:week:2026-w26:zmem",
                "scope": "project:week:2026-w26:zmem",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:week:2026-w26:zmem:child:one",
                    "summary:week:2026-w26:zmem:child:two",
                ],
                "source_child_count": 2,
                "source_child_digests": {
                    "summary:week:2026-w26:zmem:child:one": "sha256:week26-child-one",
                    "summary:week:2026-w26:zmem:child:two": "sha256:week26-child-two",
                },
                "summary_text": (
                    "[summary:week:2026-w26:zmem:child:one] week 26 child one.\n"
                    "[summary:week:2026-w26:zmem:child:two] week 26 child two."
                ),
                "content_digest": "sha256:week26-irrev",
                "non_blocking": True,
                "reversible": False,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T12:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(irreversible_week_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(
            record_by_subject["person:mallory"]["verified_source_summary_ids"],
            ["summary:week:2026-w25:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["unverified_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_audit_statuses"],
            {
                "summary:week:2026-w25:zmem": "verified",
                "summary:week:2026-w26:zmem": "mismatch",
            },
        )
        dependencies = record_by_subject["person:mallory"]["source_summary_dependencies"]
        self.assertEqual(dependencies[1]["gate_status"], "unverified")
        self.assertEqual(dependencies[1]["audit_status"], "mismatch")
        self.assertFalse(dependencies[1]["reversible"])
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_gate_reason"],
            "unverified-source-summaries",
        )
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "source-summaries-not-materialized",
        )

    def test_profile_aggregation_planner_ledger_report_blocks_blocking_week_summaries(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w26:zmem",
                created_at="2026-06-27T12:06:00Z",
                completed_at="2026-06-27T12:10:00Z",
            )
            blocking_week_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:week:2026-w26:zmem",
                "job_id": "consolidation-job:summary:week:2026-w26:zmem",
                "scope": "project:week:2026-w26:zmem",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:week:2026-w26:zmem:child:one",
                    "summary:week:2026-w26:zmem:child:two",
                ],
                "source_child_count": 2,
                "source_child_digests": {
                    "summary:week:2026-w26:zmem:child:one": "sha256:week26-child-one",
                    "summary:week:2026-w26:zmem:child:two": "sha256:week26-child-two",
                },
                "summary_text": (
                    "[summary:week:2026-w26:zmem:child:one] week 26 child one.\n"
                    "[summary:week:2026-w26:zmem:child:two] week 26 child two."
                ),
                "content_digest": "sha256:week26-blocking",
                "non_blocking": False,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "blocking-override", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-27T12:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(blocking_week_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(
            record_by_subject["person:mallory"]["verified_source_summary_ids"],
            ["summary:week:2026-w25:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["unverified_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_audit_statuses"],
            {
                "summary:week:2026-w25:zmem": "verified",
                "summary:week:2026-w26:zmem": "mismatch",
            },
        )
        dependencies = record_by_subject["person:mallory"]["source_summary_dependencies"]
        self.assertEqual(dependencies[1]["gate_status"], "unverified")
        self.assertEqual(dependencies[1]["audit_status"], "mismatch")
        self.assertFalse(dependencies[1]["non_blocking"])
        self.assertEqual(
            dependencies[1]["content_digest"],
            "sha256:week26-blocking",
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_gate_reason"],
            "unverified-source-summaries",
        )
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "source-summaries-not-materialized",
        )

    def test_profile_aggregation_planner_ledger_report_blocks_hosted_llm_week_summaries(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w26:zmem",
                created_at="2026-06-27T12:06:00Z",
                completed_at="2026-06-27T12:10:00Z",
            )
            hosted_week_summary = {
                "schema": CONSOLIDATION_SUMMARY_SCHEMA,
                "summary_id": "summary:week:2026-w26:zmem",
                "job_id": "consolidation-job:summary:week:2026-w26:zmem",
                "scope": "project:week:2026-w26:zmem",
                "summary_level": "week",
                "source_level": "day",
                "source_child_ids": [
                    "summary:week:2026-w26:zmem:child:one",
                    "summary:week:2026-w26:zmem:child:two",
                ],
                "source_child_count": 2,
                "source_child_digests": {
                    "summary:week:2026-w26:zmem:child:one": "sha256:week26-child-one",
                    "summary:week:2026-w26:zmem:child:two": "sha256:week26-child-two",
                },
                "summary_text": (
                    "[summary:week:2026-w26:zmem:child:one] week 26 child one.\n"
                    "[summary:week:2026-w26:zmem:child:two] week 26 child two."
                ),
                "content_digest": "sha256:week26-hosted",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "summarizer": {"kind": "hosted-override", "hosted_llm": True, "model_id": "hosted/v1"},
                "created_at": "2026-06-27T12:10:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(hosted_week_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(
            record_by_subject["person:mallory"]["verified_source_summary_ids"],
            ["summary:week:2026-w25:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["unverified_source_summary_ids"],
            ["summary:week:2026-w26:zmem"],
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_audit_statuses"],
            {
                "summary:week:2026-w25:zmem": "verified",
                "summary:week:2026-w26:zmem": "mismatch",
            },
        )
        dependencies = record_by_subject["person:mallory"]["source_summary_dependencies"]
        self.assertEqual(dependencies[1]["gate_status"], "unverified")
        self.assertEqual(dependencies[1]["audit_status"], "mismatch")
        self.assertEqual(
            dependencies[1]["content_digest"],
            "sha256:week26-hosted",
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["source_summary_gate_reason"],
            "unverified-source-summaries",
        )
        self.assertEqual(record_by_subject["person:mallory"]["planner_decision"], "skipped")
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "source-summaries-not-materialized",
        )

    def test_profile_aggregation_planner_ledger_report_surfaces_week_summary_timestamp_audit_fields(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w26:zmem",
                created_at="2026-06-27T12:06:00Z",
                completed_at="2026-06-27T12:10:00Z",
            )
            tampered_created_at_summary = dict(
                latest_consolidation_summaries(summary_ledger_path)["summary:week:2026-w26:zmem"]
            )
            tampered_created_at_summary["created_at"] = "2026-06-27T12:09:59Z"
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_created_at_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        dependencies = {
            record["subject_id"]: record["source_summary_dependencies"] for record in report["records"]
        }["person:mallory"]
        self.assertEqual(dependencies[1]["audit_status"], "mismatch")
        self.assertEqual(
            dependencies[1]["mismatch_reasons"],
            ["created-at-before-job-completed"],
        )
        self.assertEqual(
            dependencies[1]["materialized_created_at"],
            "2026-06-27T12:09:59Z",
        )
        self.assertEqual(
            dependencies[1]["job_completed_at"],
            "2026-06-27T12:10:00Z",
        )

    def test_profile_aggregation_planner_ledger_report_loads_job_history_and_retries_terminal_jobs(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w25:zmem",
                created_at="2026-06-27T12:00:00Z",
                completed_at="2026-06-27T12:05:00Z",
            )
            self._append_materialized_week_summary(
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
                summary_id="summary:week:2026-w26:zmem",
                created_at="2026-06-27T12:06:00Z",
                completed_at="2026-06-27T12:10:00Z",
            )

            running_job = transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/profile-project/person:mallory",
                    summary_level="profile_project",
                    source_level="week",
                    source_child_ids=[
                        "summary:week:2026-w25:zmem",
                        "summary:week:2026-w26:zmem",
                    ],
                    created_at="2026-06-27T12:11:00Z",
                    job_id="consolidation-job:running-profile-person",
                ),
                status="running",
                updated_at="2026-06-27T12:12:00Z",
            )
            failed_job = transition_consolidation_job(
                create_consolidation_job(
                    scope="project:zmem/profile-project/project:zmem",
                    summary_level="profile_project",
                    source_level="week",
                    source_child_ids=[
                        "summary:week:2026-w25:zmem",
                        "summary:week:2026-w26:zmem",
                    ],
                    created_at="2026-06-27T12:13:00Z",
                    job_id="consolidation-job:failed-profile-project",
                ),
                status="failed",
                updated_at="2026-06-27T12:14:00Z",
                error="local summary write deferred",
            )
            append_consolidation_job_record(job_ledger_path, running_job)
            append_consolidation_job_record(job_ledger_path, failed_job)

            report = consolidation_profile_aggregation_planner_ledger_report(
                consolidation_recall_planner_fixture(),
                consolidation_profile_aggregation_fixture(),
                planned_at="2026-06-27T12:30:00Z",
                job_ledger_path=job_ledger_path,
                summary_ledger_path=summary_ledger_path,
            )

        self.assertEqual(report["schema"], CONSOLIDATION_PROFILE_PLANNER_LEDGER_REPORT_SCHEMA)
        self.assertEqual(report["job_history_count"], 6)
        self.assertEqual(report["materialized_summary_count"], 2)
        self.assertEqual(report["queued_candidate_count"], 1)
        self.assertEqual(report["blocked_ready_candidate_count"], 1)
        self.assertEqual(
            [job["job_id"] for job in report["planned_jobs"]],
            ["consolidation-job:planned:candidate:profile-project:project:zmem"],
        )

        record_by_subject = {record["subject_id"]: record for record in report["records"]}
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_latest_matching_job"]["job_id"],
            "consolidation-job:running-profile-person",
        )
        self.assertEqual(
            record_by_subject["person:mallory"]["planner_decision_reason"],
            "existing-running-job",
        )
        self.assertEqual(
            record_by_subject["project:zmem"]["planner_latest_matching_job"]["job_id"],
            "consolidation-job:failed-profile-project",
        )
        self.assertEqual(record_by_subject["project:zmem"]["planner_decision"], "queued")
        self.assertTrue(record_by_subject["project:zmem"]["planner_retrying_terminal_job"])

    def test_materialize_consolidation_summary_completes_job_with_reversible_summary_payload(self):
        pending = create_consolidation_job(
            scope="project:zmem/session:alpha",
            summary_level="session",
            source_level="turn",
            source_child_ids=["memory:turn:101", "memory:turn:102", "memory:turn:103"],
            created_at="2026-06-23T04:00:00Z",
            job_id="consolidation-job:materialize",
        )

        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-23T04:05:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada confirmed the deploy checklist owner."},
                {"child_id": "memory:turn:102", "content": "Ben captured the rollback contact."},
                {"child_id": "memory:turn:103", "content": "Cara flagged a recall gap for weekly cleanup."},
            ],
        )

        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.output_summary_ids, (summary["summary_id"],))
        self.assertEqual(summary["schema"], CONSOLIDATION_SUMMARY_SCHEMA)
        self.assertEqual(summary["job_id"], "consolidation-job:materialize")
        self.assertEqual(
            summary["source_child_ids"],
            ["memory:turn:101", "memory:turn:102", "memory:turn:103"],
        )
        self.assertEqual(summary["source_child_count"], 3)
        self.assertEqual(summary["lineage_kind"], CONSOLIDATION_LINEAGE_KIND)
        self.assertTrue(summary["reversible"])
        self.assertTrue(summary["non_blocking"])
        self.assertFalse(summary["summarizer"]["hosted_llm"])
        self.assertTrue(summary["summary_id"].startswith("summary:session:"))
        self.assertIn("[memory:turn:101] Ada confirmed the deploy checklist owner.", summary["summary_text"])
        self.assertIn("[memory:turn:103] Cara flagged a recall gap for weekly cleanup.", summary["summary_text"])
        self.assertEqual(
            sorted(summary["source_child_digests"]),
            ["memory:turn:101", "memory:turn:102", "memory:turn:103"],
        )
        self.assertTrue(summary["content_digest"].startswith("sha256:"))

    def test_materialize_consolidation_summary_rejects_source_child_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-23",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-23T04:00:00Z",
            job_id="consolidation-job:mismatch",
        )

        with self.assertRaisesRegex(ValueError, "source_child_ids order"):
            materialize_consolidation_summary(
                pending,
                completed_at="2026-06-23T04:05:00Z",
                source_children=[
                    {"child_id": "summary:session:beta", "content": "Beta session summary."},
                    {"child_id": "summary:session:alpha", "content": "Alpha session summary."},
                ],
            )

    def test_summary_records_persist_in_append_only_local_ledger(self):
        pending = create_consolidation_job(
            scope="project:zmem/session:alpha",
            summary_level="session",
            source_level="turn",
            source_child_ids=["memory:turn:101", "memory:turn:102"],
            created_at="2026-06-23T05:00:00Z",
            job_id="consolidation-job:summary-ledger",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-23T05:04:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, completed, summary)

            records = load_consolidation_summary_records(ledger_path)
            latest = latest_consolidation_summaries(ledger_path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["schema"], CONSOLIDATION_SUMMARY_SCHEMA)
        self.assertEqual(records[0]["job_id"], completed.job_id)
        self.assertEqual(records[0]["summary_id"], summary["summary_id"])
        self.assertEqual(records[0]["source_child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(latest[summary["summary_id"]]["content_digest"], summary["content_digest"])

    def test_summary_ledger_rejects_mismatch_with_completed_job_output_ids(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-23",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-23T05:00:00Z",
            job_id="consolidation-job:summary-ledger-mismatch",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-23T05:06:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        mismatched_summary = dict(summary)
        mismatched_summary["summary_id"] = "summary:day:mismatch"

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            with self.assertRaisesRegex(ValueError, "output_summary_ids"):
                append_consolidation_summary_record(ledger_path, completed, mismatched_summary)

    def test_consolidation_audit_report_verifies_completed_job_summary_lineage(self):
        pending = create_consolidation_job(
            scope="project:zmem/session:alpha",
            summary_level="session",
            source_level="turn",
            source_child_ids=["memory:turn:101", "memory:turn:102"],
            created_at="2026-06-24T01:00:00Z",
            job_id="consolidation-job:audit-ok",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:04:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            append_consolidation_summary_record(summary_ledger_path, completed, summary)

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["schema"], CONSOLIDATION_AUDIT_REPORT_SCHEMA)
        self.assertEqual(report["job_count"], 1)
        self.assertEqual(report["completed_job_count"], 1)
        self.assertEqual(report["verified_record_count"], 1)
        self.assertEqual(report["incomplete_record_count"], 0)
        self.assertEqual(report["records"][0]["schema"], CONSOLIDATION_AUDIT_RECORD_SCHEMA)
        self.assertEqual(report["records"][0]["audit_status"], "verified")
        self.assertEqual(report["records"][0]["job_id"], completed.job_id)
        self.assertEqual(report["records"][0]["expected_output_summary_ids"], [summary["summary_id"]])
        self.assertEqual(report["records"][0]["materialized_summary_ids"], [summary["summary_id"]])
        self.assertEqual(report["records"][0]["missing_output_summary_ids"], [])
        self.assertEqual(report["records"][0]["unexpected_output_summary_ids"], [])
        self.assertEqual(report["records"][0]["summaries"][0]["job_id"], completed.job_id)
        self.assertEqual(report["records"][0]["summaries"][0]["content_digest"], summary["content_digest"])

    def test_consolidation_audit_report_marks_missing_completed_summary_outputs(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-missing",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["schema"], CONSOLIDATION_AUDIT_REPORT_SCHEMA)
        self.assertEqual(report["verified_record_count"], 0)
        self.assertEqual(report["incomplete_record_count"], 1)
        self.assertEqual(report["records"][0]["audit_status"], "missing-summary")
        self.assertEqual(report["records"][0]["expected_output_summary_ids"], [summary["summary_id"]])
        self.assertEqual(report["records"][0]["materialized_summary_ids"], [])
        self.assertEqual(report["records"][0]["missing_output_summary_ids"], [summary["summary_id"]])
        self.assertEqual(report["records"][0]["unexpected_output_summary_ids"], [])
        self.assertEqual(report["records"][0]["summaries"], [])

    def test_consolidation_audit_report_marks_irreversible_materialized_summary_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-irreversible",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        irreversible_summary = dict(summary)
        irreversible_summary["reversible"] = False

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(irreversible_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])
        self.assertEqual(
            report["records"][0]["summary_mismatch_reasons"],
            {
                summary["summary_id"]: ["reversible-required"],
            },
        )

    def test_consolidation_audit_report_marks_hosted_llm_materialized_summary_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-hosted-llm",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        hosted_summary = dict(summary)
        hosted_summary["summarizer"] = {"kind": "hosted-override", "hosted_llm": True, "model_id": "hosted/v1"}

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(hosted_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])
        self.assertEqual(
            report["records"][0]["summary_mismatch_reasons"],
            {
                summary["summary_id"]: ["hosted-llm-disallowed"],
            },
        )

    def test_consolidation_audit_report_marks_blocking_materialized_summary_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-blocking",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        blocking_summary = dict(summary)
        blocking_summary["non_blocking"] = False

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(blocking_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])
        self.assertEqual(
            report["records"][0]["summary_mismatch_reasons"],
            {
                summary["summary_id"]: ["non-blocking-required"],
            },
        )

    def test_consolidation_audit_report_marks_miscounted_materialized_summary_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-miscounted",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        miscounted_summary = dict(summary)
        miscounted_summary["source_child_count"] = 1

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(miscounted_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])

    def test_consolidation_audit_report_marks_materialized_summary_with_tampered_digests_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-tampered-digests",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        tampered_digests_summary = dict(summary)
        tampered_digests_summary["source_child_digests"] = {
            "summary:session:alpha": summary["source_child_digests"]["summary:session:alpha"],
        }

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_digests_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])

    def test_consolidation_audit_report_marks_materialized_summary_with_tampered_content_digest_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-tampered-content-digest",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        tampered_content_digest_summary = dict(summary)
        tampered_content_digest_summary["content_digest"] = "sha256:tampered-content-digest"

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_content_digest_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])

    def test_consolidation_audit_report_marks_materialized_summary_with_tampered_job_id_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-tampered-job-id",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        tampered_job_id_summary = dict(summary)
        tampered_job_id_summary["job_id"] = "consolidation-job:audit-tampered-job-id:wrong"

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_job_id_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])
        self.assertEqual(
            report["records"][0]["summary_mismatch_reasons"],
            {
                summary["summary_id"]: ["job-id-mismatch"],
            },
        )
        self.assertEqual(
            report["records"][0]["summaries"][0]["job_id"],
            "consolidation-job:audit-tampered-job-id:wrong",
        )

    def test_consolidation_audit_report_marks_materialized_summary_created_before_completed_job_as_mismatch(self):
        pending = create_consolidation_job(
            scope="project:zmem/day:2026-06-24",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-24T01:10:00Z",
            job_id="consolidation-job:audit-created-before-completed",
        )
        completed, summary = materialize_consolidation_summary(
            pending,
            completed_at="2026-06-24T01:12:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )
        tampered_created_at_summary = dict(summary)
        tampered_created_at_summary["created_at"] = "2026-06-24T01:11:59Z"

        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "consolidation-jobs.jsonl"
            summary_ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_job_record(job_ledger_path, pending)
            append_consolidation_job_record(job_ledger_path, completed)
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_created_at_summary, sort_keys=True))
                handle.write("\n")

            report = consolidation_audit_report(job_ledger_path, summary_ledger_path)

        self.assertEqual(report["records"][0]["audit_status"], "mismatch")
        self.assertEqual(report["records"][0]["summary_scope_mismatches"], [summary["summary_id"]])
        self.assertEqual(
            report["records"][0]["summary_mismatch_reasons"],
            {
                summary["summary_id"]: ["created-at-before-job-completed"],
            },
        )
        self.assertEqual(report["records"][0]["completed_at"], "2026-06-24T01:12:00Z")

    def test_consolidation_summary_lineage_report_expands_nested_summary_children(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T02:00:00Z",
                job_id="consolidation-job:lineage-session-alpha",
            ),
            completed_at="2026-06-24T02:05:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        session_beta, session_beta_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:beta",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:201", "memory:turn:202"],
                created_at="2026-06-24T02:10:00Z",
                job_id="consolidation-job:lineage-session-beta",
            ),
            completed_at="2026-06-24T02:15:00Z",
            source_children=[
                {"child_id": "memory:turn:201", "content": "Cara grouped the benchmark deltas."},
                {"child_id": "memory:turn:202", "content": "Drew recorded the release blocker."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"], session_beta_summary["summary_id"]],
                created_at="2026-06-24T02:20:00Z",
                job_id="consolidation-job:lineage-day",
            ),
            completed_at="2026-06-24T02:25:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
                {"child_id": session_beta_summary["summary_id"], "content": session_beta_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, session_beta, session_beta_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_lineage_report(ledger_path, day_summary["summary_id"])

        self.assertEqual(report["schema"], CONSOLIDATION_LINEAGE_REPORT_SCHEMA)
        self.assertEqual(report["summary_id"], day_summary["summary_id"])
        self.assertEqual(report["summary_level"], "day")
        self.assertEqual(report["source_level"], "session")
        self.assertEqual(
            report["leaf_source_child_ids"],
            ["memory:turn:101", "memory:turn:102", "memory:turn:201", "memory:turn:202"],
        )
        self.assertEqual(
            report["transitive_summary_ids"],
            [day_summary["summary_id"], session_alpha_summary["summary_id"], session_beta_summary["summary_id"]],
        )
        self.assertEqual(report["missing_summary_ids"], [])
        self.assertEqual(report["cycle_summary_ids"], [])
        self.assertEqual(
            [child["summary_id"] for child in report["node"]["children"]],
            [session_alpha_summary["summary_id"], session_beta_summary["summary_id"]],
        )
        self.assertEqual(
            report["node"]["children"][0]["leaf_source_child_ids"],
            ["memory:turn:101", "memory:turn:102"],
        )

    def test_consolidation_summary_lineage_report_surfaces_persisted_source_child_digests(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T02:00:00Z",
                job_id="consolidation-job:lineage-digests-session-alpha",
            ),
            completed_at="2026-06-24T02:05:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T02:20:00Z",
                job_id="consolidation-job:lineage-digests-day",
            ),
            completed_at="2026-06-24T02:25:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_lineage_report(ledger_path, day_summary["summary_id"])

        self.assertEqual(
            report["node"]["source_child_digests"],
            day_summary["source_child_digests"],
        )
        self.assertEqual(
            report["node"]["children"][0]["source_child_digests"],
            session_alpha_summary["source_child_digests"],
        )

    def test_consolidation_summary_lineage_report_surfaces_persisted_job_timestamps(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T02:00:00Z",
                job_id="consolidation-job:lineage-job-meta-session-alpha",
            ),
            completed_at="2026-06-24T02:05:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T02:20:00Z",
                job_id="consolidation-job:lineage-job-meta-day",
            ),
            completed_at="2026-06-24T02:25:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_lineage_report(ledger_path, day_summary["summary_id"])

        self.assertEqual(report["node"]["job_id"], day_summary["job_id"])
        self.assertEqual(report["node"]["created_at"], day_summary["created_at"])
        self.assertEqual(
            report["node"]["children"][0]["job_id"],
            session_alpha_summary["job_id"],
        )
        self.assertEqual(
            report["node"]["children"][0]["created_at"],
            session_alpha_summary["created_at"],
        )

    def test_consolidation_summary_lineage_report_surfaces_non_blocking_reversible_contract(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T02:00:00Z",
                job_id="consolidation-job:lineage-contract-session-alpha",
            ),
            completed_at="2026-06-24T02:05:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T02:20:00Z",
                job_id="consolidation-job:lineage-contract-day",
            ),
            completed_at="2026-06-24T02:25:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_lineage_report(ledger_path, day_summary["summary_id"])

        self.assertTrue(report["node"]["non_blocking"])
        self.assertTrue(report["node"]["reversible"])
        self.assertTrue(report["node"]["children"][0]["non_blocking"])
        self.assertTrue(report["node"]["children"][0]["reversible"])

    def test_consolidation_summary_lineage_report_surfaces_persisted_summarizer_contract(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T02:00:00Z",
                job_id="consolidation-job:lineage-summarizer-session-alpha",
                summarizer={
                    "kind": "fixture-local-summarizer",
                    "hosted_llm": False,
                    "model_id": None,
                    "planner_id": "planner:lineage",
                },
            ),
            completed_at="2026-06-24T02:05:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T02:20:00Z",
                job_id="consolidation-job:lineage-summarizer-day",
                summarizer={
                    "kind": "fixture-local-summarizer",
                    "hosted_llm": False,
                    "model_id": None,
                    "planner_id": "planner:lineage",
                },
            ),
            completed_at="2026-06-24T02:25:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_lineage_report(ledger_path, day_summary["summary_id"])

        self.assertEqual(report["node"]["summarizer"], day_summary["summarizer"])
        self.assertEqual(
            report["node"]["children"][0]["summarizer"],
            session_alpha_summary["summarizer"],
        )

    def test_consolidation_summary_lineage_report_marks_missing_nested_summary_records(self):
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=["summary:session:alpha", "summary:session:beta"],
                created_at="2026-06-24T02:30:00Z",
                job_id="consolidation-job:lineage-missing",
            ),
            completed_at="2026-06-24T02:35:00Z",
            source_children=[
                {"child_id": "summary:session:alpha", "content": "Alpha captured rollback contacts."},
                {"child_id": "summary:session:beta", "content": "Beta captured deploy approvals."},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_lineage_report(ledger_path, day_summary["summary_id"])

        self.assertEqual(report["schema"], CONSOLIDATION_LINEAGE_REPORT_SCHEMA)
        self.assertEqual(report["leaf_source_child_ids"], [])
        self.assertEqual(report["transitive_summary_ids"], [day_summary["summary_id"]])
        self.assertEqual(report["missing_summary_ids"], ["summary:session:alpha", "summary:session:beta"])
        self.assertEqual(report["cycle_summary_ids"], [])
        self.assertEqual(
            [child["kind"] for child in report["node"]["children"]],
            ["missing_summary", "missing_summary"],
        )

    def test_consolidation_summary_reverse_lineage_report_tracks_transitive_parent_summaries(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T03:00:00Z",
                job_id="consolidation-job:reverse-session-alpha",
            ),
            completed_at="2026-06-24T03:05:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T03:10:00Z",
                job_id="consolidation-job:reverse-day",
            ),
            completed_at="2026-06-24T03:15:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )
        week_job, week_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/week:2026-w26",
                summary_level="week",
                source_level="day",
                source_child_ids=[day_summary["summary_id"]],
                created_at="2026-06-24T03:20:00Z",
                job_id="consolidation-job:reverse-week",
            ),
            completed_at="2026-06-24T03:25:00Z",
            source_children=[
                {"child_id": day_summary["summary_id"], "content": day_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)
            append_consolidation_summary_record(ledger_path, week_job, week_summary)

            report = consolidation_summary_reverse_lineage_report(ledger_path, "memory:turn:101")

        self.assertEqual(report["schema"], CONSOLIDATION_REVERSE_LINEAGE_REPORT_SCHEMA)
        self.assertEqual(report["child_id"], "memory:turn:101")
        self.assertEqual(report["direct_summary_ids"], [session_alpha_summary["summary_id"]])
        self.assertEqual(
            report["transitive_summary_ids"],
            [session_alpha_summary["summary_id"], day_summary["summary_id"], week_summary["summary_id"]],
        )
        self.assertEqual(report["root_summary_ids"], [week_summary["summary_id"]])
        self.assertEqual(report["cycle_summary_ids"], [])
        self.assertEqual(len(report["paths"]), 1)
        self.assertEqual(
            report["paths"][0]["summary_ids"],
            [session_alpha_summary["summary_id"], day_summary["summary_id"], week_summary["summary_id"]],
        )
        self.assertEqual(report["paths"][0]["summary_levels"], ["session", "day", "week"])
        self.assertEqual(report["paths"][0]["root_summary_id"], week_summary["summary_id"])

    def test_consolidation_summary_reverse_lineage_report_tracks_nested_summary_children(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T03:30:00Z",
                job_id="consolidation-job:reverse-nested-session-alpha",
            ),
            completed_at="2026-06-24T03:35:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T03:40:00Z",
                job_id="consolidation-job:reverse-nested-day",
            ),
            completed_at="2026-06-24T03:45:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_reverse_lineage_report(ledger_path, session_alpha_summary["summary_id"])

        self.assertEqual(report["schema"], CONSOLIDATION_REVERSE_LINEAGE_REPORT_SCHEMA)
        self.assertEqual(report["child_id"], session_alpha_summary["summary_id"])
        self.assertEqual(report["direct_summary_ids"], [day_summary["summary_id"]])
        self.assertEqual(report["transitive_summary_ids"], [day_summary["summary_id"]])
        self.assertEqual(report["root_summary_ids"], [day_summary["summary_id"]])
        self.assertEqual(report["cycle_summary_ids"], [])
        self.assertEqual([path["summary_ids"] for path in report["paths"]], [[day_summary["summary_id"]]])
        self.assertEqual([path["summary_levels"] for path in report["paths"]], [["day"]])
        self.assertEqual([path["root_summary_id"] for path in report["paths"]], [day_summary["summary_id"]])
        self.assertEqual(
            report["paths"][0]["summary_nodes"],
            [
                {
                    "summary_id": day_summary["summary_id"],
                    "job_id": day_summary["job_id"],
                    "created_at": day_summary["created_at"],
                    "summarizer": day_summary["summarizer"],
                    "non_blocking": day_summary["non_blocking"],
                    "reversible": day_summary["reversible"],
                    "summary_level": "day",
                    "source_level": "session",
                    "source_child_ids": [session_alpha_summary["summary_id"]],
                    "source_child_digests": day_summary["source_child_digests"],
                    "content_digest": day_summary["content_digest"],
                }
            ],
        )

    def test_consolidation_summary_reverse_lineage_report_surfaces_persisted_source_child_digests(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T03:30:00Z",
                job_id="consolidation-job:reverse-digests-session-alpha",
            ),
            completed_at="2026-06-24T03:35:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T03:40:00Z",
                job_id="consolidation-job:reverse-digests-day",
            ),
            completed_at="2026-06-24T03:45:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_reverse_lineage_report(ledger_path, "memory:turn:101")

        self.assertEqual(
            [node["summary_id"] for node in report["paths"][0]["summary_nodes"]],
            [session_alpha_summary["summary_id"], day_summary["summary_id"]],
        )
        self.assertEqual(
            report["paths"][0]["summary_nodes"][0]["source_child_digests"],
            session_alpha_summary["source_child_digests"],
        )
        self.assertEqual(
            report["paths"][0]["summary_nodes"][1]["source_child_digests"],
            day_summary["source_child_digests"],
        )

    def test_consolidation_summary_reverse_lineage_report_surfaces_persisted_job_timestamps(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T03:30:00Z",
                job_id="consolidation-job:reverse-job-meta-session-alpha",
            ),
            completed_at="2026-06-24T03:35:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T03:40:00Z",
                job_id="consolidation-job:reverse-job-meta-day",
            ),
            completed_at="2026-06-24T03:45:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_reverse_lineage_report(ledger_path, "memory:turn:101")

        self.assertEqual(
            report["paths"][0]["summary_nodes"][0]["job_id"],
            session_alpha_summary["job_id"],
        )
        self.assertEqual(
            report["paths"][0]["summary_nodes"][0]["created_at"],
            session_alpha_summary["created_at"],
        )
        self.assertEqual(
            report["paths"][0]["summary_nodes"][1]["job_id"],
            day_summary["job_id"],
        )
        self.assertEqual(
            report["paths"][0]["summary_nodes"][1]["created_at"],
            day_summary["created_at"],
        )

    def test_consolidation_summary_reverse_lineage_report_surfaces_persisted_summarizer_contract(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T03:30:00Z",
                job_id="consolidation-job:reverse-summarizer-session-alpha",
                summarizer={
                    "kind": "fixture-local-summarizer",
                    "hosted_llm": False,
                    "model_id": None,
                    "planner_id": "planner:reverse-lineage",
                },
            ),
            completed_at="2026-06-24T03:35:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T03:40:00Z",
                job_id="consolidation-job:reverse-summarizer-day",
                summarizer={
                    "kind": "fixture-local-summarizer",
                    "hosted_llm": False,
                    "model_id": None,
                    "planner_id": "planner:reverse-lineage",
                },
            ),
            completed_at="2026-06-24T03:45:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_reverse_lineage_report(ledger_path, "memory:turn:101")

        self.assertEqual(
            report["paths"][0]["summary_nodes"][0]["summarizer"],
            session_alpha_summary["summarizer"],
        )
        self.assertEqual(
            report["paths"][0]["summary_nodes"][1]["summarizer"],
            day_summary["summarizer"],
        )

    def test_consolidation_summary_reverse_lineage_report_surfaces_non_blocking_reversible_contract(self):
        session_alpha, session_alpha_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-24T03:30:00Z",
                job_id="consolidation-job:reverse-contract-session-alpha",
            ),
            completed_at="2026-06-24T03:35:00Z",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada updated the rollback owner."},
                {"child_id": "memory:turn:102", "content": "Ben confirmed the deploy checklist."},
            ],
        )
        day_job, day_summary = materialize_consolidation_summary(
            create_consolidation_job(
                scope="project:zmem/day:2026-06-24",
                summary_level="day",
                source_level="session",
                source_child_ids=[session_alpha_summary["summary_id"]],
                created_at="2026-06-24T03:40:00Z",
                job_id="consolidation-job:reverse-contract-day",
            ),
            completed_at="2026-06-24T03:45:00Z",
            source_children=[
                {"child_id": session_alpha_summary["summary_id"], "content": session_alpha_summary["summary_text"]},
            ],
        )

        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "consolidation-summaries.jsonl"
            append_consolidation_summary_record(ledger_path, session_alpha, session_alpha_summary)
            append_consolidation_summary_record(ledger_path, day_job, day_summary)

            report = consolidation_summary_reverse_lineage_report(ledger_path, "memory:turn:101")

        self.assertTrue(report["paths"][0]["summary_nodes"][0]["non_blocking"])
        self.assertTrue(report["paths"][0]["summary_nodes"][0]["reversible"])
        self.assertTrue(report["paths"][0]["summary_nodes"][1]["non_blocking"])
        self.assertTrue(report["paths"][0]["summary_nodes"][1]["reversible"])

if __name__ == "__main__":
    unittest.main()
