import json
import tempfile
import unittest
from pathlib import Path

from zerker_memory.exporter import artifact_id, export_receipt
from zerker_memory.store import sha256_text, stable_json


class ExporterTest(unittest.TestCase):
    @staticmethod
    def _valid_bundle() -> dict:
        bundle = {
            "bundle_schema": "zerker.receipt_bundle.v1",
            "hash_alg": "sha256",
            "merkle_alg": "binary-sha256-v1",
            "created_at": "2026-05-26T00:00:01Z",
            "action_id": "act_1",
            "receipt": {
                "action_id": "act_1",
                "agent_id": "codex",
                "task_hash": "hash",
                "retrieved_memory_ids": [],
                "injected_memory_ids": [],
                "withheld_memory_ids": [],
                "policy_checks": [],
                "merkle_root": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6",
                "created_at": "2026-05-26T00:00:00Z",
            },
            "supporting_memory_ids": [],
            "supporting_memories": [],
            "supporting_events": [{"event_hash": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6"}],
            "proof": {
                "event_count": 1,
                "computed_merkle_root": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6",
                "receipt_merkle_root": "2d711642b726b04401627ca9fbac32f5da7e5f3bca8d9f1d8b6a5234f1d2b8d6",
                "verified": True,
            },
        }
        bundle["bundle_hash"] = sha256_text(stable_json(bundle))
        return bundle

    def test_artifact_id_is_stable_for_canonical_json(self):
        left = {"b": 2, "a": 1}
        right = {"a": 1, "b": 2}
        self.assertEqual(artifact_id(left), artifact_id(right))

    def test_exports_raw_receipt_to_file(self):
        receipt = {
            "action_id": "act_1",
            "agent_id": "codex",
            "task": "task",
            "task_hash": "hash",
            "retrieved_memory_ids": [],
            "injected_memory_ids": [],
            "withheld_memory_ids": [],
            "policy_checks": [],
            "merkle_root": "root",
            "created_at": "2026-05-26T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = export_receipt(receipt, fmt="json", out_dir=Path(tmp))
            path = Path(result["path"])
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["action_id"], "act_1")

    def test_exports_treeship_statement_to_file(self):
        receipt = self._valid_bundle()
        with tempfile.TemporaryDirectory() as tmp:
            result = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(result["path"]).read_text())
            self.assertEqual(payload["kind"], "zerker.memory.action_receipt")
            self.assertEqual(payload["evidence"]["bundle_hash"], receipt["bundle_hash"])


if __name__ == "__main__":
    unittest.main()
