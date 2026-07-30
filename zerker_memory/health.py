from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .paths import expand_user_path
from .store import MemoryRecord, _resolve_current_conflicts, now_iso, sha256_text


MEMORY_HEALTH_REPORT_SCHEMA = "zerker.memory_health_report.v1"
CATEGORY_ORDER = (
    "stale_or_expired",
    "contradictory_or_conflicting",
    "exact_duplicate",
    "weak_or_missing_provenance",
    "high_risk_active",
)
CATEGORY_LABELS = {
    "stale_or_expired": "Stale / expired",
    "contradictory_or_conflicting": "Contradictory / conflicting",
    "exact_duplicate": "Exact duplicate",
    "weak_or_missing_provenance": "Weak / missing provenance",
    "high_risk_active": "High-risk active",
}
LIVE_STATUSES = frozenset({"active", "proposed", "quarantined"})
DIRECT_SOURCE_KINDS = frozenset({"human", "system"})
PROVENANCE_FIELDS = (
    "actor_uri",
    "session_id",
    "content_digest",
    "environment_hash",
    "event_hash",
    "receipt_hash",
)


def build_memory_health_report(
    db_path: Path,
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    path = expand_user_path(db_path)
    timestamp = evaluated_at or now_iso()
    report = _empty_report(path, evaluated_at=timestamp)
    if not path.is_file():
        return _failed_report(
            report,
            code="database_not_found",
            message=f"memory database not found: {path}",
        )

    try:
        connection = _open_read_only(path)
    except sqlite3.Error as exc:
        return _failed_report(report, code="database_open_failed", message=str(exc))

    try:
        missing_tables = _missing_tables(connection)
        if missing_tables:
            return _failed_report(
                report,
                code="missing_tables",
                message=f"memory database is missing required tables: {', '.join(missing_tables)}",
                evidence={"missing_tables": missing_tables},
            )

        memories = _load_memories(connection)
        write_receipts = _load_write_receipts(connection)
        high_risk_actions = _load_high_risk_actions(connection)
    except (json.JSONDecodeError, KeyError, sqlite3.Error, TypeError, ValueError) as exc:
        return _failed_report(report, code="database_read_failed", message=str(exc))
    finally:
        connection.close()

    findings = {category: [] for category in CATEGORY_ORDER}
    findings["stale_or_expired"].extend(_stale_or_expired_findings(memories, evaluated_at=timestamp))
    findings["contradictory_or_conflicting"].extend(_conflict_findings(memories))
    findings["exact_duplicate"].extend(_duplicate_findings(memories))
    findings["weak_or_missing_provenance"].extend(_provenance_findings(memories, write_receipts))
    findings["high_risk_active"].extend(_high_risk_findings(memories, high_risk_actions))
    for category in CATEGORY_ORDER:
        findings[category].sort(key=_finding_sort_key)

    category_counts = {category: len(findings[category]) for category in CATEGORY_ORDER}
    finding_count = sum(category_counts.values())
    report.update(
        {
            "ok": True,
            "healthy": finding_count == 0,
            "memory_count": len(memories),
            "active_memory_count": sum(memory.status == "active" for memory in memories),
            "finding_count": finding_count,
            "category_counts": category_counts,
            "findings": findings,
            "error": None,
        }
    )
    return report


def render_memory_health_summary(report: dict[str, Any]) -> str:
    lines = [
        "Zerker Memory health audit",
        f"Database: {report.get('db_path')}",
        f"Audit: {'complete' if report.get('ok') else 'failed'}",
        f"Read-only: {'yes' if report.get('read_only') else 'no'}",
    ]
    if report.get("ok"):
        lines.extend(
            [
                f"Healthy: {'yes' if report.get('healthy') else 'no'}",
                f"Memories inspected: {report.get('memory_count', 0)}",
                f"Findings: {report.get('finding_count', 0)}",
            ]
        )
        counts = report.get("category_counts", {})
        for category in CATEGORY_ORDER:
            lines.append(f"- {CATEGORY_LABELS[category]}: {counts.get(category, 0)}")
    else:
        error = report.get("error") or {}
        lines.append(f"Error: {error.get('message', 'unknown audit error')}")
    lines.append("Semantic truth: not evaluated")
    return "\n".join(lines) + "\n"


def _empty_report(path: Path, *, evaluated_at: str) -> dict[str, Any]:
    return {
        "schema": MEMORY_HEALTH_REPORT_SCHEMA,
        "ok": False,
        "healthy": False,
        "read_only": True,
        "db_path": str(path),
        "evaluated_at": evaluated_at,
        "memory_count": 0,
        "active_memory_count": 0,
        "finding_count": 0,
        "category_counts": {category: 0 for category in CATEGORY_ORDER},
        "findings": {category: [] for category in CATEGORY_ORDER},
        "semantic_truth_claimed": False,
        "limitations": [
            "Findings describe persisted metadata and deterministic lexical signals only.",
            "The audit does not establish whether memory content is factually or semantically true.",
            "The audit reads one SQLite snapshot and may not include writes committed after that snapshot begins.",
        ],
        "error": None,
    }


def _failed_report(
    report: dict[str, Any],
    *,
    code: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report["error"] = {
        "code": code,
        "message": message,
        "evidence": evidence or {},
    }
    return report


def _open_read_only(path: Path) -> sqlite3.Connection:
    wal_path = Path(f"{path}-wal")
    try:
        has_wal_state = wal_path.stat().st_size > 0
    except OSError:
        has_wal_state = False
    immutable = "" if has_wal_state else "&immutable=1"
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro{immutable}",
        uri=True,
        timeout=5.0,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _missing_tables(connection: sqlite3.Connection) -> list[str]:
    required = {"memories", "memory_write_receipts", "receipts"}
    available = {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    }
    return sorted(required - available)


def _load_memories(connection: sqlite3.Connection) -> list[MemoryRecord]:
    rows = connection.execute(
        """
        SELECT id, type, content, scope, source_kind, trust, authority, status,
               parents_json, labels_json, created_at, updated_at, expires_at, content_hash
        FROM memories
        ORDER BY id ASC
        """
    ).fetchall()
    return [MemoryRecord.from_row(row) for row in rows]


def _load_write_receipts(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT receipt_id, memory_id, actor_uri, session_id, source_uri, content_digest,
               environment_hash, event_hash, receipt_hash, created_at
        FROM memory_write_receipts
        ORDER BY memory_id ASC, created_at ASC, receipt_id ASC
        """
    ).fetchall()
    receipts: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        receipts.setdefault(str(row["memory_id"]), []).append(dict(row))
    return receipts


def _load_high_risk_actions(connection: sqlite3.Connection) -> dict[str, list[str]]:
    rows = connection.execute(
        """
        SELECT action_id, injected_ids_json
        FROM receipts
        WHERE risk = 'high'
        ORDER BY action_id ASC
        """
    ).fetchall()
    actions_by_memory_id: dict[str, list[str]] = {}
    for row in rows:
        injected_ids = json.loads(row["injected_ids_json"])
        if not isinstance(injected_ids, list):
            raise ValueError(f"receipt {row['action_id']} has non-list injected_ids_json")
        for memory_id in sorted({str(value) for value in injected_ids if str(value)}):
            actions_by_memory_id.setdefault(memory_id, []).append(str(row["action_id"]))
    return actions_by_memory_id


def _finding(
    category: str,
    reason: str,
    memory_ids: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "category": category,
        "memory_ids": sorted(set(memory_ids)),
        "reason": reason,
        "evidence": evidence,
        "semantic_truth_claimed": False,
    }


def _finding_sort_key(finding: dict[str, Any]) -> tuple[str, tuple[str, ...], str]:
    return (
        str(finding["reason"]),
        tuple(str(memory_id) for memory_id in finding["memory_ids"]),
        json.dumps(finding["evidence"], sort_keys=True, separators=(",", ":")),
    )


def _stale_or_expired_findings(
    memories: list[MemoryRecord],
    *,
    evaluated_at: str,
) -> list[dict[str, Any]]:
    findings = []
    active_by_id = {memory.id: memory for memory in memories if memory.status == "active"}
    for memory in active_by_id.values():
        if memory.expires_at and memory.expires_at <= evaluated_at:
            findings.append(
                _finding(
                    "stale_or_expired",
                    "active_memory_expired",
                    [memory.id],
                    {
                        "status": memory.status,
                        "expires_at": memory.expires_at,
                        "evaluated_at": evaluated_at,
                    },
                )
            )

    active_children_by_parent: dict[str, list[str]] = {}
    for child in active_by_id.values():
        for parent_id in child.parents:
            if parent_id in active_by_id:
                active_children_by_parent.setdefault(parent_id, []).append(child.id)
    for parent_id, child_ids in active_children_by_parent.items():
        ordered_child_ids = sorted(set(child_ids))
        findings.append(
            _finding(
                "stale_or_expired",
                "active_memory_has_active_child_candidate",
                [parent_id, *ordered_child_ids],
                {
                    "parent_memory_id": parent_id,
                    "active_child_ids": ordered_child_ids,
                    "relationship": "persisted_parent_lineage",
                },
            )
        )
    return findings


def _conflict_findings(memories: list[MemoryRecord]) -> list[dict[str, Any]]:
    findings = []
    active_by_scope: dict[str, list[MemoryRecord]] = {}
    for memory in memories:
        if memory.status == "active":
            active_by_scope.setdefault(memory.scope, []).append(memory)
    for scope in sorted(active_by_scope):
        candidates = sorted(active_by_scope[scope], key=lambda memory: memory.id)
        candidate_by_id = {memory.id: memory for memory in candidates}
        conflicts = _resolve_current_conflicts(
            candidate_by_id=candidate_by_id,
            current_ids=[memory.id for memory in candidates],
            candidate_ids_in_rank_order=[memory.id for memory in candidates],
        )
        for conflict in conflicts:
            memory_ids = sorted(str(value) for value in conflict.get("involved_candidate_ids", []))
            value_hash_by_memory_id = {
                memory_id: sha256_text(str(value))
                for memory_id, value in sorted((conflict.get("value_by_id") or {}).items())
            }
            findings.append(
                _finding(
                    "contradictory_or_conflicting",
                    "active_lexical_subject_relation_has_distinct_values",
                    memory_ids,
                    {
                        "scope": scope,
                        "detector": "zerker.lexical_current_conflict.v1",
                        "subject_key": conflict.get("subject_key"),
                        "relation": conflict.get("relation"),
                        "value_hash_by_memory_id": value_hash_by_memory_id,
                        "resolution_outcome": conflict.get("resolution_outcome"),
                        "chosen_current_id": conflict.get("chosen_current_id"),
                        "dropped_current_ids": sorted(
                            str(value) for value in conflict.get("dropped_current_ids", [])
                        ),
                        "abstained_current_ids": sorted(
                            str(value) for value in conflict.get("abstained_current_ids", [])
                        ),
                    },
                )
            )
    return findings


def _duplicate_findings(memories: list[MemoryRecord]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[MemoryRecord]] = {}
    for memory in memories:
        if memory.status not in LIVE_STATUSES:
            continue
        key = (memory.content, memory.type, memory.scope)
        groups.setdefault(key, []).append(memory)

    findings = []
    for (content, memory_type, scope), group in sorted(groups.items()):
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda memory: memory.id)
        findings.append(
            _finding(
                "exact_duplicate",
                "same_content_hash_type_and_scope",
                [memory.id for memory in ordered],
                {
                    "computed_content_hash": sha256_text(content),
                    "memory_type": memory_type,
                    "scope": scope,
                    "persisted_content_hash_by_memory_id": {
                        memory.id: memory.content_hash for memory in ordered
                    },
                    "status_by_memory_id": {
                        memory.id: memory.status for memory in ordered
                    },
                },
            )
        )
    return findings


def _provenance_findings(
    memories: list[MemoryRecord],
    receipts_by_memory_id: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    findings = []
    for memory in memories:
        receipts = receipts_by_memory_id.get(memory.id, [])
        if not receipts:
            findings.append(
                _finding(
                    "weak_or_missing_provenance",
                    "memory_has_no_write_receipt",
                    [memory.id],
                    {
                        "source_kind": memory.source_kind,
                        "write_receipt_count": 0,
                    },
                )
            )
            continue

        first_receipt = receipts[0]
        missing_fields = [
            field
            for field in PROVENANCE_FIELDS
            if not isinstance(first_receipt.get(field), str) or not str(first_receipt[field]).strip()
        ]
        source_uri_required = memory.source_kind not in DIRECT_SOURCE_KINDS
        if source_uri_required and (
            not isinstance(first_receipt.get("source_uri"), str)
            or not str(first_receipt["source_uri"]).strip()
        ):
            missing_fields.append("source_uri")
        if missing_fields:
            findings.append(
                _finding(
                    "weak_or_missing_provenance",
                    "memory_write_receipt_missing_provenance_fields",
                    [memory.id],
                    {
                        "source_kind": memory.source_kind,
                        "receipt_id": first_receipt["receipt_id"],
                        "write_receipt_count": len(receipts),
                        "missing_fields": sorted(set(missing_fields)),
                        "source_uri_required_for_source_kind": source_uri_required,
                    },
                )
            )
    return findings


def _high_risk_findings(
    memories: list[MemoryRecord],
    high_risk_actions_by_memory_id: dict[str, list[str]],
) -> list[dict[str, Any]]:
    findings = []
    for memory in memories:
        if memory.status != "active":
            continue
        explicit_risk_labels = sorted(
            label for label in memory.labels if label.strip().lower() == "risk:high"
        )
        action_ids = sorted(set(high_risk_actions_by_memory_id.get(memory.id, [])))
        if not explicit_risk_labels and not action_ids:
            continue
        findings.append(
            _finding(
                "high_risk_active",
                "active_memory_has_explicit_high_risk_evidence",
                [memory.id],
                {
                    "status": memory.status,
                    "risk_labels": explicit_risk_labels,
                    "high_risk_action_ids": action_ids,
                    "evidence_sources": [
                        source
                        for source, present in (
                            ("memory_label", bool(explicit_risk_labels)),
                            ("injection_receipt", bool(action_ids)),
                        )
                        if present
                    ],
                },
            )
        )
    return findings
