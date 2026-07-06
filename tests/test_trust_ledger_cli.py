import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from zerker_memory.cli import main
from zerker_memory.store import MemoryStore, sha256_text, stable_json


class TrustLedgerCliTest(unittest.TestCase):
    def test_bundle_verify_summary_only_marks_tampered_supporting_receipt_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-a",
                session_id="session://alpha",
                source_uri="conversation://session-a/message-17",
                parent_action_id="act_prompt_injection",
                environment_hash="sha256:env_fixture",
                status="active",
            )
            receipt = store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
            bundle = store.receipt_bundle(receipt["action_id"])
            bundle["supporting_memory_write_receipts"][memory.id]["treeship_statement"]["object"]["status"] = (
                "quarantined"
            )
            bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))
            bundle_path = Path(tmp) / "receipt.bundle.json"
            bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "bundle", "verify", str(bundle_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Receipt bundle verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Bundle verify: failed", summary)
        self.assertIn("Supporting write receipts: 1", summary)
        self.assertIn("Supporting provenance verify: failed (0/1 verified)", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("write receipt_hash mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_mutation_receipt_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-a",
                session_id="session://alpha",
                source_uri="conversation://session-a/message-17",
                parent_action_id="act_prompt_injection",
                environment_hash="sha256:env_fixture",
            )
            store.promote(memory.id, actor_id="reviewer")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["status"] = "quarantined"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event mutation status mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_reject_reason_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Staging deploys require manual SSH",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-b",
                session_id="session://beta",
                source_uri="conversation://session-b/message-4",
                parent_action_id="act_review",
                environment_hash="sha256:env_fixture",
            )
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["reason"] = "forged reason"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event reject reason mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_reject_actor_identity_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Staging deploys require manual SSH",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-b",
                session_id="session://beta",
                source_uri="conversation://session-b/message-4",
                parent_action_id="act_review",
                environment_hash="sha256:env_fixture",
            )
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["actor_id"] = "mallory"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event actor_id mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_revoke_descendant_metadata_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            source = store.remember(
                "Production deploys go through Railway",
                memory_type="episodic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-c",
                session_id="session://gamma",
                source_uri="conversation://session-c/message-9",
                parent_action_id="act_review",
                environment_hash="sha256:env_fixture",
            )
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["descendant_count"] = 0
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event descendant_count mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_revoke_reason_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            source = store.remember(
                "Production deploys go through Railway",
                memory_type="episodic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-c",
                session_id="session://gamma",
                source_uri="conversation://session-c/message-9",
                parent_action_id="act_review",
                environment_hash="sha256:env_fixture",
            )
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["reason"] = "forged reason"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event revoke reason mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_revoke_previous_status_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            source = store.remember(
                "Production deploys go through Railway",
                memory_type="episodic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-c",
                session_id="session://gamma",
                source_uri="conversation://session-c/message-9",
                parent_action_id="act_review",
                environment_hash="sha256:env_fixture",
            )
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["previous_status"] = "active"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event previous_status mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_revoke_actor_identity_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            source = store.remember(
                "Production deploys go through Railway",
                memory_type="episodic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-c",
                session_id="session://gamma",
                source_uri="conversation://session-c/message-9",
                parent_action_id="act_review",
                environment_hash="sha256:env_fixture",
            )
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["actor_id"] = "mallory"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event actor_id mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_forget_previous_status_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Temporary routing snack is ramen",
                memory_type="episodic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-d",
                session_id="session://delta",
                source_uri="conversation://session-d/message-5",
                parent_action_id="act_capture",
                environment_hash="sha256:env_fixture",
                status="active",
            )
            store.forget(memory.id, actor_id="reviewer")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["previous_status"] = "quarantined"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event previous_status mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_forget_actor_identity_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Temporary routing snack is ramen",
                memory_type="episodic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-d",
                session_id="session://delta",
                source_uri="conversation://session-d/message-5",
                parent_action_id="act_capture",
                environment_hash="sha256:env_fixture",
                status="active",
            )
            store.forget(memory.id, actor_id="reviewer")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["actor_id"] = "mallory"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event actor_id mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_promote_authority_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-a",
                session_id="session://alpha",
                source_uri="conversation://session-a/message-17",
                parent_action_id="act_prompt_injection",
                environment_hash="sha256:env_fixture",
            )
            store.promote(memory.id, actor_id="reviewer")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["authority"] = "none"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event promote authority mismatch", summary)

    def test_snapshot_verify_summary_only_marks_tampered_promote_actor_identity_as_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/session-a",
                session_id="session://alpha",
                source_uri="conversation://session-a/message-17",
                parent_action_id="act_prompt_injection",
                environment_hash="sha256:env_fixture",
            )
            store.promote(memory.id, actor_id="reviewer")
            snapshot = store.snapshot()
            latest_receipt = snapshot["write_receipts"][-1]
            latest_receipt["treeship_statement"]["object"]["actor_id"] = "mallory"
            stripped_statement = json.loads(json.dumps(latest_receipt["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(latest_receipt["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            latest_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
            snapshot["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 1)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn("Ready: no", summary)
        self.assertIn("Snapshot verify: failed", summary)
        self.assertIn("Write receipt verify: failed", summary)
        self.assertIn("Trusted provenance: not verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("source event actor_id mismatch", summary)


if __name__ == "__main__":
    unittest.main()
