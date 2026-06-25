import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import main
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
            memory = store.remember(
                "Payment service owner is Alice",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
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
            self.assertEqual(report["sources"][0]["memory_id"], memory.id)
            self.assertEqual(report["sources"][0]["source_uri"], "conversation://codex/session-17/message-3")
            self.assertEqual(report["sources"][0]["source_identity"]["tool"], "codex")
            self.assertEqual(report["sources"][0]["source_identity"]["session_scheme"], "chat")
            self.assertEqual(report["sources"][0]["source_identity"]["source_scheme"], "conversation")
            self.assertEqual(report["sources"][0]["source_identity"]["repo_name"], "project")
            self.assertEqual(report["sources"][0]["source_identity"]["repo_root"], str(root.resolve()))
            self.assertEqual(report["sources"][0]["proof_lineage"]["memory_id"], memory.id)
            self.assertEqual(
                report["sources"][0]["proof_lineage"]["treeship_statement_kind"],
                "zerker.memory.write_provenance",
            )
            self.assertIsNone(report["sources"][0]["proof_lineage"]["treeship_artifact_id"])

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
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_artifact_id"], "ts_artifact_123")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_payload_digest"], "sha256:abc123")
            self.assertEqual(report["sources"][0]["proof_lineage"]["treeship_signed_at"], "2026-06-24T09:10:11Z")

    def test_workspace_source_report_surfaces_cross_agent_claim_conflicts(self):
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
            claims_by_id = {claim["memory_id"]: claim for claim in conflict["claims"]}
            self.assertEqual(claims_by_id[first.id]["source_identity"]["tool"], "codex")
            self.assertEqual(claims_by_id[second.id]["source_identity"]["tool"], "openclaw")
            self.assertEqual(claims_by_id[first.id]["source_identity"]["repo_name"], "project")
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
            self.assertCountEqual(conflict["merge_preview"]["abstained_memory_ids"], [first.id, second.id])
            self.assertEqual(conflict["merge_preview"]["tie_fields"], ["authority", "trust", "updated_at", "created_at"])
            self.assertEqual(
                conflict["merge_preview"]["resolution_basis"]["summary"],
                "exact tie on authority, trust, updated_at, created_at",
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
            self.assertIn("abstention basis: exact tie on authority, trust, updated_at, created_at", summary)
            self.assertIn("alex: codex @ chat://codex/session-17", summary)
            self.assertIn("priya: openclaw @ chat://openclaw/session-22", summary)
            self.assertIn("conversation://codex/session-17/message-3", summary)
            self.assertIn("conversation://openclaw/session-22/message-9", summary)
            self.assertIn("status=active authority=medium trust=0.95", summary)
            self.assertIn("workspace=ws_", summary)
            self.assertIn("session_scheme=chat source_scheme=conversation", summary)
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
            first = store.remember(
                "Incident owner is Alex",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
                status="active",
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
            self.assertIn("chosen priya: openclaw @ chat://openclaw/session-22", summary)
            self.assertIn("other alex: codex @ chat://codex/session-17", summary)
            self.assertIn("session_scheme=chat source_scheme=conversation", summary)
            self.assertIn("attestation=none", summary)
            self.assertIn("tool=openclaw repo=project", summary)
            self.assertIn("tool=codex repo=project", summary)

    def test_workspace_sources_cli_summary_surfaces_recent_source_identity_and_treeship_artifact(self):
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
                status="active",
            )
            row = store.conn.execute(
                "SELECT receipt_id, treeship_statement_json FROM memory_write_receipts WHERE memory_id = ?",
                (memory.id,),
            ).fetchone()
            treeship_statement = json.loads(row["treeship_statement_json"])
            treeship_statement["attestation"] = {
                "schema": "zerker.memory.treeship_attestation.v1",
                "status": "signed",
                "payload_digest": "sha256:abc123",
                "artifact_id": "ts_artifact_123",
                "signed_at": "2026-06-24T09:10:11Z",
            }
            store.conn.execute(
                "UPDATE memory_write_receipts SET treeship_statement_json = ? WHERE receipt_id = ?",
                (json.dumps(treeship_statement, sort_keys=True), row["receipt_id"]),
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
            self.assertIn("Recent sources:", summary)
            self.assertIn("tool=codex repo=project", summary)
            self.assertIn("workspace=ws_", summary)
            self.assertIn("latest_artifact=ts_artifact_123", summary)
            self.assertIn("latest_attestation=signed", summary)
            self.assertIn("artifact=ts_artifact_123", summary)
            self.assertIn("attestation=signed", summary)
            self.assertIn("session_scheme=chat source_scheme=conversation", summary)
            self.assertIn("conversation://codex/session-17/message-3", summary)


if __name__ == "__main__":
    unittest.main()
