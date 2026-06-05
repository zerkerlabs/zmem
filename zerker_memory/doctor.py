from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .eval import run_eval
from .providers import provider_doctor
from .store import MemoryStore, default_db_path
from .cli import agent_export_config_path


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "details": self.details}


def run_doctor(
    db_path: Path | None = None,
    *,
    run_eval_check: bool = True,
    agent_presets: list[str] | tuple[str, ...] | None = None,
    agent_config_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    db_path = db_path or default_db_path()
    checks = [
        check_python_version(),
        check_sqlite_fts5(),
        check_db_path(db_path),
        check_mcp_command(db_path),
        check_providers(),
    ]
    if agent_presets:
        checks.append(check_agent_prompt())
        checks.extend(check_agent_install(preset) for preset in agent_presets)
    if agent_config_paths:
        if not agent_presets:
            checks.append(check_agent_prompt())
        checks.extend(check_agent_install(preset, config_path=path) for preset, path in agent_config_paths.items())
    if run_eval_check:
        checks.append(check_eval())
    return {
        "schema": "zerker.doctor.v1",
        "ok": all(check.ok for check in checks),
        "checks": [check.to_dict() for check in checks],
    }


def check_python_version() -> DoctorCheck:
    version = sys.version_info
    ok = version >= (3, 10)
    version_text = f"{version.major}.{version.minor}.{version.micro}"
    if ok:
        return DoctorCheck("python_version", True, version_text)
    details = f"{version_text}; Python >=3.10 required; fastest fix: bash install.sh"
    supported_python = find_supported_python()
    if supported_python:
        details += f"; manual fix: {supported_python} -m venv .venv"
    else:
        details += "; manual fix: create a venv with python3.10+"
    return DoctorCheck(
        "python_version",
        False,
        details,
    )


def find_supported_python() -> str | None:
    for candidate in ("python3.12", "python3.11", "python3.10", "python3"):
        path = shutil.which(candidate)
        if path and python_supports_version(path):
            return path
    pyenv = shutil.which("pyenv")
    if pyenv:
        for candidate in ("3.12", "3.11", "3.10"):
            completed = subprocess.run(
                [pyenv, "prefix", candidate],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            prefix = completed.stdout.strip()
            path = Path(prefix) / "bin" / "python"
            if completed.returncode == 0 and prefix and path.exists() and python_supports_version(str(path)):
                return str(path)
    return None


def python_supports_version(command: str, minimum: tuple[int, int] = (3, 10)) -> bool:
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


def check_sqlite_fts5() -> DoctorCheck:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(content)")
        conn.close()
        return DoctorCheck("sqlite_fts5", True, "available")
    except sqlite3.Error as exc:
        return DoctorCheck("sqlite_fts5", False, str(exc))


def check_db_path(db_path: Path) -> DoctorCheck:
    try:
        store = MemoryStore(db_path)
        store.init()
        return DoctorCheck("db_path", True, str(db_path))
    except Exception as exc:
        return DoctorCheck("db_path", False, f"{db_path}: {exc}")


def check_mcp_command(db_path: Path) -> DoctorCheck:
    command = f"python3 -m zerker_memory --db {db_path} mcp"
    return DoctorCheck("mcp_command", True, command)


def check_agent_prompt() -> DoctorCheck:
    path = Path.cwd() / ".zerker" / "AGENT_PROMPT.md"
    if path.exists():
        return DoctorCheck("agent_prompt", True, str(path))
    return DoctorCheck("agent_prompt", False, f"{path} missing; run `zmem init --with-agent-prompt`")


def check_agent_install(preset: str, *, server_name: str = "zerker-memory", config_path: Path | None = None) -> DoctorCheck:
    if preset == "codex":
        path = config_path or Path.home() / ".codex" / "config.toml"
        if not path.exists():
            return DoctorCheck(f"agent_{preset}", False, f"{path} missing; run `zmem agent install {preset}`")
        marker = f"[mcp_servers.{server_name}]"
        if marker in path.read_text(encoding="utf-8"):
            return DoctorCheck(f"agent_{preset}", True, str(path))
        command = f"zmem agent install {preset} --force"
        if config_path is not None:
            command += f" --config-path {path}"
        return DoctorCheck(f"agent_{preset}", False, f"{path} missing {marker}; run `{command}`")
    if preset in {"claude-code", "cursor", "openclaw", "hermes", "generic"}:
        path = config_path or (Path.home() / ".claude" / "mcp.json" if preset == "claude-code" else agent_export_config_path(preset))
        if path is None:
            return DoctorCheck(
                f"agent_{preset}",
                False,
                f"{preset} requires an explicit config path; run `zmem doctor --agent-config {preset}=/path/to/config.json`",
            )
        if not path.exists():
            command = f"zmem agent install {preset}"
            if config_path is not None:
                command += f" --config-path {path}"
            return DoctorCheck(f"agent_{preset}", False, f"{path} missing; run `{command}`")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return DoctorCheck(f"agent_{preset}", False, f"{path} is not valid JSON: {exc}")
        if server_name in payload.get("mcpServers", {}):
            return DoctorCheck(f"agent_{preset}", True, str(path))
        command = f"zmem agent install {preset} --force"
        if config_path is not None:
            command += f" --config-path {path}"
        return DoctorCheck(
            f"agent_{preset}",
            False,
            f"{path} missing mcpServers.{server_name}; run `{command}`",
        )
    return DoctorCheck(f"agent_{preset}", False, f"{preset} does not have a supported default doctor check")


def check_eval() -> DoctorCheck:
    result = run_eval()
    if result["ok"]:
        return DoctorCheck("eval", True, f"{result['passed']} checks passed")
    return DoctorCheck("eval", False, f"{result['failed']} failed: {result}")


def check_providers() -> DoctorCheck:
    result = provider_doctor(live=False)
    configured = [check for check in result["checks"] if check["name"].endswith("_config")]
    return DoctorCheck(
        "providers",
        result["ok"],
        f"{len(configured)} provider config checks; live checks skipped",
    )
