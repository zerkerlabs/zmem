from __future__ import annotations

import json
import uuid
from typing import Any

from .store import MemoryStore, now_iso, sha256_text, stable_json


FAILURE_MEMORY_SCHEMA = "zerker.failure_memory.v1"
FAILURE_MEMORY_LABEL = "zmem:failure-memory"


def record_failure_memory(
    store: MemoryStore,
    *,
    expected_result: str,
    observed_result: str,
    correction: str,
    invalidation: str,
    confidence: float,
    scope: str,
    actor_id: str,
    source_kind: str = "agent",
    action_id: str | None = None,
    session_id: str | None = None,
    invalidated_memory_ids: list[str] | None = None,
    source_uri: str | None = None,
) -> dict[str, Any]:
    values = {
        "expected_result": expected_result,
        "observed_result": observed_result,
        "correction": correction,
        "invalidation": invalidation,
    }
    for name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    invalidated_memory_ids = list(dict.fromkeys(invalidated_memory_ids or []))
    for memory_id in invalidated_memory_ids:
        store.get(memory_id)

    failure_id = "fail_" + uuid.uuid4().hex[:16]
    payload = {
        "schema": FAILURE_MEMORY_SCHEMA,
        "failure_id": failure_id,
        "action_id": action_id,
        "session_id": session_id,
        "expected_result": expected_result.strip(),
        "observed_result": observed_result.strip(),
        "confidence": float(confidence),
        "correction": correction.strip(),
        "invalidation": {
            "condition": invalidation.strip(),
            "memory_ids": invalidated_memory_ids,
        },
        "recorded_at": now_iso(),
    }
    memory = store.remember(
        stable_json(payload),
        memory_type="episodic",
        scope=scope,
        source_kind=source_kind,
        actor_id=actor_id,
        labels=[
            FAILURE_MEMORY_LABEL,
            "failure:expected",
            "failure:observed",
            "failure:correction",
            "failure:invalidation",
        ],
        source_uri=source_uri or f"zmem://failure/{failure_id}",
        session_id=session_id,
        parent_action_id=action_id,
    )
    receipt = store.memory_write_receipt(memory.id)
    receipt_verification = store.verify_memory_write_receipt(receipt)
    return {
        "ok": bool(receipt_verification["ok"]),
        "schema": "zerker.failure_memory_record.v1",
        "failure": payload,
        "memory": memory.to_dict(),
        "write_receipt": receipt,
        "write_receipt_verification": receipt_verification,
        "review_required": memory.status in {"proposed", "quarantined"},
    }


def inspect_failure_memory(store: MemoryStore, memory_id: str) -> dict[str, Any]:
    memory = store.get(memory_id)
    if FAILURE_MEMORY_LABEL not in memory.labels:
        raise ValueError(f"memory is not a typed failure memory: {memory_id}")
    try:
        payload = json.loads(memory.content)
    except json.JSONDecodeError as exc:
        raise ValueError("failure memory payload is not valid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != FAILURE_MEMORY_SCHEMA:
        raise ValueError("unsupported failure memory schema")
    required = ("failure_id", "expected_result", "observed_result", "confidence", "correction", "invalidation")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"failure memory missing required fields: {', '.join(missing)}")
    receipt = store.memory_write_receipt(memory.id)
    content_hash_verified = sha256_text(memory.content) == memory.content_hash
    receipt_verification = store.verify_memory_write_receipt(receipt)
    return {
        "ok": bool(content_hash_verified and receipt_verification["ok"]),
        "schema": "zerker.failure_memory_inspection.v1",
        "failure": payload,
        "memory": memory.to_dict(),
        "content_hash_verified": content_hash_verified,
        "write_receipt": receipt,
        "write_receipt_verification": receipt_verification,
    }


def render_failure_summary(result: dict[str, Any]) -> str:
    memory = result["memory"]
    failure = result["failure"]
    lines = [
        "Failure memory",
        f"  id: {memory['id']}",
        f"  status: {memory['status']}",
        f"  expected: {failure['expected_result']}",
        f"  observed: {failure['observed_result']}",
        f"  correction: {failure['correction']}",
        f"  invalidation: {failure['invalidation']['condition']}",
        f"  receipt: {'verified' if result['write_receipt_verification']['ok'] else 'failed'}",
    ]
    if result.get("review_required"):
        lines.append("  next: review before promotion")
    return "\n".join(lines) + "\n"
