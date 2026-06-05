import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zerker_memory.doctor import check_python_version, run_doctor


class DoctorTest(unittest.TestCase):
    def test_python_version_check_includes_install_and_manual_fix_hints(self):
        class OldPythonVersion:
            major = 3
            minor = 9
            micro = 6

            def __ge__(self, other):
                return (self.major, self.minor, self.micro) >= other

        with patch("zerker_memory.doctor.sys.version_info", OldPythonVersion()), patch(
            "zerker_memory.doctor.find_supported_python",
            return_value="/opt/python3.10/bin/python3.10",
        ):
            check = check_python_version()

        self.assertFalse(check.ok)
        self.assertIn("Python >=3.10 required", check.details)
        self.assertIn("bash install.sh", check.details)
        self.assertIn("/opt/python3.10/bin/python3.10 -m venv .venv", check.details)

    def test_doctor_reports_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_doctor(Path(tmp) / "memory.sqlite")
        names = {check["name"] for check in result["checks"]}
        self.assertIn("python_version", names)
        self.assertIn("sqlite_fts5", names)
        self.assertIn("db_path", names)
        self.assertIn("mcp_command", names)
        self.assertIn("providers", names)
        self.assertIn("eval", names)
        self.assertIsInstance(result["ok"], bool)

    def test_doctor_reports_installed_agent_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            (root / ".claude").mkdir()
            (root / ".codex" / "config.toml").write_text(
                '[mcp_servers.zerker-memory]\ncommand = "zmem"\nargs = ["--db", ".zerker/memory.sqlite", "mcp"]\n',
                encoding="utf-8",
            )
            (root / ".claude" / "mcp.json").write_text(
                json.dumps({"mcpServers": {"zerker-memory": {"command": "zmem", "args": ["mcp"]}}}),
                encoding="utf-8",
            )
            cwd = Path.cwd()
            try:
                os.chdir(root)
                (root / ".zerker").mkdir()
                (root / ".zerker" / "AGENT_PROMPT.md").write_text("Use memory.inject\n", encoding="utf-8")
                with patch.dict(os.environ, {"HOME": str(root)}, clear=False):
                    result = run_doctor(Path(tmp) / "memory.sqlite", run_eval_check=False, agent_presets=["codex", "claude-code"])
            finally:
                os.chdir(cwd)

        checks = {check["name"]: check for check in result["checks"]}
        self.assertTrue(checks["agent_prompt"]["ok"])
        self.assertTrue(checks["agent_codex"]["ok"])
        self.assertTrue(checks["agent_claude-code"]["ok"])

    def test_doctor_fails_agent_check_when_install_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"HOME": str(root)}, clear=False):
                    result = run_doctor(Path(tmp) / "memory.sqlite", run_eval_check=False, agent_presets=["codex"])
            finally:
                os.chdir(cwd)

        checks = {check["name"]: check for check in result["checks"]}
        self.assertFalse(result["ok"])
        self.assertFalse(checks["agent_prompt"]["ok"])
        self.assertFalse(checks["agent_codex"]["ok"])

    def test_doctor_reports_manual_agent_config_when_explicit_path_is_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "openclaw-mcp.json"
            config_path.write_text(
                json.dumps({"mcpServers": {"zerker-memory": {"command": "zmem", "args": ["mcp"]}}}),
                encoding="utf-8",
            )
            cwd = Path.cwd()
            try:
                os.chdir(root)
                (root / ".zerker").mkdir()
                (root / ".zerker" / "AGENT_PROMPT.md").write_text("Use memory.inject\n", encoding="utf-8")
                result = run_doctor(
                    Path(tmp) / "memory.sqlite",
                    run_eval_check=False,
                    agent_config_paths={"openclaw": config_path},
                )
            finally:
                os.chdir(cwd)

        checks = {check["name"]: check for check in result["checks"]}
        self.assertTrue(checks["agent_prompt"]["ok"])
        self.assertTrue(checks["agent_openclaw"]["ok"])

    def test_doctor_reports_manual_agent_config_from_project_default_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / ".zerker" / "agents" / "openclaw-mcp.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps({"mcpServers": {"zerker-memory": {"command": "zmem", "args": ["mcp"]}}}),
                encoding="utf-8",
            )
            cwd = Path.cwd()
            try:
                os.chdir(root)
                (root / ".zerker" / "AGENT_PROMPT.md").write_text("Use memory.inject\n", encoding="utf-8")
                result = run_doctor(
                    Path(tmp) / "memory.sqlite",
                    run_eval_check=False,
                    agent_presets=["openclaw"],
                )
            finally:
                os.chdir(cwd)

        checks = {check["name"]: check for check in result["checks"]}
        self.assertTrue(checks["agent_prompt"]["ok"])
        self.assertTrue(checks["agent_openclaw"]["ok"])


if __name__ == "__main__":
    unittest.main()
