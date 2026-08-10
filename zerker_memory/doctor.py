from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .eval import run_eval
from .providers import provider_doctor
from .store import MemoryStore, default_db_path, default_policy_path
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
    policy_path: Path | None = None,
    run_eval_check: bool = True,
    agent_presets: list[str] | tuple[str, ...] | None = None,
    agent_config_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    db_path = db_path or default_db_path()
    policy_path = policy_path or default_policy_path()
    checks = [
        check_python_version(),
        check_sqlite_fts5(),
        check_db_path(db_path),
        check_mcp_command(db_path),
        check_providers(),
    ]
    if agent_presets:
        checks.append(check_agent_prompt())
        checks.extend(
            check_agent_install(
                preset,
                db_path=db_path,
                policy_path=policy_path,
            )
            for preset in agent_presets
        )
    if agent_config_paths:
        if not agent_presets:
            checks.append(check_agent_prompt())
        checks.extend(
            check_agent_install(
                preset,
                config_path=path,
                db_path=db_path,
                policy_path=policy_path,
            )
            for preset, path in agent_config_paths.items()
        )
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


def check_agent_install(
    preset: str,
    *,
    server_name: str = "zerker-memory",
    config_path: Path | None = None,
    db_path: Path | None = None,
    policy_path: Path | None = None,
    working_dir: Path | None = None,
) -> DoctorCheck:
    inspection = inspect_agent_connection(
        preset,
        server_name=server_name,
        config_path=config_path,
        db_path=db_path,
        policy_path=policy_path,
        working_dir=working_dir,
    )
    return DoctorCheck(
        f"agent_{preset}",
        bool(inspection["ok"]),
        str(inspection["details"]),
    )


