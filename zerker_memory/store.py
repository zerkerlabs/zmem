from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .policy import POLICY_ENGINE, authority_at_least, decide_memory, load_policy_config, max_authority


MEMORY_TYPES = {"episodic", "semantic", "procedural", "policy"}
AUTHORITIES = {"none", "low", "medium", "high", "policy"}
STATUSES = {"proposed", "quarantined", "active", "deprecated", "revoked", "forgotten"}
HASH_ALG = "sha256"
MERKLE_ALG = "binary-sha256-v1"
RECEIPT_SCHEMA = "zerker.memory_action.v1"
EVENT_SCHEMA = "zerker.memory_event.v1"
SNAPSHOT_SCHEMA = "zerker.memory_snapshot.v1"
BUNDLE_SCHEMA = "zerker.receipt_bundle.v1"
MEMORY_TREE_SCHEMA = "zerker.memory_tree.v1"


def default_db_path() -> Path:
    return Path.cwd() / ".zerker" / "memory.sqlite"


def default_policy_path() -> Path:
    return Path.cwd() / ".zerker" / "policy.json"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def query_terms(value: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z0-9_]+", value) if len(term) > 2]


def fts_safe_query(value: str) -> str:
    terms = query_terms(value)
    return " ".join(f'"{term}"' for term in terms)


def merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return sha256_text("")
    level = hashes[:]
    while len(level) > 1:
        nxt: list[str] = []
        for idx in range(0, len(level), 2):
            left = level[idx]
            right = level[idx + 1] if idx + 1 < len(level) else left
            nxt.append(sha256_text(left + right))
        level = nxt
    return level[0]


def merkle_proof(hashes: list[str], index: int) -> list[dict[str, Any]]:
    if index < 0 or index >= len(hashes):
        raise IndexError("merkle proof index out of range")
    proof: list[dict[str, Any]] = []
    level = hashes[:]
    cursor = index
    while len(level) > 1:
        sibling_index = cursor - 1 if cursor % 2 else cursor + 1
        if sibling_index >= len(level):
            sibling_index = cursor
        proof.append(
            {
                "position": "left" if sibling_index < cursor else "right",
                "hash": level[sibling_index],
            }
        )
        nxt: list[str] = []
        for idx in range(0, len(level), 2):
            left = level[idx]
            right = level[idx + 1] if idx + 1 < len(level) else left
            nxt.append(sha256_text(left + right))
        cursor //= 2
        level = nxt
    return proof


