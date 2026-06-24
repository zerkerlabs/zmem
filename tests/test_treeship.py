import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zerker_memory.store import sha256_text, stable_json
from zerker_memory.treeship import (
    DEFAULT_TREESHIP_COMMAND_TEMPLATE,
    TREESHIP_STATEMENT_KIND,
    TREESHIP_STATEMENT_SCHEMA,
    TREESHIP_STATEMENT_SCHEMA_VERSION,
    attest_treeship_payload_digest,
    build_treeship_publish_command,
    publish_treeship_statement,
    treeship_cli_status,
    to_treeship_statement,
)


class TreeshipAdapterTest(unittest.TestCase):
    @staticmethod
    def _valid_bundle() -> dict:
        bundle = {
            "bundle_schema": "zerker.receipt_bundle.v1",
            "hash_alg": "sha256",
            "merkle_alg": "binary-sha256-v1",
            "created_at": "2026-05-25T12:00:01Z",
            "action_id": "act_bundle",
            "receipt": {
                "action_id": "act_bundle",
                "agent_id": "codex",
                "task_hash": "task_sha256",
                "retrieved_memory_ids": ["mem_a"],
                "injected_memory_ids": ["mem_a"],
                "withheld_memory_ids": [],
                "policy_checks": ["mem_a"],
                "merkle_root": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6",
                "created_at": "2026-05-25T12:00:00Z",
            },
            "supporting_memory_ids": ["mem_a"],
            "supporting_memories": [],
            "supporting_events": [
                {
                    "event_hash": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6",
                }
            ],
            "proof": {
                "event_count": 1,
                "computed_merkle_root": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6",
                "receipt_merkle_root": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6",
                "verified": True,
            },
        }
        bundle["bundle_hash"] = sha256_text(stable_json(bundle))
        return bundle

    def test_converts_memory_action_receipt_dict_to_statement(self):
        statement = to_treeship_statement(
            {
                "action_id": "act_123",
                "agent_id": "codex",
                "task_hash": "task_sha256",
                "retrieved_memory_ids": ["mem_a", "mem_b"],
                "injected_memory_ids": ["mem_a"],
                "withheld_memory_ids": ["mem_b"],
                "policy_checks": ["mem_a"],
                "merkle_root": "root_sha256",
                "hash_alg": "sha256",
                "merkle_alg": "binary-sha256-v1",
                "created_at": "2026-05-25T12:00:00Z",
            }
        )

        self.assertEqual(statement["schema"], TREESHIP_STATEMENT_SCHEMA)
        self.assertEqual(statement["schema_version"], TREESHIP_STATEMENT_SCHEMA_VERSION)
        self.assertEqual(statement["statement_version"], "1")
        self.assertEqual(statement["kind"], TREESHIP_STATEMENT_KIND)
        self.assertEqual(statement["subject"], {"type": "memory_action", "id": "act_123", "agent_id": "codex"})
        self.assertEqual(statement["predicate"], "memory.receipt.generated")
        self.assertEqual(statement["object"]["injected_memory_ids"], ["mem_a"])
        self.assertEqual(statement["object"]["withheld_memory_ids"], ["mem_b"])
        self.assertEqual(
            statement["evidence"],
            {
                "task_hash": "task_sha256",
                "merkle_root": "root_sha256",
                "hash_alg": "sha256",
                "merkle_alg": "binary-sha256-v1",
            },
        )
        self.assertEqual(statement["source"]["receipt_type"], "MemoryActionReceipt")
        self.assertEqual(statement["source"]["receipt"]["action_id"], "act_123")
        self.assertEqual(statement["source"]["receipt"]["hash_alg"], "sha256")
        self.assertEqual(statement["source"]["receipt"]["merkle_alg"], "binary-sha256-v1")

    def test_accepts_spec_style_camel_case_receipts(self):
        statement = to_treeship_statement(
            {
                "actionId": "act_camel",
                "agentId": "codex",
                "taskHash": "task_sha256",
                "retrievedMemoryIds": [],
                "injectedMemoryIds": [],
                "withheldMemoryIds": [],
                "policyChecks": [],
                "merkleRoot": "root_sha256",
                "createdAt": "2026-05-25T12:00:00Z",
                "signature": "sig_123",
            }
        )

        self.assertEqual(statement["subject"]["id"], "act_camel")
        self.assertEqual(statement["evidence"]["signature"], "sig_123")
        self.assertEqual(statement["source"]["receipt"]["created_at"], "2026-05-25T12:00:00Z")

    def test_embeds_bundle_proof_when_exporting_from_receipt_bundle(self):
        bundle = self._valid_bundle()

        statement = to_treeship_statement(bundle)

        self.assertEqual(statement["subject"]["id"], "act_bundle")
        self.assertEqual(statement["evidence"]["bundle_hash"], bundle["bundle_hash"])
        self.assertEqual(statement["evidence"]["bundle_event_count"], 1)
        self.assertTrue(statement["evidence"]["bundle_verified"])
        self.assertEqual(statement["source"]["bundle"]["action_id"], "act_bundle")

    def test_rejects_tampered_receipt_bundles(self):
        bundle = self._valid_bundle()
        bundle["bundle_hash"] = "bad"

        with self.assertRaisesRegex(ValueError, "bundle_hash mismatch"):
            to_treeship_statement(bundle)

    def test_requires_receipt_identity_and_proof_fields(self):
        with self.assertRaisesRegex(ValueError, "action_id"):
            to_treeship_statement({"agent_id": "codex"})

    def test_build_publish_command_uses_placeholders(self):
        command = build_treeship_publish_command(
            Path("/tmp/proof.json"),
            action_id="act_123",
            command_template="treeship prove {statement} --action {action_id}",
        )

        self.assertEqual(command, ["treeship", "prove", "/tmp/proof.json", "--action", "act_123"])

    def test_build_publish_command_appends_statement_without_placeholder(self):
        command = build_treeship_publish_command(
            Path("/tmp/proof.json"),
            command_template="treeship prove",
        )

        self.assertEqual(command, ["treeship", "prove", "/tmp/proof.json"])

    def test_treeship_cli_status_reports_missing_cli(self):
        with patch("zerker_memory.treeship.shutil.which", return_value=None):
            status = treeship_cli_status()

        self.assertFalse(status["ok"])
        self.assertEqual(status["command_template"], DEFAULT_TREESHIP_COMMAND_TEMPLATE)
        self.assertEqual(
            status["command_preview"],
            [
                "treeship",
                "attest",
                "receipt",
                "--system",
                "system://zmem",
                "--kind",
                "memory.proof",
                "--payload-file",
                "/tmp/zerker-memory.statement.json",
            ],
        )

    def test_publish_treeship_statement_supports_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            statement_path = Path(tmp) / "proof.json"
            statement_path.write_text("{}", encoding="utf-8")

            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                result = publish_treeship_statement(
                    statement_path,
                    action_id="act_123",
                    command_template="treeship prove {statement} --action {action_id}",
                    dry_run=True,
                )

        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["command"], ["treeship", "prove", str(statement_path), "--action", "act_123"])

    def test_publish_treeship_statement_runs_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            statement_path = Path(tmp) / "proof.json"
            statement_path.write_text("{}", encoding="utf-8")

            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.return_value.returncode = 0
                    run.return_value.stdout = "published"
                    run.return_value.stderr = ""

                    result = publish_treeship_statement(statement_path)

        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "published")
        run.assert_called_once_with(
            [
                "treeship",
                "attest",
                "receipt",
                "--system",
                "system://zmem",
                "--kind",
                "memory.proof",
                "--payload-file",
                str(statement_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_publish_treeship_statement_falls_back_for_published_cli_without_payload_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            statement_path = Path(tmp) / "proof.json"
            statement_path.write_text('{"ok":true}', encoding="utf-8")

            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    first = run.return_value
                    first.returncode = 2
                    first.stdout = ""
                    first.stderr = "error: unexpected argument '--payload-file' found"
                    second = type(first)()
                    second.returncode = 0
                    second.stdout = "published"
                    second.stderr = ""
                    run.side_effect = [first, second]

                    result = publish_treeship_statement(statement_path)

        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], "published")
        self.assertEqual(result["fallback"]["reason"], "treeship_cli_missing_payload_file")
        self.assertEqual(
            result["fallback"]["command"],
            [
                "treeship",
                "attest",
                "receipt",
                "--system",
                "system://zmem",
                "--kind",
                "memory.proof",
                "--payload",
                "<inline-json-redacted>",
            ],
        )
        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[1].args[0],
            [
                "treeship",
                "attest",
                "receipt",
                "--system",
                "system://zmem",
                "--kind",
                "memory.proof",
                "--payload",
                '{"ok":true}',
            ],
        )

    def test_attest_treeship_payload_digest_uses_compact_digest_payload(self):
        with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
            with patch("zerker_memory.treeship.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = (
                    '{"id":"art_write","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}'
                )
                run.return_value.stderr = ""

                result = attest_treeship_payload_digest(
                    "sha256:abc123",
                    kind="memory.write",
                    subject="wr_123",
                    config_path=Path("/tmp/treeship-config.json"),
                )

        self.assertEqual(result["status"], "signed")
        self.assertEqual(result["artifact_id"], "art_write")
        self.assertEqual(result["signed_at"], "2026-06-24T05:27:53Z")
        run.assert_called_once_with(
            [
                "treeship",
                "attest",
                "receipt",
                "--config",
                "/tmp/treeship-config.json",
                "--system",
                "system://zmem",
                "--kind",
                "memory.write",
                "--payload-digest",
                "sha256:abc123",
                "--format",
                "json",
                "--subject",
                "wr_123",
            ],
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
