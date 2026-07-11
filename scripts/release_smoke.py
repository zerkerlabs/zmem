from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any


SUPPORTED_PYTHON_CANDIDATES = ("python3.12", "python3.11", "python3.10", "python3")
MIN_PYTHON_VERSION = (3, 10)
INSTALL_MODE_CHOICES = ("packaged", "editable", "editable-no-build-isolation", "venv-pth", "local-wrappers")


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    print("$ " + " ".join(cmd))
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout.rstrip())
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed.stdout


def run_capture(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> tuple[str, int]:
    print("$ " + " ".join(cmd))
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout.rstrip())
    return completed.stdout, completed.returncode


def try_run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> bool:
    try:
        run(cmd, cwd=cwd, env=env)
    except SystemExit:
        return False
    return True


def create_release_venv(path: Path) -> None:
    # uv-managed standalone Python builds are not relocatable when copied on POSIX.
    venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(path)


def parse_json(output: str) -> dict[str, Any]:
    return json.loads(output[output.find("{") :])


def ensure_status_summary(output: str, *, source: str) -> None:
    if "Zerker Memory status" not in output:
        raise SystemExit(f"{source} did not print the readiness summary")


def ensure_release_pack_summary(output: str, *, source: str) -> None:
    if "Zerker Memory release pack" not in output:
        raise SystemExit(f"{source} missing human-readable heading")
    if "Launch proof: ok" not in output:
        raise SystemExit(f"{source} missing launch-proof status")
    if "Public verify:" not in output:
        raise SystemExit(f"{source} missing public-verify readiness")
    if "Launch assets:" not in output:
        raise SystemExit(f"{source} missing launch-assets readiness")
    if "Operator packet:" not in output:
        raise SystemExit(f"{source} missing operator-packet readiness")
    if "Operator prompt:" not in output:
        raise SystemExit(f"{source} missing operator prompt path")
    if "Expected public repo: https://github.com/zerkerlabs/zmem" not in output:
        raise SystemExit(f"{source} missing expected public repo")
    if "Expected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh" not in output:
        raise SystemExit(f"{source} missing expected raw install URL")
    if "Open first:" not in output:
        raise SystemExit(f"{source} missing open-first runbook path")
    if "Runbook:" not in output:
        raise SystemExit(f"{source} missing runbook path")
    if "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md" not in output:
        raise SystemExit(f"{source} missing durable operator brief path")
    if "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html" not in output:
        raise SystemExit(f"{source} missing durable launch asset board path")
    if "Forward together:" not in output:
        raise SystemExit(f"{source} missing outbound handoff triplet")
    if "Required install mode: packaged" not in output:
        raise SystemExit(f"{source} missing packaged install requirement")
    if "Command log map:" not in output:
        raise SystemExit(f"{source} missing command log map")
    if '- `python3 -m zerker_memory verify-operator-packet ".zerker/launch-proof/public-verify-operator-packet.tar.gz" --summary-only` -> `public-verify-logs/operator-packet-verify.log`' not in output:
        raise SystemExit(f"{source} missing operator-packet preflight log contract")
    if "- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`" not in output:
        raise SystemExit(f"{source} missing curl install command log contract")
    if "Launch asset board:" not in output:
        raise SystemExit(f"{source} missing launch asset board path")
    if "Expected launch assets:" not in output:
        raise SystemExit(f"{source} missing launch asset storyboard")
    if "Return packet finalize:" not in output:
        raise SystemExit(f"{source} missing return packet finalize path")
    if "Return packet archive:" not in output:
        raise SystemExit(f"{source} missing return packet archive path")
    if "Return packet:" not in output:
        raise SystemExit(f"{source} missing return packet readiness")
    if "Prelaunch: blocked" not in output:
        raise SystemExit(f"{source} missing strict prelaunch blocker state")
    if '"schema": "zerker.release_pack.v1"' in output or "{" in output:
        raise SystemExit(f"{source} should not include JSON output")


def ensure_launch_proof_summary(output: str, *, source: str) -> None:
    if "Zerker Memory launch proof" not in output:
        raise SystemExit(f"{source} missing human-readable heading")
    if "Ready: yes" not in output:
        raise SystemExit(f"{source} did not report ready state")
    if "Manifest:" not in output:
        raise SystemExit(f"{source} missing manifest path")
    if "Report:" not in output:
        raise SystemExit(f"{source} missing report path")
    if "Launch asset handoff:" not in output:
        raise SystemExit(f"{source} missing launch asset handoff path")
    if "Receive-side handoff:" not in output:
        raise SystemExit(f"{source} missing receive-side handoff path")
    if "Public verify logs dir:" not in output:
        raise SystemExit(f"{source} missing public verify logs dir")
    if "Public verify result:" not in output:
        raise SystemExit(f"{source} missing public verify result path")
    if "Operator packet:" not in output:
        raise SystemExit(f"{source} missing operator-packet readiness")
    if "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md" not in output:
        raise SystemExit(f"{source} missing durable operator brief path")
    if "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html" not in output:
        raise SystemExit(f"{source} missing durable launch asset board path")
    if "Return packet finalize:" not in output:
        raise SystemExit(f"{source} missing return packet finalize path")
    if "Return packet:" not in output:
        raise SystemExit(f"{source} missing return packet readiness")
    if '"schema": "zerker.launch_proof.v1"' in output or "{" in output:
        raise SystemExit(f"{source} should not include JSON output")


def ensure_operator_packet_summary(output: str, *, source: str) -> None:
    if "Zerker Memory operator packet" not in output:
        raise SystemExit(f"{source} missing human-readable heading")
    if "Ready: yes" not in output:
        raise SystemExit(f"{source} did not report ready state")
    if "Archive:" not in output:
        raise SystemExit(f"{source} missing archive path")
    if "Manifest:" not in output:
        raise SystemExit(f"{source} missing manifest path")
    if "Details:" not in output:
        raise SystemExit(f"{source} missing archive details")
    if "Required install mode: packaged" not in output:
        raise SystemExit(f"{source} missing packaged install requirement")
    if "Public verify script:" not in output:
        raise SystemExit(f"{source} missing public verify script path")
    if "Expected logs dir:" not in output:
        raise SystemExit(f"{source} missing expected logs dir")
    if "Expected logs:" not in output:
        raise SystemExit(f"{source} missing expected log list")
    if "Command log map:" not in output:
        raise SystemExit(f"{source} missing command log map")
    if '- `python3 -m zerker_memory verify-operator-packet ".zerker/launch-proof/public-verify-operator-packet.tar.gz" --summary-only` -> `public-verify-logs/operator-packet-verify.log`' not in output:
        raise SystemExit(f"{source} missing operator-packet preflight log contract")
    if "- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`" not in output:
        raise SystemExit(f"{source} missing curl install command log contract")
    if "- `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`" not in output:
        raise SystemExit(f"{source} missing packaged release-smoke command log contract")
    if "Local alpha gate:" not in output:
        raise SystemExit(f"{source} missing local alpha gate snapshot")
    if "Strict publish gate:" not in output:
        raise SystemExit(f"{source} missing strict publish gate snapshot")
    if "Result receipt:" not in output:
        raise SystemExit(f"{source} missing result receipt path")
    if "Run summary:" not in output:
        raise SystemExit(f"{source} missing run summary path")
    if "Operator prompt:" not in output:
        raise SystemExit(f"{source} missing operator prompt path")
    if "Open first:" not in output:
        raise SystemExit(f"{source} missing open-first runbook path")
    if "Runbook:" not in output:
        raise SystemExit(f"{source} missing runbook path")
    if "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md" not in output:
        raise SystemExit(f"{source} missing durable operator brief path")
    if "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html" not in output:
        raise SystemExit(f"{source} missing durable launch asset board path")
    if "Forward together:" not in output:
        raise SystemExit(f"{source} missing outbound handoff triplet")
    if "Launch assets dir:" not in output:
        raise SystemExit(f"{source} missing launch assets dir")
    if "Expected launch assets:" not in output:
        raise SystemExit(f"{source} missing launch asset storyboard")
    if "Return packet finalize:" not in output:
        raise SystemExit(f"{source} missing return packet finalize path")
    if "Return packet archive:" not in output:
        raise SystemExit(f"{source} missing return packet archive path")
    if '"schema": "zerker.operator_packet_verify.v1"' in output or "{" in output:
        raise SystemExit(f"{source} should not include JSON output")


