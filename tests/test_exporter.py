import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from zerker_memory.exporter import artifact_id, export_receipt
from zerker_memory.store import MemoryStore, sha256_text, stable_json


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

    def test_exports_embedded_lifecycle_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = MemoryStore(Path(tmp) / "source.sqlite")
            source.init()
            source.remember(
                "Portable snapshots must preserve memory provenance",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            snapshot = source.snapshot()

            restored = MemoryStore(Path(tmp) / "restored.sqlite")
            result = restored.restore_snapshot(snapshot)

            export = export_receipt(result["receipt"], fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "snapshot_restore")
        self.assertEqual(payload["subject"]["id"], result["receipt"]["receipt_id"])
        self.assertEqual(payload["object"]["mutation"], "restore_snapshot")
        self.assertEqual(payload["evidence"]["new_merkle_root"], snapshot["merkle_root"])

    def test_exports_embedded_session_checkpoint_lifecycle_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Portable checkpoints must preserve lifecycle provenance",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            checkpoint = store.checkpoint_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="handoff before context compaction",
            )

            export = export_receipt(checkpoint["receipt"], fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "session_mutation")
        self.assertEqual(payload["subject"]["id"], checkpoint["receipt"]["receipt_id"])
        self.assertEqual(payload["subject"]["mutation_id"], checkpoint["checkpoint_id"])
        self.assertEqual(payload["subject"]["session_id"], "session://alpha")
        self.assertEqual(payload["object"]["mutation"], "checkpoint_session")
        self.assertEqual(payload["object"]["actor_id"], "codex")
        self.assertEqual(payload["object"]["scope"], "project:alpha")
        self.assertEqual(payload["object"]["snapshot_hash"], checkpoint["snapshot"]["snapshot_hash"])
        self.assertEqual(payload["object"]["content_digest"], checkpoint["receipt"]["content_digest"])
        self.assertEqual(
            payload["evidence"]["prior_merkle_root"],
            checkpoint["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(payload["evidence"]["new_merkle_root"], checkpoint["receipt"]["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], checkpoint["receipt"]["receipt_id"])
        self.assertIsNone(payload["source"]["treeship_artifact_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_embedded_session_start_lifecycle_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Portable session starts must preserve lifecycle provenance",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            started = store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="resume deploy swarm",
                context_budget_tokens=256,
            )

            export = export_receipt(started["receipt"], fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "session_mutation")
        self.assertEqual(payload["subject"]["id"], started["receipt"]["receipt_id"])
        self.assertEqual(payload["subject"]["mutation_id"], started["session_start_id"])
        self.assertEqual(payload["subject"]["session_id"], "session://alpha")
        self.assertEqual(payload["object"]["mutation"], "start_session")
        self.assertEqual(payload["object"]["actor_id"], "codex")
        self.assertEqual(payload["object"]["scope"], "project:alpha")
        self.assertEqual(payload["object"]["summary"], "resume deploy swarm")
        self.assertEqual(payload["object"]["context_budget_tokens"], 256)
        self.assertEqual(payload["object"]["snapshot_hash"], started["snapshot"]["snapshot_hash"])
        self.assertEqual(payload["object"]["content_digest"], started["receipt"]["content_digest"])
        self.assertEqual(
            payload["evidence"]["prior_merkle_root"],
            started["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(payload["evidence"]["new_merkle_root"], started["receipt"]["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], started["receipt"]["receipt_id"])
        self.assertIsNone(payload["source"]["treeship_artifact_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_embedded_session_end_lifecycle_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Portable session endings must preserve lifecycle provenance",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            ended = store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="handoff after deploy swarm",
            )

            export = export_receipt(ended["receipt"], fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "session_mutation")
        self.assertEqual(payload["subject"]["id"], ended["receipt"]["receipt_id"])
        self.assertEqual(payload["subject"]["mutation_id"], ended["session_end_id"])
        self.assertEqual(payload["subject"]["session_id"], "session://alpha")
        self.assertEqual(payload["object"]["mutation"], "end_session")
        self.assertEqual(payload["object"]["actor_id"], "codex")
        self.assertEqual(payload["object"]["scope"], "project:alpha")
        self.assertEqual(payload["object"]["summary"], "handoff after deploy swarm")
        self.assertEqual(payload["object"]["snapshot_hash"], ended["snapshot"]["snapshot_hash"])
        self.assertEqual(payload["object"]["content_digest"], ended["receipt"]["content_digest"])
        self.assertEqual(
            payload["evidence"]["prior_merkle_root"],
            ended["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(payload["evidence"]["new_merkle_root"], ended["receipt"]["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], ended["receipt"]["receipt_id"])
        self.assertIsNone(payload["source"]["treeship_artifact_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_embedded_session_snapshot_lifecycle_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Portable session snapshots must preserve lifecycle provenance",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="handoff after context compaction",
            )

            export = export_receipt(session_snapshot["receipt"], fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "session_mutation")
        self.assertEqual(payload["subject"]["id"], session_snapshot["receipt"]["receipt_id"])
        self.assertEqual(payload["subject"]["mutation_id"], session_snapshot["session_snapshot_id"])
        self.assertEqual(payload["subject"]["session_id"], "session://alpha")
        self.assertEqual(payload["object"]["mutation"], "snapshot_session")
        self.assertEqual(payload["object"]["actor_id"], "codex")
        self.assertEqual(payload["object"]["scope"], "project:alpha")
        self.assertEqual(payload["object"]["snapshot_hash"], session_snapshot["snapshot"]["snapshot_hash"])
        self.assertEqual(payload["object"]["content_digest"], session_snapshot["receipt"]["content_digest"])
        self.assertEqual(
            payload["evidence"]["prior_merkle_root"],
            session_snapshot["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(payload["evidence"]["new_merkle_root"], session_snapshot["receipt"]["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], session_snapshot["receipt"]["receipt_id"])
        self.assertIsNone(payload["source"]["treeship_artifact_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            memory = store.remember(
                "Portable write receipts must preserve provenance",
                memory_type="policy",
                scope="project",
                source_kind="human",
                actor_id="reviewer",
            )

            export = export_receipt(store.memory_write_receipt(memory.id), fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.write_provenance")
        self.assertEqual(payload["subject"]["type"], "memory_write")
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_attested_quarantined_memory_write_provenance_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.return_value = mock.Mock(
                        returncode=0,
                        stdout='{"id":"art_write_q","kind":"memory.write","signed":"2026-06-28T11:31:00Z","status":"ok","system":"system://zmem"}',
                        stderr="",
                    )
                    memory = store.remember(
                        "Status page owner came from an unreviewed run",
                        memory_type="semantic",
                        scope="project",
                        source_kind="agent",
                        actor_id="codex",
                        actor_uri="agent://codex/session-q",
                        session_id="session://quarantine",
                        source_uri="conversation://session-q/message-2",
                        parent_action_id="act_capture",
                        environment_hash="sha256:env_fixture",
                    )

            receipt = store.memory_write_receipt(memory.id)
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.write_provenance")
        self.assertEqual(payload["subject"]["type"], "memory_write")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "codex")
        self.assertEqual(payload["object"]["status"], "quarantined")
        self.assertEqual(payload["object"]["authority"], "low")
        self.assertEqual(payload["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(payload["evidence"]["prior_merkle_root"], receipt["treeship_statement"]["evidence"]["prior_merkle_root"])
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(payload["attestation"]["artifact_id"], "art_write_q")
        self.assertEqual(payload["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_promote_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
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
            original_receipt = store.memory_write_receipt(memory.id)
            store.promote(memory.id, actor_id="reviewer")

            receipt = store.memory_write_receipts(memory.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "promote")
        self.assertEqual(payload["object"]["status"], "active")
        self.assertEqual(payload["object"]["authority"], "policy")
        self.assertEqual(payload["object"]["content_digest"], f"sha256:{memory.content_hash}")
        self.assertEqual(
            payload["evidence"]["prior_merkle_root"],
            receipt["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_id"], original_receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], original_receipt["receipt_hash"])
        self.assertNotIn("attestation", payload)
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_attested_promote_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.side_effect = [
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                    ]
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

            receipt = store.memory_write_receipts(memory.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "promote")
        self.assertEqual(payload["object"]["status"], "active")
        self.assertEqual(payload["object"]["authority"], "policy")
        self.assertEqual(payload["object"]["content_digest"], f"sha256:{memory.content_hash}")
        self.assertEqual(payload["evidence"]["prior_merkle_root"], receipt["treeship_statement"]["evidence"]["prior_merkle_root"])
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["prior_receipt_id"], store.memory_write_receipts(memory.id)[0]["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], store.memory_write_receipts(memory.id)[0]["receipt_hash"])
        self.assertEqual(payload["attestation"]["artifact_id"], "art_write_2")
        self.assertEqual(payload["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_reject_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
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
            original_receipt = store.memory_write_receipt(memory.id)
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")

            receipt = store.memory_write_receipts(memory.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "reject")
        self.assertEqual(payload["object"]["status"], "deprecated")
        self.assertEqual(payload["object"]["authority"], "none")
        self.assertEqual(payload["object"]["reason"], "superseded runbook")
        self.assertEqual(payload["object"]["previous_status"], "quarantined")
        self.assertEqual(payload["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(
            payload["evidence"]["prior_merkle_root"],
            receipt["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_id"], original_receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], original_receipt["receipt_hash"])
        self.assertNotIn("attestation", payload)
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_attested_reject_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.side_effect = [
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                    ]
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

            receipt = store.memory_write_receipts(memory.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "reject")
        self.assertEqual(payload["object"]["status"], "deprecated")
        self.assertEqual(payload["object"]["authority"], "none")
        self.assertEqual(payload["object"]["reason"], "superseded runbook")
        self.assertEqual(payload["object"]["previous_status"], "quarantined")
        self.assertEqual(payload["evidence"]["prior_merkle_root"], receipt["treeship_statement"]["evidence"]["prior_merkle_root"])
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["prior_receipt_id"], store.memory_write_receipts(memory.id)[0]["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], store.memory_write_receipts(memory.id)[0]["receipt_hash"])
        self.assertEqual(payload["attestation"]["artifact_id"], "art_write_2")
        self.assertEqual(payload["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_revoke_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
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
            derived = store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            original_receipt = store.memory_write_receipt(source.id)
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")

            receipt = store.memory_write_receipts(source.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], source.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "revoke")
        self.assertEqual(payload["object"]["status"], "revoked")
        self.assertEqual(payload["object"]["authority"], "none")
        self.assertEqual(payload["object"]["reason"], "source evidence was wrong")
        self.assertEqual(payload["object"]["revoked_ids"], [source.id, derived.id])
        self.assertEqual(payload["object"]["descendant_ids"], [derived.id])
        self.assertEqual(payload["object"]["descendant_count"], 1)
        self.assertEqual(payload["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(
            payload["evidence"]["prior_merkle_root"],
            receipt["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_id"], original_receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], original_receipt["receipt_hash"])
        self.assertNotIn("attestation", payload)
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_attested_revoke_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.side_effect = [
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_3","kind":"memory.write","signed":"2026-06-24T05:27:55Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                    ]
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

            receipt = store.memory_write_receipts(source.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], source.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "revoke")
        self.assertEqual(payload["object"]["reason"], "source evidence was wrong")
        self.assertEqual(payload["object"]["revoked_ids"], [source.id, payload["object"]["descendant_ids"][0]])
        self.assertEqual(payload["evidence"]["prior_merkle_root"], receipt["treeship_statement"]["evidence"]["prior_merkle_root"])
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["prior_receipt_id"], store.memory_write_receipts(source.id)[0]["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], store.memory_write_receipts(source.id)[0]["receipt_hash"])
        self.assertEqual(payload["attestation"]["artifact_id"], "art_write_3")
        self.assertEqual(payload["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_forget_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
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
            original_receipt = store.memory_write_receipt(memory.id)
            store.forget(memory.id, actor_id="reviewer")

            receipt = store.memory_write_receipts(memory.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "forget")
        self.assertEqual(payload["object"]["status"], "forgotten")
        self.assertEqual(payload["object"]["authority"], "low")
        self.assertEqual(payload["object"]["previous_status"], "active")
        self.assertEqual(payload["object"]["content_digest"], f"sha256:{memory.content_hash}")
        self.assertEqual(payload["evidence"]["prior_merkle_root"], receipt["treeship_statement"]["evidence"]["prior_merkle_root"])
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_id"], original_receipt["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], original_receipt["receipt_hash"])
        self.assertNotIn("attestation", payload)
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_exports_attested_forget_memory_write_treeship_statement_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.side_effect = [
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                        mock.Mock(
                            returncode=0,
                            stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
                            stderr="",
                        ),
                    ]
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

            receipt = store.memory_write_receipts(memory.id)[1]
            export = export_receipt(receipt, fmt="treeship", out_dir=Path(tmp))
            payload = json.loads(Path(export["path"]).read_text())

        self.assertEqual(payload["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(payload["subject"]["type"], "memory_mutation")
        self.assertEqual(payload["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(payload["subject"]["memory_id"], memory.id)
        self.assertEqual(payload["object"]["actor_id"], "reviewer")
        self.assertEqual(payload["object"]["mutation"], "forget")
        self.assertEqual(payload["object"]["status"], "forgotten")
        self.assertEqual(payload["object"]["authority"], "low")
        self.assertEqual(payload["object"]["previous_status"], "active")
        self.assertEqual(payload["object"]["content_digest"], f"sha256:{memory.content_hash}")
        self.assertEqual(payload["evidence"]["prior_merkle_root"], receipt["treeship_statement"]["evidence"]["prior_merkle_root"])
        self.assertEqual(payload["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(payload["source"]["prior_receipt_id"], store.memory_write_receipts(memory.id)[0]["receipt_id"])
        self.assertEqual(payload["source"]["prior_receipt_hash"], store.memory_write_receipts(memory.id)[0]["receipt_hash"])
        self.assertEqual(payload["attestation"]["artifact_id"], "art_write_2")
        self.assertEqual(payload["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(payload["object"]["semantic_truth_guaranteed"])

    def test_rejects_tampered_forget_actor_identity_memory_write_treeship_file_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
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

            tampered = json.loads(json.dumps(store.memory_write_receipts(memory.id)[1]))
            tampered["treeship_statement"]["object"]["actor_id"] = "mallory"
            stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
            stripped_statement.pop("attestation", None)
            tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
            tampered_hash_input["treeship_statement"] = stripped_statement
            tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

            with self.assertRaisesRegex(ValueError, "write receipt .*actor_id mismatch"):
                export_receipt(tampered, fmt="treeship", out_dir=Path(tmp))

            self.assertEqual(sorted(Path(tmp).glob("*.treeship.json")), [])

    def test_rejects_duplicate_supporting_memory_entries_in_bundle_treeship_file_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
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
            bundle["supporting_memories"].append(json.loads(json.dumps(bundle["supporting_memories"][0])))
            bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

            with self.assertRaisesRegex(ValueError, "bundle supporting memory id is duplicated"):
                export_receipt(bundle, fmt="treeship", out_dir=Path(tmp))

            self.assertEqual(sorted(Path(tmp).glob("*.treeship.json")), [])


if __name__ == "__main__":
    unittest.main()
