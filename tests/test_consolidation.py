import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from zerker_memory.consolidation import (
    CONSOLIDATION_AUDIT_RECORD_SCHEMA,
    CONSOLIDATION_AUDIT_REPORT_SCHEMA,
    CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA,
    CONSOLIDATION_LINEAGE_KIND,
    CONSOLIDATION_LINEAGE_REPORT_SCHEMA,
    CONSOLIDATION_REVERSE_LINEAGE_REPORT_SCHEMA,
    CONSOLIDATION_SUMMARY_SCHEMA,
    append_consolidation_job_record,
    append_consolidation_summary_record,
    consolidation_audit_report,
    consolidation_summary_reverse_lineage_report,
    consolidation_summary_lineage_report,
    create_consolidation_job,
    consolidation_levels,
    consolidation_lineage_fixture,
    consolidation_recall_planner_fixture,
    latest_consolidation_jobs,
    latest_consolidation_summaries,
    load_consolidation_job_records,
    load_consolidation_summary_records,
    materialize_consolidation_summary,
    plan_consolidation_jobs,
    source_child_ids_for_summary,
    summary_ids_for_source_child,
    transition_consolidation_job,
    validate_consolidation_lineage_fixture,
)


class ConsolidationFixtureTest(unittest.TestCase):
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
        self.assertEqual(
            report["paths"],
            [
                {
                    "summary_ids": [day_summary["summary_id"]],
                    "summary_levels": ["day"],
                    "root_summary_id": day_summary["summary_id"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
