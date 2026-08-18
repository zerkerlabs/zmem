from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .store import MemoryStore, digest_uri, sha256_text, stable_json

PREMISE_CONTENT_SCHEMA = "zerker.memory.reason-premise.v1"
PREMISES_ARTIFACT_SCHEMA = "zerker.memory.reason-premises.v1"
PREMISE_LABEL = "reason:premise:v1"
MAX_PREMISE_CONTENT_BYTES = 1 * 1024 * 1024
MAX_PREMISES_ARTIFACT_BYTES = 16 * 1024 * 1024

_REQUIRED_FACT_FIELDS = {"id", "predicate", "arguments", "authority", "observed_at"}
_OPTIONAL_FACT_FIELDS = {"negated", "valid_from", "valid_until", "supersedes"}


def _strict_json_object(value: str, *, memory_id: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"Reason premise memory {memory_id} contains duplicate JSON key {key!r}")
            result[key] = item
        return result

    try:
        loaded = json.loads(value, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Reason premise memory {memory_id} is not valid JSON: {exc.msg}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"Reason premise memory {memory_id} must contain a JSON object")
    return loaded


def _parse_fact(content: str, *, memory_id: str) -> dict[str, Any]:
    if len(content.encode("utf-8")) > MAX_PREMISE_CONTENT_BYTES:
        raise ValueError(
            f"Reason premise memory {memory_id} exceeds the {MAX_PREMISE_CONTENT_BYTES}-byte content limit"
        )
    envelope = _strict_json_object(content, memory_id=memory_id)
    if set(envelope) != {"schema", "fact"}:
        raise ValueError(
            f"Reason premise memory {memory_id} must contain exactly 'schema' and 'fact'"
        )
    if envelope.get("schema") != PREMISE_CONTENT_SCHEMA:
        raise ValueError(
            f"Reason premise memory {memory_id} has unsupported schema {envelope.get('schema')!r}"
        )
    fact = envelope.get("fact")
    if not isinstance(fact, dict):
        raise ValueError(f"Reason premise memory {memory_id} fact must be an object")
    fields = set(fact)
    missing = sorted(_REQUIRED_FACT_FIELDS - fields)
    unknown = sorted(fields - _REQUIRED_FACT_FIELDS - _OPTIONAL_FACT_FIELDS)
    if missing:
        raise ValueError(f"Reason premise memory {memory_id} fact is missing fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Reason premise memory {memory_id} fact has unknown fields: {', '.join(unknown)}")
    for field in ("id", "predicate", "authority", "observed_at"):
        if not isinstance(fact.get(field), str) or not fact[field].strip():
            raise ValueError(f"Reason premise memory {memory_id} fact.{field} must be a non-empty string")
    if not isinstance(fact.get("arguments"), list):
        raise ValueError(f"Reason premise memory {memory_id} fact.arguments must be an array")
    if "negated" in fact and not isinstance(fact["negated"], bool):
        raise ValueError(f"Reason premise memory {memory_id} fact.negated must be a boolean")
    for field in ("valid_from", "valid_until"):
        if field in fact and (not isinstance(fact[field], str) or not fact[field].strip()):
            raise ValueError(f"Reason premise memory {memory_id} fact.{field} must be a non-empty string")
    if "supersedes" in fact:
        supersedes = fact["supersedes"]
        if not isinstance(supersedes, list) or any(not isinstance(item, str) or not item for item in supersedes):
            raise ValueError(f"Reason premise memory {memory_id} fact.supersedes must be an array of non-empty strings")
    return fact


