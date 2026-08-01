import io
import json
import sqlite3
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import main
from zerker_memory.consolidation_live import (
    LIVE_CONSOLIDATION_PREVIEW_SCHEMA,
    build_live_consolidation_preview,
)
from zerker_memory.store import MemoryStore


EVALUATED_AT = "2026-08-01T00:00:00Z"


class LiveConsolidationPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "memory.sqlite"
        self.store = MemoryStore(self.db_path)
        self.store.init()

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    def test_preview_groups_verified_live_sources_without_writing_or_leaking_content(self):
        self._remember(
            "The launch owner is Ada.",
            memory_id="mem_ep_1",
            memory_type="episodic",
            trust=0.9,
            authority="medium",
        )
        self._remember(
            "The release gate requires proof.",
            memory_id="mem_sem_1",
            memory_type="semantic",
            trust=0.7,
            authority="low",
        )
        self._remember(
            "The canary passed.",
            memory_id="mem_ep_2",
            memory_type="episodic",
            trust=0.8,
            authority="high",
        )
        before = self._database_bytes()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=3,
            evaluated_at=EVALUATED_AT,
        )

        self.assertEqual(before, self._database_bytes())
        self.assertEqual(report["schema"], LIVE_CONSOLIDATION_PREVIEW_SCHEMA)
        self.assertTrue(report["ok"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["writes_performed"])
        self.assertFalse(report["summary_materialized"])
        self.assertFalse(report["canonical_memory_written"])
        self.assertEqual(report["ready_candidate_count"], 1)
        candidate = report["candidates"][0]
        self.assertEqual(candidate["session_id"], "session://codex/release")
        self.assertEqual(candidate["source_memory_ids"], ["mem_ep_1", "mem_sem_1", "mem_ep_2"])
        self.assertEqual(candidate["decision"], "ready-for-review")
        self.assertEqual(candidate["trust_ceiling"], 0.7)
        self.assertEqual(candidate["authority_ceiling"], "low")
        self.assertFalse(candidate["output_contract"]["canonical_memory_write_allowed"])
        self.assertEqual(candidate["output_contract"]["required_initial_status"], "quarantined")
        self.assertEqual(candidate["output_contract"]["required_initial_trust"], 0.0)
        self.assertEqual(candidate["output_contract"]["required_initial_authority"], "none")
        serialized = json.dumps(report)
        self.assertNotIn("launch owner", serialized)
        self.assertNotIn("release gate", serialized)
        self.assertNotIn("canary passed", serialized)

    def test_preview_lists_policy_procedural_nonactive_and_missing_receipt_omissions(self):
        self._remember(
            "Eligible source.",
            memory_id="mem_eligible",
            memory_type="episodic",
        )
        self._remember(
            "Policy source.",
            memory_id="mem_policy",
            memory_type="policy",
        )
        self._remember(
            "Procedure source.",
            memory_id="mem_procedure",
            memory_type="procedural",
        )
        self._remember(
            "Quarantined source.",
            memory_id="mem_quarantined",
            memory_type="semantic",
            status="quarantined",
        )
        self._remember(
            "Missing receipt source.",
            memory_id="mem_no_receipt",
            memory_type="semantic",
        )
        self.store.conn.execute(
            "DELETE FROM memory_write_receipts WHERE memory_id = ?",
            ("mem_no_receipt",),
        )
        self.store.conn.commit()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["included_source_count"], 1)
        omissions = {item["memory_id"]: item for item in report["omissions"]}
        self.assertIn("memory-type-not-consolidatable", omissions["mem_policy"]["reason_codes"])
        self.assertIn("memory-type-not-consolidatable", omissions["mem_procedure"]["reason_codes"])
        self.assertIn("status-not-active", omissions["mem_quarantined"]["reason_codes"])
        self.assertIn("missing-write-receipt", omissions["mem_no_receipt"]["reason_codes"])
        self.assertIn("missing-session-provenance", omissions["mem_no_receipt"]["reason_codes"])

    def test_preview_omits_a_source_with_a_tampered_receipt_chain(self):
        self._remember("Verified source.", memory_id="mem_verified", memory_type="episodic")
        self._remember("Tampered source.", memory_id="mem_tampered", memory_type="semantic")
        self.store.conn.execute(
            "UPDATE memory_write_receipts SET receipt_hash = ? WHERE memory_id = ?",
            ("0" * 64, "mem_tampered"),
        )
        self.store.conn.commit()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["included_source_count"], 1)
        omission = next(item for item in report["omissions"] if item["memory_id"] == "mem_tampered")
        self.assertIn("unverified-write-receipt-chain", omission["reason_codes"])
        self.assertIn("receipt_hash mismatch", omission["receipt_chain_error"])

    def test_preview_keeps_a_malformed_receipt_local_to_one_omission(self):
        self._remember("Verified source.", memory_id="mem_verified", memory_type="episodic")
        self._remember("Malformed source.", memory_id="mem_malformed", memory_type="semantic")
        self.store.conn.execute(
            "UPDATE memory_write_receipts SET treeship_statement_json = ? WHERE memory_id = ?",
            ("{", "mem_malformed"),
        )
        self.store.conn.commit()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["included_source_count"], 1)
        omission = next(item for item in report["omissions"] if item["memory_id"] == "mem_malformed")
        self.assertIn("unverified-write-receipt-chain", omission["reason_codes"])
        self.assertNotIn("missing-write-receipt", omission["reason_codes"])

    def test_preview_omits_out_of_band_memory_row_drift(self):
        self._remember("Verified source.", memory_id="mem_verified", memory_type="episodic")
        self._remember("Drifted source.", memory_id="mem_drifted", memory_type="semantic")
        self.store.conn.execute(
            "UPDATE memories SET trust = ?, authority = ?, content = ?, content_hash = ? WHERE id = ?",
            (1.0, "policy", "Rewritten without a receipt.", "0" * 64, "mem_drifted"),
        )
        self.store.conn.commit()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["included_source_count"], 1)
        omission = next(item for item in report["omissions"] if item["memory_id"] == "mem_drifted")
        self.assertIn("memory-row-receipt-divergence", omission["reason_codes"])
        self.assertEqual(
            omission["row_receipt_mismatch_fields"],
            ["authority", "content_digest", "content_hash", "trust"],
        )
        self.assertNotIn("Rewritten without a receipt", json.dumps(report))

    def test_preview_rejects_global_event_chain_tampering(self):
        self._remember("Source.", memory_id="mem_source", memory_type="episodic")
        self.store.conn.execute(
            "UPDATE events SET payload_json = ? WHERE seq = 1",
            ('{"tampered":true}',),
        )
        self.store.conn.commit()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["error"]["code"], "database_read_failed")
        self.assertIn("event payload hash mismatch", report["error"]["message"])

    def test_preview_omits_a_source_with_a_newer_unreceipted_event(self):
        self._remember("Source.", memory_id="mem_source", memory_type="episodic")
        self.store._append_event(
            "ANNOTATED",
            actor_id="operator",
            memory_id="mem_source",
            payload={"note_hash": "sha256:" + "1" * 64},
        )
        self.store.conn.commit()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["included_source_count"], 0)
        self.assertIn("latest-memory-event-unreceipted", report["omissions"][0]["reason_codes"])

    def test_preview_does_not_mix_distinct_origin_actors_in_one_session(self):
        self._remember("Actor A one.", memory_id="mem_a_1", memory_type="episodic")
        self._remember("Actor A two.", memory_id="mem_a_2", memory_type="semantic")
        self._remember(
            "Actor B one.",
            memory_id="mem_b_1",
            memory_type="episodic",
            actor_uri="agent://other",
        )

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=2,
            evaluated_at=EVALUATED_AT,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["ready_candidate_count"], 1)
        candidates = {candidate["origin_actor_uri"]: candidate for candidate in report["candidates"]}
        self.assertEqual(candidates["human://operator"]["source_count"], 2)
        self.assertEqual(candidates["agent://other"]["source_count"], 1)

    def test_preview_accepts_a_receipted_promotion_and_keeps_origin_provenance(self):
        self._remember(
            "Agent-proposed fact.",
            memory_id="mem_promoted",
            memory_type="semantic",
            status="quarantined",
            trust=0.4,
            authority="low",
            actor_uri="agent://proposer",
        )
        promoted = self.store.promote("mem_promoted", actor_id="human")

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertEqual(promoted.status, "active")
        self.assertEqual(promoted.trust, 0.9)
        self.assertTrue(report["ok"])
        self.assertEqual(report["included_source_count"], 1)
        self.assertEqual(report["omitted_source_count"], 0)
        candidate = report["candidates"][0]
        self.assertEqual(candidate["origin_actor_uri"], "agent://proposer")
        self.assertEqual(candidate["trust_ceiling"], 0.9)
        self.assertEqual(candidate["authority_ceiling"], "medium")

    def test_preview_keeps_malformed_row_metadata_local_to_one_omission(self):
        self._remember("Verified source.", memory_id="mem_verified", memory_type="episodic")
        self._remember("Malformed source.", memory_id="mem_malformed", memory_type="semantic")
        self.store.conn.execute(
            "UPDATE memories SET trust = ?, created_at = ?, updated_at = ? WHERE id = ?",
            ("not-a-number", "not-a-time", "", "mem_malformed"),
        )
        self.store.conn.commit()

        report = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["included_source_count"], 1)
        omission = next(item for item in report["omissions"] if item["memory_id"] == "mem_malformed")
        self.assertIn("invalid-trust-value", omission["reason_codes"])
        self.assertIn("invalid-created-at", omission["reason_codes"])
        self.assertIn("invalid-updated-at", omission["reason_codes"])

    def test_preview_uses_exact_scope_and_is_deterministic(self):
        self._remember("Project one.", memory_id="mem_project_1", memory_type="episodic")
        self._remember("Project two.", memory_id="mem_project_2", memory_type="semantic")
        self._remember(
            "Global source.",
            memory_id="mem_global",
            memory_type="episodic",
            scope="global",
        )

        first = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=2,
            evaluated_at=EVALUATED_AT,
        )
        second = build_live_consolidation_preview(
            self.db_path,
            scope="project",
            min_source_children=2,
            evaluated_at=EVALUATED_AT,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["included_source_count"], 2)
        self.assertNotIn("mem_global", json.dumps(first))
        self.assertEqual(first["ready_candidate_count"], 1)

    def test_preview_identity_excludes_observational_timestamp(self):
        self._remember("Source.", memory_id="mem_source", memory_type="episodic")

        with patch(
            "zerker_memory.consolidation_live.now_iso",
            side_effect=["2026-08-01T00:00:00Z", "2026-08-01T01:00:00Z"],
        ):
            first = build_live_consolidation_preview(self.db_path, scope="project")
            second = build_live_consolidation_preview(self.db_path, scope="project")

        self.assertNotEqual(first["evaluated_at"], second["evaluated_at"])
        self.assertEqual(first["preview_hash"], second["preview_hash"])
        self.assertEqual(first["preview_id"], second["preview_id"])

    def test_missing_database_is_not_created(self):
        missing_path = self.root / "missing.sqlite"

        report = build_live_consolidation_preview(
            missing_path,
            scope="project",
            evaluated_at=EVALUATED_AT,
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["error"]["code"], "database_not_found")
        self.assertFalse(missing_path.exists())

    def test_read_only_store_rejects_sqlite_writes(self):
        self._remember("Source.", memory_id="mem_source", memory_type="episodic")
        read_only_store = MemoryStore.open_read_only(self.db_path)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                read_only_store.conn.execute(
                    "UPDATE memories SET trust = 1.0 WHERE id = ?",
                    ("mem_source",),
                )
        finally:
            read_only_store.conn.close()

    def test_cli_preview_writes_secure_artifact_and_summary(self):
        self._remember("Source one.", memory_id="mem_1", memory_type="episodic")
        self._remember("Source two.", memory_id="mem_2", memory_type="semantic")
        output_path = self.root / "preview.json"
        self.store.conn.close()
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "preview",
                    "--scope",
                    "project",
                    "--min-sources",
                    "2",
                    "--evaluated-at",
                    EVALUATED_AT,
                    "--out",
                    str(output_path),
                    "--summary-only",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(output_path.is_file())
        self.assertEqual(stat.S_IMODE(output_path.stat().st_mode), 0o600)
        self.assertIn("Candidates: 1 (1 ready, 0 waiting)", output.getvalue())
        self.assertIn("Summary writes: none", output.getvalue())
        self.assertIn("Canonical memory writes: none", output.getvalue())
        artifact = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(artifact["schema"], LIVE_CONSOLIDATION_PREVIEW_SCHEMA)
        self.store = MemoryStore(self.db_path)

    def test_cli_existing_artifact_requires_force(self):
        self._remember("Source one.", memory_id="mem_1", memory_type="episodic")
        output_path = self.root / "preview.json"
        output_path.write_text("occupied", encoding="utf-8")
        self.store.conn.close()
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "consolidation",
                    "preview",
                    "--scope",
                    "project",
                    "--out",
                    str(output_path),
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(output_path.read_text(encoding="utf-8"), "occupied")
        self.assertIn("already exists", output.getvalue())
        self.store = MemoryStore(self.db_path)

    def _remember(
        self,
        content: str,
        *,
        memory_id: str,
        memory_type: str,
        scope: str = "project",
        status: str = "active",
        trust: float = 0.8,
        authority: str = "medium",
        actor_uri: str = "human://operator",
    ):
        sequence = int(memory_id.rsplit("_", 1)[-1]) if memory_id.rsplit("_", 1)[-1].isdigit() else 1
        return self.store.remember(
            content,
            memory_type=memory_type,
            scope=scope,
            source_kind="human",
            status=status,
            trust=trust,
            authority=authority,
            actor_id="human",
            actor_uri=actor_uri,
            session_id="session://codex/release",
            memory_id=memory_id,
            created_at=f"2026-07-01T00:00:{sequence:02d}Z",
        )

    def _database_bytes(self) -> dict[str, bytes]:
        return {
            path.name: path.read_bytes()
            for path in sorted(self.root.iterdir())
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
