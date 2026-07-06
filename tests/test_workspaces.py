import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import create_handoff_package, main, restore_snapshot_file
from zerker_memory.store import MemoryStore
from zerker_memory.workspaces import (
    current_workspace,
    list_workspaces,
    register_workspace,
    use_workspace,
    workspace_source_report,
    workspace_status_for_paths,
)


class WorkspaceRegistryTest(unittest.TestCase):
    def test_register_list_current_and_use_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            alpha = tmp_path / "alpha"
            beta = tmp_path / "beta"
            alpha.mkdir()
            beta.mkdir()

            alpha_result = register_workspace(name="Alpha", root=alpha, registry_path=registry_path)
            beta_result = register_workspace(name="Beta", root=beta, registry_path=registry_path, make_current=False)

            listed = list_workspaces(registry_path=registry_path)
            self.assertTrue(listed["ok"])
            self.assertEqual([item["name"] for item in listed["items"]], ["Alpha", "Beta"])
            self.assertEqual(listed["current"], alpha_result["workspace"]["id"])

            current = current_workspace(registry_path=registry_path)
            self.assertEqual(current["workspace"]["name"], "Alpha")

            switched = use_workspace(beta_result["workspace"]["id"], registry_path=registry_path)
            self.assertTrue(switched["ok"])
            self.assertEqual(switched["workspace"]["name"], "Beta")

    def test_workspace_status_matches_current_db_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            result = register_workspace(name="Project", root=root, registry_path=registry_path)

            status = workspace_status_for_paths(
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            self.assertEqual(status["match_state"], "matched-current")
            self.assertEqual(status["matched"]["id"], result["workspace"]["id"])

    def test_workspace_source_report_groups_agents_sessions_and_proof_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            registered = register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            action = store.inject("review payment ownership", agent_id="codex", risk="medium", scope="project")
            memory = store.remember(
                "Payment service owner is Alice",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
                parent_action_id=action["action_id"],
            )

            report = workspace_source_report(
                store,
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            self.assertEqual(report["schema"], "zerker.workspace_sources.v1")
            self.assertEqual(report["workspace_id"], registered["workspace"]["id"])
            self.assertEqual(report["connected_agent_count"], 1)
            self.assertEqual(report["chat_session_count"], 1)
            self.assertEqual(report["connected_agents"][0]["agent_id"], "codex")
            self.assertEqual(report["connected_agents"][0]["tool"], "codex")
            self.assertEqual(report["connected_agents"][0]["repo_name"], "project")
            self.assertEqual(report["connected_agents"][0]["chat_session_ids"], ["chat://codex/session-17"])
            self.assertEqual(
                report["connected_agents"][0]["identity_anchor"]["key"],
                f"{registered['workspace']['id']}::codex",
            )
            self.assertEqual(
                report["connected_agents"][0]["identity_resolution"]["resolution_method"],
                "actor_uri_agent_scheme",
            )
            self.assertFalse(report["connected_agents"][0]["identity_resolution"]["cross_session"])
            self.assertEqual(report["sources"][0]["memory_id"], memory.id)
            self.assertEqual(report["sources"][0]["source_uri"], "conversation://codex/session-17/message-3")
            self.assertEqual(report["sources"][0]["source_identity"]["tool"], "codex")
            self.assertEqual(report["sources"][0]["source_identity"]["session_scheme"], "chat")
            self.assertEqual(report["sources"][0]["source_identity"]["source_scheme"], "conversation")
            self.assertEqual(report["sources"][0]["source_identity"]["origin_kind"], "chat_message")
            self.assertEqual(
                report["sources"][0]["source_identity"]["origin_summary"],
                "chat_message:codex/session-17/message-3",
            )
            self.assertEqual(
                report["sources"][0]["identity_anchor"]["key"],
                f"{registered['workspace']['id']}::codex",
            )
            self.assertEqual(
                report["sources"][0]["identity_anchor"]["resolution_method"],
                "actor_uri_agent_scheme",
            )
            self.assertEqual(report["sources"][0]["source_identity"]["repo_name"], "project")
            self.assertEqual(report["sources"][0]["source_identity"]["repo_root"], str(root.resolve()))
            self.assertEqual(report["sources"][0]["parent_action"]["action_id"], action["action_id"])
            self.assertEqual(report["sources"][0]["parent_action"]["agent_id"], "codex")
            self.assertEqual(report["sources"][0]["parent_action"]["risk"], "medium")
            self.assertEqual(report["sources"][0]["parent_action"]["task_summary"], "review payment ownership")
            self.assertTrue(report["sources"][0]["parent_action"]["available_local_receipt"])
            self.assertEqual(report["sources"][0]["proof_lineage"]["memory_id"], memory.id)
            self.assertEqual(
                report["sources"][0]["proof_lineage"]["treeship_statement_kind"],
                "zerker.memory.write_provenance",
            )
            self.assertIsNone(report["sources"][0]["proof_lineage"]["treeship_artifact_id"])
            self.assertEqual(report["connected_agents"][0]["latest_origin_summary"], "chat_message:codex/session-17/message-3")
            self.assertEqual(report["connected_agents"][0]["latest_parent_action"]["action_id"], action["action_id"])

    def test_workspace_source_report_resolves_cross_session_identity_anchor_per_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            registered = register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Release owner is Alice",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
            )
            store.remember(
                "Release runbook is in docs/release.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-22",
                session_id="chat://codex/session-22",
                source_uri="conversation://codex/session-22/message-4",
            )

            report = workspace_source_report(
                store,
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            self.assertEqual(report["connected_agent_count"], 1)
            agent = report["connected_agents"][0]
            self.assertEqual(agent["identity_anchor"]["key"], f"{registered['workspace']['id']}::codex")
            self.assertTrue(agent["identity_resolution"]["cross_session"])
            self.assertEqual(agent["identity_resolution"]["session_count"], 2)
            self.assertCountEqual(
                agent["chat_session_ids"],
                ["chat://codex/session-17", "chat://codex/session-22"],
            )
            for source in report["sources"]:
                self.assertEqual(source["identity_anchor"]["key"], f"{registered['workspace']['id']}::codex")
                self.assertEqual(source["identity_resolution"]["key"], f"{registered['workspace']['id']}::codex")
                self.assertTrue(source["identity_resolution"]["cross_session"])
                self.assertEqual(source["identity_resolution"]["session_count"], 2)

    def test_workspace_source_report_derives_non_conversation_origin_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Compiled local claim from ActiveGraph sync",
                memory_type="semantic",
                scope="project",
                source_kind="tool",
                actor_uri="agent://codex/sync-1",
                session_id="session://sync/run-1",
                source_uri="activegraph://event/evt-123#history-0",
            )

            report = workspace_source_report(
                store,
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            source_identity = report["sources"][0]["source_identity"]
            self.assertEqual(source_identity["origin_kind"], "activegraph_event")
            self.assertEqual(source_identity["origin_locator"], "event/evt-123#history-0")
            self.assertEqual(source_identity["origin_summary"], "activegraph_event:event/evt-123#history-0")
            self.assertEqual(report["connected_agents"][0]["latest_origin_summary"], "activegraph_event:event/evt-123#history-0")

    def test_workspace_source_report_surfaces_optional_treeship_attestation_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            memory = store.remember(
                "Release dashboard lives in the product repo",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
            )
            row = store.conn.execute(
                "SELECT receipt_id, treeship_statement_json FROM memory_write_receipts WHERE memory_id = ?",
                (memory.id,),
            ).fetchone()
            treeship_statement = json.loads(row["treeship_statement_json"])
            treeship_statement["attestation"] = {
                "schema": "zerker.memory.treeship_attestation.v1",
                "status": "signed",
                "system": "system://zmem",
                "subject": "ts-subject-123",
                "payload_digest": "sha256:abc123",
                "artifact_id": "ts_artifact_123",
                "signed_at": "2026-06-24T09:10:11Z",
            }
            store.conn.execute(
                "UPDATE memory_write_receipts SET treeship_statement_json = ? WHERE receipt_id = ?",
                (json.dumps(treeship_statement, sort_keys=True), row["receipt_id"]),
            )
            store.conn.commit()

            report = workspace_source_report(
                store,
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_attestation_status"], "signed")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_system"], "system://zmem")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_artifact_id"], "ts_artifact_123")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_subject_key"], "ts-subject-123")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_subject_type"], "memory_write")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_payload_digest"], "sha256:abc123")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_signed_at"], "2026-06-24T09:10:11Z")

    def test_workspace_source_report_surfaces_local_handoff_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Release checklist lives in docs/release.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
            )
            handoff = create_handoff_package(
                store,
                providers_path=root / ".zerker" / "providers.json",
                out_dir=root / ".zerker" / "handoff",
                action_id=None,
            )
            snapshot_payload = json.loads(Path(handoff["snapshot_path"]).read_text(encoding="utf-8"))

            report = workspace_source_report(
                store,
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            continuity = report["workspace_continuity"]
            self.assertEqual(continuity["kind"], "local_handoff_manifest")
            self.assertIsNone(continuity["action_id"])
            self.assertEqual(
                continuity["manifest_path"],
                str((root / ".zerker" / "handoff" / "handoff.json").resolve()),
            )
            self.assertEqual(continuity["snapshot_path"], str(Path(handoff["snapshot_path"]).resolve()))
            self.assertEqual(continuity["snapshot_hash"], snapshot_payload["snapshot_hash"])
            self.assertEqual(continuity["snapshot_merkle_root"], snapshot_payload["merkle_root"])

    def test_workspace_source_report_surfaces_local_restore_continuity_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.remember(
                "Imported workspace remembers the release checklist",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
            )
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            continuity_sidecar_path = snapshot_path.with_suffix(".continuity.json").resolve()

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)

            report = workspace_source_report(
                restored_store,
                db_path=root / ".zerker" / "imported.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            continuity = report["workspace_continuity"]
            self.assertEqual(continuity["kind"], "local_snapshot_restore")
            self.assertIsNone(continuity["action_id"])
            self.assertIsNone(continuity["manifest_path"])
            self.assertEqual(continuity["snapshot_path"], str(snapshot_path.resolve()))
            self.assertEqual(continuity["snapshot_hash"], snapshot_payload["snapshot_hash"])
            self.assertEqual(continuity["snapshot_merkle_root"], snapshot_payload["merkle_root"])
            self.assertEqual(continuity["continuity_sidecar_path"], str(continuity_sidecar_path))
            self.assertTrue(continuity["continuity_sidecar_ok"])
            self.assertEqual(continuity["restore_actor_uri"], "actor://snapshot_restore")
            self.assertTrue(str(continuity["restore_receipt_id"]).startswith("lr_"))
            self.assertTrue(str(continuity["restore_receipt_hash"]))
            source_imported_origin = report["sources"][0]["imported_origin"]
            self.assertEqual(source_imported_origin["kind"], "local_snapshot_restore")
            self.assertEqual(source_imported_origin["snapshot_hash"], snapshot_payload["snapshot_hash"])
            self.assertEqual(source_imported_origin["restore_receipt_id"], continuity["restore_receipt_id"])
            self.assertEqual(source_imported_origin["restore_receipt_hash"], continuity["restore_receipt_hash"])
            self.assertTrue(source_imported_origin["continuity_sidecar_ok"])
            self.assertEqual(report["connected_agents"][0]["agent_id"], "codex")
            self.assertEqual(
                report["connected_agents"][0]["latest_imported_origin"]["restore_receipt_id"],
                continuity["restore_receipt_id"],
            )

    def test_workspace_source_report_surfaces_imported_origin_on_claim_conflict_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            first = source_store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
                status="active",
            )
            second = source_store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/import-2",
                session_id="chat://openclaw/import-2",
                source_uri="conversation://openclaw/import-2/message-2",
                status="active",
            )
            source_store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
            )
            source_store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
            )
            source_store.conn.commit()
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)

            report = workspace_source_report(
                restored_store,
                db_path=root / ".zerker" / "imported.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            continuity = report["workspace_continuity"]
            self.assertEqual(report["claim_conflict_count"], 1)
            claims_by_id = {claim["memory_id"]: claim for claim in report["claim_conflicts"][0]["claims"]}
            self.assertEqual(
                claims_by_id[first.id]["imported_origin"]["restore_receipt_id"],
                continuity["restore_receipt_id"],
            )
            self.assertEqual(
                claims_by_id[second.id]["imported_origin"]["restore_receipt_hash"],
                continuity["restore_receipt_hash"],
            )
            self.assertEqual(
                claims_by_id[second.id]["imported_origin"]["snapshot_hash"],
                continuity["snapshot_hash"],
            )
            self.assertTrue(claims_by_id[first.id]["imported_origin"]["continuity_sidecar_ok"])

    def test_workspace_source_report_distinguishes_post_restore_local_claims_from_imported_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            imported = source_store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
                status="active",
            )
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)
            local = restored_store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/local-1",
                session_id="chat://openclaw/local-1",
                source_uri="conversation://openclaw/local-1/message-1",
                status="active",
            )
            restored_store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2099-01-01T00:00:00Z", "2099-01-01T00:00:00Z", local.id),
            )
            restored_store.conn.execute(
                "UPDATE memory_write_receipts SET created_at = ? WHERE memory_id = ?",
                ("2099-01-01T00:00:00Z", local.id),
            )
            restored_store.conn.commit()

            report = workspace_source_report(
                restored_store,
                db_path=root / ".zerker" / "imported.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            sources_by_id = {source["memory_id"]: source for source in report["sources"]}
            claims_by_id = {claim["memory_id"]: claim for claim in report["claim_conflicts"][0]["claims"]}
            agents_by_id = {agent["agent_id"]: agent for agent in report["connected_agents"]}
            continuity = report["workspace_continuity"]

            self.assertEqual(sources_by_id[imported.id]["restore_lineage"]["kind"], "imported_snapshot_write")
            self.assertEqual(
                sources_by_id[imported.id]["restore_lineage"]["basis"],
                "receipt_created_at<=restore_created_at",
            )
            self.assertEqual(
                sources_by_id[imported.id]["restore_lineage"]["restore_created_at"],
                continuity["created_at"],
            )
            self.assertEqual(sources_by_id[local.id]["restore_lineage"]["kind"], "local_post_restore_write")
            self.assertEqual(
                sources_by_id[local.id]["restore_lineage"]["basis"],
                "receipt_created_at>restore_created_at",
            )
            self.assertEqual(
                sources_by_id[local.id]["restore_lineage"]["restore_created_at"],
                continuity["created_at"],
            )
            self.assertEqual(
                sources_by_id[local.id]["restore_lineage"]["source_receipt_created_at"],
                "2099-01-01T00:00:00Z",
            )
            self.assertIn("imported_origin", sources_by_id[imported.id])
            self.assertNotIn("imported_origin", sources_by_id[local.id])
            self.assertEqual(claims_by_id[imported.id]["restore_lineage"]["kind"], "imported_snapshot_write")
            self.assertEqual(claims_by_id[local.id]["restore_lineage"]["kind"], "local_post_restore_write")
            self.assertIn("imported_origin", claims_by_id[imported.id])
            self.assertNotIn("imported_origin", claims_by_id[local.id])
            self.assertEqual(agents_by_id["codex"]["latest_restore_lineage"]["kind"], "imported_snapshot_write")
            self.assertEqual(agents_by_id["openclaw"]["latest_restore_lineage"]["kind"], "local_post_restore_write")
            self.assertIsNone(agents_by_id["openclaw"]["latest_imported_origin"])

    def test_workspace_source_report_surfaces_failed_local_restore_continuity_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.remember(
                "Imported workspace remembers the release checklist",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
            )
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)
            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["snapshot_hash"] = "sha256:copied-sidecar"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)

            report = workspace_source_report(
                restored_store,
                db_path=root / ".zerker" / "imported.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            continuity = report["workspace_continuity"]
            self.assertEqual(continuity["kind"], "local_snapshot_restore")
            self.assertFalse(continuity["continuity_sidecar_ok"])
            self.assertEqual(continuity["continuity_sidecar_path"], str(continuity_path.resolve()))
            self.assertIn("continuity sidecar snapshot hash mismatch", continuity["continuity_error"])

    def test_workspace_source_report_surfaces_cross_agent_claim_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            first_action = store.inject(
                "capture first incident-owner claim",
                agent_id="codex",
                risk="medium",
                scope="project",
            )
            second_action = store.inject(
                "capture second incident-owner claim",
                agent_id="openclaw",
                risk="high",
                scope="project",
            )
            first = store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
                status="active",
                parent_action_id=first_action["action_id"],
            )
            second = store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/chat-22",
                session_id="chat://openclaw/session-22",
                source_uri="conversation://openclaw/session-22/message-9",
                status="active",
                parent_action_id=second_action["action_id"],
            )
            store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
            )
            store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
            )
            store.conn.commit()

            report = workspace_source_report(
                store,
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            self.assertEqual(report["claim_conflict_count"], 1)
            conflict = report["claim_conflicts"][0]
            self.assertEqual(conflict["entity_key"], "incident owner")
            self.assertEqual(conflict["relation"], "is")
            self.assertTrue(conflict["cross_session"])
            self.assertEqual(conflict["connected_agent_ids"], ["codex", "openclaw"])
            self.assertEqual(conflict["merge_preview"]["resolution_outcome"], "resolved")
            self.assertEqual(conflict["merge_preview"]["chosen_memory_id"], second.id)
            self.assertEqual(conflict["merge_preview"]["chosen_value"], "priya")
            self.assertEqual(conflict["merge_preview"]["resolution_basis"]["field"], "updated_at")
            self.assertEqual(conflict["merge_preview"]["resolution_basis"]["summary"], "freshest updated_at")
            self.assertEqual(
                conflict["merge_preview"]["decisive_claim_lineage"]["memory_id"],
                second.id,
            )
            self.assertEqual(
                conflict["merge_preview"]["decisive_claim_lineage"]["field"],
                "updated_at",
            )
            self.assertEqual(
                conflict["merge_preview"]["decisive_claim_lineage"]["summary"],
                "freshest updated_at came from openclaw @ chat://openclaw/session-22",
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_contrast"]["field"],
                "updated_at",
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_contrast"]["losing_memory_ids"],
                [first.id],
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_contrast"]["summary"],
                "freshest updated_at kept openclaw @ chat://openclaw/session-22 (2024-02-01T00:00:00Z) over codex @ chat://codex/session-17 (2024-01-01T00:00:00Z)",
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_parent_action"]["memory_id"],
                first.id,
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_parent_action"]["parent_action"]["action_id"],
                first_action["action_id"],
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_parent_action"]["parent_action"]["risk"],
                "medium",
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_parent_action"]["parent_action"]["task_summary"],
                "capture first incident-owner claim",
            )
            self.assertEqual(
                conflict["merge_preview"]["losing_claim_parent_action"]["summary"],
                f"losing claim came from {first_action['action_id']} by codex @ chat://codex/session-17",
            )
            self.assertEqual(
                [step["summary"] for step in conflict["merge_preview"]["resolution_trace"]],
                [
                    "authority kept 2 claims tied at low",
                    "trust kept 2 claims tied at 0.50",
                    "updated_at selected 2024-02-01T00:00:00Z",
                ],
            )
            claims_by_id = {claim["memory_id"]: claim for claim in conflict["claims"]}
            self.assertEqual(claims_by_id[first.id]["source_identity"]["tool"], "codex")
            self.assertEqual(claims_by_id[second.id]["source_identity"]["tool"], "openclaw")
            self.assertEqual(claims_by_id[first.id]["source_identity"]["repo_name"], "project")
            self.assertEqual(claims_by_id[first.id]["parent_action"]["action_id"], first_action["action_id"])
            self.assertEqual(claims_by_id[second.id]["parent_action"]["action_id"], second_action["action_id"])
            self.assertEqual(claims_by_id[second.id]["parent_action"]["risk"], "high")
            self.assertEqual(conflict["claims"][0]["proof_lineage"]["treeship_statement_kind"], "zerker.memory.write_provenance")

    def test_workspace_source_report_surfaces_unresolved_exact_tie_claim_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            first = store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
                status="active",
                trust=0.95,
                authority="medium",
            )
            second = store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/chat-22",
                session_id="chat://openclaw/session-22",
                source_uri="conversation://openclaw/session-22/message-9",
                status="active",
                trust=0.95,
                authority="medium",
            )
            shared_timestamp = "2024-02-01T00:00:00Z"
            store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
                (shared_timestamp, shared_timestamp, first.id, second.id),
            )
            store.conn.commit()

            report = workspace_source_report(
                store,
                db_path=root / ".zerker" / "memory.sqlite",
                policy_path=root / ".zerker" / "policy.json",
                registry_path=registry_path,
            )

            self.assertEqual(report["claim_conflict_count"], 1)
            conflict = report["claim_conflicts"][0]
            self.assertEqual(conflict["merge_preview"]["resolution_outcome"], "abstained")
            self.assertIsNone(conflict["merge_preview"]["chosen_memory_id"])
            self.assertIsNone(conflict["merge_preview"]["decisive_claim_lineage"])
            self.assertIsNone(conflict["merge_preview"]["losing_claim_contrast"])
            self.assertIsNone(conflict["merge_preview"]["losing_claim_parent_action"])
            self.assertCountEqual(conflict["merge_preview"]["abstained_memory_ids"], [first.id, second.id])
            self.assertEqual(conflict["merge_preview"]["tie_fields"], ["authority", "trust", "updated_at", "created_at"])
            self.assertEqual(
                conflict["merge_preview"]["resolution_basis"]["summary"],
                "exact tie on authority, trust, updated_at, created_at",
            )
            self.assertEqual(
                [step["summary"] for step in conflict["merge_preview"]["resolution_trace"]],
                [
                    "authority kept 2 claims tied at medium",
                    "trust kept 2 claims tied at 0.95",
                    "updated_at kept 2 claims tied at 2024-02-01T00:00:00Z",
                    "created_at kept 2 claims tied at 2024-02-01T00:00:00Z",
                ],
            )

    def test_workspace_sources_cli_prints_read_only_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Deploy approvals live in the release checklist",
                memory_type="procedural",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/chat-4",
                session_id="chat://openclaw/session-4",
                source_uri="conversation://openclaw/session-4/message-9",
            )
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "memory.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                        ]
                    )

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["schema"], "zerker.workspace_sources.v1")
            self.assertEqual(payload["connected_agents"][0]["agent_id"], "openclaw")
            self.assertEqual(payload["sources"][0]["chat_session_id"], "chat://openclaw/session-4")
            self.assertEqual(payload["sources"][0]["workspace_id"], payload["workspace_id"])

    def test_workspace_sources_cli_summary_surfaces_unresolved_exact_tie(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            first = store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
                status="active",
                trust=0.95,
                authority="medium",
            )
            second = store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/chat-22",
                session_id="chat://openclaw/session-22",
                source_uri="conversation://openclaw/session-22/message-9",
                status="active",
                trust=0.95,
                authority="medium",
            )
            shared_timestamp = "2024-02-01T00:00:00Z"
            store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
                (shared_timestamp, shared_timestamp, first.id, second.id),
            )
            store.conn.commit()
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "memory.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Workspace sources", summary)
            self.assertIn("Claim conflicts: 1", summary)
            self.assertIn("unresolved exact tie", summary)
            self.assertIn("authority, trust, updated_at, created_at", summary)
            self.assertIn("ignored tie breakers: retrieval_rank, memory_id", summary)
            self.assertIn("abstention basis: exact tie on authority, trust, updated_at, created_at", summary)
            self.assertIn("decision trace:", summary)
            self.assertIn("authority kept 2 claims tied at medium", summary)
            self.assertIn("trust kept 2 claims tied at 0.95", summary)
            self.assertIn("updated_at kept 2 claims tied at 2024-02-01T00:00:00Z", summary)
            self.assertIn("created_at kept 2 claims tied at 2024-02-01T00:00:00Z", summary)
            self.assertIn("alex: codex @ chat://codex/session-17", summary)
            self.assertIn("priya: openclaw @ chat://openclaw/session-22", summary)
            self.assertIn("conversation://codex/session-17/message-3", summary)
            self.assertIn("conversation://openclaw/session-22/message-9", summary)
            self.assertIn("status=active authority=medium trust=0.95", summary)
            self.assertIn("workspace=ws_", summary)
            self.assertIn("session_scheme=chat source_scheme=conversation origin=chat_message:codex/session-17/message-3", summary)
            self.assertIn("identity=ws_", summary)
            self.assertIn("via=actor_uri_agent_scheme", summary)
            self.assertIn("attestation=none", summary)
            self.assertIn("root=", summary)
            self.assertIn("tool=codex repo=project", summary)
            self.assertIn("tool=openclaw repo=project", summary)

    def test_workspace_sources_cli_summary_surfaces_resolution_basis_for_resolved_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            first_action = store.inject(
                "capture first incident-owner claim",
                agent_id="codex",
                risk="medium",
                scope="project",
            )
            second_action = store.inject(
                "capture second incident-owner claim",
                agent_id="openclaw",
                risk="high",
                scope="project",
            )
            first = store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
                status="active",
                parent_action_id=first_action["action_id"],
            )
            second = store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/chat-22",
                session_id="chat://openclaw/session-22",
                source_uri="conversation://openclaw/session-22/message-9",
                status="active",
                parent_action_id=second_action["action_id"],
            )
            store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
            )
            store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
            )
            row = store.conn.execute(
                "SELECT receipt_id, treeship_statement_json FROM memory_write_receipts WHERE memory_id = ?",
                (second.id,),
            ).fetchone()
            treeship_statement = json.loads(row["treeship_statement_json"])
            treeship_statement["attestation"] = {
                "schema": "zerker.memory.treeship_attestation.v1",
                "status": "signed",
                "system": "system://zmem",
                "subject": "ts-conflict-subject-123",
                "payload_digest": "sha256:0123456789abcdef",
                "artifact_id": "ts_conflict_123",
                "signed_at": "2026-06-28T03:20:00Z",
            }
            store.conn.execute(
                "UPDATE memory_write_receipts SET treeship_statement_json = ? WHERE receipt_id = ?",
                (json.dumps(treeship_statement, sort_keys=True), row["receipt_id"]),
            )
            store.conn.commit()
            chosen_lineage = store.conn.execute(
                "SELECT event_hash, receipt_hash FROM memory_write_receipts WHERE memory_id = ?",
                (second.id,),
            ).fetchone()
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "memory.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("resolved: incident owner is -> priya", summary)
            self.assertIn("resolution basis: freshest updated_at", summary)
            self.assertIn(
                "decision source: freshest updated_at came from openclaw @ chat://openclaw/session-22",
                summary,
            )
            self.assertIn(
                "decision contrast: freshest updated_at kept openclaw @ chat://openclaw/session-22 (2024-02-01T00:00:00Z) over codex @ chat://codex/session-17 (2024-01-01T00:00:00Z)",
                summary,
            )
            self.assertIn(
                "losing action: losing claim came from act_",
                summary,
            )
            self.assertIn(
                "losing_action=act_",
                summary,
            )
            self.assertIn(
                "losing_agent=codex losing_risk=medium losing_receipt=local losing_task=capture first incident-owner claim",
                summary,
            )
            self.assertIn("decision trace:", summary)
            self.assertIn("authority kept 2 claims tied at low", summary)
            self.assertIn("trust kept 2 claims tied at 0.50", summary)
            self.assertIn("updated_at selected 2024-02-01T00:00:00Z", summary)
            self.assertIn("chosen priya: openclaw @ chat://openclaw/session-22", summary)
            self.assertIn("other alex: codex @ chat://codex/session-17", summary)
            self.assertIn("session_scheme=chat source_scheme=conversation origin=chat_message:openclaw/session-22/message-9", summary)
            self.assertIn("identity=ws_", summary)
            self.assertIn("via=actor_uri_agent_scheme", summary)
            self.assertIn("latest_attestation=signed", summary)
            self.assertIn("latest_system=system://zmem", summary)
            self.assertIn("latest_subject=ts-conflict-subject-123", summary)
            self.assertIn("latest_signed_at=2026-06-28T03:20:00Z", summary)
            self.assertIn(f"latest_event_hash={chosen_lineage['event_hash'][:12]}...", summary)
            self.assertIn(f"latest_receipt_hash={chosen_lineage['receipt_hash'][:12]}...", summary)
            self.assertIn("latest_payload_digest=sha256:01234567...", summary)
            self.assertIn(
                (
                    "attestation=signed system=system://zmem subject=ts-conflict-subject-123 signed_at=2026-06-28T03:20:00Z "
                    f"payload_digest=sha256:01234567... event_hash={chosen_lineage['event_hash'][:12]}... "
                    f"receipt_hash={chosen_lineage['receipt_hash'][:12]}..."
                ),
                summary,
            )
            self.assertIn("tool=openclaw repo=project", summary)

    def test_workspace_sources_cli_summary_surfaces_cross_session_identity_resolution_for_recent_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            registered = register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Release owner is Alice",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
            )
            store.remember(
                "Release runbook is in docs/release.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-22",
                session_id="chat://codex/session-22",
                source_uri="conversation://codex/session-22/message-4",
            )
            store.remember(
                "Release slack channel is #launch",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-39",
                session_id="chat://codex/session-39",
                source_uri="conversation://codex/session-39/message-5",
            )
            store.remember(
                "Release owner backup is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-44",
                session_id="chat://codex/session-44",
                source_uri="conversation://codex/session-44/message-6",
            )
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "memory.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("conversation://codex/session-22/message-4", summary)
            self.assertIn(
                f"identity={registered['workspace']['id']}::codex via=actor_uri_agent_scheme cross_session=yes sessions=4",
                summary,
            )
            self.assertIn(
                "chat_sessions=chat://codex/session-17,chat://codex/session-22,chat://codex/session-39,+1 more",
                summary,
            )
            self.assertIn(
                (
                    "source_uris=conversation://codex/session-17/message-3,"
                    "conversation://codex/session-22/message-4,"
                    "conversation://codex/session-39/message-5,+1 more"
                ),
                summary,
            )
            self.assertIn("tool=codex repo=project", summary)

    def test_workspace_sources_cli_summary_surfaces_recent_source_identity_and_treeship_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            action = store.inject("review release-dashboard memory", agent_id="codex", risk="medium", scope="project")
            memory = store.remember(
                "Release dashboard lives in the product repo",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
                status="active",
                parent_action_id=action["action_id"],
            )
            row = store.conn.execute(
                "SELECT receipt_id, treeship_statement_json FROM memory_write_receipts WHERE memory_id = ?",
                (memory.id,),
            ).fetchone()
            treeship_statement = json.loads(row["treeship_statement_json"])
            treeship_statement["attestation"] = {
                "schema": "zerker.memory.treeship_attestation.v1",
                "status": "signed",
                "system": "system://zmem",
                "subject": "ts-source-subject-123",
                "payload_digest": "sha256:0123456789abcdef",
                "artifact_id": "ts_artifact_123",
                "signed_at": "2026-06-24T09:10:11Z",
            }
            store.conn.execute(
                "UPDATE memory_write_receipts SET treeship_statement_json = ? WHERE receipt_id = ?",
                (json.dumps(treeship_statement, sort_keys=True), row["receipt_id"]),
            )
            store.conn.commit()
            source_lineage = store.conn.execute(
                "SELECT event_hash, receipt_hash FROM memory_write_receipts WHERE memory_id = ?",
                (memory.id,),
            ).fetchone()
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "memory.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Recent sources:", summary)
            self.assertIn("tool=codex repo=project", summary)
            self.assertIn("workspace=ws_", summary)
            self.assertIn("latest_artifact=ts_artifact_123", summary)
            self.assertIn("latest_attestation=signed", summary)
            self.assertIn("latest_system=system://zmem", summary)
            self.assertIn("latest_subject=ts-source-subject-123", summary)
            self.assertIn("latest_signed_at=2026-06-24T09:10:11Z", summary)
            self.assertIn(f"latest_event_hash={source_lineage['event_hash'][:12]}...", summary)
            self.assertIn(f"latest_receipt_hash={source_lineage['receipt_hash'][:12]}...", summary)
            self.assertIn("latest_origin=chat_message:codex/session-17/message-3", summary)
            self.assertIn(f"latest_parent_action={action['action_id']}", summary)
            self.assertIn("latest_parent_agent=codex", summary)
            self.assertIn("latest_parent_risk=medium", summary)
            self.assertIn("identity=ws_", summary)
            self.assertIn("via=actor_uri_agent_scheme", summary)
            self.assertIn("cross_session=no", summary)
            self.assertIn("artifact=ts_artifact_123", summary)
            self.assertIn(f"parent_action={action['action_id']}", summary)
            self.assertIn("parent_agent=codex", summary)
            self.assertIn("parent_risk=medium", summary)
            self.assertIn("latest_payload_digest=sha256:01234567...", summary)
            self.assertIn(
                (
                    "attestation=signed system=system://zmem subject=ts-source-subject-123 signed_at=2026-06-24T09:10:11Z "
                    f"payload_digest=sha256:01234567... event_hash={source_lineage['event_hash'][:12]}... "
                    f"receipt_hash={source_lineage['receipt_hash'][:12]}..."
                ),
                summary,
            )

    def test_workspace_sources_cli_summary_surfaces_cross_session_identity_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Release owner is Alice",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
            )
            store.remember(
                "Release runbook is in docs/release.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-22",
                session_id="chat://codex/session-22",
                source_uri="conversation://codex/session-22/message-4",
            )
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "memory.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("codex: 2 receipts, 2 sessions", summary)
            self.assertIn("latest_origin=chat_message:codex/session-22/message-4", summary)
            self.assertIn("identity=ws_", summary)
            self.assertIn("via=actor_uri_agent_scheme", summary)
            self.assertIn("cross_session=yes", summary)
            self.assertIn("attestation=none", summary)
            self.assertIn("session_scheme=chat source_scheme=conversation origin=chat_message:codex/session-17/message-3", summary)
            self.assertIn("conversation://codex/session-17/message-3", summary)

    def test_workspace_sources_cli_summary_surfaces_local_handoff_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Release checklist lives in docs/release.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
            )
            handoff = create_handoff_package(
                store,
                providers_path=root / ".zerker" / "providers.json",
                out_dir=root / ".zerker" / "handoff",
                action_id=None,
            )
            snapshot_payload = json.loads(Path(handoff["snapshot_path"]).read_text(encoding="utf-8"))
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "memory.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Workspace continuity: local_handoff_manifest", summary)
            snapshot_hash = str(snapshot_payload["snapshot_hash"])
            expected_snapshot_hash = (
                f"sha256:{snapshot_hash.split(':', 1)[1][:8]}..."
                if ":" in snapshot_hash
                else f"{snapshot_hash[:12]}..."
            )
            self.assertIn(
                f"snapshot_hash={expected_snapshot_hash}",
                summary,
            )
            self.assertIn("action_id=none", summary)
            self.assertIn("manifest=", summary)
            self.assertIn("handoff.json", summary)

    def test_workspace_sources_cli_summary_surfaces_local_restore_continuity_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.remember(
                "Imported workspace remembers the release checklist",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
            )
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "imported.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Workspace continuity: local_snapshot_restore", summary)
            snapshot_hash = str(snapshot_payload["snapshot_hash"])
            expected_snapshot_hash = (
                f"sha256:{snapshot_hash.split(':', 1)[1][:8]}..."
                if ":" in snapshot_hash
                else f"{snapshot_hash[:12]}..."
            )
            self.assertIn(f"snapshot_hash={expected_snapshot_hash}", summary)
            self.assertIn("restore_receipt=lr_", summary)
            self.assertIn("continuity=ok", summary)
            self.assertIn("sidecar=", summary)
            self.assertIn("snapshot=", summary)
            self.assertIn("imports/snapshot.json", summary)
            self.assertIn("latest_imported_restore=lr_", summary)
            self.assertIn(f"latest_imported_snapshot={expected_snapshot_hash}", summary)
            self.assertIn("latest_imported_continuity=ok", summary)
            self.assertIn("imported_restore=lr_", summary)
            self.assertIn(f"imported_snapshot={expected_snapshot_hash}", summary)
            self.assertIn("imported_continuity=ok", summary)

    def test_workspace_sources_cli_summary_surfaces_imported_origin_on_claim_conflict_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            first = source_store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
                status="active",
            )
            second = source_store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/import-2",
                session_id="chat://openclaw/import-2",
                source_uri="conversation://openclaw/import-2/message-2",
                status="active",
            )
            source_store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
            )
            source_store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
            )
            source_store.conn.commit()
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "imported.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            snapshot_hash = str(snapshot_payload["snapshot_hash"])
            expected_snapshot_hash = (
                f"sha256:{snapshot_hash.split(':', 1)[1][:8]}..."
                if ":" in snapshot_hash
                else f"{snapshot_hash[:12]}..."
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("resolved: incident owner is -> priya", summary)
            self.assertIn("chosen priya: openclaw @ chat://openclaw/import-2", summary)
            self.assertIn("other alex: codex @ chat://codex/import-1", summary)
            self.assertIn("imported_restore=lr_", summary)
            self.assertIn(f"imported_snapshot={expected_snapshot_hash}", summary)
            self.assertIn("imported_continuity=ok", summary)

    def test_workspace_sources_cli_summary_distinguishes_post_restore_local_claims_from_imported_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
                status="active",
            )
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)
            local = restored_store.remember(
                "Incident owner is Priya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/local-1",
                session_id="chat://openclaw/local-1",
                source_uri="conversation://openclaw/local-1/message-1",
                status="active",
            )
            restored_store.conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2099-01-01T00:00:00Z", "2099-01-01T00:00:00Z", local.id),
            )
            restored_store.conn.execute(
                "UPDATE memory_write_receipts SET created_at = ? WHERE memory_id = ?",
                ("2099-01-01T00:00:00Z", local.id),
            )
            restored_store.conn.commit()
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "imported.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("latest_restore_lineage=imported_snapshot_write", summary)
            self.assertIn("latest_restore_basis=receipt_created_at<=restore_created_at", summary)
            self.assertIn("latest_restore_lineage=local_post_restore_write", summary)
            self.assertIn("latest_restore_basis=receipt_created_at>restore_created_at", summary)
            imported_line = next(line for line in summary.splitlines() if "other alex:" in line)
            local_line = next(line for line in summary.splitlines() if "chosen priya:" in line)
            self.assertIn("restore_lineage=imported_snapshot_write", imported_line)
            self.assertIn("restore_basis=receipt_created_at<=restore_created_at", imported_line)
            self.assertIn("imported_restore=lr_", imported_line)
            self.assertIn("restore_lineage=local_post_restore_write", local_line)
            self.assertIn("restore_basis=receipt_created_at>restore_created_at", local_line)
            self.assertIn("source_receipt_at=2099-01-01T00:00:00Z", local_line)
            self.assertNotIn("imported_restore=", local_line)

    def test_workspace_sources_cli_summary_surfaces_failed_local_restore_continuity_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            register_workspace(name="Project", root=root, registry_path=registry_path)
            source_db_path = root / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.remember(
                "Imported workspace remembers the release checklist",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/import-1",
                session_id="chat://codex/import-1",
                source_uri="conversation://codex/import-1/message-1",
            )
            snapshot_path = root / ".zerker" / "imports" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            self.assertEqual(export_exit_code, 0)
            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["snapshot_hash"] = "sha256:copied-sidecar"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            restored_store = MemoryStore(root / ".zerker" / "imported.sqlite")
            restore_snapshot_file(restored_store, snapshot_path=snapshot_path)
            output = io.StringIO()

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(root / ".zerker" / "imported.sqlite"),
                            "--policy",
                            str(root / ".zerker" / "policy.json"),
                            "ws",
                            "sources",
                            "--limit",
                            "5",
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Workspace continuity: local_snapshot_restore", summary)
            self.assertIn("continuity=failed", summary)
            self.assertIn("error=continuity sidecar snapshot hash mismatch", summary)
            self.assertIn("sidecar=", summary)


if __name__ == "__main__":
    unittest.main()
