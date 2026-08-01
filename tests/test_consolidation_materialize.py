import io
import json
import os
import sqlite3
import stat
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

from zerker_memory.cli import main
from zerker_memory.consolidation import (
    append_consolidation_job_record,
    consolidation_audit_report,
    load_consolidation_job_records,
    load_consolidation_summary_records,
)
from zerker_memory.consolidation_live import (
    build_live_consolidation_preview,
    write_live_consolidation_preview,
)
from zerker_memory.consolidation_materialize import (
    LIVE_CONSOLIDATION_MATERIALIZATION_SCHEMA,
    database_protected_paths,
    default_job_ledger_path,
    default_summary_ledger_path,
    consolidation_ledger_recovery_dir,
    materialize_live_consolidation_candidate,
    validate_consolidation_artifact_destination,
    _consolidation_ledger_locks,
)
from zerker_memory.store import MemoryStore, sha256_text


EVALUATED_AT = "2026-08-01T00:00:00Z"
COMPLETED_AT = "2026-08-01T00:05:00Z"


class LiveConsolidationMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "memory.sqlite"
        self.store = MemoryStore(self.db_path)
        self.store.init()

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    def test_materializes_one_confirmed_candidate_without_writing_canonical_memory(self):
        preview = self._ready_preview()
        candidate = preview["candidates"][0]
        before = self._database_files()

        result = self._materialize(preview, candidate["candidate_id"])

        self.assertEqual(before, self._database_files())
        self.assertEqual(result["schema"], LIVE_CONSOLIDATION_MATERIALIZATION_SCHEMA)
        self.assertEqual(result["status"], "materialized")
        self.assertFalse(result["canonical_memory_written"])
        self.assertEqual(result["admission"]["status"], "quarantined")
        self.assertEqual(result["admission"]["trust"], 0.0)
        self.assertEqual(result["admission"]["authority"], "none")
        self.assertEqual(result["ledger_writes"]["job_records_appended"], 2)
        self.assertEqual(result["ledger_writes"]["summary_records_appended"], 1)
        self.assertEqual(result["audit"]["audit_status"], "verified")

        job_ledger = default_job_ledger_path(self.db_path)
        summary_ledger = default_summary_ledger_path(self.db_path)
        jobs = load_consolidation_job_records(job_ledger)
        summaries = load_consolidation_summary_records(summary_ledger)
        self.assertEqual([job.status for job in jobs], ["pending", "completed"])
        self.assertEqual(len(summaries), 1)
        summary = summaries[0]
        self.assertEqual(summary["source_preview"]["preview_id"], preview["preview_id"])
        self.assertEqual(summary["source_child_digests"], candidate["source_content_digests"])
        self.assertEqual(summary["admission"], result["admission"])
        self.assertFalse(summary["canonical_memory_written"])
        self.assertEqual(stat.S_IMODE(job_ledger.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(summary_ledger.stat().st_mode), 0o600)
        with self.assertRaises(KeyError):
            self.store.get(result["summary_id"])
        serialized_result = json.dumps(result)
        self.assertNotIn("launch owner", serialized_result)
        self.assertNotIn("padded source", serialized_result)

    def test_materialization_is_idempotent_for_the_same_verified_source_set(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]
        first = self._materialize(preview, candidate_id)
        job_ledger = default_job_ledger_path(self.db_path)
        summary_ledger = default_summary_ledger_path(self.db_path)
        before = (job_ledger.read_bytes(), summary_ledger.read_bytes())

        second = self._materialize(preview, candidate_id)

        self.assertEqual(second["status"], "already_materialized")
        self.assertEqual(second["job_id"], first["job_id"])
        self.assertEqual(second["summary_id"], first["summary_id"])
        self.assertEqual(second["ledger_writes"]["job_records_appended"], 0)
        self.assertEqual(second["ledger_writes"]["summary_records_appended"], 0)
        self.assertEqual(before, (job_ledger.read_bytes(), summary_ledger.read_bytes()))

    def test_confirmation_mismatch_rejects_before_ledger_creation(self):
        preview = self._ready_preview()

        with self.assertRaisesRegex(ValueError, "confirmation mismatch"):
            materialize_live_consolidation_candidate(
                self.db_path,
                preview,
                candidate_id=preview["candidates"][0]["candidate_id"],
                actor_id="operator",
                confirmed_preview_id="consolidation-preview:wrong",
                completed_at=COMPLETED_AT,
            )

        self.assertFalse(default_job_ledger_path(self.db_path).exists())
        self.assertFalse(default_summary_ledger_path(self.db_path).exists())

    def test_stale_preview_rejects_after_live_source_set_changes(self):
        preview = self._ready_preview()
        self._remember("New source after preview.", "mem_4", "episodic", 4)

        with self.assertRaisesRegex(ValueError, "preview is stale"):
            self._materialize(preview, preview["candidates"][0]["candidate_id"])

        self.assertFalse(default_job_ledger_path(self.db_path).exists())

    def test_waiting_candidate_cannot_materialize(self):
        self._remember("Only source.", "mem_1", "episodic", 1)
        preview = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=3,
            evaluated_at=EVALUATED_AT,
        )

        with self.assertRaisesRegex(ValueError, "not ready for review"):
            self._materialize(preview, preview["candidates"][0]["candidate_id"])

    def test_audit_rejects_tampered_live_admission_binding(self):
        preview = self._ready_preview()
        result = self._materialize(preview, preview["candidates"][0]["candidate_id"])
        summary_ledger = default_summary_ledger_path(self.db_path)
        summary = load_consolidation_summary_records(summary_ledger)[0]
        summary["admission"]["trust"] = 1.0
        with summary_ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, sort_keys=True) + "\n")

        audit = consolidation_audit_report(
            default_job_ledger_path(self.db_path),
            summary_ledger,
        )

        record = next(item for item in audit["records"] if item["job_id"] == result["job_id"])
        self.assertEqual(record["audit_status"], "mismatch")
        self.assertIn(
            "admission-contract-mismatch",
            record["summary_mismatch_reasons"][result["summary_id"]],
        )
        self.assertIn(
            "admission-safety-boundary-mismatch",
            record["summary_mismatch_reasons"][result["summary_id"]],
        )

    def test_ledger_paths_cannot_alias_or_symlink_to_the_database(self):
        preview = self._ready_preview()
        before = self.db_path.read_bytes()

        with self.assertRaisesRegex(ValueError, "cannot alias the memory database"):
            materialize_live_consolidation_candidate(
                self.db_path,
                preview,
                candidate_id=preview["candidates"][0]["candidate_id"],
                actor_id="operator",
                confirmed_preview_id=preview["confirmation_id"],
                job_ledger_path=self.db_path,
                completed_at=COMPLETED_AT,
            )

        target = self.root / "redirected.jsonl"
        target.touch(mode=0o600)
        symlink = self.root / "jobs-link.jsonl"
        symlink.symlink_to(target)
        parent_mode = stat.S_IMODE(self.root.stat().st_mode)
        with self.assertRaisesRegex(ValueError, "cannot be a symlink"):
            materialize_live_consolidation_candidate(
                self.db_path,
                preview,
                candidate_id=preview["candidates"][0]["candidate_id"],
                actor_id="operator",
                confirmed_preview_id=preview["confirmation_id"],
                job_ledger_path=symlink,
                completed_at=COMPLETED_AT,
            )
        self.assertEqual(self.db_path.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), parent_mode)

    def test_cli_force_cannot_replace_database_with_result_artifact(self):
        preview = self._ready_preview()
        preview_path = self.root / "preview.json"
        write_live_consolidation_preview(preview_path, preview)
        before = self.db_path.read_bytes()
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "materialize",
                    str(preview_path),
                    "--select",
                    preview["candidates"][0]["candidate_id"],
                    "--actor-id",
                    "operator",
                    "--confirm-preview",
                    preview["confirmation_id"],
                    "--completed-at",
                    COMPLETED_AT,
                    "--out",
                    str(self.db_path),
                    "--force",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("cannot replace protected path", output.getvalue())
        self.assertEqual(self.db_path.read_bytes(), before)
        self.assertFalse(default_job_ledger_path(self.db_path).exists())

    def test_retry_recovers_pending_job_when_summary_append_was_interrupted(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]
        with patch(
            "zerker_memory.consolidation_materialize.append_consolidation_summary_record",
            side_effect=OSError("simulated summary append failure"),
        ):
            with self.assertRaisesRegex(OSError, "simulated summary append failure"):
                self._materialize(preview, candidate_id)
        self.assertEqual(
            [job.status for job in load_consolidation_job_records(default_job_ledger_path(self.db_path))],
            ["pending"],
        )

        recovered = self._materialize(preview, candidate_id)

        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(recovered["ledger_writes"], {
            "job_records_appended": 1,
            "summary_records_appended": 1,
        })
        self.assertEqual(recovered["audit"]["audit_status"], "verified")

    def test_retry_recovers_pending_job_when_completed_append_was_interrupted(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]

        def fail_completed(path, job):
            if job.status == "completed":
                raise OSError("simulated completed append failure")
            append_consolidation_job_record(path, job)

        with patch(
            "zerker_memory.consolidation_materialize.append_consolidation_job_record",
            side_effect=fail_completed,
        ):
            with self.assertRaisesRegex(OSError, "simulated completed append failure"):
                self._materialize(preview, candidate_id)
        self.assertEqual(
            [job.status for job in load_consolidation_job_records(default_job_ledger_path(self.db_path))],
            ["pending"],
        )
        self.assertEqual(
            len(load_consolidation_summary_records(default_summary_ledger_path(self.db_path))),
            1,
        )

        recovered = self._materialize(preview, candidate_id)

        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(recovered["ledger_writes"], {
            "job_records_appended": 1,
            "summary_records_appended": 0,
        })
        self.assertEqual(recovered["audit"]["audit_status"], "verified")

    def test_partial_ledger_append_rolls_back_to_the_last_complete_record(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]
        real_write = os.write
        write_count = 0

        def short_write_then_fail(fd, payload):
            nonlocal write_count
            write_count += 1
            if write_count == 1:
                return real_write(fd, payload[:11])
            raise OSError("simulated disk-full append")

        with patch("zerker_memory.consolidation.os.write", side_effect=short_write_then_fail):
            with self.assertRaisesRegex(OSError, "simulated disk-full append"):
                self._materialize(preview, candidate_id)

        job_ledger = default_job_ledger_path(self.db_path)
        self.assertEqual(job_ledger.read_bytes(), b"")
        recovered = self._materialize(preview, candidate_id)
        self.assertEqual(recovered["status"], "materialized")
        self.assertEqual(recovered["audit"]["audit_status"], "verified")

    def test_abrupt_exit_fragment_is_truncated_before_retry_loads_the_ledger(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]
        with patch(
            "zerker_memory.consolidation_materialize.append_consolidation_summary_record",
            side_effect=OSError("stop after pending"),
        ):
            with self.assertRaisesRegex(OSError, "stop after pending"):
                self._materialize(preview, candidate_id)

        job_ledger = default_job_ledger_path(self.db_path)
        with job_ledger.open("ab") as handle:
            handle.write(b'{"schema":"')
            handle.flush()
            os.fsync(handle.fileno())

        recovered = self._materialize(preview, candidate_id)

        self.assertEqual(recovered["status"], "recovered")
        self.assertTrue(recovered["ledger_recovery"]["job"]["recovered"])
        self.assertEqual(recovered["ledger_recovery"]["job"]["truncated_bytes"], 11)
        self.assertEqual(recovered["ledger_recovery"]["job"]["receipt_status"], "completed")
        self.assertTrue(Path(recovered["ledger_recovery"]["job"]["receipt_path"]).is_file())
        self.assertFalse(recovered["ledger_recovery"]["summary"]["recovered"])
        self.assertEqual(recovered["audit"]["audit_status"], "verified")

    def test_recovery_receipt_survives_later_stale_preview_failure(self):
        preview = self._ready_preview()
        job_ledger = default_job_ledger_path(self.db_path)
        job_ledger.parent.mkdir(mode=0o700)
        job_ledger.write_bytes(b'{"schema":"')
        job_ledger.chmod(0o600)
        self._remember("Source added after review.", "mem_4", "episodic", 4)

        with self.assertRaisesRegex(ValueError, "durable ledger recovery receipt"):
            self._materialize(preview, preview["candidates"][0]["candidate_id"])

        receipts = list(consolidation_ledger_recovery_dir(job_ledger).glob("*.json"))
        self.assertEqual(job_ledger.read_bytes(), b"")
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["truncated_bytes"], 11)

    def test_shared_summary_ledger_has_its_own_cross_job_lock(self):
        job_a = self.root / "job-a.jsonl"
        job_b = self.root / "job-b.jsonl"
        summary = self.root / "shared-summary.jsonl"
        first_acquired = Event()
        release_first = Event()
        second_acquired = Event()

        def hold_first():
            with _consolidation_ledger_locks((job_a, summary)):
                first_acquired.set()
                release_first.wait(timeout=2)

        def hold_second():
            with _consolidation_ledger_locks((job_b, summary)):
                second_acquired.set()

        first = Thread(target=hold_first)
        second = Thread(target=hold_second)
        first.start()
        self.assertTrue(first_acquired.wait(timeout=1))
        second.start()
        self.assertFalse(second_acquired.wait(timeout=0.05))
        release_first.set()
        self.assertTrue(second_acquired.wait(timeout=1))
        first.join(timeout=1)
        second.join(timeout=1)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())

    def test_concurrent_materialization_appends_one_transition(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self._materialize(preview, candidate_id), range(2)))

        self.assertEqual({result["status"] for result in results}, {"materialized", "already_materialized"})
        self.assertEqual(
            [job.status for job in load_consolidation_job_records(default_job_ledger_path(self.db_path))],
            ["pending", "completed"],
        )
        self.assertEqual(
            len(load_consolidation_summary_records(default_summary_ledger_path(self.db_path))),
            1,
        )

    def test_source_database_is_writer_locked_until_ledger_commit(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]
        write_attempts = []

        def append_with_write_attempt(path, job):
            connection = sqlite3.connect(self.db_path, timeout=0.01)
            try:
                with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                    connection.execute(
                        "UPDATE memories SET status = 'revoked' WHERE id = 'mem_1'"
                    )
                    connection.commit()
                write_attempts.append("blocked")
            finally:
                connection.close()
            append_consolidation_job_record(path, job)

        with patch(
            "zerker_memory.consolidation_materialize.append_consolidation_job_record",
            side_effect=append_with_write_attempt,
        ):
            result = self._materialize(preview, candidate_id)

        self.assertEqual(write_attempts, ["blocked", "blocked"])
        self.assertEqual(result["database_event_merkle_root_before"], result["database_event_merkle_root_after"])
        self.assertEqual(self.store.get("mem_1").status, "active")

    def test_audit_rejects_forged_replacement_summary_with_recomputed_digest(self):
        preview = self._ready_preview()
        result = self._materialize(preview, preview["candidates"][0]["candidate_id"])
        summary_ledger = default_summary_ledger_path(self.db_path)
        forged = load_consolidation_summary_records(summary_ledger)[0]
        forged["summary_text"] = "Forged replacement summary."
        forged["content_digest"] = f"sha256:{sha256_text(forged['summary_text'])}"
        with summary_ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(forged, sort_keys=True) + "\n")

        audit = consolidation_audit_report(default_job_ledger_path(self.db_path), summary_ledger)

        record = next(item for item in audit["records"] if item["job_id"] == result["job_id"])
        reasons = record["summary_mismatch_reasons"][result["summary_id"]]
        self.assertEqual(record["audit_status"], "mismatch")
        self.assertIn("summary-content-commitment-mismatch", reasons)
        self.assertIn("duplicate-summary-record", reasons)
        self.assertEqual(audit["duplicate_summary_record_count"], 1)

    def test_audit_rejects_completed_only_job_history(self):
        preview = self._ready_preview()
        result = self._materialize(preview, preview["candidates"][0]["candidate_id"])
        job_ledger = default_job_ledger_path(self.db_path)
        lines = job_ledger.read_text(encoding="utf-8").splitlines()
        job_ledger.write_text(lines[-1] + "\n", encoding="utf-8")

        audit = consolidation_audit_report(job_ledger, default_summary_ledger_path(self.db_path))
        record = next(item for item in audit["records"] if item["job_id"] == result["job_id"])

        self.assertEqual(audit["invalid_job_history_count"], 1)
        self.assertTrue(record["invalid_job_history"])
        self.assertEqual(record["audit_status"], "mismatch")

    def test_audit_rejects_immutable_job_binding_drift(self):
        preview = self._ready_preview()
        result = self._materialize(preview, preview["candidates"][0]["candidate_id"])
        job_ledger = default_job_ledger_path(self.db_path)
        records = [
            json.loads(line)
            for line in job_ledger.read_text(encoding="utf-8").splitlines()
        ]
        records[0]["scope"] = "tampered-scope"
        job_ledger.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )

        audit = consolidation_audit_report(job_ledger, default_summary_ledger_path(self.db_path))
        record = next(item for item in audit["records"] if item["job_id"] == result["job_id"])

        self.assertEqual(audit["invalid_job_history_count"], 1)
        self.assertTrue(record["invalid_job_history"])
        self.assertEqual(record["audit_status"], "mismatch")

    def test_resolved_database_sidecars_are_protected_for_symlinked_database_path(self):
        alias = self.root / "memory-alias.sqlite"
        alias.symlink_to(self.db_path)
        real_wal = Path(f"{self.db_path}-wal")

        with self.assertRaisesRegex(ValueError, "cannot replace protected path"):
            validate_consolidation_artifact_destination(
                real_wal,
                protected_paths=database_protected_paths(alias),
                force=True,
            )

    def test_audit_cli_fails_for_pending_and_orphan_records(self):
        preview = self._ready_preview()
        candidate_id = preview["candidates"][0]["candidate_id"]
        with patch(
            "zerker_memory.consolidation_materialize.append_consolidation_summary_record",
            side_effect=OSError("stop after pending"),
        ):
            with self.assertRaises(OSError):
                self._materialize(preview, candidate_id)
        pending_output = io.StringIO()
        with redirect_stdout(pending_output):
            pending_exit = main(
                ["--db", str(self.db_path), "consolidation", "audit", "--summary-only"]
            )
        self.assertEqual(pending_exit, 1)
        self.assertIn("Incomplete: 1", pending_output.getvalue())

        recovered = self._materialize(preview, candidate_id)
        default_job_ledger_path(self.db_path).unlink()
        orphan_output = io.StringIO()
        with redirect_stdout(orphan_output):
            orphan_exit = main(
                ["--db", str(self.db_path), "consolidation", "audit", "--summary-only"]
            )
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(orphan_exit, 1)
        self.assertIn("Orphan summaries: 1", orphan_output.getvalue())

    def test_cli_materialize_and_audit_are_compact_and_write_private_result(self):
        preview = self._ready_preview()
        preview_path = self.root / "preview.json"
        result_path = self.root / "result.json"
        write_live_consolidation_preview(preview_path, preview)
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "materialize",
                    str(preview_path),
                    "--select",
                    preview["candidates"][0]["candidate_id"],
                    "--actor-id",
                    "operator",
                    "--confirm-preview",
                    preview["confirmation_id"],
                    "--completed-at",
                    COMPLETED_AT,
                    "--out",
                    str(result_path),
                    "--summary-only",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("Ledger audit: verified", output.getvalue())
        self.assertIn("Canonical memory written: no", output.getvalue())
        self.assertEqual(stat.S_IMODE(result_path.stat().st_mode), 0o600)
        audit_output = io.StringIO()
        with redirect_stdout(audit_output):
            audit_exit = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "audit",
                    "--summary-only",
                ]
            )
        self.assertEqual(audit_exit, 0)
        self.assertIn("Verified: 1", audit_output.getvalue())
        self.assertIn("Incomplete: 0", audit_output.getvalue())

    def _ready_preview(self):
        self._remember("The launch owner is Ada.", "mem_1", "episodic", 1)
        self._remember("  Padded source content.  ", "mem_2", "semantic", 2)
        self._remember("The rollback gate is required.", "mem_3", "episodic", 3)
        return build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=3,
            evaluated_at=EVALUATED_AT,
        )

    def _materialize(self, preview, candidate_id):
        return materialize_live_consolidation_candidate(
            self.db_path,
            preview,
            candidate_id=candidate_id,
            actor_id="operator",
            confirmed_preview_id=preview["confirmation_id"],
            completed_at=COMPLETED_AT,
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

    def _database_files(self):
        return {
            path.name: path.read_bytes()
            for path in sorted(self.root.glob("memory.sqlite*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
