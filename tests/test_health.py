import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import main
from zerker_memory.health import (
    CATEGORY_ORDER,
    MEMORY_HEALTH_REPORT_SCHEMA,
    build_memory_health_report,
)
from zerker_memory.store import MemoryStore


EVALUATED_AT = "2025-01-01T00:00:00Z"


class MemoryHealthAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "memory.sqlite"
        self.store = MemoryStore(self.db_path)
        self.store.init()

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    def test_report_covers_supported_categories_without_claiming_semantic_truth(self):
        expired = self._remember(
            "Expired deployment note.",
            memory_id="mem_expired",
        )
        self.store.conn.execute(
            "UPDATE memories SET expires_at = ? WHERE id = ?",
            ("2024-12-01T00:00:00Z", expired.id),
        )
        parent = self._remember(
            "Status page owner is Alex.",
            memory_id="mem_parent",
        )
        self._remember(
            "Status page owner is Priya.",
            memory_id="mem_child",
            parents=[parent.id],
        )
        self._remember(
            "Incident owner is Alex.",
            memory_id="mem_conflict_a",
            created_at="2024-01-02T00:00:00Z",
        )
        self._remember(
            "Incident owner is Priya.",
            memory_id="mem_conflict_b",
            source_kind="system",
            created_at="2024-01-02T00:00:00Z",
        )
        self._remember(
            "Exact duplicate memory.",
            memory_id="mem_duplicate_a",
        )
        self._remember(
            "Exact duplicate memory.",
            memory_id="mem_duplicate_b",
        )
        missing_receipt = self._remember(
            "Memory without a surviving write receipt.",
            memory_id="mem_missing_receipt",
        )
        self.store.conn.execute(
            "DELETE FROM memory_write_receipts WHERE memory_id = ?",
            (missing_receipt.id,),
        )
        self._remember(
            "Agent memory without a source URI.",
            memory_id="mem_weak_source",
            source_kind="agent",
            status="active",
        )
        high_risk = self._remember(
            "Production deploys require signed approval.",
            memory_id="mem_high_risk",
            labels=["risk:high"],
        )
        self.store.inject(
            "Production deploys require signed approval.",
            agent_id="codex",
            risk="high",
            scope="project",
        )
        self.store.conn.commit()
        self.store.conn.close()

        report = build_memory_health_report(self.db_path, evaluated_at=EVALUATED_AT)

        self.assertEqual(report["schema"], MEMORY_HEALTH_REPORT_SCHEMA)
        self.assertTrue(report["ok"])
        self.assertFalse(report["healthy"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["semantic_truth_claimed"])
        self.assertEqual(list(report["findings"]), list(CATEGORY_ORDER))
        for category in CATEGORY_ORDER:
            self.assertGreater(report["category_counts"][category], 0)
            for finding in report["findings"][category]:
                self.assertEqual(finding["category"], category)
                self.assertTrue(finding["memory_ids"])
                self.assertTrue(finding["reason"])
                self.assertIsInstance(finding["evidence"], dict)
                self.assertFalse(finding["semantic_truth_claimed"])

        stale_reasons = {
            finding["reason"]: finding for finding in report["findings"]["stale_or_expired"]
        }
        self.assertEqual(
            stale_reasons["active_memory_expired"]["memory_ids"],
            [expired.id],
        )
        self.assertEqual(
            stale_reasons["active_memory_has_active_child_candidate"]["memory_ids"],
            sorted([parent.id, "mem_child"]),
        )
        conflict = next(
            finding
            for finding in report["findings"]["contradictory_or_conflicting"]
            if finding["memory_ids"] == ["mem_conflict_a", "mem_conflict_b"]
        )
        self.assertEqual(conflict["memory_ids"], ["mem_conflict_a", "mem_conflict_b"])
        self.assertEqual(conflict["evidence"]["relation"], "is")
        self.assertNotIn("value_by_memory_id", conflict["evidence"])
        duplicate = report["findings"]["exact_duplicate"][0]
        self.assertEqual(duplicate["memory_ids"], ["mem_duplicate_a", "mem_duplicate_b"])
        provenance_by_reason = {
            finding["reason"]: finding
            for finding in report["findings"]["weak_or_missing_provenance"]
        }
        self.assertEqual(
            provenance_by_reason["memory_has_no_write_receipt"]["memory_ids"],
            [missing_receipt.id],
        )
        weak_source = next(
            finding
            for finding in report["findings"]["weak_or_missing_provenance"]
            if finding["memory_ids"] == ["mem_weak_source"]
        )
        self.assertIn("source_uri", weak_source["evidence"]["missing_fields"])
        high_risk_finding = next(
            finding
            for finding in report["findings"]["high_risk_active"]
            if finding["memory_ids"] == [high_risk.id]
        )
        self.assertEqual(
            high_risk_finding["evidence"]["evidence_sources"],
            ["memory_label", "injection_receipt"],
        )

    def test_report_and_findings_have_deterministic_order(self):
        self._remember(
            "Duplicate text.",
            memory_id="mem_z",
        )
        self._remember(
            "Duplicate text.",
            memory_id="mem_a",
        )
        self._remember(
            "Build target is Railway.",
            memory_id="mem_conflict_z",
        )
        self._remember(
            "Build target is Render.",
            memory_id="mem_conflict_a",
            source_kind="system",
        )
        self.store.conn.close()

        first = build_memory_health_report(self.db_path, evaluated_at=EVALUATED_AT)
        second = build_memory_health_report(self.db_path, evaluated_at=EVALUATED_AT)

        self.assertEqual(first, second)
        self.assertEqual(
            first["findings"]["exact_duplicate"][0]["memory_ids"],
            ["mem_a", "mem_z"],
        )
        self.assertEqual(
            first["findings"]["contradictory_or_conflicting"][0]["memory_ids"],
            ["mem_conflict_a", "mem_conflict_z"],
        )

    def test_cli_json_and_summary_are_read_only(self):
        memory = self._remember(
            "Production deploys require approval.",
            memory_id="mem_read_only",
            labels=["risk:high"],
        )
        self.store.conn.commit()
        self.store.conn.close()
        before_files = self._directory_bytes()
        before_mtime = self.db_path.stat().st_mtime_ns

        json_output = io.StringIO()
        with patch(
            "zerker_memory.cli.MemoryStore",
            side_effect=AssertionError("audit must not construct MemoryStore"),
        ):
            with redirect_stdout(json_output):
                json_exit = main(["--db", str(self.db_path), "audit", "health"])

        summary_output = io.StringIO()
        with patch(
            "zerker_memory.cli.MemoryStore",
            side_effect=AssertionError("audit must not construct MemoryStore"),
        ):
            with redirect_stdout(summary_output):
                summary_exit = main(
                    ["--db", str(self.db_path), "audit", "health", "--summary-only"]
                )

        after_files = self._directory_bytes()
        self.assertEqual(json_exit, 0)
        self.assertEqual(summary_exit, 0)
        self.assertEqual(before_files, after_files)
        self.assertEqual(before_mtime, self.db_path.stat().st_mtime_ns)
        machine_report = json.loads(json_output.getvalue())
        self.assertEqual(machine_report["schema"], MEMORY_HEALTH_REPORT_SCHEMA)
        self.assertEqual(
            machine_report["findings"]["high_risk_active"][0]["memory_ids"],
            [memory.id],
        )
        summary = summary_output.getvalue()
        self.assertIn("Zerker Memory health audit", summary)
        self.assertIn("Read-only: yes", summary)
        self.assertIn("Semantic truth: not evaluated", summary)
        self.store = MemoryStore(self.db_path)

    def test_report_reads_committed_wal_state_without_closing_writer(self):
        self._remember(
            "Fresh committed WAL memory.",
            memory_id="mem_wal_fresh",
        )
        self.store.conn.commit()
        before_files = self._directory_bytes()

        report = build_memory_health_report(self.db_path, evaluated_at=EVALUATED_AT)

        self.assertTrue(report["ok"])
        self.assertEqual(report["memory_count"], 1)
        self.assertEqual(before_files, self._directory_bytes())

    def test_missing_database_is_reported_without_creating_it(self):
        self.store.conn.close()
        self.db_path.unlink()
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["--db", str(self.db_path), "audit", "health"])

        report = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(self.db_path.exists())
        self.assertEqual(report["error"]["code"], "database_not_found")
        self.store = MemoryStore(self.db_path)

    def _remember(
        self,
        content: str,
        *,
        memory_id: str,
        source_kind: str = "human",
        status: str = "active",
        parents: list[str] | None = None,
        labels: list[str] | None = None,
        created_at: str = "2024-01-01T00:00:00Z",
    ):
        return self.store.remember(
            content,
            memory_type="semantic",
            scope="project",
            source_kind=source_kind,
            status=status,
            actor_id="tester",
            actor_uri="agent://tester/session-health",
            session_id="session://health",
            source_uri=(
                None
                if source_kind == "agent"
                else f"fixture://health/{memory_id}"
            ),
            memory_id=memory_id,
            parents=parents,
            labels=labels,
            created_at=created_at,
        )

    def _directory_bytes(self) -> dict[str, bytes]:
        return {
            path.name: path.read_bytes()
            for path in sorted(Path(self.temp_dir.name).iterdir())
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
