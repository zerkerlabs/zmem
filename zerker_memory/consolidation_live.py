from __future__ import annotations

import json
import math
import os
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .paths import expand_user_path
from .store import EVENT_SCHEMA, HASH_ALG, MemoryStore, merkle_root, now_iso, sha256_text, stable_json


LIVE_CONSOLIDATION_PREVIEW_SCHEMA = "zerker.live_consolidation_preview.v1"
SOURCE_TYPES = ("episodic", "semantic")
AUTHORITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "policy": 4}


def build_live_consolidation_preview(
    db_path: Path,
    *,
    scope: str,
    min_source_children: int = 3,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    path = expand_user_path(db_path)
    timestamp = evaluated_at or now_iso()
    report = _empty_report(
        path,
        scope=scope,
        min_source_children=min_source_children,
        evaluated_at=timestamp,
    )
    if not isinstance(scope, str) or not scope.strip():
        return _failed_report(report, code="invalid_scope", message="scope must be a non-empty string")
    if not isinstance(min_source_children, int) or min_source_children < 2:
        return _failed_report(
            report,
            code="invalid_min_source_children",
            message="min_source_children must be at least 2",
        )
    if not path.is_file():
        return _failed_report(
            report,
            code="database_not_found",
            message=f"memory database not found: {path}",
        )

    try:
        store = MemoryStore.open_read_only(path)
    except (OSError, sqlite3.Error, ValueError) as exc:
        return _failed_report(report, code="database_open_failed", message=str(exc))

    try:
        store.conn.execute("BEGIN")
        missing_tables = _missing_tables(store)
        if missing_tables:
            return _failed_report(
                report,
                code="missing_tables",
                message=f"memory database is missing required tables: {', '.join(missing_tables)}",
                evidence={"missing_tables": missing_tables},
            )
        event_state = _verified_event_state(store)
        rows = store.conn.execute(
            """
            SELECT id, type, content, scope, source_kind, trust, authority, status,
                   created_at, updated_at, content_hash
            FROM memories
            WHERE scope = ?
            ORDER BY created_at ASC, id ASC
            """,
            (scope,),
        ).fetchall()

        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        omissions: list[dict[str, Any]] = []
        for row in rows:
            memory_id = str(row["id"])
            reasons: list[str] = []
            if row["status"] != "active":
                reasons.append("status-not-active")
            if row["type"] not in SOURCE_TYPES:
                reasons.append("memory-type-not-consolidatable")

            receipt_row_count = int(
                store.conn.execute(
                    "SELECT COUNT(*) FROM memory_write_receipts WHERE memory_id = ?",
                    (memory_id,),
                ).fetchone()[0]
            )
            try:
                receipts = store.memory_write_receipts(memory_id, initialize=False)
                verification = (
                    store.verify_memory_write_receipt_chain(receipts, initialize=False)
                    if receipts
                    else {"ok": False, "error": "write receipt chain is empty"}
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                receipts = []
                verification = {"ok": False, "error": str(exc)}
            if not receipts and receipt_row_count == 0:
                reasons.append("missing-write-receipt")
            elif not verification["ok"]:
                reasons.append("unverified-write-receipt-chain")

            try:
                trust = float(row["trust"])
            except (OverflowError, TypeError, ValueError):
                trust = 0.0
                reasons.append("invalid-trust-value")
            else:
                if not math.isfinite(trust) or not 0.0 <= trust <= 1.0:
                    reasons.append("invalid-trust-value")
            if row["authority"] not in AUTHORITY_RANK:
                reasons.append("invalid-authority-value")
            if not _valid_timestamp(row["created_at"]):
                reasons.append("invalid-created-at")
            if not _valid_timestamp(row["updated_at"]):
                reasons.append("invalid-updated-at")

            try:
                row_receipt_mismatch_fields = (
                    _row_receipt_mismatch_fields(row, receipts)
                    if receipts and verification["ok"]
                    else []
                )
            except (KeyError, TypeError, ValueError) as exc:
                row_receipt_mismatch_fields = []
                reasons.append("malformed-write-receipt-structure")
                verification = {"ok": False, "error": str(exc)}
            if row_receipt_mismatch_fields:
                reasons.append("memory-row-receipt-divergence")

            initial_receipt = receipts[0] if receipts else None
            latest_receipt = receipts[-1] if receipts else None
            session_id = initial_receipt.get("session_id") if initial_receipt is not None else None
            origin_actor_uri = initial_receipt.get("actor_uri") if initial_receipt is not None else None
            origin_environment_hash = (
                initial_receipt.get("environment_hash") if initial_receipt is not None else None
            )
            if not isinstance(session_id, str) or not session_id:
                reasons.append("missing-session-provenance")
            if not isinstance(origin_actor_uri, str) or not origin_actor_uri:
                reasons.append("missing-actor-provenance")
            if not isinstance(origin_environment_hash, str) or not origin_environment_hash:
                reasons.append("missing-environment-provenance")

            latest_event_row = store.conn.execute(
                "SELECT event_hash FROM events WHERE memory_id = ? ORDER BY seq DESC LIMIT 1",
                (memory_id,),
            ).fetchone()
            latest_event_hash = latest_event_row["event_hash"] if latest_event_row is not None else None
            if latest_receipt is not None and latest_receipt.get("event_hash") != latest_event_hash:
                reasons.append("latest-memory-event-unreceipted")

            if reasons:
                omissions.append(
                    {
                        "memory_id": memory_id,
                        "memory_type": row["type"],
                        "status": row["status"],
                        "reason_codes": sorted(set(reasons)),
                        "receipt_chain_error": verification.get("error"),
                        "row_receipt_mismatch_fields": row_receipt_mismatch_fields,
                    }
                )
                continue

            groups[(session_id, origin_actor_uri, origin_environment_hash)].append(
                {
                    "memory_id": memory_id,
                    "memory_type": row["type"],
                    "source_kind": row["source_kind"],
                    "trust": trust,
                    "authority": row["authority"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "content_hash": row["content_hash"],
                    "content_digest": latest_receipt["content_digest"],
                    "receipt_id": latest_receipt["receipt_id"],
                    "receipt_hash": latest_receipt["receipt_hash"],
                    "event_hash": latest_receipt["event_hash"],
                }
            )

        candidates = [
            _candidate(
                session_id,
                origin_actor_uri,
                origin_environment_hash,
                sources,
                scope=scope,
                min_source_children=min_source_children,
            )
            for (session_id, origin_actor_uri, origin_environment_hash), sources in sorted(groups.items())
        ]
        included_source_count = sum(candidate["source_count"] for candidate in candidates)
        ready_candidate_count = sum(candidate["decision"] == "ready-for-review" for candidate in candidates)
        report.update(
            {
                "ok": True,
                "event_count": event_state["event_count"],
                "event_merkle_root": event_state["event_merkle_root"],
                "source_memory_count": len(rows),
                "included_source_count": included_source_count,
                "omitted_source_count": len(omissions),
                "candidate_count": len(candidates),
                "ready_candidate_count": ready_candidate_count,
                "waiting_candidate_count": len(candidates) - ready_candidate_count,
                "candidates": candidates,
                "omissions": omissions,
                "error": None,
            }
        )
        return _finalize_report(report)
    except (KeyError, OSError, sqlite3.Error, TypeError, ValueError) as exc:
        return _failed_report(report, code="database_read_failed", message=str(exc))
    finally:
        store.conn.close()


def render_live_consolidation_preview_summary(
    report: Mapping[str, Any],
    *,
    artifact_path: Path | None = None,
) -> str:
    lines = ["Zerker Memory consolidation preview", ""]
    if not report.get("ok"):
        error = report.get("error") or {}
        lines.extend(
            [
                "Ready: no",
                f"Error: {error.get('message', 'preview failed')}",
                "Database writes: none",
            ]
        )
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "Ready: yes",
            f"Scope: {report['scope']}",
            f"Candidates: {report['candidate_count']} ({report['ready_candidate_count']} ready, {report['waiting_candidate_count']} waiting)",
            f"Sources: {report['included_source_count']} included, {report['omitted_source_count']} omitted",
            f"Event root: {report['event_merkle_root']}",
            "Summary writes: none",
            "Canonical memory writes: none",
        ]
    )
    if artifact_path is not None:
        lines.append(f"Artifact: {artifact_path}")
    return "\n".join(lines) + "\n"


def write_live_consolidation_preview(
    path: Path,
    report: Mapping[str, Any],
    *,
    force: bool = False,
) -> Path:
    destination = expand_user_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        raise FileExistsError(f"consolidation preview already exists: {destination}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(report), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(0o600)
        os.replace(temp_path, destination)
        destination.chmod(0o600)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return destination


def _candidate(
    session_id: str,
    origin_actor_uri: str,
    origin_environment_hash: str,
    sources: list[dict[str, Any]],
    *,
    scope: str,
    min_source_children: int,
) -> dict[str, Any]:
    ordered_sources = sorted(sources, key=lambda source: (source["created_at"], source["memory_id"]))
    source_ids = [source["memory_id"] for source in ordered_sources]
    source_digests = {source["memory_id"]: source["content_digest"] for source in ordered_sources}
    trust_ceiling = min(source["trust"] for source in ordered_sources)
    authority_ceiling = min(
        (source["authority"] for source in ordered_sources),
        key=lambda authority: AUTHORITY_RANK.get(str(authority), -1),
    )
    source_set = {
        "scope": scope,
        "session_id": session_id,
        "origin_actor_uri": origin_actor_uri,
        "origin_environment_hash": origin_environment_hash,
        "source_memory_ids": source_ids,
        "source_content_digests": source_digests,
        "source_receipt_hashes": {
            source["memory_id"]: source["receipt_hash"] for source in ordered_sources
        },
    }
    source_set_hash = sha256_text(stable_json(source_set))
    ready = len(ordered_sources) >= min_source_children
    return {
        "candidate_id": f"consolidation-candidate:{source_set_hash[:24]}",
        "scope": scope,
        "session_id": session_id,
        "origin_actor_uri": origin_actor_uri,
        "origin_environment_hash": origin_environment_hash,
        "summary_level": "session",
        "source_level": "turn",
        "source_memory_ids": source_ids,
        "source_count": len(ordered_sources),
        "source_content_digests": source_digests,
        "source_receipt_ids": {
            source["memory_id"]: source["receipt_id"] for source in ordered_sources
        },
        "source_receipt_hashes": source_set["source_receipt_hashes"],
        "source_set_hash": source_set_hash,
        "trust_ceiling": trust_ceiling,
        "authority_ceiling": authority_ceiling,
        "decision": "ready-for-review" if ready else "waiting",
        "decision_reason": "minimum-source-count-met" if ready else "insufficient-source-count",
        "min_source_children": min_source_children,
        "output_contract": {
            "non_blocking": True,
            "reversible": True,
            "canonical_memory_write_allowed": False,
            "required_initial_status": "quarantined",
            "required_initial_trust": 0.0,
            "required_initial_authority": "none",
            "trust_ceiling": trust_ceiling,
            "authority_ceiling": authority_ceiling,
        },
    }


def _row_receipt_mismatch_fields(row: Mapping[str, Any], receipts: list[dict[str, Any]]) -> list[str]:
    initial_object = receipts[0]["treeship_statement"]["object"]
    latest_object = receipts[-1]["treeship_statement"]["object"]
    mismatches: list[str] = []
    current_content_hash = sha256_text(str(row["content"]))
    if row["content_hash"] != current_content_hash:
        mismatches.append("content_hash")
    if latest_object.get("content_digest") != f"sha256:{current_content_hash}":
        mismatches.append("content_digest")
    for row_field, receipt_field in (
        ("type", "memory_type"),
        ("scope", "scope"),
        ("source_kind", "source_kind"),
    ):
        if row[row_field] != initial_object.get(receipt_field):
            mismatches.append(row_field)
    expected_trust = initial_object.get("trust")
    for receipt in receipts[1:]:
        receipt_object = receipt["treeship_statement"]["object"]
        if "trust" in receipt_object:
            expected_trust = receipt_object["trust"]
        elif receipt_object.get("mutation") == "promote" and isinstance(expected_trust, (int, float)):
            expected_trust = max(float(expected_trust), 0.9)
    if row["trust"] != expected_trust:
        mismatches.append("trust")
    expected_status = latest_object.get("status", initial_object.get("status"))
    expected_authority = latest_object.get("authority", initial_object.get("authority"))
    if row["status"] != expected_status:
        mismatches.append("status")
    if row["authority"] != expected_authority:
        mismatches.append("authority")
    return sorted(set(mismatches))


def _verified_event_state(store: MemoryStore) -> dict[str, Any]:
    rows = store.conn.execute(
        """
        SELECT seq, event_type, memory_id, action_id, actor_id, payload_json,
               payload_hash, prev_event_hash, event_hash, merkle_root, created_at
        FROM events
        ORDER BY seq ASC
        """
    ).fetchall()
    prior_event_hash = sha256_text("genesis")
    event_hashes: list[str] = []
    for row in rows:
        payload_json = str(row["payload_json"])
        if sha256_text(payload_json) != row["payload_hash"]:
            raise ValueError(f"event payload hash mismatch at seq {row['seq']}")
        if row["prev_event_hash"] != prior_event_hash:
            raise ValueError(f"event predecessor mismatch at seq {row['seq']}")
        canonical_event = {
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
        computed_event_hash = sha256_text(stable_json(canonical_event))
        if computed_event_hash != row["event_hash"]:
            raise ValueError(f"event hash mismatch at seq {row['seq']}")
        event_hashes.append(computed_event_hash)
        computed_root = merkle_root(event_hashes)
        if computed_root != row["merkle_root"]:
            raise ValueError(f"event Merkle root mismatch at seq {row['seq']}")
        prior_event_hash = computed_event_hash
    return {
        "event_count": len(rows),
        "event_merkle_root": merkle_root(event_hashes),
    }


def _missing_tables(store: MemoryStore) -> list[str]:
    required = {"events", "memories", "memory_write_receipts"}
    rows = store.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    present = {str(row["name"]) for row in rows}
    return sorted(required - present)


def _empty_report(
    path: Path,
    *,
    scope: str,
    min_source_children: int,
    evaluated_at: str,
) -> dict[str, Any]:
    return {
        "schema": LIVE_CONSOLIDATION_PREVIEW_SCHEMA,
        "ok": False,
        "preview_id": None,
        "preview_hash": None,
        "database": str(path),
        "evaluated_at": evaluated_at,
        "scope": scope,
        "source_types": list(SOURCE_TYPES),
        "min_source_children": min_source_children,
        "read_only": True,
        "writes_performed": False,
        "summary_materialized": False,
        "canonical_memory_written": False,
        "semantic_truth_guaranteed": False,
        "event_count": 0,
        "event_merkle_root": None,
        "source_memory_count": 0,
        "included_source_count": 0,
        "omitted_source_count": 0,
        "candidate_count": 0,
        "ready_candidate_count": 0,
        "waiting_candidate_count": 0,
        "candidates": [],
        "omissions": [],
        "limitations": [
            "The preview identifies structurally eligible source sets; it does not judge semantic truth.",
            "No summary is generated, persisted, admitted, or injected.",
            "A future summary must remain reversible and cannot exceed the weakest source trust or authority.",
        ],
        "error": None,
    }


def _failed_report(
    report: dict[str, Any],
    *,
    code: str,
    message: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    failed = dict(report)
    failed["error"] = {
        "code": code,
        "message": message,
        "evidence": dict(evidence or {}),
    }
    return failed


def _finalize_report(report: dict[str, Any]) -> dict[str, Any]:
    payload = dict(report)
    payload["database"] = None
    payload["evaluated_at"] = None
    payload["preview_id"] = None
    payload["preview_hash"] = None
    preview_hash = sha256_text(stable_json(payload))
    report["preview_hash"] = preview_hash
    report["preview_id"] = f"consolidation-preview:{preview_hash[:24]}"
    return report


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None
