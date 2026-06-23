import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from zerker_memory.consolidation import (
    CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA,
    CONSOLIDATION_LINEAGE_KIND,
    CONSOLIDATION_SUMMARY_SCHEMA,
    append_consolidation_job_record,
    create_consolidation_job,
    consolidation_levels,
    consolidation_lineage_fixture,
    consolidation_recall_planner_fixture,
    latest_consolidation_jobs,
    load_consolidation_job_records,
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


if __name__ == "__main__":
    unittest.main()
