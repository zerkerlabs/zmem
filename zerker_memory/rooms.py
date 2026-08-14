from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import quote

from .store import MemoryRecord, MemoryStore, sha256_text, stable_json


ROOM_CONTEXT_SCHEMA = "zerker.room_memory_context.v1"
ROOM_CONTEXT_COMMITMENT_SCHEMA = "zerker.room_memory_context_commitment.v1"
ROOM_MEMORY_WRITE_SCHEMA = "zerker.room_memory_write.v1"
ROOM_STORAGE_SCHEMA = "zerker.room_memory_storage.v1"
ROOM_STORAGE_DESCRIPTOR_SCHEMA = "zerker.room_memory_storage_descriptor.v1"
ROOM_CONTEXT_STATES = frozenset({"ready", "partial", "empty", "blocked", "abstained", "budget_exhausted"})
ROOM_MEMORY_VISIBILITIES = frozenset({"room", "member"})
ROOM_MEMORY_TYPES = frozenset({"episodic", "semantic", "procedural", "policy"})
ROOM_RISKS = frozenset({"low", "medium", "high"})
DEFAULT_CONTEXT_BUDGET_TOKENS = 2_000
MAX_CONTEXT_BUDGET_TOKENS = 64_000
MAX_CONTENT_CHARS = 256_000
MAX_PURPOSE_CHARS = 32_000
MAX_LABELS = 64
MAX_LABEL_CHARS = 128
MAX_ABSTENTION_IDS = 64
MAX_ABSTENTION_REASONS = 16
MAX_ABSTENTION_TEXT_CHARS = 128