def ensure_public_verify_summary(output: str, *, source: str) -> None:
    if "Zerker Memory public verify" not in output:
        raise SystemExit(f"{source} missing human-readable heading")
    if "Logs dir:" not in output:
        raise SystemExit(f"{source} missing logs dir")
    if "Result receipt:" not in output:
        raise SystemExit(f"{source} missing result receipt path")
    if "Run summary:" not in output:
        raise SystemExit(f"{source} missing run summary path")
    if "Checklist:" not in output:
        raise SystemExit(f"{source} missing checklist path")
    if "Handoff:" not in output:
        raise SystemExit(f"{source} missing handoff path")
    if "Operator prompt:" not in output:
        raise SystemExit(f"{source} missing operator prompt path")
    if "Open first:" not in output:
        raise SystemExit(f"{source} missing open-first runbook path")
    if "Runbook:" not in output:
        raise SystemExit(f"{source} missing runbook path")
    if "Phase-1 operator brief: docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md" not in output:
        raise SystemExit(f"{source} missing durable operator brief path")
    if "Durable launch asset board: docs/LAUNCH_ASSET_BOARD.html" not in output:
        raise SystemExit(f"{source} missing durable launch asset board path")
    if "Unpack into repo:" not in output:
        raise SystemExit(f"{source} missing unpack command")
    if "Forward together:" not in output:
        raise SystemExit(f"{source} missing outbound handoff triplet")
    if "Required install mode:" not in output:
        raise SystemExit(f"{source} missing required install mode")
    if "Command log map:" not in output:
        raise SystemExit(f"{source} missing command log map")
    if '- `python3 -m zerker_memory verify-operator-packet ".zerker/launch-proof/public-verify-operator-packet.tar.gz" --summary-only` -> `public-verify-logs/operator-packet-verify.log`' not in output:
        raise SystemExit(f"{source} missing operator-packet preflight log contract")
    if "- `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`" not in output:
        raise SystemExit(f"{source} missing curl install command log contract")
    if "- `zmem prelaunch` -> `public-verify-logs/prelaunch.log`" not in output:
        raise SystemExit(f"{source} missing prelaunch command log contract")
    if "Logs:" not in output:
        raise SystemExit(f"{source} missing log readiness")
    if "Details:" not in output:
        raise SystemExit(f"{source} missing verification details")
    if '"schema": "zerker.public_verify_verify.v1"' in output or "{" in output:
        raise SystemExit(f"{source} should not include JSON output")


def ensure_public_verify_result_summary_artifact(output: str, *, source: str) -> None:
    if "# Zerker Memory Public Verify Run Summary" not in output:
        raise SystemExit(f"{source} missing summary heading")
    if "- Open first:" not in output:
        raise SystemExit(f"{source} missing open-first runbook path")
    if "- Operator prompt:" not in output:
        raise SystemExit(f"{source} missing operator prompt path")
    if "- Outbound packet:" not in output:
        raise SystemExit(f"{source} missing outbound packet path")
    if "- Verify outbound packet: `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`" not in output:
        raise SystemExit(f"{source} missing outbound packet verification command")
    if "- Forward together:" not in output:
        raise SystemExit(f"{source} missing outbound handoff triplet")
    if "- Verify before asset pass: `zmem verify-public-verify --summary-only`" not in output:
        raise SystemExit(f"{source} missing verify-public-verify reminder")
    if "- Verify after asset capture: `zmem verify-launch-assets --summary-only`" not in output:
        raise SystemExit(f"{source} missing verify-launch-assets reminder")
    if "- Receive-side accept: `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`" not in output:
        raise SystemExit(f"{source} missing receive-side acceptance command")
    if "## Command Log Map" not in output:
        raise SystemExit(f"{source} missing command log map heading")
    if '1. `python3 -m zerker_memory verify-operator-packet ".zerker/launch-proof/public-verify-operator-packet.tar.gz" --summary-only` -> `public-verify-logs/operator-packet-verify.log`' not in output:
        raise SystemExit(f"{source} missing operator-packet preflight log contract")
    if "2. `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`" not in output:
        raise SystemExit(f"{source} missing curl install log contract")
    if "3. `bash examples/first_run.sh` -> `public-verify-logs/first-run.log`" not in output:
        raise SystemExit(f"{source} missing first-run log contract")
    if "4. `zmem release-pack --summary-only` -> `public-verify-logs/release-pack.log`" not in output:
        raise SystemExit(f"{source} missing release-pack log contract")
    if "5. `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`" not in output:
        raise SystemExit(f"{source} missing packaged release-smoke log contract")
    if "6. `zmem prelaunch` -> `public-verify-logs/prelaunch.log`" not in output:
        raise SystemExit(f"{source} missing prelaunch log contract")


def ensure_launch_proof_report(output: str, *, source: str) -> None:
    if "<h2>Clean-Shell Public Verify</h2>" not in output:
        raise SystemExit(f"{source} missing clean-shell section")
    if "Operator Prompt" not in output:
        raise SystemExit(f"{source} missing operator prompt card")
    if "CLEAN_SHELL_OPERATOR_PROMPT.md" not in output:
        raise SystemExit(f"{source} missing operator prompt path")
    if "Runbook" not in output:
        raise SystemExit(f"{source} missing runbook card")
    if "CLEAN_SHELL_PUBLIC_VERIFY.md" not in output:
        raise SystemExit(f"{source} missing runbook path")
    if "Outbound Packet" not in output:
        raise SystemExit(f"{source} missing outbound packet card")
    if "public-verify-operator-packet.tar.gz" not in output:
        raise SystemExit(f"{source} missing outbound packet path")
    if "Forward together:" not in output:
        raise SystemExit(f"{source} missing outbound handoff summary")


def ensure_return_packet_summary(output: str, *, source: str) -> None:
    if "Zerker Memory return packet" not in output:
        raise SystemExit(f"{source} missing human-readable heading")
    if "Archive:" not in output:
        raise SystemExit(f"{source} missing archive path")
    if "Receive-side handoff:" not in output:
        raise SystemExit(f"{source} missing receive-side handoff path")
    if "Public verify logs dir:" not in output:
        raise SystemExit(f"{source} missing public verify logs dir")
    if "Public verify:" not in output:
        raise SystemExit(f"{source} missing public-verify status")
    if "Launch assets:" not in output:
        raise SystemExit(f"{source} missing launch-assets status")
    if "Details:" not in output:
        raise SystemExit(f"{source} missing verification details")
    if "Required install mode:" not in output:
        raise SystemExit(f"{source} missing required install mode")
    if "Expected public repo:" not in output:
        raise SystemExit(f"{source} missing expected public repo")
    if "Expected raw install URL:" not in output:
        raise SystemExit(f"{source} missing expected raw install URL")
    if "Return packet finalize:" not in output:
        raise SystemExit(f"{source} missing return packet finalize path")
    if "If not ready, sender should rerun" not in output:
        raise SystemExit(f"{source} missing sender rerun contract")
    if '"schema": "zerker.return_packet_verify.v1"' in output or "{" in output:
        raise SystemExit(f"{source} should not include JSON output")


def ensure_launch_assets_summary(output: str, *, source: str) -> None:
    if "Zerker Memory launch assets" not in output:
        raise SystemExit(f"{source} missing human-readable heading")
    if "Outputs dir:" not in output:
        raise SystemExit(f"{source} missing outputs dir")
    if "Checklist:" not in output:
        raise SystemExit(f"{source} missing checklist path")
    if "Board:" not in output:
        raise SystemExit(f"{source} missing board path")
    if "Handoff:" not in output:
        raise SystemExit(f"{source} missing handoff path")
    if "Assets:" not in output:
        raise SystemExit(f"{source} missing asset status")
    if "Details:" not in output:
        raise SystemExit(f"{source} missing verification details")
    if "Expected launch assets:" not in output:
        raise SystemExit(f"{source} missing expected launch asset storyboard")
    if "install-status.png from install-status ->" not in output:
        raise SystemExit(f"{source} missing launch asset deliverable mapping")
    if "Command: bash install.sh" not in output:
        raise SystemExit(f"{source} missing launch asset command cue")
    if "Capture: End on `Zerker Memory status`." not in output:
        raise SystemExit(f"{source} missing launch asset capture cue")
    if '"schema": "zerker.launch_assets_verify.v1"' in output or "{" in output:
        raise SystemExit(f"{source} should not include JSON output")


