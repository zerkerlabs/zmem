from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from zerker_memory.bench import resolve_benchmark_retrieval_config
from zerker_memory.store import MemoryStore, sha256_text, stable_json


PERSIST_BEHAVIOR = "zmem.persist"
RECALL_BEHAVIOR = "zmem.recall"
PERSIST_EVENT_TYPES = {
    "object.created",
    "patch.applied",
    "llm.responded",
    "tool.responded",
    "policy.created",
    "relation.created",
}


@dataclass(frozen=True)
class ActiveGraphMemoryResult:
    behavior: str
    event_id: str
    scope: str
    memory_id: str | None = None
    receipt_id: str | None = None
    treeship: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None


def behavior_names() -> list[str]:
    return [
        PERSIST_BEHAVIOR,
        RECALL_BEHAVIOR,
        "zmem.bench.question_started",
        "zmem.bench.memory_retrieved",
        "zmem.bench.answer_generated",
        "zmem.bench.question_completed",
    ]


def persist(event: Any, *, store: MemoryStore | None = None, db_path: Path | None = None) -> ActiveGraphMemoryResult:
    event_type = _event_type(event)
    if event_type not in PERSIST_EVENT_TYPES:
        raise ValueError(f"zmem.persist does not handle ActiveGraph event type: {event_type}")
    store = store or MemoryStore(db_path)
    payload = _event_payload(event)
    session_id = _session_id(event, payload)
    event_id = _event_id(event, payload)
    scope = str(payload.get("scope") or f"ag:{session_id}")
    content = _memory_content(event_type, payload)
    memory_type = _memory_type(event_type, payload)
    memory = store.remember(
        content,
        memory_type=memory_type,
        scope=scope,
        source_kind=_source_kind(event_type),
        actor_id=str(payload.get("actor_id") or payload.get("agent_id") or "activegraph"),
        labels=["activegraph", event_type],
        source_uri=f"activegraph://event/{event_id}",
        session_id=f"activegraph://session/{session_id}",
        caused_by_event=event_id,
        status=str(payload.get("status") or "active"),
    )
    treeship = _maybe_emit_treeship(
        "memory.write.v1",
        {
            "memory_id": memory.id,
            "content_hash": memory.content_hash,
            "memory_type": memory.type,
            "scope": memory.scope,
            "activegraph_event_id": event_id,
            "activegraph_run_id": _run_id(event, payload),
            "supersedes": payload.get("supersedes"),
        },
    )
    return ActiveGraphMemoryResult(
        behavior=PERSIST_BEHAVIOR,
        event_id=event_id,
        scope=scope,
        memory_id=memory.id,
        treeship=treeship,
        payload=memory.to_dict(),
    )


def recall(event: Any, *, store: MemoryStore | None = None, db_path: Path | None = None) -> ActiveGraphMemoryResult:
    store = store or MemoryStore(db_path)
    payload = _event_payload(event)
    session_id = _session_id(event, payload)
    event_id = _event_id(event, payload)
    scope = str(payload.get("scope") or f"ag:{session_id}")
    task = str(payload.get("prompt") or payload.get("query") or payload.get("task") or "")
    retrieval_mode = os.environ.get("ZMEM_RETRIEVAL_MODE", "fts")
    receipt = store.inject(
        task,
        agent_id=str(payload.get("agent_id") or "activegraph"),
        risk=str(payload.get("risk") or "low"),
        scope=scope,
        retrieval_config=_retrieval_config(retrieval_mode),
    )
    memory_prefix = _memory_prefix(receipt.get("memories", []))
    treeship = _maybe_emit_treeship(
        "memory.read.v1",
        {
            "zmem_receipt_id": receipt["action_id"],
            "trace_sha256": sha256_text(stable_json(receipt.get("retrieval", {}))),
            "activegraph_event_id": event_id,
            "activegraph_run_id": _run_id(event, payload),
            "query_hash": receipt["task_hash"],
            "retrieval_mode": retrieval_mode,
            "memories_returned": len(receipt.get("memories", [])),
            "scope": scope,
        },
    )
    return ActiveGraphMemoryResult(
        behavior=RECALL_BEHAVIOR,
        event_id=event_id,
        scope=scope,
        receipt_id=receipt["action_id"],
        treeship=treeship,
        payload={
            "prepend_context": memory_prefix,
            "receipt": receipt,
            "retrieval_mode": retrieval_mode,
        },
    )


