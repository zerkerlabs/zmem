import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import (
    PUBLIC_VERIFY_COMMAND_SEQUENCE,
    PUBLIC_VERIFY_LOG_FILENAMES,
    agent_checklist_path,
    agent_pack_path,
    agent_doctor_presets,
    agent_export_config_path,
    agent_manual_import_guide,
    agent_manual_install_command,
    agent_manual_verify_command,
    agent_presets,
    codex_mcp_server_block,
    build_agent_config_preset,
    build_agent_server_snippet,
    build_parser,
    build_session_end_result,
    build_session_ends_report,
    build_session_start_result,
    build_session_starts_report,
    build_session_checkpoint_result,
    build_session_lifecycle_rollup_report,
    build_session_retention_rollup_report,
    build_retrieval_provider_readiness_report,
    build_session_checkpoints_report,
    build_session_snapshot_soft_delete_result,
    build_session_snapshot_prune_result,
    build_session_snapshot_result,
    build_session_snapshots_report,
    build_session_timeline_report,
    build_status_report,
    build_status_next_steps,
    build_mcp_config,
    command_supports_runtime_reexec,
    create_agent_checklist,
    create_handoff_package,
    create_manual_agent_pack,
    extract_release_smoke_install_mode,
    install_mode_satisfies_requirement,
    install_agent_preset,
    install_codex_mcp_server,
    install_json_mcp_server,
    main,
    manual_agent_presets,
    maybe_reexec_with_supported_python,
    parse_agent_config_specs,
    policy_template,
    provider_live_overrides,
    provider_overrides,
    render_agent_guide,
    render_handoff_summary,
    render_inject_summary,
    render_agent_install_summary,
    render_launch_assets_summary,
    render_launch_proof_summary,
    render_manual_agent_pack_summary,
    render_memory_context_verification_summary,
    render_operator_packet_summary,
    render_session_end_summary,
    render_session_ends_summary,
    render_public_verify_summary,
    render_return_packet_summary,
    render_release_pack_summary,
    render_session_start_summary,
    render_session_starts_summary,
    render_session_checkpoint_summary,
    render_session_checkpoints_summary,
    render_session_lifecycle_rollup_summary,
    render_session_retention_rollup_summary,
    render_session_snapshot_soft_delete_summary,
    render_session_snapshot_prune_summary,
    render_session_snapshot_summary,
    render_session_snapshots_summary,
    render_session_timeline_summary,
    render_prelaunch_summary,
    render_retrieval_provider_readiness_summary,
    render_restore_summary,
    render_status_summary,
    render_why_summary,
    prelaunch_next_steps,
    public_verify_status,
    restore_snapshot_file,
    verify_public_verify,
    verify_operator_packet_archive,
    return_packet_status,
    verify_launch_assets,
    verify_return_packet_archive,
    run_agent_smoke,
    run_launch_proof,
    run_release_pack,
    run_prelaunch_check,
    restore_handoff_package,
    write_agent_prompt_template,
    write_json_file,
    write_policy_template,
    write_operator_packet_archive,
    write_public_verify_script,
    write_provider_config_template,
    write_return_packet_archive,
)
from zerker_memory.retrieval_providers import retrieval_provider_config_template
from zerker_memory.store import MemoryStore