def ensure_launch_proof_manifest_status(payload: dict[str, Any], *, source: str) -> None:
    status_summary = payload.get("status_summary", "")
    public_verify = payload.get("public_verify")
    return_packet = payload.get("return_packet")
    launch_assets = payload.get("launch_assets")
    launch_assets_dir_path = payload.get("launch_assets_dir_path")
    if not isinstance(public_verify, dict):
        raise SystemExit(f"{source} manifest missing public verify contract")
    if not isinstance(return_packet, dict):
        raise SystemExit(f"{source} manifest missing return packet contract")
    if payload.get("public_verify_handoff_path") != "PUBLIC_VERIFY_HANDOFF.md":
        raise SystemExit(f"{source} manifest missing public verify handoff path")
    if payload.get("receive_verify_handoff_path") != "RECEIVE_VERIFY_HANDOFF.md":
        raise SystemExit(f"{source} manifest missing receive-side handoff path")
    if payload.get("operator_packet_archive_path") != "public-verify-operator-packet.tar.gz":
        raise SystemExit(f"{source} manifest missing operator packet archive path")
    if payload.get("public_verify_operator_prompt_path") != "CLEAN_SHELL_OPERATOR_PROMPT.md":
        raise SystemExit(f"{source} manifest missing operator prompt path")
    if payload.get("return_packet_finalize_script_path") != "FINALIZE_RETURN_PACKET.sh":
        raise SystemExit(f"{source} manifest missing return packet finalize script path")
    if payload.get("launch_asset_handoff_path") != "LAUNCH_ASSET_HANDOFF.md":
        raise SystemExit(f"{source} manifest missing launch asset handoff path")
    if launch_assets_dir_path != "assets":
        raise SystemExit(f"{source} manifest missing launch assets output directory")
    if return_packet.get("manifest_path") != "launch-proof.json":
        raise SystemExit(f"{source} manifest missing return packet manifest path")
    if return_packet.get("public_verify_logs_dir_path") != "public-verify-logs":
        raise SystemExit(f"{source} manifest missing return packet public verify logs dir")
    if return_packet.get("public_verify_result_path") != "public-verify-result.json":
        raise SystemExit(f"{source} manifest missing return packet public verify result path")
    if return_packet.get("launch_assets_dir_path") != "assets":
        raise SystemExit(f"{source} manifest missing return packet launch assets dir")
    if return_packet.get("archive_path") != "public-verify-return-packet.tar.gz":
        raise SystemExit(f"{source} manifest missing return packet archive path")
    if return_packet.get("finalize_script_path") != "FINALIZE_RETURN_PACKET.sh":
        raise SystemExit(f"{source} manifest missing return packet finalize script path")
    if payload.get("return_packet_archive_path") != "public-verify-return-packet.tar.gz":
        raise SystemExit(f"{source} manifest missing top-level return packet archive path")
    if public_verify.get("handoff_path") != "PUBLIC_VERIFY_HANDOFF.md":
        raise SystemExit(f"{source} manifest missing public verify handoff contract")
    if public_verify.get("receive_verify_handoff_path") != "RECEIVE_VERIFY_HANDOFF.md":
        raise SystemExit(f"{source} manifest missing receive-side handoff contract")
    if not isinstance(launch_assets, list) or not launch_assets:
        raise SystemExit(f"{source} manifest missing launch asset storyboard")
    launch_asset_ids = [asset.get("id") for asset in launch_assets if isinstance(asset, dict)]
    for required_asset in ("ui-release-pack", "ui-handoff-restore"):
        if required_asset not in launch_asset_ids:
            raise SystemExit(f"{source} manifest missing required launch asset `{required_asset}`")
    for asset in launch_assets:
        if not isinstance(asset, dict) or not asset.get("output_path", "").startswith("assets/"):
            raise SystemExit(f"{source} manifest missing launch asset output paths")
    if public_verify.get("install_mode_requirement") != "packaged":
        raise SystemExit(f"{source} manifest missing packaged public verify install requirement")
    if public_verify.get("result_path") != "public-verify-result.json":
        raise SystemExit(f"{source} manifest missing public verify result path")
    if public_verify.get("operator_prompt_path") != "CLEAN_SHELL_OPERATOR_PROMPT.md":
        raise SystemExit(f"{source} manifest missing public verify operator prompt path")
    if public_verify.get("finalize_script_path") != "FINALIZE_RETURN_PACKET.sh":
        raise SystemExit(f"{source} manifest missing public verify finalize script path")
    expected_logs = public_verify.get("expected_log_files")
    if expected_logs != [
        "operator-packet-verify.log",
        "curl-install.log",
        "first-run.log",
        "release-pack.log",
        "packaged-release-smoke.log",
        "prelaunch.log",
    ]:
        raise SystemExit(f"{source} manifest missing expected public verify log files")
    if "Release:" not in status_summary:
        return
    if "Launch proof: ok" not in status_summary:
        raise SystemExit(f"{source} manifest missing post-generation launch-proof status")
    if "Local alpha gate: ready" not in status_summary:
        raise SystemExit(f"{source} manifest missing post-generation local alpha readiness")
    if "Launch proof: missing" in status_summary:
        raise SystemExit(f"{source} manifest still reports launch proof as missing")


def ensure_prelaunch_publish_ready(output: str, *, source: str) -> None:
    if "Zerker Memory prelaunch" not in output:
        raise SystemExit(f"{source} missing prelaunch heading")
    if "Ready to publish: yes" not in output:
        raise SystemExit(f"{source} did not pass the strict publish gate")


def ensure_prelaunch_public_verify_block(output: str, *, source: str) -> None:
    if "Zerker Memory prelaunch" not in output:
        raise SystemExit(f"{source} missing prelaunch heading")
    if "Ready to publish: no" not in output:
        raise SystemExit(f"{source} should remain blocked before public-verify logs exist")
    if "- public_verify_evidence: blocker" not in output:
        raise SystemExit(f"{source} missing public-verify blocker")
    if "- launch_assets: blocker" not in output:
        raise SystemExit(f"{source} missing launch-assets blocker")
    if "public_urls: ok" not in output:
        raise SystemExit(f"{source} did not verify live public URLs")
    if '"schema": "zerker.prelaunch.v1"' in output or "{" in output:
        raise SystemExit(f"{source} should not include JSON output")


def ensure_bootstrap_contract(repo: Path) -> None:
    install_script = (repo / "install.sh").read_text(encoding="utf-8")
    first_run_script = (repo / "examples" / "first_run.sh").read_text(encoding="utf-8")
    required = [
        ("install.sh", install_script, 'SMOKE_AGENT="openclaw"'),
        ("install.sh", install_script, 'zmem agent smoke --agent "$SMOKE_AGENT"'),
        ("install.sh", install_script, 'zmem agent mcp-smoke --agent "$SMOKE_AGENT"'),
        ("install.sh", install_script, "zmem agent pack --summary-only"),
        ("install.sh", install_script, "zmem status --summary-only"),
        ("examples/first_run.sh", first_run_script, '"${ZMEM[@]}" agent smoke --agent codex'),
        ("examples/first_run.sh", first_run_script, '"${ZMEM[@]}" agent mcp-smoke --agent codex'),
        ("examples/first_run.sh", first_run_script, '"${ZMEM[@]}" agent pack --summary-only'),
        ("examples/first_run.sh", first_run_script, '"${ZMEM[@]}" status --summary-only'),
    ]
    for source, content, snippet in required:
        if snippet not in content:
            raise SystemExit(f"{source} missing bootstrap contract snippet: {snippet}")


