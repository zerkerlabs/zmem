from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import struct
from datetime import datetime, timezone
from typing import Any, Mapping

from . import retrieval_providers


DENSE_INDEX_SCHEMA = "zerker.dense_index.v1"
DENSE_HYBRID_SCHEMA = "zerker.dense_hybrid_retrieval.v1"
DEFAULT_DENSE_PROVIDER_ID = "local:fastembed"
DEFAULT_DENSE_LIMIT = 20
DEFAULT_DENSE_MIN_SCORE = 0.35


def dense_hybrid_retrieval_config(
    *,
    provider_id: str = DEFAULT_DENSE_PROVIDER_ID,
    limit: int = DEFAULT_DENSE_LIMIT,
    min_score: float = DEFAULT_DENSE_MIN_SCORE,
) -> dict[str, Any]:
    return {
        "dense": {
            "enabled": True,
            "provider_id": provider_id,
            "limit": limit,
            "min_score": min_score,
            "fusion": "reciprocal_rank_fusion_v1",
        }
    }


def ensure_dense_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS memory_embeddings (
          memory_id TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          provider_id TEXT NOT NULL,
          model_id TEXT NOT NULL,
          config_hash TEXT NOT NULL,
          dimensions INTEGER NOT NULL,
          normalized INTEGER NOT NULL,
          model_digest TEXT,
          vector_blob BLOB NOT NULL,
          vector_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(memory_id, provider_id, model_id, config_hash),
          FOREIGN KEY(memory_id) REFERENCES memories(id)
        );

        CREATE INDEX IF NOT EXISTS memory_embeddings_lookup_idx
          ON memory_embeddings(provider_id, model_id, config_hash, memory_id);
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(memory_embeddings)")}
    if "model_digest" not in columns:
        conn.execute("ALTER TABLE memory_embeddings ADD COLUMN model_digest TEXT")


def index_embeddings(
    conn: sqlite3.Connection,
    *,
    provider_config: Mapping[str, Any],
    provider_id: str = DEFAULT_DENSE_PROVIDER_ID,
    scope: str | None = None,
    allow_model_download: bool = False,
    force: bool = False,
    batch_size: int | None = None,
) -> dict[str, Any]:
    ensure_dense_schema(conn)
    config = retrieval_providers.normalize_retrieval_provider_config(provider_config)
    entry = retrieval_providers.resolve_embedding_provider(config, provider_id)
    config_hash = retrieval_providers.retrieval_provider_config_hash(config)
    model_id = entry.model_id or provider_id
    rows = _eligible_memory_rows(conn, scope=scope, include_quarantined=True)
    pending = []
    for row in rows:
        cached = conn.execute(
            """
            SELECT content_hash
            FROM memory_embeddings
            WHERE memory_id = ? AND provider_id = ? AND model_id = ? AND config_hash = ?
            """,
            (row["id"], provider_id, model_id, config_hash),
        ).fetchone()
        if force or cached is None or cached["content_hash"] != row["content_hash"]:
            pending.append(row)

    resolved_batch_size = batch_size or int((entry.settings or {}).get("batch_size", 64))
    if resolved_batch_size < 1:
        raise ValueError("embedding batch size must be at least 1")
    indexed_count = 0
    model_download_observed = False
    observed_model_digest = None
    if not pending and allow_model_download and not retrieval_providers.fastembed_model_cached(entry):
        readiness = retrieval_providers.embed_texts(
            entry,
            ["zmem dense model readiness"],
            input_type="document",
            allow_model_download=True,
        )
        model_download_observed = readiness.network_call
        observed_model_digest = readiness.model_digest
    for offset in range(0, len(pending), resolved_batch_size):
        batch = pending[offset : offset + resolved_batch_size]
        result = retrieval_providers.embed_texts(
            entry,
            [str(row["content"]) for row in batch],
            input_type="document",
            allow_model_download=allow_model_download,
        )
        if len(result.vectors) != len(batch):
            raise RuntimeError("embedding provider returned the wrong vector count")
        model_id = result.model_id
        model_download_observed = bool(model_download_observed or result.network_call)
        observed_model_digest = result.model_digest
        created_at = _now_iso()
        for row, vector, vector_hash in zip(batch, result.vectors, result.vector_hashes):
            conn.execute(
                """
                INSERT INTO memory_embeddings (
                  memory_id, content_hash, provider_id, model_id, config_hash,
                  dimensions, normalized, model_digest, vector_blob, vector_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id, provider_id, model_id, config_hash) DO UPDATE SET
                  content_hash = excluded.content_hash,
                  dimensions = excluded.dimensions,
                  normalized = excluded.normalized,
                  model_digest = excluded.model_digest,
                  vector_blob = excluded.vector_blob,
                  vector_hash = excluded.vector_hash,
                  created_at = excluded.created_at
                """,
                (
                    row["id"],
                    row["content_hash"],
                    provider_id,
                    model_id,
                    config_hash,
                    len(vector),
                    int(result.normalized),
                    result.model_digest,
                    sqlite3.Binary(_pack_vector(vector)),
                    vector_hash,
                    created_at,
                ),
            )
            indexed_count += 1
        conn.commit()

    status = embedding_index_status(
        conn,
        provider_config=config,
        provider_id=provider_id,
        scope=scope,
    )
    return {
        **status,
        "model_digest": status.get("model_digest") or observed_model_digest,
        "indexed_count": indexed_count,
        "skipped_current_count": len(rows) - len(pending),
        "force": force,
        "model_download_allowed": allow_model_download,
        "model_download_observed": model_download_observed,
    }