def handle_event(event: Any, *, store: MemoryStore | None = None, db_path: Path | None = None) -> ActiveGraphMemoryResult | None:
    event_type = _event_type(event)
    if event_type in PERSIST_EVENT_TYPES:
        return persist(event, store=store, db_path=db_path)
    if event_type == "llm.requested":
        return recall(event, store=store, db_path=db_path)
    return None


def _retrieval_config(mode: str) -> dict[str, Any]:
    mode_map = {
        "fts": "fts",
        "semantic": "pseudo-embedding",
        "hybrid": "pseudo-embedding-rerank",
    }
    return resolve_benchmark_retrieval_config(mode_map.get(mode, mode))


def _memory_type(event_type: str, payload: Mapping[str, Any]) -> str:
    explicit = payload.get("memory_type")
    if explicit in {"episodic", "semantic", "procedural", "policy"}:
        return str(explicit)
    return {
        "object.created": "semantic",
        "patch.applied": "episodic",
        "llm.responded": "episodic",
        "tool.responded": "episodic",
        "policy.created": "policy",
        "relation.created": "semantic",
    }[event_type]


def _source_kind(event_type: str) -> str:
    if event_type == "policy.created":
        return "system"
    if event_type == "tool.responded":
        return "tool"
    return "agent"


def _memory_content(event_type: str, payload: Mapping[str, Any]) -> str:
    for key in ("memory", "content", "text", "response", "output", "summary"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return json.dumps({"event_type": event_type, "payload": dict(payload)}, sort_keys=True)


def _memory_prefix(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return ""
    lines = ["Relevant persisted memory:"]
    for memory in memories:
        lines.append(f"- [{memory.get('id')}] {memory.get('content', '')}")
    return "\n".join(lines) + "\n\n"


def _maybe_emit_treeship(kind: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if os.environ.get("ZMEM_TREESHIP_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return None
    out_dir = Path(os.environ.get("ZMEM_TREESHIP_OUT", ".zerker/activegraph/treeship"))
    out_dir.mkdir(parents=True, exist_ok=True)
    statement_path = out_dir / f"{kind}-{sha256_text(stable_json(payload))[:16]}.json"
    statement_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cmd = ["treeship", "attest", "receipt", "--system", "system://zmem", "--kind", kind, "--payload-file", str(statement_path)]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "kind": kind,
        "payload_path": str(statement_path),
        "command": cmd,
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _event_payload(event: Any) -> dict[str, Any]:
    payload = _field(event, "payload", default={})
    if isinstance(payload, Mapping):
        return dict(payload)
    return {"content": payload}


def _event_type(event: Any) -> str:
    return str(_field(event, "type", default=_field(event, "event_type", default="")))


def _event_id(event: Any, payload: Mapping[str, Any]) -> str:
    return str(_field(event, "id", default=payload.get("event_id") or payload.get("id") or "ag_evt_unknown"))


def _session_id(event: Any, payload: Mapping[str, Any]) -> str:
    return str(_field(event, "session_id", default=payload.get("session_id") or "default"))


def _run_id(event: Any, payload: Mapping[str, Any]) -> str | None:
    value = _field(event, "run_id", default=payload.get("run_id"))
    return None if value is None else str(value)


def _field(event: Any, name: str, *, default: Any = None) -> Any:
    if isinstance(event, Mapping):
        return event.get(name, default)
    return getattr(event, name, default)


class ZMemActiveGraphPack:
    name = "zmem"
    behaviors = behavior_names()

    def handle(self, event: Any, **kwargs: Any) -> ActiveGraphMemoryResult | None:
        return handle_event(event, **kwargs)
