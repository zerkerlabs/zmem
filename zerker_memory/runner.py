from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .store import MemoryStore, now_iso, sha256_text


RUN_SCHEMA = "zerker.run.v1"
MEMORY_CONTEXT_SCHEMA = "zerker.memory_context.v1"
MEMORY_TYPES = ("episodic", "policy", "procedural", "semantic")


def _group_memories_by_type(memories: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {memory_type: [] for memory_type in MEMORY_TYPES}
    for memory in memories:
        memory_type = str(memory.get("type") or "")
        if memory_type in grouped:
            grouped[memory_type].append(memory)
    return grouped


def _build_temporal_context(retrieval: dict[str, Any]) -> dict[str, Any] | None:
    temporal = retrieval.get("temporal")
    if not isinstance(temporal, dict):
        return None

    temporal_context: dict[str, Any] = {}
    for key in (
        "temporal_projection_at",
        "selection_strategy",
        "selection_reason",
        "selected_ids",
        "history_memory_ids",
        "current_memory_ids",
        "superseded_memory_ids",
        "resolved_current_memory_ids",
        "dropped_current_memory_ids",
        "abstained_current_memory_ids",
        "conflict_sets",
        "abstention",
    ):
        value = temporal.get(key)
        if value is not None:
            temporal_context[key] = value

    for key in (
        "selected_temporal_graph",
        "injected_temporal_graph",
        "withheld_temporal_graph",
        "budget_dropped_temporal_graph",
    ):
        value = temporal.get(key)
        if isinstance(value, dict):
            temporal_context[key] = value

    return temporal_context or None


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
    memories = receipt.get("memories")
    if not isinstance(memories, list):
        injected = receipt.get("injected")
        memories = injected if isinstance(injected, list) else []
    retrieval = receipt.get("retrieval") if isinstance(receipt.get("retrieval"), dict) else {}
    packing = retrieval.get("packing") if isinstance(retrieval.get("packing"), dict) else {}
    temporal_context = _build_temporal_context(retrieval)
    budget_dropped = packing.get("budget_dropped") if isinstance(packing.get("budget_dropped"), list) else []
    memory_classes = _group_memories_by_type(memories)
    memory_type_summary = packing.get("memory_type_summary") if isinstance(packing.get("memory_type_summary"), dict) else None
    if memory_type_summary is None:
        memory_type_summary = {
            "instruction_types": ["policy", "procedural"],
            "recall_types": ["episodic", "semantic"],
            "injected_ids_by_type": {
                memory_type: [memory["id"] for memory in grouped_memories]
                for memory_type, grouped_memories in memory_classes.items()
            },
            "withheld_ids_by_type": {memory_type: [] for memory_type in MEMORY_TYPES},
            "budget_dropped_ids_by_type": {memory_type: [] for memory_type in MEMORY_TYPES},
        }
    return {
        "schema": MEMORY_CONTEXT_SCHEMA,
        "action_id": receipt["action_id"],
        "task": receipt["task"],
        "risk": receipt["risk"],
        "merkle_root": receipt["merkle_root"],
        "policy_checks": receipt["policy_checks"],
        "memories": memories,
        "memory_classes": memory_classes,
        "memory_type_summary": memory_type_summary,
        "withheld": receipt.get("withheld", []),
        "budget_dropped": budget_dropped,
        "temporal": temporal_context,
        "instructions": [
            "Use only the memories listed in `memories` as durable memory context.",
            "Treat `policy` and `procedural` memories as rules or workflows, not as narrative recall.",
            "Treat `episodic` and `semantic` memories as recall/evidence, not as procedural rules.",
            "Treat `withheld` memories as unavailable and non-authoritative.",
            "Treat `budget_dropped` memories as relevant-but-omitted due to the current context budget.",
            "Use `temporal` to distinguish current, superseded, abstained, and omitted memory envelopes.",
            "Use ZERKER_ACTION_ID when asking Zerker to explain this run later.",
        ],
    }
