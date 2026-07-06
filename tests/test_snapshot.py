import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest import mock

from zerker_memory.exporter import export_bundle, export_snapshot
from zerker_memory.store import MemoryStore, merkle_root, sha256_text, stable_json


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
        self.assertEqual(snapshot["write_receipts"][0]["treeship_statement"]["evidence"]["prior_merkle_root"], merkle_root([]))
        self.assertEqual(
            snapshot["write_receipts"][0]["treeship_statement"]["evidence"]["new_merkle_root"],
            snapshot["write_receipts"][0]["merkle_root"],
        )
        self.assertGreaterEqual(snapshot["event_count"], 2)
        self.assertEqual(snapshot["merkle_root"], self.store.current_merkle_root())

        snapshot_hash = snapshot["snapshot_hash"]
        without_hash = dict(snapshot)
        without_hash.pop("snapshot_hash")
        self.assertEqual(snapshot_hash, sha256_text(stable_json(without_hash)))

    def test_snapshot_captures_promote_event_lineage(self):
        memory = self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="agent",
        )

        promoted = self.store.promote(memory.id, actor_id="reviewer")
        snapshot = self.store.snapshot()

        self.assertEqual(promoted.status, "active")
        self.assertEqual(snapshot["event_count"], 2)
        self.assertEqual([event["event_type"] for event in snapshot["events"]], ["PROPOSED", "PROMOTED"])
        proposed_event, promoted_event = snapshot["events"]
        promoted_payload = json.loads(promoted_event["payload_json"])
        self.assertEqual(promoted_event["memory_id"], memory.id)
        self.assertEqual(promoted_event["actor_id"], "reviewer")
        self.assertEqual(promoted_event["prev_event_hash"], proposed_event["event_hash"])
        self.assertEqual(promoted_event["merkle_root"], snapshot["merkle_root"])
        self.assertEqual(promoted_payload["id"], memory.id)
        self.assertEqual(promoted_payload["authority"], "policy")

    def test_snapshot_captures_promote_mutation_write_receipt(self):
        memory = self.store.remember(
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

        self.store.promote(memory.id, actor_id="reviewer")
        snapshot = self.store.snapshot()

        self.assertEqual(snapshot["write_receipt_count"], 2)
        memory_receipts = [receipt for receipt in snapshot["write_receipts"] if receipt["memory_id"] == memory.id]
        self.assertEqual(len(memory_receipts), 2)
        mutation_receipt = memory_receipts[-1]
        self.assertEqual(mutation_receipt["treeship_statement"]["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(mutation_receipt["treeship_statement"]["object"]["mutation"], "promote")
        self.assertEqual(
            mutation_receipt["treeship_statement"]["evidence"]["new_merkle_root"],
            mutation_receipt["merkle_root"],
        )

    def test_snapshot_captures_revoke_mutation_write_receipt(self):
        source = self.store.remember(
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
        derived = self.store.remember(
            "Deploy target is Railway",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
            parents=[source.id],
        )

        self.store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")
        snapshot = self.store.snapshot()

        self.assertEqual(snapshot["write_receipt_count"], 3)
        source_receipts = [receipt for receipt in snapshot["write_receipts"] if receipt["memory_id"] == source.id]
        derived_receipts = [receipt for receipt in snapshot["write_receipts"] if receipt["memory_id"] == derived.id]
        self.assertEqual(len(source_receipts), 2)
        self.assertEqual(len(derived_receipts), 1)
        mutation_receipt = source_receipts[-1]
        self.assertEqual(mutation_receipt["treeship_statement"]["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(mutation_receipt["treeship_statement"]["object"]["mutation"], "revoke")
        self.assertEqual(
            mutation_receipt["treeship_statement"]["object"]["revoked_ids"],
            [source.id, derived.id],
        )
        self.assertEqual(
            mutation_receipt["treeship_statement"]["evidence"]["new_merkle_root"],
            mutation_receipt["merkle_root"],
        )

    def test_snapshot_captures_forget_mutation_write_receipt(self):
        memory = self.store.remember(
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

        self.store.forget(memory.id, actor_id="reviewer")
        snapshot = self.store.snapshot()

        self.assertEqual(snapshot["write_receipt_count"], 2)
        memory_receipts = [receipt for receipt in snapshot["write_receipts"] if receipt["memory_id"] == memory.id]
        self.assertEqual(len(memory_receipts), 2)
        mutation_receipt = memory_receipts[-1]
        self.assertEqual(mutation_receipt["treeship_statement"]["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(mutation_receipt["treeship_statement"]["object"]["mutation"], "forget")
        self.assertEqual(
            mutation_receipt["treeship_statement"]["evidence"]["new_merkle_root"],
            mutation_receipt["merkle_root"],
        )

    def test_snapshot_restore_preserves_attested_ordered_write_receipt_chain(self):
        store = MemoryStore(Path(self.tmp.name) / "attested-memory.sqlite", treeship_auto_sign=True)
        signed_provenance = mock.Mock(
            returncode=0,
            stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
            stderr="",
        )
        signed_mutation = mock.Mock(
            returncode=0,
            stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
            stderr="",
        )
        with mock.patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
            with mock.patch("zerker_memory.treeship.subprocess.run", side_effect=[signed_provenance, signed_mutation]) as run:
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
        snapshot_receipts = [receipt for receipt in snapshot["write_receipts"] if receipt["memory_id"] == memory.id]
        self.assertEqual(len(snapshot_receipts), 2)
        self.assertEqual([receipt["treeship_attestation"]["artifact_id"] for receipt in snapshot_receipts], ["art_write_1", "art_write_2"])
        for receipt in snapshot_receipts:
            self.assertEqual(receipt["treeship_attestation"]["payload_digest"], f"sha256:{receipt['receipt_hash']}")
            self.assertEqual(receipt["treeship_statement"]["attestation"], receipt["treeship_attestation"])

        restored = MemoryStore(Path(self.tmp.name) / "restored-attested.sqlite")
        result = restored.restore_snapshot(snapshot)

        self.assertTrue(result["ok"])
        restored_receipts = restored.memory_write_receipts(memory.id)
        self.assertEqual([receipt["receipt_id"] for receipt in restored_receipts], [receipt["receipt_id"] for receipt in snapshot_receipts])
        self.assertEqual(restored.memory_write_receipt(memory.id)["receipt_id"], snapshot_receipts[0]["receipt_id"])
        for expected, actual in zip(snapshot_receipts, restored_receipts):
            self.assertEqual(actual["treeship_attestation"], expected["treeship_attestation"])
            self.assertEqual(actual["treeship_statement"]["attestation"], expected["treeship_attestation"])
            self.assertEqual(actual["treeship_attestation"]["payload_digest"], f"sha256:{actual['receipt_hash']}")
        self.assertEqual(run.call_count, 2)

        snapshot_verification = store.verify_memory_write_receipt_chain(snapshot_receipts)
        restored_verification = restored.verify_memory_write_receipt_chain(restored_receipts)
        self.assertTrue(snapshot_verification["ok"])
        self.assertTrue(restored_verification["ok"])
        self.assertEqual(snapshot_verification["attestation_artifacts"], restored_verification["attestation_artifacts"])
        self.assertFalse(restored_verification["semantic_truth_guaranteed"])

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

    def test_restore_snapshot_returns_deterministic_restore_receipt_without_changing_snapshot_root(self):
        self.store.remember(
            "Portable snapshots must preserve memory provenance",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        snapshot = self.store.snapshot()

        restored = MemoryStore(Path(self.tmp.name) / "restored-with-receipt.sqlite")
        result = restored.restore_snapshot(snapshot)

        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot_hash"], snapshot["snapshot_hash"])
        self.assertEqual(result["merkle_root"], snapshot["merkle_root"])
        self.assertEqual(restored.current_merkle_root(), snapshot["merkle_root"])
        receipt = result["receipt"]
        receipt_without_hash = dict(receipt)
        receipt_hash = receipt_without_hash.pop("receipt_hash")
        self.assertEqual(receipt["receipt_schema"], "zerker.lifecycle_receipt.v1")
        self.assertEqual(receipt["mutation"], "restore_snapshot")
        self.assertEqual(receipt["actor_uri"], "actor://snapshot_restore")
        self.assertEqual(receipt["treeship_artifact_id"], None)
        self.assertEqual(receipt["merkle_root"], snapshot["merkle_root"])
        self.assertEqual(receipt["content_digest"], f"sha256:{sha256_text(stable_json(receipt['source_payload']))}")
        self.assertEqual(receipt_hash, sha256_text(stable_json(receipt_without_hash)))
        self.assertEqual(receipt["treeship_statement"]["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(receipt["treeship_statement"]["object"]["mutation"], "restore_snapshot")
        self.assertEqual(receipt["treeship_statement"]["object"]["semantic_truth_guaranteed"], False)
        self.assertEqual(receipt["treeship_statement"]["evidence"]["prior_merkle_root"], merkle_root([]))
        self.assertEqual(receipt["treeship_statement"]["evidence"]["new_merkle_root"], snapshot["merkle_root"])
        self.assertEqual(receipt["treeship_statement"]["evidence"]["snapshot_hash"], snapshot["snapshot_hash"])

    def test_verify_lifecycle_receipt_accepts_restore_snapshot_receipt_with_source_snapshot(self):
        self.store.remember(
            "Portable snapshots must preserve memory provenance",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        snapshot = self.store.snapshot()

        restored = MemoryStore(Path(self.tmp.name) / "restored-with-verified-receipt.sqlite")
        result = restored.restore_snapshot(snapshot)

        verification = restored.verify_lifecycle_receipt(result["receipt"], source_snapshot=snapshot)

        self.assertTrue(verification["ok"])
        self.assertEqual(verification["mutation"], "restore_snapshot")
        self.assertEqual(verification["computed_receipt_hash"], result["receipt"]["receipt_hash"])
        self.assertEqual(verification["computed_content_digest"], result["receipt"]["content_digest"])
        self.assertTrue(verification["treeship_statement_verified"])
        self.assertTrue(verification["source_snapshot_verified"])
        self.assertFalse(verification["semantic_truth_guaranteed"])

    def test_verify_lifecycle_receipt_reports_tampered_restore_receipt(self):
        self.store.remember(
            "Portable snapshots must preserve memory provenance",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        snapshot = self.store.snapshot()

        restored = MemoryStore(Path(self.tmp.name) / "restored-with-tampered-receipt.sqlite")
        result = restored.restore_snapshot(snapshot)
        tampered = json.loads(json.dumps(result["receipt"]))
        tampered["source_payload"]["memory_count"] += 1
        tampered_without_hash = dict(tampered)
        tampered_without_hash.pop("receipt_hash", None)
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_without_hash))

        verification = restored.verify_lifecycle_receipt(tampered, source_snapshot=snapshot)

        self.assertFalse(verification["ok"])
        self.assertEqual(verification["error"], "lifecycle content_digest mismatch")

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
        self.assertEqual(result["attestation_artifacts"], [])

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

    def test_verify_snapshot_accepts_revoke_receipt_with_intervening_events(self):
        source = self.store.remember(
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
        self.store.remember(
            "Deploy target is Railway",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
            parents=[source.id],
        )
        self.store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")
        snapshot = self.store.snapshot()

        result = self.store.verify_snapshot(snapshot)

        self.assertTrue(result["ok"])
        self.assertEqual(result["write_receipt_chain_count"], 2)
        self.assertEqual(result["verified_write_receipt_count"], 3)
        self.assertEqual(result["verified_write_receipt_transition_count"], 1)

    def test_verify_snapshot_surfaces_intervening_write_continuity_counts(self):
        memory = self.store.remember(
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
        self.store.remember(
            "Unrelated runbook note",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
            actor_id="codex",
        )
        self.store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")

        result = self.store.verify_snapshot(self.store.snapshot())

        self.assertTrue(result["ok"])
        self.assertEqual(result["write_receipt_chain_count"], 2)
        self.assertEqual(result["verified_write_receipt_transition_count"], 1)
        self.assertEqual(result["total_intervening_event_count"], 1)
        self.assertEqual(result["total_intervening_other_memory_event_count"], 1)
        self.assertEqual(len(result["write_receipt_chains"]), 2)
        memory_chain = next(item for item in result["write_receipt_chains"] if item["memory_id"] == memory.id)
        self.assertTrue(memory_chain["ok"])
        self.assertEqual(memory_chain["receipt_count"], 2)
        self.assertEqual(memory_chain["total_intervening_event_count"], 1)
        self.assertEqual(memory_chain["total_intervening_other_memory_event_count"], 1)
        self.assertEqual(len(memory_chain["transitions"]), 1)
        transition = memory_chain["transitions"][0]
        self.assertEqual(transition["continuity_basis"], "prior_receipt_link_plus_snapshot_previous_event_root")
        self.assertEqual(transition["intervening_event_count"], 1)
        self.assertEqual(transition["intervening_other_memory_event_count"], 1)
        self.assertTrue(transition["trusted_provenance_verified"])
        self.assertFalse(transition["semantic_truth_guaranteed"])

    def test_verify_snapshot_surfaces_provenance_anchor_summary(self):
        memory = self.store.remember(
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
        self.store.promote(memory.id, actor_id="reviewer")

        result = self.store.verify_snapshot(self.store.snapshot())

        self.assertTrue(result["ok"])
        self.assertEqual(result["provenance_receipt_count"], 1)
        self.assertEqual(result["verified_provenance_receipt_count"], 1)
        self.assertEqual(len(result["provenance_receipts"]), 1)
        provenance = result["provenance_receipts"][0]
        self.assertEqual(provenance["memory_id"], memory.id)
        self.assertEqual(provenance["actor_id"], "codex")
        self.assertEqual(provenance["actor_uri"], "agent://codex/session-a")
        self.assertEqual(provenance["content_digest"], f"sha256:{memory.content_hash}")
        self.assertEqual(provenance["prior_merkle_root"], merkle_root([]))
        self.assertEqual(provenance["new_merkle_root"], provenance["merkle_root"])
        self.assertEqual(provenance["treeship_artifact_id"], None)
        self.assertTrue(provenance["trusted_provenance_verified"])
        self.assertFalse(provenance["semantic_truth_guaranteed"])

    def test_verify_snapshot_surfaces_parent_supersession_transition_summary(self):
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_id="reporter",
            actor_uri="agent://reporter/session-a",
            session_id="session://alpha",
            source_uri="conversation://session-a/message-3",
            parent_action_id="act_capture_stale",
            environment_hash="sha256:env_fixture",
            status="active",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
            actor_id="codex",
            actor_uri="agent://codex/session-b",
            session_id="session://beta",
            source_uri="conversation://session-b/message-4",
            parent_action_id="act_capture_current",
            environment_hash="sha256:env_fixture",
            parents=[stale.id],
        )
        self.store.promote(current.id, actor_id="reviewer")
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = ?",
            ("2024-01-01T00:00:00Z", stale.id, "OBSERVED"),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = ?",
            ("2024-01-15T00:00:00Z", current.id, "PROPOSED"),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = ?",
            ("2024-02-01T00:00:00Z", current.id, "PROMOTED"),
        )
        self.store.conn.commit()

        result = self.store.verify_snapshot(self.store.snapshot())

        self.assertTrue(result["ok"])
        self.assertEqual(result["supersession_transition_count"], 1)
        self.assertEqual(result["verified_supersession_transition_count"], 1)
        self.assertEqual(len(result["supersession_transitions"]), 1)
        transition = result["supersession_transitions"][0]
        current_receipts = self.store.memory_write_receipts(current.id)
        anchor_receipt = current_receipts[-1]
        self.assertEqual(transition["superseded_memory_id"], stale.id)
        self.assertEqual(transition["superseding_memory_ids"], [current.id])
        self.assertEqual(transition["superseded_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(transition["supersession_reasons"], ["active-child-candidate"])
        self.assertEqual(transition["anchor_memory_id"], current.id)
        self.assertEqual(transition["anchor_receipt_id"], anchor_receipt["receipt_id"])
        self.assertEqual(transition["anchor_receipt_hash"], anchor_receipt["receipt_hash"])
        self.assertEqual(transition["anchor_receipt_kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(transition["anchor_event_hash"], anchor_receipt["event_hash"])
        self.assertEqual(transition["actor_id"], "reviewer")
        self.assertEqual(transition["actor_uri"], "actor://reviewer")
        self.assertEqual(transition["content_digest"], f"sha256:{current.content_hash}")
        self.assertEqual(
            transition["prior_merkle_root"],
            anchor_receipt["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(transition["new_merkle_root"], anchor_receipt["merkle_root"])
        self.assertEqual(transition["treeship_artifact_id"], None)
        self.assertTrue(transition["trusted_provenance_verified"])
        self.assertFalse(transition["semantic_truth_guaranteed"])

    def test_verify_snapshot_surfaces_explicit_update_supersession_transition_summary(self):
        stale = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, stale.id, current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, current.id),
        )
        self.store.conn.commit()

        result = self.store.verify_snapshot(self.store.snapshot())

        self.assertTrue(result["ok"])
        self.assertEqual(result["supersession_transition_count"], 1)
        self.assertEqual(result["verified_supersession_transition_count"], 1)
        self.assertEqual(len(result["supersession_transitions"]), 1)
        transition = result["supersession_transitions"][0]
        anchor_receipt = self.store.memory_write_receipts(current.id)[-1]
        self.assertEqual(transition["superseded_memory_id"], stale.id)
        self.assertEqual(transition["superseding_memory_ids"], [current.id])
        self.assertEqual(transition["superseded_at"], shared_timestamp)
        self.assertEqual(transition["supersession_reasons"], ["explicit-update-candidate"])
        self.assertEqual(transition["anchor_memory_id"], current.id)
        self.assertEqual(transition["anchor_receipt_id"], anchor_receipt["receipt_id"])
        self.assertEqual(transition["anchor_receipt_hash"], anchor_receipt["receipt_hash"])
        self.assertEqual(transition["anchor_receipt_kind"], "zerker.memory.write_provenance")
        self.assertEqual(transition["anchor_event_hash"], anchor_receipt["event_hash"])
        self.assertEqual(transition["actor_id"], "human")
        self.assertEqual(transition["actor_uri"], "actor://human")
        self.assertEqual(transition["content_digest"], f"sha256:{current.content_hash}")
        self.assertEqual(
            transition["prior_merkle_root"],
            anchor_receipt["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(transition["new_merkle_root"], anchor_receipt["merkle_root"])
        self.assertEqual(transition["treeship_artifact_id"], None)
        self.assertTrue(transition["trusted_provenance_verified"])
        self.assertFalse(transition["semantic_truth_guaranteed"])

    def test_verify_snapshot_surfaces_subject_lookup_restatement_supersession_transition_summary(self):
        stale = self.store.remember(
            "Incident owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Incident owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-10T00:00:00Z", "2024-01-10T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-15T00:00:00Z", "2024-02-15T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-10T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-15T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        result = self.store.verify_snapshot(self.store.snapshot())

        self.assertTrue(result["ok"])
        self.assertEqual(result["supersession_transition_count"], 1)
        self.assertEqual(result["verified_supersession_transition_count"], 1)
        self.assertEqual(len(result["supersession_transitions"]), 1)
        transition = result["supersession_transitions"][0]
        anchor_receipt = self.store.memory_write_receipts(current.id)[-1]
        self.assertEqual(transition["superseded_memory_id"], stale.id)
        self.assertEqual(transition["superseding_memory_ids"], [current.id])
        self.assertEqual(transition["superseded_at"], "2024-02-15T00:00:00Z")
        self.assertEqual(transition["supersession_reasons"], ["subject-lookup-restatement"])
        self.assertEqual(transition["anchor_memory_id"], current.id)
        self.assertEqual(transition["anchor_receipt_id"], anchor_receipt["receipt_id"])
        self.assertEqual(transition["anchor_receipt_hash"], anchor_receipt["receipt_hash"])
        self.assertEqual(transition["anchor_receipt_kind"], "zerker.memory.write_provenance")
        self.assertEqual(transition["anchor_event_hash"], anchor_receipt["event_hash"])
        self.assertEqual(transition["actor_id"], "human")
        self.assertEqual(transition["actor_uri"], "actor://human")
        self.assertEqual(transition["content_digest"], f"sha256:{current.content_hash}")
        self.assertEqual(
            transition["prior_merkle_root"],
            anchor_receipt["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(transition["new_merkle_root"], anchor_receipt["merkle_root"])
        self.assertEqual(transition["treeship_artifact_id"], None)
        self.assertTrue(transition["trusted_provenance_verified"])
        self.assertFalse(transition["semantic_truth_guaranteed"])

    def test_verify_snapshot_rejects_tampered_write_receipt_chain(self):
        memory = self.store.remember(
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
        self.store.promote(memory.id, actor_id="reviewer")
        snapshot = self.store.snapshot()

        tampered = json.loads(json.dumps(snapshot))
        tampered_receipt = tampered["write_receipts"][1]
        tampered_receipt["treeship_statement"]["evidence"]["prior_merkle_root"] = "bad-root"
        stripped_statement = json.loads(json.dumps(tampered_receipt["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered_receipt["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
        tampered["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in tampered.items() if k != "snapshot_hash"}))

        result = self.store.verify_snapshot(tampered)

        self.assertFalse(result["ok"])
        self.assertIn("snapshot write receipt chain invalid", result["error"])
        self.assertIn("prior_merkle_root mismatch", result["error"])

    def test_verify_snapshot_rejects_tampered_first_provenance_prior_merkle_root(self):
        self.store.remember(
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
        snapshot = self.store.snapshot()

        tampered = json.loads(json.dumps(snapshot))
        tampered_receipt = tampered["write_receipts"][0]
        tampered_receipt["treeship_statement"]["evidence"]["prior_merkle_root"] = "bad-root"
        stripped_statement = json.loads(json.dumps(tampered_receipt["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered_receipt["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
        tampered["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in tampered.items() if k != "snapshot_hash"}))

        result = self.store.verify_snapshot(tampered)

        self.assertFalse(result["ok"])
        self.assertIn("snapshot write receipt chain invalid", result["error"])
        self.assertIn("prior_merkle_root mismatch", result["error"])

    def test_verify_snapshot_surfaces_attested_write_receipt_artifacts(self):
        store = MemoryStore(Path(self.tmp.name) / "attested-snapshot.sqlite", treeship_auto_sign=True)
        store.init()
        signed_provenance = mock.Mock(
            returncode=0,
            stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
            stderr="",
        )
        signed_mutation = mock.Mock(
            returncode=0,
            stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
            stderr="",
        )
        with mock.patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
            with mock.patch("zerker_memory.treeship.subprocess.run", side_effect=[signed_provenance, signed_mutation]):
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

        result = store.verify_snapshot(store.snapshot())

        self.assertTrue(result["ok"])
        self.assertEqual(result["write_receipt_attestation_count"], 2)
        self.assertEqual(
            [item["artifact_id"] for item in result["attestation_artifacts"]],
            ["art_write_1", "art_write_2"],
        )

    def test_restore_rejects_snapshot_with_tampered_write_receipt_chain(self):
        memory = self.store.remember(
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
        self.store.promote(memory.id, actor_id="reviewer")
        snapshot = self.store.snapshot()

        tampered = json.loads(json.dumps(snapshot))
        tampered_receipt = tampered["write_receipts"][1]
        tampered_receipt["treeship_statement"]["evidence"]["prior_merkle_root"] = "bad-root"
        stripped_statement = json.loads(json.dumps(tampered_receipt["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered_receipt["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
        tampered["snapshot_hash"] = sha256_text(stable_json({k: v for k, v in tampered.items() if k != "snapshot_hash"}))

        restored = MemoryStore(Path(self.tmp.name) / "tampered-write-receipt.sqlite")
        with self.assertRaisesRegex(ValueError, "snapshot write receipt chain invalid"):
            restored.restore_snapshot(tampered)

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

    def test_verify_bundle_surfaces_supporting_provenance_anchor_summary(self):
        store = MemoryStore(Path(self.tmp.name) / "attested-bundle.sqlite", treeship_auto_sign=True)
        store.init()
        signed_provenance = subprocess.CompletedProcess(
            args=["treeship"],
            returncode=0,
            stdout='{"id":"art_write_bundle","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
            stderr="",
        )
        with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
            with patch("zerker_memory.treeship.subprocess.run", return_value=signed_provenance):
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

        result = store.verify_bundle(bundle)

        self.assertTrue(result["ok"])
        self.assertEqual(result["supporting_write_receipt_count"], 1)
        self.assertEqual(result["verified_supporting_write_receipt_count"], 1)
        self.assertTrue(result["supporting_provenance_verified"])
        self.assertEqual(len(result["supporting_provenance_receipts"]), 1)
        provenance = result["supporting_provenance_receipts"][0]
        self.assertEqual(provenance["memory_id"], memory.id)
        self.assertEqual(provenance["actor_id"], "codex")
        self.assertEqual(provenance["actor_uri"], "agent://codex/session-a")
        self.assertEqual(provenance["content_digest"], f"sha256:{memory.content_hash}")
        self.assertEqual(provenance["prior_merkle_root"], merkle_root([]))
        self.assertEqual(provenance["new_merkle_root"], provenance["merkle_root"])
        self.assertEqual(provenance["treeship_artifact_id"], "art_write_bundle")
        self.assertTrue(provenance["trusted_provenance_verified"])
        self.assertFalse(provenance["semantic_truth_guaranteed"])
        self.assertEqual(len(result["attestation_artifacts"]), 1)
        self.assertEqual(result["attestation_artifacts"][0]["artifact_id"], "art_write_bundle")
        self.assertTrue(result["trusted_provenance_verified"])
        self.assertFalse(result["semantic_truth_guaranteed"])

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

    def test_verify_bundle_rejects_tampered_supporting_write_receipt(self):
        self.store.remember(
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
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        supporting_receipt = bundle["supporting_memory_write_receipts"][bundle["supporting_memory_ids"][0]]
        supporting_receipt["treeship_statement"]["object"]["status"] = "quarantined"
        stripped_statement = json.loads(json.dumps(supporting_receipt["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(supporting_receipt["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        supporting_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertFalse(result["supporting_provenance_verified"])
        self.assertEqual(result["supporting_write_receipt_count"], 1)
        self.assertEqual(result["verified_supporting_write_receipt_count"], 0)
        self.assertIn("supporting write receipt", result["error"])
        self.assertIn("status mismatch", result["error"])

    def test_verify_bundle_rejects_supporting_write_receipt_key_missing_from_declared_supporting_ids(self):
        self.store.remember(
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
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        memory_id = bundle["supporting_memory_ids"][0]
        supporting_receipt = bundle["supporting_memory_write_receipts"].pop(memory_id)
        bundle["supporting_memory_write_receipts"]["mem_forged"] = supporting_receipt
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertFalse(result["supporting_provenance_verified"])
        self.assertFalse(result["trusted_provenance_verified"])
        self.assertEqual(result["supporting_write_receipt_count"], 1)
        self.assertEqual(result["verified_supporting_write_receipt_count"], 0)
        self.assertEqual(result["error"], "bundle supporting write receipt key missing from supporting_memory_ids")

    def test_verify_bundle_rejects_supporting_write_receipt_key_memory_id_mismatch(self):
        self.store.remember(
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
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        memory_id = bundle["supporting_memory_ids"][0]
        supporting_receipt = bundle["supporting_memory_write_receipts"].pop(memory_id)
        forged_key = "mem_forged"
        bundle["supporting_memory_ids"] = [forged_key]
        bundle["supporting_memory_write_receipts"][forged_key] = supporting_receipt
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertFalse(result["supporting_provenance_verified"])
        self.assertFalse(result["trusted_provenance_verified"])
        self.assertEqual(result["supporting_write_receipt_count"], 1)
        self.assertEqual(result["verified_supporting_write_receipt_count"], 0)
        self.assertEqual(result["error"], "bundle supporting write receipt memory_id mismatch")

    def test_verify_bundle_rejects_supporting_memory_entry_missing_from_declared_supporting_ids(self):
        self.store.remember(
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
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        bundle["supporting_memories"][0]["id"] = "mem_forged"
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertFalse(result["supporting_provenance_verified"])
        self.assertFalse(result["trusted_provenance_verified"])
        self.assertEqual(result["supporting_write_receipt_count"], 1)
        self.assertEqual(result["verified_supporting_write_receipt_count"], 1)
        self.assertEqual(result["error"], "bundle supporting memory id missing from supporting_memory_ids")

    def test_verify_bundle_rejects_duplicate_supporting_memory_entries(self):
        self.store.remember(
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
        receipt = self.store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
        bundle = self.store.receipt_bundle(receipt["action_id"])
        bundle["supporting_memories"].append(json.loads(json.dumps(bundle["supporting_memories"][0])))
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        result = self.store.verify_bundle(bundle)

        self.assertFalse(result["ok"])
        self.assertFalse(result["supporting_provenance_verified"])
        self.assertFalse(result["trusted_provenance_verified"])
        self.assertEqual(result["supporting_write_receipt_count"], 1)
        self.assertEqual(result["verified_supporting_write_receipt_count"], 1)
        self.assertEqual(result["error"], "bundle supporting memory id is duplicated")

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