def ensure_launch_plan_contract(repo: Path) -> None:
    launch_plan = (repo / "docs" / "LAUNCH_PLAN.md").read_text(encoding="utf-8")
    required = [
        "python3 scripts/release_smoke.py --summary-only",
        "zmem release-pack --summary-only",
        "zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only",
        "https://github.com/zerkerlabs/zmem",
        "https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh",
        "zmem verify-public-verify --summary-only",
        "assets/install-status.png",
        "assets/first-run-status.png",
        "assets/release-pack-summary.png",
        "assets/proof-report-overview.png",
        "assets/transcript-proof.png",
        "assets/ui-release-pack.gif",
        "assets/handoff-restore-terminal.png",
        "assets/ui-handoff-restore.gif",
        "zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only",
        "docs/CLEAN_SHELL_PUBLIC_VERIFY.md",
    ]
    for snippet in required:
        if snippet not in launch_plan:
            raise SystemExit(f"docs/LAUNCH_PLAN.md missing Phase 1 launch contract snippet: {snippet}")


def run_mcp_request(process: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    if process.stdin is None or process.stdout is None:
        raise SystemExit("MCP process missing stdio pipes")
    process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    process.stdin.flush()
    while True:
        line = process.stdout.readline()
        if line == "":
            stderr = ""
            if process.stderr is not None:
                stderr = process.stderr.read().strip()
            raise SystemExit(f"MCP process exited before responding: {stderr}")
        line = line.strip()
        if not line:
            continue
        return json.loads(line)


def stop_mcp_process(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None:
        process.stdin.close()
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()


def run_mcp_smoke(
    command: list[str],
    *,
    cwd: Path,
    db_path: Path,
    policy_path: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    operator_process = subprocess.Popen(
        [*command, "--db", str(db_path), "--policy", str(policy_path), "--profile", "operator"],
        cwd=cwd,
        env=env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        remember = run_mcp_request(
            operator_process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "memory.remember",
                    "arguments": {
                        "content": "Production deploys require approval",
                        "type": "policy",
                        "scope": "project",
                    },
                },
            },
        )
    finally:
        stop_mcp_process(operator_process)

    if "error" in remember:
        raise SystemExit(f"MCP operator seed failed: {remember['error']['message']}")
    remember_payload = json.loads(remember["result"]["content"][0]["text"])
    process = subprocess.Popen(
        [*command, "--db", str(db_path), "--policy", str(policy_path), "--profile", "agent"],
        cwd=cwd,
        env=env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        initialize = run_mcp_request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "release-smoke", "version": "0.1.0"},
                },
            },
        )
        initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        if process.stdin is None:
            raise SystemExit("MCP process missing stdin pipe")
        process.stdin.write(json.dumps(initialized, separators=(",", ":")) + "\n")
        process.stdin.flush()
        tools = run_mcp_request(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        inject = run_mcp_request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "memory.inject",
                    "arguments": {
                        "task": "deploy service to production",
                        "agent": "release-smoke",
                        "risk": "high",
                        "scope": "project",
                    },
                },
            },
        )
        inject_payload = json.loads(inject["result"]["content"][0]["text"])
        action_id = inject_payload.get("action_id")
        if not action_id:
            raise SystemExit("MCP inject did not return an action_id")
        why = run_mcp_request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "memory.why", "arguments": {"action_id": action_id}},
            },
        )
        verify = run_mcp_request(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "memory.verify", "arguments": {"action_id": action_id}},
            },
        )
    finally:
        stop_mcp_process(process)

    tool_names = [tool["name"] for tool in tools["result"]["tools"]]
    why_payload = json.loads(why["result"]["content"][0]["text"])
    verify_payload = json.loads(verify["result"]["content"][0]["text"])
    if initialize["result"]["serverInfo"]["name"] != "zerker-memory":
        raise SystemExit("MCP initialize returned unexpected server name")
    if "memory.inject" not in tool_names:
        raise SystemExit("MCP tools/list missing memory.inject")
    if "memory.why" not in tool_names:
        raise SystemExit("MCP tools/list missing memory.why")
    if {"memory.remember", "memory.promote", "memory.restore"}.intersection(tool_names):
        raise SystemExit("MCP agent profile exposed trusted operator tools")
    if not verify_payload.get("ok"):
        raise SystemExit("MCP verify did not verify the action")
    return {
        "ok": True,
        "server": initialize["result"]["serverInfo"],
        "protocol_version": initialize["result"]["protocolVersion"],
        "tool_count": len(tool_names),
        "remembered_memory_id": remember_payload["id"],
        "action_id": inject_payload["action_id"],
        "injected_memory_ids": inject_payload["injected_memory_ids"],
        "why": {
            "retrieved_memory_ids": why_payload.get("retrieved_memory_ids", []),
            "injected_memory_ids": why_payload.get("injected_memory_ids", []),
            "withheld_memory_ids": why_payload.get("withheld_memory_ids", []),
        },
        "verified": verify_payload,
    }


def venv_bin(venv_dir: Path, name: str) -> Path:
    subdir = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return venv_dir / subdir / f"{name}{suffix}"


def write_cli_wrappers(venv_dir: Path, python: Path, repo: Path, *, include_pythonpath: bool) -> None:
    wrapper_lines = []
    if include_pythonpath:
        wrapper_lines.append(f'export PYTHONPATH="{repo}${{PYTHONPATH:+:$PYTHONPATH}}"')
    wrappers = {
        "zmem": "zerker_memory",
        "zerker-memory": "zerker_memory",
        "zerker": "zerker_memory",
        "zerker-memory-mcp": "zerker_memory.mcp",
    }
    for name, module in wrappers.items():
        wrapper = venv_bin(venv_dir, name)
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    *wrapper_lines,
                    f'exec "{python}" -m {module} "$@"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)


def create_local_wrappers(venv_dir: Path, repo: Path) -> None:
    python = venv_bin(venv_dir, "python")
    write_cli_wrappers(venv_dir, python, repo, include_pythonpath=True)


def create_venv_pth_install(venv_dir: Path, repo: Path) -> None:
    python = venv_bin(venv_dir, "python")
    purelib = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    site_packages = Path(purelib)
    site_packages.mkdir(parents=True, exist_ok=True)
    (site_packages / "zerker_memory_repo.pth").write_text(f"{repo}\n", encoding="utf-8")
    write_cli_wrappers(venv_dir, python, repo, include_pythonpath=False)


def copy_release_surface(repo: Path, destination: Path) -> None:
    shutil.copytree(
        repo,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".treeship",
            ".venv",
            ".zerker",
            ".next",
            ".turbo",
            "__pycache__",
            "node_modules",
            "*.pyc",
            "*.pyo",
            "*.sqlite",
            "*.egg-info",
            "build",
            "dist",
        ),
    )


def install_editable_with_fallback(python: Path, repo: Path, *, cwd: Path) -> str:
    if try_run([str(python), "-m", "pip", "install", "-e", str(repo)], cwd=cwd):
        return "editable"
    print("Editable install with build isolation failed; retrying with local build backend.")
    if try_run([str(python), "-m", "pip", "install", "-e", str(repo), "--no-build-isolation"], cwd=cwd):
        return "editable-no-build-isolation"
    print("Editable install could not fetch or build packaging dependencies; creating venv-local import bootstrap.")
    try:
        create_venv_pth_install(python.parent.parent, repo)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Venv-local import bootstrap failed ({exc}); creating local venv wrappers.")
        create_local_wrappers(python.parent.parent, repo)
        return "local-wrappers"
    return "venv-pth"


def install_mode_satisfies_requirement(install_mode: str, required_mode: str) -> bool:
    if required_mode == "packaged":
        return install_mode in {"editable", "editable-no-build-isolation", "venv-pth"}
    return install_mode == required_mode


def ensure_install_mode(install_mode: str, *, required_mode: str) -> None:
    if install_mode_satisfies_requirement(install_mode, required_mode):
        return
    raise SystemExit(
        "release smoke used install_mode="
        f"{install_mode}, which does not satisfy --require-install-mode {required_mode}"
    )


