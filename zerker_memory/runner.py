from __future__ import annotations

import hmac
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .store import MemoryStore, now_iso, sha256_text, stable_json


RUN_SCHEMA = "zerker.run.v1"
MEMORY_CONTEXT_SCHEMA = "zerker.memory_context.v1"
MEMORY_CONTEXT_VERIFICATION_SCHEMA = "zerker.memory_context_verification.v1"
MEMORY_CONTEXT_DIGEST_ALG = "sha256"
MEMORY_TYPES = ("episodic", "policy", "procedural", "semantic")


def memory_context_digest(context: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in context.items() if key != "context_digest"}
    return f"{MEMORY_CONTEXT_DIGEST_ALG}:{sha256_text(stable_json(payload))}"


def verify_memory_context(context: Mapping[str, Any]) -> bool:
    expected = context.get("context_digest")
    if context.get("schema") != MEMORY_CONTEXT_SCHEMA or not isinstance(expected, str):
        return False
    return hmac.compare_digest(expected, memory_context_digest(context))


def memory_context_commitment(context: Mapping[str, Any]) -> dict[str, Any]:
    commitment = {
        "schema": MEMORY_CONTEXT_SCHEMA,
        "context_digest": memory_context_digest(context),
        "hash_alg": MEMORY_CONTEXT_DIGEST_ALG,
        "action_id": context.get("action_id"),
        "agent_id": context.get("agent_id"),
        "task_hash": context.get("task_hash"),
        "scope": context.get("scope"),
        "policy_digest": context.get("policy_digest"),
        "merkle_root": context.get("merkle_root"),
        "memory_tree_root": context.get("memory_tree_root"),
        "retrieved_memory_ids": list(context.get("retrieved_memory_ids") or []),
        "injected_memory_ids": list(context.get("injected_memory_ids") or []),
        "withheld_memory_ids": list(context.get("withheld_memory_ids") or []),
        "budget_dropped_memory_ids": list(context.get("budget_dropped_memory_ids") or []),
        "created_at": context.get("created_at"),
    }
    if context.get("continuity") is not None:
        commitment["continuity"] = context.get("continuity")
    return commitment


def verify_memory_context_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("memory context file must contain a JSON object")
    computed_digest = memory_context_digest(payload)
    recorded_digest = payload.get("context_digest")
    ok = verify_memory_context(payload)
    if ok:
        reason = "verified"
    elif payload.get("schema") != MEMORY_CONTEXT_SCHEMA:
        reason = "unsupported-schema"
    elif not isinstance(recorded_digest, str):
        reason = "missing-context-digest"
    else:
        reason = "context-digest-mismatch"
    return {
        "schema": MEMORY_CONTEXT_VERIFICATION_SCHEMA,
        "ok": ok,
        "reason": reason,
        "path": str(path),
        "context_schema": payload.get("schema"),
        "action_id": payload.get("action_id"),
        "agent_id": payload.get("agent_id"),
        "recorded_context_digest": recorded_digest,
        "computed_context_digest": computed_digest,
    }


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
        "query_at",
        "scope",
        "search_query",
        "include_abstained_current",
        "current_resolution",
        "learned_only",
        "unlearned_only",
        "superseded_only",
        "future_only",
        "temporal_projection_at",
        "selection_strategy",
        "selection_reason",
        "selection_exclusions",
        "selected_ids",
        "history_memory_ids",
        "current_memory_ids",
        "future_memory_ids",
        "unlearned_memory_ids",
        "learned_memory_ids",
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
        "temporal_graph",
        "history_temporal_graph",
        "current_temporal_graph",
        "future_temporal_graph",
        "superseded_temporal_graph",
        "unlearned_temporal_graph",
        "learned_temporal_graph",
        "selected_temporal_graph",
        "abstained_temporal_graph",
        "dropped_current_temporal_graph",
        "injected_temporal_graph",
        "withheld_temporal_graph",
        "budget_dropped_temporal_graph",
        "current_ordering",
        "history_ordering",
        "current_history_receipt_metadata",
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
    continuity: Mapping[str, Any] | None = None,
    retrieval_config: dict[str, Any] | None = None,
    retrieval_provider_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not command:
        raise ValueError("run command cannot be empty")
    receipt = store.inject(
        task,
        agent_id=agent_id,
        risk=risk,
        scope=scope,
        retrieval_config=retrieval_config,
        retrieval_provider_config=retrieval_provider_config,
    )
    context = build_context(receipt)
    if continuity is not None:
        context["continuity"] = dict(continuity)
        context["instructions"].append(
            "Inspect `continuity` before acting; stale or unknown state must not be treated as current evidence."
        )
        context["context_digest"] = memory_context_digest(context)
    context_retained = context_path is not None
    if context_path is None:
        file_descriptor, raw_context_path = tempfile.mkstemp(
            prefix=f"zerker-memory-{receipt['action_id']}-",
            suffix=".json",
        )
        context_path = Path(raw_context_path)
        try:
            _write_private_context(file_descriptor, context)
        except Exception:
            context_path.unlink(missing_ok=True)
            raise
    else:
        context_path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor = os.open(context_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        _write_private_context(file_descriptor, context)

    env = os.environ.copy()
    env["ZERKER_ACTION_ID"] = receipt["action_id"]
    env["ZERKER_MEMORY_CONTEXT"] = str(context_path)
    env["ZERKER_MEMORY_CONTEXT_DIGEST"] = context["context_digest"]
    env["ZERKER_MEMORY_DB"] = str(store.db_path)
    env["ZERKER_MEMORY_MERKLE_ROOT"] = receipt["merkle_root"]

    started_at = now_iso()
    try:
        result = subprocess.run(command, env=env)
        completed_at = now_iso()
    finally:
        if not context_retained:
            context_path.unlink(missing_ok=True)
    run_receipt = {
        "schema": RUN_SCHEMA,
        "action_id": receipt["action_id"],
        "agent_id": agent_id,
        "task": task,
        "command": command,
        "command_hash": sha256_text("\u0000".join(command)),
        "exit_code": result.returncode,
        "context_path": str(context_path),
        "context_retained": context_retained,
        "memory_context": memory_context_commitment(context),
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
            "context_retained": context_retained,
            "memory_context_schema": context["schema"],
            "memory_context_digest": context["context_digest"],
        },
    )
    store.conn.commit()
    return run_receipt