def _receipt_object(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    statement = receipt.get("treeship_statement")
    if not isinstance(statement, Mapping):
        return {}
    value = statement.get("object")
    return value if isinstance(value, Mapping) else {}


def _verified_premise_provenance(
    store: MemoryStore,
    *,
    memory: Mapping[str, Any],
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    memory_id = str(memory["id"])
    if not receipts:
        raise ValueError(f"Reason premise memory {memory_id} has no write-receipt chain")
    chain = store.verify_memory_write_receipt_chain(receipts, initialize=False)
    if not chain.get("ok"):
        raise ValueError(
            f"Reason premise memory {memory_id} write-receipt chain failed verification: {chain.get('error', 'unknown error')}"
        )

    content = memory.get("content")
    if not isinstance(content, str):
        raise ValueError(f"Reason premise memory {memory_id} content is invalid")
    content_hash = sha256_text(content)
    if memory.get("content_hash") != content_hash:
        raise ValueError(f"Reason premise memory {memory_id} content_hash mismatch")
    expected_content_digest = digest_uri(content)
    if any(receipt.get("content_digest") != expected_content_digest for receipt in receipts):
        raise ValueError(f"Reason premise memory {memory_id} content differs from its write-receipt chain")

    initial_object = _receipt_object(receipts[0])
    for field, memory_field in (
        ("memory_type", "type"),
        ("scope", "scope"),
        ("source_kind", "source_kind"),
        ("labels", "labels"),
    ):
        if initial_object.get(field) != memory.get(memory_field):
            raise ValueError(f"Reason premise memory {memory_id} {memory_field} differs from its write receipt")

    lifecycle_objects = [_receipt_object(receipt) for receipt in receipts]
    latest_object = lifecycle_objects[-1]
    if latest_object.get("status") != "active" or memory.get("status") != "active":
        raise ValueError(f"Reason premise memory {memory_id} is not active in its verified lifecycle")

    source_kind = memory.get("source_kind")
    promotions = [
        (receipt, obj)
        for receipt, obj in zip(receipts, lifecycle_objects)
        if obj.get("mutation") == "promote" and obj.get("status") == "active"
    ]
    if source_kind not in {"human", "system"} and not promotions:
        raise ValueError(
            f"Reason premise memory {memory_id} was authored by {source_kind!r} and has no explicit promotion receipt"
        )

    governing_receipt, governing_object = promotions[-1] if promotions else (receipts[0], initial_object)
    return {
        "memory_id": memory_id,
        "memory_scope": memory["scope"],
        "source_kind": source_kind,
        "content_digest": expected_content_digest,
        "initial_receipt_id": receipts[0]["receipt_id"],
        "initial_receipt_hash": receipts[0]["receipt_hash"],
        "governing_receipt_id": governing_receipt["receipt_id"],
        "governing_receipt_hash": governing_receipt["receipt_hash"],
        "governing_actor_uri": governing_receipt["actor_uri"],
        "governing_event_hash": governing_receipt["event_hash"],
        "governing_merkle_root": governing_receipt["merkle_root"],
        "governance_transition": governing_object.get("mutation", "observed"),
        "write_receipt_count": len(receipts),
    }


def _artifact_digest(payload: Mapping[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_digest", None)
    return "sha256:" + sha256_text(stable_json(unsigned))


def build_reason_premises(db_path: Path, *, scope: str) -> dict[str, Any]:
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("Reason premise export requires a non-empty scope")
    store = MemoryStore.open_locked_read_snapshot(db_path)
    try:
        snapshot = store.snapshot(initialize=False)
        if not store.conn.in_transaction:
            raise ValueError("locked memory snapshot ended before Reason premise export completed")
        snapshot_verification = store.verify_snapshot(snapshot)
        if not snapshot_verification.get("ok"):
            raise ValueError(
                "memory snapshot failed verification before Reason premise export: "
                + str(snapshot_verification.get("error", "unknown error"))
            )

        receipts_by_memory: dict[str, list[dict[str, Any]]] = {}
        for receipt in snapshot.get("write_receipts", []):
            if isinstance(receipt, dict) and isinstance(receipt.get("memory_id"), str):
                receipts_by_memory.setdefault(receipt["memory_id"], []).append(receipt)

        facts: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        withheld: list[dict[str, str]] = []
        seen_fact_ids: dict[str, str] = {}
        memories = sorted(snapshot.get("memories", []), key=lambda item: str(item.get("id", "")))
        for memory in memories:
            if not isinstance(memory, dict) or PREMISE_LABEL not in memory.get("labels", []):
                continue
            if memory.get("scope") not in {"global", scope}:
                continue
            memory_id = str(memory.get("id", ""))
            if memory.get("status") != "active":
                withheld.append(
                    {
                        "memory_id": memory_id,
                        "status": str(memory.get("status")),
                        "reason": "not_active",
                    }
                )
                continue
            if memory.get("type") != "policy":
                raise ValueError(f"Reason premise memory {memory_id} must have type 'policy'")

            premise_provenance = _verified_premise_provenance(
                store,
                memory=memory,
                receipts=receipts_by_memory.get(memory_id, []),
            )
            fact = _parse_fact(str(memory.get("content", "")), memory_id=memory_id)
            fact_id = str(fact["id"])
            if fact_id in seen_fact_ids:
                raise ValueError(
                    f"Reason fact id {fact_id!r} is duplicated by memories {seen_fact_ids[fact_id]} and {memory_id}"
                )
            seen_fact_ids[fact_id] = memory_id
            facts.append(fact)
            provenance.append({"fact_id": fact_id, **premise_provenance})

        facts.sort(key=lambda fact: (str(fact["id"]), stable_json(fact)))
        provenance.sort(key=lambda item: (str(item["fact_id"]), str(item["memory_id"])))
        withheld.sort(key=lambda item: item["memory_id"])
        payload: dict[str, Any] = {
            "schema": PREMISES_ARTIFACT_SCHEMA,
            "scope": scope,
            "facts": facts,
            "provenance": provenance,
            "withheld": withheld,
            "source": {
                "snapshot_merkle_root": snapshot["merkle_root"],
                "event_count": snapshot["event_count"],
                "write_receipt_count": snapshot["write_receipt_count"],
            },
        }
        payload["artifact_digest"] = _artifact_digest(payload)
        return payload
    finally:
        store.conn.rollback()
        store.conn.close()


def load_reason_premises(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > MAX_PREMISES_ARTIFACT_BYTES:
            raise ValueError(
                f"Reason premises artifact exceeds the {MAX_PREMISES_ARTIFACT_BYTES}-byte input limit"
            )
        return _strict_json_object(path.read_text(encoding="utf-8"), memory_id=f"artifact:{path}")
    except OSError as exc:
        raise ValueError(f"could not read Reason premises artifact {path}: {exc}") from exc


def verify_reason_premises(db_path: Path, artifact: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "schema": artifact.get("schema"),
        "artifact_digest": artifact.get("artifact_digest"),
        "computed_artifact_digest": _artifact_digest(artifact),
        "current": False,
    }
    try:
        if artifact.get("schema") != PREMISES_ARTIFACT_SCHEMA:
            raise ValueError("unsupported Reason premises artifact schema")
        if artifact.get("artifact_digest") != result["computed_artifact_digest"]:
            raise ValueError("Reason premises artifact_digest mismatch")
        scope = artifact.get("scope")
        if not isinstance(scope, str) or not scope:
            raise ValueError("Reason premises artifact scope is invalid")
        current = build_reason_premises(db_path, scope=scope)
        if stable_json(dict(artifact)) != stable_json(current):
            raise ValueError("Reason premises artifact is stale or does not match current governed memory")
        result["ok"] = True
        result["current"] = True
        result["fact_count"] = len(current["facts"])
        result["snapshot_merkle_root"] = current["source"]["snapshot_merkle_root"]
    except (KeyError, TypeError, ValueError) as exc:
        result["error"] = str(exc)
    return result


def write_reason_premises(path: Path, artifact: Mapping[str, Any], *, force: bool = False) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(f"Reason premises artifact already exists: {path}")
    encoded = json.dumps(dict(artifact), indent=2, sort_keys=True) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not force:
            raise FileExistsError(f"Reason premises artifact already exists: {path}")
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
