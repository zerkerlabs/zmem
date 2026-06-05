from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .store import MemoryStore, now_iso, sha256_text


RUN_SCHEMA = "zerker.run.v1"


def run_with_memory(
    store: MemoryStore,
    command: list[str],
    *,
    task: str,
    agent_id: str,
    risk: str,
    scope: str | None = None,
    context_path: Path | None = None,
) -> dict[str, Any]:
    if not command:
        raise ValueError("run command cannot be empty")
    receipt = store.inject(task, agent_id=agent_id, risk=risk, scope=scope)
    context_path = context_path or default_context_path(receipt["action_id"])
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context = build_context(receipt)
    context_path.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["ZERKER_ACTION_ID"] = receipt["action_id"]
    env["ZERKER_MEMORY_CONTEXT"] = str(context_path)
    env["ZERKER_MEMORY_DB"] = str(store.db_path)
    env["ZERKER_MEMORY_MERKLE_ROOT"] = receipt["merkle_root"]

    started_at = now_iso()
    result = subprocess.run(command, env=env)
    completed_at = now_iso()
    run_receipt = {
        "schema": RUN_SCHEMA,
        "action_id": receipt["action_id"],
        "agent_id": agent_id,
        "task": task,
        "command": command,
        "command_hash": sha256_text("\u0000".join(command)),
        "exit_code": result.returncode,
        "context_path": str(context_path),
        "memory_receipt": receipt,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    store._append_event(
        "RUN_COMPLETED",
        actor_id=agent_id,
        action_id=receipt["action_id"],
        payload={
            "action_id": receipt["action_id"],
            "command_hash": run_receipt["command_hash"],
            "exit_code": result.returncode,
            "context_path": str(context_path),
        },
    )
    store.conn.commit()
    return run_receipt


def default_context_path(action_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"zerker-memory-{action_id}.json"


def build_context(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "zerker.memory_context.v1",
        "action_id": receipt["action_id"],
        "task": receipt["task"],
        "risk": receipt["risk"],
        "merkle_root": receipt["merkle_root"],
        "policy_checks": receipt["policy_checks"],
        "memories": receipt.get("memories", []),
        "withheld": receipt.get("withheld", []),
        "instructions": [
            "Use only the memories listed in `memories` as durable memory context.",
            "Treat `withheld` memories as unavailable and non-authoritative.",
            "Use ZERKER_ACTION_ID when asking Zerker to explain this run later.",
        ],
    }
