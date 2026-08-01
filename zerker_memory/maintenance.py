from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .health import (
    CATEGORY_ORDER,
    _build_memory_health_report_from_connection,
    _open_read_only,
)
from .paths import expand_user_path
from .store import EVENT_SCHEMA, HASH_ALG, MemoryStore, merkle_root, now_iso, sha256_text, stable_json


MAINTENANCE_PLAN_SCHEMA = "zerker.memory_maintenance_plan.v1"
MAINTENANCE_RESULT_SCHEMA = "zerker.memory_maintenance_result.v1"
MAINTENANCE_VERIFICATION_SCHEMA = "zerker.memory_maintenance_verification.v1"
MAINTENANCE_PLANNER = "zerker.deterministic_memory_maintenance.v1"
MAX_SUMMARY_ITEMS = 5
ISO_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def build_memory_maintenance_plan(
    db_path: Path,
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    path = expand_user_path(db_path)
    timestamp = evaluated_at or now_iso()
    if not ISO_UTC_PATTERN.match(timestamp):
        raise ValueError("maintenance evaluated_at must use ISO 8601 UTC form like 2025-01-01T00:00:00Z")
    if not path.is_file():
        return _finalize_plan(
            {
                "schema": MAINTENANCE_PLAN_SCHEMA,
                "planner": MAINTENANCE_PLANNER,
                "ok": False,
                "read_only_preview": True,
                "db_path": str(path),
                "evaluated_at": timestamp,
                "source": None,
                "findings": [],
                "selectable_actions": [],
                "review_items": [],
                "summary": _summary_counts(0, 0, 0),
                "semantic_truth_claimed": False,
                "limitations": _plan_limitations(),
                "error": {
                    "code": "database_not_found",
                    "message": f"memory database not found: {path}",
                },
            }
        )

    try:
        connection = _open_read_only(path)
    except sqlite3.Error as exc:
        return _failed_plan(path, timestamp, code="database_open_failed", message=str(exc))

    try:
        connection.execute("BEGIN")
        health_report = _build_memory_health_report_from_connection(
            connection,
            path=path,
            evaluated_at=timestamp,
        )
        if not health_report.get("ok"):
            error = health_report.get("error") or {}
            return _failed_plan(
                path,
                timestamp,
                code=str(error.get("code") or "health_audit_failed"),
                message=str(error.get("message") or "memory health audit failed"),
            )
        state = _database_state(connection)
    except (json.JSONDecodeError, KeyError, sqlite3.Error, TypeError, ValueError) as exc:
        return _failed_plan(path, timestamp, code="database_read_failed", message=str(exc))
    finally:
        connection.close()

    health_report_hash = _digest(health_report)
    findings: list[dict[str, Any]] = []
    selectable_actions: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    envelopes = state.pop("memory_envelopes_by_id")

    for category in CATEGORY_ORDER:
        for finding in health_report["findings"].get(category, []):
            finding_record = _finding_record(finding)
            findings.append(finding_record)
            memory_ids = list(finding_record["memory_ids"])
            if finding_record["reason"] == "active_memory_expired" and len(memory_ids) == 1:
                memory_id = memory_ids[0]
                envelope = envelopes.get(memory_id)
                if envelope is None:
                    raise ValueError(f"health finding references missing memory: {memory_id}")
                if envelope.get("latest_receipt_hash") is None:
                    review_items.append(
                        _review_item(
                            finding_record,
                            reason_override="expired_memory_requires_verified_provenance",
                            guidance_override=(
                                "The expiry is observable, but the memory has no write receipt; review it manually."
                            ),
                        )
                    )
                else:
                    selectable_actions.append(
                        _expiry_action(
                            finding_record,
                            envelope=envelope,
                            health_report_hash=health_report_hash,
                        )
                    )
            else:
                review_items.append(_review_item(finding_record))

    plan = {
        "schema": MAINTENANCE_PLAN_SCHEMA,
        "planner": MAINTENANCE_PLANNER,
        "ok": True,
        "read_only_preview": True,
        "db_path": str(path.resolve()),
        "evaluated_at": timestamp,
        "source": {
            "health_report_schema": health_report["schema"],
            "health_report_hash": health_report_hash,
            **state,
        },
        "findings": findings,
        "selectable_actions": selectable_actions,
        "review_items": review_items,
        "summary": _summary_counts(
            len(findings),
            len(selectable_actions),
            len(review_items),
        ),
        "semantic_truth_claimed": False,
        "limitations": _plan_limitations(),
        "error": None,
    }
    return _finalize_plan(plan)


def apply_memory_maintenance_plan(
    db_path: Path,
    plan: Mapping[str, Any],
    *,
    selected_action_id: str,
    actor_id: str,
    confirmed_plan_id: str,
) -> dict[str, Any]:
    canonical_plan = _validate_plan(plan)
    if not canonical_plan.get("ok"):
        raise ValueError("cannot apply a failed maintenance plan")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("maintenance actor_id must be a non-empty string")
    if confirmed_plan_id != canonical_plan["plan_id"]:
        raise ValueError("maintenance plan confirmation mismatch")
    action = _selected_action(canonical_plan, selected_action_id)
    _validate_expiry_action(canonical_plan, action)
    path = expand_user_path(db_path)
    if path.resolve() != Path(str(canonical_plan["db_path"])).resolve():
        raise ValueError("maintenance plan database path mismatch")
    if not path.is_file():
        raise ValueError(f"memory database not found: {path}")

    store = MemoryStore(path, treeship_auto_sign=False)
    try:
        store.init()
        store.conn.execute("BEGIN IMMEDIATE")
        target_receipts = store.memory_write_receipts(
            str(action["target_memory_id"]),
            initialize=False,
        )
        receipt_chain_verification = store.verify_memory_write_receipt_chain(
            target_receipts,
            initialize=False,
        )
        if not receipt_chain_verification["ok"]:
            raise ValueError(
                "maintenance action precondition failed: write receipt chain is not verified"
            )
        existing = _existing_maintenance_receipt(canonical_plan, action, target_receipts)
        if existing is not None:
            result = _maintenance_result(
                store,
                canonical_plan,
                action,
                actor_id=actor_id,
                receipt=existing,
                status="already_applied",
                state_before=dict(canonical_plan["source"]),
                applied_count=0,
            )
            store.conn.commit()
            return result

        state_before = _database_state(store.conn)
        state_before.pop("memory_envelopes_by_id")
        expected_source = canonical_plan["source"]
        if state_before["state_hash"] != expected_source.get("state_hash"):
            raise ValueError("maintenance plan is stale: database state hash changed")
        if state_before["merkle_root"] != expected_source.get("merkle_root"):
            raise ValueError("maintenance plan is stale: database Merkle root changed")

        target = store.get(str(action["target_memory_id"]))
        current_envelope = _memory_envelope(store.conn, target.id)
        preconditions = action["preconditions"]
        if current_envelope["state_leaf_hash"] != preconditions.get("memory_state_hash"):
            raise ValueError("maintenance action precondition failed: memory state changed")
        if target.status != preconditions.get("status"):
            raise ValueError("maintenance action precondition failed: status changed")
        if target.expires_at != preconditions.get("expires_at"):
            raise ValueError("maintenance action precondition failed: expires_at changed")
        if not target.expires_at or target.expires_at > canonical_plan["evaluated_at"]:
            raise ValueError("maintenance action precondition failed: memory is not expired")
        if target.expires_at > now_iso():
            raise ValueError("maintenance action precondition failed: expiry is still in the future")
        if action.get("operation") != "expire":
            raise ValueError("unsupported maintenance operation")

        transition = store._expire_in_transaction(
            target.id,
            actor_id=actor_id.strip(),
            reason="explicit_expiry_reached",
            maintenance={
                "schema": MAINTENANCE_PLAN_SCHEMA,
                "plan_id": canonical_plan["plan_id"],
                "plan_hash": canonical_plan["plan_hash"],
                "action_id": action["action_id"],
                "health_report_hash": canonical_plan["source"]["health_report_hash"],
                "finding_ids": list(action["finding_ids"]),
            },
        )
        result = _maintenance_result(
            store,
            canonical_plan,
            action,
            actor_id=actor_id.strip(),
            receipt=transition["receipt"],
            status="applied",
            state_before=state_before,
            applied_count=1,
        )
        store.conn.commit()
        return result
    except Exception:
        if store.conn.in_transaction:
            store.conn.rollback()
        raise
    finally:
        store.conn.close()


def verify_memory_maintenance_result(
    db_path: Path,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    verification = {
        "schema": MAINTENANCE_VERIFICATION_SCHEMA,
        "ok": False,
        "status": "invalid",
        "result_id": result.get("result_id") if isinstance(result, Mapping) else None,
        "result_hash": result.get("result_hash") if isinstance(result, Mapping) else None,
        "verified_transition_count": 0,
        "current_merkle_root": None,
        "current_state_hash": None,
        "state_matches_result": None,
        "state_advanced": None,
        "out_of_band_state_change": None,
        "target_state_checks": [],
        "semantic_truth_claimed": False,
        "error": None,
    }
    try:
        canonical_result = _validate_result(result)
        path = expand_user_path(db_path)
        if path.resolve() != Path(str(canonical_result["db_path"])).resolve():
            raise ValueError("maintenance result database path mismatch")
        if not path.is_file():
            raise ValueError(f"memory database not found: {path}")
        store = MemoryStore(path, treeship_auto_sign=False)
        try:
            store.init()
            for transition in canonical_result.get("transitions", []):
                memory_id = str(transition["memory_id"])
                receipt_id = str(transition["receipt_id"])
                receipts = store.memory_write_receipts(memory_id)
                receipt_index = next(
                    (index for index, receipt in enumerate(receipts) if receipt["receipt_id"] == receipt_id),
                    None,
                )
                if receipt_index is None:
                    raise ValueError(f"maintenance receipt not found: {receipt_id}")
                receipt = receipts[receipt_index]
                if receipt["receipt_hash"] != transition.get("receipt_hash"):
                    raise ValueError(f"maintenance receipt hash mismatch: {receipt_id}")
                receipt_chain_verification = store.verify_memory_write_receipt_chain(
                    receipts[: receipt_index + 1]
                )
                if not receipt_chain_verification["ok"]:
                    raise ValueError(f"maintenance receipt chain verification failed: {receipt_id}")
                statement = receipt["treeship_statement"]
                maintenance = statement.get("object", {}).get("maintenance")
                if not isinstance(maintenance, dict):
                    raise ValueError(f"maintenance receipt reference missing: {receipt_id}")
                if maintenance.get("plan_id") != canonical_result["plan_id"]:
                    raise ValueError(f"maintenance receipt plan mismatch: {receipt_id}")
                if maintenance.get("plan_hash") != canonical_result["plan_hash"]:
                    raise ValueError(f"maintenance receipt plan hash mismatch: {receipt_id}")
                if maintenance.get("action_id") != canonical_result["selected_action_id"]:
                    raise ValueError(f"maintenance receipt action mismatch: {receipt_id}")
                statement_object = statement.get("object", {})
                if (
                    transition.get("operation") != "expire"
                    or transition.get("old_status") != "active"
                    or transition.get("new_status") != "expired"
                    or statement_object.get("mutation") != "expire"
                    or statement_object.get("previous_status") != "active"
                    or statement_object.get("status") != "expired"
                    or transition.get("event_hash") != receipt.get("event_hash")
                    or transition.get("merkle_root") != receipt.get("merkle_root")
                    or transition.get("receipt_verified") is not True
                ):
                    raise ValueError(f"maintenance transition mismatch: {receipt_id}")
                verification["verified_transition_count"] += 1
            current_state = _database_state(store.conn)
            current_envelopes = current_state.pop("memory_envelopes_by_id")
            result_state = canonical_result["state_after"]
            verification["current_merkle_root"] = current_state["merkle_root"]
            verification["current_state_hash"] = current_state["state_hash"]
            verification["state_matches_result"] = current_state["state_hash"] == result_state["state_hash"]
            verification["state_advanced"] = current_state["merkle_root"] != result_state["merkle_root"]
            target_state_checks = []
            for transition in canonical_result["transitions"]:
                memory_id = str(transition["memory_id"])
                envelope = current_envelopes.get(memory_id)
                derived = _event_derived_memory_status(store.conn, memory_id)
                current_status = envelope.get("status") if isinstance(envelope, dict) else None
                status_matches = current_status == derived["status"] and current_status is not None
                target_state_checks.append(
                    {
                        "memory_id": memory_id,
                        "current_status": current_status,
                        "event_derived_status": derived["status"],
                        "last_status_event_hash": derived["event_hash"],
                        "status_matches_event_log": status_matches,
                    }
                )
            verification["target_state_checks"] = target_state_checks
            verification["out_of_band_state_change"] = (
                any(not check["status_matches_event_log"] for check in target_state_checks)
                or (not verification["state_matches_result"] and not verification["state_advanced"])
            )
        finally:
            store.conn.close()
        verification["ok"] = True
        if verification["out_of_band_state_change"]:
            verification["status"] = "verified_historical_with_state_divergence"
        elif verification["state_matches_result"]:
            verification["status"] = "verified"
        else:
            verification["status"] = "verified_historical"
    except (KeyError, sqlite3.Error, TypeError, ValueError) as exc:
        verification["error"] = str(exc)
    return verification


def render_memory_maintenance_plan_summary(plan: Mapping[str, Any], *, artifact_path: Path | None = None) -> str:
    lines = [
        "ZMem maintenance preview",
        f"Plan: {plan.get('plan_id') or 'unavailable'}",
        f"Database: {plan.get('db_path')}",
        f"Audit: {'complete' if plan.get('ok') else 'failed'}",
    ]
    if not plan.get("ok"):
        error = plan.get("error") or {}
        lines.append(f"Error: {error.get('message') or 'maintenance preview failed'}")
        lines.append("No memory changed.")
        return "\n".join(lines) + "\n"
    summary = plan.get("summary") or {}
    source = plan.get("source") or {}
    lines.extend(
        [
            f"State root: {source.get('state_hash')}",
            f"Findings: {summary.get('finding_count', 0)}",
            f"Selectable actions: {summary.get('selectable_action_count', 0)}",
            f"Review required: {summary.get('review_item_count', 0)}",
        ]
    )
    actions = list(plan.get("selectable_actions") or [])
    for action in actions[:MAX_SUMMARY_ITEMS]:
        lines.append(
            f"- {action['action_id']} expire {action['target_memory_id']} "
            f"({action['expected_transition']['from']} -> {action['expected_transition']['to']})"
        )
    if len(actions) > MAX_SUMMARY_ITEMS:
        lines.append(f"- ... {len(actions) - MAX_SUMMARY_ITEMS} more selectable actions")
    if artifact_path is not None:
        lines.append(f"Plan file: {artifact_path}")
    lines.append("No memory changed.")
    return "\n".join(lines) + "\n"


def render_memory_maintenance_result_summary(
    result: Mapping[str, Any],
    *,
    artifact_path: Path | None = None,
) -> str:
    transitions = list(result.get("transitions") or [])
    lines = [
        "ZMem maintenance result",
        f"Result: {result.get('result_id')}",
        f"Status: {result.get('status')}",
        f"Action: {result.get('selected_action_id')}",
        f"Applied: {result.get('applied_count', 0)}",
        f"Receipts verified: {result.get('verified_receipt_count', 0)}/{len(transitions)}",
        f"State root: {(result.get('state_before') or {}).get('merkle_root')} -> {(result.get('state_after') or {}).get('merkle_root')}",
        "Replan required: yes",
    ]
    if artifact_path is not None:
        lines.append(f"Result file: {artifact_path}")
    return "\n".join(lines) + "\n"


def render_memory_maintenance_verification_summary(verification: Mapping[str, Any]) -> str:
    lines = [
        "ZMem maintenance verification",
        f"Result: {verification.get('result_id')}",
        f"Verification: {'passed' if verification.get('ok') else 'failed'}",
        f"Transitions verified: {verification.get('verified_transition_count', 0)}",
    ]
    if verification.get("ok"):
        state = "matches result"
        if verification.get("out_of_band_state_change"):
            state = "diverged without a new event"
        elif verification.get("state_advanced"):
            state = "advanced after result"
        lines.append(f"Current state: {state}")
    if verification.get("error"):
        lines.append(f"Error: {verification['error']}")
    lines.append("Semantic truth: not evaluated")
    return "\n".join(lines) + "\n"


def load_json_artifact(path: Path) -> dict[str, Any]:
    value = json.loads(expand_user_path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("maintenance artifact must be a JSON object")
    return value


def write_json_artifact(path: Path, value: Mapping[str, Any], *, force: bool = False) -> Path:
    destination = expand_user_path(path)
    if destination.exists() and not force:
        raise FileExistsError(f"maintenance artifact already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def default_maintenance_plan_path(db_path: Path, plan: Mapping[str, Any]) -> Path:
    return expand_user_path(db_path).parent / "maintenance" / f"{plan['plan_id']}.json"


def default_maintenance_result_path(db_path: Path, result: Mapping[str, Any]) -> Path:
    return expand_user_path(db_path).parent / "maintenance" / f"{result['result_id']}.json"


def _failed_plan(path: Path, timestamp: str, *, code: str, message: str) -> dict[str, Any]:
    return _finalize_plan(
        {
            "schema": MAINTENANCE_PLAN_SCHEMA,
            "planner": MAINTENANCE_PLANNER,
            "ok": False,
            "read_only_preview": True,
            "db_path": str(path),
            "evaluated_at": timestamp,
            "source": None,
            "findings": [],
            "selectable_actions": [],
            "review_items": [],
            "summary": _summary_counts(0, 0, 0),
            "semantic_truth_claimed": False,
            "limitations": _plan_limitations(),
            "error": {"code": code, "message": message},
        }
    )


def _database_state(connection: sqlite3.Connection) -> dict[str, Any]:
    event_rows = connection.execute(
        """
        SELECT seq, event_type, memory_id, action_id, actor_id, payload_json,
               payload_hash, prev_event_hash, event_hash, merkle_root, created_at
        FROM events
        ORDER BY seq
        """
    ).fetchall()
    event_hashes: list[str] = []
    expected_previous_hash = sha256_text("genesis")
    for row in event_rows:
        payload_json = str(row["payload_json"])
        if sha256_text(payload_json) != row["payload_hash"]:
            raise ValueError(f"event payload hash mismatch at seq {row['seq']}")
        if row["prev_event_hash"] != expected_previous_hash:
            raise ValueError(f"event chain predecessor mismatch at seq {row['seq']}")
        event_material = stable_json(
            {
                "event_schema": EVENT_SCHEMA,
                "hash_alg": HASH_ALG,
                "event_type": row["event_type"],
                "memory_id": row["memory_id"],
                "action_id": row["action_id"],
                "actor_id": row["actor_id"],
                "payload_hash": row["payload_hash"],
                "prev_event_hash": row["prev_event_hash"],
                "created_at": row["created_at"],
            }
        )
        event_hash = sha256_text(event_material)
        if event_hash != row["event_hash"]:
            raise ValueError(f"event hash mismatch at seq {row['seq']}")
        event_hashes.append(event_hash)
        if merkle_root(event_hashes) != row["merkle_root"]:
            raise ValueError(f"event Merkle root mismatch at seq {row['seq']}")
        expected_previous_hash = event_hash
    latest_receipt_by_memory_id: dict[str, dict[str, Any]] = {}
    for row in connection.execute(
        """
        SELECT receipt_id, receipt_schema, hash_alg, merkle_alg, memory_id, actor_uri,
               session_id, parent_action_id, source_uri, content_digest, environment_hash,
               event_hash, merkle_root, treeship_statement_json, created_at, receipt_hash
        FROM memory_write_receipts
        ORDER BY memory_id, created_at, receipt_id
        """
    ).fetchall():
        latest_receipt_by_memory_id[str(row["memory_id"])] = dict(row)

    envelopes: dict[str, dict[str, Any]] = {}
    for row in connection.execute(
        """
        SELECT id, type, content, scope, source_kind, trust, authority, status,
               parents_json, labels_json, created_at, updated_at, expires_at, content_hash
        FROM memories
        ORDER BY id
        """
    ).fetchall():
        memory_id = str(row["id"])
        latest_receipt = latest_receipt_by_memory_id.get(memory_id)
        material = {
            "memory_id": memory_id,
            "type": row["type"],
            "scope": row["scope"],
            "source_kind": row["source_kind"],
            "trust": row["trust"],
            "authority": row["authority"],
            "status": row["status"],
            "parents": json.loads(row["parents_json"]),
            "labels": json.loads(row["labels_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "expires_at": row["expires_at"],
            "persisted_content_hash": row["content_hash"],
            "computed_content_hash": sha256_text(str(row["content"])),
            "latest_receipt_hash": latest_receipt.get("receipt_hash") if latest_receipt else None,
            "latest_receipt_record_hash": _digest(latest_receipt) if latest_receipt else None,
        }
        material["state_leaf_hash"] = _digest(material)
        envelopes[memory_id] = material

    memory_leaf_hashes = [envelopes[memory_id]["state_leaf_hash"] for memory_id in sorted(envelopes)]
    memory_state_root = merkle_root(memory_leaf_hashes)
    head = event_rows[-1] if event_rows else None
    computed_merkle_root = merkle_root(event_hashes)
    recorded_merkle_root = str(head["merkle_root"]) if head is not None else computed_merkle_root
    if recorded_merkle_root != computed_merkle_root:
        raise ValueError("event log Merkle root mismatch")
    state = {
        "event_count": len(event_rows),
        "head_event_hash": str(head["event_hash"]) if head is not None else None,
        "merkle_root": computed_merkle_root,
        "memory_count": len(envelopes),
        "memory_state_root": memory_state_root,
    }
    state["state_hash"] = _digest(state)
    state["memory_envelopes_by_id"] = envelopes
    return state


def _memory_envelope(connection: sqlite3.Connection, memory_id: str) -> dict[str, Any]:
    state = _database_state(connection)
    envelope = state["memory_envelopes_by_id"].get(memory_id)
    if envelope is None:
        raise KeyError(f"memory not found: {memory_id}")
    return envelope


def _event_derived_memory_status(connection: sqlite3.Connection, memory_id: str) -> dict[str, Any]:
    status = None
    event_hash = None
    for row in connection.execute(
        """
        SELECT event_type, memory_id, payload_json, event_hash
        FROM events
        ORDER BY seq
        """
    ).fetchall():
        event_type = str(row["event_type"])
        payload = json.loads(str(row["payload_json"]))
        directly_affected = row["memory_id"] == memory_id
        revoked_ids = payload.get("revoked_ids") if event_type == "REVOKED" else None
        revoked_by_ancestor = isinstance(revoked_ids, list) and memory_id in revoked_ids
        if not directly_affected and not revoked_by_ancestor:
            continue
        next_status = None
        if event_type in {"OBSERVED", "PROPOSED"}:
            next_status = payload.get("status")
        elif event_type == "PROMOTED":
            next_status = "active"
        elif event_type == "REJECTED":
            next_status = "deprecated"
        elif event_type == "REVOKED":
            next_status = "revoked"
        elif event_type == "FORGOTTEN":
            next_status = "forgotten"
        elif event_type == "EXPIRED":
            next_status = "expired"
        if next_status is not None:
            status = str(next_status)
            event_hash = str(row["event_hash"])
    return {"status": status, "event_hash": event_hash}


def _finding_record(finding: Mapping[str, Any]) -> dict[str, Any]:
    evidence = dict(finding.get("evidence") or {})
    for key in ("subject_key", "relation"):
        value = evidence.pop(key, None)
        if value is not None:
            evidence[f"{key}_hash"] = sha256_text(str(value))
    material = {
        "category": str(finding["category"]),
        "reason": str(finding["reason"]),
        "memory_ids": sorted(str(value) for value in finding["memory_ids"]),
        "evidence": evidence,
        "semantic_truth_claimed": False,
    }
    finding_hash = _digest(material)
    return {
        "finding_id": f"mhf_{finding_hash.split(':', 1)[1][:24]}",
        "finding_hash": finding_hash,
        **material,
    }


def _expiry_action(
    finding: Mapping[str, Any],
    *,
    envelope: Mapping[str, Any],
    health_report_hash: str,
) -> dict[str, Any]:
    target_memory_id = str(finding["memory_ids"][0])
    action_material = {
        "finding_ids": [finding["finding_id"]],
        "operation": "expire",
        "target_memory_id": target_memory_id,
        "health_report_hash": health_report_hash,
        "preconditions": {
            "memory_state_hash": envelope["state_leaf_hash"],
            "status": "active",
            "updated_at": envelope["updated_at"],
            "expires_at": envelope["expires_at"],
            "latest_receipt_hash": envelope["latest_receipt_hash"],
            "latest_receipt_record_hash": envelope["latest_receipt_record_hash"],
        },
        "expected_transition": {"from": "active", "to": "expired"},
        "cascade": False,
        "row_deleted": False,
        "requires_explicit_apply": True,
        "semantic_truth_claimed": False,
    }
    action_hash = _digest(action_material)
    return {
        "action_id": f"maint_{action_hash.split(':', 1)[1][:24]}",
        "action_hash": action_hash,
        **action_material,
    }


def _review_item(
    finding: Mapping[str, Any],
    *,
    reason_override: str | None = None,
    guidance_override: str | None = None,
) -> dict[str, Any]:
    reason = reason_override or str(finding["reason"])
    material = {
        "finding_id": finding["finding_id"],
        "category": finding["category"],
        "reason": reason,
        "memory_ids": list(finding["memory_ids"]),
        "disposition": "review_required",
        "operator_guidance": guidance_override or _review_guidance(reason),
        "semantic_truth_claimed": False,
    }
    review_hash = _digest(material)
    return {"review_id": f"review_{review_hash.split(':', 1)[1][:24]}", **material}


def _review_guidance(reason: str) -> str:
    guidance = {
        "active_memory_has_active_child_candidate": "Review lineage before changing either active record.",
        "active_lexical_subject_relation_has_distinct_values": "Keep conflicting claims withheld until an operator resolves them.",
        "same_content_hash_type_and_scope": "Choose a canonical memory explicitly before tombstoning a duplicate.",
        "memory_has_no_write_receipt": "Do not synthesize missing provenance; review the memory source.",
        "memory_write_receipt_missing_provenance_fields": "Review or replace the source evidence before trusting this memory.",
        "active_memory_has_explicit_high_risk_evidence": "High-risk use is not evidence that the memory is false; review it explicitly.",
    }
    return guidance.get(reason, "Review this finding before changing memory state.")


def _maintenance_result(
    store: MemoryStore,
    plan: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    actor_id: str,
    receipt: Mapping[str, Any],
    status: str,
    state_before: Mapping[str, Any],
    applied_count: int,
) -> dict[str, Any]:
    receipts = store.memory_write_receipts(
        str(action["target_memory_id"]),
        initialize=False,
    )
    receipt_index = next(index for index, item in enumerate(receipts) if item["receipt_id"] == receipt["receipt_id"])
    prior = receipts[receipt_index - 1] if receipt_index > 0 else None
    receipt_verification = store.verify_memory_write_receipt(
        dict(receipt),
        prior_receipt=prior,
        allow_intervening_prior_merkle_root=True,
    )
    if not receipt_verification["ok"]:
        raise ValueError(f"maintenance receipt verification failed: {receipt['receipt_id']}")
    state_after = _database_state(store.conn)
    state_after.pop("memory_envelopes_by_id")
    transition = {
        "memory_id": action["target_memory_id"],
        "operation": action["operation"],
        "old_status": action["expected_transition"]["from"],
        "new_status": action["expected_transition"]["to"],
        "receipt_id": receipt["receipt_id"],
        "receipt_hash": receipt["receipt_hash"],
        "event_hash": receipt["event_hash"],
        "merkle_root": receipt["merkle_root"],
        "receipt_verified": True,
    }
    result = {
        "schema": MAINTENANCE_RESULT_SCHEMA,
        "ok": True,
        "status": status,
        "db_path": str(store.db_path.resolve()),
        "plan_id": plan["plan_id"],
        "plan_hash": plan["plan_hash"],
        "selected_action_id": action["action_id"],
        "actor_id": actor_id,
        "operator_identity_authenticated": False,
        "applied_count": applied_count,
        "verified_receipt_count": 1,
        "transitions": [transition],
        "state_before": {
            key: state_before.get(key)
            for key in (
                "event_count",
                "head_event_hash",
                "merkle_root",
                "memory_count",
                "memory_state_root",
                "state_hash",
            )
        },
        "state_after": state_after,
        "replan_required": True,
        "semantic_truth_claimed": False,
    }
    result_material = dict(result)
    result_digest = _digest(result_material)
    result["result_id"] = _maintenance_result_id(result_digest)
    result["result_hash"] = result_digest
    return result


def _existing_maintenance_receipt(
    plan: Mapping[str, Any],
    action: Mapping[str, Any],
    receipts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for receipt in reversed(receipts):
        statement = receipt.get("treeship_statement")
        statement_object = statement.get("object") if isinstance(statement, dict) else None
        maintenance = statement_object.get("maintenance") if isinstance(statement_object, dict) else None
        if isinstance(maintenance, dict) and maintenance.get("action_id") == action["action_id"]:
            if statement_object.get("mutation") != "expire" or statement_object.get("status") != "expired":
                raise ValueError("maintenance action receipt has an unexpected transition")
            if maintenance.get("plan_id") != plan["plan_id"]:
                raise ValueError("maintenance action receipt plan id mismatch")
            if maintenance.get("plan_hash") != plan["plan_hash"]:
                raise ValueError("maintenance action receipt plan hash mismatch")
            return receipt
    return None


def _selected_action(plan: Mapping[str, Any], action_id: str) -> dict[str, Any]:
    matches = [
        dict(action)
        for action in plan.get("selectable_actions", [])
        if isinstance(action, Mapping) and action.get("action_id") == action_id
    ]
    if len(matches) != 1:
        raise ValueError(f"maintenance action is not selectable: {action_id}")
    return matches[0]


def _validate_expiry_action(plan: Mapping[str, Any], action: Mapping[str, Any]) -> None:
    canonical = json.loads(stable_json(action))
    action_id = canonical.pop("action_id", None)
    action_hash = canonical.pop("action_hash", None)
    computed = _digest(canonical)
    if action_hash != computed:
        raise ValueError("maintenance action hash mismatch")
    if action_id != f"maint_{computed.split(':', 1)[1][:24]}":
        raise ValueError("maintenance action id mismatch")

    target_memory_id = action.get("target_memory_id")
    finding_ids = action.get("finding_ids")
    preconditions = action.get("preconditions")
    if (
        action.get("operation") != "expire"
        or action.get("expected_transition") != {"from": "active", "to": "expired"}
        or action.get("cascade") is not False
        or action.get("row_deleted") is not False
        or action.get("requires_explicit_apply") is not True
        or action.get("semantic_truth_claimed") is not False
        or not isinstance(target_memory_id, str)
        or not target_memory_id
        or not isinstance(finding_ids, list)
        or len(finding_ids) != 1
        or not isinstance(preconditions, dict)
        or preconditions.get("status") != "active"
        or not isinstance(preconditions.get("expires_at"), str)
    ):
        raise ValueError("unsupported maintenance action contract")
    source = plan.get("source")
    if not isinstance(source, dict) or action.get("health_report_hash") != source.get("health_report_hash"):
        raise ValueError("maintenance action health report mismatch")
    matching_findings = [
        finding
        for finding in plan.get("findings", [])
        if isinstance(finding, dict) and finding.get("finding_id") == finding_ids[0]
    ]
    if len(matching_findings) != 1:
        raise ValueError("maintenance action finding mismatch")
    finding = matching_findings[0]
    if (
        finding.get("category") != "stale_or_expired"
        or finding.get("reason") != "active_memory_expired"
        or finding.get("memory_ids") != [target_memory_id]
    ):
        raise ValueError("maintenance action is not backed by an explicit expiry finding")


def _finalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    material = dict(plan)
    digest = _digest(material)
    plan["plan_id"] = f"mplan_{digest.split(':', 1)[1][:24]}"
    plan["plan_hash"] = digest
    return plan


def _validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise ValueError("maintenance plan must be a JSON object")
    canonical = json.loads(stable_json(plan))
    if canonical.get("schema") != MAINTENANCE_PLAN_SCHEMA:
        raise ValueError("unsupported maintenance plan schema")
    plan_id = canonical.pop("plan_id", None)
    plan_hash = canonical.pop("plan_hash", None)
    computed = _digest(canonical)
    if plan_hash != computed:
        raise ValueError("maintenance plan hash mismatch")
    if plan_id != f"mplan_{computed.split(':', 1)[1][:24]}":
        raise ValueError("maintenance plan id mismatch")
    canonical["plan_id"] = plan_id
    canonical["plan_hash"] = plan_hash
    return canonical


def _validate_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("maintenance result must be a JSON object")
    canonical = json.loads(stable_json(result))
    if canonical.get("schema") != MAINTENANCE_RESULT_SCHEMA:
        raise ValueError("unsupported maintenance result schema")
    result_id = canonical.pop("result_id", None)
    result_hash = canonical.pop("result_hash", None)
    computed = _digest(canonical)
    if result_hash != computed:
        raise ValueError("maintenance result hash mismatch")
    transitions = canonical.get("transitions")
    if not isinstance(transitions, list) or len(transitions) != 1 or not isinstance(transitions[0], dict):
        raise ValueError("maintenance result must contain exactly one transition")
    expected_id = _maintenance_result_id(computed)
    if result_id != expected_id:
        raise ValueError("maintenance result id mismatch")
    canonical["result_id"] = result_id
    canonical["result_hash"] = result_hash
    return canonical


def _summary_counts(findings: int, selectable: int, review: int) -> dict[str, int]:
    return {
        "finding_count": findings,
        "selectable_action_count": selectable,
        "review_item_count": review,
    }


def _plan_limitations() -> list[str]:
    return [
        "The plan evaluates persisted metadata and deterministic lexical signals, not semantic truth.",
        "Only an explicit expires_at boundary can produce an executable v1 action.",
        "Operator identity is recorded but not cryptographically authenticated by this local CLI flow.",
        "Contradictions, duplicates, provenance gaps, lineage ambiguity, and high-risk use remain review-only.",
    ]


def _digest(value: Any) -> str:
    return f"{HASH_ALG}:{sha256_text(stable_json(value))}"


def _maintenance_result_id(result_hash: str) -> str:
    return f"mrun_{result_hash.split(':', 1)[1][:24]}"