def embedding_index_status(
    conn: sqlite3.Connection,
    *,
    provider_config: Mapping[str, Any],
    provider_id: str = DEFAULT_DENSE_PROVIDER_ID,
    scope: str | None = None,
) -> dict[str, Any]:
    ensure_dense_schema(conn)
    config = retrieval_providers.normalize_retrieval_provider_config(provider_config)
    entry = retrieval_providers.resolve_embedding_provider(config, provider_id)
    config_hash = retrieval_providers.retrieval_provider_config_hash(config)
    model_id = entry.model_id or provider_id
    rows = _eligible_memory_rows(conn, scope=scope, include_quarantined=True)
    current_rows = conn.execute(
        """
        SELECT e.memory_id, e.content_hash, e.vector_hash, e.model_digest
        FROM memory_embeddings AS e
        JOIN memories AS m ON m.id = e.memory_id AND m.content_hash = e.content_hash
        WHERE e.provider_id = ? AND e.model_id = ? AND e.config_hash = ?
          AND m.status IN ('active', 'quarantined', 'proposed')
        """,
        (provider_id, model_id, config_hash),
    ).fetchall()
    eligible_ids = {str(row["id"]) for row in rows}
    indexed_rows = [row for row in current_rows if str(row["memory_id"]) in eligible_ids]
    manifest = [
        {
            "memory_id": str(row["memory_id"]),
            "content_hash": str(row["content_hash"]),
            "vector_hash": str(row["vector_hash"]),
            "model_digest": str(row["model_digest"]) if row["model_digest"] else None,
        }
        for row in sorted(indexed_rows, key=lambda item: str(item["memory_id"]))
    ]
    return {
        "ok": True,
        "schema": DENSE_INDEX_SCHEMA,
        "provider_id": provider_id,
        "model_id": model_id,
        "config_hash": config_hash,
        "scope": scope,
        "eligible_memory_count": len(rows),
        "indexed_memory_count": len(indexed_rows),
        "missing_or_stale_count": len(rows) - len(indexed_rows),
        "coverage": round(len(indexed_rows) / len(rows), 6) if rows else 1.0,
        "index_hash": _digest_json(manifest),
        "model_digest": next(
            (str(row["model_digest"]) for row in indexed_rows if row["model_digest"]),
            None,
        ),
        "model_cached": retrieval_providers.fastembed_model_cached(entry),
    }


