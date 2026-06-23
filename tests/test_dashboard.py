import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zerker_memory.dashboard import (
    DashboardServer,
    INDEX_HTML,
    build_benchmark_state,
    build_onboarding_state,
    build_release_readiness_state,
    build_workspace_sources_state,
    create_dashboard_handoff,
    create_dashboard_handoff_restore,
    create_dashboard_launch_assets_verify,
    create_dashboard_launch_proof,
    create_dashboard_release_pack,
    create_dashboard_return_packet_verify,
    re_memory_action,
    re_receipt_action,
)
from zerker_memory.store import MemoryStore
from zerker_memory.workspaces import register_workspace


class DashboardTest(unittest.TestCase):
    def test_console_has_proof_inspector(self):
        self.assertIn("Proof Inspector", INDEX_HTML)
        self.assertIn("Memory In Use", INDEX_HTML)
        self.assertIn("Workspace Profile", INDEX_HTML)
        self.assertIn("Connected Agents And Sources", INDEX_HTML)
        self.assertIn("Memory Status", INDEX_HTML)
        self.assertIn("Memory Clusters", INDEX_HTML)
        self.assertIn("Benchmark Panel", INDEX_HTML)
        self.assertIn("Proven Zone", INDEX_HTML)
        self.assertIn("Asserted Zone", INDEX_HTML)
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
        self.assertIn("Restore Handoff", INDEX_HTML)
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

    def test_build_workspace_sources_state_is_dashboard_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "workspaces.json"
            root = tmp_path / "project"
            root.mkdir()
            registered = register_workspace(name="Project", root=root, registry_path=registry_path)
            store = MemoryStore(root / ".zerker" / "memory.sqlite")
            store.remember(
                "Release notes owner is Maya",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_uri="agent://codex/chat-5",
                session_id="chat://codex/session-5",
                source_uri="conversation://codex/session-5/message-2",
            )

            with patch.dict(os.environ, {"ZMEM_WORKSPACE_REGISTRY": str(registry_path)}):
                state = build_workspace_sources_state(store)

        self.assertEqual(state["schema"], "zerker.workspace_sources.v1")
        self.assertEqual(state["workspace_id"], registered["workspace"]["id"])
        self.assertEqual(state["connected_agents"][0]["agent_id"], "codex")
        self.assertEqual(state["sources"][0]["source_uri"], "conversation://codex/session-5/message-2")
        self.assertEqual(state["sources"][0]["trust_status"], "quarantined")
        self.assertIn("merkle_root", state["sources"][0]["proof_lineage"])

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

        self.assertEqual(result["bundle_schema"], "zerker.receipt_bundle.v1")
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
                restore = create_dashboard_handoff_restore(store)
                self.assertTrue(Path(launch["report_path"]).exists())
                self.assertTrue(Path(handoff["manifest_path"]).exists())
                self.assertTrue(Path(restore["db_path"]).exists())
            finally:
                os.chdir(cwd)

        self.assertTrue(launch["ok"])
        self.assertEqual(launch["schema"], "zerker.launch_proof.v1")
        self.assertTrue(handoff["ok"])
        self.assertEqual(handoff["schema"], "zerker.handoff.v1")
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
                first = create_dashboard_handoff_restore(store)
                second = create_dashboard_handoff_restore(store)
            finally:
                os.chdir(cwd)

        self.assertNotEqual(first["db_path"], second["db_path"])
        self.assertTrue(first["db_path"].endswith("imported.sqlite"))
        self.assertTrue(second["db_path"].endswith("imported-2.sqlite"))

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