def _write_private_context(file_descriptor: int, context: dict[str, Any]) -> None:
    try:
        os.fchmod(file_descriptor, 0o600)
    except Exception:
        os.close(file_descriptor)
        raise
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(context, indent=2, sort_keys=True) + "\n")


def build_context(receipt: dict[str, Any]) -> dict[str, Any]:
    memories = receipt.get("memories")
    if not isinstance(memories, list):
        injected = receipt.get("injected")
        memories = injected if isinstance(injected, list) else []
    retrieval = receipt.get("retrieval") if isinstance(receipt.get("retrieval"), dict) else {}
    packing = retrieval.get("packing") if isinstance(retrieval.get("packing"), dict) else {}
    temporal_context = _build_temporal_context(retrieval)
    budget_dropped = packing.get("budget_dropped") if isinstance(packing.get("budget_dropped"), list) else []
    policy = retrieval.get("policy") if isinstance(retrieval.get("policy"), dict) else {}
    policy_decisions = receipt.get("policy_decisions")
    if not isinstance(policy_decisions, list):
        policy_decisions = policy.get("decisions") if isinstance(policy.get("decisions"), list) else []
    withheld = receipt.get("withheld") if isinstance(receipt.get("withheld"), list) else []
    withheld_memory_ids = receipt.get("withheld_memory_ids")
    if not isinstance(withheld_memory_ids, list):
        withheld_memory_ids = [item["memory_id"] for item in withheld if isinstance(item, dict) and item.get("memory_id")]
    budget_dropped_memory_ids = [
        item["memory_id"]
        for item in budget_dropped
        if isinstance(item, dict) and item.get("memory_id")
    ]
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
    memory_tree = receipt.get("memory_tree") if isinstance(receipt.get("memory_tree"), dict) else {}
    context = {
        "schema": MEMORY_CONTEXT_SCHEMA,
        "hash_alg": receipt.get("hash_alg") or MEMORY_CONTEXT_DIGEST_ALG,
        "merkle_alg": receipt.get("merkle_alg"),
        "action_id": receipt["action_id"],
        "agent_id": receipt.get("agent_id"),
        "task": receipt["task"],
        "task_hash": receipt.get("task_hash") or sha256_text(receipt["task"]),
        "risk": receipt["risk"],
        "scope": retrieval.get("scope"),
        "merkle_root": receipt["merkle_root"],
        "memory_tree_root": memory_tree.get("root"),
        "retrieved_memory_ids": list(receipt.get("retrieved_memory_ids") or []),
        "injected_memory_ids": list(receipt.get("injected_memory_ids") or []),
        "withheld_memory_ids": withheld_memory_ids,
        "budget_dropped_memory_ids": budget_dropped_memory_ids,
        "policy_engine": receipt.get("policy_engine") or policy.get("engine"),
        "policy_digest": policy.get("policy_digest"),
        "policy_checks": receipt["policy_checks"],
        "policy_decisions": policy_decisions,
        "memories": memories,
        "memory_classes": memory_classes,
        "memory_type_summary": memory_type_summary,
        "withheld": withheld,
        "budget_dropped": budget_dropped,
        "temporal": temporal_context,
        "abstention": temporal_context.get("abstention") if temporal_context else None,
        "created_at": receipt.get("created_at"),
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
    context["context_digest"] = memory_context_digest(context)
    return context