class CliOnboardingTest(unittest.TestCase):
    def test_cli_expands_user_paths(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME": home}):
            args = build_parser().parse_args(
                [
                    "--db",
                    "~/memory.sqlite",
                    "snapshot",
                    "verify",
                    "~/snapshot.json",
                    "--out",
                    "~/verified.json",
                ]
            )

        self.assertEqual(args.db, Path(home) / "memory.sqlite")
        self.assertEqual(args.snapshot_path, Path(home) / "snapshot.json")
        self.assertEqual(args.out, Path(home) / "verified.json")

    def test_inject_and_why_accept_compact_summary_flags(self):
        inject = build_parser().parse_args(["inject", "continue release", "--agent", "codex", "--summary-only"])
        why = build_parser().parse_args(["why", "act_123", "--summary"])

        self.assertTrue(inject.summary_only)
        self.assertTrue(why.summary)

    def test_room_service_parser_uses_local_secure_defaults(self):
        args = build_parser().parse_args(["serve", "--tenant-id", "tenant-a"])

        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8766)
        self.assertEqual(args.tenant_id, "tenant-a")
        self.assertEqual(args.token_env, "ZMEM_SERVICE_TOKEN")
        self.assertFalse(args.allow_remote)
        self.assertEqual(args.retrieval_mode, "fts")

    def test_compact_memory_summaries_are_bounded_and_explain_governance(self):
        receipt = {
            "action_id": "act_123",
            "agent_id": "codex",
            "risk": "medium",
            "task": "continue the release",
            "retrieved_memory_ids": ["mem_1", "mem_2"],
            "injected_memory_ids": ["mem_1"],
            "memories": [
                {
                    "id": "mem_1",
                    "type": "semantic",
                    "status": "active",
                    "content": "The release branch is ready for verification.",
                }
            ],
            "injected": [
                {
                    "id": "mem_1",
                    "type": "semantic",
                    "status": "active",
                    "content": "The release branch is ready for verification.",
                }
            ],
            "withheld": [{"memory_id": "mem_2", "reason": "untrusted source"}],
            "merkle_root": "abc123",
            "memory_context": {"context_digest": "sha256:context123"},
        }

        inject_summary = render_inject_summary(receipt)
        why_summary = render_why_summary(receipt, verified=True)

        self.assertIn("Injected: 1 | Withheld: 1", inject_summary)
        self.assertIn("Explain: zmem why act_123 --summary-only", inject_summary)
        self.assertIn("Context proof: sha256:context123", inject_summary)
        self.assertIn("Memory that shaped the action", why_summary)
        self.assertIn("Memory kept out", why_summary)
        self.assertIn("Verification: ok", why_summary)
        self.assertIn("Context proof: sha256:context123", why_summary)
        self.assertLess(len(inject_summary), 1200)
        self.assertLess(len(why_summary), 1200)

    def test_context_verify_cli_reports_valid_and_tampered_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            context_path = Path(tmp) / "context.json"
            context = {
                "schema": "zerker.memory_context.v1",
                "action_id": "act_context",
                "agent_id": "codex",
                "memories": [],
            }
            from zerker_memory.runner import memory_context_digest

            context["context_digest"] = memory_context_digest(context)
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                return_code = main(["context", "verify", str(context_path), "--summary-only"])

            self.assertEqual(return_code, 0)
            self.assertIn("Verified: yes", output.getvalue())

            context["agent_id"] = "mallory"
            context_path.write_text(json.dumps(context), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                return_code = main(["context", "verify", str(context_path), "--summary-only"])

            self.assertEqual(return_code, 1)
            self.assertIn("Reason: context-digest-mismatch", output.getvalue())

    def test_context_verification_summary_is_compact(self):
        summary = render_memory_context_verification_summary(
            {
                "ok": True,
                "reason": "verified",
                "action_id": "act_context",
                "agent_id": "codex",
                "recorded_context_digest": "sha256:recorded",
                "computed_context_digest": "sha256:recorded",
                "path": "/tmp/context.json",
            }
        )

        self.assertIn("ZMem memory context verification", summary)
        self.assertIn("Verified: yes", summary)
        self.assertLess(len(summary), 600)

    def test_runtime_reexec_command_filter_is_scoped(self):
        self.assertTrue(command_supports_runtime_reexec("doctor"))
        self.assertTrue(command_supports_runtime_reexec("status"))
        self.assertFalse(command_supports_runtime_reexec("remember"))

    def test_write_operator_packet_archive_preserves_existing_archive_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            launch_dir = Path(tmpdir)
            for relative_path in (
                "launch-proof.json",
                "README.md",
                "index.html",
                "CAPTURE_CHECKLIST.md",
                "LAUNCH_ASSET_BOARD.html",
                "LAUNCH_ASSET_HANDOFF.md",
                "PUBLIC_VERIFY_HANDOFF.md",
                "RECEIVE_VERIFY_HANDOFF.md",
                "CLEAN_SHELL_PUBLIC_VERIFY.md",
                "CLEAN_SHELL_OPERATOR_PROMPT.md",
                "PUBLIC_VERIFY_CHECKLIST.md",
                "PUBLIC_VERIFY_COMMANDS.sh",
                "FINALIZE_RETURN_PACKET.sh",
                "public-verify-result.json",
                "public-verify-summary.md",
                "public-verify-return-packet.tar.gz",
            ):
                (launch_dir / relative_path).write_text(relative_path, encoding="utf-8")
            archive_path = launch_dir / "public-verify-operator-packet.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                marker_path = launch_dir / "marker.txt"
                marker_path.write_text("stable", encoding="utf-8")
                archive.add(marker_path, arcname="marker.txt")

            real_tarfile_open = tarfile.open

            def fake_tarfile_open(name, mode="r", *args, **kwargs):
                if mode == "w:gz":
                    Path(name).write_bytes(b"broken")
                    raise tarfile.TarError("simulated write failure")
                return real_tarfile_open(name, mode, *args, **kwargs)

            with patch("zerker_memory.cli.tarfile.open", side_effect=fake_tarfile_open):
                with self.assertRaises(tarfile.TarError):
                    write_operator_packet_archive(root=launch_dir, archive_path=archive_path)

            with tarfile.open(archive_path, "r:gz") as archive:
                self.assertIn("marker.txt", {member.name.rstrip("/") for member in archive.getmembers()})
            self.assertEqual(list(launch_dir.glob(".public-verify-operator-packet.tar.gz.*.tmp")), [])

    def test_write_return_packet_archive_preserves_existing_archive_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            launch_dir = Path(tmpdir)
            (launch_dir / "public-verify-logs").mkdir()
            (launch_dir / "assets").mkdir()
            for relative_path in (
                "launch-proof.json",
                "public-verify-logs/curl-install.log",
                "public-verify-result.json",
                "public-verify-summary.md",
                "assets/install-status.png",
            ):
                path = launch_dir / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative_path, encoding="utf-8")
            archive_path = launch_dir / "public-verify-return-packet.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                marker_path = launch_dir / "marker.txt"
                marker_path.write_text("stable", encoding="utf-8")
                archive.add(marker_path, arcname="marker.txt")

            real_tarfile_open = tarfile.open

            def fake_tarfile_open(name, mode="r", *args, **kwargs):
                if mode == "w:gz":
                    Path(name).write_bytes(b"broken")
                    raise tarfile.TarError("simulated write failure")
                return real_tarfile_open(name, mode, *args, **kwargs)

            with patch("zerker_memory.cli.tarfile.open", side_effect=fake_tarfile_open):
                with self.assertRaises(tarfile.TarError):
                    write_return_packet_archive(root=launch_dir, archive_path=archive_path)

            with tarfile.open(archive_path, "r:gz") as archive:
                self.assertIn("marker.txt", {member.name.rstrip("/") for member in archive.getmembers()})
            self.assertEqual(list(launch_dir.glob(".public-verify-return-packet.tar.gz.*.tmp")), [])

    def test_maybe_reexec_with_supported_python_reexecs_old_python_for_doctor(self):
        class OldPythonVersion:
            major = 3
            minor = 9
            micro = 6

            def __ge__(self, other):
                return (self.major, self.minor, self.micro) >= other

        with patch("zerker_memory.cli.sys.version_info", OldPythonVersion()), patch(
            "zerker_memory.doctor.find_supported_python",
            return_value="/opt/python3.10/bin/python3.10",
        ), patch(
            "zerker_memory.cli.subprocess.run",
            return_value=subprocess.CompletedProcess(["python"], 0),
        ) as run_mock, patch.dict(os.environ, {}, clear=False):
            result = maybe_reexec_with_supported_python("doctor", ["doctor", "--skip-eval"])

        self.assertEqual(result, 0)
        cmd = run_mock.call_args.args[0]
        env = run_mock.call_args.kwargs["env"]
        self.assertEqual(cmd, ["/opt/python3.10/bin/python3.10", "-m", "zerker_memory", "doctor", "--skip-eval"])
        self.assertEqual(env["ZERKER_MEMORY_RUNTIME_REEXEC"], "1")

    def test_maybe_reexec_with_supported_python_skips_when_guard_is_set(self):
        class OldPythonVersion:
            major = 3
            minor = 9
            micro = 6

            def __ge__(self, other):
                return (self.major, self.minor, self.micro) >= other

        with patch("zerker_memory.cli.sys.version_info", OldPythonVersion()), patch.dict(
            os.environ, {"ZERKER_MEMORY_RUNTIME_REEXEC": "1"}, clear=False
        ), patch("zerker_memory.cli.subprocess.run") as run_mock:
            result = maybe_reexec_with_supported_python("status", ["status", "--summary-only"])

        self.assertIsNone(result)
        run_mock.assert_not_called()

    def test_build_mcp_config_uses_zmem_command(self):
        config = build_mcp_config(
            name="zerker-memory",
            command="zmem",
            db_path=Path(".zerker/memory.sqlite"),
            policy_path=Path(".zerker/policy.json"),
        )

        server = config["mcpServers"]["zerker-memory"]
        self.assertEqual(server["command"], "zmem")
        self.assertEqual(
            server["args"],
            ["--db", ".zerker/memory.sqlite", "--policy", ".zerker/policy.json", "mcp", "--profile", "agent"],
        )

    def test_agent_presets_include_launch_targets(self):
        self.assertIn("codex", agent_presets())
        self.assertIn("claude-code", agent_presets())
        self.assertIn("cursor", agent_presets())
        self.assertIn("openclaw", agent_presets())
        self.assertIn("hermes", agent_presets())

    def test_manual_agent_presets_match_manual_targets(self):
        self.assertEqual(manual_agent_presets(), ("cursor", "openclaw", "hermes", "generic"))

    def test_agent_doctor_presets_include_supported_default_targets(self):
        self.assertEqual(agent_doctor_presets(), agent_presets())

    def test_build_parser_parses_session_snapshot_summary_only(self):
        args = build_parser().parse_args(
            ["session", "snapshots", "--session-id", "session://alpha", "--scope", "project:alpha", "--summary-only"]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "snapshots")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.scope, "project:alpha")
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_retention_summary_only(self):
        args = build_parser().parse_args(
            ["session", "retention", "--scope", "project:alpha", "--limit", "2", "--summary-only"]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "retention")
        self.assertEqual(args.scope, "project:alpha")
        self.assertEqual(args.limit, 2)
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_timeline_summary_only(self):
        args = build_parser().parse_args(
            ["session", "timeline", "--session-id", "session://alpha", "--scope", "project:alpha", "--summary-only"]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "timeline")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.scope, "project:alpha")
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_rollup_summary_only(self):
        args = build_parser().parse_args(
            ["session", "rollup", "--scope", "project:alpha", "--limit", "2", "--summary-only"]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "rollup")
        self.assertEqual(args.scope, "project:alpha")
        self.assertEqual(args.limit, 2)
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_prune_snapshots_summary_only(self):
        args = build_parser().parse_args(
            [
                "session",
                "prune-snapshots",
                "--session-id",
                "session://alpha",
                "--actor-id",
                "reviewer",
                "--scope",
                "project:alpha",
                "--keep-latest",
                "2",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "prune-snapshots")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.actor_id, "reviewer")
        self.assertEqual(args.scope, "project:alpha")
        self.assertEqual(args.keep_latest, 2)
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_start_summary_only(self):
        args = build_parser().parse_args(
            [
                "session",
                "start",
                "--session-id",
                "session://alpha",
                "--actor-id",
                "codex",
                "--scope",
                "project:alpha",
                "--context-budget-tokens",
                "256",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "start")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.actor_id, "codex")
        self.assertEqual(args.scope, "project:alpha")
        self.assertEqual(args.context_budget_tokens, 256)
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_starts_summary_only(self):
        args = build_parser().parse_args(
            ["session", "starts", "--session-id", "session://alpha", "--scope", "project:alpha", "--summary-only"]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "starts")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.scope, "project:alpha")
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_checkpoint_write_summary_only(self):
        args = build_parser().parse_args(
            [
                "session",
                "checkpoint",
                "--session-id",
                "session://alpha",
                "--actor-id",
                "codex",
                "--scope",
                "project:alpha",
                "--summary",
                "handoff before context compaction",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "checkpoint")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.actor_id, "codex")
        self.assertEqual(args.scope, "project:alpha")
        self.assertEqual(args.summary, "handoff before context compaction")
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_snapshot_write_summary_only(self):
        args = build_parser().parse_args(
            [
                "session",
                "snapshot",
                "--session-id",
                "session://alpha",
                "--actor-id",
                "codex",
                "--scope",
                "project:alpha",
                "--summary",
                "freeze before context compaction",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "snapshot")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.actor_id, "codex")
        self.assertEqual(args.scope, "project:alpha")
        self.assertEqual(args.summary, "freeze before context compaction")
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_delete_snapshot_summary_only(self):
        args = build_parser().parse_args(
            [
                "session",
                "delete-snapshot",
                "--session-snapshot-id",
                "ssn_abc123",
                "--actor-id",
                "reviewer",
                "--reason",
                "retention window expired",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "delete-snapshot")
        self.assertEqual(args.session_snapshot_id, "ssn_abc123")
        self.assertEqual(args.actor_id, "reviewer")
        self.assertEqual(args.reason, "retention window expired")
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_bundle_verify_summary_only(self):
        args = build_parser().parse_args(
            [
                "bundle",
                "verify",
                "/tmp/receipt.bundle.json",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "bundle")
        self.assertEqual(args.bundle_target, "verify")
        self.assertEqual(str(args.bundle_path), "/tmp/receipt.bundle.json")
        self.assertTrue(args.summary_only)

    def test_lineage_parser_accepts_summary_only(self):
        args = build_parser().parse_args(["lineage", "mem_123", "--summary-only"])

        self.assertEqual(args.command, "lineage")
        self.assertEqual(args.memory_id, "mem_123")
        self.assertTrue(args.summary_only)

    def test_agent_export_config_path_uses_project_local_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                agent_export_config_path("openclaw", cwd=root),
                root / ".zerker" / "agents" / "openclaw-mcp.json",
            )
            self.assertEqual(
                agent_export_config_path("cursor", cwd=root),
                root / ".zerker" / "agents" / "cursor-mcp.json",
            )
            self.assertIsNone(agent_export_config_path("codex", cwd=root))

    def test_agent_checklist_path_uses_project_local_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                agent_checklist_path("openclaw", cwd=root),
                root / ".zerker" / "agents" / "openclaw-checklist.md",
            )
            self.assertEqual(
                agent_checklist_path("cursor", cwd=root),
                root / ".zerker" / "agents" / "cursor-checklist.md",
            )
            self.assertIsNone(agent_checklist_path("codex", cwd=root))

    def test_session_checkpoints_summary_surfaces_checkpoint_root_and_memory_type_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Use the release checklist before tagging",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )
            checkpoint = store.checkpoint_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="handoff before context compaction",
            )

            report = build_session_checkpoints_report(
                store,
                session_id="session://alpha",
                scope="project:alpha",
                limit=10,
            )
            summary = render_session_checkpoints_summary(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["checkpoints"][0]["checkpoint_id"], checkpoint["checkpoint_id"])
        self.assertEqual(report["verified_receipt_count"], 1)
        self.assertEqual(report["failed_receipt_count"], 0)
        self.assertEqual(report["linked_treeship_artifact_count"], 0)
        self.assertTrue(report["checkpoints"][0]["receipt_verification"]["ok"])
        self.assertEqual(
            report["checkpoints"][0]["receipt_summary"]["source_event_hash"],
            checkpoint["receipt"]["source_event_hash"],
        )
        self.assertIn("Session checkpoints", summary)
        self.assertIn("Session filter: session://alpha", summary)
        self.assertIn("Receipt provenance: 1 verified, 0 failed", summary)
        self.assertIn("Linked Treeship artifacts: 0", summary)
        self.assertIn(f"Latest checkpoint root: {checkpoint['checkpoint_merkle_root']}", summary)
        self.assertIn("trusted_provenance=verified", summary)
        self.assertIn(f"content_digest={checkpoint['receipt']['content_digest']}", summary)
        self.assertIn(f"source event: hash={checkpoint['receipt']['source_event_hash']}", summary)
        self.assertIn("semantic truth: not guaranteed", summary)
        self.assertIn("policy=1 procedural=1 episodic=0 semantic=1", summary)
        self.assertIn("handoff before context compaction", summary)

    def test_session_checkpoint_summary_surfaces_written_checkpoint_root_and_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Use the release checklist before tagging",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )

            result = build_session_checkpoint_result(
                store,
                session_id="session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="handoff before context compaction",
            )
            summary = render_session_checkpoint_summary(result)

        checkpoint = result["checkpoint"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.session_checkpoint_result.v1")
        self.assertEqual(checkpoint["session_id"], "session://alpha")
        self.assertIn("Session checkpoint created", summary)
        self.assertIn(f"Checkpoint id: {checkpoint['checkpoint_id']}", summary)
        self.assertIn(f"Checkpoint root: {checkpoint['checkpoint_merkle_root']}", summary)
        self.assertIn("policy=1 procedural=1 episodic=0 semantic=1", summary)
        self.assertIn("handoff before context compaction", summary)

    def test_build_parser_parses_session_end_summary_only(self):
        args = build_parser().parse_args(
            ["session", "end", "--session-id", "session://alpha", "--actor-id", "codex", "--scope", "project:alpha", "--summary-only"]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "end")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.actor_id, "codex")
        self.assertEqual(args.scope, "project:alpha")
        self.assertTrue(args.summary_only)

    def test_build_parser_parses_session_ends_summary_only(self):
        args = build_parser().parse_args(
            ["session", "ends", "--session-id", "session://alpha", "--scope", "project:alpha", "--summary-only"]
        )

        self.assertEqual(args.command, "session")
        self.assertEqual(args.session_command, "ends")
        self.assertEqual(args.session_id, "session://alpha")
        self.assertEqual(args.scope, "project:alpha")
        self.assertTrue(args.summary_only)

    def test_session_end_summary_surfaces_written_end_root_and_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Use the release checklist before tagging",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )

            result = build_session_end_result(
                store,
                session_id="session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="context budget exhausted after deploy handoff",
            )
            summary = render_session_end_summary(result)

        session_end = result["session_end"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.session_end_result.v1")
        self.assertEqual(session_end["session_id"], "session://alpha")
        self.assertIn("Session ended", summary)
        self.assertIn(f"Session end id: {session_end['session_end_id']}", summary)
        self.assertIn(f"Session end root: {session_end['session_end_merkle_root']}", summary)
        self.assertIn("policy=1 procedural=1 episodic=0 semantic=1", summary)
        self.assertIn("context budget exhausted after deploy handoff", summary)

    def test_session_ends_summary_surfaces_latest_end_root_and_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Use the release checklist before tagging",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="first closeout",
            )
            latest = store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="second closeout",
            )

            report = build_session_ends_report(
                store,
                session_id="session://alpha",
                scope="project:alpha",
                limit=10,
            )
            summary = render_session_ends_summary(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 2)
        self.assertEqual(report["verified_receipt_count"], 2)
        self.assertEqual(report["failed_receipt_count"], 0)
        self.assertEqual(report["linked_treeship_artifact_count"], 0)
        self.assertTrue(report["ends"][0]["receipt_verification"]["ok"])
        self.assertIn("Session ends", summary)
        self.assertIn("Session filter: session://alpha", summary)
        self.assertIn("Receipt provenance: 2 verified, 0 failed", summary)
        self.assertIn("Linked Treeship artifacts: 0", summary)
        self.assertIn(f"Latest session end root: {latest['session_end_merkle_root']}", summary)
        self.assertIn("trusted_provenance=verified", summary)
        self.assertIn(f"content_digest={latest['receipt']['content_digest']}", summary)
        self.assertIn(f"source event: hash={latest['receipt']['source_event_hash']}", summary)
        self.assertIn("semantic truth: not guaranteed", summary)
        self.assertIn("policy=1 procedural=1 episodic=0 semantic=0", summary)
        self.assertIn("second closeout", summary)
        self.assertIn("first closeout", summary)

    def test_session_start_summary_surfaces_written_start_root_and_budget_hint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Use the release checklist before tagging",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )

            result = build_session_start_result(
                store,
                session_id="session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="resume deploy swarm",
                context_budget_tokens=256,
            )
            summary = render_session_start_summary(result)

        session_start = result["session_start"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.session_start_result.v1")
        self.assertEqual(session_start["session_id"], "session://alpha")
        self.assertEqual(session_start["token_budget_hint"], {"context_budget_tokens": 256})
        self.assertIn("Session started", summary)
        self.assertIn(f"Session start id: {session_start['session_start_id']}", summary)
        self.assertIn(f"Session start root: {session_start['session_start_merkle_root']}", summary)
        self.assertIn("Context budget hint: 256", summary)
        self.assertIn("policy=1 procedural=1 episodic=0 semantic=1", summary)
        self.assertIn("resume deploy swarm", summary)

    def test_session_starts_summary_surfaces_latest_start_root_and_budget_hints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="initial resume",
                context_budget_tokens=256,
            )
            latest = store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="resume after checkpoint restore",
                context_budget_tokens=128,
            )

            report = build_session_starts_report(
                store,
                session_id="session://alpha",
                scope="project:alpha",
                limit=10,
            )
            summary = render_session_starts_summary(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 2)
        self.assertEqual(report["verified_receipt_count"], 2)
        self.assertEqual(report["failed_receipt_count"], 0)
        self.assertEqual(report["linked_treeship_artifact_count"], 0)
        self.assertTrue(report["starts"][0]["receipt_verification"]["ok"])
        self.assertIn("Session starts", summary)
        self.assertIn("Session filter: session://alpha", summary)
        self.assertIn("Budget hints: 2 set, 0 unset", summary)
        self.assertIn("Receipt provenance: 2 verified, 0 failed", summary)
        self.assertIn("Linked Treeship artifacts: 0", summary)
        self.assertIn(f"Latest session start root: {latest['session_start_merkle_root']}", summary)
        self.assertIn("trusted_provenance=verified", summary)
        self.assertIn(f"content_digest={latest['receipt']['content_digest']}", summary)
        self.assertIn(f"source event: hash={latest['receipt']['source_event_hash']}", summary)
        self.assertIn("semantic truth: not guaranteed", summary)
        self.assertIn("context_budget_tokens=128", summary)
        self.assertIn("context_budget_tokens=256", summary)
        self.assertIn("resume after checkpoint restore", summary)
        self.assertIn("initial resume", summary)

    def test_session_snapshot_summary_surfaces_written_snapshot_root_and_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Use the release checklist before tagging",
                memory_type="procedural",
                scope="project:alpha",
                source_kind="human",
            )
            store.remember(
                "Deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )

            result = build_session_snapshot_result(
                store,
                session_id="session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="freeze before context compaction",
            )
            summary = render_session_snapshot_summary(result)

        session_snapshot = result["session_snapshot"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.session_snapshot_result.v1")
        self.assertEqual(session_snapshot["session_id"], "session://alpha")
        self.assertEqual(session_snapshot["payload_status"], "available")
        self.assertIn("Session snapshot created", summary)
        self.assertIn(f"Session snapshot id: {session_snapshot['session_snapshot_id']}", summary)
        self.assertIn(f"Session snapshot root: {session_snapshot['session_snapshot_merkle_root']}", summary)
        self.assertIn(f"Snapshot hash: {session_snapshot['snapshot_hash']}", summary)
        self.assertIn("policy=1 procedural=1 episodic=0 semantic=1", summary)
        self.assertIn("freeze before context compaction", summary)

    def test_session_snapshots_summary_surfaces_soft_deleted_retention_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )
            available = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="available snapshot",
            )
            deleted = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="soft deleted snapshot",
            )
            store.soft_delete_session_snapshot_payload(
                deleted["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention window expired",
            )

            report = build_session_snapshots_report(
                store,
                session_id="session://alpha",
                scope="project:alpha",
                limit=10,
            )
            summary = render_session_snapshots_summary(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 2)
        self.assertEqual(report["verified_receipt_count"], 2)
        self.assertEqual(report["failed_receipt_count"], 0)
        self.assertEqual(report["linked_treeship_artifact_count"], 0)
        self.assertTrue(report["snapshots"][0]["receipt_verification"]["ok"])
        self.assertIn("Session snapshots", summary)
        self.assertIn("Receipt provenance: 2 verified, 0 failed", summary)
        self.assertIn("Linked Treeship artifacts: 0", summary)
        self.assertIn("Payloads: 1 available, 1 soft-deleted", summary)
        self.assertIn(f"Latest session snapshot root: {deleted['session_snapshot_merkle_root']}", summary)
        self.assertIn("trusted_provenance=verified", summary)
        self.assertIn(f"content_digest={deleted['receipt']['content_digest']}", summary)
        self.assertIn(f"source event: hash={deleted['receipt']['source_event_hash']}", summary)
        self.assertIn("semantic truth: not guaranteed", summary)
        self.assertIn("payload=soft_deleted", summary)
        self.assertIn("deleted_by=reviewer", summary)
        self.assertIn("deleted_reason=retention window expired", summary)
        self.assertIn("payload=available", summary)

    def test_session_retention_rollup_summary_surfaces_mixed_available_and_soft_deleted_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )
            alpha_available = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="alpha retained",
            )
            alpha_deleted = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="alpha latest soft-deleted",
            )
            store.soft_delete_session_snapshot_payload(
                alpha_deleted["session_snapshot_id"],
                actor_id="reviewer",
                reason="keep only stable checkpoint",
            )
            beta_available = store.snapshot_session(
                "session://beta",
                actor_id="hermes",
                scope="project:beta",
                summary="beta retained",
            )
            gamma_deleted = store.snapshot_session(
                "session://gamma",
                actor_id="opencode",
                scope="project:gamma",
                summary="gamma deleted",
            )
            store.soft_delete_session_snapshot_payload(
                gamma_deleted["session_snapshot_id"],
                actor_id="reviewer",
                reason="expired retention window",
            )

            report = build_session_retention_rollup_report(store, limit=10)
            summary = render_session_retention_rollup_summary(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 3)
        self.assertEqual(
            report["retention_state_counts"],
            {"all_available": 1, "mixed": 1, "soft_deleted_only": 1},
        )
        self.assertEqual(report["payload_status_counts"], {"available": 2, "soft_deleted": 2})
        self.assertIn("Session snapshot retention", summary)
        self.assertIn("Retention states: all_available=1 mixed=1 soft_deleted_only=1", summary)
        self.assertIn("Snapshot payloads: 2 available, 2 soft-deleted", summary)
        self.assertIn("session://alpha: scope=project:alpha latest=soft_deleted state=mixed", summary)
        self.assertIn(f"latest available: id={alpha_available['session_snapshot_id']}", summary)
        self.assertIn("deleted_reason=keep only stable checkpoint", summary)
        self.assertIn("session://beta: scope=project:beta latest=available state=all_available", summary)
        self.assertIn(f"latest_snapshot={beta_available['session_snapshot_id']}", summary)
        self.assertIn("latest soft-deleted: id=none", summary)
        self.assertIn("session://gamma: scope=project:gamma latest=soft_deleted state=soft_deleted_only", summary)
        self.assertIn("deleted_reason=expired retention window", summary)

    def test_session_snapshot_soft_delete_summary_surfaces_retention_roots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="freeze before context compaction",
            )

            result = build_session_snapshot_soft_delete_result(
                store,
                session_snapshot_id=session_snapshot["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention window expired",
            )
            summary = render_session_snapshot_soft_delete_summary(result)

        deleted = result["session_snapshot"]
        retention = deleted["retention"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.session_snapshot_soft_delete_result.v1")
        self.assertEqual(deleted["payload_status"], "soft_deleted")
        self.assertIn("Session snapshot payload soft-deleted", summary)
        self.assertIn(f"Session snapshot id: {deleted['session_snapshot_id']}", summary)
        self.assertIn("Deleted by: reviewer", summary)
        self.assertIn("Reason: retention window expired", summary)
        self.assertIn(f"Snapshot hash: {deleted['snapshot_hash']}", summary)
        self.assertIn(f"Soft-delete root: {retention['soft_delete_merkle_root']}", summary)
        self.assertIn('"payload_status": "soft_deleted"', json.dumps(deleted, sort_keys=True))

    def test_session_snapshot_prune_summary_surfaces_kept_and_pruned_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploy target is Render",
                memory_type="semantic",
                scope="project:alpha",
                source_kind="human",
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="first freeze",
            )
            pruned_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="second freeze",
            )
            kept_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="third freeze",
            )

            result = build_session_snapshot_prune_result(
                store,
                session_id="session://alpha",
                actor_id="reviewer",
                scope="project:alpha",
                keep_latest=1,
                reason="keep latest only",
            )
            summary = render_session_snapshot_prune_summary(result)

        prune = result["prune"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.session_snapshot_prune_result.v1")
        self.assertEqual(prune["keep_latest"], 1)
        self.assertIn("Session snapshot retention prune", summary)
        self.assertIn("Session id: session://alpha", summary)
        self.assertIn("Keep latest: 1", summary)
        self.assertIn("Available before: 3", summary)
        self.assertIn("Pruned: 2", summary)
        self.assertIn(f"Kept snapshot ids: {kept_snapshot['session_snapshot_id']}", summary)
        self.assertIn(pruned_snapshot["session_snapshot_id"], summary)
        self.assertIn("Reason: keep latest only", summary)

    def test_session_timeline_summary_surfaces_mixed_lifecycle_entries_and_retention_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            start = store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="resume deploy swarm",
                context_budget_tokens=256,
            )
            store.checkpoint_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="checkpoint before compaction",
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="freeze before retention prune",
            )
            store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="closeout after handoff",
            )
            store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention window expired",
            )

            report = build_session_timeline_report(
                store,
                session_id="session://alpha",
                scope="project:alpha",
                limit=10,
            )
            summary = render_session_timeline_summary(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 5)
        self.assertIn("Session timeline", summary)
        self.assertIn("Session filter: session://alpha", summary)
        self.assertIn("Event kinds: starts=1 checkpoints=1 snapshots=1 snapshot_soft_deletes=1 ends=1", summary)
        self.assertIn("Receipt provenance: 5 verified, 0 failed", summary)
        self.assertEqual(report["verified_receipt_count"], 5)
        self.assertEqual(report["failed_receipt_count"], 0)
        self.assertEqual(report["linked_treeship_artifact_count"], 0)
        self.assertIn("Snapshot payloads: 0 available, 1 soft-deleted", summary)
        self.assertIn(f"Latest timeline root: {report['timeline'][0]['timeline_root']}", summary)
        self.assertIn(f"start:{start['session_start_id']}", summary)
        self.assertIn("context_budget_tokens=256", summary)
        self.assertIn("receipt: trusted_provenance=verified", summary)
        self.assertIn("source event: hash=", summary)
        self.assertIn("semantic truth: not guaranteed", summary)
        self.assertIn(f"snapshot_soft_delete:{session_snapshot['session_snapshot_id']}", summary)
        self.assertIn("deleted_by=reviewer", summary)
        self.assertIn("deleted_reason=retention window expired", summary)

    def test_session_lifecycle_rollup_summary_groups_sessions_and_latest_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(Path(tmpdir) / "memory.sqlite")
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="resume deploy swarm",
                context_budget_tokens=256,
            )
            store.checkpoint_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="checkpoint before compaction",
            )
            alpha_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="freeze before retention prune",
            )
            store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="closeout after handoff",
            )
            store.soft_delete_session_snapshot_payload(
                alpha_snapshot["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention window expired",
            )
            beta_start = store.start_session(
                "session://beta",
                actor_id="hermes",
                scope="project:beta",
                summary="beta resume",
                context_budget_tokens=128,
            )
            beta_snapshot = store.snapshot_session(
                "session://beta",
                actor_id="hermes",
                scope="project:beta",
                summary="beta retained",
            )
            gamma_start = store.start_session(
                "session://gamma",
                actor_id="opencode",
                scope="project:gamma",
                summary="gamma active",
            )

            report = build_session_lifecycle_rollup_report(store, limit=10)
            summary = render_session_lifecycle_rollup_summary(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["count"], 3)
        self.assertEqual(
            report["event_kind_counts"],
            {"start": 3, "checkpoint": 1, "snapshot": 2, "snapshot_soft_delete": 1, "end": 1},
        )
        self.assertEqual(report["payload_status_counts"], {"available": 1, "soft_deleted": 1})
        self.assertEqual(report["verified_receipt_count"], 8)
        self.assertEqual(report["failed_receipt_count"], 0)
        self.assertEqual(report["linked_treeship_artifact_count"], 0)
        self.assertEqual(report["sessions"][0]["verified_receipt_count"], 1)
        self.assertEqual(report["sessions"][1]["verified_receipt_count"], 2)
        self.assertEqual(report["sessions"][2]["verified_receipt_count"], 5)
        self.assertIn("Session lifecycle rollup", summary)
        self.assertIn("Lifecycle events: starts=3 checkpoints=1 snapshots=2 snapshot_soft_deletes=1 ends=1", summary)
        self.assertIn("Snapshot payloads: 1 available, 1 soft-deleted", summary)
        self.assertIn("Receipt provenance: 8 verified, 0 failed", summary)
        self.assertIn("Linked Treeship artifacts: 0", summary)
        self.assertIn("session://gamma: scope=project:gamma latest=start", summary)
        self.assertIn("receipts=1 verified, 0 failed linked_artifacts=0 latest_receipt=verified", summary)
        self.assertIn(f"latest_start={gamma_start['session_start_id']}", summary)
        self.assertIn("session://beta: scope=project:beta latest=snapshot", summary)
        self.assertIn(f"latest_start={beta_start['session_start_id']}", summary)
        self.assertIn("context_budget_tokens=128", summary)
        self.assertIn(f"latest_snapshot={beta_snapshot['session_snapshot_id']}", summary)
        self.assertIn("payload=available", summary)
        self.assertIn("session://alpha: scope=project:alpha latest=snapshot_soft_delete", summary)
        self.assertIn("events=5", summary)
        self.assertIn("context_budget_tokens=256", summary)
        self.assertIn(f"latest_soft_deleted={alpha_snapshot['session_snapshot_id']}", summary)
        self.assertIn("deleted_reason=retention window expired", summary)
        self.assertIn("latest_end=", summary)

    def test_agent_pack_path_uses_project_local_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(agent_pack_path(cwd=root), root / ".zerker" / "agents" / "manual-agent-pack.md")

    def test_build_agent_config_preset_wraps_mcp_config(self):
        result = build_agent_config_preset(
            "claude-code",
            name="zerker-memory",
            command="zmem",
            db_path=Path(".zerker/memory.sqlite"),
            policy_path=Path(".zerker/policy.json"),
        )

        server = result["config"]["mcpServers"]["zerker-memory"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.agent_config.v1")
        self.assertEqual(result["preset"], "claude-code")
        self.assertIn("Claude Code", result["install_hint"])
        self.assertEqual(
            server["args"],
            ["--db", ".zerker/memory.sqlite", "--policy", ".zerker/policy.json", "mcp", "--profile", "agent"],
        )

    def test_build_agent_server_snippet_returns_single_server_entry(self):
        result = build_agent_server_snippet(
            "openclaw",
            name="zerker-memory",
            command="zmem",
            db_path=Path(".zerker/memory.sqlite"),
            policy_path=Path(".zerker/policy.json"),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.agent_server_snippet.v1")
        self.assertEqual(result["server"]["command"], "zmem")
        self.assertEqual(
            result["server"]["args"],
            ["--db", ".zerker/memory.sqlite", "--policy", ".zerker/policy.json", "mcp", "--profile", "agent"],
        )

    def test_agent_config_parser(self):
        args = build_parser().parse_args(["agent", "config", "codex", "--no-policy", "--out", "/tmp/codex-mcp.json"])

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "config")
        self.assertEqual(args.preset, "codex")
        self.assertFalse(args.include_policy)
        self.assertEqual(str(args.out), "/tmp/codex-mcp.json")

    def test_agent_install_parser(self):
        args = build_parser().parse_args(["agent", "install", "codex", "--config-path", "/tmp/codex.toml", "--force", "--summary"])

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "install")
        self.assertEqual(args.preset, "codex")
        self.assertEqual(str(args.config_path), "/tmp/codex.toml")
        self.assertTrue(args.force)
        self.assertTrue(args.summary)
        self.assertFalse(args.summary_only)

    def test_agent_install_parser_accepts_summary_only(self):
        args = build_parser().parse_args(["agent", "install", "generic", "--summary-only"])

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "install")
        self.assertEqual(args.preset, "generic")
        self.assertTrue(args.summary_only)
        self.assertFalse(args.summary)

    def test_agent_guide_parser(self):
        args = build_parser().parse_args(["agent", "guide", "openclaw", "--config-path", "/tmp/openclaw-mcp.json"])

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "guide")
        self.assertEqual(args.preset, "openclaw")
        self.assertEqual(str(args.config_path), "/tmp/openclaw-mcp.json")

    def test_agent_checklist_parser(self):
        args = build_parser().parse_args(["agent", "checklist", "openclaw", "--out", "/tmp/openclaw-checklist.md", "--force"])

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "checklist")
        self.assertEqual(args.preset, "openclaw")
        self.assertEqual(str(args.out), "/tmp/openclaw-checklist.md")
        self.assertTrue(args.force)

    def test_agent_pack_parser(self):
        args = build_parser().parse_args(
            ["agent", "pack", "--out", "/tmp/manual-agent-pack.md", "--force", "--summary-only"]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "pack")
        self.assertEqual(str(args.out), "/tmp/manual-agent-pack.md")
        self.assertTrue(args.force)
        self.assertTrue(args.summary_only)
        self.assertFalse(args.summary)

    def test_agent_snippet_parser(self):
        args = build_parser().parse_args(["agent", "snippet", "openclaw", "--no-policy", "--out", "/tmp/openclaw-server.json"])

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "snippet")
        self.assertEqual(args.preset, "openclaw")
        self.assertFalse(args.include_policy)
        self.assertEqual(str(args.out), "/tmp/openclaw-server.json")

    def test_agent_mcp_smoke_parser(self):
        args = build_parser().parse_args(["agent", "mcp-smoke", "--agent", "hermes", "--scope", "project"])

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "mcp-smoke")
        self.assertEqual(args.agent, "hermes")
        self.assertEqual(args.scope, "project")

    def test_doctor_parser_accepts_agent_install_checks(self):
        args = build_parser().parse_args(
            ["doctor", "--agent", "codex", "--agent", "claude-code", "--agent-config", "openclaw=/tmp/openclaw.json", "--skip-eval"]
        )

        self.assertEqual(args.command, "doctor")
        self.assertEqual(args.agent, ["codex", "claude-code"])
        self.assertEqual(args.agent_config, ["openclaw=/tmp/openclaw.json"])
        self.assertTrue(args.skip_eval)

    def test_status_parser_accepts_summary_only(self):
        args = build_parser().parse_args(["status", "--skip-eval", "--summary-only"])

        self.assertEqual(args.command, "status")
        self.assertTrue(args.skip_eval)
        self.assertTrue(args.summary_only)
        self.assertFalse(args.summary)

    def test_workspace_parser_accepts_register_and_alias(self):
        register = build_parser().parse_args(
            ["workspace", "register", "--name", "Zerker Memory", "--root", "/tmp/zmem", "--no-current"]
        )
        status = build_parser().parse_args(["ws", "status"])
        sources = build_parser().parse_args(["ws", "sources", "--limit", "7"])

        self.assertEqual(register.command, "workspace")
        self.assertEqual(register.workspace_command, "register")
        self.assertEqual(register.name, "Zerker Memory")
        self.assertEqual(str(register.root), "/tmp/zmem")
        self.assertTrue(register.no_current)
        self.assertEqual(status.command, "ws")
        self.assertEqual(status.workspace_command, "status")
        self.assertEqual(sources.command, "ws")
        self.assertEqual(sources.workspace_command, "sources")
        self.assertEqual(sources.limit, 7)

    def test_launch_proof_parser(self):
        args = build_parser().parse_args(["launch-proof", "--out-dir", "/tmp/launch-proof", "--agent", "openclaw", "--summary-only"])

        self.assertEqual(args.command, "launch-proof")
        self.assertEqual(str(args.out_dir), "/tmp/launch-proof")
        self.assertEqual(args.agent, "openclaw")
        self.assertEqual(args.scope, "project")
        self.assertTrue(args.summary_only)

    def test_release_pack_parser(self):
        args = build_parser().parse_args(["release-pack", "--agent", "openclaw", "--allow-placeholders", "--summary-only"])

        self.assertEqual(args.command, "release-pack")
        self.assertEqual(args.agent, "openclaw")
        self.assertTrue(args.allow_placeholders)
        self.assertTrue(args.summary_only)

    def test_prelaunch_parser_accepts_summary_only(self):
        args = build_parser().parse_args(["prelaunch", "--allow-placeholders", "--no-launch-proof", "--summary-only"])

        self.assertEqual(args.command, "prelaunch")
        self.assertTrue(args.allow_placeholders)
        self.assertTrue(args.no_launch_proof)
        self.assertTrue(args.summary_only)

    def test_handoff_parser_accepts_action_and_summary_only(self):
        args = build_parser().parse_args(["handoff", "--out-dir", "/tmp/handoff", "--action-id", "act_123", "--summary-only"])

        self.assertEqual(args.command, "handoff")
        self.assertEqual(str(args.out_dir), "/tmp/handoff")
        self.assertEqual(args.action_id, "act_123")
        self.assertTrue(args.summary_only)

    def test_restore_parser_accepts_handoff_dir_and_summary_only(self):
        args = build_parser().parse_args(["restore", "--handoff-dir", "/tmp/handoff", "--summary-only"])

        self.assertEqual(args.command, "restore")
        self.assertEqual(str(args.handoff_dir), "/tmp/handoff")
        self.assertTrue(args.summary_only)
        self.assertIsNone(args.snapshot_path)

    def test_restore_parser_accepts_snapshot_path_and_summary_only(self):
        args = build_parser().parse_args(["restore", "/tmp/handoff.snapshot.json", "--summary-only"])

        self.assertEqual(args.command, "restore")
        self.assertEqual(str(args.snapshot_path), "/tmp/handoff.snapshot.json")
        self.assertTrue(args.summary_only)
        self.assertIsNone(args.handoff_dir)

    def test_create_handoff_package_exports_snapshot_and_latest_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            store = MemoryStore(work / ".zerker" / "memory.sqlite")
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            receipt = store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")

            result = create_handoff_package(
                store,
                providers_path=work / ".zerker" / "providers.json",
                out_dir=work / ".zerker" / "handoff",
                action_id=None,
            )
            summary = render_handoff_summary(result)
            readme_exists = Path(result["readme_path"]).exists()
            manifest_exists = Path(result["manifest_path"]).exists()
            snapshot_exists = Path(result["snapshot_path"]).exists()
            bundle_exists = Path(result["bundle_path"]).exists()
            treeship_exists = Path(result["treeship_path"]).exists()
            readme = Path(result["readme_path"]).read_text(encoding="utf-8")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.handoff.v1")
        self.assertEqual(result["action_id"], receipt["action_id"])
        self.assertTrue(readme_exists)
        self.assertTrue(manifest_exists)
        self.assertTrue(snapshot_exists)
        self.assertTrue(bundle_exists)
        self.assertTrue(treeship_exists)
        self.assertTrue(result["snapshot_verify"]["ok"])
        self.assertTrue(result["bundle_verify"]["ok"])
        self.assertIn("Bundle verify: ok", summary)
        self.assertIn("Manifest:", summary)
        self.assertIn("Treeship statement:", summary)
        self.assertIn("Treeship statement:", readme)
        self.assertIn("restore --handoff-dir .", readme)
        self.assertEqual(manifest["schema"], "zerker.handoff_manifest.v1")
        self.assertEqual(manifest["snapshot_path"].split("/")[0], "exports")

    def test_write_public_verify_script_uses_script_relative_logs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_path = root / "PUBLIC_VERIFY_COMMANDS.sh"
            logs_dir_path = root / "public-verify-logs"

            write_public_verify_script(script_path=script_path, logs_dir_path=logs_dir_path)

            script = script_path.read_text(encoding="utf-8")

        self.assertIn('SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"', script)
        self.assertIn('LOG_DIR="$SCRIPT_DIR/public-verify-logs"', script)
        self.assertNotIn(str(logs_dir_path), script)

    def test_create_handoff_package_handles_snapshot_only_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            store = MemoryStore(work / ".zerker" / "memory.sqlite")
            store.remember(
                "Use SQLite for local memory",
                memory_type="semantic",
                scope="project",
                source_kind="human",
            )

            result = create_handoff_package(
                store,
                providers_path=work / ".zerker" / "providers.json",
                out_dir=work / ".zerker" / "handoff",
                action_id=None,
            )
            readme = Path(result["readme_path"]).read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertIsNone(result["action_id"])
        self.assertIsNone(result["bundle_path"])
        self.assertIsNone(result["bundle_verify"])
        self.assertIsNone(result["treeship_path"])
        self.assertIn("none yet", readme)

    def test_create_handoff_package_includes_session_lifecycle_rollup_for_context_boundary_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            store = MemoryStore(work / ".zerker" / "memory.sqlite")
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="resume after compaction",
                context_budget_tokens=256,
            )
            store.checkpoint_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="checkpoint before handoff",
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="snapshot before handoff",
            )
            store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="codex",
                reason="retention compacted before handoff",
            )
            store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="closeout after handoff",
            )

            result = create_handoff_package(
                store,
                providers_path=work / ".zerker" / "providers.json",
                out_dir=work / ".zerker" / "handoff",
                action_id=None,
            )
            summary = render_handoff_summary(result)
            readme = Path(result["readme_path"]).read_text(encoding="utf-8")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

        lifecycle_rollup = result["session_lifecycle_rollup"]
        retention_rollup = result["session_retention_rollup"]
        self.assertEqual(lifecycle_rollup["count"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["start"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["checkpoint"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["snapshot"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["snapshot_soft_delete"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["end"], 1)
        self.assertEqual(lifecycle_rollup["verified_receipt_count"], 5)
        self.assertEqual(lifecycle_rollup["failed_receipt_count"], 0)
        self.assertEqual(lifecycle_rollup["sessions"][0]["session_id"], "session://alpha")
        self.assertEqual(lifecycle_rollup["sessions"][0]["latest_event_kind"], "end")
        self.assertEqual(lifecycle_rollup["sessions"][0]["latest_payload_status"], "soft_deleted")
        self.assertEqual(
            lifecycle_rollup["sessions"][0]["latest_start_token_budget_hint"]["context_budget_tokens"],
            256,
        )
        self.assertEqual(retention_rollup["count"], 1)
        self.assertEqual(retention_rollup["retention_state_counts"]["soft_deleted_only"], 1)
        self.assertEqual(retention_rollup["payload_status_counts"], {"available": 0, "soft_deleted": 1})
        self.assertEqual(retention_rollup["sessions"][0]["session_id"], "session://alpha")
        self.assertEqual(retention_rollup["sessions"][0]["retention_state"], "soft_deleted_only")
        self.assertEqual(retention_rollup["sessions"][0]["latest_payload_status"], "soft_deleted")
        self.assertEqual(retention_rollup["sessions"][0]["latest_soft_deleted_reason"], "retention compacted before handoff")
        self.assertIn("## Session Lifecycle Continuity", readme)
        self.assertIn("Session lifecycle rollup", readme)
        self.assertIn("## Session Snapshot Retention", readme)
        self.assertIn("Session snapshot retention", readme)
        self.assertIn("soft_deleted_only=1", readme)
        self.assertIn("retention compacted before handoff", readme)
        self.assertEqual(manifest["session_lifecycle_rollup"]["count"], 1)
        self.assertEqual(manifest["session_retention_rollup"]["count"], 1)
        self.assertEqual(
            manifest["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"],
            "end",
        )
        self.assertEqual(
            manifest["session_retention_rollup"]["sessions"][0]["latest_payload_status"],
            "soft_deleted",
        )
        self.assertIn("Session lifecycle rollup", manifest["session_lifecycle_rollup_summary"])
        self.assertIn("Session snapshot retention", manifest["session_retention_rollup_summary"])
        self.assertIn("retention compacted before handoff", manifest["session_retention_rollup_summary"])
        self.assertIn("Lifecycle sessions: 1", summary)
        self.assertIn("Lifecycle events: starts=1 checkpoints=1 snapshots=1 snapshot_soft_deletes=1 ends=1", summary)
        self.assertIn("Lifecycle receipt provenance: 5 verified, 0 failed", summary)

    def test_run_release_pack_refreshes_artifacts_and_prelaunch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=root / ".zerker" / "policy.json")
            os.chdir(root)
            try:
                store.init()
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_agent_prompt_template(root / ".zerker" / "AGENT_PROMPT.md", force=False)
                write_json_file(root / ".zerker" / "mcp.json", {"mcpServers": {}}, force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)
                run_agent_smoke(store, agent_id="codex", scope="project", task="prove governed memory")
                self._write_prelaunch_fixture(root, readme="https://github.com/zerkerlabs/zmem")

                result = run_release_pack(
                    store,
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path("examples") / "bt_trace.jsonl",
                    action_id=None,
                    allow_placeholders=True,
                )
                summary = render_release_pack_summary(result)
                handoff_manifest_exists = Path(result["handoff"]["manifest_path"]).exists()
                launch_report_exists = Path(result["launch_proof"]["report_path"]).exists()
                capture_checklist_exists = Path(result["capture_checklist_path"]).exists()
                launch_asset_handoff_exists = Path(result["launch_asset_handoff_path"]).exists()
                public_verify_handoff_exists = Path(result["public_verify_handoff_path"]).exists()
                public_verify_checklist_exists = Path(result["public_verify_checklist_path"]).exists()
                public_verify_runbook_exists = Path(result["launch_proof"]["public_verify_runbook_path"]).exists()
                operator_packet_archive_exists = Path(result["operator_packet_archive_path"]).exists()
                manifest = json.loads(Path(result["launch_proof"]["manifest_path"]).read_text(encoding="utf-8"))
                capture_checklist = Path(result["capture_checklist_path"]).read_text(encoding="utf-8")
                launch_asset_handoff = Path(result["launch_asset_handoff_path"]).read_text(encoding="utf-8")
                public_verify_handoff = Path(result["public_verify_handoff_path"]).read_text(encoding="utf-8")
                public_verify_runbook = Path(result["launch_proof"]["public_verify_runbook_path"]).read_text(encoding="utf-8")
                launch_report = Path(result["launch_proof"]["report_path"]).read_text(encoding="utf-8")
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.release_pack.v1")
        self.assertTrue(handoff_manifest_exists)
        self.assertTrue(launch_report_exists)
        self.assertTrue(capture_checklist_exists)
        self.assertTrue(launch_asset_handoff_exists)
        self.assertTrue(public_verify_handoff_exists)
        self.assertTrue(public_verify_checklist_exists)
        self.assertTrue(public_verify_runbook_exists)
        self.assertTrue(operator_packet_archive_exists)
        self.assertTrue(result["prelaunch"]["ok"])
        self.assertFalse(result["public_verify"]["ready"])
        self.assertIn("Zerker Memory release pack", summary)
        self.assertIn("Launch proof: ok", summary)
        self.assertIn("Public verify: pending", summary)
        self.assertIn("Launch assets: pending", summary)
        self.assertIn("Capture checklist:", summary)
        self.assertIn("Launch asset handoff:", summary)
        self.assertIn("Public verify handoff:", summary)
        self.assertIn("Public verify checklist:", summary)
        self.assertIn("Public verify script:", summary)
        self.assertIn("Operator packet archive:", summary)
        self.assertIn("Operator packet: ok", summary)
        self.assertIn(".zerker/launch-proof/public-verify-operator-packet.tar.gz", summary)
        self.assertIn(".zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh", summary)
        self.assertIn(".zerker/launch-proof/public-verify-logs", summary)
        self.assertIn(".zerker/launch-proof/public-verify-return-packet.tar.gz", summary)
        self.assertIn(
            "Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz",
            summary,
        )
        self.assertIn("Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", summary)
        self.assertIn("Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html", summary)
        self.assertIn("Phase 1 complete when:", summary)
        self.assertIn("verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` is ready", summary)
        self.assertEqual(manifest["launch_assets"][-1]["id"], "ui-handoff-restore")
        self.assertEqual(manifest["launch_assets_dir_path"], "assets")
        self.assertEqual(manifest["launch_asset_handoff_path"], "LAUNCH_ASSET_HANDOFF.md")
        self.assertEqual(manifest["public_verify_handoff_path"], "PUBLIC_VERIFY_HANDOFF.md")
        self.assertEqual(manifest["public_verify"]["handoff_path"], "PUBLIC_VERIFY_HANDOFF.md")
        self.assertEqual(manifest["public_verify_runbook_path"], "CLEAN_SHELL_PUBLIC_VERIFY.md")
        self.assertEqual(manifest["public_verify"]["runbook_path"], "CLEAN_SHELL_PUBLIC_VERIFY.md")
        self.assertTrue(manifest["local_alpha_gate"].startswith("ok with warnings ("))
        self.assertIn("launch_assets", manifest["local_alpha_gate"])
        self.assertIn("public_verify_evidence", manifest["local_alpha_gate"])
        self.assertTrue(manifest["strict_publish_gate"].startswith("blocked ("))
        self.assertIn("launch_assets", manifest["strict_publish_gate"])
        self.assertIn("public_verify_evidence", manifest["strict_publish_gate"])
        self.assertEqual(manifest["launch_assets"][-1]["output_path"], "assets/ui-handoff-restore.gif")
        self.assertIn("Zerker Memory Public Verify Handoff", public_verify_handoff)
        self.assertIn("# Clean-Shell Public Verify", public_verify_runbook)
        self.assertIn("PUBLIC_VERIFY_COMMANDS.sh", public_verify_runbook)
        self.assertIn("tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof", public_verify_runbook)
        self.assertIn("zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only", public_verify_handoff)
        self.assertIn("## Success Criteria", public_verify_handoff)
        self.assertIn("`curl-install.log`", public_verify_handoff)
        self.assertIn("`packaged-release-smoke.log`", public_verify_handoff)
        self.assertIn("`ui-release-pack.gif` from `ui-release-pack`", public_verify_handoff)
        self.assertIn("`ui-handoff-restore.gif` from `ui-handoff-restore`", public_verify_handoff)
        self.assertIn("## Return Packet Contract", public_verify_handoff)
        self.assertIn("`.zerker/launch-proof/public-verify-summary.md`", public_verify_handoff)
        self.assertIn("ui-release-pack", capture_checklist)
        self.assertIn("ui-handoff-restore", capture_checklist)
        self.assertIn("handoff-restore-terminal", capture_checklist)
        self.assertIn("Required capture set: `8` assets total; `zmem verify-launch-assets --summary-only` must report `8/8 captured`.", capture_checklist)
        self.assertIn("Capture: Show launch proof, handoff, public verify script, logs dir, and the current strict publish gate result.", capture_checklist)
        self.assertIn("Save as: `assets/ui-release-pack.gif`", capture_checklist)
        self.assertIn("Zerker Memory Launch Asset Handoff", launch_asset_handoff)
        self.assertIn("`ui-release-pack.gif` from `ui-release-pack`", launch_asset_handoff)
        self.assertIn("`ui-handoff-restore.gif` from `ui-handoff-restore`", launch_asset_handoff)
        self.assertIn("`zmem verify-launch-assets --summary-only` reports `8/8 captured` before handback.", launch_asset_handoff)
        self.assertIn("`zmem verify-launch-assets --summary-only` reports `8/8 captured` before `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` is accepted.", public_verify_handoff)
        self.assertIn("Launch Asset Storyboard", launch_report)
        self.assertIn("ui-handoff-restore", launch_report)

    def test_run_launch_proof_surfaces_public_verify_contract_in_readme_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)

                result = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path("examples") / "bt_trace.jsonl",
                )
                readme = Path(result["summary_path"]).read_text(encoding="utf-8")
                report = Path(result["report_path"]).read_text(encoding="utf-8")
                public_verify_summary = Path(result["public_verify_summary_path"]).read_text(encoding="utf-8")
                public_verify_runbook = Path(result["public_verify_runbook_path"]).read_text(encoding="utf-8")
                manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            finally:
                os.chdir(previous_cwd)

        self.assertIn("## Clean-Shell Public Verify", readme)
        self.assertIn("python3 scripts/release_smoke.py --require-install-mode packaged", readme)
        self.assertIn("`curl-install.log`", readme)
        self.assertIn("Launch assets dir", readme)
        self.assertIn("Launch assets: `0/6` expected assets present", public_verify_summary)
        self.assertIn("Capture checklist: `.zerker/launch-proof/CAPTURE_CHECKLIST.md`", public_verify_summary)
        self.assertIn("Return packet finalize: `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`", public_verify_summary)
        self.assertIn("Return packet archive: `.zerker/launch-proof/public-verify-return-packet.tar.gz`", public_verify_summary)
        self.assertIn("Open first: `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`", public_verify_summary)
        self.assertIn("Operator prompt: `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`", public_verify_summary)
        self.assertIn("Outbound packet: `.zerker/launch-proof/public-verify-operator-packet.tar.gz`", public_verify_summary)
        self.assertIn(
            "Verify outbound packet: `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`",
            public_verify_summary,
        )
        self.assertIn(
            "Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz",
            public_verify_summary,
        )
        self.assertIn("Verify before asset pass: `zmem verify-public-verify --summary-only`", public_verify_summary)
        self.assertIn("Verify after asset capture: `zmem verify-launch-assets --summary-only`", public_verify_summary)
        self.assertIn(
            "Bootstrap note: use one bootstrap install to create the clean repo path and restore the operator packet.",
            public_verify_summary,
        )
        self.assertIn(
            "PUBLIC_VERIFY_COMMANDS.sh` reruns the raw installer itself and records `public-verify-logs/curl-install.log`",
            public_verify_summary,
        )
        self.assertIn(
            "Receive-side accept: `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`",
            public_verify_summary,
        )
        self.assertIn("## Next Step", public_verify_summary)
        self.assertIn("Run PUBLIC_VERIFY_COMMANDS.sh from a clean networked shell and keep the saved logs with this proof pack.", public_verify_summary)
        self.assertIn("## Expected Launch Assets", public_verify_summary)
        self.assertIn("- Launch asset board: `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`", public_verify_summary)
        self.assertIn("`install-status.png` from `install-status`: missing", public_verify_summary)
        self.assertIn("  Command: `bash install.sh`", public_verify_summary)
        self.assertIn("  Capture: End on `Zerker Memory status`.", public_verify_summary)
        self.assertIn("`ui-release-pack.gif` from `ui-release-pack`: missing", public_verify_summary)
        self.assertIn('  Command: `zmem --db ".zerker/launch-proof/memory.sqlite" ui`', public_verify_summary)
        self.assertIn("  Capture: Show the `zmem ui` release-pack action and the proof-review surface.", public_verify_summary)
        self.assertIn("<h2>Clean-Shell Public Verify</h2>", report)
        self.assertIn("packaged-install proof", report)
        self.assertIn("Operator Prompt", report)
        self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", report)
        self.assertIn("Runbook", report)
        self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", report)
        self.assertIn("Outbound Packet", report)
        self.assertIn("public-verify-operator-packet.tar.gz", report)
        self.assertIn("Durable Brief", report)
        self.assertIn("docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", report)
        self.assertIn("docs/LAUNCH_ASSET_BOARD.html", report)
        self.assertIn("Forward together:", report)
        self.assertIn("public-verify-logs", report)
        self.assertIn("assets/ui-release-pack.gif", report)
        self.assertIn("# Clean-Shell Public Verify", public_verify_runbook)
        self.assertEqual(manifest["public_verify_runbook_path"], "CLEAN_SHELL_PUBLIC_VERIFY.md")
        self.assertEqual(manifest["public_verify"]["runbook_path"], "CLEAN_SHELL_PUBLIC_VERIFY.md")

    def test_run_launch_proof_mirrors_handoff_session_continuity_into_operator_packet_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                source_store = MemoryStore(root / ".zerker" / "memory.sqlite")
                source_store.remember(
                    "Production deploys require approval",
                    memory_type="policy",
                    scope="project",
                    source_kind="human",
                )
                source_store.start_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="resume after compaction",
                    context_budget_tokens=256,
                )
                source_store.checkpoint_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="checkpoint before launch proof",
                )
                session_snapshot = source_store.snapshot_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="snapshot before launch proof",
                )
                source_store.soft_delete_session_snapshot_payload(
                    session_snapshot["session_snapshot_id"],
                    actor_id="reviewer",
                    reason="retention compacted before operator packet",
                )
                source_store.end_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="closeout before launch proof",
                )
                create_handoff_package(
                    source_store,
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "handoff",
                    action_id=None,
                )
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)

                result = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path("examples") / "bt_trace.jsonl",
                )
                manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
                public_verify_summary = Path(result["public_verify_summary_path"]).read_text(encoding="utf-8")
                operator_packet = verify_operator_packet_archive(Path(result["operator_packet_archive_path"]))
                operator_packet_summary = render_operator_packet_summary(operator_packet)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(manifest["session_lifecycle_rollup"]["count"], 1)
        self.assertEqual(manifest["session_lifecycle_rollup"]["event_kind_counts"]["start"], 1)
        self.assertEqual(manifest["session_lifecycle_rollup"]["event_kind_counts"]["checkpoint"], 1)
        self.assertEqual(manifest["session_lifecycle_rollup"]["event_kind_counts"]["snapshot"], 1)
        self.assertEqual(manifest["session_lifecycle_rollup"]["event_kind_counts"]["snapshot_soft_delete"], 1)
        self.assertEqual(manifest["session_lifecycle_rollup"]["event_kind_counts"]["end"], 1)
        self.assertEqual(manifest["session_lifecycle_rollup"]["verified_receipt_count"], 5)
        self.assertEqual(manifest["session_retention_rollup"]["count"], 1)
        self.assertEqual(manifest["session_retention_rollup"]["retention_state_counts"]["soft_deleted_only"], 1)
        self.assertEqual(
            manifest["session_retention_rollup"]["sessions"][0]["latest_soft_deleted_reason"],
            "retention compacted before operator packet",
        )
        self.assertIn("Lifecycle sessions: 1", public_verify_summary)
        self.assertIn("Lifecycle events: starts=1 checkpoints=1 snapshots=1 snapshot_soft_deletes=1 ends=1", public_verify_summary)
        self.assertIn("Lifecycle receipt provenance: 5 verified, 0 failed", public_verify_summary)
        self.assertIn("Latest lifecycle session: session://alpha latest=end payload=soft_deleted context_budget_tokens=256", public_verify_summary)
        self.assertIn("Retention sessions: 1", public_verify_summary)
        self.assertIn("Retention states: all_available=0 mixed=0 soft_deleted_only=1", public_verify_summary)
        self.assertIn("Retention payloads: 0 available, 1 soft-deleted", public_verify_summary)
        self.assertIn("retention compacted before operator packet", public_verify_summary)
        self.assertEqual(operator_packet["session_lifecycle_rollup"]["count"], 1)
        self.assertEqual(operator_packet["session_retention_rollup"]["count"], 1)
        self.assertIn("Lifecycle sessions: 1", operator_packet_summary)
        self.assertIn("Lifecycle receipt provenance: 5 verified, 0 failed", operator_packet_summary)
        self.assertIn("Retention sessions: 1", operator_packet_summary)
        self.assertIn("retention compacted before operator packet", operator_packet_summary)

    def test_restore_handoff_package_verifies_and_restores_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_store = MemoryStore(work / ".zerker" / "source.sqlite")
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            source_store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
            handoff = create_handoff_package(
                source_store,
                providers_path=work / ".zerker" / "providers.json",
                out_dir=work / ".zerker" / "handoff",
                action_id=None,
            )

            target_store = MemoryStore(work / ".zerker" / "restored.sqlite")
            result = restore_handoff_package(target_store, handoff_dir=Path(handoff["out_dir"]))
            summary = render_restore_summary(result)

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.restore_handoff.v1")
        self.assertTrue(result["snapshot_verify"]["ok"])
        self.assertTrue(result["bundle_verify"]["ok"])
        self.assertTrue(result["restore_verify"]["ok"])
        self.assertFalse(result["restore_verify"]["semantic_truth_guaranteed"])
        self.assertEqual(result["restore"]["memory_count"], 1)
        self.assertEqual(result["restore"]["receipt_count"], 1)
        self.assertIn("Bundle verify: ok", summary)
        self.assertIn("Restore receipt verify: ok", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn("Treeship artifact: none", summary)
        self.assertIn("Restored memories: 1", summary)

    def test_restore_handoff_package_surfaces_session_lifecycle_rollup_for_receive_side_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_store = MemoryStore(work / ".zerker" / "source.sqlite")
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="resume after compaction",
                context_budget_tokens=256,
            )
            source_store.checkpoint_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="checkpoint before handoff",
            )
            session_snapshot = source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="snapshot before handoff",
            )
            source_store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention compacted before handoff",
            )
            source_store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project",
                summary="closeout after handoff",
            )
            handoff = create_handoff_package(
                source_store,
                providers_path=work / ".zerker" / "providers.json",
                out_dir=work / ".zerker" / "handoff",
                action_id=None,
            )

            target_store = MemoryStore(work / ".zerker" / "restored.sqlite")
            result = restore_handoff_package(target_store, handoff_dir=Path(handoff["out_dir"]))
            summary = render_restore_summary(result)

        lifecycle_rollup = result["session_lifecycle_rollup"]
        retention_rollup = result["session_retention_rollup"]
        self.assertEqual(lifecycle_rollup["count"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["start"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["checkpoint"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["snapshot"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["snapshot_soft_delete"], 1)
        self.assertEqual(lifecycle_rollup["event_kind_counts"]["end"], 1)
        self.assertEqual(lifecycle_rollup["verified_receipt_count"], 5)
        self.assertEqual(lifecycle_rollup["failed_receipt_count"], 0)
        self.assertEqual(lifecycle_rollup["sessions"][0]["session_id"], "session://alpha")
        self.assertEqual(lifecycle_rollup["sessions"][0]["latest_event_kind"], "end")
        self.assertEqual(lifecycle_rollup["sessions"][0]["latest_payload_status"], "soft_deleted")
        self.assertEqual(
            lifecycle_rollup["sessions"][0]["latest_start_token_budget_hint"]["context_budget_tokens"],
            256,
        )
        self.assertEqual(retention_rollup["count"], 1)
        self.assertEqual(retention_rollup["retention_state_counts"]["soft_deleted_only"], 1)
        self.assertEqual(retention_rollup["payload_status_counts"], {"available": 0, "soft_deleted": 1})
        self.assertEqual(retention_rollup["sessions"][0]["latest_payload_status"], "soft_deleted")
        self.assertEqual(retention_rollup["sessions"][0]["latest_soft_deleted_reason"], "retention compacted before handoff")
        self.assertIn("Lifecycle sessions: 1", summary)
        self.assertIn("Lifecycle events: starts=1 checkpoints=1 snapshots=1 snapshot_soft_deletes=1 ends=1", summary)
        self.assertIn("Lifecycle receipt provenance: 5 verified, 0 failed", summary)
        self.assertIn("session://alpha latest=end payload=soft_deleted", summary)
        self.assertIn("context_budget_tokens=256", summary)
        self.assertIn("Retention sessions: 1", summary)
        self.assertIn("Retention states: all_available=0 mixed=0 soft_deleted_only=1", summary)
        self.assertIn("Retention payloads: 0 available, 1 soft-deleted", summary)
        self.assertIn("retention compacted before handoff", summary)
        self.assertNotIn("Session continuity: none", summary)

    def test_restore_snapshot_summary_only_verifies_and_restores_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_store = MemoryStore(work / ".zerker" / "source.sqlite")
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
            )
            source_store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")
            snapshot_path = work / ".zerker" / "snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(source_store.snapshot()), encoding="utf-8")
            db_path = work / ".zerker" / "restored.sqlite"

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Source: {snapshot_path.resolve()}", summary)
        self.assertIn(f"Snapshot: {snapshot_path.resolve()}", summary)
        self.assertIn("Snapshot verify: ok", summary)
        self.assertIn("Snapshot write receipts: 1", summary)
        self.assertIn("Snapshot write receipt chains: 1", summary)
        self.assertIn("Snapshot write receipt verify: ok (1/1 verified)", summary)
        self.assertIn("Snapshot verified write transitions: 0", summary)
        self.assertIn("Snapshot provenance anchors: 1 verified", summary)
        self.assertIn("Snapshot Treeship artifacts: none", summary)
        self.assertIn("Snapshot trusted provenance: verified", summary)
        self.assertIn("Restore receipt verify: ok", summary)
        self.assertIn("Treeship artifact: none", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)
        self.assertIn(
            "Session continuity: none (standalone snapshot restores do not carry lifecycle or retention history)",
            summary,
        )
        self.assertNotIn("Lifecycle sessions:", summary)
        self.assertNotIn("Retention sessions:", summary)

    def test_snapshot_export_writes_adjacent_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot export",
                context_budget_tokens=256,
            )
            store.checkpoint_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="checkpoint before raw snapshot export",
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot export",
            )
            store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention compacted before raw snapshot export",
            )
            store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="end before raw snapshot export",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            result = json.loads(output.getvalue())
            continuity_path = Path(result["continuity_path"])
            continuity_exists = continuity_path.exists()
            continuity = json.loads(continuity_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["format"], "snapshot")
        self.assertEqual(result["path"], str(snapshot_path))
        self.assertTrue(continuity_exists)
        self.assertEqual(continuity["schema"], "zerker.snapshot_continuity.v1")
        self.assertEqual(continuity["snapshot_hash"], result["payload"]["snapshot_hash"])
        self.assertEqual(continuity["session_lifecycle_rollup"]["count"], 1)
        self.assertEqual(
            continuity["session_lifecycle_rollup"]["event_kind_counts"],
            {"start": 1, "checkpoint": 1, "snapshot": 1, "snapshot_soft_delete": 1, "end": 1},
        )
        self.assertEqual(continuity["session_retention_rollup"]["count"], 1)
        self.assertEqual(
            continuity["session_retention_rollup"]["retention_state_counts"],
            {"all_available": 0, "mixed": 0, "soft_deleted_only": 1},
        )

    def test_snapshot_parser_accepts_verify_summary_only(self):
        args = build_parser().parse_args(["snapshot", "verify", "/tmp/snapshot.json", "--summary-only"])

        self.assertEqual(args.command, "snapshot")
        self.assertEqual(args.snapshot_action, "verify")
        self.assertEqual(args.snapshot_path, Path("/tmp/snapshot.json"))
        self.assertTrue(args.summary_only)

    def test_snapshot_verify_summary_only_surfaces_adjacent_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify",
                context_budget_tokens=256,
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify",
            )
            store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention compacted before raw snapshot verify",
            )
            store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="end before raw snapshot verify",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Snapshot: {snapshot_path}", summary)
        self.assertIn(f"Session continuity sidecar: {snapshot_path.with_suffix('.continuity.json').resolve()}", summary)
        self.assertIn("Session continuity verify: ok", summary)
        self.assertIn("Lifecycle sessions: 1", summary)
        self.assertIn("Lifecycle events: starts=1 checkpoints=0 snapshots=1 snapshot_soft_deletes=1 ends=1", summary)
        self.assertIn("Retention sessions: 1", summary)
        self.assertIn("Retention states: all_available=0 mixed=0 soft_deleted_only=1", summary)
        self.assertIn("Latest lifecycle retention: retention compacted before raw snapshot verify", summary)
        self.assertNotIn("Session continuity: none", summary)

    def test_snapshot_verify_summary_only_reports_mismatched_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify mismatch",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["snapshot_hash"] = "sha256:copied-sidecar"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn("Session continuity error: continuity sidecar snapshot hash mismatch", summary)
        self.assertIn("expected", summary)
        self.assertIn("got sha256:copied-sidecar", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_missing_lifecycle_rollup_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify truncated sidecar",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload.pop("session_lifecycle_rollup", None)
            continuity_payload.pop("session_lifecycle_rollup_summary", None)
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn("Session continuity error: invalid continuity sidecar: missing session_lifecycle_rollup", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_invalid_lifecycle_rollup_session_entry_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify malformed lifecycle entry",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_lifecycle_rollup"]["sessions"] = ["bad-entry"]
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_lifecycle_rollup.sessions[0] must be an object",
            summary,
        )
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_lifecycle_rollup_count_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify incoherent lifecycle count",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_lifecycle_rollup"]["count"] = 99
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_lifecycle_rollup.count must equal sessions length (99 != 1)",
            summary,
        )
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_lifecycle_event_totals_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify incoherent lifecycle events",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_lifecycle_rollup"]["event_kind_counts"]["start"] = 7
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_lifecycle_rollup.event_kind_counts.start must equal summed session start_count (7 != 1)",
            summary,
        )
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_retention_payload_totals_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify incoherent retention payload totals",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify incoherent retention payload totals",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["payload_status_counts"]["available"] = 7
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_retention_rollup.payload_status_counts.available must equal summed session available_payload_count (7 != 1)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_retention_state_totals_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify incoherent retention states",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify incoherent retention states",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["all_available"] = 0
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_retention_rollup.retention_state_counts.all_available must equal counted session retention_state=all_available (0 != 1)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_retention_state_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative retention state total",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify negative retention state total",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["all_available"] = -1
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.retention_state_counts.all_available must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_mixed_retention_state_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative mixed retention state total",
                context_budget_tokens=256,
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify negative mixed retention state total",
            )
            store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="codex",
                reason="retention compacted before verify mixed total check",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["mixed"] = -1
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.retention_state_counts.mixed must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_soft_deleted_only_retention_state_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative soft-deleted-only retention state total",
                context_budget_tokens=256,
            )
            session_snapshot = store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify negative soft-deleted-only retention state total",
            )
            store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="codex",
                reason="retention compacted before verify soft-deleted total check",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["soft_deleted_only"] = -1
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.retention_state_counts.soft_deleted_only must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_lifecycle_event_totals_in_session_continuity_sidecar(self):
        count_fields = {
            "start": "start_count",
            "checkpoint": "checkpoint_count",
            "snapshot": "snapshot_count",
            "snapshot_soft_delete": "snapshot_soft_delete_count",
            "end": "end_count",
        }

        for event_kind in count_fields:
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify negative {event_kind} lifecycle total",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify negative {event_kind} lifecycle total",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify negative {event_kind} lifecycle total",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify negative {event_kind} lifecycle total",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify negative {event_kind} lifecycle total",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["event_kind_counts"][event_kind] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.event_kind_counts.{event_kind} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_session_lifecycle_counts_in_session_continuity_sidecar(self):
        count_fields = {
            "start": "start_count",
            "checkpoint": "checkpoint_count",
            "snapshot": "snapshot_count",
            "snapshot_soft_delete": "snapshot_soft_delete_count",
            "end": "end_count",
        }

        for event_kind, session_field in count_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify negative session {event_kind} lifecycle count",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify negative session {event_kind} lifecycle count",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify negative session {event_kind} lifecycle count",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify negative session {event_kind} lifecycle count",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify negative session {event_kind} lifecycle count",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][session_field] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].{session_field} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_session_latest_event_kind_in_session_continuity_sidecar(self):
        count_fields = {
            "start": "start_count",
            "checkpoint": "checkpoint_count",
            "snapshot": "snapshot_count",
            "snapshot_soft_delete": "snapshot_soft_delete_count",
            "end": "end_count",
        }

        for event_kind, session_field in count_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify incoherent latest {event_kind} lifecycle row",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify incoherent latest {event_kind} lifecycle row",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify incoherent latest {event_kind} lifecycle row",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify incoherent latest {event_kind} lifecycle row",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify incoherent latest {event_kind} lifecycle row",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][session_field] = 0
                    continuity_payload["session_lifecycle_rollup"]["event_kind_counts"][event_kind] = 0
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].latest_event_kind={event_kind} requires {session_field} > 0",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_missing_latest_event_identifier_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }

        for event_kind, identifier_field in identifier_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify missing latest {event_kind} identifier",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify missing latest {event_kind} identifier",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify missing latest {event_kind} identifier",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify missing latest {event_kind} identifier",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify missing latest {event_kind} identifier",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_field] = None
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].latest_event_kind={event_kind} "
                    f"requires {identifier_field}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_mismatched_latest_lifecycle_id_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }

        for event_kind, identifier_field in identifier_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify mismatched latest lifecycle id for {event_kind}",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify mismatched latest lifecycle id for {event_kind}",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify mismatched latest lifecycle id for {event_kind}",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify mismatched latest lifecycle id for {event_kind}",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify mismatched latest lifecycle id for {event_kind}",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_status_root"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][root_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        f"mismatched-{event_kind}-lifecycle-id"
                    )
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    "session_lifecycle_rollup.sessions[*].latest_lifecycle_id must equal "
                    f"{identifier_field} when latest_event_kind={event_kind}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_missing_latest_event_root_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }

        for event_kind, root_field in root_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify missing latest {event_kind} root",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify missing latest {event_kind} root",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify missing latest {event_kind} root",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify missing latest {event_kind} root",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify missing latest {event_kind} root",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][root_field] = None
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].latest_event_kind={event_kind} "
                    f"requires {root_field}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_mismatched_latest_status_root_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }

        for event_kind, root_field in root_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify mismatched latest status root for {event_kind}",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify mismatched latest status root for {event_kind}",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify mismatched latest status root for {event_kind}",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify mismatched latest status root for {event_kind}",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify mismatched latest status root for {event_kind}",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_status_root"] = "sha256:mismatched-status-root"
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    "session_lifecycle_rollup.sessions[*].latest_status_root must equal "
                    f"{root_field} when latest_event_kind={event_kind}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_mismatched_latest_event_created_at_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }
        created_at_fields = {
            "start": "latest_start_created_at",
            "checkpoint": "latest_checkpoint_created_at",
            "snapshot": "latest_session_snapshot_created_at",
            "snapshot_soft_delete": "latest_soft_deleted_deleted_at",
            "end": "latest_session_end_created_at",
        }

        for event_kind, created_at_field in created_at_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify mismatched latest event created_at for {event_kind}",
                        context_budget_tokens=256,
                    )
                    store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot verify mismatched latest event created_at for {event_kind}",
                    )
                    session_snapshot = store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot verify mismatched latest event created_at for {event_kind}",
                    )
                    store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before verify mismatched latest event created_at for {event_kind}",
                    )
                    store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot verify mismatched latest event created_at for {event_kind}",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_status_root"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][root_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_created_at"] = (
                        f"mismatched-{event_kind}-created-at"
                    )
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    "session_lifecycle_rollup.sessions[*].latest_event_created_at must equal "
                    f"{created_at_field} when latest_event_kind={event_kind}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_lifecycle_receipt_provenance_totals_in_session_continuity_sidecar(self):
        count_totals = {
            "verified_receipt_count": 1,
            "failed_receipt_count": 0,
            "linked_treeship_artifact_count": 0,
        }

        for count_field, session_total in count_totals.items():
            with self.subTest(count_field=count_field):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify incoherent {count_field}",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"][count_field] = 7
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.{count_field} must equal summed session {count_field} "
                    f"(7 != {session_total})",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_lifecycle_receipt_provenance_counts_in_session_continuity_sidecar(self):
        count_fields = (
            "verified_receipt_count",
            "failed_receipt_count",
            "linked_treeship_artifact_count",
        )

        for count_field in count_fields:
            with self.subTest(count_field=count_field):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify negative {count_field}",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"][count_field] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.{count_field} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_session_lifecycle_receipt_provenance_counts_in_session_continuity_sidecar(self):
        count_fields = (
            "verified_receipt_count",
            "failed_receipt_count",
            "linked_treeship_artifact_count",
        )

        for count_field in count_fields:
            with self.subTest(count_field=count_field):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot verify negative session {count_field}",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"][count_field] = 0
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][count_field] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].{count_field} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_latest_start_context_budget_hint_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative latest start context budget hint",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_start_token_budget_hint"] = {
                "context_budget_tokens": -1
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint.context_budget_tokens "
            "must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_malformed_latest_start_token_budget_hint_payloads_in_session_continuity_sidecar(self):
        cases = (
            (
                ["not", "an", "object"],
                "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint must be an object",
            ),
            (
                {"context_budget_tokens": "256"},
                "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint.context_budget_tokens must be an integer",
            ),
            (
                {"context_budget_tokens": True},
                "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint.context_budget_tokens must be an integer",
            ),
        )

        for latest_start_token_budget_hint, expected_error in cases:
            with self.subTest(latest_start_token_budget_hint=latest_start_token_budget_hint):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    db_path = work / ".zerker" / "memory.sqlite"
                    store = MemoryStore(db_path)
                    store.init()
                    store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary="start before raw snapshot verify malformed latest start token budget hint",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][
                        "latest_start_token_budget_hint"
                    ] = latest_start_token_budget_hint
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertIn("Memory snapshot verify", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(f"Session continuity error: invalid continuity sidecar: {expected_error}", summary)
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_unknown_session_retention_state_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify unknown retention state",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify unknown retention state",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["sessions"][0]["retention_state"] = "archived"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].retention_state must be one of "
            "[all_available, mixed, soft_deleted_only]",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_unknown_session_payload_status_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify unknown payload status",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify unknown payload status",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["sessions"][0]["latest_payload_status"] = "archived"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].latest_payload_status must be one of "
            "[available, soft_deleted]",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_session_payload_status_counts_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify incoherent payload status counts",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify incoherent payload status counts",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "available"
            session["available_payload_count"] = 0
            session["soft_deleted_payload_count"] = 1
            session["retention_state"] = "soft_deleted_only"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 0,
                "soft_deleted": 1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 0,
                "mixed": 0,
                "soft_deleted_only": 1,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].latest_payload_status=available requires available_payload_count > 0",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_incoherent_session_retention_state_counts_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify incoherent retention state counts",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify incoherent retention state counts",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "soft_deleted"
            session["available_payload_count"] = 0
            session["soft_deleted_payload_count"] = 1
            session["retention_state"] = "all_available"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 0,
                "soft_deleted": 1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 1,
                "mixed": 0,
                "soft_deleted_only": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].retention_state=all_available must match "
            "available_payload_count=0 and soft_deleted_payload_count=1 (expected soft_deleted_only)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_zero_payload_session_row_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify zero-payload session row",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify zero-payload session row",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "available"
            session["available_payload_count"] = 0
            session["soft_deleted_payload_count"] = 0
            session["retention_state"] = "all_available"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 0,
                "soft_deleted": 0,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 1,
                "mixed": 0,
                "soft_deleted_only": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*] must report at least one available or soft_deleted payload",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_available_payload_count_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative available payload count",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify negative available payload count",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "soft_deleted"
            session["available_payload_count"] = -1
            session["soft_deleted_payload_count"] = 1
            session["retention_state"] = "soft_deleted_only"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": -1,
                "soft_deleted": 1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 0,
                "mixed": 0,
                "soft_deleted_only": 1,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].available_payload_count must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_soft_deleted_payload_count_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative soft-deleted payload count",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify negative soft-deleted payload count",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "available"
            session["available_payload_count"] = 1
            session["soft_deleted_payload_count"] = -1
            session["retention_state"] = "all_available"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 1,
                "soft_deleted": -1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 1,
                "mixed": 0,
                "soft_deleted_only": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].soft_deleted_payload_count must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_available_payload_status_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative available payload-status total",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify negative available payload-status total",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": -1,
                "soft_deleted": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.payload_status_counts.available must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_reports_negative_soft_deleted_payload_status_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            store = MemoryStore(db_path)
            store.init()
            store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot verify negative soft-deleted payload-status total",
                context_budget_tokens=256,
            )
            store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot verify negative soft-deleted payload-status total",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "soft_deleted"
            session["available_payload_count"] = 0
            session["soft_deleted_payload_count"] = 1
            session["retention_state"] = "soft_deleted_only"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 0,
                "soft_deleted": -1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 0,
                "mixed": 0,
                "soft_deleted_only": 1,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.payload_status_counts.soft_deleted must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_snapshot_verify_summary_only_surfaces_verified_export_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path, treeship_auto_sign=True)
            store.init()
            signed_provenance = subprocess.CompletedProcess(
                args=["treeship"],
                returncode=0,
                stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
                stderr="",
            )
            signed_mutation = subprocess.CompletedProcess(
                args=["treeship"],
                returncode=0,
                stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
                stderr="",
            )
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run", side_effect=[signed_provenance, signed_mutation]):
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
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(store.snapshot()), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Memory snapshot verify", summary)
        self.assertIn(f"Snapshot: {snapshot_path}", summary)
        self.assertIn("Snapshot verify: ok", summary)
        self.assertIn("Write receipts: 2", summary)
        self.assertIn("Write receipt chains: 1", summary)
        self.assertIn("Write receipt verify: ok (2/2 verified)", summary)
        self.assertIn("Verified write transitions: 1", summary)
        self.assertIn("Provenance anchors: 1 verified", summary)
        self.assertIn(f"Provenance memory: {memory.id}", summary)
        self.assertIn("Provenance actor: codex", summary)
        self.assertIn(f"Provenance digest: sha256:{memory.content_hash}", summary)
        self.assertIn("Provenance roots:", summary)
        self.assertIn("Provenance Treeship artifact: art_write_1", summary)
        self.assertIn("Treeship artifacts: art_write_1, art_write_2", summary)
        self.assertIn("Trusted provenance: verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)

    def test_snapshot_verify_summary_only_explains_intervening_write_continuity(self):
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
            store.remember(
                "Unrelated runbook note",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
            )
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")
            snapshot_path = Path(tmp) / "snapshot.json"
            snapshot_path.write_text(json.dumps(store.snapshot()), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "snapshot", "verify", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Snapshot verify: ok", summary)
        self.assertIn("Write receipt verify: ok (3/3 verified)", summary)
        self.assertIn("Verified write transitions: 1", summary)
        self.assertIn("Intervening events: 1", summary)
        self.assertIn("Intervening other-memory events: 1", summary)
        self.assertIn("Continuity basis: prior receipt link plus snapshot previous event root", summary)
        self.assertIn("Trusted provenance: verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)

    def test_restore_snapshot_summary_only_surfaces_adjacent_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore",
                context_budget_tokens=256,
            )
            session_snapshot = source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore",
            )
            source_store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="reviewer",
                reason="retention compacted before raw snapshot restore",
            )
            source_store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="end before raw snapshot restore",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            db_path = work / ".zerker" / "restored.sqlite"

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Source: {snapshot_path.resolve()}", summary)
        self.assertIn(f"Snapshot: {snapshot_path.resolve()}", summary)
        self.assertIn(f"Session continuity sidecar: {snapshot_path.with_suffix('.continuity.json').resolve()}", summary)
        self.assertIn("Session continuity verify: ok", summary)
        self.assertIn("Lifecycle sessions: 1", summary)
        self.assertIn("Lifecycle events: starts=1 checkpoints=0 snapshots=1 snapshot_soft_deletes=1 ends=1", summary)
        self.assertIn("Retention sessions: 1", summary)
        self.assertIn("Retention states: all_available=0 mixed=0 soft_deleted_only=1", summary)
        self.assertIn("Latest lifecycle retention: retention compacted before raw snapshot restore", summary)
        self.assertNotIn("Session continuity: none", summary)

    def test_restore_snapshot_file_writes_local_workspace_restore_continuity_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore",
            )
            source_store.end_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="end before raw snapshot restore",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            with redirect_stdout(io.StringIO()):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])
            db_path = work / ".zerker" / "restored.sqlite"
            restored_store = MemoryStore(db_path)

            result = restore_snapshot_file(restored_store, snapshot_path=snapshot_path)

            anchor = result["workspace_restore_continuity"]
            anchor_path = Path(anchor["path"])
            anchor_exists = anchor_path.exists()
            anchor_payload = json.loads(anchor_path.read_text(encoding="utf-8"))
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(export_exit_code, 0)
        self.assertTrue(anchor_exists)
        self.assertEqual(anchor_payload["schema"], "zerker.workspace_restore_continuity.v1")
        self.assertEqual(anchor_payload["kind"], "local_snapshot_restore")
        self.assertEqual(anchor_payload["snapshot_path"], str(snapshot_path.resolve()))
        self.assertEqual(anchor_payload["snapshot_hash"], snapshot_payload["snapshot_hash"])
        self.assertEqual(anchor_payload["snapshot_merkle_root"], snapshot_payload["merkle_root"])
        self.assertEqual(anchor_payload["restore_receipt_id"], result["restore"]["receipt"]["receipt_id"])
        self.assertEqual(anchor_payload["restore_receipt_hash"], result["restore"]["receipt"]["receipt_hash"])
        self.assertEqual(anchor_payload["restore_actor_uri"], "actor://snapshot_restore")
        self.assertEqual(
            anchor_payload["continuity_sidecar_path"],
            str(snapshot_path.with_suffix(".continuity.json").resolve()),
        )
        self.assertTrue(anchor_payload["continuity_sidecar_ok"])

    def test_restore_snapshot_summary_only_reports_mismatched_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore mismatch",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["snapshot_merkle_root"] = "root://copied-sidecar"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn("Session continuity error: continuity sidecar snapshot Merkle root mismatch", summary)

    def test_restore_snapshot_summary_only_reports_invalid_retention_rollup_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore invalid sidecar",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"] = []
            continuity_payload["session_retention_rollup_summary"] = "bad sidecar"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn("Session continuity error: invalid continuity sidecar: session_retention_rollup must be an object", summary)
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_invalid_retention_rollup_session_entry_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore malformed retention entry",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["sessions"] = ["bad-entry"]
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_retention_rollup.sessions[0] must be an object",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_retention_rollup_count_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore incoherent retention count",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore incoherent retention count",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["count"] = 42
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_retention_rollup.count must equal sessions length (42 != 1)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_lifecycle_event_totals_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore incoherent lifecycle events",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_lifecycle_rollup"]["event_kind_counts"]["start"] = 0
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_lifecycle_rollup.event_kind_counts.start must equal summed session start_count (0 != 1)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_retention_payload_totals_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore incoherent retention payload totals",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore incoherent retention payload totals",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["payload_status_counts"]["available"] = 0
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_retention_rollup.payload_status_counts.available must equal summed session available_payload_count (0 != 1)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_retention_state_totals_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore incoherent retention states",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore incoherent retention states",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["all_available"] = 2
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: session_retention_rollup.retention_state_counts.all_available must equal counted session retention_state=all_available (2 != 1)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_retention_state_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative retention state total",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore negative retention state total",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["all_available"] = -1
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.retention_state_counts.all_available must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_mixed_retention_state_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative mixed retention state total",
                context_budget_tokens=256,
            )
            session_snapshot = source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore negative mixed retention state total",
            )
            source_store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="codex",
                reason="retention compacted before restore mixed total check",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["mixed"] = -1
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.retention_state_counts.mixed must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_soft_deleted_only_retention_state_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative soft-deleted-only retention state total",
                context_budget_tokens=256,
            )
            session_snapshot = source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore negative soft-deleted-only retention state total",
            )
            source_store.soft_delete_session_snapshot_payload(
                session_snapshot["session_snapshot_id"],
                actor_id="codex",
                reason="retention compacted before restore soft-deleted total check",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["retention_state_counts"]["soft_deleted_only"] = -1
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.retention_state_counts.soft_deleted_only must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_lifecycle_receipt_provenance_totals_in_session_continuity_sidecar(self):
        count_totals = {
            "verified_receipt_count": 1,
            "failed_receipt_count": 0,
            "linked_treeship_artifact_count": 0,
        }

        for count_field, session_total in count_totals.items():
            with self.subTest(count_field=count_field):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore incoherent {count_field}",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"][count_field] = 7
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.{count_field} must equal summed session {count_field} "
                    f"(7 != {session_total})",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_lifecycle_receipt_provenance_counts_in_session_continuity_sidecar(self):
        count_fields = (
            "verified_receipt_count",
            "failed_receipt_count",
            "linked_treeship_artifact_count",
        )

        for count_field in count_fields:
            with self.subTest(count_field=count_field):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore negative {count_field}",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"][count_field] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.{count_field} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_session_lifecycle_receipt_provenance_counts_in_session_continuity_sidecar(self):
        count_fields = (
            "verified_receipt_count",
            "failed_receipt_count",
            "linked_treeship_artifact_count",
        )

        for count_field in count_fields:
            with self.subTest(count_field=count_field):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore negative session {count_field}",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"][count_field] = 0
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][count_field] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].{count_field} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_latest_start_context_budget_hint_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative latest start context budget hint",
                context_budget_tokens=256,
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_start_token_budget_hint"] = {
                "context_budget_tokens": -1
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint.context_budget_tokens "
            "must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_malformed_latest_start_token_budget_hint_payloads_in_session_continuity_sidecar(self):
        cases = (
            (
                ["not", "an", "object"],
                "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint must be an object",
            ),
            (
                {"context_budget_tokens": "256"},
                "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint.context_budget_tokens must be an integer",
            ),
            (
                {"context_budget_tokens": True},
                "session_lifecycle_rollup.sessions[*].latest_start_token_budget_hint.context_budget_tokens must be an integer",
            ),
        )

        for latest_start_token_budget_hint, expected_error in cases:
            with self.subTest(latest_start_token_budget_hint=latest_start_token_budget_hint):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary="start before raw snapshot restore malformed latest start token budget hint",
                        context_budget_tokens=256,
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][
                        "latest_start_token_budget_hint"
                    ] = latest_start_token_budget_hint
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(f"Session continuity error: invalid continuity sidecar: {expected_error}", summary)
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_lifecycle_event_totals_in_session_continuity_sidecar(self):
        count_fields = {
            "start": "start_count",
            "checkpoint": "checkpoint_count",
            "snapshot": "snapshot_count",
            "snapshot_soft_delete": "snapshot_soft_delete_count",
            "end": "end_count",
        }

        for event_kind in count_fields:
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore negative {event_kind} lifecycle total",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore negative {event_kind} lifecycle total",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore negative {event_kind} lifecycle total",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore negative {event_kind} lifecycle total",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore negative {event_kind} lifecycle total",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["event_kind_counts"][event_kind] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.event_kind_counts.{event_kind} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_session_lifecycle_counts_in_session_continuity_sidecar(self):
        count_fields = {
            "start": "start_count",
            "checkpoint": "checkpoint_count",
            "snapshot": "snapshot_count",
            "snapshot_soft_delete": "snapshot_soft_delete_count",
            "end": "end_count",
        }

        for event_kind, session_field in count_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore negative session {event_kind} lifecycle count",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore negative session {event_kind} lifecycle count",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore negative session {event_kind} lifecycle count",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore negative session {event_kind} lifecycle count",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore negative session {event_kind} lifecycle count",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][session_field] = -1
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].{session_field} must be non-negative",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_session_latest_event_kind_in_session_continuity_sidecar(self):
        count_fields = {
            "start": "start_count",
            "checkpoint": "checkpoint_count",
            "snapshot": "snapshot_count",
            "snapshot_soft_delete": "snapshot_soft_delete_count",
            "end": "end_count",
        }

        for event_kind, session_field in count_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore incoherent latest {event_kind} lifecycle row",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore incoherent latest {event_kind} lifecycle row",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore incoherent latest {event_kind} lifecycle row",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore incoherent latest {event_kind} lifecycle row",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore incoherent latest {event_kind} lifecycle row",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][session_field] = 0
                    continuity_payload["session_lifecycle_rollup"]["event_kind_counts"][event_kind] = 0
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].latest_event_kind={event_kind} requires {session_field} > 0",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_missing_latest_event_identifier_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }

        for event_kind, identifier_field in identifier_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore missing latest {event_kind} identifier",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore missing latest {event_kind} identifier",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore missing latest {event_kind} identifier",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore missing latest {event_kind} identifier",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore missing latest {event_kind} identifier",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_field] = None
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].latest_event_kind={event_kind} "
                    f"requires {identifier_field}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_mismatched_latest_lifecycle_id_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }

        for event_kind, identifier_field in identifier_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore mismatched latest lifecycle id for {event_kind}",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore mismatched latest lifecycle id for {event_kind}",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore mismatched latest lifecycle id for {event_kind}",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore mismatched latest lifecycle id for {event_kind}",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore mismatched latest lifecycle id for {event_kind}",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_status_root"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][root_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        f"mismatched-{event_kind}-lifecycle-id"
                    )
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    "session_lifecycle_rollup.sessions[*].latest_lifecycle_id must equal "
                    f"{identifier_field} when latest_event_kind={event_kind}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_missing_latest_event_root_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }

        for event_kind, root_field in root_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore missing latest {event_kind} root",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore missing latest {event_kind} root",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore missing latest {event_kind} root",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore missing latest {event_kind} root",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore missing latest {event_kind} root",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0][root_field] = None
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    f"session_lifecycle_rollup.sessions[*].latest_event_kind={event_kind} "
                    f"requires {root_field}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_mismatched_latest_status_root_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }

        for event_kind, root_field in root_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore mismatched latest status root for {event_kind}",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore mismatched latest status root for {event_kind}",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore mismatched latest status root for {event_kind}",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore mismatched latest status root for {event_kind}",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore mismatched latest status root for {event_kind}",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_status_root"] = "sha256:mismatched-status-root"
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    "session_lifecycle_rollup.sessions[*].latest_status_root must equal "
                    f"{root_field} when latest_event_kind={event_kind}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_mismatched_latest_event_created_at_in_session_continuity_sidecar(self):
        identifier_fields = {
            "start": "latest_start_session_start_id",
            "checkpoint": "latest_checkpoint_id",
            "snapshot": "latest_session_snapshot_id",
            "snapshot_soft_delete": "latest_soft_deleted_session_snapshot_id",
            "end": "latest_session_end_id",
        }
        root_fields = {
            "start": "latest_start_root",
            "checkpoint": "latest_checkpoint_root",
            "snapshot": "latest_session_snapshot_root",
            "snapshot_soft_delete": "latest_soft_delete_root",
            "end": "latest_session_end_root",
        }
        created_at_fields = {
            "start": "latest_start_created_at",
            "checkpoint": "latest_checkpoint_created_at",
            "snapshot": "latest_session_snapshot_created_at",
            "snapshot_soft_delete": "latest_soft_deleted_deleted_at",
            "end": "latest_session_end_created_at",
        }

        for event_kind, created_at_field in created_at_fields.items():
            with self.subTest(event_kind=event_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    work = Path(tmp)
                    source_db_path = work / ".zerker" / "source.sqlite"
                    source_store = MemoryStore(source_db_path)
                    source_store.init()
                    source_store.remember(
                        "Production deploys require approval",
                        memory_type="policy",
                        scope="project:alpha",
                        source_kind="human",
                    )
                    source_store.start_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"start before raw snapshot restore mismatched latest event created_at for {event_kind}",
                        context_budget_tokens=256,
                    )
                    source_store.checkpoint_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"checkpoint before raw snapshot restore mismatched latest event created_at for {event_kind}",
                    )
                    session_snapshot = source_store.snapshot_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"snapshot before raw snapshot restore mismatched latest event created_at for {event_kind}",
                    )
                    source_store.soft_delete_session_snapshot_payload(
                        session_snapshot["session_snapshot_id"],
                        actor_id="codex",
                        reason=f"retention compacted before restore mismatched latest event created_at for {event_kind}",
                    )
                    source_store.end_session(
                        "session://alpha",
                        actor_id="codex",
                        scope="project:alpha",
                        summary=f"end before raw snapshot restore mismatched latest event created_at for {event_kind}",
                    )
                    snapshot_path = work / ".zerker" / "snapshot.json"
                    export_output = io.StringIO()
                    with redirect_stdout(export_output):
                        export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

                    continuity_path = snapshot_path.with_suffix(".continuity.json")
                    continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_kind"] = event_kind
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_lifecycle_id"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][identifier_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_status_root"] = (
                        continuity_payload["session_lifecycle_rollup"]["sessions"][0][root_fields[event_kind]]
                    )
                    continuity_payload["session_lifecycle_rollup"]["sessions"][0]["latest_event_created_at"] = (
                        f"mismatched-{event_kind}-created-at"
                    )
                    continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

                    db_path = work / ".zerker" / "restored.sqlite"
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

                    summary = output.getvalue()
                    restored_store = MemoryStore(db_path)

                self.assertEqual(export_exit_code, 0)
                self.assertEqual(exit_code, 0)
                self.assertEqual(restored_store.stats()["memory_count"], 1)
                self.assertIn("Zerker Memory restore", summary)
                self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
                self.assertIn("Session continuity verify: failed", summary)
                self.assertIn(
                    "Session continuity error: invalid continuity sidecar: "
                    "session_lifecycle_rollup.sessions[*].latest_event_created_at must equal "
                    f"{created_at_field} when latest_event_kind={event_kind}",
                    summary,
                )
                self.assertNotIn("Retention sessions:", summary)
                self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_unknown_session_retention_state_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore unknown retention state",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore unknown retention state",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["sessions"][0]["retention_state"] = "archived"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].retention_state must be one of "
            "[all_available, mixed, soft_deleted_only]",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_unknown_session_payload_status_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore unknown payload status",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore unknown payload status",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["sessions"][0]["latest_payload_status"] = "archived"
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].latest_payload_status must be one of "
            "[available, soft_deleted]",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_session_payload_status_counts_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore incoherent payload status counts",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore incoherent payload status counts",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "soft_deleted"
            session["available_payload_count"] = 1
            session["soft_deleted_payload_count"] = 0
            session["retention_state"] = "all_available"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 1,
                "soft_deleted": 0,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 1,
                "mixed": 0,
                "soft_deleted_only": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].latest_payload_status=soft_deleted requires soft_deleted_payload_count > 0",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_incoherent_session_retention_state_counts_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore incoherent retention state counts",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore incoherent retention state counts",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "available"
            session["available_payload_count"] = 1
            session["soft_deleted_payload_count"] = 0
            session["retention_state"] = "soft_deleted_only"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 1,
                "soft_deleted": 0,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 0,
                "mixed": 0,
                "soft_deleted_only": 1,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].retention_state=soft_deleted_only must match "
            "available_payload_count=1 and soft_deleted_payload_count=0 (expected all_available)",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_zero_payload_session_row_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore zero-payload session row",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore zero-payload session row",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "available"
            session["available_payload_count"] = 0
            session["soft_deleted_payload_count"] = 0
            session["retention_state"] = "all_available"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 0,
                "soft_deleted": 0,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 1,
                "mixed": 0,
                "soft_deleted_only": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*] must report at least one available or soft_deleted payload",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_available_payload_count_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative available payload count",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore negative available payload count",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "soft_deleted"
            session["available_payload_count"] = -1
            session["soft_deleted_payload_count"] = 1
            session["retention_state"] = "soft_deleted_only"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": -1,
                "soft_deleted": 1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 0,
                "mixed": 0,
                "soft_deleted_only": 1,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].available_payload_count must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_soft_deleted_payload_count_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative soft-deleted payload count",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore negative soft-deleted payload count",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "available"
            session["available_payload_count"] = 1
            session["soft_deleted_payload_count"] = -1
            session["retention_state"] = "all_available"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 1,
                "soft_deleted": -1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 1,
                "mixed": 0,
                "soft_deleted_only": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.sessions[*].soft_deleted_payload_count must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_available_payload_status_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative available payload-status total",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore negative available payload-status total",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": -1,
                "soft_deleted": 0,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.payload_status_counts.available must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_restore_snapshot_summary_only_reports_negative_soft_deleted_payload_status_total_in_session_continuity_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source_db_path = work / ".zerker" / "source.sqlite"
            source_store = MemoryStore(source_db_path)
            source_store.init()
            source_store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project:alpha",
                source_kind="human",
            )
            source_store.start_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="start before raw snapshot restore negative soft-deleted payload-status total",
                context_budget_tokens=256,
            )
            source_store.snapshot_session(
                "session://alpha",
                actor_id="codex",
                scope="project:alpha",
                summary="snapshot before raw snapshot restore negative soft-deleted payload-status total",
            )
            snapshot_path = work / ".zerker" / "snapshot.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                export_exit_code = main(["--db", str(source_db_path), "snapshot", "--out", str(snapshot_path)])

            continuity_path = snapshot_path.with_suffix(".continuity.json")
            continuity_payload = json.loads(continuity_path.read_text(encoding="utf-8"))
            session = continuity_payload["session_retention_rollup"]["sessions"][0]
            session["latest_payload_status"] = "soft_deleted"
            session["available_payload_count"] = 0
            session["soft_deleted_payload_count"] = 1
            session["retention_state"] = "soft_deleted_only"
            continuity_payload["session_retention_rollup"]["payload_status_counts"] = {
                "available": 0,
                "soft_deleted": -1,
            }
            continuity_payload["session_retention_rollup"]["retention_state_counts"] = {
                "all_available": 0,
                "mixed": 0,
                "soft_deleted_only": 1,
            }
            continuity_path.write_text(json.dumps(continuity_payload, indent=2), encoding="utf-8")

            db_path = work / ".zerker" / "restored.sqlite"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "restore", str(snapshot_path), "--summary-only"])

            summary = output.getvalue()
            restored_store = MemoryStore(db_path)

        self.assertEqual(export_exit_code, 0)
        self.assertEqual(exit_code, 0)
        self.assertEqual(restored_store.stats()["memory_count"], 1)
        self.assertIn("Zerker Memory restore", summary)
        self.assertIn(f"Session continuity sidecar: {continuity_path.resolve()}", summary)
        self.assertIn("Session continuity verify: failed", summary)
        self.assertIn(
            "Session continuity error: invalid continuity sidecar: "
            "session_retention_rollup.payload_status_counts.soft_deleted must be non-negative",
            summary,
        )
        self.assertNotIn("Retention sessions:", summary)
        self.assertNotIn("Lifecycle sessions:", summary)

    def test_lineage_summary_only_surfaces_verified_write_receipt_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path, treeship_auto_sign=True)
            store.init()
            signed_provenance = subprocess.CompletedProcess(
                args=["treeship"],
                returncode=0,
                stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
                stderr="",
            )
            signed_mutation = subprocess.CompletedProcess(
                args=["treeship"],
                returncode=0,
                stdout='{"id":"art_write_2","kind":"memory.write","signed":"2026-06-24T05:27:54Z","status":"ok","system":"system://zmem"}',
                stderr="",
            )
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run", side_effect=[signed_provenance, signed_mutation]):
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

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "lineage", memory.id, "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Memory lineage", summary)
        self.assertIn(f"Memory id: {memory.id}", summary)
        self.assertIn(f"Content digest: sha256:{memory.content_hash}", summary)
        self.assertIn("Write receipt chain verify: ok", summary)
        self.assertIn("Verified transitions: 1", summary)
        self.assertIn("Treeship artifacts: art_write_1, art_write_2", summary)
        self.assertIn("agent://codex/session-a", summary)
        self.assertIn("actor=actor://reviewer", summary)
        self.assertIn("Trusted provenance: verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)

    def test_lineage_summary_only_explains_intervening_write_continuity(self):
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
            store.remember(
                "Unrelated runbook note",
                memory_type="semantic",
                scope="project",
                source_kind="agent",
                actor_id="codex",
            )
            store.reject(memory.id, actor_id="reviewer", reason="superseded runbook")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "lineage", memory.id, "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Write receipt chain verify: ok", summary)
        self.assertIn("Continuity basis: prior receipt link + live previous event root", summary)
        self.assertIn("Intervening events: 1", summary)
        self.assertIn("Intervening other-memory events: 1", summary)
        self.assertIn("Trusted provenance: verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)

    def test_bundle_verify_summary_only_surfaces_verified_supporting_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path, treeship_auto_sign=True)
            store.init()
            signed_provenance = subprocess.CompletedProcess(
                args=["treeship"],
                returncode=0,
                stdout='{"id":"art_write_1","kind":"memory.write","signed":"2026-06-24T05:27:53Z","status":"ok","system":"system://zmem"}',
                stderr="",
            )
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with patch("zerker_memory.treeship.subprocess.run", return_value=signed_provenance):
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
            bundle_path = Path(tmp) / "receipt.bundle.json"
            bundle_path.write_text(json.dumps(store.receipt_bundle(receipt["action_id"])), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "bundle", "verify", str(bundle_path), "--summary-only"])

            summary = output.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Receipt bundle verify", summary)
        self.assertIn(f"Bundle: {bundle_path.resolve()}", summary)
        self.assertIn(f"Action id: {receipt['action_id']}", summary)
        self.assertIn("Bundle verify: ok", summary)
        self.assertIn("Supporting memories: 1", summary)
        self.assertIn("Schema: zerker.receipt_bundle.v2", summary)
        self.assertIn("Event log entries: 1", summary)
        self.assertIn("Event witnesses: 1", summary)
        self.assertIn("Supporting write receipts: 1", summary)
        self.assertIn("Supporting provenance verify: ok", summary)
        self.assertIn("Memory tree verify: ok", summary)
        self.assertIn("Treeship artifacts: art_write_1", summary)
        self.assertIn("Provenance memory:", summary)
        self.assertIn("Provenance actor: codex", summary)
        self.assertIn("Provenance digest:", summary)
        self.assertIn("Provenance roots:", summary)
        self.assertIn("Provenance Treeship artifact: art_write_1", summary)
        self.assertIn("Trusted provenance: verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)

    def test_run_prelaunch_check_flags_public_url_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_prelaunch_fixture(root, readme="https://github.com/zerker-memory/zerker-memory")
            install_path = root / "install.sh"
            install_path.write_text(
                install_path.read_text(encoding="utf-8").replace(
                    "zmem status --summary-only",
                    "https://github.com/zerker-memory/zerker-memory.git\nzmem status --summary-only",
                ),
                encoding="utf-8",
            )
            handoff_dir = root / ".zerker" / "handoff" / "exports"
            handoff_dir.mkdir(parents=True, exist_ok=True)
            (root / ".zerker" / "handoff" / "README.md").write_text("ready\n", encoding="utf-8")
            (handoff_dir / "handoff.snapshot.json").write_text("{}", encoding="utf-8")
            (handoff_dir / "handoff.bundle.json").write_text("{}", encoding="utf-8")
            (handoff_dir / "handoff.treeship.json").write_text("{}", encoding="utf-8")

            result = run_prelaunch_check(cwd=root, require_launch_proof=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["blockers"][0]["name"], "public_urls")
        self.assertIn("install.sh", result["blockers"][0]["details"])
        self.assertIn("Choose the final GitHub owner/repo", result["next_steps"][0])

    def test_run_prelaunch_check_allows_local_alpha_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_prelaunch_fixture(root, readme="https://github.com/zerker-memory/zerker-memory")
            install_path = root / "install.sh"
            install_path.write_text(
                install_path.read_text(encoding="utf-8").replace(
                    "zmem status --summary-only",
                    "https://github.com/zerker-memory/zerker-memory.git\nzmem status --summary-only",
                ),
                encoding="utf-8",
            )
            handoff_dir = root / ".zerker" / "handoff" / "exports"
            handoff_dir.mkdir(parents=True, exist_ok=True)
            (root / ".zerker" / "handoff" / "README.md").write_text("ready\n", encoding="utf-8")
            (handoff_dir / "handoff.snapshot.json").write_text("{}", encoding="utf-8")
            (handoff_dir / "handoff.bundle.json").write_text("{}", encoding="utf-8")
            (handoff_dir / "handoff.treeship.json").write_text("{}", encoding="utf-8")

            result = run_prelaunch_check(cwd=root, allow_placeholders=True, require_launch_proof=False)
            summary = render_prelaunch_summary(result)

        self.assertTrue(result["ok"])
        self.assertIn("public_urls", {warning["name"] for warning in result["warnings"]})
        self.assertIn("launch_assets", {warning["name"] for warning in result["warnings"]})
        self.assertIn("public_verify_evidence", {warning["name"] for warning in result["warnings"]})
        self.assertIn("Ready to publish: yes", summary)
        self.assertIn("public_urls: warning", summary)
        self.assertIn("launch_assets: warning", summary)

    def test_run_prelaunch_check_requires_public_verify_evidence_for_strict_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_prelaunch_fixture(root)
            handoff_dir = root / ".zerker" / "handoff" / "exports"
            handoff_dir.mkdir(parents=True, exist_ok=True)
            (root / ".zerker" / "handoff" / "README.md").write_text("ready\n", encoding="utf-8")
            (handoff_dir / "handoff.snapshot.json").write_text("{}", encoding="utf-8")
            (handoff_dir / "handoff.bundle.json").write_text("{}", encoding="utf-8")
            (handoff_dir / "handoff.treeship.json").write_text("{}", encoding="utf-8")
            launch_dir = root / ".zerker" / "launch-proof"
            launch_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "schema": "zerker.launch_proof_manifest.v1",
                "public_verify": {"expected_log_files": PUBLIC_VERIFY_LOG_FILENAMES},
                "launch_assets": [],
            }
            (launch_dir / "launch-proof.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = run_prelaunch_check(cwd=root, require_launch_proof=False)

        self.assertFalse(result["ok"])
        blocker_names = {check["name"] for check in result["blockers"]}
        self.assertIn("public_verify_evidence", blocker_names)
        self.assertIn("launch_assets", blocker_names)
        public_verify_blocker = next(check for check in result["blockers"] if check["name"] == "public_verify_evidence")
        launch_assets_blocker = next(check for check in result["blockers"] if check["name"] == "launch_assets")
        self.assertIn(".zerker/launch-proof/public-verify-logs", public_verify_blocker["details"])
        self.assertIn(".zerker/launch-proof/assets", launch_assets_blocker["details"])

    def test_run_prelaunch_check_requires_handoff_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_prelaunch_fixture(root)

            result = run_prelaunch_check(cwd=root, require_launch_proof=False)

        self.assertFalse(result["ok"])
        self.assertIn("handoff_artifacts", {check["name"] for check in result["blockers"]})
        self.assertIn("zmem handoff --summary-only", result["next_steps"][0])

    def test_run_prelaunch_check_suggests_release_pack_when_both_artifact_sets_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_prelaunch_fixture(root)

            result = run_prelaunch_check(cwd=root)

        self.assertFalse(result["ok"])
        self.assertIn("zmem release-pack --summary-only", result["next_steps"][0])

    def test_run_prelaunch_check_requires_treeship_handoff_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_prelaunch_fixture(root)
            handoff_dir = root / ".zerker" / "handoff" / "exports"
            handoff_dir.mkdir(parents=True, exist_ok=True)
            (root / ".zerker" / "handoff" / "README.md").write_text("ready\n", encoding="utf-8")
            (handoff_dir / "handoff.snapshot.json").write_text("{}", encoding="utf-8")
            (handoff_dir / "handoff.bundle.json").write_text("{}", encoding="utf-8")

            result = run_prelaunch_check(cwd=root, require_launch_proof=False)

        self.assertFalse(result["ok"])
        handoff_blocker = next(check for check in result["blockers"] if check["name"] == "handoff_artifacts")
        self.assertIn(".zerker/handoff/exports/*.treeship.json", handoff_blocker["details"])

    def _write_prelaunch_fixture(self, root: Path, *, readme: str = "ready") -> None:
        for relative_path in (
            "QUICKSTART.md",
            "LICENSE",
            "install.sh",
            "scripts/release_smoke.py",
            "scripts/launch_proof.sh",
            "docs/PUBLIC_LAUNCH_AUDIT.md",
            "docs/GITHUB_RELEASE_CHECKLIST.md",
            "docs/PRODUCT_STATUS.md",
            ".github/workflows/test.yml",
        ):
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("zmem status --summary-only\n", encoding="utf-8")
        (root / "README.md").write_text(readme, encoding="utf-8")
        (root / ".gitignore").write_text(".zerker/\n.venv/\n*.sqlite\n*.egg-info/\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            "\n".join(
                [
                    "[project.scripts]",
                    'zmem = "zerker_memory.cli:main"',
                    'zerker-memory = "zerker_memory.cli:main"',
                    'zerker = "zerker_memory.cli:main"',
                    'zerker-memory-mcp = "zerker_memory.mcp:main"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_public_verify_status_tracks_missing_and_present_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch_dir = root / ".zerker" / "launch-proof"
            logs_dir = launch_dir / "public-verify-logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "schema": "zerker.launch_proof_manifest.v1",
                "public_verify": {"expected_log_files": PUBLIC_VERIFY_LOG_FILENAMES},
            }
            (launch_dir / "launch-proof.json").write_text(json.dumps(manifest), encoding="utf-8")

            pending = public_verify_status(root)
            for name in PUBLIC_VERIFY_LOG_FILENAMES:
                (logs_dir / name).write_text("ok\n", encoding="utf-8")
            still_pending = public_verify_status(root)
            (launch_dir / "public-verify-result.json").write_text(
                json.dumps(
                    {
                        "schema": "zerker.public_verify_result.v1",
                        "ok": True,
                        "exit_code": 0,
                        "details": "public verify ok",
                        "failed_steps": [],
                        "steps": [],
                    }
                ),
                encoding="utf-8",
            )
            ready = public_verify_status(root)

        self.assertFalse(pending["ready"])
        self.assertIn("0/6 logs captured", pending["details"])
        self.assertFalse(still_pending["ready"])
        self.assertIn("result pending", still_pending["details"])
        self.assertTrue(ready["ready"])
        self.assertIn("6/6 logs captured", ready["details"])
        self.assertIn("public verify ok", ready["details"])

    def test_public_verify_status_surfaces_last_attempt_receipt_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch_dir = root / ".zerker" / "launch-proof"
            logs_dir = launch_dir / "public-verify-logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "schema": "zerker.launch_proof_manifest.v1",
                "public_verify": {"expected_log_files": PUBLIC_VERIFY_LOG_FILENAMES},
            }
            (launch_dir / "launch-proof.json").write_text(json.dumps(manifest), encoding="utf-8")
            (launch_dir / "public-verify-result.json").write_text(
                json.dumps(
                    {
                        "schema": "zerker.public_verify_result.v1",
                        "status": "failed",
                        "ok": False,
                        "exit_code": 1,
                        "details": "public verify failed",
                        "failed_steps": ["packaged-release-smoke"],
                        "install_mode_requirement": "packaged",
                        "install_mode": "local-wrappers",
                    }
                ),
                encoding="utf-8",
            )

            result = public_verify_status(root)

        self.assertFalse(result["ready"])
        self.assertIn("missing operator-packet-verify.log, curl-install.log", result["details"])
        self.assertIn("last receipt: public verify failed; failed packaged-release-smoke", result["details"])
        self.assertIn("install_mode local-wrappers", result["details"])

    def test_extract_release_smoke_install_mode_reads_json_or_failure_message(self):
        json_log = '{\n  "schema": "zerker.release_smoke.v1",\n  "install_mode": "editable-no-build-isolation"\n}\n'
        self.assertEqual(extract_release_smoke_install_mode(json_log), "editable-no-build-isolation")
        failure_log = "release smoke used install_mode=local-wrappers, which does not satisfy --require-install-mode packaged\n"
        self.assertEqual(extract_release_smoke_install_mode(failure_log), "local-wrappers")

    def test_install_mode_satisfies_packaged_requirement_for_venv_pth(self):
        self.assertTrue(install_mode_satisfies_requirement("venv-pth", "packaged"))

    def test_return_packet_status_requires_complete_archive_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch_dir = root / ".zerker" / "launch-proof"
            logs_dir = launch_dir / "public-verify-logs"
            assets_dir = launch_dir / "assets"
            logs_dir.mkdir(parents=True, exist_ok=True)
            assets_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "schema": "zerker.launch_proof_manifest.v1",
                "return_packet_archive_path": "public-verify-return-packet.tar.gz",
                "return_packet": {
                    "manifest_path": "launch-proof.json",
                    "public_verify_logs_dir_path": "public-verify-logs",
                    "public_verify_result_path": "public-verify-result.json",
                    "launch_assets_dir_path": "assets",
                    "archive_path": "public-verify-return-packet.tar.gz",
                },
                "public_verify": {
                    "expected_log_files": PUBLIC_VERIFY_LOG_FILENAMES,
                    "result_path": "public-verify-result.json",
                },
                "launch_assets": [
                    {"id": "install-status", "deliverable": "install-status.png", "output_path": "assets/install-status.png"},
                    {"id": "ui-release-pack", "deliverable": "ui-release-pack.gif", "output_path": "assets/ui-release-pack.gif"},
                ],
            }
            (launch_dir / "launch-proof.json").write_text(json.dumps(manifest), encoding="utf-8")
            pending = return_packet_status(root)

            for name in PUBLIC_VERIFY_LOG_FILENAMES:
                (logs_dir / name).write_text("ok\n", encoding="utf-8")
            (launch_dir / "public-verify-result.json").write_text(
                json.dumps(
                    {
                        "schema": "zerker.public_verify_result.v1",
                        "ok": True,
                        "exit_code": 0,
                        "details": "public verify ok",
                        "failed_steps": [],
                        "steps": [],
                    }
                ),
                encoding="utf-8",
            )
            (launch_dir / "public-verify-summary.md").write_text("summary\n", encoding="utf-8")
            (assets_dir / "install-status.png").write_text("png\n", encoding="utf-8")
            (assets_dir / "ui-release-pack.gif").write_text("gif\n", encoding="utf-8")
            stale_archive_path = launch_dir / "public-verify-return-packet.tar.gz"
            with tarfile.open(stale_archive_path, "w:gz") as archive:
                archive.add(launch_dir / "launch-proof.json", arcname="launch-proof.json")
                archive.add(logs_dir, arcname="public-verify-logs")
                archive.add(launch_dir / "public-verify-result.json", arcname="public-verify-result.json")
                archive.add(launch_dir / "public-verify-summary.md", arcname="public-verify-summary.md")
                archive.add(assets_dir / "install-status.png", arcname="assets/install-status.png")
            stale = return_packet_status(root)

            with tarfile.open(stale_archive_path, "w:gz") as archive:
                archive.add(launch_dir / "launch-proof.json", arcname="launch-proof.json")
                archive.add(logs_dir, arcname="public-verify-logs")
                archive.add(launch_dir / "public-verify-result.json", arcname="public-verify-result.json")
                archive.add(launch_dir / "public-verify-summary.md", arcname="public-verify-summary.md")
                archive.add(assets_dir, arcname="assets")
            ready = return_packet_status(root)

        self.assertFalse(pending["ready"])
        self.assertIn("archive pending", pending["details"])
        self.assertFalse(stale["ready"])
        self.assertIn("archive stale", stale["details"])
        self.assertIn("ui-release-pack.gif", stale["details"])
        self.assertTrue(ready["ready"])
        self.assertIn("archive ready", ready["details"])

    def test_parse_agent_config_specs(self):
        specs = parse_agent_config_specs(["openclaw=/tmp/openclaw.json", "hermes=/tmp/hermes.json"])

        self.assertEqual(specs["openclaw"], Path("/tmp/openclaw.json"))
        self.assertEqual(specs["hermes"], Path("/tmp/hermes.json"))

    def test_agent_smoke_creates_verifiable_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")

            result = run_agent_smoke(store, agent_id="codex", scope="project", task="use Zerker Memory as the durable memory source")

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], "zerker.agent_smoke.v1")
        self.assertEqual(result["agent"], "codex")
        self.assertEqual(len(result["injected_memory_ids"]), 1)
        self.assertTrue(result["action_id"].startswith("act_"))

    def test_build_status_report_surfaces_missing_workspace_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=root / ".zerker" / "policy.json")
            result = build_status_report(
                store,
                providers_path=root / ".zerker" / "providers.json",
                include_eval=False,
                cwd=root,
            )

        self.assertEqual(result["schema"], "zerker.status.v1")
        self.assertFalse(result["workspace_ready"])
        self.assertFalse(result["proof_ready"])
        self.assertIn("zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config", result["next_steps"])
        self.assertIn("zmem eval", result["next_steps"])
        self.assertIn("zmem agent pack --summary-only", result["next_steps"])

    def test_build_status_report_marks_ready_workspace_and_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=root / ".zerker" / "policy.json")
            os.chdir(root)
            try:
                store.init()
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_agent_prompt_template(root / ".zerker" / "AGENT_PROMPT.md", force=False)
                write_json_file(root / ".zerker" / "mcp.json", {"mcpServers": {}}, force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)
                create_manual_agent_pack(
                    name="zerker-memory",
                    command="zmem",
                    db_path=store.db_path,
                    policy_path=store.policy_path,
                    force=False,
                )
                run_agent_smoke(store, agent_id="codex", scope="project", task="prove governed memory")

                result = build_status_report(
                    store,
                    providers_path=root / ".zerker" / "providers.json",
                    include_eval=False,
                    cwd=root,
                )
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["workspace_ready"])
        self.assertTrue(result["proof_ready"])
        self.assertTrue(result["manual_pack_ready"])
        self.assertEqual(result["latest_receipt"]["agent_id"], "codex")
        self.assertEqual(result["next_steps"][0], "zmem ui")

    def test_build_status_report_surfaces_release_refresh_steps_when_repo_surface_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=root / ".zerker" / "policy.json")
            os.chdir(root)
            try:
                store.init()
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_agent_prompt_template(root / ".zerker" / "AGENT_PROMPT.md", force=False)
                write_json_file(root / ".zerker" / "mcp.json", {"mcpServers": {}}, force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)
                create_manual_agent_pack(
                    name="zerker-memory",
                    command="zmem",
                    db_path=store.db_path,
                    policy_path=store.policy_path,
                    force=False,
                )
                run_agent_smoke(store, agent_id="codex", scope="project", task="prove governed memory")
                self._write_prelaunch_fixture(root)

                result = build_status_report(
                    store,
                    providers_path=root / ".zerker" / "providers.json",
                    include_eval=False,
                    cwd=root,
                )
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["release_readiness"]["repo_surface_present"])
        self.assertFalse(result["release_readiness"]["launch_proof_ready"])
        self.assertFalse(result["release_readiness"]["handoff_ready"])
        self.assertFalse(result["release_readiness"]["public_verify_ready"])
        self.assertFalse(result["release_readiness"]["launch_assets_ready"])
        self.assertIn("zmem release-pack --summary-only", result["next_steps"])

    def test_build_status_report_prefers_configured_manual_agent_for_next_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=root / ".zerker" / "policy.json")
            os.chdir(root)
            try:
                store.init()
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_agent_prompt_template(root / ".zerker" / "AGENT_PROMPT.md", force=False)
                write_json_file(root / ".zerker" / "mcp.json", {"mcpServers": {}}, force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)
                install_agent_preset(
                    "openclaw",
                    name="zerker-memory",
                    command="zmem",
                    db_path=store.db_path,
                    policy_path=store.policy_path,
                    force=False,
                )
                run_agent_smoke(store, agent_id="openclaw", scope="project", task="prove manual-target onboarding")

                result = build_status_report(
                    store,
                    providers_path=root / ".zerker" / "providers.json",
                    include_eval=False,
                    cwd=root,
                )
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(
            result["next_steps"],
            [
                "zmem agent pack --summary-only",
                "zmem ui",
                "zmem agent smoke --agent openclaw",
                "zmem agent mcp-smoke --agent openclaw",
            ],
        )

    def test_render_status_summary_includes_workspace_and_agent_pack(self):
        result = {
            "workspace_ready": True,
            "doctor_ok": True,
            "doctor_blockers": [],
            "proof_ready": False,
            "manual_pack_ready": False,
            "workspace": {
                "db_path": ".zerker/memory.sqlite",
                "policy_path": ".zerker/policy.json",
                "prompt_path": ".zerker/AGENT_PROMPT.md",
                "mcp_config_path": ".zerker/mcp.json",
                "providers_path": ".zerker/providers.json",
                "checks": {
                    "db": True,
                    "policy": True,
                    "prompt": True,
                    "mcp_config": False,
                    "providers": False,
                },
            },
            "stats": {
                "memory_count": 1,
                "receipt_count": 0,
                "event_count": 1,
                "merkle_root": "abc123",
            },
            "latest_receipt": None,
            "agents": {
                "codex": {"configured": False, "config_path": "~/.codex/config.toml"},
                "claude-code": {"configured": False, "config_path": "~/.claude/mcp.json"},
                "openclaw": {
                    "configured": True,
                    "config_path": ".zerker/agents/openclaw-mcp.json",
                    "checklist_present": True,
                    "checklist_path": ".zerker/agents/openclaw-checklist.md",
                },
                "hermes": {
                    "configured": True,
                    "config_path": ".zerker/agents/hermes-mcp.json",
                    "checklist_present": True,
                    "checklist_path": ".zerker/agents/hermes-checklist.md",
                },
                "generic": {
                    "configured": True,
                    "config_path": ".zerker/agents/generic-mcp.json",
                    "checklist_present": False,
                    "checklist_path": ".zerker/agents/generic-checklist.md",
                },
            },
            "manual_agent_pack": {
                "present": False,
                "path": ".zerker/agents/manual-agent-pack.md",
            },
            "next_steps": ["zmem eval", "zmem agent pack --summary-only"],
        }

        summary = render_status_summary(result)

        self.assertIn("Zerker Memory status", summary)
        self.assertIn("Workspace ready: yes", summary)
        self.assertIn("Memory proof ready: no", summary)
        self.assertIn("Manual pack: missing (.zerker/agents/manual-agent-pack.md)", summary)
        self.assertIn("zmem agent pack --summary-only", summary)

    def test_render_status_summary_includes_release_readiness_when_repo_surface_exists(self):
        summary = render_status_summary(
            {
                "workspace_ready": True,
                "doctor_ok": True,
                "doctor_blockers": [],
                "proof_ready": True,
                "manual_pack_ready": True,
                "workspace": {
                    "db_path": ".zerker/memory.sqlite",
                    "policy_path": ".zerker/policy.json",
                    "prompt_path": ".zerker/AGENT_PROMPT.md",
                    "mcp_config_path": ".zerker/mcp.json",
                    "providers_path": ".zerker/providers.json",
                    "checks": {"db": True, "policy": True, "prompt": True, "mcp_config": True, "providers": True},
                },
                "stats": {"memory_count": 1, "receipt_count": 1, "event_count": 2, "merkle_root": "abc123"},
                "latest_receipt": {"action_id": "act_123"},
                "agents": {
                    "codex": {"configured": False, "config_path": "~/.codex/config.toml"},
                    "claude-code": {"configured": False, "config_path": "~/.claude/mcp.json"},
                    "openclaw": {"configured": True, "config_path": "a", "checklist_present": True, "checklist_path": "b"},
                    "hermes": {"configured": True, "config_path": "c", "checklist_present": True, "checklist_path": "d"},
                    "generic": {"configured": True, "config_path": "e", "checklist_present": True, "checklist_path": "f"},
                },
                "manual_agent_pack": {"present": True, "path": ".zerker/agents/manual-agent-pack.md"},
                "release_readiness": {
                    "repo_surface_present": True,
                    "launch_proof_ready": False,
                    "handoff_ready": True,
                    "capture_checklist_path": ".zerker/launch-proof/CAPTURE_CHECKLIST.md",
                    "launch_asset_handoff_path": ".zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md",
                    "public_verify_handoff_path": ".zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md",
                    "receive_verify_handoff_path": ".zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md",
                    "public_verify_checklist_path": ".zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md",
                    "public_verify_script_path": ".zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh",
                    "operator_packet_ready": True,
                    "operator_packet_details": "archive ready at .zerker/launch-proof/public-verify-operator-packet.tar.gz (16/16 files packed)",
                    "operator_packet_archive_path": ".zerker/launch-proof/public-verify-operator-packet.tar.gz",
                    "public_verify_ready": False,
                    "public_verify_details": "0/6 logs captured in .zerker/launch-proof/public-verify-logs; missing operator-packet-verify.log, curl-install.log, first-run.log, ...",
                    "public_verify_logs_dir_path": ".zerker/launch-proof/public-verify-logs",
                    "public_verify_result_path": ".zerker/launch-proof/public-verify-result.json",
                    "public_verify_runbook_path": ".zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md",
                    "public_verify_operator_prompt_path": ".zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md",
                    "return_packet_finalize_script_path": ".zerker/launch-proof/FINALIZE_RETURN_PACKET.sh",
                    "launch_assets_ready": False,
                    "launch_assets_details": "0/8 captured in .zerker/launch-proof/assets; missing install-status.png",
                    "return_packet_ready": False,
                    "return_packet_details": "archive ok at .zerker/launch-proof/public-verify-return-packet.tar.gz; pending public verify evidence, launch assets",
                    "return_packet_archive_path": ".zerker/launch-proof/public-verify-return-packet.tar.gz",
                    "local_alpha_ready": False,
                    "local_alpha_blockers": [{"name": "launch_proof_artifacts", "ok": False, "details": "missing"}],
                    "local_alpha_warnings": [{"name": "public_urls", "ok": False, "details": "README.md"}],
                    "strict_publish_ready": False,
                    "strict_publish_blockers": [{"name": "public_urls", "ok": False, "details": "README.md"}],
                    "strict_publish_warnings": [{"name": "launch_assets", "ok": False, "details": "pending"}],
                },
                "next_steps": ["zmem release-pack --summary-only"],
            }
        )

        self.assertIn("Release:", summary)
        self.assertIn("Memory proof ready: yes", summary)
        self.assertIn("Release packet ready: no", summary)
        self.assertIn("Strict publish ready: no", summary)
        self.assertIn("Launch proof: missing", summary)
        self.assertIn("Handoff: ok", summary)
        self.assertIn("Public verify: pending", summary)
        self.assertIn("Launch assets: pending", summary)
        self.assertIn("Return packet: pending", summary)
        self.assertIn(
            "Release pack: run `zmem release-pack --summary-only` to generate the operator packet, runbook, checklists, and return archive.",
            summary,
        )
        self.assertNotIn("Capture checklist: .zerker/launch-proof/CAPTURE_CHECKLIST.md", summary)
        self.assertNotIn("Public verify script: .zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh", summary)
        self.assertNotIn("Operator packet archive: .zerker/launch-proof/public-verify-operator-packet.tar.gz", summary)
        self.assertIn("Local alpha gate: blocked (launch_proof_artifacts)", summary)
        self.assertIn("Strict publish gate: blocked (public_urls)", summary)
        self.assertIn("zmem release-pack --summary-only", summary)

    def test_render_status_summary_lists_doctor_blockers(self):
        summary = render_status_summary(
            {
                "workspace_ready": True,
                "doctor_ok": False,
                "doctor_blockers": [{"name": "python_version", "details": "3.9.6; Python >=3.10 required", "ok": False}],
                "proof_ready": True,
                "manual_pack_ready": True,
                "workspace": {
                    "db_path": ".zerker/memory.sqlite",
                    "policy_path": ".zerker/policy.json",
                    "prompt_path": ".zerker/AGENT_PROMPT.md",
                    "mcp_config_path": ".zerker/mcp.json",
                    "providers_path": ".zerker/providers.json",
                    "checks": {"db": True, "policy": True, "prompt": True, "mcp_config": True, "providers": True},
                },
                "stats": {"memory_count": 1, "receipt_count": 1, "event_count": 2, "merkle_root": "abc123"},
                "latest_receipt": {"action_id": "act_123"},
                "agents": {
                    "codex": {"configured": False, "config_path": "~/.codex/config.toml"},
                    "claude-code": {"configured": False, "config_path": "~/.claude/mcp.json"},
                    "openclaw": {"configured": True, "config_path": "a", "checklist_present": True, "checklist_path": "b"},
                    "hermes": {"configured": True, "config_path": "c", "checklist_present": True, "checklist_path": "d"},
                    "generic": {"configured": True, "config_path": "e", "checklist_present": True, "checklist_path": "f"},
                },
                "manual_agent_pack": {"present": True, "path": ".zerker/agents/manual-agent-pack.md"},
                "next_steps": ["zmem ui"],
            }
        )

        self.assertIn("Doctor blockers:", summary)
        self.assertIn("python_version: 3.9.6; Python >=3.10 required", summary)
        self.assertIn("bash install.sh", summary)

    def test_run_launch_proof_writes_transcript_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                self._write_prelaunch_fixture(root, readme="https://github.com/zerkerlabs/zmem")
                result = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(result["ok"])
            self.assertEqual(result["schema"], "zerker.launch_proof.v1")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            transcript = Path(result["transcript_path"]).read_text(encoding="utf-8")
            summary = Path(result["summary_path"]).read_text(encoding="utf-8")
            report = Path(result["report_path"]).read_text(encoding="utf-8")
            capture_checklist = Path(result["capture_checklist_path"]).read_text(encoding="utf-8")
            launch_asset_handoff = Path(result["launch_asset_handoff_path"]).read_text(encoding="utf-8")
            public_verify_checklist = Path(result["public_verify_checklist_path"]).read_text(encoding="utf-8")
            public_verify_handoff = Path(result["public_verify_handoff_path"]).read_text(encoding="utf-8")
            receive_verify_handoff = Path(result["receive_verify_handoff_path"]).read_text(encoding="utf-8")
            public_verify_script = Path(result["public_verify_script_path"]).read_text(encoding="utf-8")
            public_verify_runbook = Path(result["public_verify_runbook_path"]).read_text(encoding="utf-8")
            return_packet_finalize_script = Path(result["return_packet_finalize_script_path"]).read_text(encoding="utf-8")
            self.assertEqual(manifest["schema"], "zerker.launch_proof_manifest.v1")
            self.assertEqual(manifest["report_path"], "index.html")
            self.assertEqual(manifest["launch_asset_handoff_path"], "LAUNCH_ASSET_HANDOFF.md")
            self.assertEqual(manifest["public_verify_handoff_path"], "PUBLIC_VERIFY_HANDOFF.md")
            self.assertEqual(manifest["receive_verify_handoff_path"], "RECEIVE_VERIFY_HANDOFF.md")
            self.assertEqual(manifest["public_verify_script_path"], "PUBLIC_VERIFY_COMMANDS.sh")
            self.assertEqual(manifest["public_verify"]["install_mode_requirement"], "packaged")
            self.assertEqual(manifest["public_verify"]["repo_url"], "https://github.com/zerkerlabs/zmem")
            self.assertEqual(
                manifest["public_verify"]["raw_install_url"],
                "https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh",
            )
            self.assertEqual(manifest["public_verify"]["commands"], PUBLIC_VERIFY_COMMAND_SEQUENCE)
            self.assertEqual(manifest["public_verify"]["expected_log_files"], PUBLIC_VERIFY_LOG_FILENAMES)
            self.assertEqual(manifest["public_verify"]["handoff_path"], "PUBLIC_VERIFY_HANDOFF.md")
            self.assertEqual(manifest["public_verify"]["receive_verify_handoff_path"], "RECEIVE_VERIFY_HANDOFF.md")
            self.assertEqual(manifest["public_verify"]["script_path"], "PUBLIC_VERIFY_COMMANDS.sh")
            self.assertEqual(manifest["public_verify"]["checklist_path"], "PUBLIC_VERIFY_CHECKLIST.md")
            self.assertEqual(manifest["public_verify"]["logs_dir_path"], "public-verify-logs")
            self.assertEqual(manifest["public_verify"]["result_path"], "public-verify-result.json")
            self.assertEqual(manifest["public_verify"]["runbook_path"], "CLEAN_SHELL_PUBLIC_VERIFY.md")
            self.assertEqual(manifest["public_verify"]["operator_prompt_path"], "CLEAN_SHELL_OPERATOR_PROMPT.md")
            self.assertEqual(manifest["public_verify"]["finalize_script_path"], "FINALIZE_RETURN_PACKET.sh")
            self.assertEqual(manifest["public_verify_result_path"], "public-verify-result.json")
            self.assertEqual(manifest["public_verify_runbook_path"], "CLEAN_SHELL_PUBLIC_VERIFY.md")
            self.assertEqual(manifest["public_verify_operator_prompt_path"], "CLEAN_SHELL_OPERATOR_PROMPT.md")
            self.assertEqual(manifest["operator_packet_archive_path"], "public-verify-operator-packet.tar.gz")
            self.assertEqual(manifest["return_packet_archive_path"], "public-verify-return-packet.tar.gz")
            self.assertEqual(manifest["return_packet_finalize_script_path"], "FINALIZE_RETURN_PACKET.sh")
            self.assertEqual(manifest["local_alpha_gate"], "blocked (handoff_artifacts)")
            self.assertEqual(
                manifest["strict_publish_gate"],
                "blocked (launch_assets, public_verify_evidence, handoff_artifacts)",
            )
            self.assertEqual(manifest["return_packet"]["manifest_path"], "launch-proof.json")
            self.assertEqual(manifest["return_packet"]["public_verify_logs_dir_path"], "public-verify-logs")
            self.assertEqual(manifest["return_packet"]["public_verify_result_path"], "public-verify-result.json")
            self.assertEqual(manifest["return_packet"]["launch_assets_dir_path"], "assets")
            self.assertEqual(manifest["return_packet"]["archive_path"], "public-verify-return-packet.tar.gz")
            self.assertEqual(manifest["return_packet"]["finalize_script_path"], "FINALIZE_RETURN_PACKET.sh")
            self.assertFalse(result["return_packet"]["ready"])
            self.assertIn("pending public verify evidence, launch assets", result["return_packet"]["details"])
            self.assertEqual(manifest["launch_assets"][0]["id"], "install-status")
            self.assertEqual(manifest["launch_assets"][-1]["id"], "ui-release-pack")
            self.assertIn("Zerker Memory Launch Proof Transcript", transcript)
            self.assertIn("bundle verify", transcript)
            self.assertIn("Zerker Memory status", transcript)
            self.assertIn("Launch proof: ok", transcript)
            self.assertIn("Handoff: missing", transcript)
            self.assertIn("Generated by `zmem launch-proof`.", summary)
            self.assertIn("launch-proof.json", summary)
            self.assertIn("Return packet after the clean-shell pass", summary)
            self.assertIn("public-verify-return-packet.tar.gz", summary)
            self.assertIn("FINALIZE_RETURN_PACKET.sh", summary)
            self.assertIn("Launch asset checklist", summary)
            self.assertIn("Launch asset handoff", summary)
            self.assertIn("Use `CAPTURE_CHECKLIST.md` as the shot list", summary)
            self.assertIn("Zerker Memory Launch Asset Handoff", launch_asset_handoff)
            self.assertIn("ui-release-pack", launch_asset_handoff)
            self.assertIn("zmem verify-launch-assets --summary-only", launch_asset_handoff)
            self.assertIn("Local alpha gate snapshot in this generated pack:", launch_asset_handoff)
            self.assertIn("Strict publish gate snapshot in this generated pack:", launch_asset_handoff)
            self.assertIn("## Durable Fallbacks", launch_asset_handoff)
            self.assertIn("docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", launch_asset_handoff)
            self.assertIn("docs/LAUNCH_ASSET_OPERATOR_PROMPT.md", launch_asset_handoff)
            self.assertIn("Zerker Memory Public Verify Handoff", public_verify_handoff)
            self.assertIn("PUBLIC_VERIFY_COMMANDS.sh", public_verify_handoff)
            self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", public_verify_handoff)
            self.assertIn("## Durable Fallbacks", public_verify_handoff)
            self.assertIn("docs/CLEAN_SHELL_OPERATOR_PROMPT.md", public_verify_handoff)
            self.assertIn("tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof", public_verify_handoff)
            self.assertIn("FINALIZE_RETURN_PACKET.sh", public_verify_handoff)
            self.assertIn("zmem verify-launch-assets --summary-only", public_verify_handoff)
            self.assertIn("zmem verify-public-verify --summary-only", public_verify_handoff)
            self.assertIn("public-verify-operator-packet.tar.gz", public_verify_handoff)
            self.assertIn("public-verify-return-packet.tar.gz", public_verify_handoff)
            self.assertIn("https://github.com/zerkerlabs/zmem", public_verify_handoff)
            self.assertIn("https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh", public_verify_handoff)
            self.assertIn("## Current Gate Snapshot", public_verify_handoff)
            self.assertIn("- Local alpha gate:", public_verify_handoff)
            self.assertIn("- Strict publish gate:", public_verify_handoff)
            self.assertIn("Zerker Memory Receive-Side Return Packet Handoff", receive_verify_handoff)
            self.assertIn("## Durable Fallbacks", receive_verify_handoff)
            self.assertIn("docs/LAUNCH_ASSET_BOARD.html", receive_verify_handoff)
            self.assertIn("zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only", receive_verify_handoff)
            self.assertIn("## Rejection Rules", receive_verify_handoff)
            self.assertIn("Reject the packet if `Ready: yes` is missing", receive_verify_handoff)
            self.assertIn("RECEIVE_VERIFY_HANDOFF.md", summary)
            self.assertIn("## Success Criteria", public_verify_handoff)
            self.assertIn("## Stop Conditions", public_verify_handoff)
            self.assertIn("Stop if the clean-shell proof path falls back to local wrappers", public_verify_handoff)
            self.assertIn("`curl-install.log`", public_verify_handoff)
            self.assertIn("`release-pack-summary.png` from `release-pack-summary`", public_verify_handoff)
            self.assertIn("## Return Packet Contract", public_verify_handoff)
            self.assertIn("`.zerker/launch-proof/public-verify-summary.md`", public_verify_handoff)
            self.assertIn("Return packet finalize script", public_verify_checklist)
            self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", public_verify_checklist)
            self.assertIn("FINALIZE_RETURN_PACKET.sh", public_verify_checklist)
            self.assertIn("zmem verify-launch-assets --summary-only", public_verify_checklist)
            self.assertIn("zmem verify-public-verify --summary-only", public_verify_checklist)
            self.assertIn("## Stop Conditions", public_verify_checklist)
            self.assertIn("falls back to local wrappers", public_verify_checklist)
            self.assertIn("Running launch-asset verification before rebuilding the archive", return_packet_finalize_script)
            self.assertIn("Running clean-shell public-verify validation before rebuilding the archive", return_packet_finalize_script)
            self.assertIn('ZMEM_CMD="${ZMEM_CMD:-python3 -m zerker_memory}"', return_packet_finalize_script)
            self.assertIn('$ZMEM_CMD verify-public-verify --summary-only', return_packet_finalize_script)
            self.assertIn("Running receive-side verification locally before handback", return_packet_finalize_script)
            self.assertIn('$ZMEM_CMD verify-launch-assets --summary-only', return_packet_finalize_script)
            self.assertIn('$ZMEM_CMD verify-return-packet "$ARCHIVE_PATH" --summary-only', return_packet_finalize_script)
            self.assertIn("Zerker Memory Launch Proof Report", report)
            self.assertIn("Clean-shell runbook copy", report)
            self.assertIn("Launch Asset Storyboard", report)
            self.assertIn("Return Packet", report)
            self.assertIn("ui-release-pack", report)
            self.assertNotIn("ui-handoff-restore", report)
            self.assertIn("terminal-transcript.txt", report)
            self.assertIn("Launch proof: ok", manifest["status_summary"])
            self.assertIn("Launch proof: ok", result["status_summary"])
            self.assertNotIn("Launch proof: missing", manifest["status_summary"])
            self.assertNotIn("Launch proof: missing", result["status_summary"])
            self.assertEqual(result["status_summary"], manifest["status_summary"])
            self.assertIn("Zerker Memory Launch Asset Checklist", capture_checklist)
            self.assertIn("Launch asset board", capture_checklist)
            self.assertIn("Launch Assets", capture_checklist)
            self.assertIn("ui-release-pack", capture_checklist)
            self.assertIn("Required capture set: `6` assets total; `zmem verify-launch-assets --summary-only` must report `6/6 captured`.", capture_checklist)
            self.assertIn("## Asset Pass Gate", capture_checklist)
            self.assertIn("zmem verify-public-verify --summary-only", capture_checklist)
            self.assertIn("docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", capture_checklist)
            self.assertIn("docs/CLEAN_SHELL_PUBLIC_VERIFY.md", capture_checklist)
            self.assertIn("docs/CLEAN_SHELL_OPERATOR_PROMPT.md", capture_checklist)
            self.assertIn("docs/LAUNCH_ASSET_BOARD.html", capture_checklist)
            self.assertIn("docs/LAUNCH_ASSET_OPERATOR_PROMPT.md", capture_checklist)
            self.assertIn("## Clean-Shell Proof Log Map", capture_checklist)
            self.assertIn("`curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`", capture_checklist)
            self.assertIn("`python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`", capture_checklist)
            self.assertIn("FINALIZE_RETURN_PACKET.sh", capture_checklist)
            self.assertIn("zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only", capture_checklist)
            self.assertIn("Local alpha gate snapshot in this pack:", capture_checklist)
            self.assertIn("Strict publish gate snapshot in this pack:", capture_checklist)
            self.assertNotIn("ui-handoff-restore", capture_checklist)
            self.assertNotIn("handoff-restore-terminal", capture_checklist)
            self.assertIn("Zerker Memory Public Verify Checklist", public_verify_checklist)
            self.assertIn('cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"', public_verify_checklist)
            self.assertIn("tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof", public_verify_checklist)
            self.assertIn("python3 scripts/release_smoke.py --require-install-mode packaged", public_verify_checklist)
            self.assertIn("Local alpha gate snapshot in this generated pack:", public_verify_checklist)
            self.assertIn("Strict publish gate snapshot in this generated pack:", public_verify_checklist)
            self.assertIn("## Command Log Map", public_verify_checklist)
            self.assertIn("`bash examples/first_run.sh` -> `public-verify-logs/first-run.log`", public_verify_checklist)
            self.assertIn("`zmem prelaunch` -> `public-verify-logs/prelaunch.log`", public_verify_checklist)
            self.assertIn("public-verify-logs", public_verify_checklist)
            self.assertIn("public-verify-result.json", public_verify_checklist)
            self.assertIn("public-verify-operator-packet.tar.gz", public_verify_checklist)
            self.assertIn("https://github.com/zerkerlabs/zmem", public_verify_runbook)
            self.assertIn("https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh", public_verify_runbook)
            self.assertIn("bootstrap the clean repo path", public_verify_runbook)
            self.assertIn("reruns the raw installer itself", public_verify_runbook)
            self.assertIn("## Command Log Map", public_verify_runbook)
            self.assertIn("`zmem release-pack --summary-only` -> `public-verify-logs/release-pack.log`", public_verify_runbook)
            self.assertIn("## Stop Conditions", public_verify_runbook)
            self.assertIn("records any install mode other than `packaged`", public_verify_runbook)
            public_verify_operator_prompt = Path(result["public_verify_operator_prompt_path"]).read_text(encoding="utf-8")
            self.assertIn("Clean-Shell Operator Prompt", public_verify_operator_prompt)
            self.assertIn("bootstrap-only", public_verify_operator_prompt)
            self.assertIn("rerun the raw installer", public_verify_operator_prompt)
            self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", public_verify_operator_prompt)
            self.assertIn("PUBLIC_VERIFY_CHECKLIST.md", public_verify_operator_prompt)
            self.assertIn("CAPTURE_CHECKLIST.md", public_verify_operator_prompt)
            self.assertIn("public-verify-return-packet.tar.gz", public_verify_operator_prompt)
            self.assertIn("public-verify-return-packet.tar.gz", public_verify_checklist)
            self.assertTrue(public_verify_runbook)
            public_verify_result = json.loads(Path(result["public_verify_result_path"]).read_text(encoding="utf-8"))
            public_verify_summary = Path(result["public_verify_summary_path"]).read_text(encoding="utf-8")
            with tarfile.open(result["operator_packet_archive_path"], "r:gz") as archive:
                operator_names = {member.name.rstrip("/") for member in archive.getmembers()}
            self.assertIn("launch-proof.json", operator_names)
            self.assertIn("README.md", operator_names)
            self.assertIn("index.html", operator_names)
            self.assertIn("CAPTURE_CHECKLIST.md", operator_names)
            self.assertIn("LAUNCH_ASSET_BOARD.html", operator_names)
            self.assertIn("LAUNCH_ASSET_HANDOFF.md", operator_names)
            self.assertIn("PUBLIC_VERIFY_HANDOFF.md", operator_names)
            self.assertIn("RECEIVE_VERIFY_HANDOFF.md", operator_names)
            self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", operator_names)
            self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", operator_names)
            self.assertIn("PUBLIC_VERIFY_CHECKLIST.md", operator_names)
            self.assertIn("PUBLIC_VERIFY_COMMANDS.sh", operator_names)
            self.assertIn("FINALIZE_RETURN_PACKET.sh", operator_names)
            self.assertIn("public-verify-result.json", operator_names)
            self.assertIn("public-verify-return-packet.tar.gz", operator_names)
            with tarfile.open(result["return_packet_archive_path"], "r:gz") as archive:
                names = {member.name.rstrip("/") for member in archive.getmembers()}
            self.assertIn("launch-proof.json", names)
            self.assertTrue(any(name.startswith("public-verify-logs") for name in names))
            self.assertIn("public-verify-result.json", names)
            self.assertIn("assets", names)
            self.assertIn("`.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`", public_verify_checklist)
            self.assertIn("`.zerker/launch-proof/README.md`", public_verify_checklist)
            self.assertIn("## Return Packet", public_verify_checklist)
            self.assertIn("`.zerker/launch-proof/launch-proof.json`", public_verify_checklist)
            self.assertIn("`ui-release-pack`", public_verify_checklist)
            self.assertNotIn("`ui-handoff-restore`", public_verify_checklist)
            self.assertNotIn(str(root), public_verify_checklist)
            self.assertIn('zmem --db ".zerker/launch-proof/memory.sqlite" ui', capture_checklist)
            self.assertIn("`.zerker/launch-proof/exports/", capture_checklist)
            self.assertNotIn(str(root), capture_checklist)
            self.assertIn('REPO_DIR="$INSTALL_DIR/repo"', public_verify_script)
            self.assertIn('LOG_DIR="', public_verify_script)
            self.assertIn('RESULT_PATH="$SCRIPT_DIR/public-verify-result.json"', public_verify_script)
            self.assertIn('ARCHIVE_PATH="$SCRIPT_DIR/public-verify-return-packet.tar.gz"', public_verify_script)
            self.assertIn('OPERATOR_PACKET_ARCHIVE="$SCRIPT_DIR/public-verify-operator-packet.tar.gz"', public_verify_script)
            self.assertIn('INSTALL_MODE_REQUIREMENT="packaged"', public_verify_script)
            self.assertIn('python3 -m zerker_memory verify-operator-packet "$OPERATOR_PACKET_ARCHIVE" --summary-only', public_verify_script)
            self.assertIn('tee "$LOG_DIR/operator-packet-verify.log"', public_verify_script)
            self.assertIn("verify_restored_operator_packet", public_verify_script)
            self.assertIn(
                'Bootstrap note: the repo should already exist from the initial clean-shell install used to restore this packet.',
                public_verify_script,
            )
            self.assertIn(
                'This script reruns the raw installer itself and records public-verify-logs/curl-install.log for the proof bundle.',
                public_verify_script,
            )
            self.assertIn('INSTALL_MODE="$(python3 - "$log_path"', public_verify_script)
            self.assertIn('run_and_log packaged-release-smoke python3 scripts/release_smoke.py --require-install-mode packaged', public_verify_script)
            self.assertIn('tee "$LOG_DIR/$name.log"', public_verify_script)
            self.assertIn('cd "$REPO_DIR"', public_verify_script)
            self.assertIn('Public verify result saved under', public_verify_script)
            self.assertIn('Return packet archive saved under', public_verify_script)
            self.assertIn('After saving launch assets, run', public_verify_script)
            self.assertIn('Run zmem verify-public-verify --summary-only before the launch-asset pass.', public_verify_script)
            self.assertIn('zmem verify-launch-assets --summary-only', public_verify_script)
            self.assertIn('FINALIZE_RETURN_PACKET.sh', public_verify_script)
            self.assertEqual(public_verify_result["status"], "pending")
            self.assertEqual(public_verify_result["install_mode_requirement"], "packaged")
            self.assertIn("clean networked shell", public_verify_result["next_step"])
            self.assertIn("Expected public repo: `https://github.com/zerkerlabs/zmem`", public_verify_summary)
            self.assertIn(
                "Expected raw install URL: `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`",
                public_verify_summary,
            )
            with tarfile.open(result["return_packet_archive_path"], "r:gz") as archive:
                self.assertEqual(
                    archive.getnames(),
                    [
                        "launch-proof.json",
                        "public-verify-logs",
                        "public-verify-result.json",
                        "public-verify-summary.md",
                        "assets",
                    ],
                )
            self.assertTrue(Path(result["public_verify_result_path"]).exists())
            self.assertTrue(Path(result["operator_packet_archive_path"]).exists())
            self.assertTrue(Path(result["return_packet_archive_path"]).exists())
            self.assertTrue(Path(result["bundle_path"]).exists())
            self.assertTrue(Path(result["snapshot_path"]).exists())
            self.assertTrue(Path(result["bt_xml_path"]).exists())
            self.assertTrue(Path(result["bt_manifest_path"]).exists())

    def test_run_launch_proof_ignores_missing_target_dir_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof_dir = root / ".zerker" / "launch-proof"
            proof_dir.mkdir(parents=True)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                with patch("zerker_memory.cli.shutil.rmtree", side_effect=FileNotFoundError("gone")):
                    result = run_launch_proof(
                        policy_path=root / ".zerker" / "policy.json",
                        providers_path=root / ".zerker" / "providers.json",
                        out_dir=proof_dir,
                        agent_id="codex",
                        scope="project",
                        task="deploy service to production",
                        bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["manifest_path"]).exists())

    def test_run_launch_proof_propagates_non_missing_target_dir_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof_dir = root / ".zerker" / "launch-proof"
            proof_dir.mkdir(parents=True)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                with patch("zerker_memory.cli.shutil.rmtree", side_effect=PermissionError("blocked")):
                    with self.assertRaises(PermissionError):
                        run_launch_proof(
                            policy_path=root / ".zerker" / "policy.json",
                            providers_path=root / ".zerker" / "providers.json",
                            out_dir=proof_dir,
                            agent_id="codex",
                            scope="project",
                            task="deploy service to production",
                            bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                        )
            finally:
                os.chdir(previous_cwd)

    def test_run_launch_proof_uses_handoff_storyboard_when_handoff_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)
                store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=root / ".zerker" / "policy.json")
                store.init()
                create_handoff_package(store, providers_path=root / ".zerker" / "providers.json", out_dir=None, action_id=None)

                result = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path("examples") / "bt_trace.jsonl",
                )
                capture_checklist = Path(result["capture_checklist_path"]).read_text(encoding="utf-8")
                launch_asset_handoff = Path(result["launch_asset_handoff_path"]).read_text(encoding="utf-8")
                public_verify_handoff = Path(result["public_verify_handoff_path"]).read_text(encoding="utf-8")
                launch_asset_board = Path(result["launch_asset_board_path"]).read_text(encoding="utf-8")
            finally:
                os.chdir(previous_cwd)

        self.assertIn("Required capture set: `8` assets total; `zmem verify-launch-assets --summary-only` must report `8/8 captured`.", capture_checklist)
        self.assertIn("handoff-restore-terminal", capture_checklist)
        self.assertIn("ui-handoff-restore", capture_checklist)
        self.assertIn("verify-public-verify --summary-only", launch_asset_board)
        self.assertIn("FINALIZE_RETURN_PACKET.sh", launch_asset_board)
        self.assertIn("verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only", launch_asset_board)
        self.assertIn("`zmem verify-public-verify --summary-only` reports `Ready: yes` before the asset pass is considered complete.", launch_asset_handoff)
        self.assertIn("`zmem verify-launch-assets --summary-only` reports `8/8 captured` before handback.", launch_asset_handoff)
        self.assertIn("`zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes` before Phase 1 is marked complete.", launch_asset_handoff)
        self.assertIn("`ui-handoff-restore.gif` from `ui-handoff-restore`", launch_asset_handoff)
        self.assertIn("`zmem verify-launch-assets --summary-only` reports `8/8 captured` before `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` is accepted.", public_verify_handoff)

    def test_verify_return_packet_archive_reports_ready_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                self._write_prelaunch_fixture(root, readme="https://github.com/zerkerlabs/zmem")
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                manifest = json.loads(Path(launch_proof["manifest_path"]).read_text(encoding="utf-8"))
                for log_name in PUBLIC_VERIFY_LOG_FILENAMES:
                    (root / ".zerker" / "launch-proof" / "public-verify-logs" / log_name).write_text("ok\n", encoding="utf-8")
                for asset in manifest["launch_assets"]:
                    (root / ".zerker" / "launch-proof" / asset["output_path"]).parent.mkdir(parents=True, exist_ok=True)
                    (root / ".zerker" / "launch-proof" / asset["output_path"]).write_text("asset\n", encoding="utf-8")
                Path(launch_proof["public_verify_result_path"]).write_text(
                    json.dumps(
                        {
                            "schema": "zerker.public_verify_result.v1",
                            "ok": True,
                            "exit_code": 0,
                            "details": "all clean-shell checks passed",
                            "failed_steps": [],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                from zerker_memory.cli import write_return_packet_archive

                write_return_packet_archive(
                    root=root / ".zerker" / "launch-proof",
                    archive_path=Path(launch_proof["return_packet_archive_path"]),
                )
                result = verify_return_packet_archive(Path(launch_proof["return_packet_archive_path"]))
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(result["ok"])
            self.assertTrue(result["public_verify_ready"])
            self.assertTrue(result["launch_assets_ready"])
            self.assertEqual(result["public_verify_present_count"], len(PUBLIC_VERIFY_LOG_FILENAMES))
            self.assertEqual(result["launch_assets_expected_count"], len(manifest["launch_assets"]))
            summary = render_return_packet_summary(result)
            self.assertIn("Zerker Memory return packet", summary)
            self.assertIn("Ready: yes", summary)
            self.assertIn("Receive-side handoff: RECEIVE_VERIFY_HANDOFF.md", summary)
            self.assertIn("Public verify logs dir: public-verify-logs", summary)
            self.assertIn("Public verify: ok", summary)
            self.assertIn("Launch assets: ok", summary)
            self.assertIn("Required install mode: packaged", summary)
            self.assertIn("Expected public repo: https://github.com/zerkerlabs/zmem", summary)
            self.assertIn("Expected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh", summary)
            self.assertIn("Return packet finalize: FINALIZE_RETURN_PACKET.sh", summary)

    def test_verify_return_packet_archive_mirrors_handoff_session_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                source_store = MemoryStore(root / ".zerker" / "memory.sqlite")
                source_store.init()
                source_store.remember(
                    "Production deploys require approval",
                    memory_type="policy",
                    scope="project",
                    source_kind="human",
                    status="active",
                )
                source_store.start_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="launch proof continuity session",
                    context_budget_tokens=256,
                )
                source_store.checkpoint_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="checkpoint before return packet",
                )
                session_snapshot = source_store.snapshot_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="snapshot before return packet",
                )
                source_store.soft_delete_session_snapshot_payload(
                    session_snapshot["session_snapshot_id"],
                    actor_id="reviewer",
                    reason="retention compacted before return packet",
                )
                source_store.end_session(
                    "session://alpha",
                    actor_id="codex",
                    scope="project",
                    summary="closeout before return packet",
                )
                create_handoff_package(
                    source_store,
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "handoff",
                    action_id=None,
                )
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path("examples") / "bt_trace.jsonl",
                )
                manifest = json.loads(Path(launch_proof["manifest_path"]).read_text(encoding="utf-8"))
                for log_name in PUBLIC_VERIFY_LOG_FILENAMES:
                    (root / ".zerker" / "launch-proof" / "public-verify-logs" / log_name).write_text("ok\n", encoding="utf-8")
                for asset in manifest["launch_assets"]:
                    asset_path = root / ".zerker" / "launch-proof" / asset["output_path"]
                    asset_path.parent.mkdir(parents=True, exist_ok=True)
                    asset_path.write_text("asset\n", encoding="utf-8")
                Path(launch_proof["public_verify_result_path"]).write_text(
                    json.dumps(
                        {
                            "schema": "zerker.public_verify_result.v1",
                            "ok": True,
                            "exit_code": 0,
                            "details": "all clean-shell checks passed",
                            "failed_steps": [],
                            "install_mode": "venv-pth",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                write_return_packet_archive(
                    root=root / ".zerker" / "launch-proof",
                    archive_path=Path(launch_proof["return_packet_archive_path"]),
                )
                result = verify_return_packet_archive(Path(launch_proof["return_packet_archive_path"]))
                summary = render_return_packet_summary(result)
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["ok"])
        self.assertEqual(result["session_lifecycle_rollup"]["count"], 1)
        self.assertEqual(result["session_lifecycle_rollup"]["event_kind_counts"]["start"], 1)
        self.assertEqual(result["session_lifecycle_rollup"]["event_kind_counts"]["checkpoint"], 1)
        self.assertEqual(result["session_lifecycle_rollup"]["event_kind_counts"]["snapshot"], 1)
        self.assertEqual(result["session_lifecycle_rollup"]["event_kind_counts"]["snapshot_soft_delete"], 1)
        self.assertEqual(result["session_lifecycle_rollup"]["event_kind_counts"]["end"], 1)
        self.assertEqual(result["session_lifecycle_rollup"]["verified_receipt_count"], 5)
        self.assertEqual(result["session_retention_rollup"]["count"], 1)
        self.assertEqual(result["session_retention_rollup"]["retention_state_counts"]["soft_deleted_only"], 1)
        self.assertEqual(
            result["session_retention_rollup"]["sessions"][0]["latest_soft_deleted_reason"],
            "retention compacted before return packet",
        )
        self.assertIn("Lifecycle sessions: 1", summary)
        self.assertIn("Lifecycle events: starts=1 checkpoints=1 snapshots=1 snapshot_soft_deletes=1 ends=1", summary)
        self.assertIn("Lifecycle receipt provenance: 5 verified, 0 failed", summary)
        self.assertIn("Latest lifecycle session: session://alpha latest=end payload=soft_deleted context_budget_tokens=256", summary)
        self.assertIn("Retention sessions: 1", summary)
        self.assertIn("Retention states: all_available=0 mixed=0 soft_deleted_only=1", summary)
        self.assertIn("Retention payloads: 0 available, 1 soft-deleted", summary)
        self.assertIn("Latest retention reason: retention compacted before return packet", summary)

    def test_verify_return_packet_archive_reports_missing_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                result = verify_return_packet_archive(Path(launch_proof["return_packet_archive_path"]))
            finally:
                os.chdir(previous_cwd)

            self.assertFalse(result["ok"])
            self.assertIn("missing logs", result["details"])
            self.assertIn("public-verify-logs/curl-install.log", result["missing_paths"])
            self.assertEqual(result["receive_verify_handoff_path"], "RECEIVE_VERIFY_HANDOFF.md")
            self.assertEqual(result["public_verify_logs_dir_path"], "public-verify-logs")
            self.assertEqual(result["install_mode_requirement"], "packaged")
            self.assertEqual(result["return_packet_finalize_script_path"], "FINALIZE_RETURN_PACKET.sh")

    def test_verify_launch_assets_reports_missing_storyboard_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                result = verify_launch_assets(root)
            finally:
                os.chdir(previous_cwd)

            self.assertFalse(result["ok"])
            self.assertIn("install-status.png", result["details"])
            self.assertIn("assets/install-status.png", result["missing_paths"])
            self.assertEqual(result["finalize_script_path"], "FINALIZE_RETURN_PACKET.sh")
            summary = render_launch_assets_summary(result)
            self.assertIn("Zerker Memory launch assets", summary)
            self.assertIn("Assets: failed", summary)
            self.assertIn("Expected launch assets:", summary)
            self.assertIn("install-status.png from install-status -> assets/install-status.png", summary)
            self.assertIn("Command: bash install.sh", summary)
            self.assertIn("Capture: End on `Zerker Memory status`.", summary)
            self.assertIn("`FINALIZE_RETURN_PACKET.sh`", summary)

    def test_verify_launch_assets_reports_ready_storyboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                manifest = json.loads(Path(launch_proof["manifest_path"]).read_text(encoding="utf-8"))
                for asset in manifest["launch_assets"]:
                    asset_path = root / ".zerker" / "launch-proof" / asset["output_path"]
                    asset_path.parent.mkdir(parents=True, exist_ok=True)
                    asset_path.write_text("asset\n", encoding="utf-8")
                result = verify_launch_assets(root)
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(result["ok"])
            self.assertEqual(result["present_count"], result["expected_count"])
            self.assertIn("storyboard verified", result["details"])
            summary = render_launch_assets_summary(result)
            self.assertIn("Ready: yes", summary)
            self.assertIn("Assets: ok", summary)
            self.assertIn("Expected launch assets:", summary)
            self.assertIn("ui-release-pack.gif from ui-release-pack -> assets/ui-release-pack.gif", summary)
            self.assertIn('Command: zmem --db ".zerker/launch-proof/memory.sqlite" ui', summary)
            self.assertIn("Capture: Show the `zmem ui` release-pack action and the proof-review surface.", summary)

    def test_verify_operator_packet_archive_reports_ready_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=root / ".zerker" / "policy.json")
            os.chdir(root)
            try:
                store.init()
                write_policy_template(root / ".zerker" / "policy.json", force=False)
                write_agent_prompt_template(root / ".zerker" / "AGENT_PROMPT.md", force=False)
                write_json_file(root / ".zerker" / "mcp.json", {"mcpServers": {}}, force=False)
                write_provider_config_template(root / ".zerker" / "providers.json", force=False)
                run_agent_smoke(store, agent_id="codex", scope="project", task="prove governed memory")
                self._write_prelaunch_fixture(root, readme="https://github.com/zerkerlabs/zmem")
                release_pack = run_release_pack(
                    store,
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                    action_id=None,
                    allow_placeholders=True,
                )
                result = verify_operator_packet_archive(Path(release_pack["operator_packet_archive_path"]))
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(result["ok"])
            summary = render_operator_packet_summary(result)
            self.assertIn("Zerker Memory operator packet", summary)
            self.assertIn("Ready: yes", summary)
            self.assertIn("16/16 files packed", summary)
            self.assertIn("Required install mode: packaged", summary)
            self.assertIn("Public verify script: PUBLIC_VERIFY_COMMANDS.sh", summary)
            self.assertIn("Expected logs dir: public-verify-logs", summary)
            self.assertIn("Expected public repo: https://github.com/zerkerlabs/zmem", summary)
            self.assertIn(
                "Expected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh",
                summary,
            )
            self.assertIn("- packaged-release-smoke.log", summary)
            self.assertIn("Local alpha gate:", summary)
            self.assertIn("Strict publish gate:", summary)
            self.assertIn("Result receipt: public-verify-result.json", summary)
            self.assertIn("Run summary: public-verify-summary.md", summary)
            self.assertIn("Operator prompt: CLEAN_SHELL_OPERATOR_PROMPT.md", summary)
            self.assertIn("Open first: CLEAN_SHELL_PUBLIC_VERIFY.md", summary)
            self.assertIn("Runbook: CLEAN_SHELL_PUBLIC_VERIFY.md", summary)
            self.assertIn("Unpack into repo: mkdir -p ", summary)
            self.assertIn("Forward together:", summary)
            self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", summary)
            self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", summary)
            self.assertIn("public-verify-operator-packet.tar.gz", summary)
            self.assertIn("public-verify-operator-packet.tar.gz", summary)
            self.assertIn("Launch assets dir: assets", summary)
            self.assertIn("Launch asset board: LAUNCH_ASSET_BOARD.html", summary)
            self.assertIn("- install-status.png from install-status -> assets/install-status.png", summary)
            self.assertIn("  Command: bash install.sh", summary)
            self.assertIn("  Capture: End on `Zerker Memory status`.", summary)
            self.assertIn("Return packet finalize: FINALIZE_RETURN_PACKET.sh", summary)
            self.assertIn("Return packet archive: public-verify-return-packet.tar.gz", summary)

    def test_verify_public_verify_reports_ready_logs_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                proof_dir = Path(launch_proof["out_dir"])
                logs_dir = proof_dir / "public-verify-logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                for name in PUBLIC_VERIFY_LOG_FILENAMES:
                    (logs_dir / name).write_text("ok\n", encoding="utf-8")
                result_payload = json.loads((proof_dir / "public-verify-result.json").read_text(encoding="utf-8"))
                result_payload["status"] = "passed"
                result_payload["ok"] = True
                result_payload["details"] = "public verify ok"
                result_payload["install_mode"] = "editable"
                (proof_dir / "public-verify-result.json").write_text(json.dumps(result_payload, indent=2) + "\n", encoding="utf-8")
                result = verify_public_verify(root)
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["ok"])
        self.assertEqual(result["present_count"], result["expected_count"])
        self.assertEqual(result["install_mode"], "editable")
        self.assertTrue(str(result["runbook_path"]).endswith("CLEAN_SHELL_PUBLIC_VERIFY.md"))
        self.assertTrue(str(result["operator_prompt_path"]).endswith("CLEAN_SHELL_OPERATOR_PROMPT.md"))
        self.assertTrue(str(result["operator_packet_archive_path"]).endswith("public-verify-operator-packet.tar.gz"))
        summary = render_public_verify_summary(result)
        self.assertIn("Zerker Memory public verify", summary)
        self.assertIn("Ready: yes", summary)
        self.assertIn("Logs: ok", summary)
        self.assertIn("Operator prompt: ", summary)
        self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", summary)
        self.assertIn("Open first: ", summary)
        self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", summary)
        self.assertIn("Runbook: ", summary)
        self.assertIn(
            "Unpack into repo: mkdir -p ",
            summary,
        )
        self.assertIn("Forward together:", summary)
        self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", summary)
        self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", summary)
        self.assertIn("public-verify-operator-packet.tar.gz", summary)
        self.assertIn("public-verify-operator-packet.tar.gz -C ", summary)
        self.assertIn("Required install mode: packaged", summary)
        self.assertIn("Observed install mode: editable", summary)
        self.assertIn("Expected public repo: https://github.com/zerkerlabs/zmem", summary)
        self.assertIn(
            "Expected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh",
            summary,
        )
        self.assertIn("Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", summary)
        self.assertIn("Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html", summary)
        self.assertIn("Launch asset board: ", summary)
        self.assertIn("LAUNCH_ASSET_BOARD.html", summary)
        self.assertIn("Expected launch assets:", summary)
        self.assertIn("- install-status.png from install-status -> assets/install-status.png", summary)
        self.assertIn("  Command: bash install.sh", summary)
        self.assertIn("  Capture: End on `Zerker Memory status`.", summary)

    def test_verify_public_verify_accepts_venv_pth_for_packaged_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                proof_dir = Path(launch_proof["out_dir"])
                logs_dir = proof_dir / "public-verify-logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                for name in PUBLIC_VERIFY_LOG_FILENAMES:
                    (logs_dir / name).write_text("ok\n", encoding="utf-8")
                result_payload = json.loads((proof_dir / "public-verify-result.json").read_text(encoding="utf-8"))
                result_payload["status"] = "passed"
                result_payload["ok"] = True
                result_payload["details"] = "public verify ok"
                result_payload["install_mode"] = "venv-pth"
                (proof_dir / "public-verify-result.json").write_text(json.dumps(result_payload, indent=2) + "\n", encoding="utf-8")

                result = verify_public_verify(root)
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["ok"])
        self.assertEqual(result["install_mode"], "venv-pth")

    def test_verify_return_packet_archive_accepts_venv_pth_for_packaged_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                proof_dir = Path(launch_proof["out_dir"])
                logs_dir = proof_dir / "public-verify-logs"
                assets_dir = proof_dir / "assets"
                logs_dir.mkdir(parents=True, exist_ok=True)
                for name in PUBLIC_VERIFY_LOG_FILENAMES:
                    (logs_dir / name).write_text("ok\n", encoding="utf-8")
                result_payload = json.loads((proof_dir / "public-verify-result.json").read_text(encoding="utf-8"))
                result_payload["status"] = "passed"
                result_payload["ok"] = True
                result_payload["details"] = "public verify ok"
                result_payload["install_mode"] = "venv-pth"
                (proof_dir / "public-verify-result.json").write_text(json.dumps(result_payload, indent=2) + "\n", encoding="utf-8")
                (proof_dir / "public-verify-summary.md").write_text("summary\n", encoding="utf-8")
                manifest = json.loads((proof_dir / "launch-proof.json").read_text(encoding="utf-8"))
                for asset in manifest["launch_assets"]:
                    asset_path = proof_dir / str(asset["output_path"])
                    asset_path.parent.mkdir(parents=True, exist_ok=True)
                    asset_path.write_text("asset\n", encoding="utf-8")
                archive_path = proof_dir / "public-verify-return-packet.tar.gz"
                with tarfile.open(archive_path, "w:gz") as archive:
                    archive.add(proof_dir / "launch-proof.json", arcname="launch-proof.json")
                    archive.add(logs_dir, arcname="public-verify-logs")
                    archive.add(proof_dir / "public-verify-result.json", arcname="public-verify-result.json")
                    archive.add(proof_dir / "public-verify-summary.md", arcname="public-verify-summary.md")
                    archive.add(assets_dir, arcname="assets")

                result = verify_return_packet_archive(archive_path)
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["ok"])
        self.assertEqual(result["install_mode_requirement"], "packaged")

    def test_release_pack_preserves_ready_public_verify_logs_and_launch_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                policy_path = root / ".zerker" / "policy.json"
                providers_path = root / ".zerker" / "providers.json"
                store = MemoryStore(root / ".zerker" / "memory.sqlite", policy_path=policy_path)
                store.init()
                bt_trace_path = Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl"
                run_release_pack(
                    store,
                    policy_path=policy_path,
                    providers_path=providers_path,
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=bt_trace_path,
                    action_id=None,
                    allow_placeholders=False,
                )
                proof_dir = root / ".zerker" / "launch-proof"
                logs_dir = proof_dir / "public-verify-logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                for name in PUBLIC_VERIFY_LOG_FILENAMES:
                    (logs_dir / name).write_text(f"{name} ok\n", encoding="utf-8")
                result_payload = json.loads((proof_dir / "public-verify-result.json").read_text(encoding="utf-8"))
                result_payload["status"] = "passed"
                result_payload["ok"] = True
                result_payload["details"] = "public verify ok"
                result_payload["install_mode"] = "venv-pth"
                (proof_dir / "public-verify-result.json").write_text(
                    json.dumps(result_payload, indent=2) + "\n",
                    encoding="utf-8",
                )
                (proof_dir / "public-verify-summary.md").write_text("public verify summary\n", encoding="utf-8")
                manifest = json.loads((proof_dir / "launch-proof.json").read_text(encoding="utf-8"))
                for asset in manifest["launch_assets"]:
                    asset_path = proof_dir / str(asset["output_path"])
                    asset_path.parent.mkdir(parents=True, exist_ok=True)
                    asset_path.write_text(f"{asset['id']} asset\n", encoding="utf-8")
                write_return_packet_archive(
                    root=proof_dir,
                    archive_path=proof_dir / "public-verify-return-packet.tar.gz",
                )

                self.assertTrue(public_verify_status(root)["ready"])
                self.assertTrue(verify_launch_assets(root)["ok"])
                self.assertTrue(return_packet_status(root)["ready"])

                result = run_release_pack(
                    store,
                    policy_path=policy_path,
                    providers_path=providers_path,
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=bt_trace_path,
                    action_id=None,
                    allow_placeholders=False,
                )
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(result["public_verify"]["ready"])
        self.assertEqual(result["public_verify"]["present_count"], len(PUBLIC_VERIFY_LOG_FILENAMES))
        self.assertTrue(result["launch_assets"]["ready"])
        self.assertEqual(result["launch_assets"]["present_count"], len(manifest["launch_assets"]))
        self.assertTrue(result["return_packet"]["ready"])
        prelaunch_checks = {check["name"]: check["ok"] for check in result["prelaunch"]["checks"]}
        self.assertTrue(prelaunch_checks["launch_assets"])
        self.assertTrue(prelaunch_checks["public_verify_evidence"])

    def test_verify_operator_packet_archive_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                launch_proof = run_launch_proof(
                    policy_path=root / ".zerker" / "policy.json",
                    providers_path=root / ".zerker" / "providers.json",
                    out_dir=root / ".zerker" / "launch-proof",
                    agent_id="codex",
                    scope="project",
                    task="deploy service to production",
                    bt_trace_path=Path(__file__).resolve().parents[1] / "examples" / "bt_trace.jsonl",
                )
                archive_path = Path(launch_proof["operator_packet_archive_path"])
                reduced_archive = archive_path.with_name("operator-packet-missing-script.tar.gz")
                with tarfile.open(archive_path, "r:gz") as src, tarfile.open(reduced_archive, "w:gz") as dst:
                    for member in src.getmembers():
                        if member.name == "PUBLIC_VERIFY_COMMANDS.sh":
                            continue
                        extracted = src.extractfile(member) if member.isfile() else None
                        if extracted is None:
                            dst.addfile(member)
                            continue
                        dst.addfile(member, extracted)
                result = verify_operator_packet_archive(reduced_archive)
            finally:
                os.chdir(previous_cwd)

            self.assertFalse(result["ok"])
            self.assertIn("missing files", result["details"])
            self.assertIn("PUBLIC_VERIFY_COMMANDS.sh", result["missing_paths"])

    def test_render_launch_proof_summary_lists_artifacts_and_next_steps(self):
        summary = render_launch_proof_summary(
            {
                "ok": True,
                "out_dir": ".zerker/launch-proof",
                "manifest_path": ".zerker/launch-proof/launch-proof.json",
                "report_path": ".zerker/launch-proof/index.html",
                "transcript_path": ".zerker/launch-proof/terminal-transcript.txt",
                "summary_path": ".zerker/launch-proof/README.md",
                "capture_checklist_path": ".zerker/launch-proof/CAPTURE_CHECKLIST.md",
                "launch_asset_board_path": ".zerker/launch-proof/LAUNCH_ASSET_BOARD.html",
                "launch_assets_dir_path": ".zerker/launch-proof/assets",
                "public_verify_handoff_path": ".zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md",
                "public_verify_checklist_path": ".zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md",
                "public_verify_script_path": ".zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh",
                "operator_packet": {
                    "ready": True,
                    "details": "16/16 files packed",
                },
                "public_verify_logs_dir_path": ".zerker/launch-proof/public-verify-logs",
                "public_verify_result_path": ".zerker/launch-proof/public-verify-result.json",
                "public_verify_runbook_path": ".zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md",
                "public_verify_operator_prompt_path": ".zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md",
                "return_packet_finalize_script_path": ".zerker/launch-proof/FINALIZE_RETURN_PACKET.sh",
                "operator_packet_archive_path": ".zerker/launch-proof/public-verify-operator-packet.tar.gz",
                "return_packet_archive_path": ".zerker/launch-proof/public-verify-return-packet.tar.gz",
                "db_path": ".zerker/launch-proof/memory.sqlite",
                "action_id": "act_123",
                "bundle_path": ".zerker/launch-proof/exports/action.bundle.json",
                "snapshot_path": ".zerker/launch-proof/exports/state.snapshot.json",
                "bt_xml_path": ".zerker/launch-proof/bt/trace.xml",
                "bt_manifest_path": ".zerker/launch-proof/bt/manifest.json",
                "next_steps": ['zmem --db ".zerker/launch-proof/memory.sqlite" ui', "open .zerker/launch-proof/index.html"],
            }
        )

        self.assertIn("Zerker Memory launch proof", summary)
        self.assertIn("Ready: yes", summary)
        self.assertIn("Manifest: .zerker/launch-proof/launch-proof.json", summary)
        self.assertIn("Report: .zerker/launch-proof/index.html", summary)
        self.assertIn("Capture checklist: .zerker/launch-proof/CAPTURE_CHECKLIST.md", summary)
        self.assertIn("Launch asset board: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html", summary)
        self.assertIn("Launch assets dir: .zerker/launch-proof/assets", summary)
        self.assertIn("Public verify handoff: .zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md", summary)
        self.assertIn("Public verify checklist: .zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md", summary)
        self.assertIn("Public verify script: .zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh", summary)
        self.assertIn("Public verify logs dir: .zerker/launch-proof/public-verify-logs", summary)
        self.assertIn("Public verify result: .zerker/launch-proof/public-verify-result.json", summary)
        self.assertIn("Public verify runbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md", summary)
        self.assertIn("Operator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md", summary)
        self.assertIn("Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", summary)
        self.assertIn("Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html", summary)
        self.assertIn("Return packet finalize: .zerker/launch-proof/FINALIZE_RETURN_PACKET.sh", summary)
        self.assertIn("Operator packet archive: .zerker/launch-proof/public-verify-operator-packet.tar.gz", summary)
        self.assertIn("Operator packet: ok (16/16 files packed)", summary)
        self.assertIn("Return packet archive: .zerker/launch-proof/public-verify-return-packet.tar.gz", summary)
        self.assertIn('zmem --db ".zerker/launch-proof/memory.sqlite" ui', summary)

    def test_render_launch_proof_summary_normalizes_workspace_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                proof_dir = root / ".zerker" / "launch-proof"
                summary = render_launch_proof_summary(
                    {
                        "ok": True,
                        "out_dir": str(proof_dir),
                        "manifest_path": str(proof_dir / "launch-proof.json"),
                        "report_path": str(proof_dir / "index.html"),
                        "transcript_path": str(proof_dir / "terminal-transcript.txt"),
                        "summary_path": str(proof_dir / "README.md"),
                        "capture_checklist_path": str(proof_dir / "CAPTURE_CHECKLIST.md"),
                        "launch_asset_board_path": str(proof_dir / "LAUNCH_ASSET_BOARD.html"),
                        "launch_assets_dir_path": str(proof_dir / "assets"),
                        "public_verify_handoff_path": str(proof_dir / "PUBLIC_VERIFY_HANDOFF.md"),
                        "public_verify_checklist_path": str(proof_dir / "PUBLIC_VERIFY_CHECKLIST.md"),
                        "public_verify_script_path": str(proof_dir / "PUBLIC_VERIFY_COMMANDS.sh"),
                        "operator_packet": {
                            "ready": True,
                            "details": "16/16 files packed",
                        },
                        "public_verify_logs_dir_path": str(proof_dir / "public-verify-logs"),
                        "public_verify_result_path": str(proof_dir / "public-verify-result.json"),
                        "public_verify_operator_prompt_path": str(proof_dir / "CLEAN_SHELL_OPERATOR_PROMPT.md"),
                        "return_packet_finalize_script_path": str(proof_dir / "FINALIZE_RETURN_PACKET.sh"),
                        "operator_packet_archive_path": str(proof_dir / "public-verify-operator-packet.tar.gz"),
                        "return_packet_archive_path": str(proof_dir / "public-verify-return-packet.tar.gz"),
                        "db_path": str(proof_dir / "memory.sqlite"),
                        "action_id": "act_123",
                        "bundle_path": str(proof_dir / "exports" / "action.bundle.json"),
                        "snapshot_path": str(proof_dir / "exports" / "state.snapshot.json"),
                        "bt_xml_path": str(proof_dir / "bt" / "trace.xml"),
                        "bt_manifest_path": str(proof_dir / "bt" / "manifest.json"),
                        "next_steps": [
                            f'zmem --db "{proof_dir / "memory.sqlite"}" ui',
                            f"open {proof_dir / 'index.html'}",
                        ],
                    }
                )
            finally:
                os.chdir(previous_cwd)

        self.assertIn("Proof dir: .zerker/launch-proof", summary)
        self.assertIn("Manifest: .zerker/launch-proof/launch-proof.json", summary)
        self.assertIn("Launch assets dir: .zerker/launch-proof/assets", summary)
        self.assertIn("Public verify result: .zerker/launch-proof/public-verify-result.json", summary)
        self.assertIn('zmem --db ".zerker/launch-proof/memory.sqlite" ui', summary)
        self.assertIn("open .zerker/launch-proof/index.html", summary)
        self.assertNotIn(str(root), summary)

    def test_prelaunch_next_steps_ready_path_points_at_generated_public_verify_artifacts(self):
        steps = prelaunch_next_steps([], [])

        self.assertIn("verify-operator-packet", steps[0])
        self.assertIn(".zerker/launch-proof/public-verify-operator-packet.tar.gz", steps[0])
        self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", steps[1])
        self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", steps[1])
        self.assertIn("public-verify-operator-packet.tar.gz", steps[1])
        self.assertIn("docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", steps[2])
        self.assertIn("docs/LAUNCH_ASSET_BOARD.html", steps[2])
        self.assertIn(".zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh", steps[3])
        self.assertIn(".zerker/launch-proof/public-verify-logs", steps[3])
        self.assertIn("verify-public-verify", steps[4])
        self.assertIn(".zerker/launch-proof/CAPTURE_CHECKLIST.md", steps[5])
        self.assertIn("verify-launch-assets", steps[5])
        self.assertIn("FINALIZE_RETURN_PACKET.sh", steps[6])
        self.assertIn("verify-return-packet", steps[6])

    def test_prelaunch_next_steps_prioritize_public_verify_before_launch_assets(self):
        steps = prelaunch_next_steps(
            [{"name": "public_verify_evidence", "ok": False, "details": "missing logs"}],
            [{"name": "launch_assets", "ok": False, "details": "pending"}],
        )

        self.assertIn("verify-operator-packet", steps[0])
        self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", steps[1])
        self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", steps[1])
        self.assertIn("public-verify-operator-packet.tar.gz", steps[1])
        self.assertIn("docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", steps[2])
        self.assertIn(".zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh", steps[3])
        self.assertIn("verify-public-verify", steps[4])
        self.assertIn(".zerker/launch-proof/CAPTURE_CHECKLIST.md", steps[5])
        self.assertIn("verify-launch-assets", steps[5])
        self.assertIn("FINALIZE_RETURN_PACKET.sh", steps[6])
        self.assertIn("verify-return-packet", steps[6])

    def test_build_status_next_steps_skips_duplicate_strict_publish_guidance(self):
        steps = build_status_next_steps(
            core_checks={"db": True, "policy": True, "prompt": True, "mcp_config": True, "providers": True},
            proof_ready=True,
            manual_pack_ready=True,
            agents={
                "codex": {"configured": False},
                "claude-code": {"configured": False},
                "openclaw": {"configured": True},
                "hermes": {"configured": False},
                "generic": {"configured": False},
            },
            release_readiness={
                "repo_surface_present": True,
                "launch_proof_ready": True,
                "handoff_ready": True,
                "public_verify_ready": False,
                "launch_assets_ready": False,
                "local_alpha_ready": True,
                "strict_publish_ready": False,
                "strict_publish_next_steps": [
                    "Use `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, save the final screenshots/GIFs under `.zerker/launch-proof/assets/`, then run `zmem verify-launch-assets --summary-only`."
                ],
            },
        )

        self.assertIn("verify-operator-packet", steps[0])
        self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", steps[1])
        self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", steps[1])
        self.assertIn("public-verify-operator-packet.tar.gz", steps[1])
        self.assertIn("docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", steps[2])
        self.assertIn(".zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh", steps[3])
        self.assertEqual(
            steps.count(
                "Use `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, save the final screenshots/GIFs under `.zerker/launch-proof/assets/`, then run `zmem verify-launch-assets --summary-only`."
            ),
            1,
        )
        self.assertEqual(sum("verify-return-packet" in step for step in steps), 1)
        self.assertNotIn("zmem ui", steps)
        self.assertNotIn("zmem agent smoke --agent openclaw", steps)
        self.assertNotIn("zmem agent mcp-smoke --agent openclaw", steps)

    def test_build_status_next_steps_prioritizes_public_verify_validation_before_launch_assets(self):
        steps = build_status_next_steps(
            core_checks={"db": True, "policy": True, "prompt": True, "mcp_config": True, "providers": True},
            proof_ready=True,
            manual_pack_ready=True,
            agents={
                "codex": {"configured": False},
                "claude-code": {"configured": False},
                "openclaw": {"configured": True},
                "hermes": {"configured": False},
                "generic": {"configured": False},
            },
            release_readiness={
                "repo_surface_present": True,
                "launch_proof_ready": True,
                "handoff_ready": True,
                "public_verify_ready": False,
                "launch_assets_ready": False,
                "return_packet_ready": False,
                "local_alpha_ready": True,
                "strict_publish_ready": False,
                "strict_publish_next_steps": prelaunch_next_steps(
                    [{"name": "public_verify_evidence", "ok": False, "details": "missing logs"}],
                    [{"name": "launch_assets", "ok": False, "details": "pending"}],
                ),
            },
        )

        self.assertIn("verify-operator-packet", steps[0])
        self.assertIn("CLEAN_SHELL_OPERATOR_PROMPT.md", steps[1])
        self.assertIn("CLEAN_SHELL_PUBLIC_VERIFY.md", steps[1])
        self.assertIn("public-verify-operator-packet.tar.gz", steps[1])
        self.assertIn("docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md", steps[2])
        self.assertIn(".zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh", steps[3])
        self.assertIn("verify-public-verify", steps[4])
        self.assertIn(".zerker/launch-proof/CAPTURE_CHECKLIST.md", steps[5])
        self.assertIn("verify-launch-assets", steps[5])
        self.assertIn("FINALIZE_RETURN_PACKET.sh", steps[6])
        self.assertIn("verify-return-packet", steps[6])
        self.assertEqual(
            steps.count(
                "Run `zmem verify-public-verify --summary-only` to validate the clean-shell logs and receipt before the launch-asset pass."
            ),
            1,
        )

    def test_build_status_next_steps_keeps_agent_guidance_when_release_gate_is_clear(self):
        steps = build_status_next_steps(
            core_checks={"db": True, "policy": True, "prompt": True, "mcp_config": True, "providers": True},
            proof_ready=True,
            manual_pack_ready=True,
            agents={
                "codex": {"configured": False},
                "claude-code": {"configured": False},
                "openclaw": {"configured": True},
                "hermes": {"configured": False},
                "generic": {"configured": False},
            },
            release_readiness={
                "repo_surface_present": True,
                "launch_proof_ready": True,
                "handoff_ready": True,
                "public_verify_ready": True,
                "launch_assets_ready": True,
                "return_packet_ready": True,
                "local_alpha_ready": True,
                "strict_publish_ready": True,
                "strict_publish_next_steps": [],
            },
        )

        self.assertEqual(
            steps,
            ["zmem ui", "zmem agent smoke --agent openclaw", "zmem agent mcp-smoke --agent openclaw"],
        )

    def test_policy_template_has_schema_and_deny_labels(self):
        template = policy_template()

        self.assertEqual(template["schema"], "zerker.policy.v1")
        self.assertIn("secret", template["deny_labels"])
        self.assertEqual(template["risk_thresholds"]["high"]["min_policy_authority"], "policy")

    def test_write_policy_template_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            first = write_policy_template(path, force=False)
            second = write_policy_template(path, force=False)

            self.assertTrue(first["written"])
            self.assertFalse(second["written"])
            self.assertEqual(json.loads(path.read_text())["schema"], "zerker.policy.v1")

    def test_write_agent_prompt_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENT_PROMPT.md"
            result = write_agent_prompt_template(path, force=False)

            self.assertTrue(result["written"])
            self.assertIn("memory.inject", path.read_text())

    def test_write_json_file_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mcp.json"
            first = write_json_file(path, {"a": 1}, force=False)
            second = write_json_file(path, {"a": 2}, force=False)

            self.assertTrue(first["written"])
            self.assertFalse(second["written"])
            self.assertEqual(json.loads(path.read_text()), {"a": 1})

    def test_install_json_mcp_server_merges_without_overwriting_other_servers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mcp.json"
            path.write_text(json.dumps({"mcpServers": {"treeship": {"command": "npx", "args": ["-y", "@treeship/mcp"]}}}), encoding="utf-8")

            result = install_json_mcp_server(
                path,
                name="zerker-memory",
                server={"command": "zmem", "args": ["--db", "/tmp/memory.sqlite", "mcp"]},
                force=False,
            )

            payload = json.loads(path.read_text())
            self.assertTrue(result["written"])
            self.assertIn("treeship", payload["mcpServers"])
            self.assertEqual(payload["mcpServers"]["zerker-memory"]["command"], "zmem")

    def test_install_codex_mcp_server_appends_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('model = "gpt-5"\n', encoding="utf-8")

            result = install_codex_mcp_server(
                path,
                name="zerker-memory",
                server={"command": "zmem", "args": ["--db", "/tmp/memory.sqlite", "mcp"]},
                force=False,
            )

            self.assertTrue(result["written"])
            contents = path.read_text()
            self.assertIn('[mcp_servers.zerker-memory]', contents)
            self.assertIn('command = "zmem"', contents)

    def test_install_agent_preset_includes_post_install_doctor_for_manual_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = install_agent_preset(
                    "openclaw",
                    name="zerker-memory",
                    command="zmem",
                    db_path=root / ".zerker" / "memory.sqlite",
                    policy_path=root / ".zerker" / "policy.json",
                )
            finally:
                os.chdir(cwd)

        self.assertTrue(result["doctor"]["ok"])
        checks = {check["name"]: check for check in result["doctor"]["checks"]}
        self.assertEqual(checks["agent_openclaw"]["details"], result["config_path"])
        self.assertEqual(checks["agent_prompt"]["details"], result["agent_prompt_path"])

    def test_render_agent_install_summary_includes_post_install_doctor(self):
        summary = render_agent_install_summary(
            {
                "preset": "generic",
                "config_path": ".zerker/agents/generic-mcp.json",
                "agent_prompt_path": ".zerker/AGENT_PROMPT.md",
                "checklist_path": ".zerker/agents/generic-checklist.md",
                "install_preview": {
                    "first_import_step": "Import .zerker/agents/generic-mcp.json if the UI supports whole-file JSON import.",
                    "fallback_import_step": "If whole-file import fails, run zmem agent snippet generic and paste the output as zerker-memory.",
                    "verify_command": "zmem doctor --agent generic",
                    "prompt_step": "Add .zerker/AGENT_PROMPT.md to the agent instructions.",
                },
                "doctor": {
                    "ok": True,
                    "checks": [
                        {"name": "agent_prompt", "ok": True, "details": ".zerker/AGENT_PROMPT.md"},
                        {"name": "agent_generic", "ok": True, "details": ".zerker/agents/generic-mcp.json"},
                    ],
                },
            }
        )

        self.assertIn("Post-install doctor: ok", summary)
        self.assertIn("agent_prompt: ok (.zerker/AGENT_PROMPT.md)", summary)
        self.assertIn("agent_generic: ok (.zerker/agents/generic-mcp.json)", summary)

    def test_codex_mcp_server_block_renders_args(self):
        block = codex_mcp_server_block("zerker-memory", {"command": "zmem", "args": ["--db", "/tmp/memory.sqlite", "mcp"]})

        self.assertIn('[mcp_servers.zerker-memory]', block)
        self.assertIn('args = ["--db", "/tmp/memory.sqlite", "mcp"]', block)

    def test_install_agent_preset_writes_claude_code_target_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "claude-mcp.json"
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = install_agent_preset(
                    "claude-code",
                    name="zerker-memory",
                    command="zmem",
                    db_path=Path(".zerker/memory.sqlite"),
                    policy_path=Path(".zerker/policy.json"),
                    config_path=config_path,
                    force=False,
                )
            finally:
                os.chdir(cwd)

            self.assertTrue(result["config_written"])
            self.assertTrue((root / ".zerker" / "AGENT_PROMPT.md").exists())
            payload = json.loads(config_path.read_text())
            self.assertIn("zerker-memory", payload["mcpServers"])
            self.assertEqual(payload["mcpServers"]["zerker-memory"]["args"][-3:], ["mcp", "--profile", "agent"])

    def test_install_agent_preset_writes_openclaw_json_when_target_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "openclaw-mcp.json"
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = install_agent_preset(
                    "openclaw",
                    name="zerker-memory",
                    command="zmem",
                    db_path=Path(".zerker/memory.sqlite"),
                    policy_path=Path(".zerker/policy.json"),
                    config_path=config_path,
                    force=False,
                )
            finally:
                os.chdir(cwd)

            self.assertTrue(result["config_written"])
            self.assertEqual(result["manual_import"]["target"], "OpenClaw MCP or tool server settings")
            self.assertIn(str(config_path), result["manual_import"]["steps"][1])
            self.assertEqual(result["install_preview"]["verify_command"], f"zmem doctor --agent-config openclaw={config_path}")
            self.assertEqual(Path(result["install_preview"]["import_path"]).resolve(), config_path.resolve())
            self.assertIn("zmem agent snippet openclaw", result["install_preview"]["fallback_import_step"])
            payload = json.loads(config_path.read_text())
            self.assertIn("zerker-memory", payload["mcpServers"])

    def test_install_agent_preset_uses_project_local_default_for_manual_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = install_agent_preset(
                    "openclaw",
                    name="zerker-memory",
                    command="zmem",
                    db_path=Path(".zerker/memory.sqlite"),
                    policy_path=Path(".zerker/policy.json"),
                    force=False,
                )
            finally:
                os.chdir(cwd)

            config_path = root / ".zerker" / "agents" / "openclaw-mcp.json"
            checklist_path = root / ".zerker" / "agents" / "openclaw-checklist.md"
            self.assertEqual(Path(result["config_path"]).resolve(), config_path.resolve())
            self.assertTrue(config_path.exists())
            self.assertEqual(Path(result["checklist_path"]).resolve(), checklist_path.resolve())
            self.assertTrue(checklist_path.exists())
            self.assertEqual(result["install_preview"]["verify_command"], "zmem doctor --agent openclaw")
            self.assertEqual(Path(result["install_preview"]["import_path"]).resolve(), config_path.resolve())
            self.assertIn(str(config_path.resolve()), result["install_preview"]["first_import_step"])
            self.assertIn("zmem doctor --agent openclaw", checklist_path.read_text(encoding="utf-8"))
            payload = json.loads(config_path.read_text())
            self.assertIn("zerker-memory", payload["mcpServers"])

    def test_render_agent_install_summary_for_manual_target_includes_import_and_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = install_agent_preset(
                    "generic",
                    name="zerker-memory",
                    command="zmem",
                    db_path=Path(".zerker/memory.sqlite"),
                    policy_path=Path(".zerker/policy.json"),
                    force=False,
                )
            finally:
                os.chdir(cwd)

        summary = render_agent_install_summary(result)
        self.assertIn("Generic MCP Agent install summary", summary)
        self.assertIn("Checklist:", summary)
        self.assertIn("Fallback: If whole-file import fails, run zmem agent snippet generic", summary)
        self.assertIn("Verify: zmem doctor --agent generic", summary)
        self.assertIn("MCP smoke: zmem agent mcp-smoke --agent generic", summary)

    def test_build_agent_config_preset_includes_manual_import_guide_for_hermes(self):
        result = build_agent_config_preset(
            "hermes",
            name="zerker-memory",
            command="zmem",
            db_path=Path(".zerker/memory.sqlite"),
            policy_path=Path(".zerker/policy.json"),
        )

        self.assertEqual(result["manual_import"]["target"], "Hermes stdio tool or MCP server settings")
        self.assertEqual(result["manual_import"]["steps"][0], "Generate or refresh the export file: zmem agent install hermes")
        self.assertEqual(result["manual_import"]["steps"][1], "Verify the exported config before import: zmem doctor --agent hermes")
        self.assertIn("zmem agent snippet hermes", result["manual_import"]["steps"][3])

    def test_agent_manual_install_command_uses_plain_install_for_default_manual_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                command = agent_manual_install_command("generic")
            finally:
                os.chdir(cwd)

        self.assertEqual(command, "zmem agent install generic")

    def test_agent_manual_verify_command_uses_plain_doctor_for_default_manual_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                verify = agent_manual_verify_command("generic", config_path=agent_export_config_path("generic"))
            finally:
                os.chdir(cwd)

        self.assertEqual(verify, "zmem doctor --agent generic")

    def test_agent_manual_import_guide_uses_default_install_and_verify_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                guide = agent_manual_import_guide("openclaw")
            finally:
                os.chdir(cwd)

        self.assertEqual(guide["steps"][0], "Generate or refresh the export file: zmem agent install openclaw")
        self.assertEqual(guide["steps"][1], "Verify the exported config before import: zmem doctor --agent openclaw")

    def test_render_agent_guide_for_codex_uses_direct_install_flow(self):
        guide = render_agent_guide("codex")

        self.assertIn("Codex setup guide", guide)
        self.assertIn("zmem agent install codex", guide)
        self.assertIn("zmem doctor --agent codex", guide)
        self.assertIn("zmem agent mcp-smoke --agent codex", guide)

    def test_render_agent_guide_for_openclaw_uses_manual_import_flow(self):
        guide = render_agent_guide("openclaw")

        self.assertIn("OpenClaw setup guide", guide)
        self.assertIn("zmem agent install openclaw", guide)
        self.assertNotIn("zmem agent install openclaw --config-path", guide)
        self.assertIn(".zerker/agents/openclaw-mcp.json", guide)
        self.assertIn("zmem doctor --agent openclaw", guide)
        self.assertIn("zmem agent snippet openclaw", guide)
        self.assertIn("Attach .zerker/AGENT_PROMPT.md", guide)

    def test_render_agent_guide_for_generic_uses_generic_smoke_commands(self):
        guide = render_agent_guide("generic")

        self.assertIn("Generic MCP Agent setup guide", guide)
        self.assertIn("zmem agent install generic", guide)
        self.assertNotIn("zmem agent install generic --config-path", guide)
        self.assertIn("zmem agent snippet generic", guide)
        self.assertIn("zmem doctor --agent generic", guide)
        self.assertIn("zmem agent smoke --agent generic", guide)
        self.assertIn("zmem agent mcp-smoke --agent generic", guide)

    def test_create_agent_checklist_writes_default_manual_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = create_agent_checklist(
                    "generic",
                    name="zerker-memory",
                    command="zmem",
                    db_path=Path(".zerker/memory.sqlite"),
                    policy_path=Path(".zerker/policy.json"),
                    force=False,
                )
            finally:
                os.chdir(cwd)

            checklist_path = root / ".zerker" / "agents" / "generic-checklist.md"
            self.assertEqual(Path(result["checklist_path"]).resolve(), checklist_path.resolve())
            self.assertTrue(checklist_path.exists())
            self.assertIn("zmem doctor --agent generic", result["checklist"])
            self.assertIn("zmem agent snippet generic", result["checklist"])
            self.assertIn('  "command": "zmem"', result["checklist"])
            self.assertIn('  "args": [', result["checklist"])
            self.assertIn(".zerker/AGENT_PROMPT.md", checklist_path.read_text(encoding="utf-8"))

    def test_create_manual_agent_pack_writes_all_manual_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = create_manual_agent_pack(
                    name="zerker-memory",
                    command="zmem",
                    db_path=Path(".zerker/memory.sqlite"),
                    policy_path=Path(".zerker/policy.json"),
                    force=False,
                )
            finally:
                os.chdir(cwd)

            pack_path = root / ".zerker" / "agents" / "manual-agent-pack.md"
            self.assertEqual(Path(result["pack_path"]).resolve(), pack_path.resolve())
            self.assertTrue(pack_path.exists())
            self.assertEqual(result["presets"], ["cursor", "openclaw", "hermes", "generic"])
            self.assertIn("zmem doctor --agent cursor --agent openclaw --agent hermes --agent generic", result["pack"])
            for preset in ("cursor", "openclaw", "hermes", "generic"):
                self.assertTrue((root / ".zerker" / "agents" / f"{preset}-mcp.json").exists())
                self.assertTrue((root / ".zerker" / "agents" / f"{preset}-checklist.md").exists())

    def test_render_manual_agent_pack_summary_includes_all_day1_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                result = create_manual_agent_pack(
                    name="zerker-memory",
                    command="zmem",
                    db_path=Path(".zerker/memory.sqlite"),
                    policy_path=Path(".zerker/policy.json"),
                    force=False,
                )
            finally:
                os.chdir(cwd)

            summary = render_manual_agent_pack_summary(result)
            self.assertIn("Manual agent pack summary", summary)
            self.assertIn("Verify all: zmem doctor --agent cursor --agent openclaw --agent hermes --agent generic", summary)
            self.assertIn("Cursor", summary)
            self.assertIn("OpenClaw", summary)
            self.assertIn("Hermes", summary)
            self.assertIn("Generic MCP Agent", summary)
            self.assertIn("Fallback: If whole-file import fails, run zmem agent snippet generic", summary)
            self.assertIn("Post-install doctor: ok", summary)

    def test_provider_import_parser(self):
        args = build_parser().parse_args(
            ["provider", "import", "deploy policy", "--provider", "mem0", "--scope", "project", "--type", "policy"]
        )

        self.assertEqual(args.command, "provider")
        self.assertEqual(args.provider_command, "import")
        self.assertEqual(args.provider, "mem0")
        self.assertEqual(args.scope, "project")
        self.assertEqual(args.type, "policy")

    def test_bt_export_parser(self):
        args = build_parser().parse_args(["bt", "export", "trace_demo", "--out-dir", "/tmp/bt-exports"])

        self.assertEqual(args.command, "bt")
        self.assertEqual(args.bt_command, "export")
        self.assertEqual(args.trace_id, "trace_demo")
        self.assertEqual(str(args.out_dir), "/tmp/bt-exports")

    def test_provider_doctor_parser(self):
        args = build_parser().parse_args(
            [
                "provider",
                "doctor",
                "--live",
                "--provider",
                "mem0",
                "--provider",
                "zep",
                "--query",
                "provider smoke",
                "--user-id",
                "u-1",
                "--limit",
                "2",
                "--mem0-base-url",
                "http://mem0.local",
                "--mem0-query",
                "mem0 smoke",
                "--zep-base-url",
                "http://zep.local",
                "--zep-user-id",
                "zep-user",
            ]
        )

        self.assertEqual(args.command, "provider")
        self.assertEqual(args.provider_command, "doctor")
        self.assertTrue(args.live)
        self.assertEqual(args.provider, ["mem0", "zep"])
        self.assertEqual(args.query, "provider smoke")
        self.assertEqual(args.user_id, "u-1")
        self.assertEqual(args.limit, 2)
        self.assertEqual(args.mem0_base_url, "http://mem0.local")
        self.assertEqual(args.mem0_query, "mem0 smoke")
        self.assertEqual(args.zep_base_url, "http://zep.local")
        self.assertEqual(args.zep_user_id, "zep-user")

    def test_retrieval_provider_doctor_parser(self):
        args = build_parser().parse_args(
            [
                "retrieval-providers",
                "doctor",
                "--config",
                "/tmp/retrieval-providers.json",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "retrieval-providers")
        self.assertEqual(args.retrieval_providers_command, "doctor")
        self.assertEqual(str(args.config), "/tmp/retrieval-providers.json")
        self.assertTrue(args.summary_only)

    def test_retrieval_provider_readiness_does_not_print_secret_values(self):
        sentinel = "sk-zmem-secret-sentinel-do-not-print"
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "retrieval-providers.json"
            config_path.write_text(json.dumps(retrieval_provider_config_template()), encoding="utf-8")
            result = build_retrieval_provider_readiness_report(
                config_path=config_path,
                env={"OPENAI_API_KEY": sentinel},
            )
            summary = render_retrieval_provider_readiness_summary(result)
            payload = json.dumps(result, sort_keys=True)

        self.assertIn("OPENAI_API_KEY", summary)
        self.assertIn("api_key_ready=yes", summary)
        self.assertNotIn(sentinel, summary)
        self.assertNotIn(sentinel, payload)

    def test_provider_search_parser_supports_zep(self):
        args = build_parser().parse_args(["provider", "search", "latest notes", "--provider", "zep", "--zep-base-url", "http://zep.local"])

        self.assertEqual(args.provider, "zep")
        self.assertEqual(args.zep_base_url, "http://zep.local")

    def test_init_parser_supports_provider_config(self):
        args = build_parser().parse_args(["init", "--with-provider-config"])

        self.assertEqual(args.command, "init")
        self.assertTrue(args.with_provider_config)

    def test_treeship_publish_parser(self):
        args = build_parser().parse_args(
            [
                "treeship",
                "publish",
                "act_123",
                "--command-template",
                "treeship prove {statement} --action {action_id}",
                "--dry-run",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "treeship")
        self.assertEqual(args.treeship_command, "publish")
        self.assertEqual(args.action_id, "act_123")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.summary_only)
        self.assertEqual(args.command_template, "treeship prove {statement} --action {action_id}")

    def test_treeship_publish_summary_only_surfaces_verified_export_and_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            statement_path = Path(tmp) / "publish.statement.json"
            displayed_statement_path = str(statement_path)
            store = MemoryStore(db_path)
            store.init()
            memory = store.remember(
                "Production deploys require approval",
                memory_type="policy",
                scope="project",
                source_kind="human",
                status="active",
            )
            receipt = store.inject("deploy service to production", agent_id="codex", risk="high", scope="project")

            output = io.StringIO()
            with patch("zerker_memory.treeship.shutil.which", return_value="/usr/local/bin/treeship"):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "--db",
                            str(db_path),
                            "treeship",
                            "publish",
                            receipt["action_id"],
                            "--dry-run",
                            "--out",
                            str(statement_path),
                            "--summary-only",
                        ]
                    )

            summary = output.getvalue()
            statement_exists = statement_path.exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(statement_exists)
        self.assertIn("Treeship publish", summary)
        self.assertIn("Ready: yes", summary)
        self.assertIn("Dry run: yes", summary)
        self.assertIn(f"Action id: {receipt['action_id']}", summary)
        self.assertIn(f"Statement: {displayed_statement_path}", summary)
        self.assertIn("Statement kind: zerker.memory.action_receipt", summary)
        self.assertIn("Bundle verify: ok", summary)
        self.assertIn("Executable: /usr/local/bin/treeship", summary)
        self.assertIn(
            f"Command: treeship attest receipt --system system://zmem --kind memory.proof --payload-file {displayed_statement_path}",
            summary,
        )
        self.assertIn("Trusted provenance: verified", summary)
        self.assertIn("Semantic truth: not guaranteed", summary)

    def test_provider_overrides_reads_all_supported_provider_flags(self):
        args = build_parser().parse_args(
            [
                "external-search",
                "deploy policy",
                "--provider",
                "zep",
                "--mem0-base-url",
                "http://mem0.local",
                "--zep-base-url",
                "http://zep.local",
                "--zep-api-key",
                "token",
            ]
        )

        self.assertEqual(
            provider_overrides(args),
            {
                "mem0": {"base_url": "http://mem0.local", "api_key": None},
                "zep": {"base_url": "http://zep.local", "api_key": "token"},
            },
        )

    def test_provider_live_overrides_include_per_provider_query_and_user_id(self):
        args = build_parser().parse_args(
            [
                "provider",
                "doctor",
                "--mem0-query",
                "mem0 smoke",
                "--mem0-user-id",
                "mem0-user",
                "--zep-query",
                "zep smoke",
            ]
        )

        self.assertEqual(
            provider_live_overrides(args),
            {
                "mem0": {
                    "base_url": None,
                    "api_key": None,
                    "query": "mem0 smoke",
                    "user_id": "mem0-user",
                },
                "zep": {
                    "base_url": None,
                    "api_key": None,
                    "query": "zep smoke",
                    "user_id": None,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
