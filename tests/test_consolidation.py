import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from zerker_memory.consolidation import (
    CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA,
    CONSOLIDATION_LINEAGE_KIND,
    append_consolidation_job_record,
    create_consolidation_job,
    consolidation_levels,
    consolidation_lineage_fixture,
    latest_consolidation_jobs,
    load_consolidation_job_records,
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


if __name__ == "__main__":
    unittest.main()
