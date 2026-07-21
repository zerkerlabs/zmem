import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from zerker_memory.store import MemoryStore, merkle_root, sha256_text, stable_json
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
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])
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

    def test_exports_compact_memory_context_commitment(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.remember(
                "The release owner is Priya.",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )
            receipt = store.inject("Who owns the release?", agent_id="codex", risk="low", scope="project")

            statement = to_treeship_statement(receipt)

        commitment = receipt["memory_context"]
        self.assertEqual(statement["evidence"]["memory_context_digest"], commitment["context_digest"])
        self.assertEqual(statement["evidence"]["policy_digest"], commitment["policy_digest"])
        self.assertEqual(statement["source"]["memory_context_commitment"], commitment)
        self.assertNotIn("memories", statement["source"]["memory_context_commitment"])

    def test_rejects_incoherent_memory_context_commitment(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.remember(
                "The release owner is Priya.",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )
            receipt = store.inject("Who owns the release?", agent_id="codex", risk="low", scope="project")

        receipt["memory_context"]["action_id"] = "act_forged"
        with self.assertRaisesRegex(ValueError, "memory context commitment action_id mismatch"):
            to_treeship_statement(receipt)

    def test_embeds_bundle_proof_when_exporting_from_receipt_bundle(self):
        bundle = self._valid_bundle()

        statement = to_treeship_statement(bundle)

        self.assertEqual(statement["subject"]["id"], "act_bundle")
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])
        self.assertEqual(statement["evidence"]["bundle_hash"], bundle["bundle_hash"])
        self.assertEqual(statement["evidence"]["bundle_event_count"], 1)
        self.assertTrue(statement["evidence"]["bundle_verified"])
        self.assertEqual(statement["evidence"]["supporting_write_receipt_count"], 0)
        self.assertEqual(statement["evidence"]["verified_supporting_write_receipt_count"], 0)
        self.assertTrue(statement["evidence"]["trusted_provenance_verified"])
        self.assertEqual(statement["source"]["supporting_provenance_receipts"], [])
        self.assertEqual(statement["source"]["bundle"]["action_id"], "act_bundle")

    def test_bundle_statement_surfaces_verified_supporting_provenance_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.return_value.returncode = 0
                    run.return_value.stdout = (
                        '{"id":"art_write_bundle","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}'
                    )
                    run.return_value.stderr = ""

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

            statement = to_treeship_statement(bundle)

        self.assertEqual(statement["evidence"]["supporting_write_receipt_count"], 1)
        self.assertEqual(statement["evidence"]["verified_supporting_write_receipt_count"], 1)
        self.assertTrue(statement["evidence"]["trusted_provenance_verified"])
        self.assertEqual(len(statement["source"]["supporting_provenance_receipts"]), 1)
        provenance = statement["source"]["supporting_provenance_receipts"][0]
        self.assertEqual(provenance["memory_id"], memory.id)
        self.assertEqual(provenance["actor_id"], "codex")
        self.assertEqual(provenance["content_digest"], f"sha256:{memory.content_hash}")
        self.assertEqual(provenance["treeship_artifact_id"], "art_write_bundle")
        self.assertTrue(provenance["trusted_provenance_verified"])
        self.assertFalse(provenance["semantic_truth_guaranteed"])
        self.assertEqual(statement["source"]["attestation_artifacts"][0]["artifact_id"], "art_write_bundle")
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_rejects_bundle_with_tampered_supporting_write_receipt(self):
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
                status="active",
            )
            receipt = store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
            bundle = store.receipt_bundle(receipt["action_id"])

        supporting_receipt = bundle["supporting_memory_write_receipts"][memory.id]
        supporting_receipt["treeship_statement"]["object"]["status"] = "quarantined"
        stripped_statement = json.loads(json.dumps(supporting_receipt["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(supporting_receipt["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        supporting_receipt["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        with self.assertRaisesRegex(ValueError, "supporting write receipt .* verification failed: .*status mismatch"):
            to_treeship_statement(bundle)

    def test_rejects_bundle_with_rekeyed_supporting_write_receipt(self):
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
                status="active",
            )
            receipt = store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
            bundle = store.receipt_bundle(receipt["action_id"])

        supporting_receipt = bundle["supporting_memory_write_receipts"].pop(memory.id)
        bundle["supporting_memory_ids"] = ["mem_forged"]
        bundle["supporting_memory_write_receipts"]["mem_forged"] = supporting_receipt
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        with self.assertRaisesRegex(ValueError, "bundle supporting write receipt memory_id mismatch"):
            to_treeship_statement(bundle)

    def test_rejects_bundle_with_supporting_memory_entry_missing_from_declared_supporting_ids(self):
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

        bundle["supporting_memories"][0]["id"] = "mem_forged"
        bundle["bundle_hash"] = sha256_text(stable_json({k: v for k, v in bundle.items() if k != "bundle_hash"}))

        with self.assertRaisesRegex(ValueError, "bundle supporting memory id missing from supporting_memory_ids"):
            to_treeship_statement(bundle)

    def test_rejects_tampered_receipt_bundles(self):
        bundle = self._valid_bundle()
        bundle["bundle_hash"] = "bad"

        with self.assertRaisesRegex(ValueError, "bundle_hash mismatch"):
            to_treeship_statement(bundle)

    def test_exports_embedded_session_start_lifecycle_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Keep deploy rules separate from run history",
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

        statement = to_treeship_statement(started["receipt"])

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "session_mutation")
        self.assertEqual(statement["subject"]["id"], started["receipt"]["receipt_id"])
        self.assertEqual(statement["object"]["mutation"], "start_session")
        self.assertEqual(statement["object"]["actor_id"], "codex")
        self.assertEqual(statement["object"]["context_budget_tokens"], 256)
        self.assertEqual(statement["object"]["content_digest"], started["receipt"]["content_digest"])
        self.assertEqual(
            statement["evidence"]["prior_merkle_root"],
            started["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(statement["evidence"]["new_merkle_root"], started["receipt"]["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], started["receipt"]["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_embedded_session_end_lifecycle_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Keep deploy rules separate from run history",
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

        statement = to_treeship_statement(ended["receipt"])

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "session_mutation")
        self.assertEqual(statement["subject"]["id"], ended["receipt"]["receipt_id"])
        self.assertEqual(statement["object"]["mutation"], "end_session")
        self.assertEqual(statement["object"]["actor_id"], "codex")
        self.assertEqual(statement["object"]["content_digest"], ended["receipt"]["content_digest"])
        self.assertEqual(
            statement["evidence"]["prior_merkle_root"],
            ended["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(statement["evidence"]["new_merkle_root"], ended["receipt"]["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], ended["receipt"]["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_embedded_session_snapshot_lifecycle_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Keep deploy rules separate from run history",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="freeze before handoff",
            )

        statement = to_treeship_statement(session_snapshot["receipt"])

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "session_mutation")
        self.assertEqual(statement["subject"]["id"], session_snapshot["receipt"]["receipt_id"])
        self.assertEqual(statement["object"]["mutation"], "snapshot_session")
        self.assertEqual(statement["object"]["actor_id"], "codex")
        self.assertEqual(statement["object"]["content_digest"], session_snapshot["receipt"]["content_digest"])
        self.assertEqual(
            statement["evidence"]["prior_merkle_root"],
            session_snapshot["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(statement["evidence"]["new_merkle_root"], session_snapshot["receipt"]["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], session_snapshot["receipt"]["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_embedded_session_checkpoint_lifecycle_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            store.remember(
                "Keep deploy rules separate from run history",
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

        statement = to_treeship_statement(checkpoint["receipt"])

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "session_mutation")
        self.assertEqual(statement["subject"]["id"], checkpoint["receipt"]["receipt_id"])
        self.assertEqual(statement["object"]["mutation"], "checkpoint_session")
        self.assertEqual(statement["object"]["actor_id"], "codex")
        self.assertEqual(statement["object"]["content_digest"], checkpoint["receipt"]["content_digest"])
        self.assertEqual(
            statement["evidence"]["prior_merkle_root"],
            checkpoint["receipt"]["treeship_statement"]["evidence"]["prior_merkle_root"],
        )
        self.assertEqual(statement["evidence"]["new_merkle_root"], checkpoint["receipt"]["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], checkpoint["receipt"]["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_embedded_restore_lifecycle_statement(self):
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

        statement = to_treeship_statement(result["receipt"])

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "snapshot_restore")
        self.assertEqual(statement["subject"]["id"], result["receipt"]["receipt_id"])
        self.assertEqual(statement["object"]["mutation"], "restore_snapshot")
        self.assertEqual(statement["object"]["actor_id"], "snapshot_restore")
        self.assertEqual(statement["object"]["snapshot_hash"], snapshot["snapshot_hash"])
        self.assertEqual(statement["evidence"]["prior_merkle_root"], merkle_root([]))
        self.assertEqual(statement["evidence"]["new_merkle_root"], snapshot["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], result["receipt"]["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_memory_write_provenance_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.return_value.returncode = 0
                    run.return_value.stdout = (
                        '{"id":"art_write_export","kind":"memory.write","signed":"2026-06-28T11:30:00Z","status":"ok","system":"system://zmem"}'
                    )
                    run.return_value.stderr = ""
                    memory = store.remember(
                        "Status page owner is Alice",
                        memory_type="semantic",
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

        receipt = store.memory_write_receipt(memory.id)
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.write_provenance")
        self.assertEqual(statement["subject"]["type"], "memory_write")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "codex")
        self.assertEqual(statement["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(statement["evidence"]["prior_merkle_root"], merkle_root([]))
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(statement["attestation"]["artifact_id"], "art_write_export")
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_quarantined_memory_write_provenance_statement_honestly(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
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
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.write_provenance")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "codex")
        self.assertEqual(statement["object"]["status"], "quarantined")
        self.assertEqual(statement["object"]["authority"], "low")
        self.assertEqual(statement["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(statement["evidence"]["prior_merkle_root"], merkle_root([]))
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_attested_quarantined_memory_write_provenance_statement_honestly(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite", treeship_auto_sign=True)
            store.init()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run") as run:
                    run.return_value.returncode = 0
                    run.return_value.stdout = (
                        '{"id":"art_write_q","kind":"memory.write","signed":"2026-06-28T11:31:00Z","status":"ok","system":"system://zmem"}'
                    )
                    run.return_value.stderr = ""
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
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.write_provenance")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "codex")
        self.assertEqual(statement["object"]["status"], "quarantined")
        self.assertEqual(statement["object"]["authority"], "low")
        self.assertEqual(statement["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(statement["evidence"]["prior_merkle_root"], merkle_root([]))
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["receipt"]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(statement["attestation"]["artifact_id"], "art_write_q")
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_memory_mutation_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            memory = store.remember(
                "Status page owner is Alice",
                memory_type="semantic",
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
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "promote")
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], store.memory_write_receipts(memory.id)[0]["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_attested_memory_mutation_statement(self):
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
                    memory = store.remember(
                        "Status page owner is Alice",
                        memory_type="semantic",
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
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "promote")
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], store.memory_write_receipts(memory.id)[0]["receipt_id"])
        self.assertEqual(statement["attestation"]["artifact_id"], "art_write_2")
        self.assertEqual(statement["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_reject_memory_mutation_statement(self):
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
            prior_merkle_root = store.current_merkle_root()
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")

        receipt = store.memory_write_receipts(memory.id)[1]
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "reject")
        self.assertEqual(statement["object"]["status"], "deprecated")
        self.assertEqual(statement["object"]["authority"], "none")
        self.assertEqual(statement["object"]["reason"], "superseded runbook")
        self.assertEqual(statement["object"]["previous_status"], "quarantined")
        self.assertEqual(statement["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(statement["evidence"]["prior_merkle_root"], prior_merkle_root)
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], original_receipt["receipt_id"])
        self.assertEqual(statement["source"]["prior_receipt_hash"], original_receipt["receipt_hash"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_attested_reject_memory_mutation_statement(self):
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
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "reject")
        self.assertEqual(statement["object"]["reason"], "superseded runbook")
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], store.memory_write_receipts(memory.id)[0]["receipt_id"])
        self.assertEqual(statement["attestation"]["artifact_id"], "art_write_2")
        self.assertEqual(statement["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_revoke_memory_mutation_statement(self):
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
            prior_merkle_root = store.current_merkle_root()
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")

        receipt = store.memory_write_receipts(source.id)[1]
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], source.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "revoke")
        self.assertEqual(statement["object"]["status"], "revoked")
        self.assertEqual(statement["object"]["authority"], "none")
        self.assertEqual(statement["object"]["reason"], "source evidence was wrong")
        self.assertEqual(statement["object"]["revoked_ids"], [source.id, derived.id])
        self.assertEqual(statement["object"]["descendant_ids"], [derived.id])
        self.assertEqual(statement["object"]["descendant_count"], 1)
        self.assertEqual(statement["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(statement["evidence"]["prior_merkle_root"], prior_merkle_root)
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], original_receipt["receipt_id"])
        self.assertEqual(statement["source"]["prior_receipt_hash"], original_receipt["receipt_hash"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_attested_revoke_memory_mutation_statement(self):
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
        statement = to_treeship_statement(receipt)
        descendant_id = statement["object"]["descendant_ids"][0]

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], source.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "revoke")
        self.assertEqual(statement["object"]["reason"], "source evidence was wrong")
        self.assertEqual(statement["object"]["revoked_ids"], [source.id, descendant_id])
        self.assertEqual(statement["object"]["descendant_ids"], [descendant_id])
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], store.memory_write_receipts(source.id)[0]["receipt_id"])
        self.assertEqual(statement["attestation"]["artifact_id"], "art_write_3")
        self.assertEqual(statement["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_forget_memory_mutation_statement(self):
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
            prior_merkle_root = store.current_merkle_root()
            store.forget(memory.id, actor_id="reviewer")

        receipt = store.memory_write_receipts(memory.id)[1]
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "forget")
        self.assertEqual(statement["object"]["status"], "forgotten")
        self.assertEqual(statement["object"]["authority"], "low")
        self.assertEqual(statement["object"]["previous_status"], "active")
        self.assertEqual(statement["object"]["content_digest"], receipt["content_digest"])
        self.assertEqual(statement["evidence"]["prior_merkle_root"], prior_merkle_root)
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], original_receipt["receipt_id"])
        self.assertEqual(statement["source"]["prior_receipt_hash"], original_receipt["receipt_hash"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_exports_verified_attested_forget_memory_mutation_statement(self):
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
        statement = to_treeship_statement(receipt)

        self.assertEqual(statement["kind"], "zerker.memory.mutation_receipt")
        self.assertEqual(statement["subject"]["type"], "memory_mutation")
        self.assertEqual(statement["subject"]["id"], receipt["receipt_id"])
        self.assertEqual(statement["subject"]["memory_id"], memory.id)
        self.assertEqual(statement["object"]["actor_id"], "reviewer")
        self.assertEqual(statement["object"]["mutation"], "forget")
        self.assertEqual(statement["object"]["previous_status"], "active")
        self.assertEqual(statement["evidence"]["new_merkle_root"], receipt["merkle_root"])
        self.assertEqual(statement["source"]["prior_receipt_id"], store.memory_write_receipts(memory.id)[0]["receipt_id"])
        self.assertEqual(statement["attestation"]["artifact_id"], "art_write_2")
        self.assertEqual(statement["attestation"]["subject"], receipt["receipt_id"])
        self.assertFalse(statement["object"]["semantic_truth_guaranteed"])

    def test_rejects_tampered_forget_previous_status_memory_write_statement(self):
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
        tampered["treeship_statement"]["object"]["previous_status"] = "quarantined"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*previous_status mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_forget_actor_identity_memory_write_statement(self):
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
            to_treeship_statement(tampered)

    def test_rejects_tampered_promote_authority_memory_write_statement(self):
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
            store.promote(memory.id, actor_id="reviewer")

        tampered = json.loads(json.dumps(store.memory_write_receipts(memory.id)[1]))
        tampered["treeship_statement"]["object"]["authority"] = "none"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*promote authority mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_promote_actor_identity_memory_write_statement(self):
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
            store.promote(memory.id, actor_id="reviewer")

        tampered = json.loads(json.dumps(store.memory_write_receipts(memory.id)[1]))
        tampered["treeship_statement"]["object"]["actor_id"] = "mallory"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*actor_id mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_embedded_restore_lifecycle_statement(self):
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

        tampered = json.loads(json.dumps(result["receipt"]))
        tampered["treeship_statement"]["object"]["actor_id"] = "mallory"

        with self.assertRaisesRegex(ValueError, "lifecycle receipt_hash mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_memory_write_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            memory = store.remember(
                "Status page owner is Alice",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
            )

        tampered = json.loads(json.dumps(store.memory_write_receipt(memory.id)))
        tampered["treeship_statement"]["object"]["status"] = "active"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*status mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_reject_memory_write_statement(self):
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
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")

        tampered = json.loads(json.dumps(store.memory_write_receipts(memory.id)[1]))
        tampered["treeship_statement"]["object"]["reason"] = "forged reason"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*reject reason mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_reject_actor_identity_memory_write_statement(self):
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
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")

        tampered = json.loads(json.dumps(store.memory_write_receipts(memory.id)[1]))
        tampered["treeship_statement"]["object"]["actor_id"] = "mallory"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*actor_id mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_revoke_memory_write_statement(self):
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
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")

        tampered = json.loads(json.dumps(store.memory_write_receipts(source.id)[1]))
        tampered["treeship_statement"]["object"]["descendant_count"] = 0
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*descendant_count mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_revoke_reason_memory_write_statement(self):
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
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")

        tampered = json.loads(json.dumps(store.memory_write_receipts(source.id)[1]))
        tampered["treeship_statement"]["object"]["reason"] = "forged reason"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*revoke reason mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_revoke_previous_status_memory_write_statement(self):
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
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")

        tampered = json.loads(json.dumps(store.memory_write_receipts(source.id)[1]))
        tampered["treeship_statement"]["object"]["previous_status"] = "active"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*previous_status mismatch"):
            to_treeship_statement(tampered)

    def test_rejects_tampered_revoke_actor_identity_memory_write_statement(self):
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
            store.remember(
                "Deploy target is Railway",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                parents=[source.id],
            )
            store.revoke(source.id, actor_id="reviewer", reason="source evidence was wrong")

        tampered = json.loads(json.dumps(store.memory_write_receipts(source.id)[1]))
        tampered["treeship_statement"]["object"]["actor_id"] = "mallory"
        stripped_statement = json.loads(json.dumps(tampered["treeship_statement"]))
        stripped_statement.pop("attestation", None)
        tampered_hash_input = dict(tampered["treeship_statement"]["source"]["receipt"])
        tampered_hash_input["treeship_statement"] = stripped_statement
        tampered["receipt_hash"] = sha256_text(stable_json(tampered_hash_input))

        with self.assertRaisesRegex(ValueError, "write receipt .*actor_id mismatch"):
            to_treeship_statement(tampered)

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