def verify_merkle_proof(leaf_hash: str, proof: list[dict[str, Any]], root: str) -> bool:
    computed = leaf_hash
    for item in proof:
        sibling = str(item.get("hash", ""))
        if item.get("position") == "left":
            computed = sha256_text(sibling + computed)
        elif item.get("position") == "right":
            computed = sha256_text(computed + sibling)
        else:
            return False
    return computed == root


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    type: str
    content: str
    scope: str
    source_kind: str
    trust: float
    authority: str
    status: str
    parents: list[str]
    labels: list[str]
    created_at: str
    updated_at: str
    expires_at: str | None
    content_hash: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MemoryRecord":
        return cls(
            id=row["id"],
            type=row["type"],
            content=row["content"],
            scope=row["scope"],
            source_kind=row["source_kind"],
            trust=row["trust"],
            authority=row["authority"],
            status=row["status"],
            parents=json.loads(row["parents_json"]),
            labels=json.loads(row["labels_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            content_hash=row["content_hash"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "scope": self.scope,
            "source_kind": self.source_kind,
            "trust": self.trust,
            "authority": self.authority,
            "status": self.status,
            "parents": self.parents,
            "labels": self.labels,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "content_hash": self.content_hash,
        }


class MemoryStore:
    def __init__(self, db_path: Path | None = None, *, policy_path: Path | None = None):
        self.db_path = db_path or default_db_path()
        self.policy_path = policy_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
              id TEXT PRIMARY KEY,
              type TEXT NOT NULL,
              content TEXT NOT NULL,
              scope TEXT NOT NULL,
              source_kind TEXT NOT NULL,
              trust REAL NOT NULL,
              authority TEXT NOT NULL,
              status TEXT NOT NULL,
              parents_json TEXT NOT NULL,
              labels_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              expires_at TEXT,
              content_hash TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
              USING fts5(id UNINDEXED, content, labels);

            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event_type TEXT NOT NULL,
              memory_id TEXT,
              action_id TEXT,
              actor_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              prev_event_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL,
              merkle_root TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS receipts (
              action_id TEXT PRIMARY KEY,
              receipt_schema TEXT NOT NULL DEFAULT 'zerker.memory_action.v1',
              hash_alg TEXT NOT NULL DEFAULT 'sha256',
              merkle_alg TEXT NOT NULL DEFAULT 'binary-sha256-v1',
              agent_id TEXT NOT NULL,
              task TEXT NOT NULL,
              task_hash TEXT NOT NULL,
              risk TEXT NOT NULL,
              retrieved_ids_json TEXT NOT NULL,
              retrieval_json TEXT NOT NULL DEFAULT '{}',
              injected_ids_json TEXT NOT NULL,
              withheld_json TEXT NOT NULL,
              policy_checks_json TEXT NOT NULL,
              memory_tree_json TEXT NOT NULL DEFAULT '{}',
              merkle_root TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self._ensure_column("receipts", "retrieval_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("receipts", "memory_tree_json", "TEXT NOT NULL DEFAULT '{}'")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def remember(
        self,
        content: str,
        *,
        memory_type: str,
        scope: str,
        source_kind: str,
        trust: float | None = None,
        authority: str | None = None,
        status: str | None = None,
        actor_id: str = "human",
        parents: list[str] | None = None,
        labels: list[str] | None = None,
        source_uri: str | None = None,
    ) -> MemoryRecord:
        self.init()
        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"unsupported memory type: {memory_type}")
        parents = parents or []
        labels = labels or []
        trust = self._default_trust(source_kind) if trust is None else trust
        authority = self._default_authority(memory_type, source_kind) if authority is None else authority
        if authority not in AUTHORITIES:
            raise ValueError(f"unsupported authority: {authority}")
        status = status or self._default_status(source_kind, memory_type)
        if status not in STATUSES:
            raise ValueError(f"unsupported status: {status}")
        memory_id = "mem_" + uuid.uuid4().hex[:16]
        created_at = now_iso()
        content_hash = sha256_text(content)
        self.conn.execute(
            """
            INSERT INTO memories (
              id, type, content, scope, source_kind, trust, authority, status,
              parents_json, labels_json, created_at, updated_at, expires_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                memory_type,
                content,
                scope,
                source_kind,
                trust,
                authority,
                status,
                stable_json(parents),
                stable_json(labels),
                created_at,
                created_at,
                None,
                content_hash,
            ),
        )
        self.conn.execute(
            "INSERT INTO memories_fts (id, content, labels) VALUES (?, ?, ?)",
            (memory_id, content, " ".join(labels)),
        )
        self._append_event(
            "PROPOSED" if status in {"proposed", "quarantined"} else "OBSERVED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={
                "id": memory_id,
                "type": memory_type,
                "scope": scope,
                "source_kind": source_kind,
                "trust": trust,
                "authority": authority,
                "status": status,
                "content_hash": content_hash,
                "source_uri": source_uri,
            },
        )
        self.conn.commit()
        return self.get(memory_id)

    def import_external(
        self,
        candidate: Any,
        *,
        memory_type: str = "semantic",
        scope: str = "global",
        actor_id: str = "zerker",
        trust: float | None = None,
        authority: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
    ) -> MemoryRecord:
        merged_labels = [f"provider:{candidate.provider}", f"external:{candidate.external_id}"]
        if candidate.score is not None:
            merged_labels.append(f"score:{candidate.score:.3f}")
        if labels:
            merged_labels.extend(str(label) for label in labels)
        source_uri = candidate.source_uri or f"{candidate.provider}://{candidate.external_id}"
        return self.remember(
            candidate.content,
            memory_type=memory_type,
            scope=scope,
            source_kind="import",
            actor_id=actor_id,
            trust=trust,
            authority=authority,
            status=status,
            labels=merged_labels,
            source_uri=source_uri,
        )

    def get(self, memory_id: str) -> MemoryRecord:
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(f"memory not found: {memory_id}")
        return MemoryRecord.from_row(row)

    def list_memories(
        self,
        *,
        scope: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        self.init()
        if status is not None and status not in STATUSES:
            raise ValueError(f"unsupported status: {status}")
        params: list[Any] = []
        where: list[str] = []
        if scope:
            where.append("(scope = ? OR scope = 'global')")
            params.append(scope)
        if status:
            where.append("status = ?")
            params.append(status)
        where_sql = "WHERE " + " AND ".join(where) if where else ""
        params.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM memories
            {where_sql}
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def memory_leaf(self, memory: MemoryRecord) -> dict[str, Any]:
        material = {
            "memory_id": memory.id,
            "type": memory.type,
            "content_hash": memory.content_hash,
            "scope": memory.scope,
            "source_kind": memory.source_kind,
            "trust": memory.trust,
            "authority": memory.authority,
            "status": memory.status,
            "parents": memory.parents,
            "labels": memory.labels,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "expires_at": memory.expires_at,
        }
        return {
            "schema": "zerker.memory_leaf.v1",
            "hash_alg": HASH_ALG,
            "memory_id": memory.id,
            "content_hash": memory.content_hash,
            "material": material,
            "leaf_hash": sha256_text(stable_json(material)),
        }

    def memory_tree(self, memories: list[MemoryRecord], *, scope: str = "selected") -> dict[str, Any]:
        leaves = [self.memory_leaf(memory) for memory in sorted(memories, key=lambda item: item.id)]
        leaf_hashes = [leaf["leaf_hash"] for leaf in leaves]
        root = merkle_root(leaf_hashes)
        proofs = {
            leaf["memory_id"]: {
                "memory_id": leaf["memory_id"],
                "leaf_hash": leaf["leaf_hash"],
                "root": root,
                "leaf_index": index,
                "leaf_count": len(leaves),
                "proof": merkle_proof(leaf_hashes, index),
            }
            for index, leaf in enumerate(leaves)
        }
        return {
            "schema": MEMORY_TREE_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "scope": scope,
            "root": root,
            "leaf_count": len(leaves),
            "leaves": leaves,
            "proofs": proofs,
        }

    def list_receipts(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.init()
        rows = self.conn.execute(
            """
            SELECT action_id, agent_id, task, risk, merkle_root, created_at
            FROM receipts
            ORDER BY created_at DESC, action_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, Any]:
        self.init()
        memory_status = {
            row["status"]: row["count"]
            for row in self.conn.execute("SELECT status, COUNT(*) AS count FROM memories GROUP BY status").fetchall()
        }
        memory_types = {
            row["type"]: row["count"]
            for row in self.conn.execute("SELECT type, COUNT(*) AS count FROM memories GROUP BY type").fetchall()
        }
        receipt_count = self.conn.execute("SELECT COUNT(*) AS count FROM receipts").fetchone()["count"]
        event_count = self.conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
        active_memory_tree = self.memory_tree(self.list_memories(status="active", limit=10_000), scope="active")
        return {
            "db_path": str(self.db_path),
            "merkle_root": self.current_merkle_root(),
            "memory_merkle_root": active_memory_tree["root"],
            "memory_status": memory_status,
            "memory_types": memory_types,
            "memory_count": sum(memory_status.values()),
            "receipt_count": receipt_count,
            "event_count": event_count,
        }

    def _exists(self, memory_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM memories WHERE id = ? LIMIT 1", (memory_id,)).fetchone()
        return row is not None

    def search(self, query: str, *, scope: str | None = None, include_quarantined: bool = False) -> list[MemoryRecord]:
        return self.search_with_meta(query, scope=scope, include_quarantined=include_quarantined)["memories"]

    def search_with_meta(self, query: str, *, scope: str | None = None, include_quarantined: bool = False) -> dict[str, Any]:
        self.init()
        status_sql = "m.status IN ('active')"
        fts_query = fts_safe_query(query)
        params: list[Any] = [fts_query]
        if include_quarantined:
            status_sql = "m.status IN ('active', 'quarantined', 'proposed')"
        scope_sql = ""
        if scope:
            scope_sql = "AND (m.scope = ? OR m.scope = 'global')"
            params.append(scope)
        rows = []
        search_mode = "none"
        if fts_query:
            try:
                rows = self.conn.execute(
                    f"""
                    SELECT m.*
                    FROM memories_fts f
                    JOIN memories m ON m.id = f.id
                    WHERE memories_fts MATCH ?
                      AND {status_sql}
                      {scope_sql}
                    ORDER BY m.authority DESC, m.trust DESC, bm25(memories_fts)
                    LIMIT 20
                    """,
                    params,
                ).fetchall()
                if rows:
                    search_mode = "fts"
            except sqlite3.OperationalError:
                rows = []
        if not rows:
            terms = query_terms(query)
            if terms:
                like_sql = " OR ".join(["lower(m.content) LIKE ?" for _ in terms])
                like_params: list[Any] = [f"%{term}%" for term in terms]
                if scope:
                    like_params.append(scope)
                rows = self.conn.execute(
                    f"""
                    SELECT m.*
                    FROM memories m
                    WHERE ({like_sql})
                      AND {status_sql}
                      {scope_sql}
                    ORDER BY m.authority DESC, m.trust DESC
                    LIMIT 20
                    """,
                    like_params,
                ).fetchall()
                if rows:
                    search_mode = "fallback"
        return {
            "memories": [MemoryRecord.from_row(row) for row in rows],
            "query": query,
            "fts_query": fts_query,
            "search_mode": search_mode,
        }

    def queue(self, *, scope: str | None = None, status: str | None = None) -> list[MemoryRecord]:
        self.init()
        if status is not None and status not in STATUSES:
            raise ValueError(f"unsupported status: {status}")
        statuses = [status] if status else ["quarantined", "proposed"]
        placeholders = ",".join(["?"] * len(statuses))
        params: list[Any] = statuses[:]
        scope_sql = ""
        if scope:
            scope_sql = "AND (scope = ? OR scope = 'global')"
            params.append(scope)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM memories
            WHERE status IN ({placeholders})
              {scope_sql}
            ORDER BY created_at ASC
            """,
            params,
        ).fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def children(self, memory_id: str) -> list[MemoryRecord]:
        self.init()
        rows = self.conn.execute("SELECT * FROM memories ORDER BY created_at ASC").fetchall()
        children = []
        for row in rows:
            memory = MemoryRecord.from_row(row)
            if memory_id in memory.parents:
                children.append(memory)
        return children

    def descendants(self, memory_id: str) -> list[MemoryRecord]:
        seen: set[str] = set()
        ordered: list[MemoryRecord] = []
        stack = self.children(memory_id)
        while stack:
            memory = stack.pop(0)
            if memory.id in seen:
                continue
            seen.add(memory.id)
            ordered.append(memory)
            stack.extend(self.children(memory.id))
        return ordered

    def lineage(self, memory_id: str) -> dict[str, Any]:
        memory = self.get(memory_id)
        parents = [self.get(parent_id).to_dict() for parent_id in memory.parents if self._exists(parent_id)]
        descendants = [child.to_dict() for child in self.descendants(memory_id)]
        return {
            "memory": memory.to_dict(),
            "parents": parents,
            "descendants": descendants,
        }

    def reject(self, memory_id: str, *, actor_id: str = "human", reason: str | None = None) -> MemoryRecord:
        self.init()
        memory = self.get(memory_id)
        self.conn.execute(
            "UPDATE memories SET status = 'deprecated', authority = 'none', updated_at = ? WHERE id = ?",
            (now_iso(), memory_id),
        )
        self._append_event(
            "REJECTED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={"id": memory_id, "previous_status": memory.status, "reason": reason},
        )
        self.conn.commit()
        return self.get(memory_id)

    def revoke(self, memory_id: str, *, actor_id: str = "human", reason: str | None = None) -> dict[str, Any]:
        self.init()
        root_memory = self.get(memory_id)
        affected = [root_memory] + self.descendants(memory_id)
        revoked_ids: list[str] = []
        for memory in affected:
            self.conn.execute(
                "UPDATE memories SET status = 'revoked', authority = 'none', updated_at = ? WHERE id = ?",
                (now_iso(), memory.id),
            )
            revoked_ids.append(memory.id)
        self._append_event(
            "REVOKED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={
                "id": memory_id,
                "reason": reason,
                "revoked_ids": revoked_ids,
                "descendant_count": len(revoked_ids) - 1,
            },
        )
        self.conn.commit()
        return {
            "memory_id": memory_id,
            "reason": reason,
            "revoked_ids": revoked_ids,
            "descendant_count": len(revoked_ids) - 1,
        }

    def promote(self, memory_id: str, *, actor_id: str = "human") -> MemoryRecord:
        self.init()
        memory = self.get(memory_id)
        authority = "policy" if memory.type == "policy" else max_authority(memory.authority, "medium")
        self.conn.execute(
            "UPDATE memories SET status = 'active', trust = ?, authority = ?, updated_at = ? WHERE id = ?",
            (max(memory.trust, 0.9), authority, now_iso(), memory_id),
        )
        self._append_event(
            "PROMOTED",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={"id": memory_id, "authority": authority},
        )
        self.conn.commit()
        return self.get(memory_id)

    def forget(self, memory_id: str, *, actor_id: str = "human") -> None:
        self.init()
        memory = self.get(memory_id)
        self.conn.execute(
            "UPDATE memories SET status = 'forgotten', updated_at = ? WHERE id = ?",
            (now_iso(), memory_id),
        )
        self._append_event(
            "FORGOTTEN",
            actor_id=actor_id,
            memory_id=memory_id,
            payload={"id": memory_id, "content_hash": memory.content_hash},
        )
        self.conn.commit()

    def inject(self, task: str, *, agent_id: str, risk: str, scope: str | None = None) -> dict[str, Any]:
        self.init()
        search_result = self.search_with_meta(task, scope=scope, include_quarantined=True)
        candidates = search_result["memories"]
        injected: list[MemoryRecord] = []
        withheld: list[dict[str, str]] = []
        policy_checks: list[str] = []
        policy_decisions: list[dict[str, str]] = []
        policy_config = load_policy_config(self.policy_path or default_policy_path())
        for memory in candidates:
            decision = decide_memory(memory, risk=risk, config=policy_config)
            policy_decisions.append(decision.to_dict())
            if decision.decision == "withhold":
                withheld.append({"memory_id": memory.id, "reason": decision.reason, "rule": decision.rule})
                continue
            injected.append(memory)
            if memory.type == "policy":
                policy_checks.append(memory.id)
        action_id = "act_" + uuid.uuid4().hex[:16]
        root = self.current_merkle_root()
        memory_tree = self.memory_tree(candidates, scope="retrieved")
        injected_memory_proofs = {
            memory.id: memory_tree["proofs"][memory.id]
            for memory in injected
            if memory.id in memory_tree["proofs"]
        }
        receipt = {
            "receipt_schema": RECEIPT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "action_id": action_id,
            "agent_id": agent_id,
            "task": task,
            "task_hash": sha256_text(task),
            "risk": risk,
            "retrieved_memory_ids": [m.id for m in candidates],
            "retrieval": {
                "query": search_result["query"],
                "fts_query": search_result["fts_query"],
                "search_mode": search_result["search_mode"],
            },
            "injected_memory_ids": [m.id for m in injected],
            "withheld": withheld,
            "policy_checks": policy_checks,
            "policy_engine": POLICY_ENGINE,
            "policy_decisions": policy_decisions,
            "memory_tree": memory_tree,
            "injected_memory_proofs": injected_memory_proofs,
            "merkle_root": root,
            "created_at": now_iso(),
        }
        self.conn.execute(
            """
            INSERT INTO receipts (
              action_id, receipt_schema, hash_alg, merkle_alg, agent_id, task, task_hash, risk, retrieved_ids_json,
              retrieval_json, injected_ids_json, withheld_json, policy_checks_json, memory_tree_json, merkle_root, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                RECEIPT_SCHEMA,
                HASH_ALG,
                MERKLE_ALG,
                agent_id,
                task,
                receipt["task_hash"],
                risk,
                stable_json(receipt["retrieved_memory_ids"]),
                stable_json(receipt["retrieval"]),
                stable_json(receipt["injected_memory_ids"]),
                stable_json(withheld),
                stable_json(policy_checks),
                stable_json(memory_tree),
                root,
                receipt["created_at"],
            ),
        )
        self._append_event(
            "INJECTED",
            actor_id=agent_id,
            action_id=action_id,
            payload=receipt,
        )
        self.conn.commit()
        receipt["memories"] = [m.to_dict() for m in injected]
        return receipt

    def why(self, action_id: str) -> dict[str, Any]:
        self.init()
        row = self.conn.execute("SELECT * FROM receipts WHERE action_id = ?", (action_id,)).fetchone()
        if row is None:
            raise KeyError(f"action receipt not found: {action_id}")
        injected_ids = json.loads(row["injected_ids_json"])
        retrieved_ids = json.loads(row["retrieved_ids_json"])
        withheld = json.loads(row["withheld_json"])
        memory_tree = json.loads(row["memory_tree_json"] or "{}")
        injected_memory_proofs = {
            memory_id: memory_tree.get("proofs", {}).get(memory_id)
            for memory_id in injected_ids
            if memory_tree.get("proofs", {}).get(memory_id)
        }
        return {
            "receipt_schema": row["receipt_schema"],
            "hash_alg": row["hash_alg"],
            "merkle_alg": row["merkle_alg"],
            "action_id": row["action_id"],
            "agent_id": row["agent_id"],
            "task": row["task"],
            "task_hash": row["task_hash"],
            "risk": row["risk"],
            "retrieved_memory_ids": retrieved_ids,
            "injected_memory_ids": injected_ids,
            "withheld_memory_ids": [item["memory_id"] for item in withheld],
            "injected": [self.get(mid).to_dict() for mid in injected_ids],
            "withheld": withheld,
            "policy_checks": json.loads(row["policy_checks_json"]),
            "policy_engine": POLICY_ENGINE,
            "retrieval": json.loads(row["retrieval_json"]),
            "memory_tree": memory_tree,
            "injected_memory_proofs": injected_memory_proofs,
            "merkle_root": row["merkle_root"],
            "created_at": row["created_at"],
        }

    def receipt(self, action_id: str) -> dict[str, Any]:
        return self.why(action_id)

    def receipt_bundle(self, action_id: str) -> dict[str, Any]:
        self.init()
        receipt = self.why(action_id)
        action_row = self.conn.execute(
            "SELECT seq FROM events WHERE action_id = ? ORDER BY seq LIMIT 1",
            (action_id,),
        ).fetchone()
        if action_row is None:
            raise KeyError(f"action event not found: {action_id}")
        event_rows = self.conn.execute(
            """
            SELECT *
            FROM events
            WHERE seq < ?
            ORDER BY seq
            """,
            (action_row["seq"],),
        ).fetchall()
        events = [
            {
                "seq": row["seq"],
                "event_schema": EVENT_SCHEMA,
                "event_type": row["event_type"],
                "memory_id": row["memory_id"],
                "action_id": row["action_id"],
                "actor_id": row["actor_id"],
                "payload_json": row["payload_json"],
                "payload_hash": row["payload_hash"],
                "prev_event_hash": row["prev_event_hash"],
                "event_hash": row["event_hash"],
                "merkle_root": row["merkle_root"],
                "created_at": row["created_at"],
            }
            for row in event_rows
        ]
        event_hashes = [event["event_hash"] for event in events]
        bundle = {
            "bundle_schema": BUNDLE_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "created_at": now_iso(),
            "action_id": action_id,
            "receipt": receipt,
            "supporting_memory_ids": receipt["retrieved_memory_ids"],
            "supporting_memories": [self.get(mid).to_dict() for mid in receipt["retrieved_memory_ids"] if self._exists(mid)],
            "supporting_events": events,
            "proof": {
                "event_count": len(events),
                "computed_merkle_root": merkle_root(event_hashes),
                "receipt_merkle_root": receipt["merkle_root"],
                "memory_tree_root": receipt.get("memory_tree", {}).get("root"),
                "memory_tree_verified": self.verify_memory_tree(receipt.get("memory_tree", {}))
                if receipt.get("memory_tree")
                else None,
                "verified": merkle_root(event_hashes) == receipt["merkle_root"],
            },
        }
        bundle["bundle_hash"] = sha256_text(stable_json(bundle))
        return bundle

    def verify_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        without_hash = dict(bundle)
        without_hash.pop("bundle_hash", None)
        computed_bundle_hash = sha256_text(stable_json(without_hash))
        receipt = bundle.get("receipt", {})
        events = bundle.get("supporting_events", [])
        computed_merkle_root = merkle_root([event.get("event_hash", "") for event in events])
        proof = bundle.get("proof", {})
        result = {
            "ok": True,
            "bundle_schema": bundle.get("bundle_schema"),
            "action_id": bundle.get("action_id"),
            "bundle_hash": bundle.get("bundle_hash"),
            "computed_bundle_hash": computed_bundle_hash,
            "receipt_merkle_root": receipt.get("merkle_root"),
            "computed_merkle_root": computed_merkle_root,
            "event_count": len(events),
            "proof_event_count": proof.get("event_count") if isinstance(proof, dict) else None,
            "proof_verified": proof.get("verified") if isinstance(proof, dict) else None,
            "memory_tree_verified": self.verify_memory_tree(receipt.get("memory_tree", {})) if receipt.get("memory_tree") else None,
        }
        try:
            if bundle.get("bundle_schema") != BUNDLE_SCHEMA:
                raise ValueError("unsupported bundle schema")
            if bundle.get("hash_alg") != HASH_ALG:
                raise ValueError("unsupported bundle hash algorithm")
            if bundle.get("merkle_alg") != MERKLE_ALG:
                raise ValueError("unsupported bundle merkle algorithm")
            if not isinstance(bundle.get("bundle_hash"), str):
                raise ValueError("bundle missing bundle_hash")
            if computed_bundle_hash != bundle["bundle_hash"]:
                raise ValueError("bundle_hash mismatch")
            if bundle.get("action_id") != receipt.get("action_id"):
                raise ValueError("bundle action_id mismatch")
            if computed_merkle_root != receipt.get("merkle_root"):
                raise ValueError("bundle merkle_root mismatch")
            if not isinstance(proof, dict):
                raise ValueError("bundle missing proof")
            if proof.get("computed_merkle_root") != computed_merkle_root:
                raise ValueError("bundle proof computed_merkle_root mismatch")
            if proof.get("receipt_merkle_root") != receipt.get("merkle_root"):
                raise ValueError("bundle proof receipt_merkle_root mismatch")
            if proof.get("event_count") != len(events):
                raise ValueError("bundle proof event_count mismatch")
            if proof.get("verified") is not True:
                raise ValueError("bundle proof is not verified")
            if receipt.get("memory_tree") and not self.verify_memory_tree(receipt["memory_tree"]):
                raise ValueError("bundle memory_tree verification failed")
            if receipt.get("memory_tree") and proof.get("memory_tree_verified") is not True:
                raise ValueError("bundle proof memory_tree_verified mismatch")
        except (KeyError, ValueError) as exc:
            result["ok"] = False
            result["error"] = str(exc)
        return result

    def snapshot(self) -> dict[str, Any]:
        self.init()
        memories = [
            MemoryRecord.from_row(row).to_dict()
            for row in self.conn.execute("SELECT * FROM memories ORDER BY created_at, id").fetchall()
        ]
        events = []
        for row in self.conn.execute("SELECT * FROM events ORDER BY seq").fetchall():
            events.append(
                {
                    "seq": row["seq"],
                    "event_schema": EVENT_SCHEMA,
                    "event_type": row["event_type"],
                    "memory_id": row["memory_id"],
                    "action_id": row["action_id"],
                    "actor_id": row["actor_id"],
                    "payload_json": row["payload_json"],
                    "payload_hash": row["payload_hash"],
                    "prev_event_hash": row["prev_event_hash"],
                    "event_hash": row["event_hash"],
                    "merkle_root": row["merkle_root"],
                    "created_at": row["created_at"],
                }
            )
        receipts = [
            self.why(row["action_id"])
            for row in self.conn.execute("SELECT action_id FROM receipts ORDER BY created_at, action_id").fetchall()
        ]
        payload = {
            "snapshot_schema": SNAPSHOT_SCHEMA,
            "hash_alg": HASH_ALG,
            "merkle_alg": MERKLE_ALG,
            "created_at": now_iso(),
            "db_path": str(self.db_path),
            "merkle_root": self.current_merkle_root(),
            "memory_count": len(memories),
            "event_count": len(events),
            "receipt_count": len(receipts),
            "memories": memories,
            "events": events,
            "receipts": receipts,
        }
        payload["snapshot_hash"] = sha256_text(stable_json(payload))
        return payload

    def restore_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        self.init()
        self._validate_snapshot(snapshot)
        existing = self.conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM memories) AS memory_count,
              (SELECT COUNT(*) FROM events) AS event_count,
              (SELECT COUNT(*) FROM receipts) AS receipt_count
            """
        ).fetchone()
        if existing["memory_count"] or existing["event_count"] or existing["receipt_count"]:
            raise ValueError("restore requires an empty memory store")

        for memory in snapshot["memories"]:
            self.conn.execute(
                """
                INSERT INTO memories (
                  id, type, content, scope, source_kind, trust, authority, status,
                  parents_json, labels_json, created_at, updated_at, expires_at, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory["id"],
                    memory["type"],
                    memory["content"],
                    memory["scope"],
                    memory["source_kind"],
                    memory["trust"],
                    memory["authority"],
                    memory["status"],
                    stable_json(memory.get("parents", [])),
                    stable_json(memory.get("labels", [])),
                    memory["created_at"],
                    memory["updated_at"],
                    memory.get("expires_at"),
                    memory["content_hash"],
                ),
            )
            self.conn.execute(
                "INSERT INTO memories_fts (id, content, labels) VALUES (?, ?, ?)",
                (memory["id"], memory["content"], " ".join(memory.get("labels", []))),
            )

        for event in snapshot["events"]:
            self.conn.execute(
                """
                INSERT INTO events (
                  seq, event_type, memory_id, action_id, actor_id, payload_json, payload_hash,
                  prev_event_hash, event_hash, merkle_root, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["seq"],
                    event["event_type"],
                    event.get("memory_id"),
                    event.get("action_id"),
                    event["actor_id"],
                    event["payload_json"],
                    event["payload_hash"],
                    event["prev_event_hash"],
                    event["event_hash"],
                    event["merkle_root"],
                    event["created_at"],
                ),
            )

        for receipt in snapshot["receipts"]:
            self.conn.execute(
                """
                INSERT INTO receipts (
                  action_id, receipt_schema, hash_alg, merkle_alg, agent_id, task, task_hash, risk, retrieved_ids_json,
                  retrieval_json, injected_ids_json, withheld_json, policy_checks_json, memory_tree_json, merkle_root, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt["action_id"],
                    receipt["receipt_schema"],
                    receipt["hash_alg"],
                    receipt["merkle_alg"],
                    receipt["agent_id"],
                    receipt["task"],
                    receipt["task_hash"],
                    receipt["risk"],
                    stable_json(receipt["retrieved_memory_ids"]),
                    stable_json(receipt.get("retrieval", {})),
                    stable_json(receipt["injected_memory_ids"]),
                    stable_json(receipt.get("withheld", [])),
                    stable_json(receipt["policy_checks"]),
                    stable_json(receipt.get("memory_tree", {})),
                    receipt["merkle_root"],
                    receipt["created_at"],
                ),
            )

        self.conn.commit()
        return {
            "ok": True,
            "snapshot_hash": snapshot["snapshot_hash"],
            "merkle_root": self.current_merkle_root(),
            "memory_count": snapshot["memory_count"],
            "event_count": snapshot["event_count"],
            "receipt_count": snapshot["receipt_count"],
        }

    def verify_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        without_hash = dict(snapshot)
        without_hash.pop("snapshot_hash", None)
        computed_snapshot_hash = sha256_text(stable_json(without_hash))
        events = snapshot.get("events", [])
        computed_merkle_root = merkle_root([event.get("event_hash", "") for event in events])
        result = {
            "ok": True,
            "snapshot_schema": snapshot.get("snapshot_schema"),
            "snapshot_hash": snapshot.get("snapshot_hash"),
            "computed_snapshot_hash": computed_snapshot_hash,
            "merkle_root": snapshot.get("merkle_root"),
            "computed_merkle_root": computed_merkle_root,
            "memory_count": snapshot.get("memory_count"),
            "event_count": snapshot.get("event_count"),
            "receipt_count": snapshot.get("receipt_count"),
        }
        try:
            self._validate_snapshot(snapshot)
        except (KeyError, ValueError) as exc:
            result["ok"] = False
            result["error"] = str(exc)
        return result

    def _validate_snapshot(self, snapshot: dict[str, Any]) -> None:
        if snapshot.get("snapshot_schema") != SNAPSHOT_SCHEMA:
            raise ValueError("unsupported snapshot schema")
        if snapshot.get("hash_alg") != HASH_ALG:
            raise ValueError("unsupported snapshot hash algorithm")
        if snapshot.get("merkle_alg") != MERKLE_ALG:
            raise ValueError("unsupported snapshot merkle algorithm")
        snapshot_hash = snapshot.get("snapshot_hash")
        if not isinstance(snapshot_hash, str):
            raise ValueError("snapshot missing snapshot_hash")
        without_hash = dict(snapshot)
        without_hash.pop("snapshot_hash", None)
        if sha256_text(stable_json(without_hash)) != snapshot_hash:
            raise ValueError("snapshot_hash mismatch")
        events = snapshot.get("events", [])
        event_hashes = [event["event_hash"] for event in events]
        if merkle_root(event_hashes) != snapshot.get("merkle_root"):
            raise ValueError("snapshot merkle_root mismatch")
        if snapshot.get("memory_count") != len(snapshot.get("memories", [])):
            raise ValueError("snapshot memory_count mismatch")
        if snapshot.get("event_count") != len(events):
            raise ValueError("snapshot event_count mismatch")
        if snapshot.get("receipt_count") != len(snapshot.get("receipts", [])):
            raise ValueError("snapshot receipt_count mismatch")

    def verify(self, action_id: str) -> bool:
        self.init()
        row = self.conn.execute("SELECT merkle_root, memory_tree_json FROM receipts WHERE action_id = ?", (action_id,)).fetchone()
        if row is None:
            raise KeyError(f"action receipt not found: {action_id}")
        event_ok = row["merkle_root"] == self.current_merkle_root(before_action_id=action_id)
        memory_tree = json.loads(row["memory_tree_json"] or "{}")
        memory_tree_ok = True if not memory_tree else self.verify_memory_tree(memory_tree)
        return event_ok and memory_tree_ok

    def verify_memory_tree(self, tree: dict[str, Any]) -> bool:
        try:
            if tree.get("schema") != MEMORY_TREE_SCHEMA:
                return False
            leaves = tree.get("leaves")
            if not isinstance(leaves, list):
                return False
            leaf_hashes: list[str] = []
            for leaf in leaves:
                if not isinstance(leaf, dict):
                    return False
                material = leaf.get("material")
                if not isinstance(material, dict):
                    return False
                leaf_hash = leaf.get("leaf_hash")
                if leaf_hash != sha256_text(stable_json(material)):
                    return False
                leaf_hashes.append(leaf_hash)
            root = tree.get("root")
            if root != merkle_root(leaf_hashes):
                return False
            proofs = tree.get("proofs")
            if not isinstance(proofs, dict):
                return False
            for leaf in leaves:
                memory_id = leaf.get("memory_id")
                proof = proofs.get(memory_id)
                if not isinstance(proof, dict):
                    return False
                if proof.get("root") != root:
                    return False
                if proof.get("leaf_hash") != leaf.get("leaf_hash"):
                    return False
                proof_path = proof.get("proof")
                if not isinstance(proof_path, list):
                    return False
                if not verify_merkle_proof(leaf["leaf_hash"], proof_path, root):
                    return False
            return True
        except (KeyError, TypeError):
            return False

    def current_merkle_root(self, *, before_action_id: str | None = None) -> str:
        if before_action_id is None:
            rows = self.conn.execute("SELECT event_hash FROM events ORDER BY seq").fetchall()
        else:
            action_row = self.conn.execute(
                "SELECT seq FROM events WHERE action_id = ? ORDER BY seq LIMIT 1",
                (before_action_id,),
            ).fetchone()
            max_seq = action_row["seq"] - 1 if action_row else 0
            rows = self.conn.execute("SELECT event_hash FROM events WHERE seq <= ? ORDER BY seq", (max_seq,)).fetchall()
        return merkle_root([row["event_hash"] for row in rows])

    def _append_event(
        self,
        event_type: str,
        *,
        actor_id: str,
        payload: dict[str, Any],
        memory_id: str | None = None,
        action_id: str | None = None,
    ) -> None:
        prev_row = self.conn.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev_row["event_hash"] if prev_row else sha256_text("genesis")
        payload_json = stable_json(payload)
        payload_hash = sha256_text(payload_json)
        created_at = now_iso()
        event_material = stable_json(
            {
                "event_schema": EVENT_SCHEMA,
                "hash_alg": HASH_ALG,
                "event_type": event_type,
                "memory_id": memory_id,
                "action_id": action_id,
                "actor_id": actor_id,
                "payload_hash": payload_hash,
                "prev_event_hash": prev_hash,
                "created_at": created_at,
            }
        )
        event_hash = sha256_text(event_material)
        existing_hashes = [row["event_hash"] for row in self.conn.execute("SELECT event_hash FROM events ORDER BY seq")]
        root = merkle_root(existing_hashes + [event_hash])
        self.conn.execute(
            """
            INSERT INTO events (
              event_type, memory_id, action_id, actor_id, payload_json, payload_hash,
              prev_event_hash, event_hash, merkle_root, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_type, memory_id, action_id, actor_id, payload_json, payload_hash, prev_hash, event_hash, root, created_at),
        )

    @staticmethod
    def _default_trust(source_kind: str) -> float:
        return {
            "human": 0.95,
            "system": 0.9,
            "tool": 0.75,
            "document": 0.65,
            "agent": 0.5,
            "import": 0.45,
        }.get(source_kind, 0.4)

    @staticmethod
    def _default_authority(memory_type: str, source_kind: str) -> str:
        if memory_type == "policy":
            return "policy" if source_kind in {"human", "system"} else "none"
        if memory_type == "procedural":
            return "medium" if source_kind in {"human", "system"} else "low"
        if memory_type == "semantic":
            return "medium" if source_kind in {"human", "system", "tool"} else "low"
        return "low"

    @staticmethod
    def _default_status(source_kind: str, memory_type: str) -> str:
        if memory_type == "policy" and source_kind not in {"human", "system"}:
            return "quarantined"
        if source_kind in {"agent", "tool", "document", "import"}:
            return "quarantined"
        return "active"
