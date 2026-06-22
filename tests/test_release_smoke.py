import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.release_smoke import (
    build_live_provider_doctor_command,
    create_venv_pth_install,
    create_local_wrappers,
    ensure_bootstrap_contract,
    ensure_launch_plan_contract,
    ensure_install_mode,
    ensure_launch_proof_manifest_status,
    ensure_launch_proof_summary,
    ensure_launch_assets_summary,
    ensure_operator_packet_summary,
    ensure_public_verify_result_summary_artifact,
    ensure_public_verify_summary,
    ensure_prelaunch_public_verify_block,
    ensure_prelaunch_publish_ready,
    ensure_release_pack_summary,
    ensure_return_packet_summary,
    ensure_status_summary,
    install_editable_with_fallback,
    install_mode_satisfies_requirement,
    live_provider_env,
    live_provider_selection,
    pick_supported_python,
    python_supports_version,
    repo_python_env,
    reexec_with_supported_python,
    run_release_smoke_summary,
    run_python_module_entrypoint_smoke,
    run_mcp_smoke,
)
from zerker_memory.cli import main as cli_main


class ReleaseSmokeTest(unittest.TestCase):
    def test_ensure_status_summary_requires_status_heading(self):
        ensure_status_summary("Zerker Memory status\nWorkspace: ready\n", source="examples/first_run.sh")

        with self.assertRaises(SystemExit) as ctx:
            ensure_status_summary("no readiness output here", source="examples/first_run.sh")

        self.assertIn("examples/first_run.sh did not print the readiness summary", str(ctx.exception))

    def test_ensure_release_pack_summary_requires_strict_human_output(self):
        ensure_release_pack_summary(
            "Zerker Memory release pack\nLaunch proof: ok\nPublic verify: pending\nLaunch assets: pending\nOperator packet: ok\nOperator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\nExpected public repo: https://github.com/zerkerlabs/zmem\nExpected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh\nOpen first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\nRunbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\nPhase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\nDurable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\nDurable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\nDurable launch asset board: docs/LAUNCH_ASSET_BOARD.html\nDurable launch asset prompt: docs/LAUNCH_ASSET_OPERATOR_PROMPT.md\nForward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\nRequired install mode: packaged\nCommand log map:\n- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n  Confirm: Reports `Ready: yes` before the live public proof steps start.\n- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n  Confirm: Ends on `Zerker Memory status`.\nLaunch asset board: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html\nExpected launch assets:\n- install-status.png from install-status -> assets/install-status.png\nReturn packet finalize: .zerker/launch-proof/FINALIZE_RETURN_PACKET.sh\nReturn packet archive: .zerker/launch-proof/public-verify-return-packet.tar.gz\nReturn packet: pending\nPrelaunch: blocked\n",
            source="release-pack summary-only",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_release_pack_summary(
                'Zerker Memory release pack\nLaunch proof: ok\nPublic verify: pending\nLaunch assets: pending\nOperator packet: ok\nOperator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\nExpected public repo: https://github.com/zerkerlabs/zmem\nExpected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh\nOpen first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\nRunbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\nPhase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\nDurable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\nDurable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\nDurable launch asset board: docs/LAUNCH_ASSET_BOARD.html\nDurable launch asset prompt: docs/LAUNCH_ASSET_OPERATOR_PROMPT.md\nForward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\nRequired install mode: packaged\nCommand log map:\n- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n  Confirm: Reports `Ready: yes` before the live public proof steps start.\n- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n  Confirm: Ends on `Zerker Memory status`.\nLaunch asset board: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html\nExpected launch assets:\n- install-status.png from install-status -> assets/install-status.png\nReturn packet finalize: .zerker/launch-proof/FINALIZE_RETURN_PACKET.sh\nReturn packet archive: .zerker/launch-proof/public-verify-return-packet.tar.gz\nReturn packet: pending\nPrelaunch: blocked\n{"schema":"zerker.release_pack.v1"}\n',
                source="release-pack summary-only",
            )

        self.assertIn("should not include JSON output", str(ctx.exception))

    def test_ensure_launch_proof_summary_requires_strict_human_output(self):
        ensure_launch_proof_summary(
            "Zerker Memory launch proof\nReady: yes\nManifest: .zerker/launch-proof/launch-proof.json\nReport: .zerker/launch-proof/index.html\nLaunch asset handoff: .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md\nReceive-side handoff: .zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md\nPublic verify logs dir: .zerker/launch-proof/public-verify-logs\nPublic verify result: .zerker/launch-proof/public-verify-result.json\nOperator packet: ok\nOperator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\nPhase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\nDurable launch asset board: docs/LAUNCH_ASSET_BOARD.html\nReturn packet finalize: .zerker/launch-proof/FINALIZE_RETURN_PACKET.sh\nReturn packet: pending\n",
            source="launch-proof summary-only",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_launch_proof_summary(
                'Zerker Memory launch proof\nReady: yes\nManifest: .zerker/launch-proof/launch-proof.json\nReport: .zerker/launch-proof/index.html\nLaunch asset handoff: .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md\nReceive-side handoff: .zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md\nPublic verify logs dir: .zerker/launch-proof/public-verify-logs\nPublic verify result: .zerker/launch-proof/public-verify-result.json\nOperator packet: ok\nOperator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\nPhase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\nDurable launch asset board: docs/LAUNCH_ASSET_BOARD.html\nReturn packet finalize: .zerker/launch-proof/FINALIZE_RETURN_PACKET.sh\nReturn packet: pending\n{"schema":"zerker.launch_proof.v1"}\n',
                source="launch-proof summary-only",
            )

        self.assertIn("should not include JSON output", str(ctx.exception))

    def test_ensure_launch_proof_summary_requires_public_verify_logs_dir(self):
        with self.assertRaises(SystemExit) as ctx:
            ensure_launch_proof_summary(
                "Zerker Memory launch proof\nReady: yes\nManifest: .zerker/launch-proof/launch-proof.json\nReport: .zerker/launch-proof/index.html\nLaunch asset handoff: .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md\nReceive-side handoff: .zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md\n",
                source="launch-proof summary-only",
            )

        self.assertIn("missing public verify logs dir", str(ctx.exception))

    def test_ensure_operator_packet_summary_requires_strict_human_output(self):
        ensure_operator_packet_summary(
            "Zerker Memory operator packet\nReady: yes\nArchive: .zerker/launch-proof/public-verify-operator-packet.tar.gz\nManifest: launch-proof.json\nDetails: 16/16 files packed\nRequired install mode: packaged\nPublic verify script: PUBLIC_VERIFY_COMMANDS.sh\nExpected logs dir: public-verify-logs\nExpected logs:\n- operator-packet-verify.log\nCommand log map:\n- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n  Confirm: Reports `Ready: yes` before the live public proof steps start.\n- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n  Confirm: Ends on `Zerker Memory status`.\n- `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`\n  Confirm: Passes with `install_mode` satisfying `packaged` and without `local-wrappers` fallback.\nLocal alpha gate: ok with warnings (launch_assets, public_verify_evidence)\nStrict publish gate: blocked (launch_assets, public_verify_evidence)\nResult receipt: public-verify-result.json\nRun summary: public-verify-summary.md\nOperator prompt: CLEAN_SHELL_OPERATOR_PROMPT.md\nOpen first: CLEAN_SHELL_PUBLIC_VERIFY.md\nRunbook: CLEAN_SHELL_PUBLIC_VERIFY.md\nPhase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\nDurable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\nDurable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\nDurable launch asset board: docs/LAUNCH_ASSET_BOARD.html\nUnpack into repo: mkdir -p .zerker/launch-proof && tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof\nForward together: CLEAN_SHELL_OPERATOR_PROMPT.md, CLEAN_SHELL_PUBLIC_VERIFY.md, and public-verify-operator-packet.tar.gz\nLaunch assets dir: assets\nExpected launch assets:\n- install-status.png from install-status -> assets/install-status.png\nReturn packet finalize: FINALIZE_RETURN_PACKET.sh\nReturn packet archive: public-verify-return-packet.tar.gz\n",
            source="verify-operator-packet summary-only",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_operator_packet_summary(
                'Zerker Memory operator packet\nReady: yes\nArchive: .zerker/launch-proof/public-verify-operator-packet.tar.gz\nManifest: launch-proof.json\nDetails: 16/16 files packed\nRequired install mode: packaged\nPublic verify script: PUBLIC_VERIFY_COMMANDS.sh\nExpected logs dir: public-verify-logs\nExpected logs:\n- operator-packet-verify.log\nCommand log map:\n- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n  Confirm: Reports `Ready: yes` before the live public proof steps start.\n- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n  Confirm: Ends on `Zerker Memory status`.\n- `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`\n  Confirm: Passes with `install_mode` satisfying `packaged` and without `local-wrappers` fallback.\nLocal alpha gate: ok with warnings (launch_assets, public_verify_evidence)\nStrict publish gate: blocked (launch_assets, public_verify_evidence)\nResult receipt: public-verify-result.json\nRun summary: public-verify-summary.md\nOperator prompt: CLEAN_SHELL_OPERATOR_PROMPT.md\nOpen first: CLEAN_SHELL_PUBLIC_VERIFY.md\nRunbook: CLEAN_SHELL_PUBLIC_VERIFY.md\nPhase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\nDurable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\nDurable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\nDurable launch asset board: docs/LAUNCH_ASSET_BOARD.html\nUnpack into repo: mkdir -p .zerker/launch-proof && tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof\nForward together: CLEAN_SHELL_OPERATOR_PROMPT.md, CLEAN_SHELL_PUBLIC_VERIFY.md, and public-verify-operator-packet.tar.gz\nLaunch assets dir: assets\nExpected launch assets:\n- install-status.png from install-status -> assets/install-status.png\nReturn packet finalize: FINALIZE_RETURN_PACKET.sh\nReturn packet archive: public-verify-return-packet.tar.gz\n{"schema":"zerker.operator_packet_verify.v1"}\n',
                source="verify-operator-packet summary-only",
            )

        self.assertIn("should not include JSON output", str(ctx.exception))

    def test_ensure_public_verify_summary_requires_strict_human_output(self):
        ensure_public_verify_summary(
            "Zerker Memory public verify\nReady: no\nLogs dir: .zerker/launch-proof/public-verify-logs\n"
            "Result receipt: .zerker/launch-proof/public-verify-result.json\n"
            "Run summary: .zerker/launch-proof/public-verify-summary.md\n"
            "Checklist: .zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md\n"
            "Handoff: .zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md\n"
            "Operator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\n"
            "Open first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
            "Runbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
            "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\n"
            "Durable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
            "Durable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\n"
            "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html\n"
            "Durable launch asset prompt: docs/LAUNCH_ASSET_OPERATOR_PROMPT.md\n"
            "Unpack into repo: mkdir -p .zerker/launch-proof && tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof\n"
            "Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\n"
            "Required install mode: packaged\n"
            "Command log map:\n"
            "- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n"
            "  Confirm: Reports `Ready: yes` before the live public proof steps start.\n"
            "- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n"
            "  Confirm: Ends on `Zerker Memory status`.\n"
            "- `zmem prelaunch` -> `public-verify-logs/prelaunch.log`\n"
            "  Confirm: Passes without placeholder warnings before tagging.\n"
            "Logs: failed (0/6 captured)\nDetails: missing logs: operator-packet-verify.log, curl-install.log, first-run.log, ...\n",
            source="public-verify summary-only",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_public_verify_summary(
                'Zerker Memory public verify\nReady: no\nLogs dir: .zerker/launch-proof/public-verify-logs\n'
                'Result receipt: .zerker/launch-proof/public-verify-result.json\n'
                'Run summary: .zerker/launch-proof/public-verify-summary.md\n'
                'Checklist: .zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md\n'
                'Handoff: .zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md\n'
                'Operator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\n'
                'Open first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n'
                'Runbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n'
                'Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\n'
                'Durable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\n'
                'Durable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\n'
                'Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html\n'
                'Durable launch asset prompt: docs/LAUNCH_ASSET_OPERATOR_PROMPT.md\n'
                'Unpack into repo: mkdir -p .zerker/launch-proof && tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof\n'
                'Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\n'
                'Required install mode: packaged\n'
                'Command log map:\n'
                '- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n'
                '  Confirm: Reports `Ready: yes` before the live public proof steps start.\n'
                '- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n'
                '  Confirm: Ends on `Zerker Memory status`.\n'
                '- `zmem prelaunch` -> `public-verify-logs/prelaunch.log`\n'
                '  Confirm: Passes without placeholder warnings before tagging.\n'
                'Logs: failed (0/6 captured)\nDetails: missing logs: operator-packet-verify.log, curl-install.log, first-run.log, ...\n{"schema":"zerker.public_verify_verify.v1"}\n',
                source="public-verify summary-only",
            )

        self.assertIn("should not include JSON output", str(ctx.exception))

    def test_ensure_public_verify_result_summary_artifact_requires_handoff_contract(self):
        ensure_public_verify_result_summary_artifact(
            "# Zerker Memory Public Verify Run Summary\n\n"
            "- Open first: `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`\n"
            "- Operator prompt: `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`\n"
            "- Outbound packet: `.zerker/launch-proof/public-verify-operator-packet.tar.gz`\n"
            "- Verify outbound packet: `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`\n"
            "- Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\n"
            "- Verify before asset pass: `zmem verify-public-verify --summary-only`\n"
            "- Verify after asset capture: `zmem verify-launch-assets --summary-only`\n"
            "- Receive-side accept: `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`\n"
            "\n## Command Log Map\n\n"
            "1. `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n"
            "   Confirm: Reports `Ready: yes` before the live public proof steps start.\n"
            "2. `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n"
            "   Confirm: Ends on `Zerker Memory status`.\n"
            "3. `bash examples/first_run.sh` -> `public-verify-logs/first-run.log`\n"
            "   Confirm: Ends on `Manual pack ready: yes`.\n"
            "4. `zmem release-pack --summary-only` -> `public-verify-logs/release-pack.log`\n"
            "   Confirm: Shows the public verify script, operator packet, and `Prelaunch: blocked` pending external proof.\n"
            "5. `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`\n"
            "   Confirm: Passes with `install_mode` satisfying `packaged` and without `local-wrappers` fallback.\n"
            "6. `zmem prelaunch` -> `public-verify-logs/prelaunch.log`\n"
            "   Confirm: Passes without placeholder warnings before tagging.\n",
            source="public-verify-summary.md",
        )

    def test_ensure_return_packet_summary_requires_strict_human_output(self):
        ensure_return_packet_summary(
            "Zerker Memory return packet\nReady: no\nArchive: .zerker/launch-proof/public-verify-return-packet.tar.gz\nReceive-side handoff: .zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md\nPublic verify logs dir: public-verify-logs\nPublic verify: failed (0/6 logs)\nLaunch assets: failed (0/8 assets)\nDetails: missing logs: operator-packet-verify.log, curl-install.log, first-run.log, ...\nRequired install mode: packaged\nExpected public repo: https://github.com/zerkerlabs/zmem\nExpected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh\nReturn packet finalize: FINALIZE_RETURN_PACKET.sh\nIf not ready, sender should rerun `zmem verify-public-verify --summary-only`, `zmem verify-launch-assets --summary-only`, then `FINALIZE_RETURN_PACKET.sh` before handback.\n",
            source="verify-return-packet summary-only",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_return_packet_summary(
                'Zerker Memory return packet\nReady: no\nArchive: .zerker/launch-proof/public-verify-return-packet.tar.gz\nReceive-side handoff: .zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md\nPublic verify logs dir: public-verify-logs\nPublic verify: failed (0/6 logs)\nLaunch assets: failed (0/8 assets)\nDetails: missing logs: operator-packet-verify.log, curl-install.log, first-run.log, ...\nRequired install mode: packaged\nExpected public repo: https://github.com/zerkerlabs/zmem\nExpected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh\nReturn packet finalize: FINALIZE_RETURN_PACKET.sh\nIf not ready, sender should rerun `zmem verify-public-verify --summary-only`, `zmem verify-launch-assets --summary-only`, then `FINALIZE_RETURN_PACKET.sh` before handback.\n{"schema":"zerker.return_packet_verify.v1"}\n',
                source="verify-return-packet summary-only",
            )

        self.assertIn("should not include JSON output", str(ctx.exception))

    def test_ensure_launch_assets_summary_requires_strict_human_output(self):
        ensure_launch_assets_summary(
            "Zerker Memory launch assets\nReady: no\nOutputs dir: .zerker/launch-proof/assets\nChecklist: .zerker/launch-proof/CAPTURE_CHECKLIST.md\nBoard: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html\nHandoff: .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md\nAssets: failed (0/8 captured)\nDetails: 0/8 captured in .zerker/launch-proof/assets; missing install-status.png\nExpected launch assets:\n- install-status.png from install-status -> assets/install-status.png\n  Command: bash install.sh\n  Capture: End on `Zerker Memory status`.\n",
            source="verify-launch-assets summary-only",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_launch_assets_summary(
                'Zerker Memory launch assets\nReady: no\nOutputs dir: .zerker/launch-proof/assets\nChecklist: .zerker/launch-proof/CAPTURE_CHECKLIST.md\nBoard: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html\nHandoff: .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md\nAssets: failed (0/8 captured)\nDetails: 0/8 captured in .zerker/launch-proof/assets; missing install-status.png\nExpected launch assets:\n- install-status.png from install-status -> assets/install-status.png\n  Command: bash install.sh\n  Capture: End on `Zerker Memory status`.\n{"schema":"zerker.launch_assets_verify.v1"}\n',
                source="verify-launch-assets summary-only",
            )

        self.assertIn("should not include JSON output", str(ctx.exception))

    def test_ensure_launch_proof_manifest_status_requires_public_verify_contract(self):
        payload = {
            "status_summary": "Release:\n  Launch proof: ok\n  Local alpha gate: ready\n",
            "launch_assets_dir_path": "assets",
            "launch_asset_handoff_path": "LAUNCH_ASSET_HANDOFF.md",
            "public_verify_handoff_path": "PUBLIC_VERIFY_HANDOFF.md",
            "receive_verify_handoff_path": "RECEIVE_VERIFY_HANDOFF.md",
            "operator_packet_archive_path": "public-verify-operator-packet.tar.gz",
            "public_verify_operator_prompt_path": "CLEAN_SHELL_OPERATOR_PROMPT.md",
            "return_packet_finalize_script_path": "FINALIZE_RETURN_PACKET.sh",
            "public_verify": {
                "install_mode_requirement": "packaged",
                "handoff_path": "PUBLIC_VERIFY_HANDOFF.md",
                "receive_verify_handoff_path": "RECEIVE_VERIFY_HANDOFF.md",
                "result_path": "public-verify-result.json",
                "operator_prompt_path": "CLEAN_SHELL_OPERATOR_PROMPT.md",
                "finalize_script_path": "FINALIZE_RETURN_PACKET.sh",
                "expected_log_files": [
                    "curl-install.log",
                    "first-run.log",
                    "release-pack.log",
                    "packaged-release-smoke.log",
                    "prelaunch.log",
                ],
            },
            "public_verify_operator_prompt_path": "CLEAN_SHELL_OPERATOR_PROMPT.md",
            "return_packet": {
                "manifest_path": "launch-proof.json",
                "public_verify_logs_dir_path": "public-verify-logs",
                "public_verify_result_path": "public-verify-result.json",
                "launch_assets_dir_path": "assets",
                "archive_path": "public-verify-return-packet.tar.gz",
                "finalize_script_path": "FINALIZE_RETURN_PACKET.sh",
            },
            "return_packet_archive_path": "public-verify-return-packet.tar.gz",
            "launch_assets": [
                {"id": "ui-release-pack", "deliverable": "ui-release-pack.gif", "output_path": "assets/ui-release-pack.gif"},
                {"id": "ui-handoff-restore", "deliverable": "ui-handoff-restore.gif", "output_path": "assets/ui-handoff-restore.gif"},
            ],
        }

        ensure_launch_proof_manifest_status(payload, source="launch-proof")

        with self.assertRaises(SystemExit) as ctx:
            ensure_launch_proof_manifest_status({"status_summary": payload["status_summary"]}, source="launch-proof")

        self.assertIn("missing public verify contract", str(ctx.exception))

    def test_ensure_prelaunch_publish_ready_requires_strict_publish_gate(self):
        ensure_prelaunch_publish_ready(
            "Zerker Memory prelaunch\nReady to publish: yes\n- public_urls: ok (no placeholders)\nNext:\n- Run `python3 scripts/release_smoke.py`, then publish the alpha repo/tag.\n",
            source="prelaunch",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_prelaunch_publish_ready(
                "Zerker Memory prelaunch\nReady to publish: no\n- public_urls: ok (no placeholders)\n",
                source="prelaunch",
            )

        self.assertIn("did not pass the strict publish gate", str(ctx.exception))

    def test_ensure_prelaunch_public_verify_block_requires_expected_gate(self):
        ensure_prelaunch_public_verify_block(
            "Zerker Memory prelaunch\nReady to publish: no\n- public_urls: ok (no placeholders)\n- launch_assets: blocker (0/8 captured in .zerker/launch-proof/assets; missing install-status.png, ...)\n- public_verify_evidence: blocker (0/6 logs captured in .zerker/launch-proof/public-verify-logs; missing operator-packet-verify.log, curl-install.log, first-run.log, ...)\n",
            source="prelaunch",
        )

        with self.assertRaises(SystemExit) as ctx:
            ensure_prelaunch_public_verify_block(
                "Zerker Memory prelaunch\nReady to publish: yes\n- public_verify_evidence: blocker (0/6 logs captured in .zerker/launch-proof/public-verify-logs; missing operator-packet-verify.log, curl-install.log, first-run.log, ...)\n",
                source="prelaunch",
            )

        self.assertIn("should remain blocked", str(ctx.exception))

    def test_install_mode_satisfies_packaged_alias(self):
        self.assertTrue(install_mode_satisfies_requirement("editable", "packaged"))
        self.assertTrue(install_mode_satisfies_requirement("editable-no-build-isolation", "packaged"))
        self.assertTrue(install_mode_satisfies_requirement("venv-pth", "packaged"))
        self.assertFalse(install_mode_satisfies_requirement("local-wrappers", "packaged"))

    def test_ensure_install_mode_rejects_wrapper_fallback_for_packaged_requirement(self):
        with self.assertRaises(SystemExit) as ctx:
            ensure_install_mode("local-wrappers", required_mode="packaged")

        self.assertIn("does not satisfy --require-install-mode packaged", str(ctx.exception))

    def test_python_supports_version_checks_minimum(self):
        self.assertTrue(python_supports_version(sys.executable, (sys.version_info.major, sys.version_info.minor)))
        self.assertFalse(python_supports_version(sys.executable, (99, 0)))

    def test_bootstrap_scripts_print_status_summary(self):
        repo = Path(__file__).resolve().parents[1]
        ensure_bootstrap_contract(repo)

    def test_launch_plan_tracks_phase_one_operator_contract(self):
        repo = Path(__file__).resolve().parents[1]
        ensure_launch_plan_contract(repo)

    def test_repo_python_env_prefixes_repo_on_pythonpath(self):
        repo = Path("/tmp/zerker-memory")
        with patch.dict(os.environ, {"PYTHONPATH": "/tmp/existing"}, clear=False):
            env = repo_python_env(repo)

        self.assertEqual(env["PYTHONPATH"], f"{repo}{os.pathsep}/tmp/existing")

    def test_run_release_smoke_summary_prints_phase_one_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            launch_dir = repo / ".zerker" / "launch-proof"
            launch_dir.mkdir(parents=True, exist_ok=True)
            (launch_dir / "public-verify-summary.md").write_text(
                "# Zerker Memory Public Verify Run Summary\n\n"
                "- Open first: `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`\n"
                "- Operator prompt: `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`\n"
                "- Outbound packet: `.zerker/launch-proof/public-verify-operator-packet.tar.gz`\n"
                "- Verify outbound packet: `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`\n"
                "- Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\n"
                "- Verify before asset pass: `zmem verify-public-verify --summary-only`\n"
                "- Verify after asset capture: `zmem verify-launch-assets --summary-only`\n"
                "- Receive-side accept: `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`\n"
                "\n## Command Log Map\n\n"
                "1. `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n"
                "   Confirm: Reports `Ready: yes` before the live public proof steps start.\n"
                "2. `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n"
                "   Confirm: Ends on `Zerker Memory status`.\n"
                "3. `bash examples/first_run.sh` -> `public-verify-logs/first-run.log`\n"
                "   Confirm: Ends on `Manual pack ready: yes`.\n"
                "4. `zmem release-pack --summary-only` -> `public-verify-logs/release-pack.log`\n"
                "   Confirm: Shows the public verify script, operator packet, and `Prelaunch: blocked` pending external proof.\n"
                "5. `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`\n"
                "   Confirm: Passes with `install_mode` satisfying `packaged` and without `local-wrappers` fallback.\n"
                "6. `zmem prelaunch` -> `public-verify-logs/prelaunch.log`\n"
                "   Confirm: Passes without placeholder warnings before tagging.\n",
                encoding="utf-8",
            )
            (launch_dir / "index.html").write_text(
                "<h2>Clean-Shell Public Verify</h2>\n"
                "Operator Prompt\n"
                "CLEAN_SHELL_OPERATOR_PROMPT.md\n"
                "Runbook\n"
                "CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                "Outbound Packet\n"
                "public-verify-operator-packet.tar.gz\n"
                "Forward together:\n",
                encoding="utf-8",
            )
            run_calls: list[list[str]] = []
            capture_calls: list[list[str]] = []

            def fake_run(cmd, *, cwd, env=None):
                run_calls.append(cmd)
                joined = " ".join(cmd)
                self.assertEqual(cwd, repo)
                self.assertIsNotNone(env)
                if " status --summary-only" in joined:
                    status_calls = sum(" status --summary-only" in " ".join(existing) for existing in run_calls)
                    if status_calls == 1:
                        return "Zerker Memory status\nWorkspace ready: yes\nRelease:\n  Launch proof: missing\n"
                    return "Zerker Memory status\nWorkspace ready: yes\nRelease:\n  Launch proof: ok\n"
                if " verify-operator-packet " in joined:
                    return (
                        "Zerker Memory operator packet\nReady: yes\nArchive: .zerker/launch-proof/public-verify-operator-packet.tar.gz\n"
                        "Manifest: launch-proof.json\nDetails: 16/16 files packed\nRequired install mode: packaged\n"
                        "Public verify script: PUBLIC_VERIFY_COMMANDS.sh\nExpected logs dir: public-verify-logs\nExpected logs:\n"
                        "- operator-packet-verify.log\nCommand log map:\n"
                        "- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n"
                        "  Confirm: Reports `Ready: yes` before the live public proof steps start.\n"
                        "- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n"
                        "  Confirm: Ends on `Zerker Memory status`.\n"
                        "- `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`\n"
                        "  Confirm: Passes with `install_mode` satisfying `packaged` and without `local-wrappers` fallback.\n"
                        "Local alpha gate: ok with warnings (launch_assets, public_verify_evidence)\n"
                        "Strict publish gate: blocked (launch_assets, public_verify_evidence)\n"
                        "Result receipt: public-verify-result.json\nRun summary: public-verify-summary.md\nOperator prompt: CLEAN_SHELL_OPERATOR_PROMPT.md\n"
                        "Open first: CLEAN_SHELL_PUBLIC_VERIFY.md\nRunbook: CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\n"
                        "Durable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Durable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\n"
                        "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html\n"
                        "Unpack into repo: mkdir -p .zerker/launch-proof && tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof\n"
                        "Forward together: CLEAN_SHELL_OPERATOR_PROMPT.md, CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\n"
                        "Launch assets dir: assets\nExpected launch assets:\n"
                        "- install-status.png from install-status -> assets/install-status.png\n"
                        "Return packet finalize: FINALIZE_RETURN_PACKET.sh\nReturn packet archive: public-verify-return-packet.tar.gz\n"
                    )
                raise AssertionError(f"unexpected run command: {joined}")

            def fake_run_capture(cmd, *, cwd, env=None):
                capture_calls.append(cmd)
                joined = " ".join(cmd)
                self.assertEqual(cwd, repo)
                self.assertIsNotNone(env)
                if " release-pack --summary-only" in joined:
                    return (
                        "Zerker Memory release pack\nLaunch proof: ok\nPublic verify: pending\nLaunch assets: pending\n"
                        "Operator packet: ok\nOperator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\n"
                        "Expected public repo: https://github.com/zerkerlabs/zmem\n"
                        "Expected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh\n"
                        "Open first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Runbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\n"
                        "Durable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Durable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\n"
                        "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html\n"
                        "Durable launch asset prompt: docs/LAUNCH_ASSET_OPERATOR_PROMPT.md\n"
                        "Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\n"
                        "Required install mode: packaged\n"
                        "Command log map:\n"
                        "- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n"
                        "  Confirm: Reports `Ready: yes` before the live public proof steps start.\n"
                        "- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n"
                        "  Confirm: Ends on `Zerker Memory status`.\n"
                        "Launch asset board: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html\n"
                        "Expected launch assets:\n"
                        "- install-status.png from install-status -> assets/install-status.png\n"
                        "Return packet finalize: .zerker/launch-proof/FINALIZE_RETURN_PACKET.sh\n"
                        "Return packet archive: .zerker/launch-proof/public-verify-return-packet.tar.gz\n"
                        "Return packet: pending\nPrelaunch: blocked\n",
                        1,
                    )
                if " verify-launch-assets --summary-only" in joined:
                    return (
                        "Zerker Memory launch assets\nReady: no\nOutputs dir: .zerker/launch-proof/assets\n"
                        "Checklist: .zerker/launch-proof/CAPTURE_CHECKLIST.md\n"
                        "Board: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html\n"
                        "Handoff: .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md\nAssets: failed (0/8 captured)\n"
                        "Details: 0/8 captured in .zerker/launch-proof/assets; missing install-status.png, ...\n"
                        "Expected launch assets:\n"
                        "- install-status.png from install-status -> assets/install-status.png\n"
                        "  Command: bash install.sh\n"
                        "  Capture: End on `Zerker Memory status`.\n",
                        1,
                    )
                if " verify-public-verify --summary-only" in joined:
                    return (
                        "Zerker Memory public verify\nReady: no\nLogs dir: .zerker/launch-proof/public-verify-logs\n"
                        "Result receipt: .zerker/launch-proof/public-verify-result.json\n"
                        "Run summary: .zerker/launch-proof/public-verify-summary.md\n"
                        "Checklist: .zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md\n"
                        "Handoff: .zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md\n"
                        "Operator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md\n"
                        "Open first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Runbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md\n"
                        "Durable runbook: docs/CLEAN_SHELL_PUBLIC_VERIFY.md\n"
                        "Durable operator prompt: docs/CLEAN_SHELL_OPERATOR_PROMPT.md\n"
                        "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html\n"
                        "Durable launch asset prompt: docs/LAUNCH_ASSET_OPERATOR_PROMPT.md\n"
                        "Unpack into repo: mkdir -p .zerker/launch-proof && tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof\n"
                        "Forward together: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md, .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md, and .zerker/launch-proof/public-verify-operator-packet.tar.gz\n"
                        "Required install mode: packaged\n"
                        "Command log map:\n"
                        "- `python3 -m zerker_memory verify-operator-packet \".zerker/launch-proof/public-verify-operator-packet.tar.gz\" --summary-only` -> `public-verify-logs/operator-packet-verify.log`\n"
                        "  Confirm: Reports `Ready: yes` before the live public proof steps start.\n"
                        "- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`\n"
                        "  Confirm: Ends on `Zerker Memory status`.\n"
                        "- `zmem prelaunch` -> `public-verify-logs/prelaunch.log`\n"
                        "  Confirm: Passes without placeholder warnings before tagging.\n"
                        "Logs: failed (0/6 captured)\n"
                        "Details: missing logs: operator-packet-verify.log, curl-install.log, first-run.log, ...; pending clean-shell public verify run; required install_mode packaged\n",
                        1,
                    )
                if " verify-return-packet " in joined:
                    return (
                        "Zerker Memory return packet\nReady: no\nArchive: .zerker/launch-proof/public-verify-return-packet.tar.gz\n"
                        "Manifest: launch-proof.json\nReceive-side handoff: RECEIVE_VERIFY_HANDOFF.md\nPublic verify logs dir: public-verify-logs\n"
                        "Public verify result: public-verify-result.json\nPublic verify summary: public-verify-summary.md\nPublic verify: failed (0/6 logs)\n"
                        "Launch assets: failed (0/8 assets)\nDetails: pending clean-shell public verify run; missing logs: operator-packet-verify.log, curl-install.log, first-run.log, ...\n"
                        "Required install mode: packaged\nExpected public repo: https://github.com/zerkerlabs/zmem\n"
                        "Expected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh\n"
                        "Return packet finalize: FINALIZE_RETURN_PACKET.sh\n"
                        "If not ready, sender should rerun `zmem verify-public-verify --summary-only`, `zmem verify-launch-assets --summary-only`, then `FINALIZE_RETURN_PACKET.sh` before handback.\n",
                        1,
                    )
                if " prelaunch --summary-only" in joined:
                    return (
                        "Zerker Memory prelaunch\nReady to publish: no\n- public_urls: ok (no placeholders)\n"
                        "- launch_assets: blocker (0/8 captured in .zerker/launch-proof/assets; missing install-status.png, ...)\n"
                        "- public_verify_evidence: blocker (0/6 logs captured in .zerker/launch-proof/public-verify-logs; missing operator-packet-verify.log, curl-install.log, first-run.log, ...)\n",
                        1,
                    )
                raise AssertionError(f"unexpected run_capture command: {joined}")

            with patch("scripts.release_smoke.run", side_effect=fake_run), patch(
                "scripts.release_smoke.run_capture", side_effect=fake_run_capture
            ), patch("scripts.release_smoke.sys.executable", "/usr/bin/python3"), patch.dict(
                os.environ, {"PYTHONPATH": "/tmp/existing"}, clear=False
            ), io.StringIO() as buffer, redirect_stdout(buffer):
                result = run_release_smoke_summary(repo)
                output = buffer.getvalue()

            self.assertEqual(result, 0)
            self.assertIn("Zerker Memory release smoke summary", output)
            self.assertIn(f"Repo: {repo}", output)
            self.assertIn("Python: /usr/bin/python3", output)
            self.assertIn("Release smoke summary checks completed.", output)
            self.assertEqual(len(run_calls), 3)
            self.assertEqual(len(capture_calls), 5)
            self.assertIn(["/usr/bin/python3", "-m", "zerker_memory", "status", "--summary-only"], run_calls)
            self.assertEqual(run_calls[1], ["/usr/bin/python3", "-m", "zerker_memory", "status", "--summary-only"])

    def test_pick_supported_python_prefers_supported_path_candidate(self):
        def fake_run(cmd, **kwargs):
            if cmd[0] == "/usr/local/bin/python3.10":
                return subprocess.CompletedProcess(cmd, 0)
            return subprocess.CompletedProcess(cmd, 1)

        with patch("scripts.release_smoke.shutil.which") as which_mock, patch("scripts.release_smoke.subprocess.run") as run_mock:
            which_mock.side_effect = lambda name: {
                "python3.12": None,
                "python3.11": None,
                "python3.10": "/usr/local/bin/python3.10",
                "python3": "/usr/bin/python3",
                "pyenv": None,
            }.get(name)
            run_mock.side_effect = fake_run

            result = pick_supported_python()

        self.assertEqual(result, "/usr/local/bin/python3.10")

    def test_pick_supported_python_falls_back_to_pyenv(self):
        def fake_run(cmd, **kwargs):
            if cmd[0] == "/usr/local/bin/pyenv":
                if cmd[2] == "3.10":
                    return subprocess.CompletedProcess(cmd, 0, stdout="/Users/test/.pyenv/versions/3.10.15\n")
                return subprocess.CompletedProcess(cmd, 1, stdout="")
            if cmd[0] == "/Users/test/.pyenv/versions/3.10.15/bin/python":
                return subprocess.CompletedProcess(cmd, 0)
            return subprocess.CompletedProcess(cmd, 1)

        with patch("scripts.release_smoke.shutil.which") as which_mock, patch("scripts.release_smoke.subprocess.run") as run_mock, patch(
            "scripts.release_smoke.Path.exists", return_value=True
        ):
            which_mock.side_effect = lambda name: {"python3.12": None, "python3.11": None, "python3.10": None, "python3": None, "pyenv": "/usr/local/bin/pyenv"}.get(name)
            run_mock.side_effect = fake_run

            result = pick_supported_python()

        self.assertEqual(result, "/Users/test/.pyenv/versions/3.10.15/bin/python")

    def test_reexec_with_supported_python_runs_script_with_selected_interpreter(self):
        with patch("scripts.release_smoke.pick_supported_python", return_value="/usr/local/bin/python3.10"), patch(
            "scripts.release_smoke.subprocess.call", return_value=0
        ) as call_mock:
            result = reexec_with_supported_python(["--keep"])

        self.assertEqual(result, 0)
        cmd = call_mock.call_args.args[0]
        self.assertEqual(cmd[0], "/usr/local/bin/python3.10")
        self.assertEqual(cmd[2:], ["--keep"])

    def test_main_uses_sys_argv_when_no_explicit_argv_is_passed(self):
        class FakeParser:
            def __init__(self):
                self.received = None

            def add_argument(self, *args, **kwargs):
                return None

            def parse_args(self, argv):
                self.received = argv
                raise SystemExit(0)

        parser = FakeParser()
        with patch.object(sys, "argv", ["release_smoke.py", "--require-install-mode", "packaged"]), patch(
            "scripts.release_smoke.argparse.ArgumentParser",
            return_value=parser,
        ), patch("scripts.release_smoke.sys.version_info", (3, 10, 0)):
            with self.assertRaises(SystemExit):
                from scripts.release_smoke import main

                main()

        self.assertEqual(parser.received, ["--require-install-mode", "packaged"])

    def test_run_python_module_entrypoint_smoke_uses_repo_on_pythonpath(self):
        with patch("scripts.release_smoke.shutil.which", return_value="/usr/bin/python3"), patch(
            "scripts.release_smoke.run",
            side_effect=[
                '{"ok": true, "schema": "zerker.doctor.v1"}',
                "Zerker Memory status\nWorkspace ready: yes\n",
            ],
        ) as run_mock:
            result = run_python_module_entrypoint_smoke(Path("/tmp/repo"), cwd=Path("/tmp/work"))

        self.assertTrue(result["ok"])
        first_env = run_mock.call_args_list[0].kwargs["env"]
        second_cmd = run_mock.call_args_list[1].args[0]
        self.assertTrue(first_env["PYTHONPATH"].startswith("/tmp/repo"))
        self.assertEqual(second_cmd, ["/usr/bin/python3", "-m", "zerker_memory", "status", "--summary-only", "--skip-eval"])

    def test_live_provider_env_uses_provider_prefix(self):
        env = {
            "ZERKER_PROVIDER_LIVE": "1",
            "ZERKER_PROVIDER_ZEP_BASE_URL": "http://zep.local",
            "ZERKER_PROVIDER_ZEP_API_KEY": "secret",
            "ZERKER_PROVIDER_ZEP_USER_ID": "user-9",
            "ZERKER_PROVIDER_ZEP_QUERY": "zep smoke",
        }
        with patch.dict(os.environ, env, clear=False):
            result = live_provider_env("zep")

        self.assertEqual(
            result,
            {
                "enabled": "1",
                "configured": "1",
                "explicit_query": "zep smoke",
                "base_url": "http://zep.local",
                "api_key": "secret",
                "user_id": "user-9",
                "query": "zep smoke",
            },
        )

    def test_build_live_provider_doctor_command_uses_per_provider_live_flags(self):
        env = {
            "ZERKER_PROVIDER_LIVE": "1",
            "ZERKER_PROVIDER_LIVE_PROVIDERS": "zep",
            "ZERKER_PROVIDER_ZEP_BASE_URL": "http://zep.local",
            "ZERKER_PROVIDER_ZEP_USER_ID": "user-9",
            "ZERKER_PROVIDER_ZEP_QUERY": "zep smoke",
        }
        with patch.dict(os.environ, env, clear=False):
            command, result = build_live_provider_doctor_command(Path("/tmp/zmem"))

        self.assertEqual(
            command,
            [
                "/tmp/zmem",
                "provider",
                "doctor",
                "--live",
                "--provider",
                "zep",
                "--zep-base-url",
                "http://zep.local",
                "--zep-query",
                "zep smoke",
                "--zep-user-id",
                "user-9",
            ],
        )
        self.assertEqual(result["selected_providers"], ["zep"])
        self.assertFalse(result["providers"]["mem0"]["configured"])
        self.assertEqual(result["providers"]["zep"]["user_id"], "user-9")

    def test_build_live_provider_doctor_command_falls_back_to_all_providers_without_specific_overrides(self):
        env = {"ZERKER_PROVIDER_LIVE": "1"}
        with patch.dict(os.environ, env, clear=False):
            command, result = build_live_provider_doctor_command(Path("/tmp/zmem"))

        self.assertEqual(command, ["/tmp/zmem", "provider", "doctor", "--live"])
        self.assertEqual(result["selected_providers"], [])

    def test_install_editable_with_fallback_retries_without_build_isolation(self):
        with patch("scripts.release_smoke.try_run", side_effect=[False, True]) as try_run_mock:
            mode = install_editable_with_fallback(Path("/tmp/venv/bin/python"), Path("/tmp/repo"), cwd=Path("/tmp/work"))

        self.assertEqual(mode, "editable-no-build-isolation")
        self.assertEqual(try_run_mock.call_count, 2)
        self.assertEqual(try_run_mock.call_args_list[1].args[0][-1], "--no-build-isolation")

    def test_install_editable_with_fallback_creates_venv_pth_install_after_install_failures(self):
        with patch("scripts.release_smoke.try_run", side_effect=[False, False]), patch(
            "scripts.release_smoke.create_venv_pth_install"
        ) as create_pth_mock:
            mode = install_editable_with_fallback(Path("/tmp/venv/bin/python"), Path("/tmp/repo"), cwd=Path("/tmp/work"))

        self.assertEqual(mode, "venv-pth")
        create_pth_mock.assert_called_once_with(Path("/tmp/venv"), Path("/tmp/repo"))

    def test_install_editable_with_fallback_creates_local_wrappers_when_venv_pth_install_fails(self):
        with patch("scripts.release_smoke.try_run", side_effect=[False, False]), patch(
            "scripts.release_smoke.create_venv_pth_install", side_effect=OSError("disk full")
        ), patch("scripts.release_smoke.create_local_wrappers") as create_wrappers_mock:
            mode = install_editable_with_fallback(Path("/tmp/venv/bin/python"), Path("/tmp/repo"), cwd=Path("/tmp/work"))

        self.assertEqual(mode, "local-wrappers")
        create_wrappers_mock.assert_called_once_with(Path("/tmp/venv"), Path("/tmp/repo"))

    def test_create_local_wrappers_writes_cli_entrypoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / ".venv"
            bin_dir = venv_dir / "bin"
            bin_dir.mkdir(parents=True)
            python = bin_dir / "python"
            python.write_text("", encoding="utf-8")

            create_local_wrappers(venv_dir, Path("/tmp/repo"))

            zmem = (bin_dir / "zmem").read_text(encoding="utf-8")
            mcp = (bin_dir / "zerker-memory-mcp").read_text(encoding="utf-8")

        self.assertIn('export PYTHONPATH="/tmp/repo${PYTHONPATH:+:$PYTHONPATH}"', zmem)
        self.assertIn('exec "', zmem)
        self.assertIn('-m zerker_memory "$@"', zmem)
        self.assertIn('-m zerker_memory.mcp "$@"', mcp)

    def test_create_venv_pth_install_writes_site_packages_path_and_wrappers(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / ".venv"
            bin_dir = venv_dir / "bin"
            site_packages = venv_dir / "lib" / "python3.10" / "site-packages"
            bin_dir.mkdir(parents=True)
            site_packages.mkdir(parents=True)
            python = bin_dir / "python"
            python.write_text("", encoding="utf-8")
            python.chmod(0o755)

            with patch("scripts.release_smoke.subprocess.run") as run_mock:
                run_mock.return_value = subprocess.CompletedProcess(
                    args=[str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                    returncode=0,
                    stdout=f"{site_packages}\n",
                    stderr="",
                )
                create_venv_pth_install(venv_dir, Path("/tmp/repo"))

            pth = (site_packages / "zerker_memory_repo.pth").read_text(encoding="utf-8")
            zmem = (bin_dir / "zmem").read_text(encoding="utf-8")

        self.assertEqual(pth, "/tmp/repo\n")
        self.assertNotIn("PYTHONPATH", zmem)
        self.assertIn('exec "', zmem)
        self.assertIn('-m zerker_memory "$@"', zmem)

    def test_live_provider_selection_parses_multiple_values(self):
        env = {"ZERKER_PROVIDER_LIVE_PROVIDERS": "zep, mem0 zep"}
        with patch.dict(os.environ, env, clear=False):
            result = live_provider_selection()

        self.assertEqual(result, ["zep", "mem0"])

    def test_run_mcp_smoke_executes_stdio_handshake(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            self.assertEqual(
                cli_main(
                    [
                        "--db",
                        str(db_path),
                        "--policy",
                        str(policy_path),
                        "init",
                        "--with-policy",
                    ]
                ),
                0,
            )

            result = run_mcp_smoke(
                [sys.executable, "-m", "zerker_memory.mcp"],
                cwd=work,
                db_path=db_path,
                policy_path=policy_path,
                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["server"]["name"], "zerker-memory")
        self.assertGreater(result["tool_count"], 0)
        self.assertTrue(result["action_id"])
        self.assertTrue(result["injected_memory_ids"])
        self.assertTrue(result["verified"]["ok"])
        self.assertEqual(result["why"]["injected_memory_ids"], result["injected_memory_ids"])

    def test_agent_snippet_cli_outputs_single_server_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            self.assertEqual(
                cli_main(
                    [
                        "--db",
                        str(db_path),
                        "--policy",
                        str(policy_path),
                        "agent",
                        "snippet",
                        "openclaw",
                    ]
                ),
                0,
            )

    def test_agent_checklist_cli_writes_manual_import_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            cwd = Path.cwd()
            try:
                os.chdir(work)
                self.assertEqual(
                    cli_main(
                        [
                            "--db",
                            str(db_path),
                            "--policy",
                            str(policy_path),
                            "agent",
                            "checklist",
                            "openclaw",
                        ]
                    ),
                    0,
                )
            finally:
                os.chdir(cwd)

            checklist_path = work / ".zerker" / "agents" / "openclaw-checklist.md"
            self.assertTrue(checklist_path.exists())
            checklist = checklist_path.read_text(encoding="utf-8")
            self.assertIn("zmem doctor --agent openclaw", checklist)
            self.assertIn("zmem agent snippet openclaw", checklist)
            self.assertIn('  "command": "zmem"', checklist)
            self.assertIn('  "args": [', checklist)

    def test_agent_install_cli_writes_default_manual_checklist_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            cwd = Path.cwd()
            try:
                os.chdir(work)
                self.assertEqual(
                    cli_main(
                        [
                            "--db",
                            str(db_path),
                            "--policy",
                            str(policy_path),
                            "agent",
                            "install",
                            "generic",
                        ]
                    ),
                    0,
                )
            finally:
                os.chdir(cwd)

            checklist_path = work / ".zerker" / "agents" / "generic-checklist.md"
            self.assertTrue(checklist_path.exists())
            checklist = checklist_path.read_text(encoding="utf-8")
            self.assertIn("zmem doctor --agent generic", checklist)
            self.assertIn("zmem agent snippet generic", checklist)
            self.assertIn('  "command": "zmem"', checklist)
            self.assertIn('  "args": [', checklist)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(
                    cli_main(
                        [
                            "--db",
                            str(db_path),
                            "--policy",
                            str(policy_path),
                            "agent",
                            "install",
                            "generic",
                        ]
                    ),
                    0,
                )
            install_output = json.loads(stdout.getvalue()[stdout.getvalue().find("{") :])
            self.assertTrue(install_output["doctor"]["ok"])
            doctor_checks = {check["name"]: check for check in install_output["doctor"]["checks"]}
            self.assertTrue(doctor_checks["agent_prompt"]["ok"])
            self.assertTrue(doctor_checks["agent_generic"]["ok"])
            self.assertEqual(install_output["install_preview"]["verify_command"], "zmem doctor --agent generic")
            self.assertIn(".zerker/agents/generic-mcp.json", install_output["install_preview"]["first_import_step"])
            self.assertIn("zmem agent snippet generic", install_output["install_preview"]["fallback_import_step"])

    def test_handoff_cli_writes_verified_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            cwd = Path.cwd()
            stdout = io.StringIO()
            try:
                os.chdir(work)
                self.assertEqual(
                    cli_main(
                        [
                            "--db",
                            str(db_path),
                            "--policy",
                            str(policy_path),
                            "init",
                            "--with-policy",
                            "--with-provider-config",
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    cli_main(
                        [
                            "--db",
                            str(db_path),
                            "--policy",
                            str(policy_path),
                            "agent",
                            "smoke",
                            "--agent",
                            "codex",
                        ]
                    ),
                    0,
                )
                with redirect_stdout(stdout):
                    self.assertEqual(
                        cli_main(
                            [
                                "--db",
                                str(db_path),
                                "--policy",
                                str(policy_path),
                                "handoff",
                            ]
                        ),
                        0,
                    )
            finally:
                os.chdir(cwd)

            output = stdout.getvalue()
            result = json.loads(output[output.find("{") :])
            readme_exists = Path(result["readme_path"]).exists()
            snapshot_exists = Path(result["snapshot_path"]).exists()
            bundle_exists = Path(result["bundle_path"]).exists()

        self.assertTrue(result["ok"])
        self.assertTrue(readme_exists)
        self.assertTrue(snapshot_exists)
        self.assertTrue(result["snapshot_verify"]["ok"])
        self.assertTrue(bundle_exists)
        self.assertTrue(result["bundle_verify"]["ok"])

    def test_agent_install_cli_summary_prepends_human_readable_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            stdout = io.StringIO()
            cwd = Path.cwd()
            try:
                os.chdir(work)
                with redirect_stdout(stdout):
                    self.assertEqual(
                        cli_main(
                            [
                                "--db",
                                str(db_path),
                                "--policy",
                                str(policy_path),
                                "agent",
                                "install",
                                "openclaw",
                                "--summary",
                            ]
                        ),
                        0,
                    )
            finally:
                os.chdir(cwd)

            output = stdout.getvalue()
            self.assertIn("OpenClaw install summary", output)
            self.assertIn("Checklist:", output)
            self.assertIn("Post-install doctor: ok", output)
            self.assertIn("Fallback: If whole-file import fails, run zmem agent snippet openclaw", output)
            install_output = json.loads(output[output.find("{") :])
            self.assertEqual(install_output["preset"], "openclaw")

    def test_agent_pack_cli_writes_manual_pack_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            stdout = io.StringIO()
            cwd = Path.cwd()
            try:
                os.chdir(work)
                with redirect_stdout(stdout):
                    self.assertEqual(
                        cli_main(
                            [
                                "--db",
                                str(db_path),
                                "--policy",
                                str(policy_path),
                                "agent",
                                "pack",
                            ]
                        ),
                        0,
                    )
            finally:
                os.chdir(cwd)

            output = json.loads(stdout.getvalue())
            pack_path = work / ".zerker" / "agents" / "manual-agent-pack.md"
            self.assertTrue(pack_path.exists())
            self.assertEqual(output["presets"], ["cursor", "openclaw", "hermes", "generic"])
            self.assertEqual(Path(output["pack_path"]).resolve(), pack_path.resolve())
            pack = pack_path.read_text(encoding="utf-8")
            self.assertIn("zmem doctor --agent cursor --agent openclaw --agent hermes --agent generic", pack)
            self.assertIn("cursor-checklist.md", pack)
            self.assertIn("openclaw-checklist.md", pack)
            self.assertIn("generic-checklist.md", pack)

    def test_agent_pack_cli_summary_only_omits_json_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            stdout = io.StringIO()
            cwd = Path.cwd()
            try:
                os.chdir(work)
                with redirect_stdout(stdout):
                    self.assertEqual(
                        cli_main(
                            [
                                "--db",
                                str(db_path),
                                "--policy",
                                str(policy_path),
                                "agent",
                                "pack",
                                "--summary-only",
                            ]
                        ),
                        0,
                    )
            finally:
                os.chdir(cwd)

            output = stdout.getvalue()
            self.assertIn("Manual agent pack summary", output)
            self.assertIn("Verify all: zmem doctor --agent cursor --agent openclaw --agent hermes --agent generic", output)
            self.assertIn("Cursor", output)
            self.assertIn("Generic MCP Agent", output)
            self.assertIn("Post-install doctor: ok", output)
            self.assertNotIn('"schema": "zerker.agent_pack.v1"', output)
            self.assertNotIn("{", output)

    def test_agent_install_cli_summary_only_omits_json_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            stdout = io.StringIO()
            cwd = Path.cwd()
            try:
                os.chdir(work)
                with redirect_stdout(stdout):
                    self.assertEqual(
                        cli_main(
                            [
                                "--db",
                                str(db_path),
                                "--policy",
                                str(policy_path),
                                "agent",
                                "install",
                                "generic",
                                "--summary-only",
                            ]
                        ),
                        0,
                    )
            finally:
                os.chdir(cwd)

            output = stdout.getvalue()
            self.assertIn("Generic MCP Agent install summary", output)
            self.assertIn("Checklist:", output)
            self.assertNotIn('"schema": "zerker.agent_install.v1"', output)
            self.assertNotIn("{", output)

    def test_launch_proof_cli_summary_only_omits_json_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            db_path = work / ".zerker" / "memory.sqlite"
            policy_path = work / ".zerker" / "policy.json"
            providers_path = work / ".zerker" / "providers.json"
            stdout = io.StringIO()
            cwd = Path.cwd()
            try:
                os.chdir(work)
                with redirect_stdout(stdout):
                    self.assertEqual(
                        cli_main(
                            [
                                "--db",
                                str(db_path),
                                "--policy",
                                str(policy_path),
                                "--providers",
                                str(providers_path),
                                "launch-proof",
                                "--summary-only",
                            ]
                        ),
                        0,
                    )
            finally:
                os.chdir(cwd)

            output = stdout.getvalue()
            self.assertIn("Zerker Memory launch proof", output)
            self.assertIn("Report:", output)
            self.assertIn("BT XML:", output)
            self.assertNotIn('"schema": "zerker.launch_proof.v1"', output)
            self.assertNotIn("{", output)


if __name__ == "__main__":
    unittest.main()
