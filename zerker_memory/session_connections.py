from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


SESSION_INVITATION_SCHEMA = "zerker.session_invitation.v1"
SESSION_ATTACHMENT_SCHEMA = "zerker.session_attachment.v1"
DEFAULT_INVITATION_TTL_SECONDS = 600
MAX_INVITATION_TTL_SECONDS = 3600
LIVE_SESSION_WINDOW_SECONDS = 120


def ensure_session_connection_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS session_invitations (
          invitation_id TEXT PRIMARY KEY,
          code_hash TEXT NOT NULL UNIQUE,
          agent_id TEXT NOT NULL,
          scope TEXT NOT NULL,
          room_id TEXT,
          session_label TEXT,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          consumed_at TEXT,
          consumed_attachment_id TEXT
        );

        CREATE INDEX IF NOT EXISTS session_invitations_agent_created_idx
          ON session_invitations(agent_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS session_attachments (
          attachment_id TEXT PRIMARY KEY,
          invitation_id TEXT NOT NULL UNIQUE,
          agent_id TEXT NOT NULL,
          connection_id TEXT NOT NULL,
          client_session_id TEXT,
          session_label TEXT,
          scope TEXT NOT NULL,
          room_id TEXT,
          identity_assurance TEXT NOT NULL,
          state TEXT NOT NULL,
          attached_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          detached_at TEXT,
          detached_by TEXT,
          detach_reason TEXT,
          FOREIGN KEY(invitation_id) REFERENCES session_invitations(invitation_id)
        );

        CREATE INDEX IF NOT EXISTS session_attachments_connection_state_idx
          ON session_attachments(connection_id, state, last_seen_at DESC);

        CREATE INDEX IF NOT EXISTS session_attachments_agent_state_idx
          ON session_attachments(agent_id, state, last_seen_at DESC);
        """
    )


def create_session_invitation(
    connection: sqlite3.Connection,
    *,
    agent_id: str,
    scope: str = "project",
    room_id: str | None = None,
    session_label: str | None = None,
    ttl_seconds: int = DEFAULT_INVITATION_TTL_SECONDS,
    now: datetime | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    ensure_session_connection_schema(connection)
    agent_id = _identifier(agent_id, label="agent id", maximum=128, forbid_slash=True)
    scope = _identifier(scope, label="scope", maximum=256)
    room_id = _optional_identifier(room_id, label="room id", maximum=256)
    session_label = _optional_identifier(session_label, label="session label", maximum=120)
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise ValueError("invitation ttl must be an integer number of seconds")
    if ttl_seconds < 30 or ttl_seconds > MAX_INVITATION_TTL_SECONDS:
        raise ValueError(f"invitation ttl must be between 30 and {MAX_INVITATION_TTL_SECONDS} seconds")

    created = _as_utc(now)
    invitation_code = code or f"zma_{secrets.token_urlsafe(24)}"
    if not invitation_code.startswith("zma_") or len(invitation_code) < 20:
        raise ValueError("activation code must use the zma_ prefix and contain sufficient entropy")
    invitation_id = f"inv_{uuid.uuid4().hex}"
    expires = created + timedelta(seconds=ttl_seconds)
    connection.execute(
        """
        INSERT INTO session_invitations (
          invitation_id, code_hash, agent_id, scope, room_id, session_label,
          created_at, expires_at, consumed_at, consumed_attachment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (
            invitation_id,
            _code_hash(invitation_code),
            agent_id,
            scope,
            room_id,
            session_label,
            _format_time(created),
            _format_time(expires),
        ),
    )
    connection.commit()
    return {
        "schema": SESSION_INVITATION_SCHEMA,
        "invitation_id": invitation_id,
        "activation_code": invitation_code,
        "agent_id": agent_id,
        "scope": scope,
        "room_id": room_id,
        "session_label": session_label,
        "created_at": _format_time(created),
        "expires_at": _format_time(expires),
        "one_time": True,
        "room_membership_authority": "gateway" if room_id else None,
    }


def consume_session_invitation(
    connection: sqlite3.Connection,
    *,
    activation_code: str,
    agent_id: str,
    connection_id: str,
    client_session_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_session_connection_schema(connection)
    activation_code = _identifier(activation_code, label="activation code", maximum=256)
    agent_id = _identifier(agent_id, label="agent id", maximum=128, forbid_slash=True)
    connection_id = _identifier(connection_id, label="connection id", maximum=256)
    client_session_id = _optional_identifier(
        client_session_id,
        label="client session id",
        maximum=512,
    )
    attached = _as_utc(now)
    attachment_id = f"att_{uuid.uuid4().hex}"

    connection.execute("BEGIN IMMEDIATE")
    try:
        invitation = connection.execute(
            "SELECT * FROM session_invitations WHERE code_hash = ?",
            (_code_hash(activation_code),),
        ).fetchone()
        if invitation is None:
            raise ValueError("activation code is invalid")
        if invitation["consumed_at"] is not None:
            raise ValueError("activation code has already been used")
        if _parse_time(invitation["expires_at"]) <= attached:
            raise ValueError("activation code has expired")
        if invitation["agent_id"] != agent_id:
            raise ValueError(f"activation code is bound to agent {invitation['agent_id']}")

        identity_assurance = "client_asserted" if client_session_id else "connector_only"
        connection.execute(
            """
            INSERT INTO session_attachments (
              attachment_id, invitation_id, agent_id, connection_id, client_session_id,
              session_label, scope, room_id, identity_assurance, state,
              attached_at, last_seen_at, detached_at, detached_by, detach_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL, NULL, NULL)
            """,
            (
                attachment_id,
                invitation["invitation_id"],
                agent_id,
                connection_id,
                client_session_id,
                invitation["session_label"],
                invitation["scope"],
                invitation["room_id"],
                identity_assurance,
                _format_time(attached),
                _format_time(attached),
            ),
        )
        updated = connection.execute(
            """
            UPDATE session_invitations
            SET consumed_at = ?, consumed_attachment_id = ?
            WHERE invitation_id = ? AND consumed_at IS NULL
            """,
            (_format_time(attached), attachment_id, invitation["invitation_id"]),
        )
        if updated.rowcount != 1:
            raise ValueError("activation code has already been used")
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return get_session_attachment(connection, attachment_id, now=attached)


def touch_session_attachments(
    connection: sqlite3.Connection,
    *,
    connection_id: str,
    now: datetime | None = None,
) -> int:
    connection_id = _identifier(connection_id, label="connection id", maximum=256)
    result = connection.execute(
        """
        UPDATE session_attachments
        SET last_seen_at = ?
        WHERE connection_id = ? AND state = 'active'
        """,
        (_format_time(_as_utc(now)), connection_id),
    )
    connection.commit()
    return int(result.rowcount)


def get_session_attachment(
    connection: sqlite3.Connection,
    attachment_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_session_connection_schema(connection)
    attachment_id = _identifier(attachment_id, label="attachment id", maximum=128)
    row = connection.execute(
        "SELECT * FROM session_attachments WHERE attachment_id = ?",
        (attachment_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"session attachment not found: {attachment_id}")
    return _attachment_payload(row, now=_as_utc(now))


def list_session_attachments(
    connection: sqlite3.Connection,
    *,
    agent_id: str | None = None,
    connection_id: str | None = None,
    active_only: bool = False,
    limit: int = 50,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_session_connection_schema(connection)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 200:
        raise ValueError("session attachment limit must be between 1 and 200")
    clauses: list[str] = []
    values: list[Any] = []
    if agent_id is not None:
        clauses.append("agent_id = ?")
        values.append(_identifier(agent_id, label="agent id", maximum=128, forbid_slash=True))
    if connection_id is not None:
        clauses.append("connection_id = ?")
        values.append(_identifier(connection_id, label="connection id", maximum=256))
    if active_only:
        clauses.append("state = 'active'")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"SELECT * FROM session_attachments{where} ORDER BY last_seen_at DESC, attachment_id LIMIT ?",
        (*values, limit),
    ).fetchall()
    observed_at = _as_utc(now)
    attachments = [_attachment_payload(row, now=observed_at) for row in rows]
    return {
        "schema": "zerker.session_attachment_list.v1",
        "observed_at": _format_time(observed_at),
        "attachment_count": len(attachments),
        "live_count": sum(1 for item in attachments if item["presence"] == "live"),
        "idle_count": sum(1 for item in attachments if item["presence"] == "idle"),
        "detached_count": sum(1 for item in attachments if item["presence"] == "detached"),
        "attachments": attachments,
    }


def detach_session_attachment(
    connection: sqlite3.Connection,
    *,
    attachment_id: str,
    detached_by: str,
    reason: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_session_connection_schema(connection)
    attachment_id = _identifier(attachment_id, label="attachment id", maximum=128)
    detached_by = _identifier(detached_by, label="detached by", maximum=256)
    reason = _optional_identifier(reason, label="detach reason", maximum=512)
    existing = connection.execute(
        "SELECT * FROM session_attachments WHERE attachment_id = ?",
        (attachment_id,),
    ).fetchone()
    if existing is None:
        raise ValueError(f"session attachment not found: {attachment_id}")
    if existing["state"] == "active":
        detached_at = _format_time(_as_utc(now))
        connection.execute(
            """
            UPDATE session_attachments
            SET state = 'detached', detached_at = ?, detached_by = ?, detach_reason = ?
            WHERE attachment_id = ? AND state = 'active'
            """,
            (detached_at, detached_by, reason, attachment_id),
        )
        connection.commit()
    return get_session_attachment(connection, attachment_id, now=now)


def _attachment_payload(row: sqlite3.Row, *, now: datetime) -> dict[str, Any]:
    state = str(row["state"])
    if state == "detached":
        presence = "detached"
    else:
        seconds_since_seen = max(0, int((now - _parse_time(row["last_seen_at"])).total_seconds()))
        presence = "live" if seconds_since_seen <= LIVE_SESSION_WINDOW_SECONDS else "idle"
    return {
        "schema": SESSION_ATTACHMENT_SCHEMA,
        "attachment_id": row["attachment_id"],
        "agent_id": row["agent_id"],
        "connection_id": row["connection_id"],
        "client_session_id": row["client_session_id"],
        "session_label": row["session_label"],
        "scope": row["scope"],
        "room_id": row["room_id"],
        "identity_assurance": row["identity_assurance"],
        "state": state,
        "presence": presence,
        "attached_at": row["attached_at"],
        "last_seen_at": row["last_seen_at"],
        "detached_at": row["detached_at"],
        "detached_by": row["detached_by"],
        "detach_reason": row["detach_reason"],
        "room_membership_authority": "gateway" if row["room_id"] else None,
    }


def _identifier(value: str, *, label: str, maximum: int, forbid_slash: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{label} must be at most {maximum} characters")
    if "\x00" in normalized or "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{label} contains unsupported control characters")
    if forbid_slash and "/" in normalized:
        raise ValueError(f"{label} must be one URI path segment")
    return normalized


def _optional_identifier(value: str | None, *, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _identifier(value, label=label, maximum=maximum)


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _as_utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
