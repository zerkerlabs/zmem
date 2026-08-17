import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import (
    create_handoff_package,
    main,
    preview_handoff_package,
    restore_handoff_package,
    restore_snapshot_file,
)
from zerker_memory.dashboard import (
    DashboardServer,
    INDEX_HTML,
    build_agent_continuity_state,
    build_benchmark_state,
    build_onboarding_state,
    build_release_readiness_state,
    build_room_inventory_state,
    build_workspace_sources_state,
    create_dashboard_handoff,
    create_dashboard_handoff_preview,
    create_dashboard_handoff_restore,
    create_dashboard_launch_assets_verify,
    create_dashboard_launch_proof,
    create_dashboard_release_pack,
    create_dashboard_return_packet_verify,
    re_memory_action,
    re_receipt_action,
)
from zerker_memory.rooms import RoomMemoryService, RoomStoreResolver
from zerker_memory.session_connections import consume_session_invitation, create_session_invitation
from zerker_memory.store import MemoryStore
from zerker_memory.workspaces import register_workspace


class DashboardTest(unittest.TestCase):
    def test_console_has_proof_inspector(self):
        self.assertIn("Proof Inspector", INDEX_HTML)
        self.assertIn("Memory In Use", INDEX_HTML)
        self.assertIn("Workspace Profile", INDEX_HTML)
        self.assertIn("Memory Provenance", INDEX_HTML)
        self.assertIn("Agent Memory Network", INDEX_HTML)
        self.assertIn("Shared Rooms", INDEX_HTML)
        self.assertIn("Context Transfer", INDEX_HTML)
        self.assertIn("Claim Conflicts", INDEX_HTML)
        self.assertIn("Memory Status", INDEX_HTML)
        self.assertIn("Memory Clusters", INDEX_HTML)
        self.assertIn("Benchmark Panel", INDEX_HTML)
        self.assertIn("Proven Zone", INDEX_HTML)
        self.assertIn("Asserted Zone", INDEX_HTML)
        self.assertIn("continuityAnchor.restore_receipt_id", INDEX_HTML)
        self.assertIn("continuityAnchor.continuity_sidecar_ok", INDEX_HTML)
        self.assertIn("function restoreLineageText(lineage)", INDEX_HTML)
        self.assertIn("basis ${restoreLineage.basis}", INDEX_HTML)
        self.assertIn("receipt at ${restoreLineage.source_receipt_created_at}", INDEX_HTML)
        self.assertIn("Treeship boundary framing", INDEX_HTML)
        self.assertIn("Agent MCP And Benchmarks", INDEX_HTML)
        self.assertIn("renderMemorySpotlight", INDEX_HTML)
        self.assertIn("renderMemoryStatusPanel", INDEX_HTML)
        self.assertIn("renderMemoryClusters", INDEX_HTML)
        self.assertIn("renderBenchmarkPanel", INDEX_HTML)
        self.assertIn("renderWorkspaceProfile", INDEX_HTML)
        self.assertIn("renderWorkspaceSources", INDEX_HTML)
        self.assertIn("renderBoundaryZones", INDEX_HTML)
        self.assertIn("renderAgentBenchmarkSpotlight", INDEX_HTML)
        self.assertIn("http://127.0.0.1:8766/benchmarks.html", INDEX_HTML)
        self.assertIn("What is the ZMem agent integration status for Codex and Claude Code?", INDEX_HTML)
        self.assertIn("renderBundleSummary", INDEX_HTML)
        self.assertIn("renderSnapshotSummary", INDEX_HTML)
        self.assertIn("renderLaunchProofSummary", INDEX_HTML)
        self.assertIn("renderHandoffSummary", INDEX_HTML)
        self.assertIn("rawOutput", INDEX_HTML)
        self.assertIn("Start with a governed-memory proof run", INDEX_HTML)
        self.assertIn("launch proof path", INDEX_HTML)
        self.assertIn("Load deploy demo", INDEX_HTML)
        self.assertIn("Run Release Pack", INDEX_HTML)
        self.assertIn("Generate Launch Proof", INDEX_HTML)
        self.assertIn("Generate Handoff", INDEX_HTML)
        self.assertIn("Preview Restore", INDEX_HTML)
        self.assertIn("Restore To New Copy", INDEX_HTML)
        self.assertIn("Verify Launch Assets", INDEX_HTML)
        self.assertIn("Verify Return Packet", INDEX_HTML)
        self.assertIn("renderReleasePackSummary", INDEX_HTML)
        self.assertIn("renderLaunchAssetsSummary", INDEX_HTML)
        self.assertIn("renderReturnPacketSummary", INDEX_HTML)
        self.assertIn("Operator packet", INDEX_HTML)
        self.assertIn("Public verify summary", INDEX_HTML)
        self.assertIn("Missing public-verify logs", INDEX_HTML)
        self.assertIn("Launch asset storyboard", INDEX_HTML)
        self.assertIn("public verify pending", INDEX_HTML)
        self.assertIn("launch assets pending", INDEX_HTML)
        self.assertIn("return packet pending", INDEX_HTML)
        self.assertIn("resolution basis", INDEX_HTML)
        self.assertIn("tool ${tool}", INDEX_HTML)
        self.assertIn("repo ${repo}", INDEX_HTML)
        self.assertIn("workspace ${workspace}", INDEX_HTML)
        self.assertIn("origin ${originSummary}", INDEX_HTML)
        self.assertIn("identity ${key} · via ${resolutionMethod}", INDEX_HTML)
        self.assertIn("cross session ${identityResolution.cross_session ? 'yes' : 'no'}", INDEX_HTML)
        self.assertIn("${prefix} ${actionId} · agent ${agent} · risk ${risk} · receipt ${receiptState} · task ${taskSummary}", INDEX_HTML)
        self.assertIn("source URIs ${sourceUriPreview}", INDEX_HTML)
        self.assertIn("session scheme ${sessionScheme}", INDEX_HTML)
        self.assertIn("source scheme ${sourceScheme}", INDEX_HTML)
        self.assertIn("attestation ${proofLineage.treeship_attestation_status || 'none'}", INDEX_HTML)
        self.assertIn("system ${proofLineage.treeship_system || 'none'}", INDEX_HTML)
        self.assertIn("subject ${proofLineage.treeship_subject_key || 'none'}", INDEX_HTML)
        self.assertIn("signed at ${proofLineage.treeship_signed_at}", INDEX_HTML)
        self.assertIn("payload digest ${shortHash(proofLineage.treeship_payload_digest)}", INDEX_HTML)
        self.assertIn("event hash ${shortHash(proofLineage.event_hash)}", INDEX_HTML)
        self.assertIn("receipt hash ${shortHash(proofLineage.receipt_hash)}", INDEX_HTML)
        self.assertIn("workspace continuity ${continuityAnchor.kind}", INDEX_HTML)
        self.assertIn("continuityAnchor.continuity_error", INDEX_HTML)
        self.assertIn("imported restore ${importedOrigin.restore_receipt_id}", INDEX_HTML)
        self.assertIn("const importedOrigin = importedOriginText(claim.imported_origin);", INDEX_HTML)
        self.assertIn("tie fields ${tieFields.join(', ') || 'none'}", INDEX_HTML)
        self.assertIn("ignored tie breakers ${ignoredTieBreakers.join(', ') || 'none'}", INDEX_HTML)
        self.assertIn("function resolutionTraceText(preview)", INDEX_HTML)
        self.assertIn("resolution trace ${step.summary || `${step.field || 'field'} ${step.outcome || 'preview'}`}", INDEX_HTML)
        self.assertIn("function decisiveClaimText(preview)", INDEX_HTML)
        self.assertIn("decision source ${decisiveClaim.summary || 'read-only merge preview'}", INDEX_HTML)
        self.assertIn("function losingClaimContrastText(preview)", INDEX_HTML)
        self.assertIn("decision contrast ${losingContrast.summary || 'read-only merge preview'}", INDEX_HTML)
        self.assertIn("function losingClaimParentActionText(preview)", INDEX_HTML)
        self.assertIn("losing action ${losingAction.summary || 'read-only merge preview'}", INDEX_HTML)
        self.assertIn("renderRoomInventory", INDEX_HTML)
        self.assertIn("renderHandoffPreviewSummary", INDEX_HTML)

    def test_agent_memory_network_distinguishes_configuration_from_observed_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            registry_path = root / "workspaces.json"
            register_workspace(name="Project", root=project, registry_path=registry_path)
            store = MemoryStore(project / ".zerker" / "memory.sqlite", policy_path=project / ".zerker" / "policy.json")
            store.remember(
                "Codex recorded the shared release decision",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                status="active",
                actor_uri="agent://codex/task-7",
                session_id="chat://codex/task-7",
                source_uri="conversation://codex/task-7/message-4",
            )
            store.remember(
                "A human-authored project note",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )
            config_paths = {
                preset: root / "configs" / f"{preset}.json"
                for preset in ("codex", "claude-code", "cursor", "openclaw", "hermes", "generic")
            }

            def inspect(preset, **_kwargs):
                configured = preset in {"codex", "claude-code"}
                return {
                    "ok": configured,
                    "state": "ready" if configured else "not_configured",
                    "details": "configured" if configured else "missing",
                    "configured_db_path": str(store.db_path) if configured else None,
                }

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}), patch(
                "zerker_memory.doctor.inspect_agent_connection",
                side_effect=inspect,
            ):
                state = build_agent_continuity_state(store, root=project, config_paths=config_paths)

        agents = {agent["agent_id"]: agent for agent in state["agents"]}
        self.assertEqual(state["schema"], "zerker.agent_memory_network.v1")
        self.assertEqual(state["configured_count"], 2)
        self.assertEqual(state["observed_count"], 1)
        self.assertEqual(state["active_count"], 1)
        self.assertTrue(state["shared_memory_ready"])
        self.assertEqual(agents["codex"]["connection_state"], "active")
        self.assertEqual(agents["codex"]["memory_count"], 1)
        self.assertTrue(agents["codex"]["shared_store_match"])
        self.assertEqual(agents["claude-code"]["connection_state"], "configured")
        self.assertFalse(agents["claude-code"]["observed"])
        self.assertNotIn("actor://human", agents)

    def test_agent_memory_network_reports_manual_exports_as_awaiting_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            config_paths = {
                preset: root / "configs" / f"{preset}.json"
                for preset in ("codex", "claude-code", "cursor", "openclaw", "hermes", "generic")
            }

            def inspect(preset, **_kwargs):
                exported = preset in {"cursor", "openclaw", "hermes", "generic"}
                return {
                    "ok": exported,
                    "state": "exported_awaiting_import" if exported else "not_configured",
                    "details": "exported awaiting import" if exported else "missing",
                    "configured_db_path": str(store.db_path) if exported else None,
                }

            with patch("zerker_memory.doctor.inspect_agent_connection", side_effect=inspect):
                state = build_agent_continuity_state(
                    store,
                    root=root,
                    config_paths=config_paths,
                    source_report={"connected_agents": []},
                )

        agents = {agent["agent_id"]: agent for agent in state["agents"]}
        self.assertEqual(state["configured_count"], 0)
        self.assertEqual(state["export_ready_count"], 4)
        self.assertEqual(agents["hermes"]["connection_state"], "export_ready")
        self.assertTrue(agents["hermes"]["export_ready"])
        self.assertFalse(agents["hermes"]["configured"])

    def test_agent_memory_network_separates_live_attachment_from_historical_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.init()
            invitation = create_session_invitation(
                store.conn,
                agent_id="claude-code",
                session_label="current release chat",
            )
            consume_session_invitation(
                store.conn,
                activation_code=invitation["activation_code"],
                agent_id="claude-code",
                connection_id="conn_live",
                client_session_id="chat_live",
            )
            config_paths = {
                preset: root / "configs" / f"{preset}.json"
                for preset in ("codex", "claude-code", "cursor", "openclaw", "hermes", "generic")
            }

            def inspect(preset, **_kwargs):
                configured = preset == "claude-code"
                return {
                    "ok": configured,
                    "state": "ready" if configured else "not_configured",
                    "details": "configured" if configured else "missing",
                    "configured_db_path": str(store.db_path) if configured else None,
                }

            with patch("zerker_memory.doctor.inspect_agent_connection", side_effect=inspect):
                state = build_agent_continuity_state(
                    store,
                    root=root,
                    config_paths=config_paths,
                    source_report={"connected_agents": []},
                )

        agents = {agent["agent_id"]: agent for agent in state["agents"]}
        claude = agents["claude-code"]
        self.assertEqual(state["live_agent_count"], 1)
        self.assertEqual(state["live_session_count"], 1)
        self.assertEqual(state["observed_count"], 0)
        self.assertEqual(claude["connection_state"], "live")
        self.assertTrue(claude["live"])
        self.assertFalse(claude["observed"])
        self.assertEqual(claude["session_attachments"][0]["client_session_id"], "chat_live")
        self.assertEqual(claude["session_attachments"][0]["identity_assurance"], "client_asserted")

    def test_room_inventory_separates_shared_and_private_memory_without_claiming_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            rooms_root = Path(tmp) / "rooms"
            resolver = RoomStoreResolver(rooms_root, tenant_id="tenant-a")
            service = RoomMemoryService(resolver)
            service.record_memory(
                {
                    "room_id": "rom_release",
                    "agent_id": "codex",
                    "content": "The release room uses the reviewed checklist",
                    "memory_type": "semantic",
                    "visibility": "room",
                    "source_event_id": "evt_shared",
                    "idempotency_key": "evt_shared:memory",
                }
            )
            service.propose_memory(
                {
                    "room_id": "rom_release",
                    "agent_id": "claude-code",
                    "content": "Private draft from Claude Code",
                    "memory_type": "episodic",
                    "visibility": "member",
                    "source_event_id": "evt_private",
                    "idempotency_key": "evt_private:memory",
                }
            )

            state = build_room_inventory_state(storage_root=rooms_root, tenant_id="tenant-a")

        self.assertEqual(state["schema"], "zerker.room_inventory.v1")
        self.assertEqual(state["room_count"], 1)
        self.assertEqual(state["shared_memory_count"], 1)
        self.assertEqual(state["member_private_memory_count"], 1)
        self.assertEqual(state["observed_contributor_ids"], ["claude-code", "codex"])
        self.assertEqual(state["membership_authority"], "gateway")
        self.assertEqual(state["rooms"][0]["status_counts"]["active"], 1)
        self.assertEqual(state["rooms"][0]["status_counts"]["quarantined"], 1)
        self.assertNotIn("Private draft from Claude Code", json.dumps(state))

    def test_room_inventory_keeps_healthy_rooms_visible_when_one_store_is_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            rooms_root = Path(tmp) / "rooms"
            resolver = RoomStoreResolver(rooms_root, tenant_id="tenant-a")
            with resolver.open("rom_broken"):
                pass
            resolver.db_path("rom_broken").write_text("not a sqlite database", encoding="utf-8")

            state = build_room_inventory_state(storage_root=rooms_root, tenant_id="tenant-a")

        self.assertEqual(state["room_count"], 1)
        self.assertEqual(state["unreadable_room_count"], 1)
        self.assertEqual(state["rooms"][0]["room_id"], "rom_broken")
        self.assertEqual(state["rooms"][0]["inventory_state"], "unreadable")
        self.assertNotIn("not a sqlite database", json.dumps(state))

    def test_build_workspace_sources_state_is_dashboard_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            registered = register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            first_action = store.inject(
                "capture first release-notes owner claim",
                agent_id="codex",
                risk="medium",
                scope="project",
            )
            second_action = store.inject(
                "capture second release-notes owner claim",
                agent_id="openclaw",
                risk="high",
                scope="project",
            )
            first = store.remember(
                "Release notes owner is Maya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-5",
                session_id="chat://codex/session-5",
                source_uri="conversation://codex/session-5/message-2",
                status="active",
                parent_action_id=first_action["action_id"],
            )
            second = store.remember(
                "Release notes owner is Iris",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://openclaw/chat-8",
                session_id="chat://openclaw/session-8",
                source_uri="conversation://openclaw/session-8/message-4",
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
                "SELECT receipt_id, event_hash, receipt_hash, treeship_statement_json FROM memory_write_receipts WHERE memory_id = ?",
                (second.id,),
            ).fetchone()
            treeship_statement = json.loads(row["treeship_statement_json"])
            treeship_statement["attestation"] = {
                "schema": "zerker.memory.treeship_attestation.v1",
                "status": "signed",
                "system": "system://zmem",
                "subject": "ts-dashboard-subject-123",
                "payload_digest": "sha256:abc123",
                "artifact_id": "ts_dashboard_123",
                "signed_at": "2026-06-25T01:10:11Z",
            }
            store.conn.execute(
                "UPDATE memory_write_receipts SET treeship_statement_json = ? WHERE receipt_id = ?",
                (json.dumps(treeship_statement, sort_keys=True), row["receipt_id"]),
            )
            store.conn.commit()
            handoff = create_handoff_package(
                store,
                providers_path=root / ".zerker" / "providers.json",
                out_dir=root / ".zerker" / "handoff",
                action_id=None,
            )
            snapshot_payload = json.loads(Path(handoff["snapshot_path"]).read_text(encoding="utf-8"))

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                state = build_workspace_sources_state(store)

        self.assertEqual(state["schema"], "zerker.workspace_sources.v1")
        self.assertEqual(state["workspace_id"], registered["workspace"]["id"])
        self.assertEqual(state["workspace_continuity"]["kind"], "local_handoff_manifest")
        self.assertEqual(state["workspace_continuity"]["action_id"], handoff["action_id"])
        self.assertEqual(state["workspace_continuity"]["snapshot_hash"], snapshot_payload["snapshot_hash"])
        self.assertEqual(state["workspace_continuity"]["snapshot_merkle_root"], snapshot_payload["merkle_root"])
        self.assertEqual(state["connected_agents"][0]["agent_id"], "codex")
        self.assertEqual(state["connected_agents"][0]["tool"], "codex")
        self.assertEqual(state["connected_agents"][0]["repo_name"], "project")
        self.assertEqual(
            state["connected_agents"][0]["identity_anchor"]["key"],
            f"{registered['workspace']['id']}::codex",
        )
        self.assertFalse(state["connected_agents"][0]["identity_resolution"]["cross_session"])
        self.assertEqual({source["source_uri"] for source in state["sources"]}, {
            "conversation://codex/session-5/message-2",
            "conversation://openclaw/session-8/message-4",
        })
        self.assertEqual({source["trust_status"] for source in state["sources"]}, {"active"})
        self.assertEqual({source["source_identity"]["repo_name"] for source in state["sources"]}, {"project"})
        self.assertEqual({source["source_identity"]["source_scheme"] for source in state["sources"]}, {"conversation"})
        self.assertEqual({source["source_identity"]["origin_kind"] for source in state["sources"]}, {"chat_message"})
        self.assertEqual(
            {source["source_identity"]["origin_summary"] for source in state["sources"]},
            {
                "chat_message:codex/session-5/message-2",
                "chat_message:openclaw/session-8/message-4",
            },
        )
        self.assertEqual(
            {source["identity_anchor"]["key"] for source in state["sources"]},
            {
                f"{registered['workspace']['id']}::codex",
                f"{registered['workspace']['id']}::openclaw",
            },
        )
        self.assertEqual(
            {source["identity_resolution"]["key"] for source in state["sources"]},
            {
                f"{registered['workspace']['id']}::codex",
                f"{registered['workspace']['id']}::openclaw",
            },
        )
        self.assertFalse(state["sources"][0]["identity_resolution"]["cross_session"])
        self.assertEqual(state["connected_agents"][0]["latest_origin_summary"], "chat_message:codex/session-5/message-2")
        self.assertEqual(state["connected_agents"][0]["latest_parent_action"]["action_id"], first_action["action_id"])
        self.assertEqual(
            state["connected_agents"][0]["source_uri_preview"],
            "conversation://codex/session-5/message-2",
        )
        self.assertEqual(state["connected_agents"][1]["latest_parent_action"]["action_id"], second_action["action_id"])
        self.assertEqual(state["connected_agents"][1]["latest_parent_action"]["risk"], "high")
        self.assertEqual(
            state["connected_agents"][1]["source_uri_preview"],
            "conversation://openclaw/session-8/message-4",
        )
        self.assertEqual(
            {source["parent_action"]["action_id"] for source in state["sources"]},
            {first_action["action_id"], second_action["action_id"]},
        )
        self.assertTrue(all("merkle_root" in source["proof_lineage"] for source in state["sources"]))
        self.assertIn("treeship_artifact_id", state["connected_agents"][1]["latest_proof_lineage"])
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["treeship_artifact_id"], "ts_dashboard_123")
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["treeship_attestation_status"], "signed")
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["treeship_system"], "system://zmem")
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["treeship_subject_key"], "ts-dashboard-subject-123")
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["treeship_subject_type"], "memory_write")
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["treeship_signed_at"], "2026-06-25T01:10:11Z")
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["treeship_payload_digest"], "sha256:abc123")
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["event_hash"], row["event_hash"])
        self.assertEqual(state["connected_agents"][1]["latest_proof_lineage"]["receipt_hash"], row["receipt_hash"])
        self.assertEqual(state["claim_conflict_count"], 1)
        self.assertEqual(state["claim_conflicts"][0]["merge_preview"]["chosen_memory_id"], second.id)
        self.assertEqual(state["claim_conflicts"][0]["merge_preview"]["chosen_value"], "iris")
        self.assertTrue(state["claim_conflicts"][0]["cross_session"])
        claims_by_id = {claim["memory_id"]: claim for claim in state["claim_conflicts"][0]["claims"]}
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["treeship_artifact_id"], "ts_dashboard_123")
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["treeship_attestation_status"], "signed")
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["treeship_system"], "system://zmem")
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["treeship_subject_key"], "ts-dashboard-subject-123")
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["treeship_subject_type"], "memory_write")
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["treeship_signed_at"], "2026-06-25T01:10:11Z")
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["treeship_payload_digest"], "sha256:abc123")
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["event_hash"], row["event_hash"])
        self.assertEqual(claims_by_id[second.id]["proof_lineage"]["receipt_hash"], row["receipt_hash"])
        self.assertEqual(claims_by_id[second.id]["source_identity"]["session_scheme"], "chat")
        self.assertEqual(claims_by_id[second.id]["source_identity"]["source_scheme"], "conversation")
        self.assertEqual(claims_by_id[first.id]["parent_action"]["action_id"], first_action["action_id"])
        self.assertEqual(claims_by_id[second.id]["parent_action"]["action_id"], second_action["action_id"])
        self.assertEqual(claims_by_id[second.id]["parent_action"]["task_summary"], "capture second release-notes owner claim")
        self.assertEqual(
            claims_by_id[second.id]["identity_anchor"]["key"],
            f"{registered['workspace']['id']}::openclaw",
        )
        self.assertEqual(
            claims_by_id[second.id]["identity_resolution"]["key"],
            f"{registered['workspace']['id']}::openclaw",
        )
        self.assertFalse(claims_by_id[second.id]["identity_resolution"]["cross_session"])
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["resolution_basis"]["summary"],
            "freshest updated_at",
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["decisive_claim_lineage"]["memory_id"],
            second.id,
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["decisive_claim_lineage"]["summary"],
            "freshest updated_at came from openclaw @ chat://openclaw/session-8",
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["losing_claim_contrast"]["summary"],
            "freshest updated_at kept openclaw @ chat://openclaw/session-8 (2024-02-01T00:00:00Z) over codex @ chat://codex/session-5 (2024-01-01T00:00:00Z)",
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["losing_claim_parent_action"]["memory_id"],
            first.id,
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["losing_claim_parent_action"]["parent_action"]["action_id"],
            first_action["action_id"],
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["losing_claim_parent_action"]["parent_action"]["risk"],
            "medium",
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["losing_claim_parent_action"]["parent_action"]["task_summary"],
            "capture first release-notes owner claim",
        )
        self.assertEqual(
            state["claim_conflicts"][0]["merge_preview"]["losing_claim_parent_action"]["summary"],
            f"losing claim came from {first_action['action_id']} by codex @ chat://codex/session-5",
        )
        self.assertEqual(
            [step["summary"] for step in state["claim_conflicts"][0]["merge_preview"]["resolution_trace"]],
            [
                "authority kept 2 claims tied at low",
                "trust kept 2 claims tied at 0.50",
                "updated_at selected 2024-02-01T00:00:00Z",
            ],
        )

    def test_build_workspace_sources_state_adds_bounded_connected_agent_source_uri_preview(self):
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
                actor_uri="agent://codex/chat-39",
                session_id="chat://codex/session-39",
                source_uri="conversation://codex/session-39/message-5",
            )
            store.remember(
                "Release runbook is in docs/release.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-17",
                session_id="chat://codex/session-17",
                source_uri="conversation://codex/session-17/message-3",
            )
            store.remember(
                "Release checklist is in docs/checklist.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-44",
                session_id="chat://codex/session-44",
                source_uri="conversation://codex/session-44/message-6",
            )
            store.remember(
                "Release note draft is in docs/notes.md",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-22",
                session_id="chat://codex/session-22",
                source_uri="conversation://codex/session-22/message-4",
            )

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                state = build_workspace_sources_state(store)

        self.assertEqual(state["connected_agent_count"], 1)
        self.assertEqual(
            state["connected_agents"][0]["source_uri_preview"],
            (
                "conversation://codex/session-17/message-3,"
                "conversation://codex/session-22/message-4,"
                "conversation://codex/session-39/message-5,+1 more"
            ),
        )

    def test_build_workspace_sources_state_surfaces_local_restore_continuity_anchor(self):
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

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                state = build_workspace_sources_state(restored_store)

        continuity = state["workspace_continuity"]
        self.assertEqual(continuity["kind"], "local_snapshot_restore")
        self.assertEqual(continuity["snapshot_hash"], snapshot_payload["snapshot_hash"])
        self.assertEqual(continuity["snapshot_merkle_root"], snapshot_payload["merkle_root"])
        self.assertEqual(continuity["snapshot_path"], str(snapshot_path.resolve()))
        self.assertTrue(continuity["continuity_sidecar_ok"])
        self.assertIn("snapshot.continuity.json", continuity["continuity_sidecar_path"])
        self.assertEqual(continuity["restore_actor_uri"], "actor://snapshot_restore")
        self.assertTrue(str(continuity["restore_receipt_id"]).startswith("lr_"))
        self.assertEqual(state["connected_agents"][0]["agent_id"], "codex")
        self.assertEqual(
            state["connected_agents"][0]["latest_imported_origin"]["restore_receipt_id"],
            continuity["restore_receipt_id"],
        )
        self.assertEqual(
            state["sources"][0]["imported_origin"]["restore_receipt_hash"],
            continuity["restore_receipt_hash"],
        )
        self.assertEqual(
            state["sources"][0]["imported_origin"]["snapshot_hash"],
            snapshot_payload["snapshot_hash"],
        )

    def test_build_workspace_sources_state_surfaces_imported_origin_on_claim_conflict_claims(self):
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

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                state = build_workspace_sources_state(restored_store)

        continuity = state["workspace_continuity"]
        self.assertEqual(state["claim_conflict_count"], 1)
        claims_by_id = {claim["memory_id"]: claim for claim in state["claim_conflicts"][0]["claims"]}
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
            snapshot_payload["snapshot_hash"],
        )
        self.assertTrue(claims_by_id[first.id]["imported_origin"]["continuity_sidecar_ok"])

    def test_build_workspace_sources_state_distinguishes_post_restore_local_claims_from_imported_claims(self):
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

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                state = build_workspace_sources_state(restored_store)

        sources_by_id = {source["memory_id"]: source for source in state["sources"]}
        claims_by_id = {claim["memory_id"]: claim for claim in state["claim_conflicts"][0]["claims"]}
        agents_by_id = {agent["agent_id"]: agent for agent in state["connected_agents"]}
        continuity = state["workspace_continuity"]

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

    def test_build_workspace_sources_state_surfaces_abstained_tie_details_for_dashboard(self):
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

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                state = build_workspace_sources_state(store)

        self.assertEqual(state["claim_conflict_count"], 1)
        preview = state["claim_conflicts"][0]["merge_preview"]
        self.assertEqual(preview["resolution_outcome"], "abstained")
        self.assertEqual(preview["chosen_memory_id"], None)
        self.assertEqual(preview["decisive_claim_lineage"], None)
        self.assertEqual(preview["losing_claim_parent_action"], None)
        self.assertEqual(preview["tie_fields"], ["authority", "trust", "updated_at", "created_at"])
        self.assertEqual(preview["ignored_tie_breakers"], ["retrieval_rank", "memory_id"])
        self.assertEqual(
            preview["resolution_basis"]["summary"],
            "exact tie on authority, trust, updated_at, created_at",
        )
        self.assertEqual(
            [step["summary"] for step in preview["resolution_trace"]],
            [
                "authority kept 2 claims tied at medium",
                "trust kept 2 claims tied at 0.95",
                "updated_at kept 2 claims tied at 2024-02-01T00:00:00Z",
                "created_at kept 2 claims tied at 2024-02-01T00:00:00Z",
            ],
        )

    def test_dashboard_server_is_threaded(self):
        self.assertIn("Threading", DashboardServer.__mro__[1].__name__)

    def test_dashboard_server_creates_request_local_stores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".zerker"
            store = MemoryStore(root / "memory.sqlite", policy_path=root / "policy.json")
            server = DashboardServer.__new__(DashboardServer)
            server.db_path = store.db_path
            server.policy_path = store.policy_path
            first = server.new_store()
            second = server.new_store()

        self.assertIsNot(first, second)
        self.assertEqual(first.db_path, store.db_path)
        self.assertEqual(second.db_path, store.db_path)
        self.assertEqual(first.policy_path, store.policy_path)
        self.assertEqual(second.policy_path, store.policy_path)

    def test_build_benchmark_state_reads_latest_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix_dir = root / ".zerker" / "bench" / "standard-synthetic-20260606-readiness"
            matrix_dir.mkdir(parents=True)
            (matrix_dir / "benchmark-dashboard.html").write_text("<html></html>", encoding="utf-8")
            (matrix_dir / "benchmark-matrix.json").write_text(
                """
                {
                  "benchmark": "synthetic",
                  "dataset": "synthetic",
                  "run_id": "standard-synthetic-20260606-readiness",
                  "matrix_hash": "matrix-hash",
                  "comparison_hash": "comparison-hash",
                  "proof": {"verification_status": "ok"},
                  "mode_runs": [
                    {
                      "run_id": "fts",
                      "retrieval_mode": "fts",
                      "summary": {"accuracy": 0.75, "passed": 3, "question_count": 4, "p95_retrieval_latency_ms": 3.64, "total_tokens": 53, "proof_verification_status": "ok"}
                    },
                    {
                      "run_id": "fts-multihop",
                      "retrieval_mode": "fts-multihop",
                      "summary": {"accuracy": 1.0, "passed": 4, "question_count": 4, "p95_retrieval_latency_ms": 5.23, "total_tokens": 56, "proof_verification_status": "ok"}
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            state = build_benchmark_state(root)

        self.assertTrue(state["ok"])
        self.assertEqual(state["claim_status"], "local synthetic proof")
        self.assertEqual(state["best_mode"], "fts-multihop")
        self.assertEqual(state["matrix_hash"], "matrix-hash")
        self.assertTrue(state["dashboard_ready"])
        self.assertEqual(state["modes"][1]["pass"], "4/4")

    def test_build_onboarding_state_shows_first_run_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".zerker"
            store = MemoryStore(root / "memory.sqlite", policy_path=root / "policy.json")
            state = build_onboarding_state(store)

        self.assertTrue(state["show"])
        self.assertIn("zmem status --summary-only", state["commands"])
        self.assertIn("zmem eval", state["commands"])
        self.assertIn("zmem ui", state["commands"])
        self.assertEqual(state["checks"][1]["label"], "Policy file present")

    def test_build_onboarding_state_hides_after_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".zerker"
            store = MemoryStore(root / "memory.sqlite", policy_path=root / "policy.json")
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            state = build_onboarding_state(store)

        self.assertFalse(state["show"])

    def test_parses_memory_action_paths(self):
        self.assertEqual(re_memory_action("/api/memories/mem_123/promote"), ("mem_123", "promote"))
        self.assertIsNone(re_memory_action("/api/memories/mem_123"))

    def test_parses_receipt_action_paths(self):
        self.assertEqual(re_receipt_action("/api/receipts/act_123/bundle"), ("act_123", "bundle"))
        self.assertIsNone(re_receipt_action("/api/receipts/act_123"))

    def test_receipt_bundle_api_exports_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            receipt = store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
            result = store.receipt_bundle(receipt["action_id"])

        self.assertEqual(result["bundle_schema"], "zerker.receipt_bundle.v2")
        self.assertTrue(result["proof"]["verified"])
        self.assertEqual(result["action_id"], receipt["action_id"])

    def test_build_release_readiness_state_reports_repo_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zerker_root = root / ".zerker"
            zerker_root.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(zerker_root / "memory.sqlite", policy_path=zerker_root / "policy.json")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                state = build_release_readiness_state(store)
            finally:
                os.chdir(cwd)

        self.assertIn("launch_proof_dir", state)
        self.assertIn("handoff_dir", state)
        self.assertIn("capture_checklist_path", state)
        self.assertIn("public_verify_script_path", state)
        self.assertIn("public_verify_result_path", state)
        self.assertIn("return_packet_finalize_script_path", state)
        self.assertIn("receive_verify_handoff_path", state)
        self.assertIn("launch_assets_outputs_dir_path", state)
        self.assertFalse(state["repo_surface_present"])

    def test_build_release_readiness_state_surfaces_public_verify_and_asset_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zerker_root = root / ".zerker"
            zerker_root.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(zerker_root / "memory.sqlite", policy_path=zerker_root / "policy.json")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            store.inject("deploy service to production after approval check", agent_id="codex", risk="high", scope="project")
            for relative_path in (
                "README.md",
                "install.sh",
                "scripts/release_smoke.py",
                "docs/PRODUCT_STATUS.md",
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder\n", encoding="utf-8")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                create_dashboard_release_pack(store)
                state = build_release_readiness_state(store)
            finally:
                os.chdir(cwd)

        self.assertTrue(state["repo_surface_present"])
        self.assertEqual(state["public_verify_expected_count"], 6)
        self.assertEqual(state["public_verify_present_count"], 0)
        self.assertEqual(state["launch_assets_expected_count"], 8)
        self.assertEqual(state["launch_assets_present_count"], 0)
        self.assertEqual(len(state["public_verify_missing_paths"]), 6)
        self.assertEqual(len(state["launch_assets_missing_paths"]), 8)
        self.assertEqual(len(state["expected_launch_assets"]), 8)
        self.assertEqual(state["expected_launch_assets"][-1]["id"], "ui-handoff-restore")
        self.assertEqual(state["operator_packet_missing_paths"], [])
        self.assertEqual(state["return_packet_missing_paths"], [])
        self.assertTrue(state["public_verify_script_path"].endswith("PUBLIC_VERIFY_COMMANDS.sh"))
        self.assertTrue(state["public_verify_result_path"].endswith("public-verify-result.json"))
        self.assertTrue(state["public_verify_summary_path"].endswith("public-verify-summary.md"))
        self.assertTrue(state["return_packet_finalize_script_path"].endswith("FINALIZE_RETURN_PACKET.sh"))
        self.assertTrue(state["return_packet_archive_path"].endswith("public-verify-return-packet.tar.gz"))
        self.assertTrue(state["launch_assets_outputs_dir_path"].endswith("assets"))

    def test_dashboard_release_helpers_create_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zerker_root = root / ".zerker"
            zerker_root.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(zerker_root / "memory.sqlite", policy_path=zerker_root / "policy.json")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            store.inject("deploy service to production after approval check", agent_id="codex", risk="high", scope="project")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                launch = create_dashboard_launch_proof(store)
                handoff = create_dashboard_handoff(store)
                preview = create_dashboard_handoff_preview(store)
                self.assertFalse(Path(preview["db_path"]).exists())
                restore = create_dashboard_handoff_restore(
                    store,
                    confirmed_preview_id=preview["preview_id"],
                )
                self.assertTrue(Path(launch["report_path"]).exists())
                self.assertTrue(Path(handoff["manifest_path"]).exists())
                self.assertTrue(Path(restore["db_path"]).exists())
            finally:
                os.chdir(cwd)

        self.assertTrue(launch["ok"])
        self.assertEqual(launch["schema"], "zerker.launch_proof.v1")
        self.assertTrue(handoff["ok"])
        self.assertEqual(handoff["schema"], "zerker.handoff.v1")
        self.assertTrue(preview["read_only_preview"])
        self.assertTrue(preview["ready_to_restore"])
        self.assertTrue(restore["ok"])
        self.assertEqual(restore["schema"], "zerker.restore_handoff.v1")
        self.assertEqual(restore["restore"]["memory_count"], 1)
        self.assertEqual(restore["restore"]["receipt_count"], 1)

    def test_dashboard_release_pack_creates_combined_release_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zerker_root = root / ".zerker"
            zerker_root.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(zerker_root / "memory.sqlite", policy_path=zerker_root / "policy.json")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            store.inject("deploy service to production after approval check", agent_id="codex", risk="high", scope="project")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = create_dashboard_release_pack(store)
            finally:
                os.chdir(cwd)
            self.assertEqual(result["schema"], "zerker.release_pack.v1")
            self.assertTrue(result["launch_proof"]["ok"])
            self.assertTrue(result["handoff"]["ok"])
            launch_report = Path(result["launch_proof"]["report_path"])
            handoff_manifest = Path(result["handoff"]["manifest_path"])
            if not launch_report.is_absolute():
                launch_report = root / launch_report
            if not handoff_manifest.is_absolute():
                handoff_manifest = root / handoff_manifest
            self.assertTrue(launch_report.exists())
            self.assertTrue(handoff_manifest.exists())
            self.assertEqual(result["prelaunch"]["schema"], "zerker.prelaunch.v1")

    def test_dashboard_handoff_restore_uses_fresh_import_db_each_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zerker_root = root / ".zerker"
            zerker_root.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(zerker_root / "memory.sqlite", policy_path=zerker_root / "policy.json")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            store.inject("deploy service to production after approval check", agent_id="codex", risk="high", scope="project")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                create_dashboard_handoff(store)
                first_preview = create_dashboard_handoff_preview(store)
                first = create_dashboard_handoff_restore(
                    store,
                    confirmed_preview_id=first_preview["preview_id"],
                )
                second_preview = create_dashboard_handoff_preview(store)
                second = create_dashboard_handoff_restore(
                    store,
                    confirmed_preview_id=second_preview["preview_id"],
                )
            finally:
                os.chdir(cwd)

        self.assertNotEqual(first["db_path"], second["db_path"])
        self.assertTrue(first["db_path"].endswith("imported.sqlite"))
        self.assertTrue(second["db_path"].endswith("imported-2.sqlite"))

    def test_handoff_restore_preview_is_read_only_and_binds_the_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = MemoryStore(root / "source.sqlite")
            source.remember(
                "The shared agent context is reviewed before transfer",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )
            handoff_dir = root / "handoff"
            create_handoff_package(
                source,
                providers_path=root / "providers.json",
                out_dir=handoff_dir,
                action_id=None,
            )
            target = MemoryStore(root / "target.sqlite")

            preview = preview_handoff_package(target, handoff_dir=handoff_dir)

            self.assertTrue(preview["ok"])
            self.assertTrue(preview["read_only_preview"])
            self.assertTrue(preview["ready_to_restore"])
            self.assertEqual(preview["effects"]["new_memory_count"], 1)
            self.assertEqual(preview["effects"]["conflict_count"], 0)
            self.assertFalse(preview["effects"]["deletes_memory"])
            self.assertEqual(target.stats()["memory_count"], 0)

            restored = restore_handoff_package(
                target,
                handoff_dir=handoff_dir,
                confirmed_preview_id=preview["preview_id"],
            )

            self.assertTrue(restored["ok"])
            self.assertEqual(restored["restore"]["memory_count"], 1)

    def test_handoff_restore_rejects_a_stale_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = MemoryStore(root / "source.sqlite")
            source.remember(
                "Transfer only the reviewed state",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )
            handoff_dir = root / "handoff"
            create_handoff_package(
                source,
                providers_path=root / "providers.json",
                out_dir=handoff_dir,
                action_id=None,
            )
            target = MemoryStore(root / "target.sqlite")
            preview = preview_handoff_package(target, handoff_dir=handoff_dir)
            target.remember(
                "A different write arrived after preview",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )

            with self.assertRaisesRegex(ValueError, "preview no longer matches"):
                restore_handoff_package(
                    target,
                    handoff_dir=handoff_dir,
                    confirmed_preview_id=preview["preview_id"],
                )

    def test_handoff_restore_rejects_manifest_changed_after_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = MemoryStore(root / "source.sqlite")
            source.remember(
                "Transfer only the exact reviewed handoff",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )
            handoff_dir = root / "handoff"
            create_handoff_package(
                source,
                providers_path=root / "providers.json",
                out_dir=handoff_dir,
                action_id=None,
            )
            target = MemoryStore(root / "target.sqlite")
            preview = preview_handoff_package(target, handoff_dir=handoff_dir)
            manifest_path = handoff_dir / "handoff.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status_summary"] = "changed after review"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "preview no longer matches"):
                restore_handoff_package(
                    target,
                    handoff_dir=handoff_dir,
                    confirmed_preview_id=preview["preview_id"],
                )

    def test_restore_cli_dry_run_prints_a_preview_without_importing_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = MemoryStore(root / "source.sqlite")
            source.remember(
                "Preview this state before another agent imports it",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )
            handoff_dir = root / "handoff"
            create_handoff_package(
                source,
                providers_path=root / "providers.json",
                out_dir=handoff_dir,
                action_id=None,
            )
            target_path = root / "target.sqlite"
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--db",
                        str(target_path),
                        "restore",
                        "--handoff-dir",
                        str(handoff_dir),
                        "--dry-run",
                        "--summary-only",
                    ]
                )

            target = MemoryStore(target_path)
            self.assertEqual(exit_code, 0)
            self.assertIn("Zerker Memory restore preview", output.getvalue())
            self.assertIn("Writes performed: no", output.getvalue())
            self.assertIn("Ready to restore: yes", output.getvalue())
            self.assertEqual(target.stats()["memory_count"], 0)

    def test_dashboard_return_packet_verify_uses_launch_proof_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zerker_root = root / ".zerker"
            zerker_root.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(zerker_root / "memory.sqlite", policy_path=zerker_root / "policy.json")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            store.inject("deploy service to production after approval check", agent_id="codex", risk="high", scope="project")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                create_dashboard_launch_proof(store)
                result = create_dashboard_return_packet_verify(store)
            finally:
                os.chdir(cwd)

        self.assertEqual(result["schema"], "zerker.return_packet_verify.v1")
        self.assertFalse(result["ok"])
        self.assertTrue(str(result["archive_path"]).endswith("public-verify-return-packet.tar.gz"))
        self.assertEqual(result["public_verify_expected_count"], 6)
        self.assertEqual(result["launch_assets_expected_count"], 6)

    def test_dashboard_launch_assets_verify_uses_launch_proof_assets_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zerker_root = root / ".zerker"
            zerker_root.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(zerker_root / "memory.sqlite", policy_path=zerker_root / "policy.json")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            store.inject("deploy service to production after approval check", agent_id="codex", risk="high", scope="project")

            cwd = Path.cwd()
            try:
                os.chdir(root)
                create_dashboard_launch_proof(store)
                result = create_dashboard_launch_assets_verify(store)
            finally:
                os.chdir(cwd)

        self.assertEqual(result["schema"], "zerker.launch_assets_verify.v1")
        self.assertFalse(result["ok"])
        self.assertTrue(str(result["outputs_dir_path"]).endswith("assets"))
        self.assertTrue(str(result["checklist_path"]).endswith("CAPTURE_CHECKLIST.md"))
        self.assertTrue(str(result["handoff_path"]).endswith("LAUNCH_ASSET_HANDOFF.md"))
        self.assertEqual(result["expected_count"], 6)
        self.assertEqual(len(result["expected_launch_assets"]), 6)
        self.assertEqual(result["expected_launch_assets"][-1]["id"], "ui-release-pack")


if __name__ == "__main__":
    unittest.main()
