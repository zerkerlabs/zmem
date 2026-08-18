import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from zerker_memory.cli import build_parser, main
from zerker_memory.reason_premises import (
    MAX_PREMISE_CONTENT_BYTES,
    PREMISE_CONTENT_SCHEMA,
    PREMISE_LABEL,
    build_reason_premises,
    verify_reason_premises,
    write_reason_premises,
)
from zerker_memory.store import MemoryStore, stable_json


def premise_content(fact_id: str = "fact_tests_abc", *, predicate: str = "tests_passed") -> str:
    return stable_json(
        {
            "schema": PREMISE_CONTENT_SCHEMA,
            "fact": {
                "id": fact_id,
                "predicate": predicate,
                "arguments": ["commit_abc"],
                "authority": "tool-reported",
                "observed_at": "2026-08-14T11:00:00Z",
            },
        }
    )


class ReasonPremisesTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "memory.sqlite"
        self.store = MemoryStore(self.db_path)
        self.store.init()
        self.addCleanup(self.store.conn.close)

    def remember_premise(
        self,
        *,
        content: str | None = None,
        scope: str = "project:release",
        source_kind: str = "human",
        memory_id: str | None = None,
    ):
        return self.store.remember(
            content or premise_content(),
            memory_type="policy",
            scope=scope,
            source_kind=source_kind,
            actor_id="reviewer" if source_kind == "human" else "agent-a",
            labels=[PREMISE_LABEL],
            memory_id=memory_id,
        )

    def test_cli_parser_and_export_verify_round_trip(self):
        parsed = build_parser().parse_args(
            ["--db", str(self.db_path), "reason", "export", "--scope", "project:release", "--out", "premises.json"]
        )
        self.assertEqual(parsed.reason_command, "export")
        self.assertEqual(parsed.scope, "project:release")

        self.remember_premise(memory_id="mem_policy")
        output_path = Path(self.tempdir.name) / "premises.json"
        output = io.StringIO()
        with redirect_stdout(output):
            export_code = main(
                [
                    "--db",
                    str(self.db_path),
                    "reason",
                    "export",
                    "--scope",
                    "project:release",
                    "--out",
                    str(output_path),
                ]
            )
        export_result = json.loads(output.getvalue())
        self.assertEqual(export_code, 0)
        self.assertTrue(export_result["ok"])
        self.assertEqual(export_result["fact_count"], 1)
        self.assertTrue(output_path.is_file())

        output = io.StringIO()
        with redirect_stdout(output):
            verify_code = main(
                ["--db", str(self.db_path), "reason", "verify", str(output_path)]
            )
        verify_result = json.loads(output.getvalue())
        self.assertEqual(verify_code, 0)
        self.assertTrue(verify_result["ok"])
        self.assertTrue(verify_result["current"])

    def test_exports_only_active_governed_reason_premises_in_stable_order(self):
        second = self.remember_premise(content=premise_content("fact_z"), memory_id="mem_z")
        first = self.remember_premise(content=premise_content("fact_a"), memory_id="mem_a")
        quarantined = self.remember_premise(
            content=premise_content("fact_quarantined"),
            source_kind="agent",
            memory_id="mem_q",
        )
        self.store.remember(
            premise_content("fact_other_scope"),
            memory_type="policy",
            scope="project:other",
            source_kind="human",
            labels=[PREMISE_LABEL],
        )
        self.store.remember(
            premise_content("fact_unlabelled"),
            memory_type="policy",
            scope="project:release",
            source_kind="human",
        )

        artifact = build_reason_premises(self.db_path, scope="project:release")

        self.assertEqual([fact["id"] for fact in artifact["facts"]], ["fact_a", "fact_z"])
        self.assertEqual(
            [item["memory_id"] for item in artifact["provenance"]],
            [first.id, second.id],
        )
        self.assertEqual(
            artifact["withheld"],
            [{"memory_id": quarantined.id, "status": "quarantined", "reason": "not_active"}],
        )
        self.assertTrue(artifact["artifact_digest"].startswith("sha256:"))
        self.assertTrue(verify_reason_premises(self.db_path, artifact)["ok"])

    def test_agent_premise_requires_and_records_explicit_promotion(self):
        memory = self.remember_premise(source_kind="agent", memory_id="mem_agent")
        before = build_reason_premises(self.db_path, scope="project:release")
        self.assertEqual(before["facts"], [])

        self.store.promote(memory.id, actor_id="release-owner")
        after = build_reason_premises(self.db_path, scope="project:release")

        self.assertEqual([fact["id"] for fact in after["facts"]], ["fact_tests_abc"])
        self.assertEqual(after["provenance"][0]["governance_transition"], "promote")
        self.assertEqual(after["provenance"][0]["governing_actor_uri"], "actor://release-owner")
        self.assertEqual(after["provenance"][0]["write_receipt_count"], 2)

    def test_direct_status_tampering_cannot_activate_agent_premise(self):
        memory = self.remember_premise(source_kind="agent", memory_id="mem_agent")
        self.store.conn.execute("UPDATE memories SET status = 'active' WHERE id = ?", (memory.id,))
        self.store.conn.commit()

        with self.assertRaisesRegex(ValueError, "not active in its verified lifecycle"):
            build_reason_premises(self.db_path, scope="project:release")

    def test_content_tampering_fails_closed(self):
        memory = self.remember_premise(memory_id="mem_policy")
        replacement = premise_content("fact_tampered")
        self.store.conn.execute(
            "UPDATE memories SET content = ?, content_hash = ? WHERE id = ?",
            (replacement, "0" * 64, memory.id),
        )
        self.store.conn.commit()

        with self.assertRaisesRegex(ValueError, "content_hash diverged|content_hash mismatch"):
            build_reason_premises(self.db_path, scope="project:release")

    def test_malformed_active_premise_fails_without_partial_artifact(self):
        self.remember_premise(content='{"schema":"zerker.memory.reason-premise.v1","fact":', memory_id="mem_bad")
        output = Path(self.tempdir.name) / "premises.json"

        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            artifact = build_reason_premises(self.db_path, scope="project:release")
            write_reason_premises(output, artifact)

        self.assertFalse(output.exists())

    def test_oversized_active_premise_fails_closed(self):
        oversized = json.dumps(
            {
                "schema": PREMISE_CONTENT_SCHEMA,
                "fact": {
                    "id": "fact_large",
                    "predicate": "reviewed",
                    "arguments": ["x" * MAX_PREMISE_CONTENT_BYTES],
                    "authority": "human-authorized",
                    "observed_at": "2026-08-14T11:00:00Z",
                },
            }
        )
        self.remember_premise(content=oversized, memory_id="mem_large")

        with self.assertRaisesRegex(ValueError, "exceeds the .*byte content limit"):
            build_reason_premises(self.db_path, scope="project:release")

    def test_duplicate_reason_fact_ids_fail_closed(self):
        self.remember_premise(memory_id="mem_one")
        self.remember_premise(memory_id="mem_two")

        with self.assertRaisesRegex(ValueError, "duplicated by memories mem_one and mem_two"):
            build_reason_premises(self.db_path, scope="project:release")

    def test_export_keeps_one_locked_snapshot_when_action_receipts_exist(self):
        self.remember_premise(memory_id="mem_policy")
        self.store.inject(
            "commit_abc",
            agent_id="reader",
            risk="low",
            scope="project:release",
        )

        artifact = build_reason_premises(self.db_path, scope="project:release")

        self.assertEqual([fact["id"] for fact in artifact["facts"]], ["fact_tests_abc"])

    def test_export_is_byte_deterministic_for_unchanged_state(self):
        self.remember_premise(memory_id="mem_policy")
        first = build_reason_premises(self.db_path, scope="project:release")
        second = build_reason_premises(self.db_path, scope="project:release")
        first_path = Path(self.tempdir.name) / "first.json"
        second_path = Path(self.tempdir.name) / "second.json"
        write_reason_premises(first_path, first)
        write_reason_premises(second_path, second)

        self.assertEqual(first, second)
        self.assertEqual(first_path.read_bytes(), second_path.read_bytes())

    def test_verify_rejects_tampering_staleness_and_replay_after_revocation(self):
        memory = self.remember_premise(memory_id="mem_policy")
        artifact = build_reason_premises(self.db_path, scope="project:release")

        tampered = json.loads(json.dumps(artifact))
        tampered["facts"][0]["arguments"] = ["commit_other"]
        self.assertFalse(verify_reason_premises(self.db_path, tampered)["ok"])

        self.store.revoke(memory.id, actor_id="release-owner", reason="approval withdrawn")
        verification = verify_reason_premises(self.db_path, artifact)
        self.assertFalse(verification["ok"])
        self.assertIn("stale", verification["error"])

    def test_missing_receipt_and_wrong_memory_type_fail_closed(self):
        missing_receipt = self.remember_premise(memory_id="mem_missing")
        self.store.conn.execute("DELETE FROM memory_write_receipts WHERE memory_id = ?", (missing_receipt.id,))
        self.store.conn.commit()
        with self.assertRaisesRegex(ValueError, "no write-receipt chain"):
            build_reason_premises(self.db_path, scope="project:release")

        self.store.conn.close()
        self.store = MemoryStore(self.db_path)
        self.store.conn.execute("DELETE FROM memories WHERE id = ?", (missing_receipt.id,))
        self.store.conn.commit()
        wrong_type = self.store.remember(
            premise_content("fact_wrong_type"),
            memory_type="semantic",
            scope="project:release",
            source_kind="human",
            labels=[PREMISE_LABEL],
        )
        with self.assertRaisesRegex(ValueError, f"Reason premise memory {wrong_type.id} must have type 'policy'"):
            build_reason_premises(self.db_path, scope="project:release")


if __name__ == "__main__":
    unittest.main()