_ROOM_ID_RE = re.compile(r"^rom_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class RoomMemoryConflict(ValueError):
    pass


def room_storage_key(tenant_id: str, room_id: str) -> str:
    tenant = _required_text(tenant_id, "tenant_id", max_chars=256)
    room = validate_room_id(room_id)
    return hashlib.sha256(f"{tenant}\0{room}".encode("utf-8")).hexdigest()[:32]


def validate_room_id(room_id: str) -> str:
    room = _required_text(room_id, "room_id", max_chars=132)
    if not _ROOM_ID_RE.fullmatch(room):
        raise ValueError("room_id must use the opaque rom_ prefix and contain only letters, numbers, _ or -")
    return room


def member_scope(agent_id: str) -> str:
    agent = _required_text(agent_id, "agent_id", max_chars=256)
    digest = hashlib.sha256(agent.encode("utf-8")).hexdigest()[:24]
    return f"member:{digest}"


def verify_room_context_commitment(response: Mapping[str, Any]) -> bool:
    commitment = response.get("commitment")
    if not isinstance(commitment, Mapping):
        return False
    recorded = commitment.get("room_context_digest")
    if not isinstance(recorded, str):
        return False
    material = {key: value for key, value in commitment.items() if key != "room_context_digest"}
    expected = f"sha256:{sha256_text(stable_json(material))}"
    return hmac.compare_digest(recorded, expected)


def discover_room_stores(storage_root: Path, *, tenant_id: str) -> list[dict[str, Any]]:
    """Read existing room-store identities without opening or mutating their databases."""

    root = Path(storage_root).expanduser().resolve(strict=False)
    tenant = _required_text(tenant_id, "tenant_id", max_chars=256)
    if not root.exists():
        return []
    discovered: list[dict[str, Any]] = []
    for db_path in sorted(root.glob("*/memory.sqlite")):
        if db_path.is_symlink() or db_path.parent.is_symlink() or not db_path.is_file():
            continue
        descriptor_path = db_path.parent / "room.json"
        descriptor = _load_room_descriptor(descriptor_path)
        descriptor_state = "recorded"
        room_id = None
        if descriptor is not None and descriptor.get("tenant_id") == tenant:
            room_id = descriptor.get("room_id")
        if not isinstance(room_id, str):
            room_id = _infer_room_id(db_path)
            descriptor_state = "inferred" if room_id else "missing"
        if not room_id:
            continue
        try:
            room = validate_room_id(room_id)
        except ValueError:
            continue
        storage_key = room_storage_key(tenant, room)
        if db_path.parent.name != storage_key:
            continue
        discovered.append(
            {
                "schema": ROOM_STORAGE_DESCRIPTOR_SCHEMA,
                "tenant_id": tenant,
                "room_id": room,
                "storage_id": "rms_" + storage_key,
                "db_path": str(db_path.resolve(strict=False)),
                "descriptor_path": str(descriptor_path.resolve(strict=False)),
                "descriptor_state": descriptor_state,
            }
        )
    return discovered


def _load_room_descriptor(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") != ROOM_STORAGE_DESCRIPTOR_SCHEMA:
        return None
    return payload


def _infer_room_id(db_path: Path) -> str | None:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        row = connection.execute(
            "SELECT session_id FROM memory_write_receipts WHERE session_id LIKE 'room://rom_%' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        if connection is not None:
            connection.close()
    if not row or not isinstance(row[0], str) or not row[0].startswith("room://"):
        return None
    return row[0].removeprefix("room://")


class RoomStoreResolver:
    """Resolve one private SQLite store per room inside one configured tenant."""

    def __init__(self, storage_root: Path, *, tenant_id: str, policy_path: Path | None = None):
        self.storage_root = Path(storage_root).expanduser().resolve(strict=False)
        self.tenant_id = _required_text(tenant_id, "tenant_id", max_chars=256)
        self.policy_path = Path(policy_path).expanduser().resolve(strict=False) if policy_path is not None else None
        self._initialization_locks: dict[str, threading.Lock] = {}
        self._initialization_locks_guard = threading.Lock()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        try:
            self.storage_root.chmod(0o700)
        except OSError:
            pass

    def db_path(self, room_id: str) -> Path:
        room = validate_room_id(room_id)
        return self.storage_root / room_storage_key(self.tenant_id, room) / "memory.sqlite"

    def storage_identity(self, room_id: str) -> dict[str, Any]:
        room = validate_room_id(room_id)
        return {
            "schema": ROOM_STORAGE_SCHEMA,
            "tenant_id": self.tenant_id,
            "room_id": room,
            "storage_id": "rms_" + room_storage_key(self.tenant_id, room),
        }

    def list_rooms(self) -> list[dict[str, Any]]:
        return discover_room_stores(self.storage_root, tenant_id=self.tenant_id)

    def _ensure_descriptor(self, room_id: str) -> None:
        identity = self.storage_identity(room_id)
        descriptor = {
            "schema": ROOM_STORAGE_DESCRIPTOR_SCHEMA,
            "tenant_id": identity["tenant_id"],
            "room_id": identity["room_id"],
            "storage_id": identity["storage_id"],
            "database": "memory.sqlite",
        }
        descriptor_path = self.db_path(room_id).parent / "room.json"
        existing = _load_room_descriptor(descriptor_path)
        if existing is not None:
            comparable = {key: existing.get(key) for key in descriptor}
            if comparable != descriptor:
                raise ValueError("room storage descriptor does not match the configured tenant and room")
            return
        if descriptor_path.exists():
            raise ValueError("room storage descriptor is malformed or unsupported")
        descriptor_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            descriptor_path.chmod(0o600)
        except OSError:
            pass

    def _initialization_lock(self, room_id: str) -> threading.Lock:
        storage_key = room_storage_key(self.tenant_id, room_id)
        with self._initialization_locks_guard:
            return self._initialization_locks.setdefault(storage_key, threading.Lock())

    @contextmanager
    def open(self, room_id: str) -> Iterator[MemoryStore]:
        path = self.db_path(room_id)
        if path.parent.is_symlink():
            raise ValueError("room storage directory cannot be a symlink")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.resolve() != path.parent:
            raise ValueError("room storage directory escaped the configured storage root")
        if path.is_symlink():
            raise ValueError("room database cannot be a symlink")
        try:
            path.parent.chmod(0o700)
        except OSError:
            pass
        with self._initialization_lock(room_id):
            self._ensure_descriptor(room_id)
            store = MemoryStore(path, policy_path=self.policy_path)
            try:
                store.init()
            except BaseException:
                store.conn.close()
                raise
        try:
            yield store
        finally:
            store.conn.close()


class RoomMemoryService:
    def __init__(
        self,
        resolver: RoomStoreResolver,
        *,
        retrieval_config: dict[str, Any] | None = None,
        retrieval_provider_config: dict[str, Any] | None = None,
    ):
        self.resolver = resolver
        self.retrieval_config = retrieval_config
        self.retrieval_provider_config = retrieval_provider_config

    def prepare_context(self, request: Mapping[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        room_id = validate_room_id(request.get("room_id"))
        agent_id = _required_text(request.get("agent_id"), "agent_id", max_chars=256)
        purpose = _request_purpose(request)
        risk = str(request.get("risk") or "medium")
        if risk not in ROOM_RISKS:
            raise ValueError(f"risk must be one of: {', '.join(sorted(ROOM_RISKS))}")
        context_budget_tokens = _context_budget(request.get("context_budget_tokens"))
        membership_digest = _optional_digest(request.get("membership_digest"), "membership_digest")
        room_state_digest = _optional_digest(request.get("room_state_digest"), "room_state_digest")
        request_id = _optional_text(request.get("request_id"), "request_id", max_chars=256)

        scope = member_scope(agent_id)
        with self.resolver.open(room_id) as store:
            retrieval_index = self._refresh_retrieval_index(store, scope=scope)
            receipt = store.inject(
                purpose,
                agent_id=agent_id,
                risk=risk,
                scope=scope,
                context_budget_tokens=context_budget_tokens,
                retrieval_config=self.retrieval_config,
                retrieval_provider_config=self.retrieval_provider_config,
            )
            has_active_memory = bool(store.list_memories(scope=scope, status="active", limit=1))

        packing = receipt.get("retrieval", {}).get("packing", {})
        budget_dropped = packing.get("budget_dropped") if isinstance(packing.get("budget_dropped"), list) else []
        withheld = receipt.get("withheld") if isinstance(receipt.get("withheld"), list) else []
        temporal = receipt.get("retrieval", {}).get("temporal", {})
        abstention = temporal.get("abstention") if isinstance(temporal, Mapping) else None
        abstained = bool(isinstance(abstention, Mapping) and abstention.get("applied") is True)
        if not abstained and not receipt.get("retrieved_memory_ids") and has_active_memory:
            abstention = {
                "applied": True,
                "reason": "no-relevant-memory",
                "abstained_ids": [],
                "conflict_reasons": [],
            }
            abstained = True
        memories = receipt.get("memories") if isinstance(receipt.get("memories"), list) else []
        state = _context_state(
            injected_count=len(memories),
            retrieved_count=len(receipt.get("retrieved_memory_ids") or []),
            withheld_count=len(withheld),
            budget_dropped_count=len(budget_dropped),
            abstained=abstained,
        )
        public_memories = [
            _public_memory(
                memory,
                agent_id=agent_id,
                write_receipt=(receipt.get("injected_memory_write_receipts") or {}).get(str(memory.get("id"))),
            )
            for memory in memories
            if isinstance(memory, Mapping)
        ]
        context_commitment = receipt.get("memory_context") if isinstance(receipt.get("memory_context"), Mapping) else {}
        storage = self.resolver.storage_identity(room_id)
        commitment = {
            "schema": ROOM_CONTEXT_COMMITMENT_SCHEMA,
            "tenant_id": self.resolver.tenant_id,
            "room_id": room_id,
            "agent_id": agent_id,
            "request_id": request_id,
            "purpose_hash": f"sha256:{sha256_text(purpose)}",
            "risk": risk,
            "context_budget_tokens": context_budget_tokens,
            "membership_digest": membership_digest,
            "room_state_digest": room_state_digest,
            "zmem_action_id": receipt.get("action_id"),
            "zmem_context_digest": context_commitment.get("context_digest"),
            "policy_digest": context_commitment.get("policy_digest"),
            "memory_merkle_root": context_commitment.get("memory_tree_root"),
            "event_merkle_root": receipt.get("merkle_root"),
            "selected_memory_ids": [memory.get("id") for memory in public_memories],
            "state": state,
            "created_at": receipt.get("created_at"),
        }
        commitment["room_context_digest"] = f"sha256:{sha256_text(stable_json(commitment))}"
        return {
            "schema": ROOM_CONTEXT_SCHEMA,
            "state": state,
            "tenant_id": self.resolver.tenant_id,
            "room_id": room_id,
            "agent_id": agent_id,
            "request_id": request_id,
            "storage_id": storage["storage_id"],
            "memories": public_memories,
            "counts": {
                "retrieved": len(receipt.get("retrieved_memory_ids") or []),
                "admitted": len(public_memories),
                "withheld": len(withheld),
                "budget_dropped": len(budget_dropped),
            },
            "omissions": {
                "withheld": [_compact_withheld(item) for item in withheld if isinstance(item, Mapping)],
                "budget_dropped": [_compact_budget_drop(item) for item in budget_dropped if isinstance(item, Mapping)],
                "abstention": _compact_abstention(abstention) if isinstance(abstention, Mapping) else None,
            },
            "packing": {
                "max_tokens": packing.get("max_tokens"),
                "used_tokens": packing.get("used_tokens"),
                "available_tokens": packing.get("available_tokens"),
                "strategy": packing.get("strategy"),
            },
            "retrieval_index": retrieval_index,
            "commitment": commitment,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    def propose_memory(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return self._write_memory(request, trusted=False)

    def record_memory(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return self._write_memory(request, trusted=True)

    def _write_memory(self, request: Mapping[str, Any], *, trusted: bool) -> dict[str, Any]:
        room_id = validate_room_id(request.get("room_id"))
        agent_id = _required_text(request.get("agent_id"), "agent_id", max_chars=256)
        content = _required_text(request.get("content"), "content", max_chars=MAX_CONTENT_CHARS)
        memory_type = str(request.get("memory_type") or "semantic")
        if memory_type not in ROOM_MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of: {', '.join(sorted(ROOM_MEMORY_TYPES))}")
        visibility = str(request.get("visibility") or "room")
        if visibility not in ROOM_MEMORY_VISIBILITIES:
            raise ValueError(f"visibility must be one of: {', '.join(sorted(ROOM_MEMORY_VISIBILITIES))}")
        source_event_id = _required_text(request.get("source_event_id"), "source_event_id", max_chars=256)
        idempotency_key = _required_text(request.get("idempotency_key"), "idempotency_key", max_chars=256)
        parent_action_id = _optional_text(request.get("parent_action_id"), "parent_action_id", max_chars=256)
        parents = _string_list(request.get("parents"), "parents", max_items=64, max_chars=128)
        labels = _string_list(request.get("labels"), "labels", max_items=MAX_LABELS, max_chars=MAX_LABEL_CHARS)
        scope = "global" if visibility == "room" else member_scope(agent_id)
        generated_labels = ["room-memory", f"visibility:{visibility}", f"contributor:{agent_id}"]
        normalized_labels = sorted(set(labels + generated_labels))
        operation = "record" if trusted else "propose"
        actor_uri = "service://zerker-rooms" if trusted else f"agent://{agent_id}"
        session_id = f"room://{room_id}"
        source_uri = f"room://{room_id}/events/{quote(source_event_id, safe='')}"
        memory_id = _idempotent_memory_id(
            tenant_id=self.resolver.tenant_id,
            room_id=room_id,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        expected = {
            "type": memory_type,
            "content_hash": sha256_text(content),
            "scope": scope,
            "parents": parents,
            "labels": normalized_labels,
            "status": "active" if trusted else "quarantined",
        }
        replayed = False
        with self.resolver.open(room_id) as store:
            try:
                memory = store.get(memory_id)
            except KeyError:
                try:
                    memory = store.remember(
                        content,
                        memory_type=memory_type,
                        scope=scope,
                        source_kind="system" if trusted else "agent",
                        status="active" if trusted else "quarantined",
                        actor_id="zerker-rooms" if trusted else agent_id,
                        actor_uri=actor_uri,
                        session_id=session_id,
                        source_uri=source_uri,
                        caused_by_event=source_event_id,
                        parent_action_id=parent_action_id,
                        parents=parents,
                        labels=normalized_labels,
                        memory_id=memory_id,
                    )
                except sqlite3.IntegrityError:
                    store.conn.rollback()
                    memory = store.get(memory_id)
                    replayed = True
                except ValueError as exc:
                    if str(exc) != f"memory id already exists: {memory_id}":
                        raise
                    memory = store.get(memory_id)
                    replayed = True
            else:
                replayed = True
            if not _memory_matches(memory, expected):
                raise RoomMemoryConflict("idempotency key was already used for a different room memory")
            write_receipt = store.memory_write_receipt(memory.id)
            if not _write_receipt_matches(
                write_receipt,
                actor_uri=actor_uri,
                session_id=session_id,
                source_uri=source_uri,
                caused_by_event=source_event_id,
                parent_action_id=parent_action_id,
            ):
                raise RoomMemoryConflict("idempotency key was already used for a different room event")
            retrieval_index = self._refresh_retrieval_index(store, scope=scope)
            event_root = store.current_merkle_root()

        return {
            "schema": ROOM_MEMORY_WRITE_SCHEMA,
            "operation": operation,
            "replayed": replayed,
            "tenant_id": self.resolver.tenant_id,
            "room_id": room_id,
            "agent_id": agent_id,
            "visibility": visibility,
            "storage_id": self.resolver.storage_identity(room_id)["storage_id"],
            "memory": _public_memory(memory.to_dict(), agent_id=agent_id, write_receipt=write_receipt),
            "proof": {
                "receipt_id": write_receipt.get("receipt_id"),
                "receipt_hash": write_receipt.get("receipt_hash"),
                "event_hash": write_receipt.get("event_hash"),
                "event_merkle_root": event_root,
                "treeship_artifact_id": _treeship_artifact_id(write_receipt),
            },
            "retrieval_index": retrieval_index,
        }

    def _refresh_retrieval_index(self, store: MemoryStore, *, scope: str) -> dict[str, Any]:
        dense = self.retrieval_config.get("dense") if isinstance(self.retrieval_config, Mapping) else None
        if not isinstance(dense, Mapping) or dense.get("enabled") is not True:
            return {
                "mode": "fts",
                "state": "not-required",
                "network_calls_enabled": False,
            }
        from .retrieval_providers import local_dense_provider_config

        provider_id = str(dense.get("provider_id") or "local:fastembed")
        provider_config = self.retrieval_provider_config or local_dense_provider_config()
        try:
            result = store.index_embeddings(
                provider_config=provider_config,
                provider_id=provider_id,
                scope=scope,
                allow_model_download=False,
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            return {
                "mode": "dense-hybrid",
                "state": "unavailable",
                "provider_id": provider_id,
                "reason": _retrieval_index_failure_reason(exc),
                "network_calls_enabled": False,
            }
        return {
            "mode": "dense-hybrid",
            "state": "ready" if result.get("missing_or_stale_count") == 0 else "partial",
            "provider_id": result.get("provider_id"),
            "model_id": result.get("model_id"),
            "model_digest": result.get("model_digest"),
            "coverage": result.get("coverage"),
            "indexed_now": result.get("indexed_count"),
            "missing_or_stale": result.get("missing_or_stale_count"),
            "index_hash": result.get("index_hash"),
            "network_calls_enabled": False,
        }


def _context_state(
    *,
    injected_count: int,
    retrieved_count: int,
    withheld_count: int,
    budget_dropped_count: int,
    abstained: bool,
) -> str:
    if injected_count:
        return "partial" if withheld_count or budget_dropped_count or abstained else "ready"
    if abstained:
        return "abstained"
    if withheld_count:
        return "blocked"
    if budget_dropped_count:
        return "budget_exhausted"
    if retrieved_count:
        return "blocked"
    return "empty"


def _retrieval_index_failure_reason(exc: BaseException) -> str:
    message = str(exc).lower()
    if "install" in message or "fastembed" in message:
        return "dense-runtime-unavailable"
    if "model" in message or "cache" in message:
        return "dense-model-unavailable"
    return "dense-index-unavailable"


def _public_memory(
    memory: Mapping[str, Any],
    *,
    agent_id: str,
    write_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    scope = str(memory.get("scope") or "")
    visibility = "room" if scope == "global" else "member"
    result = {
        "id": memory.get("id"),
        "type": memory.get("type"),
        "content": memory.get("content"),
        "visibility": visibility,
        "owner_agent_id": agent_id if visibility == "member" else None,
        "source_kind": memory.get("source_kind"),
        "trust": memory.get("trust"),
        "authority": memory.get("authority"),
        "status": memory.get("status"),
        "parents": list(memory.get("parents") or []),
        "labels": list(memory.get("labels") or []),
        "created_at": memory.get("created_at"),
        "updated_at": memory.get("updated_at"),
        "expires_at": memory.get("expires_at"),
        "content_hash": memory.get("content_hash"),
    }
    if isinstance(write_receipt, Mapping):
        statement = write_receipt.get("treeship_statement")
        statement_object = statement.get("object") if isinstance(statement, Mapping) else None
        result["provenance"] = {
            "receipt_id": write_receipt.get("receipt_id"),
            "receipt_hash": write_receipt.get("receipt_hash"),
            "actor_uri": write_receipt.get("actor_uri"),
            "source_uri": write_receipt.get("source_uri"),
            "session_id": write_receipt.get("session_id"),
            "caused_by_event": (
                statement_object.get("caused_by_event") if isinstance(statement_object, Mapping) else None
            ),
            "parent_action_id": write_receipt.get("parent_action_id"),
            "event_hash": write_receipt.get("event_hash"),
            "merkle_root": write_receipt.get("merkle_root"),
            "treeship_artifact_id": _treeship_artifact_id(write_receipt),
        }
    return result


def _treeship_artifact_id(write_receipt: Mapping[str, Any]) -> str | None:
    attestation = write_receipt.get("treeship_attestation")
    return str(attestation.get("artifact_id")) if isinstance(attestation, Mapping) and attestation.get("artifact_id") else None


def _compact_withheld(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": item.get("memory_id"),
        "reason": item.get("reason"),
        "rule": item.get("rule"),
    }


def _compact_budget_drop(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": item.get("memory_id"),
        "reason": item.get("reason"),
        "approx_tokens": item.get("approx_tokens"),
        "rank": item.get("rank"),
        "packing_rank": item.get("packing_rank"),
        "packing_rank_basis": item.get("packing_rank_basis"),
    }


def _compact_abstention(item: Mapping[str, Any]) -> dict[str, Any]:
    abstained_ids = item.get("abstained_ids") if isinstance(item.get("abstained_ids"), list) else []
    conflict_reasons = item.get("conflict_reasons") if isinstance(item.get("conflict_reasons"), list) else []
    valid_abstained_ids = [value for value in abstained_ids if isinstance(value, str)]
    public_ids = [
        value[:MAX_ABSTENTION_TEXT_CHARS]
        for value in valid_abstained_ids
    ][:MAX_ABSTENTION_IDS]
    public_reasons = [
        value[:MAX_ABSTENTION_TEXT_CHARS]
        for value in conflict_reasons
        if isinstance(value, str)
    ][:MAX_ABSTENTION_REASONS]
    reason = item.get("reason")
    return {
        "applied": item.get("applied") is True,
        "reason": reason[:MAX_ABSTENTION_TEXT_CHARS] if isinstance(reason, str) else None,
        "abstained_ids": public_ids,
        "abstained_count": len(valid_abstained_ids),
        "conflict_reasons": public_reasons,
    }


def _memory_matches(memory: MemoryRecord, expected: Mapping[str, Any]) -> bool:
    return (
        memory.type == expected.get("type")
        and memory.content_hash == expected.get("content_hash")
        and memory.scope == expected.get("scope")
        and memory.parents == expected.get("parents")
        and memory.labels == expected.get("labels")
        and memory.status == expected.get("status")
    )


def _write_receipt_matches(
    receipt: Mapping[str, Any],
    *,
    actor_uri: str,
    session_id: str,
    source_uri: str,
    caused_by_event: str,
    parent_action_id: str | None,
) -> bool:
    statement = receipt.get("treeship_statement")
    statement_object = statement.get("object") if isinstance(statement, Mapping) else None
    receipt_caused_by_event = (
        statement_object.get("caused_by_event") if isinstance(statement_object, Mapping) else receipt.get("caused_by_event")
    )
    return (
        receipt.get("actor_uri") == actor_uri
        and receipt.get("session_id") == session_id
        and receipt.get("source_uri") == source_uri
        and receipt_caused_by_event == caused_by_event
        and receipt.get("parent_action_id") == parent_action_id
    )


def _idempotent_memory_id(*, tenant_id: str, room_id: str, operation: str, idempotency_key: str) -> str:
    material = f"zerker.room_memory.v1\0{tenant_id}\0{room_id}\0{operation}\0{idempotency_key}"
    return "mem_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _context_budget(value: Any) -> int:
    if value is None:
        return DEFAULT_CONTEXT_BUDGET_TOKENS
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("context_budget_tokens must be an integer")
    if value < 1 or value > MAX_CONTEXT_BUDGET_TOKENS:
        raise ValueError(f"context_budget_tokens must be between 1 and {MAX_CONTEXT_BUDGET_TOKENS}")
    return value


def _request_purpose(request: Mapping[str, Any]) -> str:
    purpose = request.get("purpose")
    task = request.get("task")
    if purpose is not None and task is not None and purpose != task:
        raise ValueError("purpose and task must match when both are supplied")
    return _required_text(purpose if purpose is not None else task, "purpose", max_chars=MAX_PURPOSE_CHARS)


def _optional_digest(value: Any, name: str) -> str | None:
    if value is None:
        return None
    digest = _required_text(value, name, max_chars=71)
    if not _DIGEST_RE.fullmatch(digest):
        raise ValueError(f"{name} must be a sha256:<64 lowercase hex> digest")
    return digest


def _required_text(value: Any, name: str, *, max_chars: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    result = value.strip()
    if len(result) > max_chars:
        raise ValueError(f"{name} must be at most {max_chars} characters")
    if any(ord(char) < 32 and char not in {"\n", "\r", "\t"} for char in result):
        raise ValueError(f"{name} contains unsupported control characters")
    return result


def _optional_text(value: Any, name: str, *, max_chars: int) -> str | None:
    if value is None:
        return None
    return _required_text(value, name, max_chars=max_chars)


def _string_list(value: Any, name: str, *, max_items: int, max_chars: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array of strings")
    if len(value) > max_items:
        raise ValueError(f"{name} must contain at most {max_items} items")
    return [_required_text(item, f"{name} item", max_chars=max_chars) for item in value]