def dense_candidates(
    conn: sqlite3.Connection,
    query: str,
    *,
    provider_config: Mapping[str, Any],
    provider_id: str = DEFAULT_DENSE_PROVIDER_ID,
    scope: str | None = None,
    include_quarantined: bool = False,
    limit: int = DEFAULT_DENSE_LIMIT,
    min_score: float = DEFAULT_DENSE_MIN_SCORE,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("dense candidate limit must be at least 1")
    ensure_dense_schema(conn)
    config = retrieval_providers.normalize_retrieval_provider_config(provider_config)
    entry = retrieval_providers.resolve_embedding_provider(config, provider_id)
    config_hash = retrieval_providers.retrieval_provider_config_hash(config)
    query_result = retrieval_providers.embed_texts(
        entry,
        [query],
        input_type="query",
        allow_model_download=False,
    )
    if len(query_result.vectors) != 1:
        raise RuntimeError("embedding provider returned the wrong query vector count")
    model_id = query_result.model_id
    rows = _current_embedding_rows(
        conn,
        provider_id=provider_id,
        model_id=model_id,
        config_hash=config_hash,
        model_digest=query_result.model_digest,
        scope=scope,
        include_quarantined=include_quarantined,
    )
    query_vector = query_result.vectors[0]
    indexed_model_digest = next((str(row["model_digest"]) for row in rows if row["model_digest"]), None)
    scored = []
    for row in rows:
        vector = _unpack_vector(row["vector_blob"], int(row["dimensions"]))
        score = _cosine_similarity(query_vector, vector)
        if score < min_score:
            continue
        scored.append(
            {
                "memory_id": str(row["memory_id"]),
                "score": round(score, 6),
                "vector_hash": str(row["vector_hash"]),
                "content_hash": str(row["content_hash"]),
            }
        )
    scored.sort(key=lambda item: (-float(item["score"]), str(item["memory_id"])))
    selected = scored[: max(0, limit)]
    eligible_count = len(_eligible_memory_rows(conn, scope=scope, include_quarantined=include_quarantined))
    return {
        "schema": DENSE_HYBRID_SCHEMA,
        "provider_id": provider_id,
        "model_id": model_id,
        "model_digest": indexed_model_digest or query_result.model_digest,
        "config_hash": config_hash,
        "query_vector_hash": query_result.vector_hashes[0],
        "network_call": query_result.network_call,
        "limit": limit,
        "min_score": min_score,
        "eligible_memory_count": eligible_count,
        "indexed_candidate_count": len(rows),
        "index_coverage": round(len(rows) / eligible_count, 6) if eligible_count else 1.0,
        "ranked_candidates": selected,
        "ranked_candidate_ids": [item["memory_id"] for item in selected],
    }


def _eligible_memory_rows(
    conn: sqlite3.Connection,
    *,
    scope: str | None,
    include_quarantined: bool,
) -> list[sqlite3.Row]:
    statuses = "('active', 'quarantined', 'proposed')" if include_quarantined else "('active')"
    scope_sql = ""
    params: list[Any] = []
    if scope:
        scope_sql = "AND (scope = ? OR scope = 'global')"
        params.append(scope)
    return conn.execute(
        f"""
        SELECT id, content, content_hash, status, scope
        FROM memories
        WHERE status IN {statuses}
          {scope_sql}
        ORDER BY id
        """,
        params,
    ).fetchall()


def _current_embedding_rows(
    conn: sqlite3.Connection,
    *,
    provider_id: str,
    model_id: str,
    config_hash: str,
    model_digest: str | None,
    scope: str | None,
    include_quarantined: bool,
) -> list[sqlite3.Row]:
    statuses = "('active', 'quarantined', 'proposed')" if include_quarantined else "('active')"
    scope_sql = ""
    model_digest_sql = ""
    params: list[Any] = [provider_id, model_id, config_hash]
    if model_digest:
        model_digest_sql = "AND e.model_digest = ?"
        params.append(model_digest)
    if scope:
        scope_sql = "AND (m.scope = ? OR m.scope = 'global')"
        params.append(scope)
    return conn.execute(
        f"""
        SELECT e.memory_id, e.content_hash, e.dimensions, e.model_digest, e.vector_blob, e.vector_hash
        FROM memory_embeddings AS e
        JOIN memories AS m ON m.id = e.memory_id AND m.content_hash = e.content_hash
        WHERE e.provider_id = ? AND e.model_id = ? AND e.config_hash = ?
          {model_digest_sql}
          AND m.status IN {statuses}
          {scope_sql}
        ORDER BY e.memory_id
        """,
        params,
    ).fetchall()


def _pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *(float(value) for value in vector))


def _unpack_vector(blob: bytes, dimensions: int) -> list[float]:
    expected_size = dimensions * 4
    if len(blob) != expected_size:
        raise ValueError("stored embedding vector has invalid dimensions")
    return list(struct.unpack(f"<{dimensions}f", blob))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _digest_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
