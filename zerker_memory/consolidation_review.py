from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .consolidation import (
    consolidation_audit_report,
    load_consolidation_job_records,
    load_consolidation_summary_records,
    materialize_consolidation_summary,
)
from .consolidation_live import verified_live_event_state
from .consolidation_materialize import (
    _consolidation_ledger_locks,
    default_job_ledger_path,
    default_summary_ledger_path,
)
from .paths import expand_user_path
from .store import AUTHORITY_RANKS, MemoryStore, digest_uri, now_iso, sha256_text, stable_json


CONSOLIDATION_INSPECTION_SCHEMA = "zerker.consolidation_inspection.v1"
CONSOLIDATION_INSPECTION_LIST_SCHEMA = "zerker.consolidation_inspection_list.v1"
CONSOLIDATION_DECISION_SCHEMA = "zerker.consolidation_decision.v1"
CONSOLIDATION_ADMITTED_EVENT = "CONSOLIDATION_ADMITTED"
CONSOLIDATION_DISCARDED_EVENT = "CONSOLIDATION_DISCARDED"
ISO_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def list_consolidation_summaries(
    db_path: Path,
    *,
    job_ledger_path: Path | None = None,
    summary_ledger_path: Path | None = None,
) -> dict[str, Any]:
    path, jobs_path, summaries_path = _review_paths(
        db_path,
        job_ledger_path=job_ledger_path,
        summary_ledger_path=summary_ledger_path,
    )
    with _consolidation_ledger_locks((jobs_path, summaries_path)):
        store = MemoryStore.open_locked_read_snapshot(path)
        try:
            event_state = verified_live_event_state(store)
            audit = consolidation_audit_report(jobs_path, summaries_path)
            summaries = load_consolidation_summary_records(summaries_path)
            records = []
            for summary in summaries:
                decision = _decision_for_summary(store, str(summary["summary_id"]))
                audit_record = _audit_record(audit, str(summary["job_id"]), required=False)
                records.append(
                    {
                        "summary_id": summary["summary_id"],
                        "job_id": summary["job_id"],
                        "scope": summary["scope"],
                        "summary_level": summary["summary_level"],
                        "source_child_count": summary["source_child_count"],
                        "content_digest": summary["content_digest"],
                        "audit_status": None if audit_record is None else audit_record.get("audit_status"),
                        "review_state": decision["state"],
                        "canonical_memory_id": decision.get("canonical_memory_id"),
                    }
                )
            issue_count = _audit_issue_count(audit)
            return {
                "schema": CONSOLIDATION_INSPECTION_LIST_SCHEMA,
                "ok": issue_count == 0,
                "database": str(path.resolve()),
                "job_ledger_path": str(jobs_path.resolve()),
                "summary_ledger_path": str(summaries_path.resolve()),
                "event_merkle_root": event_state["event_merkle_root"],
                "summary_count": len(records),
                "awaiting_review_count": sum(
                    record["review_state"] == "awaiting_review" for record in records
                ),
                "admitted_count": sum(record["review_state"] == "admitted" for record in records),
                "discarded_count": sum(record["review_state"] == "discarded" for record in records),
                "audit_issue_count": issue_count,
                "summaries": records,
                "semantic_truth_guaranteed": False,
            }
        finally:
            store.conn.rollback()
            store.conn.close()


def build_consolidation_summary_inspection(
    db_path: Path,
    summary_id: str,
    *,
    job_ledger_path: Path | None = None,
    summary_ledger_path: Path | None = None,
    inspected_at: str | None = None,
) -> dict[str, Any]:
    timestamp = inspected_at or now_iso()
    _validate_timestamp(timestamp, label="consolidation inspected_at")
    path, jobs_path, summaries_path = _review_paths(
        db_path,
        job_ledger_path=job_ledger_path,
        summary_ledger_path=summary_ledger_path,
    )
    with _consolidation_ledger_locks((jobs_path, summaries_path)):
        store = MemoryStore.open_locked_read_snapshot(path)
        try:
            state = _verified_summary_state(store, jobs_path, summaries_path, summary_id)
            inspection = {
                "schema": CONSOLIDATION_INSPECTION_SCHEMA,
                "ok": True,
                "inspection_id": None,
                "inspection_hash": None,
                "confirmation_id": None,
                "confirmation_hash": None,
                "database": str(path.resolve()),
                "job_ledger_path": str(jobs_path.resolve()),
                "summary_ledger_path": str(summaries_path.resolve()),
                "inspected_at": timestamp,
                "review_state": state["decision"]["state"],
                "actionable": state["decision"]["state"] == "awaiting_review",
                "summary": state["summary_view"],
                "source_verification": state["source_verification"],
                "ledger_audit": state["ledger_audit"],
                "target": state["target"],
                "existing_decision": state["decision"],
                "operator_identity_authenticated": False,
                "canonical_memory_written": state["decision"]["state"] == "admitted",
                "semantic_truth_guaranteed": False,
                "limitations": [
                    "Inspection proves local lineage and deterministic recomputation, not semantic truth.",
                    "The operator identity is asserted CLI metadata unless separately authenticated.",
                    "A principal able to rewrite the database and all local ledgers requires an external proof anchor.",
                ],
            }
            return _finalize_inspection(inspection)
        finally:
            store.conn.rollback()
            store.conn.close()


