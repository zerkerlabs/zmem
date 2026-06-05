from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


JSON = dict[str, Any]


def run_mcp_protocol_smoke(
    *,
    db_path: Path | None = None,
    policy_path: Path | None = None,
    agent_id: str = "codex",
    scope: str = "project",
    python_executable: str | None = None,
) -> JSON:
    with tempfile.TemporaryDirectory() as tmp:
        db = db_path or Path(tmp) / "mcp-smoke.sqlite"
        command = [
            python_executable or sys.executable,
            "-m",
            "zerker_memory",
            "--db",
            str(db),
        ]
        if policy_path is not None:
            command.extend(["--policy", str(policy_path)])
        command.append("mcp")
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            client = JsonRpcClient(proc)
            initialize = client.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            client.notify({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            tools = client.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tool_names = [tool["name"] for tool in tools["result"]["tools"]]
            require("memory.inject" in tool_names, "memory.inject missing from MCP tools/list")
            require("memory.why" in tool_names, "memory.why missing from MCP tools/list")
            remember = client.call_tool(
                3,
                "memory.remember",
                {
                    "content": "Use Zerker Memory as the durable memory source for this project",
                    "type": "semantic",
                    "scope": scope,
                    "source": "human",
                    "labels": ["mcp-smoke"],
                },
            )
            remembered = parse_tool_text(remember)
            inject = client.call_tool(
                4,
                "memory.inject",
                {
                    "task": "use Zerker Memory as the durable memory source",
                    "agent": agent_id,
                    "risk": "medium",
                    "scope": scope,
                },
            )
            injection = parse_tool_text(inject)
            require(injection.get("action_id"), "memory.inject did not return action_id")
            require(injection.get("injected_memory_ids"), "memory.inject did not inject the smoke memory")
            action_id = injection["action_id"]
            why = parse_tool_text(client.call_tool(5, "memory.why", {"action_id": action_id}))
            verified = parse_tool_text(client.call_tool(6, "memory.verify", {"action_id": action_id}))
            require(verified.get("ok") is True, "memory.verify returned false")
            return {
                "ok": True,
                "schema": "zerker.mcp_smoke.v1",
                "server": initialize["result"]["serverInfo"],
                "tool_count": len(tool_names),
                "memory_id": remembered["id"],
                "action_id": action_id,
                "injected_memory_ids": injection["injected_memory_ids"],
                "why": {
                    "retrieved_memory_ids": why.get("retrieved_memory_ids", []),
                    "injected_memory_ids": why.get("injected_memory_ids", []),
                    "withheld_memory_ids": why.get("withheld_memory_ids", []),
                },
                "verified": verified,
                "db": str(db),
            }
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()


class JsonRpcClient:
    def __init__(self, proc: subprocess.Popen[str]):
        self.proc = proc

    def notify(self, request: JSON) -> None:
        self._write(request)

    def send(self, request: JSON) -> JSON:
        self._write(request)
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.stderr is not None else ""
            raise RuntimeError(f"MCP server exited before response; stderr={stderr}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        return response

    def call_tool(self, request_id: int, name: str, arguments: JSON) -> JSON:
        return self.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )

    def _write(self, request: JSON) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(request) + "\n")
        self.proc.stdin.flush()


def parse_tool_text(response: JSON) -> Any:
    content = response["result"]["content"]
    require(content and content[0]["type"] == "text", "MCP tool response did not contain text")
    return json.loads(content[0]["text"])


def require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)