def inspect_agent_connection(
    preset: str,
    *,
    server_name: str = "zerker-memory",
    config_path: Path | None = None,
    db_path: Path | None = None,
    policy_path: Path | None = None,
    working_dir: Path | None = None,
) -> dict[str, Any]:
    root = (working_dir or Path.cwd()).resolve()
    if preset == "codex":
        path = config_path or Path.home() / ".codex" / "config.toml"
        if not path.exists():
            return _missing_agent_connection(preset, path, config_path=config_path)
        try:
            server = _read_codex_mcp_server(path, server_name)
        except ValueError as exc:
            return _invalid_agent_connection(preset, path, str(exc))
        if server is None:
            marker = f"[mcp_servers.{server_name}]"
            return _missing_agent_connection(preset, path, config_path=config_path, missing=marker)
    elif preset in {"claude-code", "cursor", "openclaw", "hermes", "generic"}:
        path = config_path or (Path.home() / ".claude" / "mcp.json" if preset == "claude-code" else agent_export_config_path(preset))
        if path is None:
            return {
                "ok": False,
                "state": "not_configured",
                "preset": preset,
                "config_path": None,
                "details": (
                    f"{preset} requires an explicit config path; "
                    f"run `zmem doctor --agent-config {preset}=/path/to/config.json`"
                ),
            }
        if not path.exists():
            return _missing_agent_connection(preset, path, config_path=config_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _invalid_agent_connection(preset, path, f"not valid JSON: {exc}")
        server = payload.get("mcpServers", {}).get(server_name)
        if not isinstance(server, dict):
            return _missing_agent_connection(
                preset,
                path,
                config_path=config_path,
                missing=f"mcpServers.{server_name}",
            )
    else:
        return {
            "ok": False,
            "state": "unsupported",
            "preset": preset,
            "config_path": str(config_path) if config_path is not None else None,
            "details": f"{preset} does not have a supported default doctor check",
        }

    command = server.get("command")
    args = server.get("args")
    if not isinstance(command, str) or not command or not isinstance(args, list) or not all(
        isinstance(arg, str) for arg in args
    ):
        return _invalid_agent_connection(preset, path, "MCP server command or args are invalid")
    configured_profile = _configured_value(args, "--profile")
    if "mcp" not in args or configured_profile not in {None, "agent"}:
        return _invalid_agent_connection(
            preset,
            path,
            "must launch the MCP agent profile",
        )

    configured_db = _configured_path(args, "--db", working_dir=root)
    configured_policy = _configured_path(args, "--policy", working_dir=root)
    configured_agent_id = _configured_value(args, "--agent-id")
    expected_db = db_path.expanduser().resolve() if db_path is not None else None
    expected_policy = policy_path.expanduser().resolve() if policy_path is not None else None
    mismatches: list[str] = []
    if expected_db is not None and configured_db != expected_db:
        mismatches.append(f"db={configured_db or 'unbound'} expected={expected_db}")
    if expected_policy is not None and configured_policy != expected_policy:
        mismatches.append(f"policy={configured_policy or 'unbound'} expected={expected_policy}")
    if mismatches:
        command_hint = _agent_rebind_command(preset, path, config_path=config_path)
        return {
            "ok": False,
            "state": "configured_for_another_workspace",
            "preset": preset,
            "config_path": str(path),
            "command": command,
            "args": args,
            "configured_db_path": str(configured_db) if configured_db is not None else None,
            "configured_policy_path": str(configured_policy) if configured_policy is not None else None,
            "configured_agent_id": configured_agent_id,
            "expected_db_path": str(expected_db) if expected_db is not None else None,
            "expected_policy_path": str(expected_policy) if expected_policy is not None else None,
            "details": f"configured for another workspace ({'; '.join(mismatches)}); run `{command_hint}`",
        }

    if configured_agent_id != preset:
        command_hint = _agent_rebind_command(preset, path, config_path=config_path)
        state = "configured_without_bound_identity" if configured_agent_id is None else "configured_for_another_agent"
        identity = configured_agent_id or "unbound"
        return {
            "ok": False,
            "state": state,
            "preset": preset,
            "config_path": str(path),
            "command": command,
            "args": args,
            "configured_db_path": str(configured_db) if configured_db is not None else None,
            "configured_policy_path": str(configured_policy) if configured_policy is not None else None,
            "configured_agent_id": configured_agent_id,
            "expected_agent_id": preset,
            "details": f"agent identity is {identity}; expected {preset}; run `{command_hint}`",
        }

    state = "exported_awaiting_import" if preset in {"cursor", "openclaw", "hermes", "generic"} else "ready_after_reload"
    detail = f"{state.replace('_', ' ')}: {path}"
    if configured_db is not None:
        detail += f" -> {configured_db}"
    return {
        "ok": True,
        "state": state,
        "preset": preset,
        "config_path": str(path),
        "command": command,
        "args": args,
        "configured_db_path": str(configured_db) if configured_db is not None else None,
        "configured_policy_path": str(configured_policy) if configured_policy is not None else None,
        "configured_agent_id": configured_agent_id,
        "expected_db_path": str(expected_db) if expected_db is not None else None,
        "expected_policy_path": str(expected_policy) if expected_policy is not None else None,
        "details": detail,
    }


def _missing_agent_connection(
    preset: str,
    path: Path,
    *,
    config_path: Path | None,
    missing: str | None = None,
) -> dict[str, Any]:
    command = f"zmem agent install {preset}"
    if config_path is not None:
        command += f" --config-path {path}"
    detail = f"{path} missing"
    if missing:
        detail = f"{path} missing {missing}"
    return {
        "ok": False,
        "state": "not_configured",
        "preset": preset,
        "config_path": str(path),
        "details": f"{detail}; run `{command}`",
    }


def _invalid_agent_connection(preset: str, path: Path, details: str) -> dict[str, Any]:
    return {
        "ok": False,
        "state": "invalid_config",
        "preset": preset,
        "config_path": str(path),
        "details": f"{path} {details}",
    }


def _agent_rebind_command(preset: str, path: Path, *, config_path: Path | None) -> str:
    command = f"zmem agent install {preset} --force"
    if config_path is not None:
        command += f" --config-path {path}"
    return command


def _read_codex_mcp_server(path: Path, server_name: str) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    marker = re.escape(f"mcp_servers.{server_name}")
    match = re.search(rf"(?ms)^\[{marker}\]\s*\n(?P<body>.*?)(?=^\[|\Z)", text)
    if match is None:
        return None
    body = match.group("body")
    command_match = re.search(r"(?m)^command\s*=\s*(.+?)\s*$", body)
    args_match = re.search(r"(?m)^args\s*=\s*(\[.*\])\s*$", body)
    if command_match is None or args_match is None:
        raise ValueError(f"[{marker}] is missing command or args")
    try:
        command = json.loads(command_match.group(1))
        args = json.loads(args_match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"[{marker}] has unsupported command or args syntax: {exc}") from exc
    return {"command": command, "args": args}


def _configured_path(args: list[str], option: str, *, working_dir: Path) -> Path | None:
    raw = _configured_value(args, option)
    if raw is None:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = working_dir / path
    return path.resolve()


def _configured_value(args: list[str], option: str) -> str | None:
    try:
        return args[args.index(option) + 1]
    except (ValueError, IndexError):
        return None


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
