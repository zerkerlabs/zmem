from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runner import run_with_memory
from .store import MemoryStore, digest_uri, now_iso, stable_json


COLD_START_AUDIT_SCHEMA = "zerker.cold_start_audit.v1"
SCHEDULED_RUN_SCHEMA = "zerker.scheduled_agent_run.v1"
SCHEDULED_RUN_PROOF_SCHEMA = "zerker.scheduled_agent_proof.v1"
_CONTINUITY_EVENT_TYPES = {
    "SESSION_STARTED",
    "SESSION_ENDED",
    "SESSION_CHECKPOINTED",
    "SESSION_SNAPSHOTTED",
}


def _parse_utc(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must use ISO 8601 UTC form like 2024-01-01T00:00:00Z") from exc


def _latest_session_event(
    store: MemoryStore,
    *,
    session_id: str,
    scope: str | None,
) -> dict[str, Any] | None:
    placeholders = ", ".join("?" for _ in _CONTINUITY_EVENT_TYPES)
    rows = store.conn.execute(
        f"SELECT * FROM events WHERE event_type IN ({placeholders}) ORDER BY seq DESC",
        tuple(sorted(_CONTINUITY_EVENT_TYPES)),
    ).fetchall()
    for row in rows:
        payload = json.loads(row["payload_json"])
        if payload.get("session_id") != session_id:
            continue
        if scope is not None and payload.get("scope") != scope:
            continue
        lifecycle_id = (
            payload.get("checkpoint_id")
            or payload.get("session_snapshot_id")
            or payload.get("session_end_id")
            or payload.get("session_start_id")
        )
        payload_status = None
        if row["event_type"] == "SESSION_SNAPSHOTTED" and lifecycle_id:
            snapshot_row = store.conn.execute(
                "SELECT deleted_at FROM session_snapshot_payloads WHERE session_snapshot_id = ?",
                (lifecycle_id,),
            ).fetchone()
            payload_status = "soft_deleted" if snapshot_row is not None and snapshot_row["deleted_at"] else "available"
        return {
            "event_type": row["event_type"],
            "event_hash": row["event_hash"],
            "merkle_root": row["merkle_root"],
            "created_at": row["created_at"],
            "scope": payload.get("scope"),
            "lifecycle_id": lifecycle_id,
            "payload_status": payload_status,
        }
    return None


def _compact_restore_evidence(restore: dict[str, Any] | None) -> dict[str, Any]:
    if restore is None:
        return {"status": "not_requested"}
    restored = restore.get("restore") if isinstance(restore.get("restore"), dict) else restore
    receipt = restored.get("receipt") if isinstance(restored.get("receipt"), dict) else {}
    return {
        "status": "verified" if bool((restore.get("restore_verify") or {}).get("ok")) else "completed",
        "source": restore.get("source"),
        "snapshot_hash": restored.get("snapshot_hash"),
        "merkle_root": restored.get("merkle_root"),
        "receipt_id": receipt.get("receipt_id"),
        "receipt_hash": receipt.get("receipt_hash"),
    }


def audit_cold_start(
    store: MemoryStore,
    *,
    session_id: str,
    actor_id: str,
    scope: str | None,
    stale_after_seconds: int,
    restore: dict[str, Any] | None = None,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    if stale_after_seconds < 0:
        raise ValueError("stale_after_seconds must be >= 0")
    store.init()
    evaluated_at = evaluated_at or now_iso()
    evaluated_clock = _parse_utc(evaluated_at)
    prior_state = _latest_session_event(store, session_id=session_id, scope=scope)

    gap_seconds: int | None = None
    if prior_state is None:
        state = "unknown"
        reason = "no-prior-session-state"
    elif prior_state["event_type"] == "SESSION_STARTED":
        state = "unknown"
        reason = "prior-session-not-checkpointed"
    elif prior_state["event_type"] == "SESSION_SNAPSHOTTED" and prior_state["payload_status"] == "soft_deleted":
        state = "unknown"
        reason = "latest-snapshot-payload-unavailable"
    else:
        gap_seconds = int((evaluated_clock - _parse_utc(prior_state["created_at"])).total_seconds())
        if gap_seconds < 0:
            state = "unknown"
            reason = "clock-precedes-prior-state"
        elif gap_seconds > stale_after_seconds:
            state = "stale"
            reason = "wall-clock-gap-exceeded"
        else:
            state = "current"
            reason = "within-wall-clock-gap"

    audit_id = "csa_" + uuid.uuid4().hex[:16]
    prior_merkle_root = store.current_merkle_root()
    snapshot = store.snapshot()
    payload = {
        "schema": COLD_START_AUDIT_SCHEMA,
        "audit_id": audit_id,
        "session_id": session_id,
        "scope": scope,
        "summary": f"cold-start state={state} reason={reason}",
        "state": state,
        "reason": reason,
        "evaluated_at": evaluated_at,
        "stale_after_seconds": stale_after_seconds,
        "gap_seconds": gap_seconds,
        "prior_state": prior_state,
        "restore": _compact_restore_evidence(restore),
        "prior_merkle_root": prior_merkle_root,
        "snapshot_hash": snapshot["snapshot_hash"],
        "snapshot_merkle_root": snapshot["merkle_root"],
        "snapshot_memory_count": snapshot["memory_count"],
        "snapshot_event_count": snapshot["event_count"],
    }
    event = store._append_event("SESSION_COLD_START_AUDITED", actor_id=actor_id, payload=payload)
    store.conn.commit()
    row = store.conn.execute("SELECT * FROM events WHERE event_hash = ?", (event["event_hash"],)).fetchone()
    if row is None:
        raise RuntimeError("cold-start audit event was not persisted")
    receipt = store._lifecycle_receipt_from_event_row(
        row,
        payload,
        mutation="audit_cold_start",
        mutation_id=audit_id,
    )
    return {
        **payload,
        "actor_id": actor_id,
        "event_hash": event["event_hash"],
        "audit_merkle_root": event["merkle_root"],
        "receipt": receipt,
        "receipt_verification": store.verify_lifecycle_receipt(receipt),
    }


def _continuity_context(audit: dict[str, Any]) -> dict[str, Any]:
    receipt = audit["receipt"]
    return {
        "schema": COLD_START_AUDIT_SCHEMA,
        "audit_id": audit["audit_id"],
        "state": audit["state"],
        "reason": audit["reason"],
        "evaluated_at": audit["evaluated_at"],
        "gap_seconds": audit["gap_seconds"],
        "stale_after_seconds": audit["stale_after_seconds"],
        "prior_state": audit["prior_state"],
        "restore": audit["restore"],
        "event_hash": audit["event_hash"],
        "receipt_id": receipt["receipt_id"],
        "receipt_hash": receipt["receipt_hash"],
    }


def _record_scheduled_run_proof(
    store: MemoryStore,
    *,
    scheduled_run_id: str,
    session_id: str,
    actor_id: str,
    scope: str | None,
    restore: dict[str, Any] | None,
    audit: dict[str, Any],
    session_start: dict[str, Any],
    run: dict[str, Any],
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    proof_basis = {
        "schema": SCHEDULED_RUN_PROOF_SCHEMA,
        "scheduled_run_id": scheduled_run_id,
        "session_id": session_id,
        "scope": scope,
        "restore": _compact_restore_evidence(restore),
        "cold_start_audit_receipt_hash": audit["receipt"]["receipt_hash"],
        "session_start_receipt_hash": session_start["receipt"]["receipt_hash"],
        "action_id": run["action_id"],
        "command_hash": run["command_hash"],
        "exit_code": run["exit_code"],
        "memory_context_digest": run["memory_context"]["context_digest"],
        "checkpoint_receipt_hash": checkpoint["receipt"]["receipt_hash"],
    }
    proof_digest = digest_uri(stable_json(proof_basis))
    prior_merkle_root = store.current_merkle_root()
    snapshot = store.snapshot()
    payload = {
        **proof_basis,
        "proof_digest": proof_digest,
        "summary": f"scheduled run exit={run['exit_code']} continuity={audit['state']}",
        "prior_merkle_root": prior_merkle_root,
        "snapshot_hash": snapshot["snapshot_hash"],
        "snapshot_merkle_root": snapshot["merkle_root"],
        "snapshot_memory_count": snapshot["memory_count"],
        "snapshot_event_count": snapshot["event_count"],
    }
    event = store._append_event("SCHEDULED_RUN_PROVED", actor_id=actor_id, payload=payload)
    store.conn.commit()
    row = store.conn.execute("SELECT * FROM events WHERE event_hash = ?", (event["event_hash"],)).fetchone()
    if row is None:
        raise RuntimeError("scheduled-run proof event was not persisted")
    receipt = store._lifecycle_receipt_from_event_row(
        row,
        payload,
        mutation="prove_scheduled_run",
        mutation_id=scheduled_run_id,
    )
    verification = store.verify_lifecycle_receipt(receipt)
    verification["proof_digest_matches"] = proof_digest == digest_uri(stable_json(proof_basis))
    verification["ok"] = bool(verification["ok"] and verification["proof_digest_matches"])
    return {
        **payload,
        "actor_id": actor_id,
        "event_hash": event["event_hash"],
        "proof_merkle_root": event["merkle_root"],
        "receipt": receipt,
        "verification": verification,
    }


def run_scheduled_agent(
    store: MemoryStore,
    command: list[str],
    *,
    session_id: str,
    agent_id: str,
    task: str,
    risk: str,
    scope: str | None = None,
    actor_id: str | None = None,
    stale_after_seconds: int = 86_400,
    restore: dict[str, Any] | None = None,
    context_path: Path | None = None,
    summary: str | None = None,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    if not command:
        raise ValueError("scheduled run command cannot be empty")
    actor_id = actor_id or agent_id
    scheduled_run_id = "srn_" + uuid.uuid4().hex[:16]
    audit = audit_cold_start(
        store,
        session_id=session_id,
        actor_id=actor_id,
        scope=scope,
        stale_after_seconds=stale_after_seconds,
        restore=restore,
        evaluated_at=evaluated_at,
    )
    session_start = store.start_session(
        session_id,
        actor_id=actor_id,
        scope=scope,
        summary=summary or f"scheduled run {scheduled_run_id}",
    )
    run = run_with_memory(
        store,
        command,
        task=task,
        agent_id=agent_id,
        risk=risk,
        scope=scope,
        context_path=context_path,
        continuity=_continuity_context(audit),
    )
    checkpoint = store.checkpoint_session(
        session_id,
        actor_id=actor_id,
        scope=scope,
        summary=f"scheduled run {scheduled_run_id} exit={run['exit_code']}",
    )
    proof = _record_scheduled_run_proof(
        store,
        scheduled_run_id=scheduled_run_id,
        session_id=session_id,
        actor_id=actor_id,
        scope=scope,
        restore=restore,
        audit=audit,
        session_start=session_start,
        run=run,
        checkpoint=checkpoint,
    )
    return {
        "ok": bool(proof["verification"]["ok"]),
        "schema": SCHEDULED_RUN_SCHEMA,
        "scheduled_run_id": scheduled_run_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "actor_id": actor_id,
        "scope": scope,
        "restore": restore,
        "cold_start": audit,
        "session_start": session_start,
        "run": run,
        "checkpoint": checkpoint,
        "proof": proof,
    }


def render_scheduled_run_summary(result: dict[str, Any]) -> str:
    cold_start = result["cold_start"]
    run = result["run"]
    proof = result["proof"]
    return "\n".join(
        [
            "Scheduled agent run",
            f"  id: {result['scheduled_run_id']}",
            f"  continuity: {cold_start['state']} ({cold_start['reason']})",
            f"  gap: {cold_start['gap_seconds'] if cold_start['gap_seconds'] is not None else 'unknown'} seconds",
            f"  admitted: {len(run['memory_receipt'].get('injected_memory_ids') or [])} memories",
            f"  withheld: {len(run['memory_receipt'].get('withheld_memory_ids') or [])} memories",
            f"  exit: {run['exit_code']}",
            f"  checkpoint: {result['checkpoint']['checkpoint_id']}",
            f"  proof: {'verified' if proof['verification']['ok'] else 'failed'}",
            f"  proof digest: {proof['proof_digest']}",
        ]
    ) + "\n"
