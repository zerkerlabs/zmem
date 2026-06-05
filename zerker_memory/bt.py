from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Mapping

from .store import MemoryStore, default_db_path, sha256_text, stable_json


BT_EVENT_SCHEMA = "zerker.bt_event.v1"
BT_EXPLANATION_SCHEMA = "zerker.bt_explanation.v1"
PY_TREES_ADAPTER_SCHEMA = "zerker.bt_adapter.py_trees.v1"
BTPG_ADAPTER_SCHEMA = "zerker.bt_adapter.btpg.v1"
BT_GROOT2_EXPORT_SCHEMA = "zerker.bt_export.groot2.v1"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass(frozen=True)
class BtEvent:
    event_id: str
    trace_id: str
    timestamp: str
    event_type: str
    node_id: str
    node_status: str
    executor_id: str
    tree_id: str | None
    node_name: str | None
    node_type: str | None
    confidence: float
    ttl_ms: int | None
    scope: str
    affected_symbols: list[str]
    causal_parent_ids: list[str]
    delivery_semantics: str
    payload: dict[str, Any]
    event_hash: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BtEvent":
        event_id = value.get("event_id") or "bte_" + uuid.uuid4().hex[:16]
        trace_id = required_str(value, "trace_id")
        timestamp = value.get("timestamp") or now_iso()
        event_type = required_str(value, "event_type")
        node_id = required_str(value, "node_id")
        node_status = value.get("node_status", "UNKNOWN")
        executor_id = value.get("executor_id", "local")
        affected_symbols = [str(item) for item in value.get("affected_symbols", [])]
        causal_parent_ids = [str(item) for item in value.get("causal_parent_ids", [])]
        payload = dict(value.get("payload", {}))
        material = {
            "event_schema": BT_EVENT_SCHEMA,
            "event_id": event_id,
            "trace_id": trace_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "node_id": node_id,
            "node_status": node_status,
            "executor_id": executor_id,
            "tree_id": value.get("tree_id"),
            "node_name": value.get("node_name"),
            "node_type": value.get("node_type"),
            "confidence": float(value.get("confidence", 1.0)),
            "ttl_ms": value.get("ttl_ms"),
            "scope": value.get("scope", "project"),
            "affected_symbols": affected_symbols,
            "causal_parent_ids": causal_parent_ids,
            "delivery_semantics": value.get("delivery_semantics", "at-least-once"),
            "payload": payload,
        }
        return cls(
            event_id=event_id,
            trace_id=trace_id,
            timestamp=timestamp,
            event_type=event_type,
            node_id=node_id,
            node_status=node_status,
            executor_id=executor_id,
            tree_id=value.get("tree_id"),
            node_name=value.get("node_name"),
            node_type=value.get("node_type"),
            confidence=float(value.get("confidence", 1.0)),
            ttl_ms=value.get("ttl_ms"),
            scope=value.get("scope", "project"),
            affected_symbols=affected_symbols,
            causal_parent_ids=causal_parent_ids,
            delivery_semantics=value.get("delivery_semantics", "at-least-once"),
            payload=payload,
            event_hash=sha256_text(stable_json(material)),
        )

    @classmethod
    def from_row(cls, row: Any) -> "BtEvent":
        return cls(
            event_id=row["event_id"],
            trace_id=row["trace_id"],
            timestamp=row["timestamp"],
            event_type=row["event_type"],
            node_id=row["node_id"],
            node_status=row["node_status"],
            executor_id=row["executor_id"],
            tree_id=row["tree_id"],
            node_name=row["node_name"],
            node_type=row["node_type"],
            confidence=row["confidence"],
            ttl_ms=row["ttl_ms"],
            scope=row["scope"],
            affected_symbols=json.loads(row["affected_symbols_json"]),
            causal_parent_ids=json.loads(row["causal_parent_ids_json"]),
            delivery_semantics=row["delivery_semantics"],
            payload=json.loads(row["payload_json"]),
            event_hash=row["event_hash"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_schema": BT_EVENT_SCHEMA,
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "node_id": self.node_id,
            "node_status": self.node_status,
            "executor_id": self.executor_id,
            "tree_id": self.tree_id,
            "node_name": self.node_name,
            "node_type": self.node_type,
            "confidence": self.confidence,
            "ttl_ms": self.ttl_ms,
            "scope": self.scope,
            "affected_symbols": self.affected_symbols,
            "causal_parent_ids": self.causal_parent_ids,
            "delivery_semantics": self.delivery_semantics,
            "payload": self.payload,
            "event_hash": self.event_hash,
        }


class BtMemory:
    def __init__(self, store: MemoryStore):
        self.store = store
        self.store.init()
        self.init()

    def init(self) -> None:
        self.store.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bt_events (
              event_id TEXT PRIMARY KEY,
              trace_id TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              event_type TEXT NOT NULL,
              node_id TEXT NOT NULL,
              node_status TEXT NOT NULL,
              executor_id TEXT NOT NULL,
              tree_id TEXT,
              node_name TEXT,
              node_type TEXT,
              confidence REAL NOT NULL,
              ttl_ms INTEGER,
              scope TEXT NOT NULL,
              affected_symbols_json TEXT NOT NULL,
              causal_parent_ids_json TEXT NOT NULL,
              delivery_semantics TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              event_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_bt_events_trace_time ON bt_events(trace_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_bt_events_node ON bt_events(node_id);
            """
        )
        self.store.conn.commit()

    def ingest_file(self, path: Path) -> dict[str, Any]:
        events = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(BtEvent.from_dict(json.loads(stripped)))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_no}: {exc}") from exc
        return self.ingest(events, source=str(path))

    def ingest(self, events: list[BtEvent], *, source: str | None = None) -> dict[str, Any]:
        inserted = 0
        duplicate = 0
        trace_ids = sorted({event.trace_id for event in events})
        for event in events:
            cursor = self.store.conn.execute(
                """
                INSERT OR IGNORE INTO bt_events (
                  event_id, trace_id, timestamp, event_type, node_id, node_status, executor_id,
                  tree_id, node_name, node_type, confidence, ttl_ms, scope,
                  affected_symbols_json, causal_parent_ids_json, delivery_semantics, payload_json, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.trace_id,
                    event.timestamp,
                    event.event_type,
                    event.node_id,
                    event.node_status,
                    event.executor_id,
                    event.tree_id,
                    event.node_name,
                    event.node_type,
                    event.confidence,
                    event.ttl_ms,
                    event.scope,
                    stable_json(event.affected_symbols),
                    stable_json(event.causal_parent_ids),
                    event.delivery_semantics,
                    stable_json(event.payload),
                    event.event_hash,
                ),
            )
            if cursor.rowcount:
                inserted += 1
            else:
                duplicate += 1
        self.store._append_event(
            "BT_TRACE_INGESTED",
            actor_id="zerker-bt",
            payload={
                "event_schema": BT_EVENT_SCHEMA,
                "source": source,
                "trace_ids": trace_ids,
                "inserted": inserted,
                "duplicate": duplicate,
                "event_hashes": [event.event_hash for event in events],
            },
        )
        self.store.conn.commit()
        return {"ok": True, "inserted": inserted, "duplicate": duplicate, "trace_ids": trace_ids}

    def ingest_py_trees_transitions(
        self,
        trace_id: str,
        transitions: list[Mapping[str, Any]],
        *,
        executor_id: str = "local",
        tree_id: str | None = None,
        scope: str = "project",
        source: str | None = "py_trees",
    ) -> dict[str, Any]:
        events = [
            bt_event_from_py_trees_transition(
                trace_id,
                transition,
                executor_id=executor_id,
                tree_id=tree_id,
                scope=scope,
            )
            for transition in transitions
        ]
        return self.ingest(events, source=source)

    def ingest_btpg_transitions(
        self,
        trace_id: str,
        transitions: list[Mapping[str, Any]],
        *,
        executor_id: str = "local",
        tree_id: str | None = None,
        scope: str = "project",
        source: str | None = "btpg",
    ) -> dict[str, Any]:
        events = [
            bt_event_from_btpg_transition(
                trace_id,
                transition,
                executor_id=executor_id,
                tree_id=tree_id,
                scope=scope,
            )
            for transition in transitions
        ]
        return self.ingest(events, source=source)

    def traces(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.store.conn.execute(
            """
            SELECT trace_id, COUNT(*) AS event_count, MIN(timestamp) AS started_at, MAX(timestamp) AS ended_at
            FROM bt_events
            GROUP BY trace_id
            ORDER BY ended_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def events(self, trace_id: str) -> list[BtEvent]:
        rows = self.store.conn.execute(
            "SELECT * FROM bt_events WHERE trace_id = ? ORDER BY timestamp, event_id",
            (trace_id,),
        ).fetchall()
        return [BtEvent.from_row(row) for row in rows]

    def explain(self, trace_id: str, *, question: str | None = None) -> dict[str, Any]:
        events = self.events(trace_id)
        if not events:
            raise KeyError(f"BT trace not found: {trace_id}")
        fallback = find_primary_fallback(events)
        cause_map = {event.event_id: event for event in events}
        cited_events = []
        if fallback:
            cited_events.append(fallback)
            for parent_id in fallback.causal_parent_ids:
                parent = cause_map.get(parent_id)
                if parent:
                    cited_events.append(parent)
        else:
            cited_events.extend(events[-3:])
        affected_symbols = sorted({symbol for event in cited_events for symbol in event.affected_symbols})
        summary = build_summary(fallback, cited_events, question=question)
        return {
            "explanation_schema": BT_EXPLANATION_SCHEMA,
            "trace_id": trace_id,
            "question": question,
            "summary": summary,
            "primary_event_id": fallback.event_id if fallback else cited_events[-1].event_id,
            "cited_event_ids": [event.event_id for event in cited_events],
            "affected_symbols": affected_symbols,
            "event_count": len(events),
            "generated_at": now_iso(),
        }

    def export_groot2_trace(
        self,
        trace_id: str,
        *,
        out: Path | None = None,
        out_dir: Path | None = None,
    ) -> dict[str, Any]:
        events = self.events(trace_id)
        if not events:
            raise KeyError(f"BT trace not found: {trace_id}")
        export_payload = groot2_export_payload(trace_id, events)
        xml_path = out or default_groot2_xml_path(trace_id, out_dir=out_dir)
        manifest_path = default_groot2_manifest_path(xml_path)
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        xml_path.write_text(export_payload["xml"], encoding="utf-8")
        manifest_path.write_text(stable_json(export_payload["manifest"]) + "\n", encoding="utf-8")
        return {
            "ok": True,
            "trace_id": trace_id,
            "format": "groot2",
            "xml_path": str(xml_path),
            "manifest_path": str(manifest_path),
            "xml_sha256": sha256_text(export_payload["xml"]),
            "manifest_sha256": sha256_text(stable_json(export_payload["manifest"])),
            "manifest": export_payload["manifest"],
        }


def find_primary_fallback(events: list[BtEvent]) -> BtEvent | None:
    for event in reversed(events):
        lowered = event.event_type.lower()
        if "fallback" in lowered or "recovery" in lowered:
            return event
    for event in reversed(events):
        if event.node_status.upper() == "FAILURE":
            return event
    return None


def groot2_export_payload(trace_id: str, events: list[BtEvent]) -> dict[str, Any]:
    explanation = _build_export_explanation(trace_id, events)
    tree_id = _tree_identifier(trace_id, events)
    node_models = _node_models(events)
    xml_lines = [
        '<root BTCPP_format="4" main_tree_to_execute="%s">' % escape(tree_id, quote=True),
        '  <BehaviorTree ID="%s">' % escape(tree_id, quote=True),
        '    <Sequence name="%s">' % escape(trace_id, quote=True),
    ]
    for model in node_models:
        xml_lines.append(
            '      <%s ID="%s" name="%s" />'
            % (
                model["tag"],
                escape(model["id"], quote=True),
                escape(model["name"], quote=True),
            )
        )
    xml_lines.extend(
        [
            "    </Sequence>",
            "  </BehaviorTree>",
            "  <TreeNodesModel>",
        ]
    )
    for model in node_models:
        xml_lines.append(
            '    <%s ID="%s" />' % (model["tag"], escape(model["id"], quote=True))
        )
    xml_lines.extend(["  </TreeNodesModel>", "</root>"])
    manifest = {
        "schema": BT_GROOT2_EXPORT_SCHEMA,
        "trace_id": trace_id,
        "tree_id": tree_id,
        "event_count": len(events),
        "generated_at": now_iso(),
        "event_hashes": [event.event_hash for event in events],
        "explanation": explanation,
        "nodes": [
            {
                "node_id": model["id"],
                "node_name": model["name"],
                "node_type": model["node_type"],
                "tag": model["tag"],
                "last_status": model["last_status"],
                "event_types": model["event_types"],
            }
            for model in node_models
        ],
    }
    return {"xml": "\n".join(xml_lines) + "\n", "manifest": manifest}


def build_summary(fallback: BtEvent | None, cited_events: list[BtEvent], *, question: str | None) -> str:
    if fallback is None:
        last = cited_events[-1]
        return f"No fallback or failure was recorded; latest cited event was {last.event_type} on node {last.node_id}."
    parent_text = ""
    parents = [event for event in cited_events if event.event_id != fallback.event_id]
    if parents:
        parent = parents[0]
        symbols = ", ".join(parent.affected_symbols) if parent.affected_symbols else "no symbols"
        reason = _failure_reason_text(parent)
        parent_text = f" It was caused by {parent.event_type} on {parent.node_id}, affecting {symbols}{reason}."
    node = fallback.node_name or fallback.node_id
    return f"Trace {fallback.trace_id} fell back at {node} because event {fallback.event_type} produced status {fallback.node_status}.{parent_text}"


def default_groot2_xml_path(trace_id: str, *, out_dir: Path | None = None) -> Path:
    target_dir = out_dir or Path.cwd() / ".zerker" / "exports"
    safe_trace_id = trace_id.replace("/", "_").replace(" ", "_")
    return target_dir / f"{safe_trace_id}.groot2.xml"


def default_groot2_manifest_path(xml_path: Path) -> Path:
    xml_name = xml_path.name
    if xml_name.endswith(".xml"):
        stem = xml_name[:-4]
    else:
        stem = xml_name
    return xml_path.with_name(f"{stem}.manifest.json")


def _build_export_explanation(trace_id: str, events: list[BtEvent]) -> dict[str, Any]:
    fallback = find_primary_fallback(events)
    cause_map = {event.event_id: event for event in events}
    cited_events = []
    if fallback:
        cited_events.append(fallback)
        for parent_id in fallback.causal_parent_ids:
            parent = cause_map.get(parent_id)
            if parent:
                cited_events.append(parent)
    else:
        cited_events.extend(events[-3:])
    return {
        "summary": build_summary(fallback, cited_events, question=None),
        "primary_event_id": fallback.event_id if fallback else cited_events[-1].event_id,
        "cited_event_ids": [event.event_id for event in cited_events],
    }


def _tree_identifier(trace_id: str, events: list[BtEvent]) -> str:
    for event in events:
        if event.tree_id:
            return event.tree_id
    return trace_id


def _node_models(events: list[BtEvent]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.node_id in seen:
            seen[event.node_id]["last_status"] = event.node_status
            event_types = seen[event.node_id]["event_types"]
            if event.event_type not in event_types:
                event_types.append(event.event_type)
            continue
        model = {
            "id": event.node_id,
            "name": event.node_name or event.node_id,
            "node_type": event.node_type or "unknown",
            "tag": _behavior_tree_tag(event),
            "last_status": event.node_status,
            "event_types": [event.event_type],
        }
        seen[event.node_id] = model
        models.append(model)
    return models


def _behavior_tree_tag(event: BtEvent) -> str:
    node_type = (event.node_type or "").lower()
    event_type = event.event_type.lower()
    if any(word in node_type for word in ("selector", "sequence", "parallel", "fallback", "control")):
        return "Control"
    if any(word in node_type for word in ("condition", "guard", "check")) or "fallback_triggered" == event_type:
        return "Condition"
    return "Action"


def bt_event_from_py_trees_transition(
    trace_id: str,
    transition: Mapping[str, Any],
    *,
    executor_id: str = "local",
    tree_id: str | None = None,
    scope: str = "project",
) -> BtEvent:
    """Normalize one py_trees-style transition record into a canonical BtEvent."""

    current_status = _status_name(
        transition.get("current_status")
        or transition.get("status")
        or transition.get("new_status")
        or transition.get("next_status")
    )
    previous_status = _status_name(transition.get("previous_status") or transition.get("old_status"))
    node_name = _optional_str(transition, "name") or _optional_str(transition, "behaviour_name")
    node_type = _optional_str(transition, "class_name") or _optional_str(transition, "behaviour_type")
    node_id = (
        _optional_str(transition, "node_id")
        or _optional_str(transition, "behaviour_id")
        or _optional_str(transition, "path")
        or node_name
    )
    if not node_id:
        raise ValueError("py_trees transition missing node identifier")

    blackboard_keys = _string_list(
        transition.get("blackboard_keys")
        or transition.get("blackboard_variables")
        or transition.get("affected_symbols")
    )
    event_type = _py_trees_event_type(current_status, previous_status)
    payload = {
        "adapter_schema": PY_TREES_ADAPTER_SCHEMA,
        "previous_status": previous_status,
        "feedback_message": _optional_str(transition, "feedback_message"),
        "tip": _optional_str(transition, "tip"),
    }
    for key, value in transition.items():
        if key not in {
            "event_id",
            "timestamp",
            "current_status",
            "status",
            "new_status",
            "next_status",
            "previous_status",
            "old_status",
            "node_id",
            "behaviour_id",
            "path",
            "name",
            "behaviour_name",
            "class_name",
            "behaviour_type",
            "tree_id",
            "executor_id",
            "scope",
            "blackboard_keys",
            "blackboard_variables",
            "affected_symbols",
            "causal_parent_ids",
        }:
            payload[key] = value

    return BtEvent.from_dict(
        {
            "event_id": transition.get("event_id"),
            "trace_id": trace_id,
            "timestamp": transition.get("timestamp") or now_iso(),
            "event_type": event_type,
            "node_id": node_id,
            "node_status": current_status,
            "executor_id": _optional_str(transition, "executor_id") or executor_id,
            "tree_id": _optional_str(transition, "tree_id") or tree_id,
            "node_name": node_name,
            "node_type": node_type,
            "scope": _optional_str(transition, "scope") or scope,
            "affected_symbols": blackboard_keys,
            "causal_parent_ids": _string_list(transition.get("causal_parent_ids")),
            "payload": payload,
        }
    )


def bt_event_from_btpg_transition(
    trace_id: str,
    transition: Mapping[str, Any],
    *,
    executor_id: str = "local",
    tree_id: str | None = None,
    scope: str = "project",
) -> BtEvent:
    """Normalize one BTPG-style transition record into a canonical BtEvent."""

    current_status = _status_name(
        transition.get("current_status")
        or transition.get("status")
        or transition.get("node_status")
        or transition.get("next_status")
    )
    previous_status = _status_name(
        transition.get("previous_status")
        or transition.get("old_status")
        or transition.get("last_status")
    )
    node_name = (
        _optional_str(transition, "node_name")
        or _optional_str(transition, "name")
        or _optional_str(transition, "task")
    )
    node_type = (
        _optional_str(transition, "node_type")
        or _optional_str(transition, "kind")
        or _optional_str(transition, "step_type")
    )
    node_id = (
        _optional_str(transition, "node_id")
        or _optional_str(transition, "task_id")
        or _optional_str(transition, "step_id")
        or node_name
    )
    if not node_id:
        raise ValueError("BTPG transition missing node identifier")

    affected_symbols = _string_list(
        transition.get("world_state_symbols")
        or transition.get("affected_symbols")
        or transition.get("facts")
        or transition.get("preconditions")
    )
    event_type = _btpg_event_type(current_status, previous_status, transition.get("event_type"))
    payload = {
        "adapter_schema": BTPG_ADAPTER_SCHEMA,
        "previous_status": previous_status,
        "goal": _optional_str(transition, "goal"),
        "failure_reason": _optional_str(transition, "failure_reason"),
        "recovery_action": _optional_str(transition, "recovery_action"),
    }
    for key, value in transition.items():
        if key not in {
            "event_id",
            "timestamp",
            "current_status",
            "status",
            "node_status",
            "next_status",
            "previous_status",
            "old_status",
            "last_status",
            "node_id",
            "task_id",
            "step_id",
            "node_name",
            "name",
            "task",
            "node_type",
            "kind",
            "step_type",
            "tree_id",
            "executor_id",
            "scope",
            "world_state_symbols",
            "affected_symbols",
            "facts",
            "preconditions",
            "causal_parent_ids",
            "event_type",
        }:
            payload[key] = value

    return BtEvent.from_dict(
        {
            "event_id": transition.get("event_id"),
            "trace_id": trace_id,
            "timestamp": transition.get("timestamp") or now_iso(),
            "event_type": event_type,
            "node_id": node_id,
            "node_status": current_status,
            "executor_id": _optional_str(transition, "executor_id") or executor_id,
            "tree_id": _optional_str(transition, "tree_id") or tree_id,
            "node_name": node_name,
            "node_type": node_type,
            "scope": _optional_str(transition, "scope") or scope,
            "affected_symbols": affected_symbols,
            "causal_parent_ids": _string_list(transition.get("causal_parent_ids")),
            "payload": payload,
        }
    )


def required_str(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"missing required BT event field: {key}")
    return result


def _optional_str(value: Mapping[str, Any], key: str) -> str | None:
    result = value.get(key)
    return result if isinstance(result, str) and result else None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("py_trees transition list fields must be lists")


def _status_name(value: Any) -> str:
    if isinstance(value, str) and value:
        return value.upper()
    if value is None:
        return "UNKNOWN"
    return str(value).upper()


def _py_trees_event_type(current_status: str, previous_status: str) -> str:
    status_map = {
        "FAILURE": "fallback_triggered" if previous_status not in {"FAILURE", "INVALID"} else "node_failure",
        "SUCCESS": "node_success",
        "RUNNING": "node_running",
        "INVALID": "node_invalidated",
    }
    return status_map.get(current_status, "node_status_changed")


def _btpg_event_type(current_status: str, previous_status: str, explicit_event_type: Any) -> str:
    if isinstance(explicit_event_type, str) and explicit_event_type:
        return explicit_event_type
    if current_status == "FAILURE":
        return "fallback_triggered" if previous_status in {"RUNNING", "SUCCESS"} else "node_failure"
    if current_status == "RUNNING" and previous_status in {"FAILURE", "INVALID"}:
        return "recovery_resumed"
    if current_status == "SUCCESS":
        return "plan_step_succeeded"
    if current_status == "RUNNING":
        return "plan_step_running"
    if current_status == "INVALID":
        return "plan_step_invalidated"
    return "plan_step_status_changed"


def _failure_reason_text(event: BtEvent) -> str:
    reason = event.payload.get("failure_reason")
    if isinstance(reason, str) and reason:
        return f" with reason: {reason}"
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zerker BT recovery memory")
    parser.add_argument("--db", type=Path, default=default_db_path(), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="Ingest BT event JSONL")
    ingest.add_argument("path", type=Path)
    explain = sub.add_parser("explain", help="Explain a BT trace")
    explain.add_argument("trace_id")
    explain.add_argument("--question")
    traces = sub.add_parser("traces", help="List BT traces")
    traces.add_argument("--limit", type=int, default=50)
    export = sub.add_parser("export", help="Export a BT trace as BehaviorTree.CPP/Groot2 artifacts")
    export.add_argument("trace_id")
    export.add_argument("--out", type=Path)
    export.add_argument("--out-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bt = BtMemory(MemoryStore(args.db))
    if args.command == "ingest":
        print(json.dumps(bt.ingest_file(args.path), indent=2, sort_keys=True))
        return 0
    if args.command == "explain":
        print(json.dumps(bt.explain(args.trace_id, question=args.question), indent=2, sort_keys=True))
        return 0
    if args.command == "traces":
        print(json.dumps(bt.traces(limit=args.limit), indent=2, sort_keys=True))
        return 0
    if args.command == "export":
        print(json.dumps(bt.export_groot2_trace(args.trace_id, out=args.out, out_dir=args.out_dir), indent=2, sort_keys=True))
        return 0
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