def validate_consolidation_inspection(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("consolidation inspection must be an object")
    inspection = json.loads(stable_json(dict(value)))
    if inspection.get("schema") != CONSOLIDATION_INSPECTION_SCHEMA:
        raise ValueError("unsupported consolidation inspection schema")
    if inspection.get("ok") is not True:
        raise ValueError("consolidation inspection is not verified")
    expected_hash = _inspection_hash(inspection)
    if inspection.get("inspection_hash") != expected_hash:
        raise ValueError("consolidation inspection hash mismatch")
    if inspection.get("inspection_id") != f"consolidation-inspection:{expected_hash[:24]}":
        raise ValueError("consolidation inspection id mismatch")
    actionable = inspection.get("review_state") == "awaiting_review"
    if inspection.get("actionable") is not actionable:
        raise ValueError("consolidation inspection actionable state mismatch")
    if actionable:
        expected_confirmation_hash = _inspection_confirmation_hash(inspection)
        if inspection.get("confirmation_hash") != expected_confirmation_hash:
            raise ValueError("consolidation inspection confirmation hash mismatch")
        if inspection.get("confirmation_id") != f"consolidation-confirmation:{expected_confirmation_hash[:24]}":
            raise ValueError("consolidation inspection confirmation id mismatch")
    elif inspection.get("confirmation_id") is not None or inspection.get("confirmation_hash") is not None:
        raise ValueError("terminal consolidation inspection cannot be confirmed")
    target = inspection.get("target")
    if not isinstance(target, dict):
        raise ValueError("consolidation inspection target is missing")
    _validate_target(target)
    return inspection


def admit_consolidation_summary(
    db_path: Path,
    inspection: Mapping[str, Any],
    *,
    actor_id: str,
    confirmed_inspection_id: str,
    decided_at: str | None = None,
) -> dict[str, Any]:
    return _apply_consolidation_decision(
        db_path,
        inspection,
        action="admit",
        actor_id=actor_id,
        confirmed_inspection_id=confirmed_inspection_id,
        reason=None,
        decided_at=decided_at,
    )


def discard_consolidation_summary(
    db_path: Path,
    inspection: Mapping[str, Any],
    *,
    actor_id: str,
    confirmed_inspection_id: str,
    reason: str,
    decided_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("consolidation discard reason must be a non-empty string")
    return _apply_consolidation_decision(
        db_path,
        inspection,
        action="discard",
        actor_id=actor_id,
        confirmed_inspection_id=confirmed_inspection_id,
        reason=reason.strip(),
        decided_at=decided_at,
    )


def render_consolidation_inspection_list_summary(report: Mapping[str, Any]) -> str:
    lines = [
        "ZMem consolidation review queue",
        f"Summaries: {report.get('summary_count', 0)}",
        f"Awaiting review: {report.get('awaiting_review_count', 0)}",
        f"Admitted: {report.get('admitted_count', 0)}",
        f"Discarded: {report.get('discarded_count', 0)}",
        f"Audit issues: {report.get('audit_issue_count', 0)}",
    ]
    for record in report.get("summaries", []):
        lines.append(
            f"{record.get('summary_id')}  {record.get('review_state')}  "
            f"{record.get('source_child_count')} sources"
        )
    return "\n".join(lines) + "\n"


def render_consolidation_inspection_summary(
    inspection: Mapping[str, Any],
    *,
    artifact_path: Path | None = None,
) -> str:
    summary = inspection.get("summary") or {}
    source = inspection.get("source_verification") or {}
    target = inspection.get("target") or {}
    lines = [
        "ZMem consolidation inspection",
        f"Summary: {summary.get('summary_id')}",
        f"Review state: {inspection.get('review_state')}",
        f"Audit: {(inspection.get('ledger_audit') or {}).get('audit_status')}",
        f"Sources verified: {source.get('verified_source_count', 0)}/{source.get('source_count', 0)}",
        f"Target memory: {target.get('memory_id')}",
        f"Trust / authority ceiling: {target.get('trust')} / {target.get('authority')}",
        "Semantic truth guaranteed: no",
    ]
    if inspection.get("confirmation_id") is not None:
        lines.append(f"Confirmation: {inspection.get('confirmation_id')}")
    if artifact_path is not None:
        lines.append(f"Inspection file: {artifact_path}")
    return "\n".join(lines) + "\n"


def render_consolidation_decision_summary(
    result: Mapping[str, Any],
    *,
    artifact_path: Path | None = None,
) -> str:
    lines = [
        "ZMem consolidation decision",
        f"Status: {result.get('status')}",
        f"Summary: {result.get('summary_id')}",
        f"Decision: {result.get('action')}",
        f"Canonical memory: {result.get('canonical_memory_id') or 'none'}",
        f"Written this run: {'yes' if result.get('canonical_memory_written_this_run') else 'no'}",
        f"Decision event: {(result.get('decision_event') or {}).get('event_hash')}",
        "Operator identity authenticated: no",
        "Semantic truth guaranteed: no",
    ]
    if artifact_path is not None:
        lines.append(f"Result file: {artifact_path}")
    return "\n".join(lines) + "\n"


def default_inspection_path(db_path: Path, inspection: Mapping[str, Any]) -> Path:
    return (
        expand_user_path(db_path).parent
        / "consolidation"
        / "inspections"
        / f"{str(inspection['inspection_id']).replace(':', '_')}.json"
    )


def default_decision_result_path(db_path: Path, result: Mapping[str, Any]) -> Path:
    return (
        expand_user_path(db_path).parent
        / "consolidation"
        / "results"
        / f"{str(result['result_id']).replace(':', '_')}.json"
    )


def _apply_consolidation_decision(
    db_path: Path,
    inspection_value: Mapping[str, Any],
    *,
    action: str,
    actor_id: str,
    confirmed_inspection_id: str,
    reason: str | None,
    decided_at: str | None,
) -> dict[str, Any]:
    inspection = validate_consolidation_inspection(inspection_value)
    if inspection["review_state"] != "awaiting_review":
        raise ValueError("consolidation summary already has a terminal review decision")
    if confirmed_inspection_id != inspection["confirmation_id"]:
        raise ValueError("consolidation inspection confirmation mismatch")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("consolidation actor_id must be a non-empty string")
    timestamp = decided_at or now_iso()
    _validate_timestamp(timestamp, label="consolidation decided_at")
    path = expand_user_path(db_path)
    if path.resolve() != Path(str(inspection["database"])).resolve():
        raise ValueError("consolidation inspection database path mismatch")
    jobs_path = expand_user_path(Path(str(inspection["job_ledger_path"])))
    summaries_path = expand_user_path(Path(str(inspection["summary_ledger_path"])))
    summary_id = str(inspection["summary"]["summary_id"])

    with _consolidation_ledger_locks((jobs_path, summaries_path)):
        store = MemoryStore(path, treeship_auto_sign=False)
        try:
            store.init()
            store.conn.execute("BEGIN IMMEDIATE")
            verified_live_event_state(store)
            existing = _decision_for_summary(store, summary_id)
            if existing["state"] != "awaiting_review":
                result = _existing_decision_result(store, inspection, existing, action=action)
                store.conn.commit()
                return result

            current = _verified_summary_state(store, jobs_path, summaries_path, summary_id)
            _validate_current_inspection_binding(inspection, current)
            target = current["target"]
            decision_id = str(target["decision_id"])
            memory = None
            write_receipt = None
            if action == "admit":
                memory = store.remember(
                    str(current["summary_view"]["summary_text"]),
                    memory_type="semantic",
                    scope=str(target["scope"]),
                    source_kind="consolidation",
                    trust=float(target["trust"]),
                    authority=str(target["authority"]),
                    status="active",
                    actor_id=actor_id.strip(),
                    parents=list(target["parents"]),
                    labels=list(target["labels"]),
                    source_uri=str(target["source_uri"]),
                    session_id=str(target["session_id"]),
                    parent_action_id=decision_id,
                    memory_id=str(target["memory_id"]),
                    created_at=timestamp,
                    _initialize=False,
                    _commit=False,
                )
                write_receipts = store.memory_write_receipts(memory.id, initialize=False)
                write_receipt = write_receipts[-1]

            payload = _decision_payload(
                action=action,
                decision_id=decision_id,
                inspection=inspection,
                current=current,
                actor_id=actor_id.strip(),
                reason=reason,
                write_receipt=write_receipt,
            )
            event = store._append_event(
                CONSOLIDATION_ADMITTED_EVENT if action == "admit" else CONSOLIDATION_DISCARDED_EVENT,
                actor_id=actor_id.strip(),
                memory_id=None,
                action_id=decision_id,
                payload=payload,
                created_at=timestamp,
            )
            store.conn.commit()
            return _decision_result(
                action=action,
                status="admitted" if action == "admit" else "discarded",
                inspection=inspection,
                actor_id=actor_id.strip(),
                reason=reason,
                event=event,
                memory=None if memory is None else memory.to_dict(),
                write_receipt=write_receipt,
                written_this_run=memory is not None,
            )
        except Exception:
            if store.conn.in_transaction:
                store.conn.rollback()
            raise
        finally:
            store.conn.close()


def _verified_summary_state(
    store: MemoryStore,
    job_ledger_path: Path,
    summary_ledger_path: Path,
    summary_id: str,
) -> dict[str, Any]:
    event_state = verified_live_event_state(store)
    audit = consolidation_audit_report(job_ledger_path, summary_ledger_path)
    summaries = [
        summary
        for summary in load_consolidation_summary_records(summary_ledger_path)
        if summary["summary_id"] == summary_id
    ]
    if len(summaries) != 1:
        raise ValueError(f"consolidation summary must have exactly one ledger record: {summary_id}")
    summary = summaries[0]
    audit_record = _audit_record(audit, str(summary["job_id"]), required=True)
    if audit_record.get("audit_status") != "verified":
        raise ValueError("consolidation summary ledger audit did not verify")
    jobs = [job for job in load_consolidation_job_records(job_ledger_path) if job.job_id == summary["job_id"]]
    pending = next((job for job in jobs if job.status == "pending"), None)
    completed = jobs[-1] if jobs else None
    if pending is None or completed is None or completed.status != "completed":
        raise ValueError("consolidation summary is missing its completed job history")

    source_children = []
    source_states = []
    for memory_id in summary["source_child_ids"]:
        memory = store.get(str(memory_id))
        receipts = store.memory_write_receipts(memory.id, initialize=False)
        verification = store.verify_memory_write_receipt_chain(receipts, initialize=False)
        if not verification["ok"]:
            raise ValueError(f"consolidation source receipt chain did not verify: {memory.id}")
        if memory.status != "active":
            raise ValueError(f"consolidation source is no longer active: {memory.id}")
        expected_digest = str(summary["source_child_digests"].get(memory.id) or "")
        if expected_digest != digest_uri(memory.content):
            raise ValueError(f"consolidation source digest changed: {memory.id}")
        latest_receipt = receipts[-1]
        latest_event = store.conn.execute(
            "SELECT event_hash FROM events WHERE memory_id = ? ORDER BY seq DESC LIMIT 1",
            (memory.id,),
        ).fetchone()
        if latest_event is None or latest_event["event_hash"] != latest_receipt["event_hash"]:
            raise ValueError(f"consolidation source latest event is not receipted: {memory.id}")
        expected_receipt_hash = (
            (summary.get("source_preview") or {}).get("source_receipt_hashes") or {}
        ).get(memory.id)
        if latest_receipt.get("receipt_hash") != expected_receipt_hash:
            raise ValueError(f"consolidation source receipt head changed: {memory.id}")
        initial_object = receipts[0]["treeship_statement"]["object"]
        latest_object = latest_receipt["treeship_statement"]["object"]
        if initial_object.get("memory_type") != memory.type or initial_object.get("scope") != memory.scope:
            raise ValueError(f"consolidation source metadata changed: {memory.id}")
        if latest_object.get("status", initial_object.get("status")) != memory.status:
            raise ValueError(f"consolidation source status receipt mismatch: {memory.id}")
        if latest_object.get("authority", initial_object.get("authority")) != memory.authority:
            raise ValueError(f"consolidation source authority receipt mismatch: {memory.id}")
        expected_trust = latest_object.get("trust", initial_object.get("trust"))
        if expected_trust != memory.trust:
            raise ValueError(f"consolidation source trust receipt mismatch: {memory.id}")
        source_children.append({"child_id": memory.id, "content": memory.content})
        source_states.append(
            {
                "memory_id": memory.id,
                "content_digest": digest_uri(memory.content),
                "status": memory.status,
                "trust": memory.trust,
                "authority": memory.authority,
                "latest_receipt_id": latest_receipt["receipt_id"],
                "latest_receipt_hash": latest_receipt["receipt_hash"],
                "latest_event_hash": latest_event["event_hash"],
            }
        )

    _, recomputed = materialize_consolidation_summary(
        pending,
        source_children=source_children,
        completed_at=str(summary["created_at"]),
        summary_id=str(summary["summary_id"]),
    )
    for key in (
        "summary_id",
        "job_id",
        "scope",
        "summary_level",
        "source_level",
        "source_child_ids",
        "source_child_count",
        "summary_text",
        "content_digest",
    ):
        if recomputed.get(key) != summary.get(key):
            raise ValueError(f"consolidation deterministic summary mismatch: {key}")

    admission = summary.get("admission")
    if not isinstance(admission, dict):
        raise ValueError("consolidation summary admission contract is missing")
    trust_ceiling = admission.get("trust_ceiling")
    authority_ceiling = admission.get("authority_ceiling")
    if not isinstance(trust_ceiling, (int, float)) or not math.isfinite(float(trust_ceiling)):
        raise ValueError("consolidation trust ceiling is invalid")
    if not 0.0 <= float(trust_ceiling) <= 1.0:
        raise ValueError("consolidation trust ceiling must be between 0 and 1")
    if authority_ceiling not in AUTHORITY_RANKS:
        raise ValueError("consolidation authority ceiling is invalid")
    if float(trust_ceiling) > min(float(source["trust"]) for source in source_states):
        raise ValueError("consolidation trust ceiling exceeds a live source")
    weakest_authority = min(
        (str(source["authority"]) for source in source_states),
        key=lambda value: AUTHORITY_RANKS[value],
    )
    if AUTHORITY_RANKS[str(authority_ceiling)] > AUTHORITY_RANKS[weakest_authority]:
        raise ValueError("consolidation authority ceiling exceeds a live source")

    source_state_hash = sha256_text(stable_json(source_states))
    summary_record_hash = sha256_text(stable_json(summary))
    job_record_hash = sha256_text(stable_json(completed.to_dict()))
    audit_record_hash = sha256_text(stable_json(audit_record))
    target = _canonical_target(summary)
    decision = _decision_for_summary(store, summary_id)
    return {
        "summary_view": {
            "summary_id": summary["summary_id"],
            "job_id": summary["job_id"],
            "scope": summary["scope"],
            "summary_level": summary["summary_level"],
            "source_level": summary["source_level"],
            "source_child_ids": list(summary["source_child_ids"]),
            "source_child_count": summary["source_child_count"],
            "source_set_hash": (summary.get("source_preview") or {}).get("source_set_hash"),
            "summary_text": summary["summary_text"],
            "content_digest": summary["content_digest"],
            "summary_record_hash": summary_record_hash,
            "job_record_hash": job_record_hash,
        },
        "source_verification": {
            "verified": True,
            "source_count": len(source_states),
            "verified_source_count": len(source_states),
            "source_state_hash": source_state_hash,
            "source_states": source_states,
            "event_merkle_root": event_state["event_merkle_root"],
            "deterministic_summary_recomputed": True,
            "receipt_chains_verified": True,
        },
        "ledger_audit": {
            "audit_status": audit_record["audit_status"],
            "audit_record_hash": audit_record_hash,
            "audit_issue_count": _audit_issue_count(audit),
        },
        "target": target,
        "decision": decision,
    }


def _canonical_target(summary: Mapping[str, Any]) -> dict[str, Any]:
    source_preview = summary.get("source_preview") or {}
    source_set_hash = str(source_preview.get("source_set_hash") or "")
    target_material = {
        "summary_id": summary["summary_id"],
        "job_id": summary["job_id"],
        "source_set_hash": source_set_hash,
        "content_digest": summary["content_digest"],
    }
    target_hash = sha256_text(stable_json(target_material))
    decision_id = f"consolidation-decision:{target_hash[:24]}"
    return {
        "memory_id": f"mem_consolidated_{target_hash[:16]}",
        "decision_id": decision_id,
        "memory_type": "semantic",
        "scope": summary["scope"],
        "status": "active",
        "trust": float(summary["admission"]["trust_ceiling"]),
        "authority": summary["admission"]["authority_ceiling"],
        "parents": list(summary["source_child_ids"]),
        "labels": [
            "consolidation",
            f"summary:{summary['summary_id']}",
            f"job:{summary['job_id']}",
            f"level:{summary['summary_level']}",
            f"source-set:{source_set_hash}",
        ],
        "source_uri": f"consolidation://{summary['summary_id']}",
        "session_id": f"session://zmem/consolidation/{target_hash[:16]}",
        "trust_ceiling_enforced": True,
        "authority_ceiling_enforced": True,
    }


def _decision_for_summary(store: MemoryStore, summary_id: str) -> dict[str, Any]:
    rows = store.conn.execute(
        """
        SELECT seq, event_type, memory_id, action_id, actor_id, payload_json,
               payload_hash, prev_event_hash, event_hash, merkle_root, created_at
        FROM events
        WHERE event_type IN (?, ?)
        ORDER BY seq ASC
        """,
        (CONSOLIDATION_ADMITTED_EVENT, CONSOLIDATION_DISCARDED_EVENT),
    ).fetchall()
    matches = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        if payload.get("summary_id") != summary_id:
            continue
        if payload.get("schema") != CONSOLIDATION_DECISION_SCHEMA:
            raise ValueError("consolidation decision event schema mismatch")
        expected_action = "admit" if row["event_type"] == CONSOLIDATION_ADMITTED_EVENT else "discard"
        if payload.get("action") != expected_action:
            raise ValueError("consolidation decision event action mismatch")
        if payload.get("decision_id") != row["action_id"]:
            raise ValueError("consolidation decision event id mismatch")
        matches.append((row, payload))
    if len(matches) > 1:
        raise ValueError("consolidation summary has multiple terminal decisions")
    if not matches:
        return {
            "state": "awaiting_review",
            "decision_id": None,
            "canonical_memory_id": None,
        }
    row, payload = matches[0]
    return {
        "state": "admitted" if payload["action"] == "admit" else "discarded",
        "decision_id": payload["decision_id"],
        "canonical_memory_id": payload.get("canonical_memory_id"),
        "actor_id": row["actor_id"],
        "decided_at": row["created_at"],
        "event_hash": row["event_hash"],
        "merkle_root": row["merkle_root"],
        "payload": payload,
    }


def _decision_payload(
    *,
    action: str,
    decision_id: str,
    inspection: Mapping[str, Any],
    current: Mapping[str, Any],
    actor_id: str,
    reason: str | None,
    write_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    target = current["target"]
    return {
        "schema": CONSOLIDATION_DECISION_SCHEMA,
        "action": action,
        "decision_id": decision_id,
        "inspection_id": inspection["inspection_id"],
        "inspection_hash": inspection["inspection_hash"],
        "confirmation_id": inspection["confirmation_id"],
        "actor_id": actor_id,
        "operator_identity_authenticated": False,
        "summary_id": current["summary_view"]["summary_id"],
        "job_id": current["summary_view"]["job_id"],
        "summary_content_digest": current["summary_view"]["content_digest"],
        "source_set_hash": current["summary_view"]["source_set_hash"],
        "source_state_hash": current["source_verification"]["source_state_hash"],
        "canonical_memory_id": target["memory_id"] if action == "admit" else None,
        "canonical_memory_written": action == "admit",
        "target": target,
        "write_receipt_id": None if write_receipt is None else write_receipt["receipt_id"],
        "write_receipt_hash": None if write_receipt is None else write_receipt["receipt_hash"],
        "reason": reason,
        "semantic_truth_guaranteed": False,
    }


def _existing_decision_result(
    store: MemoryStore,
    inspection: Mapping[str, Any],
    existing: Mapping[str, Any],
    *,
    action: str,
) -> dict[str, Any]:
    existing_action = "admit" if existing["state"] == "admitted" else "discard"
    if existing_action != action:
        raise ValueError(
            f"consolidation summary is already {existing['state']}; the opposite decision is not allowed"
        )
    payload = existing.get("payload") or {}
    if payload.get("inspection_id") != inspection.get("inspection_id"):
        raise ValueError("consolidation decision already exists for a different inspection")
    memory = None
    write_receipt = None
    if action == "admit":
        memory_id = str(existing.get("canonical_memory_id") or "")
        memory = store.get(memory_id).to_dict()
        _validate_existing_canonical_memory(
            memory,
            payload.get("target") or {},
            expected_content=str(inspection["summary"]["summary_text"]),
            expected_content_digest=str(inspection["summary"]["content_digest"]),
        )
        receipts = store.memory_write_receipts(memory_id, initialize=False)
        verification = store.verify_memory_write_receipt_chain(receipts, initialize=False)
        if not verification["ok"]:
            raise ValueError("existing consolidation memory receipt chain did not verify")
        write_receipt = receipts[-1]
        if write_receipt.get("receipt_hash") != payload.get("write_receipt_hash"):
            raise ValueError("existing consolidation memory receipt does not match its decision")
    event = {
        "event_hash": existing["event_hash"],
        "merkle_root": existing["merkle_root"],
        "created_at": existing["decided_at"],
        "action_id": existing["decision_id"],
    }
    return _decision_result(
        action=action,
        status="already_admitted" if action == "admit" else "already_discarded",
        inspection=inspection,
        actor_id=str(existing.get("actor_id") or ""),
        reason=payload.get("reason"),
        event=event,
        memory=memory,
        write_receipt=write_receipt,
        written_this_run=False,
    )


def _decision_result(
    *,
    action: str,
    status: str,
    inspection: Mapping[str, Any],
    actor_id: str,
    reason: str | None,
    event: Mapping[str, Any],
    memory: Mapping[str, Any] | None,
    write_receipt: Mapping[str, Any] | None,
    written_this_run: bool,
) -> dict[str, Any]:
    target = inspection["target"]
    result = {
        "schema": CONSOLIDATION_DECISION_SCHEMA,
        "result_id": None,
        "result_hash": None,
        "status": status,
        "action": action,
        "decision_id": target["decision_id"],
        "inspection_id": inspection["inspection_id"],
        "inspection_hash": inspection["inspection_hash"],
        "confirmation_id": inspection["confirmation_id"],
        "actor_id": actor_id,
        "operator_identity_authenticated": False,
        "summary_id": inspection["summary"]["summary_id"],
        "job_id": inspection["summary"]["job_id"],
        "summary_content_digest": inspection["summary"]["content_digest"],
        "source_state_hash": inspection["source_verification"]["source_state_hash"],
        "reason": reason,
        "canonical_memory_id": None if memory is None else memory["id"],
        "canonical_memory": memory,
        "canonical_memory_written": memory is not None,
        "canonical_memory_written_this_run": written_this_run,
        "write_receipt": write_receipt,
        "decision_event": {
            "event_hash": event.get("event_hash"),
            "merkle_root": event.get("merkle_root"),
            "created_at": event.get("created_at"),
            "action_id": event.get("action_id"),
        },
        "treeship_anchor_status": "not_requested",
        "semantic_truth_guaranteed": False,
    }
    payload = dict(result)
    payload["result_id"] = None
    payload["result_hash"] = None
    result_hash = sha256_text(stable_json(payload))
    result["result_hash"] = result_hash
    result["result_id"] = f"consolidation-decision-result:{result_hash[:24]}"
    return result


def _validate_current_inspection_binding(
    inspection: Mapping[str, Any],
    current: Mapping[str, Any],
) -> None:
    if current["decision"]["state"] != "awaiting_review":
        raise ValueError("consolidation summary already has a terminal decision")
    for key in ("summary_id", "job_id", "content_digest", "summary_record_hash", "job_record_hash"):
        if inspection["summary"].get(key) != current["summary_view"].get(key):
            raise ValueError(f"consolidation inspection is stale: {key} changed")
    if (
        inspection["source_verification"].get("source_state_hash")
        != current["source_verification"].get("source_state_hash")
    ):
        raise ValueError("consolidation inspection is stale: source state changed")
    if (
        inspection["ledger_audit"].get("audit_record_hash")
        != current["ledger_audit"].get("audit_record_hash")
    ):
        raise ValueError("consolidation inspection is stale: ledger audit changed")
    if stable_json(inspection["target"]) != stable_json(current["target"]):
        raise ValueError("consolidation inspection is stale: canonical target changed")


def _validate_existing_canonical_memory(
    memory: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    expected_content: str,
    expected_content_digest: str,
) -> None:
    expected = {
        "id": target.get("memory_id"),
        "type": target.get("memory_type"),
        "scope": target.get("scope"),
        "source_kind": "consolidation",
        "trust": target.get("trust"),
        "authority": target.get("authority"),
        "status": target.get("status"),
        "parents": target.get("parents"),
        "labels": target.get("labels"),
    }
    for key, value in expected.items():
        if memory.get(key) != value:
            raise ValueError(f"existing consolidation memory does not match decision target: {key}")
    if memory.get("content") != expected_content:
        raise ValueError("existing consolidation memory does not match reviewed summary content")
    if digest_uri(str(memory.get("content") or "")) != expected_content_digest:
        raise ValueError("existing consolidation memory content digest mismatch")
    if memory.get("content_hash") != sha256_text(expected_content):
        raise ValueError("existing consolidation memory content hash mismatch")


def _finalize_inspection(inspection: dict[str, Any]) -> dict[str, Any]:
    inspection_hash = _inspection_hash(inspection)
    inspection["inspection_hash"] = inspection_hash
    inspection["inspection_id"] = f"consolidation-inspection:{inspection_hash[:24]}"
    if inspection["actionable"]:
        confirmation_hash = _inspection_confirmation_hash(inspection)
        inspection["confirmation_hash"] = confirmation_hash
        inspection["confirmation_id"] = f"consolidation-confirmation:{confirmation_hash[:24]}"
    return inspection


def _inspection_hash(inspection: Mapping[str, Any]) -> str:
    payload = dict(inspection)
    payload["inspection_id"] = None
    payload["inspection_hash"] = None
    payload["confirmation_id"] = None
    payload["confirmation_hash"] = None
    return sha256_text(stable_json(payload))


def _inspection_confirmation_hash(inspection: Mapping[str, Any]) -> str:
    return sha256_text(
        stable_json(
            {
                "schema": CONSOLIDATION_INSPECTION_SCHEMA,
                "inspection_id": inspection["inspection_id"],
                "inspection_hash": inspection["inspection_hash"],
                "database": inspection["database"],
                "summary_id": inspection["summary"]["summary_id"],
                "job_id": inspection["summary"]["job_id"],
                "summary_content_digest": inspection["summary"]["content_digest"],
                "source_state_hash": inspection["source_verification"]["source_state_hash"],
                "audit_record_hash": inspection["ledger_audit"]["audit_record_hash"],
                "target": inspection["target"],
                "review_state": inspection["review_state"],
            }
        )
    )


def _validate_target(target: Mapping[str, Any]) -> None:
    trust = target.get("trust")
    authority = target.get("authority")
    if not isinstance(trust, (int, float)) or not math.isfinite(float(trust)):
        raise ValueError("consolidation target trust is invalid")
    if not 0.0 <= float(trust) <= 1.0:
        raise ValueError("consolidation target trust must be between 0 and 1")
    if authority not in AUTHORITY_RANKS:
        raise ValueError("consolidation target authority is invalid")
    if target.get("trust_ceiling_enforced") is not True:
        raise ValueError("consolidation target trust ceiling is not enforced")
    if target.get("authority_ceiling_enforced") is not True:
        raise ValueError("consolidation target authority ceiling is not enforced")
    parents = target.get("parents")
    labels = target.get("labels")
    if not isinstance(parents, list) or not parents:
        raise ValueError("consolidation target parents are missing")
    if not isinstance(labels, list) or not labels:
        raise ValueError("consolidation target labels are missing")


def _review_paths(
    db_path: Path,
    *,
    job_ledger_path: Path | None,
    summary_ledger_path: Path | None,
) -> tuple[Path, Path, Path]:
    path = expand_user_path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"memory database not found: {path}")
    jobs_path = expand_user_path(job_ledger_path or default_job_ledger_path(path))
    summaries_path = expand_user_path(summary_ledger_path or default_summary_ledger_path(path))
    if not jobs_path.is_file():
        raise FileNotFoundError(f"consolidation job ledger not found: {jobs_path}")
    if not summaries_path.is_file():
        raise FileNotFoundError(f"consolidation summary ledger not found: {summaries_path}")
    return path, jobs_path, summaries_path


def _audit_record(
    audit: Mapping[str, Any],
    job_id: str,
    *,
    required: bool,
) -> dict[str, Any] | None:
    matches = [record for record in audit.get("records", []) if record.get("job_id") == job_id]
    if len(matches) == 1:
        return dict(matches[0])
    if required:
        raise ValueError(f"consolidation audit record not found: {job_id}")
    return None


def _audit_issue_count(audit: Mapping[str, Any]) -> int:
    return sum(
        int(audit.get(key, 0))
        for key in (
            "incomplete_record_count",
            "duplicate_summary_record_count",
            "orphan_summary_count",
            "invalid_job_history_count",
        )
    )


def _validate_timestamp(value: str, *, label: str) -> None:
    if not isinstance(value, str) or not ISO_UTC_PATTERN.match(value):
        raise ValueError(f"{label} must use ISO 8601 UTC form like 2025-01-01T00:00:00Z")
