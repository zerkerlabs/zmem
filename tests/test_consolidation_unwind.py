import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from zerker_memory.consolidation import (
    append_consolidation_job_record,
    append_consolidation_summary_record,
    create_consolidation_job,
    materialize_consolidation_summary,
    transition_consolidation_job,
)
from zerker_memory.consolidation_unwind import (
    CONSOLIDATION_RETRY_GROUP_REPORT_SCHEMA,
    CONSOLIDATION_RETRY_GUIDANCE_SCHEMA,
    consolidation_retry_group_report,
    CONSOLIDATION_UNWIND_PLAN_SCHEMA,
    consolidation_retry_guidance,
    consolidation_unwind_plan,
)


class ConsolidationUnwindPlanTest(unittest.TestCase):
    def test_unwind_plan_orders_direct_parent_before_root_summary(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path, summary_ledger_path = self._build_verified_nested_ledgers(Path(tmp))

            plan = consolidation_unwind_plan(job_ledger_path, summary_ledger_path, "memory:turn:101")

        self.assertEqual(plan["schema"], CONSOLIDATION_UNWIND_PLAN_SCHEMA)
        self.assertEqual(plan["child_kind"], "source_child")
        self.assertEqual(plan["direct_summary_ids"], ["summary:session:alpha"])
        self.assertEqual(
            plan["impacted_summary_ids"],
            ["summary:session:alpha", "summary:day:2026-06-23:zmem"],
        )
        self.assertEqual(plan["root_summary_ids"], ["summary:day:2026-06-23:zmem"])
        self.assertEqual(plan["blocked_summary_ids"], [])
        self.assertEqual(plan["steps"][0]["summary_id"], "summary:session:alpha")
        self.assertEqual(plan["steps"][0]["audit_status"], "verified")
        self.assertEqual(plan["steps"][0]["depends_on_summary_ids"], [])
        self.assertEqual(plan["steps"][1]["summary_id"], "summary:day:2026-06-23:zmem")
        self.assertEqual(plan["steps"][1]["depends_on_summary_ids"], ["summary:session:alpha"])
        self.assertEqual(plan["steps"][1]["action"], "review-and-rematerialize")

    def test_unwind_plan_surfaces_nested_summary_leaf_lineage(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path, summary_ledger_path = self._build_verified_nested_ledgers(Path(tmp))

            plan = consolidation_unwind_plan(job_ledger_path, summary_ledger_path, "summary:session:alpha")

        self.assertEqual(plan["child_kind"], "nested_summary")
        self.assertEqual(plan["direct_summary_ids"], ["summary:day:2026-06-23:zmem"])
        self.assertEqual(plan["impacted_summary_ids"], ["summary:day:2026-06-23:zmem"])
        self.assertEqual(
            plan["nested_child_lineage"]["leaf_source_child_ids"],
            ["memory:turn:101", "memory:turn:102"],
        )
        self.assertEqual(plan["nested_child_lineage"]["missing_summary_ids"], [])
        self.assertEqual(plan["blocked_child_summary_ids"], [])

    def test_unwind_plan_marks_mismatched_summary_as_blocked(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "jobs.jsonl"
            summary_ledger_path = Path(tmp) / "summaries.jsonl"

            session_job = create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-25T09:00:00Z",
                job_id="consolidation-job:session-alpha",
            )
            completed_session_job, session_summary = materialize_consolidation_summary(
                session_job,
                completed_at="2026-06-25T09:03:00Z",
                summary_id="summary:session:alpha",
                source_children=[
                    {"child_id": "memory:turn:101", "content": "Ada confirmed deploy gate owner."},
                    {"child_id": "memory:turn:102", "content": "Ben logged rollback contact."},
                ],
            )

            append_consolidation_job_record(job_ledger_path, session_job)
            append_consolidation_job_record(job_ledger_path, completed_session_job)
            append_consolidation_summary_record(summary_ledger_path, completed_session_job, session_summary)

            day_job = create_consolidation_job(
                scope="project:zmem/day:2026-06-23",
                summary_level="day",
                source_level="session",
                source_child_ids=["summary:session:alpha", "summary:session:beta"],
                created_at="2026-06-25T09:05:00Z",
                job_id="consolidation-job:day-zmem",
            )
            completed_day_job = transition_consolidation_job(
                day_job,
                status="completed",
                updated_at="2026-06-25T09:08:00Z",
                output_summary_ids=["summary:day:2026-06-23:zmem"],
            )

            append_consolidation_job_record(job_ledger_path, day_job)
            append_consolidation_job_record(job_ledger_path, completed_day_job)
            tampered_day_summary = {
                "schema": "zerker.consolidation_summary.v1",
                "summary_id": "summary:day:2026-06-23:zmem",
                "job_id": "consolidation-job:day-zmem",
                "scope": "project:zmem/day:2026-06-23",
                "summary_level": "day",
                "source_level": "session",
                "source_child_ids": ["summary:session:alpha"],
                "source_child_count": 1,
                "source_child_digests": {"summary:session:alpha": "sha256:tampered"},
                "summary_text": "[summary:session:alpha] Tampered day rollup.",
                "content_digest": "sha256:tampered-day",
                "non_blocking": True,
                "reversible": True,
                "lineage_kind": "source-child-to-summary",
                "summarizer": {"kind": "tampered-local", "hosted_llm": False, "model_id": None},
                "created_at": "2026-06-25T09:08:00Z",
            }
            with summary_ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered_day_summary, sort_keys=True))
                handle.write("\n")

            plan = consolidation_unwind_plan(job_ledger_path, summary_ledger_path, "summary:session:alpha")

        self.assertEqual(plan["blocked_summary_ids"], ["summary:day:2026-06-23:zmem"])
        self.assertEqual(plan["steps"][0]["summary_id"], "summary:day:2026-06-23:zmem")
        self.assertEqual(plan["steps"][0]["audit_status"], "mismatch")
        self.assertEqual(plan["steps"][0]["action"], "review-before-rematerialize")

    def test_retry_guidance_marks_direct_verified_step_ready_and_parent_waiting(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path, summary_ledger_path = self._build_verified_nested_ledgers(Path(tmp))

            guidance = consolidation_retry_guidance(job_ledger_path, summary_ledger_path, "memory:turn:101")

        self.assertEqual(guidance["schema"], CONSOLIDATION_RETRY_GUIDANCE_SCHEMA)
        self.assertEqual(guidance["child_kind"], "source_child")
        self.assertEqual(guidance["child_retry_action"], "repair-source-child-first")
        self.assertEqual(guidance["ready_summary_ids"], ["summary:session:alpha"])
        self.assertEqual(guidance["steps"][0]["summary_id"], "summary:session:alpha")
        self.assertTrue(guidance["steps"][0]["retryable_now"])
        self.assertEqual(guidance["steps"][0]["retry_action"], "rematerialize-local-summary")
        self.assertEqual(guidance["steps"][0]["blocking_reasons"], [])
        self.assertEqual(guidance["steps"][1]["summary_id"], "summary:day:2026-06-23:zmem")
        self.assertFalse(guidance["steps"][1]["retryable_now"])
        self.assertEqual(
            guidance["steps"][1]["blocked_by_summary_ids"],
            ["summary:session:alpha"],
        )
        self.assertEqual(
            guidance["steps"][1]["retry_action"],
            "wait-for-dependent-summary-repair",
        )

    def test_retry_guidance_requires_nested_child_repair_before_parents(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path, summary_ledger_path = self._build_verified_nested_ledgers(Path(tmp))

            guidance = consolidation_retry_guidance(job_ledger_path, summary_ledger_path, "summary:session:alpha")

        self.assertEqual(guidance["child_kind"], "nested_summary")
        self.assertEqual(guidance["child_retry_action"], "repair-child-summary-first")
        self.assertTrue(guidance["child_repair_required"])
        self.assertEqual(guidance["ready_summary_ids"], [])
        self.assertEqual(
            guidance["steps"][0]["blocking_reasons"],
            ["nested-child-summary-needs-repair"],
        )
        self.assertEqual(
            guidance["steps"][0]["retry_action"],
            "wait-for-child-summary-repair",
        )

    def test_retry_guidance_can_recreate_missing_summary_without_parent_dependencies(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path = Path(tmp) / "jobs.jsonl"
            summary_ledger_path = Path(tmp) / "summaries.jsonl"
            session_job = create_consolidation_job(
                scope="project:zmem/session:alpha",
                summary_level="session",
                source_level="turn",
                source_child_ids=["memory:turn:101", "memory:turn:102"],
                created_at="2026-06-25T10:00:00Z",
                job_id="consolidation-job:session-alpha",
            )
            completed_session_job = transition_consolidation_job(
                session_job,
                status="completed",
                updated_at="2026-06-25T10:04:00Z",
                output_summary_ids=["summary:session:alpha"],
            )

            append_consolidation_job_record(job_ledger_path, session_job)
            append_consolidation_job_record(job_ledger_path, completed_session_job)

            guidance = consolidation_retry_guidance(job_ledger_path, summary_ledger_path, "memory:turn:101")

        self.assertEqual(guidance["ready_summary_ids"], ["summary:session:alpha"])
        self.assertEqual(guidance["blocked_summary_ids"], ["summary:session:alpha"])
        self.assertEqual(guidance["steps"][0]["audit_status"], "missing-summary")
        self.assertTrue(guidance["steps"][0]["retryable_now"])
        self.assertEqual(guidance["steps"][0]["blocking_reasons"], [])
        self.assertEqual(guidance["steps"][0]["retry_action"], "recreate-missing-summary")

    def test_retry_group_report_groups_shared_impacts_across_multiple_children(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path, summary_ledger_path = self._build_verified_nested_ledgers(Path(tmp))

            report = consolidation_retry_group_report(
                job_ledger_path,
                summary_ledger_path,
                ["memory:turn:101", "memory:turn:102"],
            )

        self.assertEqual(report["schema"], CONSOLIDATION_RETRY_GROUP_REPORT_SCHEMA)
        self.assertEqual(report["requested_child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(report["child_report_count"], 2)
        self.assertEqual(report["impacted_summary_count"], 2)
        self.assertEqual(report["shared_impacted_summary_count"], 2)
        self.assertEqual(report["ready_summary_ids"], ["summary:session:alpha"])
        self.assertEqual(report["blocked_summary_ids"], ["summary:day:2026-06-23:zmem"])

        groups_by_summary_id = {group["summary_id"]: group for group in report["groups"]}
        session_group = groups_by_summary_id["summary:session:alpha"]
        self.assertEqual(session_group["dependency_group_status"], "retryable-now")
        self.assertEqual(session_group["child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(session_group["ready_child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(session_group["blocked_child_ids"], [])
        self.assertEqual(session_group["direct_child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(session_group["root_child_ids"], [])
        self.assertEqual(session_group["retry_actions"], ["rematerialize-local-summary"])
        self.assertEqual(session_group["blocking_reasons"], [])
        self.assertTrue(session_group["shared_dependency_group"])

        day_group = groups_by_summary_id["summary:day:2026-06-23:zmem"]
        self.assertEqual(day_group["dependency_group_status"], "blocked")
        self.assertEqual(day_group["child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(day_group["ready_child_ids"], [])
        self.assertEqual(day_group["blocked_child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(day_group["direct_child_ids"], [])
        self.assertEqual(day_group["root_child_ids"], ["memory:turn:101", "memory:turn:102"])
        self.assertEqual(day_group["retry_actions"], ["wait-for-dependent-summary-repair"])
        self.assertEqual(day_group["blocked_by_summary_ids"], ["summary:session:alpha"])

    def test_retry_group_report_dedupes_requested_children_and_keeps_orphans_out_of_groups(self):
        with TemporaryDirectory() as tmp:
            job_ledger_path, summary_ledger_path = self._build_verified_nested_ledgers(Path(tmp))

            report = consolidation_retry_group_report(
                job_ledger_path,
                summary_ledger_path,
                ["summary:session:alpha", "memory:turn:999", "summary:session:alpha"],
            )

        self.assertEqual(report["requested_child_ids"], ["summary:session:alpha", "memory:turn:999"])
        self.assertEqual(report["child_report_count"], 2)
        self.assertEqual(report["impacted_summary_count"], 1)
        self.assertEqual(report["shared_impacted_summary_count"], 0)
        self.assertEqual(report["ready_summary_ids"], [])
        self.assertEqual(report["blocked_summary_ids"], ["summary:day:2026-06-23:zmem"])

        child_reports = {report["child_id"]: report for report in report["child_reports"]}
        self.assertEqual(child_reports["summary:session:alpha"]["child_kind"], "nested_summary")
        self.assertEqual(child_reports["summary:session:alpha"]["child_retry_action"], "repair-child-summary-first")
        self.assertEqual(child_reports["summary:session:alpha"]["impacted_summary_ids"], ["summary:day:2026-06-23:zmem"])
        self.assertEqual(child_reports["memory:turn:999"]["child_kind"], "orphan_child")
        self.assertEqual(child_reports["memory:turn:999"]["child_retry_action"], "no-dependent-summaries")
        self.assertEqual(child_reports["memory:turn:999"]["impacted_summary_ids"], [])

        group = report["groups"][0]
        self.assertEqual(group["summary_id"], "summary:day:2026-06-23:zmem")
        self.assertEqual(group["child_ids"], ["summary:session:alpha"])
        self.assertEqual(group["child_kinds"], ["nested_summary"])
        self.assertEqual(group["blocking_reasons"], ["nested-child-summary-needs-repair"])
        self.assertEqual(group["retry_actions"], ["wait-for-child-summary-repair"])

    def _build_verified_nested_ledgers(self, root: Path) -> tuple[Path, Path]:
        job_ledger_path = root / "jobs.jsonl"
        summary_ledger_path = root / "summaries.jsonl"

        session_job = create_consolidation_job(
            scope="project:zmem/session:alpha",
            summary_level="session",
            source_level="turn",
            source_child_ids=["memory:turn:101", "memory:turn:102"],
            created_at="2026-06-25T08:00:00Z",
            job_id="consolidation-job:session-alpha",
        )
        completed_session_job, session_summary = materialize_consolidation_summary(
            session_job,
            completed_at="2026-06-25T08:03:00Z",
            summary_id="summary:session:alpha",
            source_children=[
                {"child_id": "memory:turn:101", "content": "Ada confirmed deploy gate owner."},
                {"child_id": "memory:turn:102", "content": "Ben logged rollback contact."},
            ],
        )

        day_job = create_consolidation_job(
            scope="project:zmem/day:2026-06-23",
            summary_level="day",
            source_level="session",
            source_child_ids=["summary:session:alpha", "summary:session:beta"],
            created_at="2026-06-25T08:05:00Z",
            job_id="consolidation-job:day-zmem",
        )
        completed_day_job, day_summary = materialize_consolidation_summary(
            day_job,
            completed_at="2026-06-25T08:09:00Z",
            summary_id="summary:day:2026-06-23:zmem",
            source_children=[
                {"child_id": "summary:session:alpha", "content": session_summary["summary_text"]},
                {"child_id": "summary:session:beta", "content": "[summary:session:beta] Cara logged benchmark drift."},
            ],
        )

        for job in (session_job, completed_session_job, day_job, completed_day_job):
            append_consolidation_job_record(job_ledger_path, job)
        append_consolidation_summary_record(summary_ledger_path, completed_session_job, session_summary)
        append_consolidation_summary_record(summary_ledger_path, completed_day_job, day_summary)
        return job_ledger_path, summary_ledger_path
