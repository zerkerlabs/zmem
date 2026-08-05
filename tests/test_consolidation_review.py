import copy
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import main
from zerker_memory.consolidation import consolidation_audit_report
from zerker_memory.consolidation_live import build_live_consolidation_preview
from zerker_memory.consolidation_materialize import (
    default_job_ledger_path,
    default_summary_ledger_path,
    materialize_live_consolidation_candidate,
)
from zerker_memory.consolidation_review import (
    CONSOLIDATION_ADMITTED_EVENT,
    _finalize_inspection,
    admit_consolidation_summary,
    build_consolidation_summary_inspection,
    discard_consolidation_summary,
    list_consolidation_summaries,
)
from zerker_memory.store import MemoryStore, sha256_text


EVALUATED_AT = "2026-08-01T00:00:00Z"
MATERIALIZED_AT = "2026-08-01T00:05:00Z"
INSPECTED_AT = "2026-08-01T00:06:00Z"
DECIDED_AT = "2026-08-01T00:07:00Z"


class ConsolidationReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "memory.sqlite"
        self.store = MemoryStore(self.db_path)
        self.store.init()
        self._remember("The launch owner is Ada.", "mem_1", "episodic", 1)
        self._remember("The release gate requires rollback proof.", "mem_2", "semantic", 2)
        self._remember("The deployment region is eu-west.", "mem_3", "episodic", 3)
        preview = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=3,
            evaluated_at=EVALUATED_AT,
        )
        candidate = preview["candidates"][0]
        materialized = materialize_live_consolidation_candidate(
            self.db_path,
            preview,
            candidate_id=candidate["candidate_id"],
            actor_id="operator",
            confirmed_preview_id=preview["confirmation_id"],
            completed_at=MATERIALIZED_AT,
        )
        self.summary_id = materialized["summary_id"]

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    def test_inspection_recomputes_summary_without_canonical_writes(self):
        before = self._counts()

        queue = list_consolidation_summaries(self.db_path)
        inspection = self._inspection()

        self.assertEqual(before, self._counts())
        self.assertTrue(queue["ok"])
        self.assertEqual(queue["awaiting_review_count"], 1)
        self.assertNotIn("summary_text", json.dumps(queue))
        self.assertEqual(inspection["review_state"], "awaiting_review")
        self.assertTrue(inspection["actionable"])
        self.assertTrue(inspection["source_verification"]["deterministic_summary_recomputed"])
        self.assertEqual(inspection["source_verification"]["verified_source_count"], 3)
        self.assertFalse(inspection["canonical_memory_written"])
        self.assertFalse(inspection["operator_identity_authenticated"])

    def test_admit_creates_one_ceiling_bound_memory_and_receipted_decision(self):
        inspection = self._inspection()
        sources_before = {memory_id: self.store.get(memory_id).to_dict() for memory_id in ("mem_1", "mem_2", "mem_3")}

        result = admit_consolidation_summary(
            self.db_path,
            inspection,
            actor_id="reviewer",
            confirmed_inspection_id=inspection["confirmation_id"],
            decided_at=DECIDED_AT,
        )

        self.assertEqual(result["status"], "admitted")
        self.assertTrue(result["canonical_memory_written_this_run"])
        memory = self.store.get(result["canonical_memory_id"])
        self.assertEqual(memory.status, "active")
        self.assertEqual(memory.type, "semantic")
        self.assertEqual(memory.source_kind, "consolidation")
        self.assertEqual(memory.trust, 0.8)
        self.assertEqual(memory.authority, "medium")
        self.assertEqual(memory.parents, ["mem_1", "mem_2", "mem_3"])
        self.assertEqual(
            sources_before,
            {memory_id: self.store.get(memory_id).to_dict() for memory_id in sources_before},
        )
        receipts = self.store.memory_write_receipts(memory.id)
        self.assertTrue(self.store.verify_memory_write_receipt_chain(receipts)["ok"])
        statement_object = receipts[0]["treeship_statement"]["object"]
        self.assertEqual(statement_object["parents"], memory.parents)
        self.assertEqual(statement_object["labels"], memory.labels)
        self.assertEqual(result["decision_event"]["action_id"], result["decision_id"])
        self.assertFalse(result["operator_identity_authenticated"])
        self.assertFalse(result["semantic_truth_guaranteed"])

        preview = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=2,
            evaluated_at="2026-08-01T00:08:00Z",
        )
        omission = next(
            (item for item in preview["omissions"] if item["memory_id"] == memory.id),
            None,
        )
        self.assertIsNone(omission)

    def test_generic_promotion_cannot_raise_consolidation_ceilings(self):
        result = self._admit(self._inspection())
        before = self._counts()

        with self.assertRaisesRegex(ValueError, "source trust and authority ceilings are immutable"):
            self.store.promote(result["canonical_memory_id"], actor_id="reviewer")

        memory = self.store.get(result["canonical_memory_id"])
        self.assertEqual(memory.trust, 0.8)
        self.assertEqual(memory.authority, "medium")
        self.assertEqual(before, self._counts())

    def test_exact_admission_replay_is_idempotent(self):
        inspection = self._inspection()
        first = self._admit(inspection)
        after_first = self._counts()

        second = self._admit(inspection)

        self.assertEqual(second["status"], "already_admitted")
        self.assertFalse(second["canonical_memory_written_this_run"])
        self.assertEqual(second["canonical_memory_id"], first["canonical_memory_id"])
        self.assertEqual(after_first, self._counts())

    def test_discard_is_terminal_idempotent_and_never_writes_memory(self):
        inspection = self._inspection()
        memories_before = self._counts()["memories"]

        first = discard_consolidation_summary(
            self.db_path,
            inspection,
            actor_id="reviewer",
            confirmed_inspection_id=inspection["confirmation_id"],
            reason="The deterministic rollup is not useful.",
            decided_at=DECIDED_AT,
        )
        after_first = self._counts()
        second = discard_consolidation_summary(
            self.db_path,
            inspection,
            actor_id="reviewer",
            confirmed_inspection_id=inspection["confirmation_id"],
            reason="The deterministic rollup is not useful.",
            decided_at=DECIDED_AT,
        )

        self.assertEqual(first["status"], "discarded")
        self.assertEqual(second["status"], "already_discarded")
        self.assertEqual(after_first, self._counts())
        self.assertEqual(self._counts()["memories"], memories_before)
        with self.assertRaisesRegex(ValueError, "already discarded"):
            self._admit(inspection)

    def test_discard_after_admission_is_rejected(self):
        inspection = self._inspection()
        self._admit(inspection)
        before = self._counts()

        with self.assertRaisesRegex(ValueError, "already admitted"):
            discard_consolidation_summary(
                self.db_path,
                inspection,
                actor_id="reviewer",
                confirmed_inspection_id=inspection["confirmation_id"],
                reason="Changed my mind.",
                decided_at=DECIDED_AT,
            )

        self.assertEqual(before, self._counts())

    def test_source_mutation_after_inspection_rejects_without_partial_write(self):
        inspection = self._inspection()
        self.store.revoke("mem_1", actor_id="reviewer", reason="stale")
        before = self._counts()

        with self.assertRaisesRegex(ValueError, "no longer active|receipt head changed"):
            self._admit(inspection)

        self.assertEqual(before, self._counts())
        with self.assertRaises(KeyError):
            self.store.get(inspection["target"]["memory_id"])

    def test_unreceipted_source_event_after_inspection_rejects_admission(self):
        inspection = self._inspection()
        self.store._append_event(
            "SOURCE_NOTE",
            actor_id="reviewer",
            memory_id="mem_1",
            payload={"note": "not covered by a memory receipt"},
        )
        self.store.conn.commit()
        before = self._counts()

        with self.assertRaisesRegex(ValueError, "latest event is not receipted"):
            self._admit(inspection)

        self.assertEqual(before, self._counts())
        with self.assertRaises(KeyError):
            self.store.get(inspection["target"]["memory_id"])

    def test_coordinated_ledger_rewrite_fails_live_recomputation(self):
        forged_text = "A coordinated local rewrite."
        forged_digest = f"sha256:{sha256_text(forged_text)}"
        job_path = default_job_ledger_path(self.db_path)
        summary_path = default_summary_ledger_path(self.db_path)
        jobs = [json.loads(line) for line in job_path.read_text(encoding="utf-8").splitlines()]
        summaries = [json.loads(line) for line in summary_path.read_text(encoding="utf-8").splitlines()]
        for job in jobs:
            job["summarizer"]["output_summary_content_digest"] = forged_digest
        summaries[0]["summary_text"] = forged_text
        summaries[0]["content_digest"] = forged_digest
        summaries[0]["summarizer"] = copy.deepcopy(jobs[-1]["summarizer"])
        job_path.write_text("".join(json.dumps(job, sort_keys=True) + "\n" for job in jobs), encoding="utf-8")
        summary_path.write_text(
            "".join(json.dumps(summary, sort_keys=True) + "\n" for summary in summaries),
            encoding="utf-8",
        )

        audit = consolidation_audit_report(job_path, summary_path)
        self.assertEqual(audit["records"][0]["audit_status"], "verified")
        with self.assertRaisesRegex(ValueError, "deterministic summary mismatch"):
            self._inspection()

    def test_tampered_target_cannot_raise_trust_or_authority(self):
        inspection = self._inspection()
        forged = copy.deepcopy(inspection)
        forged["target"]["trust"] = 1.0
        forged["target"]["authority"] = "high"
        forged["inspection_id"] = None
        forged["inspection_hash"] = None
        forged["confirmation_id"] = None
        forged["confirmation_hash"] = None
        forged = _finalize_inspection(forged)

        with self.assertRaisesRegex(ValueError, "canonical target changed"):
            self._admit(forged)

        with self.assertRaises(KeyError):
            self.store.get(forged["target"]["memory_id"])

    def test_lineage_tampering_breaks_receipt_chain_verification(self):
        result = self._admit(self._inspection())
        memory_id = result["canonical_memory_id"]
        self.store.conn.execute(
            "UPDATE memories SET parents_json = ? WHERE id = ?",
            (json.dumps(["mem_1"]), memory_id),
        )
        self.store.conn.commit()

        verification = self.store.verify_memory_write_receipt_chain(
            self.store.memory_write_receipts(memory_id)
        )

        self.assertFalse(verification["ok"])
        self.assertIn("parents diverged", verification["error"])

    def test_canonical_content_tampering_breaks_verification_and_replay(self):
        inspection = self._inspection()
        result = self._admit(inspection)
        memory_id = result["canonical_memory_id"]
        forged_content = "Forged canonical summary."
        self.store.conn.execute(
            "UPDATE memories SET content = ?, content_hash = ? WHERE id = ?",
            (forged_content, sha256_text(forged_content), memory_id),
        )
        self.store.conn.commit()

        verification = self.store.verify_memory_write_receipt_chain(
            self.store.memory_write_receipts(memory_id)
        )

        self.assertFalse(verification["ok"])
        self.assertIn("content diverged", verification["error"])
        with self.assertRaisesRegex(ValueError, "reviewed summary content"):
            self._admit(inspection)

    def test_concurrent_admission_creates_exactly_one_memory(self):
        inspection = self._inspection()

        def admit():
            return self._admit(inspection)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [future.result() for future in (executor.submit(admit), executor.submit(admit))]

        self.assertEqual(sorted(result["status"] for result in results), ["admitted", "already_admitted"])
        memory_id = inspection["target"]["memory_id"]
        self.assertEqual(
            self.store.conn.execute("SELECT COUNT(*) FROM memories WHERE id = ?", (memory_id,)).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.store.conn.execute(
                "SELECT COUNT(*) FROM events WHERE action_id = ?",
                (inspection["target"]["decision_id"],),
            ).fetchone()[0],
            1,
        )

    def test_failure_before_decision_event_rolls_back_canonical_memory(self):
        inspection = self._inspection()
        original_append = MemoryStore._append_event

        def fail_decision_event(store, event_type, **kwargs):
            if event_type == CONSOLIDATION_ADMITTED_EVENT:
                raise RuntimeError("simulated decision event failure")
            return original_append(store, event_type, **kwargs)

        before = self._counts()
        with patch.object(MemoryStore, "_append_event", new=fail_decision_event):
            with self.assertRaisesRegex(RuntimeError, "simulated decision event failure"):
                self._admit(inspection)

        self.assertEqual(before, self._counts())
        with self.assertRaises(KeyError):
            self.store.get(inspection["target"]["memory_id"])

    def test_result_write_failure_reports_committed_state_and_replays(self):
        inspection = self._inspection()
        inspection_path = self.root / "inspection.json"
        inspection_path.write_text(json.dumps(inspection), encoding="utf-8")
        blocked_parent = self.root / "not-a-directory"
        blocked_parent.write_text("blocked", encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "admit",
                    str(inspection_path),
                    "--actor-id",
                    "reviewer",
                    "--confirm-inspection",
                    inspection["confirmation_id"],
                    "--decided-at",
                    DECIDED_AT,
                    "--out",
                    str(blocked_parent / "result.json"),
                    "--summary-only",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("Status: admitted", output.getvalue())
        self.assertIn("Recovery: rerun the same confirmed decision", output.getvalue())
        self.assertEqual(self.store.get(inspection["target"]["memory_id"]).status, "active")
        replay = self._admit(inspection)
        self.assertEqual(replay["status"], "already_admitted")

    def test_cli_inspect_and_admit_write_private_artifacts(self):
        inspection_path = self.root / "inspection.json"
        inspect_output = io.StringIO()
        with redirect_stdout(inspect_output):
            inspect_exit = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "inspect",
                    self.summary_id,
                    "--inspected-at",
                    INSPECTED_AT,
                    "--out",
                    str(inspection_path),
                    "--summary-only",
                ]
            )
        inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
        result_path = self.root / "decision.json"
        admit_output = io.StringIO()
        with redirect_stdout(admit_output):
            admit_exit = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "admit",
                    str(inspection_path),
                    "--actor-id",
                    "reviewer",
                    "--confirm-inspection",
                    inspection["confirmation_id"],
                    "--decided-at",
                    DECIDED_AT,
                    "--out",
                    str(result_path),
                    "--summary-only",
                ]
            )

        self.assertEqual(inspect_exit, 0)
        self.assertEqual(admit_exit, 0)
        self.assertIn("Sources verified: 3/3", inspect_output.getvalue())
        self.assertIn("Status: admitted", admit_output.getvalue())
        self.assertTrue(result_path.is_file())
        self.assertEqual(result_path.stat().st_mode & 0o777, 0o600)

    def _inspection(self):
        return build_consolidation_summary_inspection(
            self.db_path,
            self.summary_id,
            inspected_at=INSPECTED_AT,
        )

    def _admit(self, inspection):
        return admit_consolidation_summary(
            self.db_path,
            inspection,
            actor_id="reviewer",
            confirmed_inspection_id=inspection["confirmation_id"],
            decided_at=DECIDED_AT,
        )

    def _remember(self, content, memory_id, memory_type, second):
        return self.store.remember(
            content,
            memory_type=memory_type,
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
            status="active",
            actor_id="human",
            actor_uri="human://operator",
            session_id="session://codex/release",
            memory_id=memory_id,
            created_at=f"2026-07-01T00:00:{second:02d}Z",
        )

    def _counts(self):
        return {
            "memories": self.store.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
            "events": self.store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "receipts": self.store.conn.execute("SELECT COUNT(*) FROM memory_write_receipts").fetchone()[0],
            "fts": self.store.conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0],
        }


if __name__ == "__main__":
    unittest.main()