def env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def python_supports_version(command: str, minimum: tuple[int, int] = MIN_PYTHON_VERSION) -> bool:
    completed = subprocess.run(
        [
            command,
            "-c",
            (
                "import sys; "
                f"raise SystemExit(0 if sys.version_info >= ({minimum[0]}, {minimum[1]}) else 1)"
            ),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def pick_supported_python(
    minimum: tuple[int, int] = MIN_PYTHON_VERSION,
    *,
    candidates: tuple[str, ...] = SUPPORTED_PYTHON_CANDIDATES,
) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved and python_supports_version(resolved, minimum):
            return resolved
    pyenv = shutil.which("pyenv")
    if not pyenv:
        return None
    for candidate in ("3.12", "3.11", "3.10"):
        completed = subprocess.run(
            [pyenv, "prefix", candidate],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        prefix = completed.stdout.strip()
        if not prefix:
            continue
        resolved = str(Path(prefix) / "bin" / "python")
        if Path(resolved).exists() and python_supports_version(resolved, minimum):
            return resolved
    return None


def reexec_with_supported_python(argv: list[str]) -> int:
    python = pick_supported_python()
    if python is None:
        raise SystemExit("Python >=3.10 required for release smoke; install python3.10+ or configure pyenv")
    return subprocess.call([python, str(Path(__file__).resolve()), *argv], env=os.environ.copy())


def repo_python_env(repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def run_release_smoke_summary(repo: Path) -> int:
    python = sys.executable
    env = repo_python_env(repo)
    print("Zerker Memory release smoke summary")
    print(f"Repo: {repo}")
    print(f"Python: {python}")
    print("")

    status_output = run([python, "-m", "zerker_memory", "status", "--summary-only"], cwd=repo, env=env)
    ensure_status_summary(status_output, source="python3 -m zerker_memory status --summary-only")

    release_pack_output, release_pack_code = run_capture(
        [python, "-m", "zerker_memory", "release-pack", "--summary-only"],
        cwd=repo,
        env=env,
    )
    if release_pack_code not in {0, 1}:
        raise SystemExit(f"release-pack summary-only exited unexpectedly with code {release_pack_code}")
    ensure_release_pack_summary(release_pack_output, source="python3 -m zerker_memory release-pack --summary-only")

    refreshed_status_output = run([python, "-m", "zerker_memory", "status", "--summary-only"], cwd=repo, env=env)
    ensure_status_summary(refreshed_status_output, source="python3 -m zerker_memory status --summary-only")

    operator_packet_output = run(
        [
            python,
            "-m",
            "zerker_memory",
            "verify-operator-packet",
            ".zerker/launch-proof/public-verify-operator-packet.tar.gz",
            "--summary-only",
        ],
        cwd=repo,
        env=env,
    )
    ensure_operator_packet_summary(
        operator_packet_output,
        source="python3 -m zerker_memory verify-operator-packet --summary-only",
    )

    public_verify_output, public_verify_code = run_capture(
        [python, "-m", "zerker_memory", "verify-public-verify", "--summary-only"],
        cwd=repo,
        env=env,
    )
    if public_verify_code not in {0, 1}:
        raise SystemExit(f"verify-public-verify summary-only exited unexpectedly with code {public_verify_code}")
    ensure_public_verify_summary(
        public_verify_output,
        source="python3 -m zerker_memory verify-public-verify --summary-only",
    )
    ensure_public_verify_result_summary_artifact(
        (repo / ".zerker" / "launch-proof" / "public-verify-summary.md").read_text(encoding="utf-8"),
        source=".zerker/launch-proof/public-verify-summary.md",
    )
    ensure_launch_proof_report(
        (repo / ".zerker" / "launch-proof" / "index.html").read_text(encoding="utf-8"),
        source=".zerker/launch-proof/index.html",
    )

    launch_assets_output, launch_assets_code = run_capture(
        [python, "-m", "zerker_memory", "verify-launch-assets", "--summary-only"],
        cwd=repo,
        env=env,
    )
    if launch_assets_code not in {0, 1}:
        raise SystemExit(f"verify-launch-assets summary-only exited unexpectedly with code {launch_assets_code}")
    ensure_launch_assets_summary(
        launch_assets_output,
        source="python3 -m zerker_memory verify-launch-assets --summary-only",
    )

    return_packet_output, return_packet_code = run_capture(
        [
            python,
            "-m",
            "zerker_memory",
            "verify-return-packet",
            ".zerker/launch-proof/public-verify-return-packet.tar.gz",
            "--summary-only",
        ],
        cwd=repo,
        env=env,
    )
    if return_packet_code not in {0, 1}:
        raise SystemExit(f"verify-return-packet summary-only exited unexpectedly with code {return_packet_code}")
    ensure_return_packet_summary(
        return_packet_output,
        source="python3 -m zerker_memory verify-return-packet --summary-only",
    )

    prelaunch_output, prelaunch_code = run_capture(
        [python, "-m", "zerker_memory", "prelaunch", "--summary-only"],
        cwd=repo,
        env=env,
    )
    if prelaunch_code not in {0, 1}:
        raise SystemExit(f"prelaunch summary-only exited unexpectedly with code {prelaunch_code}")
    if prelaunch_code == 0:
        ensure_prelaunch_publish_ready(prelaunch_output, source="python3 -m zerker_memory prelaunch --summary-only")
    else:
        ensure_prelaunch_public_verify_block(
            prelaunch_output,
            source="python3 -m zerker_memory prelaunch --summary-only",
        )

    print("Release smoke summary checks completed.")
    return 0


def run_python_module_entrypoint_smoke(repo: Path, *, cwd: Path) -> dict[str, Any]:
    python3 = shutil.which("python3")
    if not python3:
        return {"ok": False, "skipped": True, "reason": "python3 not found"}
    env = repo_python_env(repo)
    run([python3, "-m", "zerker_memory", "doctor", "--skip-eval"], cwd=cwd, env=env)
    status_output = run([python3, "-m", "zerker_memory", "status", "--summary-only", "--skip-eval"], cwd=cwd, env=env)
    ensure_status_summary(status_output, source="python3 -m zerker_memory status --summary-only --skip-eval")
    return {"ok": True, "python": python3, "skipped": False}


def live_provider_env(provider: str) -> dict[str, str | None]:
    prefix = f"ZERKER_PROVIDER_{provider.upper()}"
    explicit_query = os.getenv(f"{prefix}_QUERY")
    base_url = os.getenv(f"{prefix}_BASE_URL")
    api_key = os.getenv(f"{prefix}_API_KEY")
    user_id = os.getenv(f"{prefix}_USER_ID")
    return {
        "enabled": "1" if env_flag("ZERKER_PROVIDER_LIVE") else "0",
        "configured": "1" if any(value is not None for value in (base_url, api_key, user_id, explicit_query)) else "0",
        "explicit_query": explicit_query,
        "base_url": base_url,
        "api_key": api_key,
        "user_id": user_id,
        "query": explicit_query or f"zerker {provider} release smoke",
    }


def live_provider_selection(providers: tuple[str, ...] = ("mem0", "zep")) -> list[str]:
    raw = os.getenv("ZERKER_PROVIDER_LIVE_PROVIDERS", "")
    if not raw.strip():
        return []
    selected: list[str] = []
    for item in raw.replace(",", " ").split():
        provider = item.strip().lower()
        if not provider:
            continue
        if provider not in providers:
            supported = ", ".join(providers)
            raise SystemExit(f"unsupported ZERKER_PROVIDER_LIVE_PROVIDERS entry: {provider}; expected one of: {supported}")
        if provider not in selected:
            selected.append(provider)
    return selected


def build_live_provider_doctor_command(zmem: Path, providers: tuple[str, ...] = ("mem0", "zep")) -> tuple[list[str], dict[str, Any]]:
    command = [str(zmem), "provider", "doctor", "--live"]
    live_provider_result: dict[str, Any] = {"enabled": env_flag("ZERKER_PROVIDER_LIVE"), "providers": {}}
    configured_providers: list[str] = []
    live_envs: dict[str, dict[str, str | None]] = {}
    for provider in providers:
        live_env = live_provider_env(provider)
        live_envs[provider] = live_env
        if live_env["configured"] == "1":
            configured_providers.append(provider)
        live_provider_result["providers"][provider] = {
            "configured": live_env["configured"] == "1",
            "base_url": live_env["base_url"],
            "query": live_env["query"],
            "user_id": live_env["user_id"],
        }
    selected_providers = live_provider_selection(providers) or configured_providers
    for provider in selected_providers:
        command.extend(["--provider", provider])
    for provider in selected_providers:
        live_env = live_envs[provider]
        if live_env["base_url"]:
            command.extend([f"--{provider}-base-url", live_env["base_url"]])
        if live_env["api_key"]:
            command.extend([f"--{provider}-api-key", live_env["api_key"]])
        if live_env["query"]:
            command.extend([f"--{provider}-query", live_env["query"]])
        if live_env["user_id"]:
            command.extend([f"--{provider}-user-id", live_env["user_id"]])
    live_provider_result["selected_providers"] = selected_providers
    return command, live_provider_result


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if sys.version_info < MIN_PYTHON_VERSION:
        return reexec_with_supported_python(argv)
    parser = argparse.ArgumentParser(description="Run the Zerker Memory alpha release smoke test")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--keep", action="store_true", help="Keep the temporary smoke directory")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print the current release-contract preflight without creating a fresh install workspace",
    )
    parser.add_argument(
        "--require-install-mode",
        choices=INSTALL_MODE_CHOICES,
        help=(
            "Fail unless the smoke used the requested install path. "
            "'packaged' accepts editable install modes plus the venv-local .pth bootstrap and rejects local wrappers."
        ),
    )
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    ensure_bootstrap_contract(repo)
    ensure_launch_plan_contract(repo)
    if args.summary_only:
        return run_release_smoke_summary(repo)

    root = Path(tempfile.mkdtemp(prefix="zmem-release-smoke-"))
    try:
        venv_dir = root / ".venv"
        work = root / "work"
        work.mkdir()
        create_release_venv(venv_dir)
        python = venv_bin(venv_dir, "python")
        zmem = venv_bin(venv_dir, "zmem")
        zerker_memory = venv_bin(venv_dir, "zerker-memory")
        zerker = venv_bin(venv_dir, "zerker")
        mcp = venv_bin(venv_dir, "zerker-memory-mcp")

        install_mode = install_editable_with_fallback(python, repo, cwd=work)
        if args.require_install_mode:
            ensure_install_mode(install_mode, required_mode=args.require_install_mode)

        for entrypoint in [zmem, zerker_memory, zerker, mcp]:
            run([str(entrypoint), "--help"], cwd=work)

        run(
            [
                str(zmem),
                "init",
                "--with-policy",
                "--with-agent-prompt",
                "--with-mcp-config",
                "--with-provider-config",
            ],
            cwd=work,
        )
        for path in [
            work / ".zerker" / "memory.sqlite",
            work / ".zerker" / "policy.json",
            work / ".zerker" / "mcp.json",
            work / ".zerker" / "providers.json",
            work / ".zerker" / "AGENT_PROMPT.md",
        ]:
            if not path.exists():
                raise SystemExit(f"missing expected init artifact: {path}")

        python_module_smoke = run_python_module_entrypoint_smoke(repo, cwd=work)
        run([str(zmem), "provider", "doctor"], cwd=work)
        agent_config = parse_json(run([str(zmem), "agent", "config", "codex", "--include-policy"], cwd=work))
        if "zerker-memory" not in agent_config["config"]["mcpServers"]:
            raise SystemExit("agent config missing zerker-memory MCP server")
        codex_install_path = work / "codex-config.toml"
        claude_install_path = work / "claude-mcp.json"
        openclaw_install_path = work / ".zerker" / "agents" / "openclaw-mcp.json"
        hermes_install_path = work / ".zerker" / "agents" / "hermes-mcp.json"
        generic_install_path = work / ".zerker" / "agents" / "generic-mcp.json"
        manual_pack_path = work / ".zerker" / "agents" / "manual-agent-pack.md"
        home_env = {**os.environ, "HOME": str(work)}
        codex_install = parse_json(
            run(
                [str(zmem), "agent", "install", "codex", "--config-path", str(codex_install_path)],
                cwd=work,
            )
        )
        if not codex_install["config_written"] or not codex_install_path.exists():
            raise SystemExit("codex agent install did not write config")
        if "[mcp_servers.zerker-memory]" not in codex_install_path.read_text(encoding="utf-8"):
            raise SystemExit("codex agent install missing mcp server block")
        if not codex_install["doctor"]["ok"]:
            raise SystemExit("codex agent install doctor verification failed")
        claude_install = parse_json(
            run(
                [str(zmem), "agent", "install", "claude-code", "--config-path", str(claude_install_path)],
                cwd=work,
            )
        )
        if not claude_install["config_written"] or not claude_install_path.exists():
            raise SystemExit("claude-code agent install did not write config")
        claude_payload = json.loads(claude_install_path.read_text(encoding="utf-8"))
        if "zerker-memory" not in claude_payload.get("mcpServers", {}):
            raise SystemExit("claude-code agent install missing zerker-memory server")
        if not claude_install["doctor"]["ok"]:
            raise SystemExit("claude-code agent install doctor verification failed")
        for preset, path in [
            ("openclaw", openclaw_install_path),
            ("hermes", hermes_install_path),
            ("generic", generic_install_path),
        ]:
            summary_title = {
                "openclaw": "OpenClaw",
                "hermes": "Hermes",
                "generic": "Generic MCP Agent",
            }[preset]
            checklist_path = work / ".zerker" / "agents" / f"{preset}-checklist.md"
            manual_install = parse_json(
                run(
                    [str(zmem), "agent", "install", preset],
                    cwd=work,
                )
            )
            if not manual_install["config_written"] or not path.exists():
                raise SystemExit(f"{preset} agent install did not write config")
            if Path(manual_install["config_path"]).resolve() != path.resolve():
                raise SystemExit(f"{preset} agent install wrote unexpected default path")
            if Path(manual_install["checklist_path"]).resolve() != checklist_path.resolve():
                raise SystemExit(f"{preset} agent install wrote unexpected checklist path")
            if not checklist_path.exists():
                raise SystemExit(f"{preset} agent install did not write checklist artifact")
            if Path(manual_install["install_preview"]["import_path"]).resolve() != path.resolve():
                raise SystemExit(f"{preset} agent install preview reported unexpected import path")
            if manual_install["install_preview"]["verify_command"] != f"zmem doctor --agent {preset}":
                raise SystemExit(f"{preset} agent install preview missing doctor command")
            if f"zmem agent snippet {preset}" not in manual_install["install_preview"]["fallback_import_step"]:
                raise SystemExit(f"{preset} agent install preview missing snippet fallback")
            if not manual_install["doctor"]["ok"]:
                raise SystemExit(f"{preset} agent install doctor verification failed")
            manual_payload = json.loads(path.read_text(encoding="utf-8"))
            if "zerker-memory" not in manual_payload.get("mcpServers", {}):
                raise SystemExit(f"{preset} agent install missing zerker-memory server")
            manual_summary_output = run([str(zmem), "agent", "install", preset, "--summary"], cwd=work)
            if f"{summary_title} install summary" not in manual_summary_output:
                raise SystemExit(f"{preset} agent install summary missing human-readable heading")
            if "Checklist:" not in manual_summary_output:
                raise SystemExit(f"{preset} agent install summary missing checklist path")
            if "Post-install doctor: ok" not in manual_summary_output:
                raise SystemExit(f"{preset} agent install summary missing post-install doctor result")
            manual_summary_only_output = run([str(zmem), "agent", "install", preset, "--summary-only"], cwd=work)
            if f"{summary_title} install summary" not in manual_summary_only_output:
                raise SystemExit(f"{preset} agent install summary-only missing human-readable heading")
            if "Post-install doctor: ok" not in manual_summary_only_output:
                raise SystemExit(f"{preset} agent install summary-only missing post-install doctor result")
            if '"schema": "zerker.agent_install.v1"' in manual_summary_only_output or "{" in manual_summary_only_output:
                raise SystemExit(f"{preset} agent install summary-only should not include JSON output")
            snippet = parse_json(run([str(zmem), "agent", "snippet", preset], cwd=work))
            if snippet["server"]["command"] != "zmem":
                raise SystemExit(f"{preset} agent snippet missing zmem command")
            if snippet["server"]["args"][-3:] != ["mcp", "--profile", "agent"]:
                raise SystemExit(f"{preset} agent snippet missing safe agent-profile command tail")
            run([str(zmem), "agent", "checklist", preset], cwd=work)
            if not checklist_path.exists():
                raise SystemExit(f"{preset} agent checklist did not write artifact")
            checklist = checklist_path.read_text(encoding="utf-8")
            if f"zmem doctor --agent {preset}" not in checklist:
                raise SystemExit(f"{preset} agent checklist missing doctor command")
            if f"zmem agent snippet {preset}" not in checklist:
                raise SystemExit(f"{preset} agent checklist missing snippet fallback")
        manual_pack = parse_json(run([str(zmem), "agent", "pack"], cwd=work))
        if Path(manual_pack["pack_path"]).resolve() != manual_pack_path.resolve():
            raise SystemExit("manual agent pack wrote unexpected default path")
        if manual_pack["presets"] != ["cursor", "openclaw", "hermes", "generic"]:
            raise SystemExit("manual agent pack reported unexpected preset list")
        if not manual_pack_path.exists():
            raise SystemExit("manual agent pack did not write artifact")
        manual_pack_text = manual_pack_path.read_text(encoding="utf-8")
        if "zmem doctor --agent cursor --agent openclaw --agent hermes --agent generic" not in manual_pack_text:
            raise SystemExit("manual agent pack missing combined doctor command")
        if "cursor-checklist.md" not in manual_pack_text or "openclaw-checklist.md" not in manual_pack_text or "generic-checklist.md" not in manual_pack_text:
            raise SystemExit("manual agent pack missing checklist references")
        manual_pack_summary = run([str(zmem), "agent", "pack", "--summary-only"], cwd=work)
        if "Manual agent pack summary" not in manual_pack_summary:
            raise SystemExit("manual agent pack summary-only missing human-readable heading")
        if "Post-install doctor: ok" not in manual_pack_summary:
            raise SystemExit("manual agent pack summary-only missing post-install doctor result")
        if '"schema": "zerker.agent_pack.v1"' in manual_pack_summary or "{" in manual_pack_summary:
            raise SystemExit("manual agent pack summary-only should not include JSON output")
        run([str(zmem), "agent", "install", "codex", "--force"], cwd=work, env=home_env)
        run([str(zmem), "agent", "install", "claude-code", "--force"], cwd=work, env=home_env)
        agent_doctor = parse_json(
            run(
                [
                    str(zmem),
                    "doctor",
                    "--skip-eval",
                    "--agent",
                    "codex",
                    "--agent",
                    "claude-code",
                    "--agent",
                    "openclaw",
                    "--agent",
                    "hermes",
                    "--agent",
                    "generic",
                ],
                cwd=work,
                env=home_env,
            )
        )
        if not agent_doctor["ok"]:
            raise SystemExit("doctor agent install verification failed")
        agent_smoke = parse_json(run([str(zmem), "agent", "smoke", "--agent", "codex"], cwd=work))
        if not agent_smoke["ok"]:
            raise SystemExit("agent smoke failed")
        agent_mcp_smoke = parse_json(run([str(zmem), "agent", "mcp-smoke", "--agent", "codex"], cwd=work))
        if not agent_mcp_smoke["ok"]:
            raise SystemExit("MCP protocol smoke failed")
        mcp_smoke = run_mcp_smoke(
            [str(mcp)],
            cwd=work,
            db_path=work / ".zerker" / "memory.sqlite",
            policy_path=work / ".zerker" / "policy.json",
        )
        live_provider_result: dict[str, Any] = {"enabled": env_flag("ZERKER_PROVIDER_LIVE"), "providers": {}}
        if live_provider_result["enabled"]:
            live_command, live_provider_result = build_live_provider_doctor_command(zmem)
            run(live_command, cwd=work)
            live_provider_result["ran"] = True
        else:
            live_provider_result["ran"] = False
        run([str(zmem), "eval"], cwd=work)
        demo = parse_json(run([str(zmem), "demo"], cwd=work))
        action_id = demo["action_id"]

        bundle = parse_json(run([str(zmem), "bundle", action_id, "--out-dir", ".zerker/exports"], cwd=work))
        run([str(zmem), "bundle", "verify", bundle["path"]], cwd=work)

        snapshot = parse_json(run([str(zmem), "snapshot", "--out-dir", ".zerker/exports"], cwd=work))
        run([str(zmem), "snapshot", "verify", snapshot["path"]], cwd=work)
        handoff = parse_json(run([str(zmem), "handoff"], cwd=work))
        if not handoff["ok"]:
            raise SystemExit("handoff CLI failed")
        if not Path(handoff["readme_path"]).exists():
            raise SystemExit("handoff CLI did not write README")
        if not Path(handoff["manifest_path"]).exists():
            raise SystemExit("handoff CLI did not write manifest")
        if not Path(handoff["snapshot_path"]).exists():
            raise SystemExit("handoff CLI did not write snapshot")
        if handoff.get("bundle_path") and not Path(handoff["bundle_path"]).exists():
            raise SystemExit("handoff CLI did not write bundle")
        if handoff.get("treeship_path") and not Path(handoff["treeship_path"]).exists():
            raise SystemExit("handoff CLI did not write Treeship statement")
        restored_db = work / ".zerker" / "handoff-restore.sqlite"
        restored = parse_json(run([str(zmem), "--db", str(restored_db), "restore", "--handoff-dir", handoff["out_dir"]], cwd=work))
        if not restored["ok"]:
            raise SystemExit("handoff restore CLI failed")
        if restored["restore"]["receipt_count"] < 1:
            raise SystemExit("handoff restore did not restore action receipts")
        launch_proof_summary = run([str(zmem), "launch-proof", "--summary-only"], cwd=work)
        ensure_launch_proof_summary(launch_proof_summary, source="launch-proof summary-only")
        launch_proof = parse_json(run([str(zmem), "launch-proof"], cwd=work))
        if not launch_proof["ok"]:
            raise SystemExit("launch-proof CLI failed")
        if not Path(launch_proof["transcript_path"]).exists():
            raise SystemExit("launch-proof CLI did not write transcript")
        if not Path(launch_proof["summary_path"]).exists():
            raise SystemExit("launch-proof CLI did not write summary")
        if not Path(launch_proof["manifest_path"]).exists():
            raise SystemExit("launch-proof CLI did not write manifest")
        ensure_launch_proof_manifest_status(
            json.loads(Path(launch_proof["manifest_path"]).read_text(encoding="utf-8")),
            source="launch-proof",
        )
        if not Path(launch_proof["report_path"]).exists():
            raise SystemExit("launch-proof CLI did not write HTML report")
        if not Path(launch_proof["capture_checklist_path"]).exists():
            raise SystemExit("launch-proof CLI did not write capture checklist")
        capture_checklist_text = Path(launch_proof["capture_checklist_path"]).read_text(encoding="utf-8")
        if "Strict publish gate snapshot in this pack:" not in capture_checklist_text:
            raise SystemExit("launch-proof capture checklist did not include the strict publish gate snapshot")
        if not Path(launch_proof["public_verify_handoff_path"]).exists():
            raise SystemExit("launch-proof CLI did not write public verify handoff")
        public_verify_handoff_text = Path(launch_proof["public_verify_handoff_path"]).read_text(encoding="utf-8")
        if "## Current Gate Snapshot" not in public_verify_handoff_text:
            raise SystemExit("launch-proof public verify handoff did not include the current gate snapshot")
        if not Path(launch_proof["receive_verify_handoff_path"]).exists():
            raise SystemExit("launch-proof CLI did not write receive-side handoff")
        if not Path(launch_proof["public_verify_checklist_path"]).exists():
            raise SystemExit("launch-proof CLI did not write public verify checklist")
        public_verify_checklist_text = Path(launch_proof["public_verify_checklist_path"]).read_text(encoding="utf-8")
        if "Strict publish gate snapshot in this generated pack:" not in public_verify_checklist_text:
            raise SystemExit("launch-proof public verify checklist did not include the strict publish gate snapshot")
        if not Path(launch_proof["public_verify_script_path"]).exists():
            raise SystemExit("launch-proof CLI did not write public verify script")
        if not Path(launch_proof["public_verify_result_path"]).exists():
            raise SystemExit("launch-proof CLI did not write public verify result placeholder")
        if not Path(launch_proof["operator_packet_archive_path"]).exists():
            raise SystemExit("launch-proof CLI did not write operator packet archive")
        operator_packet_summary = run(
            [str(zmem), "verify-operator-packet", launch_proof["operator_packet_archive_path"], "--summary-only"],
            cwd=work,
        )
        ensure_operator_packet_summary(operator_packet_summary, source="verify-operator-packet summary-only")
        launch_assets_summary, launch_assets_code = run_capture(
            [str(zmem), "verify-launch-assets", "--summary-only"],
            cwd=work,
        )
        if launch_assets_code != 1:
            raise SystemExit(
                f"verify-launch-assets summary-only should stay blocked until launch assets exist (got exit {launch_assets_code})"
            )
        ensure_launch_assets_summary(launch_assets_summary, source="verify-launch-assets summary-only")
        return_packet_summary, return_packet_code = run_capture(
            [str(zmem), "verify-return-packet", launch_proof["return_packet_archive_path"], "--summary-only"],
            cwd=work,
        )
        if return_packet_code != 1:
            raise SystemExit(
                f"verify-return-packet summary-only should stay blocked until public verify evidence exists (got exit {return_packet_code})"
            )
        ensure_return_packet_summary(return_packet_summary, source="verify-return-packet summary-only")
        release_work = root / "release-pack-work"
        copy_release_surface(repo, release_work)
        shutil.copytree(work / ".zerker", release_work / ".zerker")
        release_pack_summary, release_pack_code = run_capture(
            [str(zmem), "release-pack", "--summary-only"],
            cwd=release_work,
        )
        if release_pack_code != 1:
            raise SystemExit(f"release-pack summary-only should stay blocked until public verify evidence exists (got exit {release_pack_code})")
        ensure_release_pack_summary(release_pack_summary, source="release-pack summary-only")
        if not (release_work / ".zerker" / "launch-proof" / "launch-proof.json").exists():
            raise SystemExit("release-pack summary-only did not refresh launch-proof manifest")
        if not (release_work / ".zerker" / "launch-proof" / "CAPTURE_CHECKLIST.md").exists():
            raise SystemExit("release-pack summary-only did not refresh capture checklist")
        release_capture_checklist_text = (release_work / ".zerker" / "launch-proof" / "CAPTURE_CHECKLIST.md").read_text(
            encoding="utf-8"
        )
        if "Strict publish gate snapshot in this pack:" not in release_capture_checklist_text:
            raise SystemExit("release-pack summary-only did not refresh the capture checklist gate snapshot")
        if "## Clean-Shell Proof Log Map" not in release_capture_checklist_text:
            raise SystemExit("release-pack summary-only did not refresh the capture checklist command/log map")
        if not (release_work / ".zerker" / "launch-proof" / "PUBLIC_VERIFY_HANDOFF.md").exists():
            raise SystemExit("release-pack summary-only did not refresh public verify handoff")
        release_public_verify_handoff_text = (
            release_work / ".zerker" / "launch-proof" / "PUBLIC_VERIFY_HANDOFF.md"
        ).read_text(encoding="utf-8")
        if "## Current Gate Snapshot" not in release_public_verify_handoff_text:
            raise SystemExit("release-pack summary-only did not refresh the public verify handoff gate snapshot")
        if not (release_work / ".zerker" / "launch-proof" / "RECEIVE_VERIFY_HANDOFF.md").exists():
            raise SystemExit("release-pack summary-only did not refresh receive-side handoff")
        if not (release_work / ".zerker" / "launch-proof" / "PUBLIC_VERIFY_CHECKLIST.md").exists():
            raise SystemExit("release-pack summary-only did not refresh public verify checklist")
        release_public_verify_checklist_text = (
            release_work / ".zerker" / "launch-proof" / "PUBLIC_VERIFY_CHECKLIST.md"
        ).read_text(encoding="utf-8")
        if "Strict publish gate snapshot in this generated pack:" not in release_public_verify_checklist_text:
            raise SystemExit("release-pack summary-only did not refresh the public verify checklist gate snapshot")
        if "## Command Log Map" not in release_public_verify_checklist_text:
            raise SystemExit("release-pack summary-only did not refresh the public verify checklist command/log map")
        if not (release_work / ".zerker" / "launch-proof" / "PUBLIC_VERIFY_COMMANDS.sh").exists():
            raise SystemExit("release-pack summary-only did not refresh public verify script")
        if not (release_work / ".zerker" / "launch-proof" / "public-verify-result.json").exists():
            raise SystemExit("release-pack summary-only did not refresh public verify result placeholder")
        if not (release_work / ".zerker" / "launch-proof" / "public-verify-operator-packet.tar.gz").exists():
            raise SystemExit("release-pack summary-only did not refresh operator packet archive")
        prelaunch_summary, prelaunch_code = run_capture([str(zmem), "prelaunch", "--summary-only"], cwd=release_work)
        if prelaunch_code != 1:
            raise SystemExit(f"prelaunch should stay blocked until public verify evidence exists (got exit {prelaunch_code})")
        ensure_prelaunch_public_verify_block(prelaunch_summary, source="prelaunch")
        launch_proof_script = parse_json(
            run(
                ["bash", str(repo / "scripts" / "launch_proof.sh")],
                cwd=work,
                env={"PATH": str(zmem.parent) + os.pathsep + os.environ.get("PATH", "")},
            )
        )
        if not launch_proof_script["ok"]:
            raise SystemExit("launch_proof.sh wrapper failed")
        first_run_output = run(
            ["bash", str(repo / "examples" / "first_run.sh")],
            cwd=work,
            env={"PATH": str(zmem.parent) + os.pathsep + os.environ.get("PATH", "")},
        )
        ensure_status_summary(first_run_output, source="examples/first_run.sh")

        print(
            json.dumps(
                {
                    "ok": True,
                    "schema": "zerker.release_smoke.v1",
                    "install_mode": install_mode,
                    "workdir": str(work),
                    "action_id": action_id,
                    "agent_action_id": agent_smoke["action_id"],
                    "agent_mcp_action_id": agent_mcp_smoke["action_id"],
                    "packaged_mcp_action_id": mcp_smoke["action_id"],
                    "codex_install_path": str(codex_install_path),
                    "claude_install_path": str(claude_install_path),
                    "openclaw_install_path": str(openclaw_install_path),
                    "hermes_install_path": str(hermes_install_path),
                    "generic_install_path": str(generic_install_path),
                    "agent_doctor": agent_doctor,
                    "bundle": bundle["path"],
                    "snapshot": snapshot["path"],
                    "handoff": handoff["readme_path"],
                    "handoff_manifest": handoff["manifest_path"],
                    "handoff_snapshot": handoff["snapshot_path"],
                    "handoff_bundle": handoff["bundle_path"],
                    "handoff_treeship": handoff.get("treeship_path"),
                    "handoff_restore_db": str(restored_db),
                    "launch_proof": launch_proof["summary_path"],
                    "launch_proof_report": launch_proof["report_path"],
                    "agent_mcp_smoke": agent_mcp_smoke,
                    "mcp_smoke": mcp_smoke,
                    "python_module_smoke": python_module_smoke,
                    "live_provider_smoke": live_provider_result,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    finally:
        if args.keep:
            print(f"kept smoke directory: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
