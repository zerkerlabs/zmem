import json
import tempfile
import unittest
from pathlib import Path

from zerker_memory.exporter import export_bundle, export_snapshot
from zerker_memory.store import MemoryStore, sha256_text, stable_json


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "memory.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_captures_memory_events_receipts_and_hash(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")

        snapshot = self.store.snapshot()

        self.assertEqual(snapshot["snapshot_schema"], "zerker.memory_snapshot.v1")
        self.assertEqual(snapshot["memory_count"], 1)
        self.assertEqual(snapshot["receipt_count"], 1)
        self.assertEqual(snapshot["write_receipt_count"], 1)
        self.assertEqual(snapshot["write_receipts"][0]["memory_id"], snapshot["memories"][0]["id"])
        self.assertGreaterEqual(snapshot["event_count"], 2)
        self.assertEqual(snapshot["merkle_root"], self.store.current_merkle_root())

        snapshot_hash = snapshot["snapshot_hash"]
        without_hash = dict(snapshot)
        without_hash.pop("snapshot_hash")
        self.assertEqual(snapshot_hash, sha256_text(stable_json(without_hash)))

    def test_export_snapshot_writes_hashed_artifact(self):
        self.store.remember(
            "Use SQLite for local memory",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        with tempfile.TemporaryDirectory() as out_dir:
            result = export_snapshot(self.store.snapshot(), out_dir=Path(out_dir))
            path = Path(result["path"])

            self.assertTrue(path.exists())
            self.assertEqual(result["format"], "snapshot")
            self.assertEqual(json.loads(path.read_text())["snapshot_schema"], "zerker.memory_snapshot.v1")

    def test_restore_snapshot_round_trips_to_empty_store(self):
        memory = self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        snapshot = self.store.snapshot()

        restored = MemoryStore(Path(self.tmp.name) / "restored.sqlite")
        result = restored.restore_snapshot(snapshot)

        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot_hash"], snapshot["snapshot_hash"])
        self.assertEqual(restored.current_merkle_root(), snapshot["merkle_root"])
        self.assertEqual(restored.get(memory.id).content, memory.content)
        self.assertEqual(restored.memory_write_receipt(memory.id)["memory_id"], memory.id)
        self.assertTrue(restored.verify(receipt["action_id"]))

    def test_restore_refuses_non_empty_store(self):
        self.store.remember(
            "Use SQLite for local memory",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        snapshot = self.store.snapshot()

        non_empty = MemoryStore(Path(self.tmp.name) / "non-empty.sqlite")
        non_empty.remember(
            "Existing memory",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )

        with self.assertRaisesRegex(ValueError, "empty memory store"):
            non_empty.restore_snapshot(snapshot)

    def test_restore_rejects_tampered_snapshot(self):
        self.store.remember(
            "Use SQLite for local memory",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        snapshot = self.store.snapshot()
        snapshot["memories"][0]["content"] = "tampered"

        restored = MemoryStore(Path(self.tmp.name) / "tampered.sqlite")
        with self.assertRaisesRegex(ValueError, "snapshot_hash mismatch"):
            restored.restore_snapshot(snapshot)

    def test_verify_snapshot_accepts_valid_snapshot(self):
        self.store.remember(
            "Use SQLite for local memory",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        snapshot = self.store.snapshot()

        result = self.store.verify_snapshot(snapshot)

        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot_hash"], snapshot["snapshot_hash"])
        self.assertEqual(result["computed_snapshot_hash"], snapshot["snapshot_hash"])
        self.assertEqual(result["computed_merkle_root"], snapshot["merkle_root"])

    def test_verify_snapshot_reports_tampering(self):
        self.store.remember(
            "Use SQLite for local memory",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        snapshot = self.store.snapshot()
        snapshot["memories"][0]["content"] = "tampered"

        result = self.store.verify_snapshot(snapshot)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "snapshot_hash mismatch")
        self.assertNotEqual(result["computed_snapshot_hash"], snapshot["snapshot_hash"])

    def test_receipt_bundle_contains_pre_action_proof(self):
        memory = self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")

        bundle = self.store.receipt_bundle(receipt["action_id"])

        self.assertEqual(bundle["bundle_schema"], "zerker.receipt_bundle.v1")
        self.assertEqual(bundle["action_id"], receipt["action_id"])
        self.assertEqual(bundle["proof"]["receipt_merkle_root"], receipt["merkle_root"])
        self.assertTrue(bundle["proof"]["verified"])
        self.assertEqual(bundle["supporting_memory_ids"], [memory.id])
        self.assertEqual(bundle["supporting_memories"][0]["id"], memory.id)
        self.assertEqual(bundle["supporting_memory_write_receipts"][memory.id]["memory_id"], memory.id)
        self.assertGreaterEqual(bundle["proof"]["event_count"], 1)

    def test_export_bundle_writes_hashed_artifact(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])

        with tempfile.TemporaryDirectory() as out_dir:
            result = export_bundle(bundle, out_dir=Path(out_dir))
            path = Path(result["path"])

            self.assertTrue(path.exists())
            self.assertEqual(result["format"], "bundle")
            self.assertEqual(json.loads(path.read_text())["bundle_schema"], "zerker.receipt_bundle.v1")

    def test_verify_bundle_accepts_valid_bundle(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])

        result = self.store.verify_bundle(bundle)

        self.assertTrue(result["ok"])
        self.assertEqual(result["bundle_hash"], bundle["bundle_hash"])
        self.assertEqual(result["computed_bundle_hash"], bundle["bundle_hash"])
        self.assertEqual(result["computed_merkle_root"], receipt["merkle_root"])
        self.assertEqual(result["proof_event_count"], bundle["proof"]["event_count"])
        self.assertTrue(result["proof_verified"])

    def test_verify_bundle_reports_tampering(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        bundle["receipt"]["task"] = "tampered"

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bundle_hash mismatch")

    def test_verify_bundle_rejects_proof_event_count_mismatch(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        bundle["proof"]["event_count"] += 1
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bundle proof event_count mismatch")

    def test_verify_bundle_rejects_unverified_proof(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        bundle["proof"]["verified"] = False
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bundle proof is not verified")


if __name__ == "__main__":
    unittest.main()
