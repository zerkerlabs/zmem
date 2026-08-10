from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .store import MemoryRecord, _resolve_current_conflicts, authority_rank, now_iso, sha256_text


WORKSPACE_REGISTRY_SCHEMA = "zerker.workspace_registry.v1"
WORKSPACE_REGISTRY_ENV = "ZMEM_WORKSPACE_REGISTRY"
WORKSPACE_RESTORE_CONTINUITY_SCHEMA = "zerker.workspace_restore_continuity.v1"


def default_workspace_registry_path() -> Path:
    override = os.environ.get(WORKSPACE_REGISTRY_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".zmem" / "workspaces.json"


def normalize_path(path: Path | str, *, root: Path | None = None) -> str:
    candidate = Path(path).expanduser()
    if root is not None and not candidate.is_absolute():
        candidate = root / candidate
    return str(candidate.resolve(strict=False))


def workspace_id_for_root(root: Path | str) -> str:
    return "ws_" + sha256_text(normalize_path(root))[:16]


def empty_registry() -> dict[str, Any]:
    return {
        "schema": WORKSPACE_REGISTRY_SCHEMA,
        "current": None,
        "workspaces": {},
    }


def load_workspace_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_workspace_registry_path()
    if not registry_path.exists():
        return empty_registry()
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if registry.get("schema") != WORKSPACE_REGISTRY_SCHEMA:
        raise ValueError(f"unsupported workspace registry schema at {registry_path}")
    registry.setdefault("current", None)
    registry.setdefault("workspaces", {})
    return registry


def save_workspace_registry(registry: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_workspace_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "registry_path": str(registry_path),
        "registry": registry,
    }


def _workspace_paths(root: Path, db_path: Path | None, policy_path: Path | None, prompt_path: Path | None) -> dict[str, str]:
    return {
        "root": normalize_path(root),
        "db_path": normalize_path(db_path or ".zerker/memory.sqlite", root=root),
        "policy_path": normalize_path(policy_path or ".zerker/policy.json", root=root),
        "prompt_path": normalize_path(prompt_path or ".zerker/AGENT_PROMPT.md", root=root),
    }


def register_workspace(
    *,
    name: str | None = None,
    root: Path | None = None,
    db_path: Path | None = None,
    policy_path: Path | None = None,
    prompt_path: Path | None = None,
    registry_path: Path | None = None,
    make_current: bool = True,
) -> dict[str, Any]:
    workspace_root = (root or Path.cwd()).expanduser().resolve(strict=False)
    paths = _workspace_paths(workspace_root, db_path, policy_path, prompt_path)
    workspace_id = workspace_id_for_root(workspace_root)
    registry = load_workspace_registry(registry_path)
    existing = registry["workspaces"].get(workspace_id, {})
    timestamp = now_iso()
    record = {
        "id": workspace_id,
        "name": name or existing.get("name") or workspace_root.name or "Zerker Memory Workspace",
        "kind": existing.get("kind") or "project",
        "created_at": existing.get("created_at") or timestamp,
        "updated_at": timestamp,
        **paths,
    }
    registry["workspaces"][workspace_id] = record
    if make_current:
        registry["current"] = workspace_id
    save_workspace_registry(registry, registry_path)
    return {
        "ok": True,
        "registry_path": str(registry_path or default_workspace_registry_path()),
        "current": registry.get("current"),
        "workspace": record,
    }


def list_workspaces(*, registry_path: Path | None = None) -> dict[str, Any]:
    registry = load_workspace_registry(registry_path)
    items = sorted(registry["workspaces"].values(), key=lambda item: (item.get("name", ""), item.get("root", "")))
    return {
        "ok": True,
        "registry_path": str(registry_path or default_workspace_registry_path()),
        "current": registry.get("current"),
        "items": items,
    }


def find_workspace(identifier: str, registry: dict[str, Any]) -> dict[str, Any] | None:
    workspaces = registry.get("workspaces") or {}
    if identifier in workspaces:
        return workspaces[identifier]
    normalized_identifier = identifier.lower()
    for workspace in workspaces.values():
        if str(workspace.get("name", "")).lower() == normalized_identifier:
            return workspace
        if normalize_path(identifier) == workspace.get("root"):
            return workspace
    return None


def current_workspace(*, registry_path: Path | None = None) -> dict[str, Any]:
    registry = load_workspace_registry(registry_path)
    current_id = registry.get("current")
    workspace = registry.get("workspaces", {}).get(current_id) if current_id else None
    return {
        "ok": bool(workspace),
        "registry_path": str(registry_path or default_workspace_registry_path()),
        "current": current_id,
        "workspace": workspace,
    }


def use_workspace(identifier: str, *, registry_path: Path | None = None) -> dict[str, Any]:
    registry = load_workspace_registry(registry_path)
    workspace = find_workspace(identifier, registry)
    if not workspace:
        return {
            "ok": False,
            "registry_path": str(registry_path or default_workspace_registry_path()),
            "error": "workspace_not_found",
            "identifier": identifier,
        }
    registry["current"] = workspace["id"]
    workspace["updated_at"] = now_iso()
    save_workspace_registry(registry, registry_path)
    return {
        "ok": True,
        "registry_path": str(registry_path or default_workspace_registry_path()),
        "current": workspace["id"],
        "workspace": workspace,
    }


def prune_missing_workspaces(
    *,
    registry_path: Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    registry_file = registry_path or default_workspace_registry_path()
    registry = load_workspace_registry(registry_file)
    current_id = registry.get("current")
    candidates = [
        workspace
        for workspace_id, workspace in registry.get("workspaces", {}).items()
        if workspace_id != current_id
        and (
            not str(workspace.get("root") or "").strip()
            or not Path(str(workspace["root"])).expanduser().exists()
        )
    ]
    candidates.sort(key=lambda item: (str(item.get("name") or ""), str(item.get("root") or "")))
    if apply:
        for workspace in candidates:
            registry["workspaces"].pop(workspace["id"], None)
        save_workspace_registry(registry, registry_file)
    return {
        "schema": "zerker.workspace_prune.v1",
        "ok": True,
        "applied": apply,
        "registry_path": str(registry_file),
        "current_id": current_id,
        "candidate_count": len(candidates),
        "removed_count": len(candidates) if apply else 0,
        "candidates": [
            {
                "id": workspace.get("id"),
                "name": workspace.get("name"),
                "root": workspace.get("root"),
            }
            for workspace in candidates
        ],
    }


def workspace_status_for_paths(
    *,
    db_path: Path,
    policy_path: Path | None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    registry_file = registry_path or default_workspace_registry_path()
    registry_exists = registry_file.exists()
    registry = load_workspace_registry(registry_file)
    current_id = registry.get("current")
    current = registry.get("workspaces", {}).get(current_id) if current_id else None
    normalized_db = normalize_path(db_path)
    normalized_policy = normalize_path(policy_path) if policy_path is not None else None
    matched = None
    for workspace in registry.get("workspaces", {}).values():
        if workspace.get("db_path") == normalized_db:
            matched = workspace
            break
    if matched and current and matched.get("id") == current.get("id"):
        match_state = "matched-current"
    elif matched:
        match_state = "matched-other"
    elif current:
        match_state = "unregistered-path"
    elif registry_exists:
        match_state = "no-current"
    else:
        match_state = "registry-missing"
    return {
        "schema": "zerker.workspace_profile.v1",
        "registry_path": str(registry_file),
        "registry_exists": registry_exists,
        "current_id": current_id,
        "current": current,
        "matched": matched,
        "match_state": match_state,
        "db_path": normalized_db,
        "policy_path": normalized_policy,
    }


def _agent_id_from_actor_uri(actor_uri: str) -> str:
    if actor_uri.startswith("agent://"):
        agent_id = actor_uri.removeprefix("agent://").split("/", 1)[0]
        return agent_id or actor_uri
    return actor_uri


def _uri_scheme(value: str | None) -> str | None:
    if not value or "://" not in value:
        return None
    scheme, _ = value.split("://", 1)
    return scheme or None


def _source_identity_descriptor(
    *,
    agent_id: str,
    session_id: str | None,
    source_uri: str | None,
    workspace: dict[str, Any] | None,
    workspace_id: str | None,
) -> dict[str, Any]:
    origin_kind, origin_locator = _source_origin_descriptor(session_id=session_id, source_uri=source_uri)
    workspace_root = None
    repo_name = None
    if isinstance(workspace, dict):
        workspace_root = workspace.get("root")
        if workspace_root:
            repo_name = Path(str(workspace_root)).name or None
    return {
        "tool": agent_id,
        "session_scheme": _uri_scheme(session_id),
        "source_scheme": _uri_scheme(source_uri),
        "workspace_id": workspace_id,
        "workspace_root": workspace_root,
        "repo_root": workspace_root,
        "repo_name": repo_name,
        "origin_kind": origin_kind,
        "origin_locator": origin_locator,
        "origin_summary": _origin_summary(origin_kind, origin_locator),
        "read_only_preview": True,
    }


def _uri_locator(value: str | None) -> str | None:
    if not value or "://" not in value:
        return None
    _, locator = value.split("://", 1)
    return locator or None


def _source_origin_descriptor(*, session_id: str | None, source_uri: str | None) -> tuple[str, str | None]:
    source_scheme = _uri_scheme(source_uri)
    if source_scheme == "conversation":
        return "chat_message", _uri_locator(source_uri)
    if source_scheme == "activegraph":
        return "activegraph_event", _uri_locator(source_uri)
    if source_scheme == "mem0":
        return "memory_candidate", _uri_locator(source_uri)
    if source_scheme == "file":
        return "workspace_file", _uri_locator(source_uri)
    if source_scheme in {"http", "https"}:
        return "web_document", _uri_locator(source_uri)
    if source_scheme:
        return f"{source_scheme}_uri", _uri_locator(source_uri)
    session_scheme = _uri_scheme(session_id)
    if session_scheme == "chat":
        return "chat_session", _uri_locator(session_id)
    if session_scheme:
        return f"{session_scheme}_session", _uri_locator(session_id)
    return "unknown", None


def _origin_summary(origin_kind: str, origin_locator: str | None) -> str:
    if origin_locator:
        return f"{origin_kind}:{origin_locator}"
    return origin_kind


def _resolve_local_artifact_path(*, base_dir: Path, candidate: Any) -> Path | None:
    text = str(candidate or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve(strict=False)


def workspace_restore_continuity_path(db_path: Path) -> Path:
    resolved_db_path = db_path.expanduser().resolve(strict=False)
    return resolved_db_path.with_name(resolved_db_path.name + ".restore.json")


def _workspace_restore_continuity_descriptor(*, db_path: Path) -> dict[str, Any] | None:
    anchor_path = workspace_restore_continuity_path(db_path)
    if not anchor_path.exists():
        return None
    try:
        anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(anchor, dict) or anchor.get("schema") != WORKSPACE_RESTORE_CONTINUITY_SCHEMA:
        return None
    continuity_sidecar_ok = anchor.get("continuity_sidecar_ok")
    if not isinstance(continuity_sidecar_ok, bool):
        continuity_sidecar_ok = None
    return {
        "kind": str(anchor.get("kind") or "local_snapshot_restore"),
        "action_id": None,
        "manifest_path": None,
        "created_at": str(anchor.get("created_at") or "").strip() or None,
        "snapshot_path": str(anchor.get("snapshot_path") or "").strip() or None,
        "snapshot_hash": str(anchor.get("snapshot_hash") or "").strip() or None,
        "snapshot_merkle_root": str(anchor.get("snapshot_merkle_root") or "").strip() or None,
        "restore_receipt_id": str(anchor.get("restore_receipt_id") or "").strip() or None,
        "restore_receipt_hash": str(anchor.get("restore_receipt_hash") or "").strip() or None,
        "restore_actor_uri": str(anchor.get("restore_actor_uri") or "").strip() or None,
        "continuity_sidecar_path": str(anchor.get("continuity_sidecar_path") or "").strip() or None,
        "continuity_sidecar_ok": continuity_sidecar_ok,
        "continuity_error": str(anchor.get("continuity_error") or "").strip() or None,
        "local_only": True,
        "read_only_preview": True,
    }


def _workspace_continuity_descriptor(*, db_path: Path) -> dict[str, Any] | None:
    handoff_dir = db_path.expanduser().resolve(strict=False).parent / "handoff"
    manifest_path = handoff_dir / "handoff.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            manifest = None
        if isinstance(manifest, dict) and manifest.get("schema") == "zerker.handoff_manifest.v1":
            snapshot_path = _resolve_local_artifact_path(base_dir=handoff_dir, candidate=manifest.get("snapshot_path"))
            snapshot_hash = None
            snapshot_merkle_root = None
            if snapshot_path is not None and snapshot_path.exists():
                try:
                    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    snapshot = None
                if isinstance(snapshot, dict):
                    value = str(snapshot.get("snapshot_hash") or "").strip()
                    snapshot_hash = value or None
                    value = str(snapshot.get("merkle_root") or "").strip()
                    snapshot_merkle_root = value or None
            action_id = str(manifest.get("action_id") or "").strip() or None
            return {
                "kind": "local_handoff_manifest",
                "action_id": action_id,
                "manifest_path": str(manifest_path.resolve(strict=False)),
                "snapshot_path": str(snapshot_path) if snapshot_path is not None else None,
                "snapshot_hash": snapshot_hash,
                "snapshot_merkle_root": snapshot_merkle_root,
                "local_only": True,
                "read_only_preview": True,
            }
    return _workspace_restore_continuity_descriptor(db_path=db_path)


def _imported_origin_descriptor(workspace_continuity: dict[str, Any] | None) -> dict[str, Any] | None:
    continuity = workspace_continuity or {}
    kind = str(continuity.get("kind") or "").strip()
    if kind != "local_snapshot_restore":
        return None
    continuity_sidecar_ok = continuity.get("continuity_sidecar_ok")
    if not isinstance(continuity_sidecar_ok, bool):
        continuity_sidecar_ok = None
    return {
        "kind": kind,
        "restore_created_at": str(continuity.get("created_at") or "").strip() or None,
        "restore_receipt_id": str(continuity.get("restore_receipt_id") or "").strip() or None,
        "restore_receipt_hash": str(continuity.get("restore_receipt_hash") or "").strip() or None,
        "restore_actor_uri": str(continuity.get("restore_actor_uri") or "").strip() or None,
        "snapshot_hash": str(continuity.get("snapshot_hash") or "").strip() or None,
        "snapshot_path": str(continuity.get("snapshot_path") or "").strip() or None,
        "continuity_sidecar_ok": continuity_sidecar_ok,
        "continuity_error": str(continuity.get("continuity_error") or "").strip() or None,
        "local_only": True,
        "read_only_preview": True,
    }


def _restore_lineage_descriptor(
    imported_origin: dict[str, Any] | None,
    *,
    source_receipt_created_at: str | None,
) -> dict[str, Any] | None:
    origin = imported_origin or {}
    restore_receipt_id = str(origin.get("restore_receipt_id") or "").strip()
    if not restore_receipt_id:
        return None
    restore_created_at = str(origin.get("restore_created_at") or "").strip() or None
    receipt_created_at = str(source_receipt_created_at or "").strip() or None
    kind = "imported_snapshot_write"
    basis = "workspace_restore_anchor"
    if restore_created_at and receipt_created_at:
        if receipt_created_at > restore_created_at:
            kind = "local_post_restore_write"
            basis = "receipt_created_at>restore_created_at"
        else:
            basis = "receipt_created_at<=restore_created_at"
    elif restore_created_at:
        basis = "restore_created_at_without_source_receipt_created_at"
    return {
        "kind": kind,
        "basis": basis,
        "restore_created_at": restore_created_at,
        "source_receipt_created_at": receipt_created_at,
        "local_only": True,
        "read_only_preview": True,
    }


def _identity_resolution_method(actor_uri: str) -> str:
    if actor_uri.startswith("agent://"):
        return "actor_uri_agent_scheme"
    return "actor_uri_literal"


def _identity_anchor(
    *,
    agent_id: str,
    actor_uri: str,
    session_id: str | None,
    source_uri: str | None,
    workspace_id: str | None,
    repo_name: str | None,
) -> dict[str, Any]:
    anchor_workspace_id = str(workspace_id or "unknown-workspace")
    return {
        "kind": "workspace_agent",
        "key": f"{anchor_workspace_id}::{agent_id}",
        "workspace_id": workspace_id,
        "agent_id": agent_id,
        "tool": agent_id,
        "repo_name": repo_name,
        "session_scheme": _uri_scheme(session_id),
        "source_scheme": _uri_scheme(source_uri),
        "resolution_method": _identity_resolution_method(actor_uri),
        "local_only": True,
        "read_only_preview": True,
    }


def _identity_resolution(
    *,
    anchor: dict[str, Any],
    chat_session_ids: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    session_ids = [str(session_id) for session_id in chat_session_ids if str(session_id)]
    return {
        "key": anchor.get("key"),
        "resolution_method": anchor.get("resolution_method"),
        "cross_session": len(session_ids) > 1,
        "session_count": len(session_ids),
        "read_only_preview": True,
        "local_only": True,
    }


def _preferred_claim_source(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    for source in source_rows:
        proof_lineage = source.get("proof_lineage") or {}
        if proof_lineage.get("treeship_statement_kind") == "zerker.memory.write_provenance":
            return source
    return source_rows[0] if source_rows else {}


def _treeship_subject_lineage(
    treeship_statement: dict[str, Any],
    treeship_attestation: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    statement_subject = treeship_statement.get("subject")
    subject_key = None
    if isinstance(treeship_attestation, dict):
        attested_subject = str(treeship_attestation.get("subject") or "").strip()
        if attested_subject:
            subject_key = attested_subject
    if not subject_key and isinstance(statement_subject, dict):
        statement_subject_id = str(statement_subject.get("id") or "").strip()
        if statement_subject_id:
            subject_key = statement_subject_id
    subject_type = None
    if isinstance(statement_subject, dict):
        value = str(statement_subject.get("type") or "").strip()
        subject_type = value or None
    return subject_key, subject_type


def _compact_action_task(task: str | None, *, limit: int = 72) -> str | None:
    text = " ".join(str(task or "").split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _parent_action_descriptor(
    store: Any,
    parent_action_id: str | None,
    *,
    action_cache: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    action_id = str(parent_action_id or "").strip()
    if not action_id:
        return None
    if action_id in action_cache:
        return dict(action_cache[action_id])
    row = store.conn.execute(
        """
        SELECT action_id, agent_id, task, risk, created_at
        FROM receipts
        WHERE action_id = ?
        """,
        (action_id,),
    ).fetchone()
    if row is None:
        descriptor = {
            "action_id": action_id,
            "agent_id": None,
            "task": None,
            "task_summary": None,
            "risk": None,
            "created_at": None,
            "available_local_receipt": False,
            "local_only": True,
            "read_only_preview": True,
        }
    else:
        descriptor = {
            "action_id": row["action_id"],
            "agent_id": row["agent_id"],
            "task": row["task"],
            "task_summary": _compact_action_task(row["task"]),
            "risk": row["risk"],
            "created_at": row["created_at"],
            "available_local_receipt": True,
            "local_only": True,
            "read_only_preview": True,
        }
    action_cache[action_id] = descriptor
    return dict(descriptor)


def _claim_resolution_key(claim: dict[str, Any], field: str) -> float | int | str:
    if field == "authority":
        return authority_rank(str(claim.get("authority") or "none"))
    if field == "trust":
        trust = claim.get("trust")
        return float(trust) if isinstance(trust, (int, float)) else float("-inf")
    return str(claim.get(field) or "")


def _claim_resolution_basis(
    *,
    claims: list[dict[str, Any]],
    chosen_memory_id: str | None,
    resolution_outcome: str,
    tie_fields: list[str],
) -> dict[str, Any]:
    if resolution_outcome == "abstained":
        summary = "exact tie on deciding fields"
        if tie_fields:
            summary = f"exact tie on {', '.join(tie_fields)}"
        return {
            "field": None,
            "summary": summary,
            "tied_fields": list(tie_fields),
            "read_only_preview": True,
        }
    if not chosen_memory_id:
        return {
            "field": None,
            "summary": "resolution preview unavailable",
            "tied_fields": [],
            "read_only_preview": True,
        }

    contenders = list(claims)
    chosen_field: str | None = None
    for field in ("authority", "trust", "updated_at", "created_at"):
        if not contenders:
            break
        max_value = max(_claim_resolution_key(claim, field) for claim in contenders)
        contenders = [claim for claim in contenders if _claim_resolution_key(claim, field) == max_value]
        if len(contenders) == 1 and contenders[0].get("memory_id") == chosen_memory_id:
            chosen_field = field
            break

    field_summary = {
        "authority": "highest authority",
        "trust": "highest trust",
        "updated_at": "freshest updated_at",
        "created_at": "freshest created_at",
    }
    return {
        "field": chosen_field,
        "summary": field_summary.get(chosen_field, "current rule preview"),
        "tied_fields": [],
        "read_only_preview": True,
    }


def _claim_resolution_display_value(field: str, claim: dict[str, Any] | None) -> str | None:
    contender = claim or {}
    if field == "authority":
        value = str(contender.get("authority") or "").strip()
        return value or None
    if field == "trust":
        trust = contender.get("trust")
        if isinstance(trust, (int, float)):
            return f"{float(trust):.2f}"
        return None
    value = str(contender.get(field) or "").strip()
    return value or None


def _claim_resolution_trace(
    *,
    claims: list[dict[str, Any]],
    resolution_outcome: str,
) -> list[dict[str, Any]]:
    contenders = list(claims)
    trace: list[dict[str, Any]] = []
    for field in ("authority", "trust", "updated_at", "created_at"):
        if not contenders:
            break
        max_value = max(_claim_resolution_key(claim, field) for claim in contenders)
        remaining = [claim for claim in contenders if _claim_resolution_key(claim, field) == max_value]
        display_value = _claim_resolution_display_value(field, remaining[0] if remaining else None)
        if len(remaining) == 1 and resolution_outcome != "abstained":
            summary = f"{field} selected {display_value}" if display_value else f"{field} selected remaining claim"
            trace.append(
                {
                    "field": field,
                    "outcome": "selected",
                    "value": display_value,
                    "remaining_memory_ids": [remaining[0].get("memory_id")],
                    "summary": summary,
                    "read_only_preview": True,
                }
            )
            break
        summary = f"{field} kept {len(remaining)} claims tied"
        if display_value:
            summary += f" at {display_value}"
        trace.append(
            {
                "field": field,
                "outcome": "tied",
                "value": display_value,
                "remaining_memory_ids": [claim.get("memory_id") for claim in remaining],
                "summary": summary,
                "read_only_preview": True,
            }
        )
        contenders = remaining
    return trace


def _claim_decisive_lineage(
    *,
    claims: list[dict[str, Any]],
    chosen_memory_id: str | None,
    resolution_basis: dict[str, Any] | None,
) -> dict[str, Any] | None:
    chosen_id = str(chosen_memory_id or "").strip()
    if not chosen_id:
        return None
    basis = resolution_basis or {}
    field = str(basis.get("field") or "").strip()
    if not field:
        return None
    chosen_claim = next(
        (
            claim
            for claim in claims
            if str(claim.get("memory_id") or "").strip() == chosen_id
        ),
        None,
    )
    if chosen_claim is None:
        return None
    agent_id = str(chosen_claim.get("agent_id") or "unknown")
    chat_session_id = str(chosen_claim.get("chat_session_id") or "unknown-session")
    summary_prefix = str(basis.get("summary") or field).strip() or field
    preview = {
        "field": field,
        "field_value": _claim_resolution_display_value(field, chosen_claim),
        "memory_id": chosen_claim.get("memory_id"),
        "chosen_value": chosen_claim.get("value"),
        "agent_id": agent_id,
        "chat_session_id": chat_session_id,
        "source_uri": chosen_claim.get("source_uri"),
        "workspace_id": chosen_claim.get("workspace_id"),
        "source_kind": chosen_claim.get("source_kind"),
        "trust_status": chosen_claim.get("trust_status"),
        "authority": chosen_claim.get("authority"),
        "trust": chosen_claim.get("trust"),
        "parent_action": dict(chosen_claim.get("parent_action") or {})
        if isinstance(chosen_claim.get("parent_action"), dict)
        else None,
        "source_identity": dict(chosen_claim.get("source_identity") or {})
        if isinstance(chosen_claim.get("source_identity"), dict)
        else None,
        "identity_anchor": dict(chosen_claim.get("identity_anchor") or {})
        if isinstance(chosen_claim.get("identity_anchor"), dict)
        else None,
        "identity_resolution": dict(chosen_claim.get("identity_resolution") or {})
        if isinstance(chosen_claim.get("identity_resolution"), dict)
        else None,
        "restore_lineage": dict(chosen_claim.get("restore_lineage") or {})
        if isinstance(chosen_claim.get("restore_lineage"), dict)
        else None,
        "proof_lineage": dict(chosen_claim.get("proof_lineage") or {})
        if isinstance(chosen_claim.get("proof_lineage"), dict)
        else None,
        "summary": f"{summary_prefix} came from {agent_id} @ {chat_session_id}",
        "read_only_preview": True,
        "local_only": True,
    }
    if isinstance(chosen_claim.get("imported_origin"), dict):
        preview["imported_origin"] = dict(chosen_claim.get("imported_origin") or {})
    return preview


def _claim_losing_contrast(
    *,
    claims: list[dict[str, Any]],
    resolution_outcome: str,
    chosen_memory_id: str | None,
    resolution_basis: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if resolution_outcome == "abstained":
        return None
    chosen_id = str(chosen_memory_id or "").strip()
    if not chosen_id:
        return None
    basis = resolution_basis or {}
    decisive_field = str(basis.get("field") or "").strip()
    if not decisive_field:
        return None
    contenders = list(claims)
    decisive_contenders = list(claims)
    for field in ("authority", "trust", "updated_at", "created_at"):
        if not contenders:
            return None
        decisive_contenders = list(contenders)
        max_value = max(_claim_resolution_key(claim, field) for claim in contenders)
        remaining = [claim for claim in contenders if _claim_resolution_key(claim, field) == max_value]
        if field == decisive_field:
            contenders = remaining
            break
        contenders = remaining
    chosen_claim = next(
        (
            claim
            for claim in decisive_contenders
            if str(claim.get("memory_id") or "").strip() == chosen_id
        ),
        None,
    )
    if chosen_claim is None:
        return None
    losing_claims = [
        claim
        for claim in decisive_contenders
        if str(claim.get("memory_id") or "").strip() != chosen_id
    ]
    if not losing_claims:
        return None
    chosen_field_value = _claim_resolution_display_value(decisive_field, chosen_claim)
    losing_field_values = [
        value
        for value in (
            _claim_resolution_display_value(decisive_field, claim)
            for claim in losing_claims
        )
        if value
    ]
    winner_agent = str(chosen_claim.get("agent_id") or "unknown")
    winner_session = str(chosen_claim.get("chat_session_id") or "unknown-session")
    summary_prefix = str(basis.get("summary") or decisive_field).strip() or decisive_field
    if len(losing_claims) == 1:
        losing_claim = losing_claims[0]
        loser_agent = str(losing_claim.get("agent_id") or "unknown")
        loser_session = str(losing_claim.get("chat_session_id") or "unknown-session")
        loser_field_value = _claim_resolution_display_value(decisive_field, losing_claim)
        winner_detail = f" ({chosen_field_value})" if chosen_field_value else ""
        loser_detail = f" ({loser_field_value})" if loser_field_value else ""
        summary = (
            f"{summary_prefix} kept {winner_agent} @ {winner_session}{winner_detail} "
            f"over {loser_agent} @ {loser_session}{loser_detail}"
        )
    else:
        losing_value_summary = ", ".join(dict.fromkeys(losing_field_values))
        summary = (
            f"{summary_prefix} kept {winner_agent} @ {winner_session}"
            f"{f' ({chosen_field_value})' if chosen_field_value else ''} "
            f"over {len(losing_claims)} competing claims"
        )
        if losing_value_summary:
            summary += f" at {losing_value_summary}"
    return {
        "field": decisive_field,
        "winner_memory_id": chosen_claim.get("memory_id"),
        "winner_value": chosen_claim.get("value"),
        "winner_field_value": chosen_field_value,
        "losing_memory_ids": [claim.get("memory_id") for claim in losing_claims],
        "losing_values": [claim.get("value") for claim in losing_claims],
        "losing_claim_count": len(losing_claims),
        "losing_claims": [
            {
                "memory_id": claim.get("memory_id"),
                "value": claim.get("value"),
                "agent_id": claim.get("agent_id"),
                "chat_session_id": claim.get("chat_session_id"),
                "source_uri": claim.get("source_uri"),
                "field_value": _claim_resolution_display_value(decisive_field, claim),
            }
            for claim in losing_claims
        ],
        "summary": summary,
        "read_only_preview": True,
        "local_only": True,
    }


def _claim_losing_parent_action(
    *,
    claims: list[dict[str, Any]],
    resolution_outcome: str,
    chosen_memory_id: str | None,
) -> dict[str, Any] | None:
    if resolution_outcome == "abstained":
        return None
    chosen_id = str(chosen_memory_id or "").strip()
    if not chosen_id:
        return None
    losing_claims = [
        claim
        for claim in claims
        if str(claim.get("memory_id") or "").strip() != chosen_id
    ]
    if len(losing_claims) != 1:
        return None
    losing_claim = losing_claims[0]
    parent_action = losing_claim.get("parent_action")
    if not isinstance(parent_action, dict):
        return None
    action_id = str(parent_action.get("action_id") or "").strip()
    if not action_id:
        return None
    agent_id = str(losing_claim.get("agent_id") or "unknown")
    chat_session_id = str(losing_claim.get("chat_session_id") or "unknown-session")
    risk = str(parent_action.get("risk") or "unknown")
    task_summary = str(parent_action.get("task_summary") or "unknown")
    return {
        "memory_id": losing_claim.get("memory_id"),
        "value": losing_claim.get("value"),
        "agent_id": agent_id,
        "chat_session_id": chat_session_id,
        "source_uri": losing_claim.get("source_uri"),
        "parent_action": dict(parent_action),
        "summary": f"losing claim came from {action_id} by {agent_id} @ {chat_session_id}",
        "read_only_preview": True,
        "local_only": True,
        "risk": risk,
        "task_summary": task_summary,
    }


def _workspace_claim_conflicts(store: Any, *, source_rows_by_memory_id: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if not source_rows_by_memory_id:
        return []
    memory_ids = list(source_rows_by_memory_id)
    placeholders = ",".join("?" for _ in memory_ids)
    rows = store.conn.execute(
        f"""
        SELECT *
        FROM memories
        WHERE id IN ({placeholders})
          AND status IN ('active', 'proposed', 'quarantined')
        ORDER BY updated_at DESC, created_at DESC, id DESC
        """,
        tuple(memory_ids),
    ).fetchall()
    candidate_by_id = {row["id"]: MemoryRecord.from_row(row) for row in rows}
    if not candidate_by_id:
        return []
    candidate_ids_in_rank_order: list[str] = []
    for memory_id in memory_ids:
        if memory_id in candidate_by_id and memory_id not in candidate_ids_in_rank_order:
            candidate_ids_in_rank_order.append(memory_id)
    conflict_sets = _resolve_current_conflicts(
        candidate_by_id=candidate_by_id,
        current_ids=list(candidate_ids_in_rank_order),
        candidate_ids_in_rank_order=candidate_ids_in_rank_order,
    )
    claim_conflicts: list[dict[str, Any]] = []
    for conflict in conflict_sets:
        involved_ids = [
            memory_id
            for memory_id in conflict.get("involved_candidate_ids", [])
            if memory_id in candidate_by_id and source_rows_by_memory_id.get(memory_id)
        ]
        if not involved_ids:
            continue
        claims: list[dict[str, Any]] = []
        connected_agent_ids: list[str] = []
        chat_session_ids: list[str] = []
        for memory_id in involved_ids:
            memory = candidate_by_id[memory_id]
            source = _preferred_claim_source(source_rows_by_memory_id[memory_id])
            agent_id = str(source.get("agent_id") or "unknown")
            chat_session_id = str(source.get("chat_session_id") or "")
            if agent_id not in connected_agent_ids:
                connected_agent_ids.append(agent_id)
            if chat_session_id and chat_session_id not in chat_session_ids:
                chat_session_ids.append(chat_session_id)
            claims.append(
                {
                    "memory_id": memory.id,
                    "content": memory.content,
                    "value": (conflict.get("value_by_id") or {}).get(memory.id),
                    "agent_id": agent_id,
                    "actor_uri": source.get("actor_uri"),
                    "chat_session_id": source.get("chat_session_id"),
                    "workspace_id": source.get("workspace_id"),
                    "source_kind": memory.source_kind,
                    "trust_status": memory.status,
                    "trust": memory.trust,
                    "authority": memory.authority,
                    "source_uri": source.get("source_uri"),
                    "parent_action_id": source.get("parent_action_id"),
                    "parent_action": source.get("parent_action"),
                    "source_identity": source.get("source_identity"),
                    "identity_anchor": source.get("identity_anchor"),
                    "identity_resolution": source.get("identity_resolution"),
                    "restore_lineage": source.get("restore_lineage"),
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                    "proof_lineage": source.get("proof_lineage"),
                }
            )
            if isinstance(source.get("imported_origin"), dict):
                claims[-1]["imported_origin"] = source.get("imported_origin")
        chosen_memory_id = conflict.get("chosen_current_id")
        chosen_memory_id_text = str(chosen_memory_id) if chosen_memory_id else None
        resolution_outcome = str(
            conflict.get("resolution_outcome") or ("resolved" if chosen_memory_id else "abstained")
        )
        tie_fields = [str(field) for field in (conflict.get("tie_fields") or []) if str(field)]
        resolution_basis = _claim_resolution_basis(
            claims=claims,
            chosen_memory_id=chosen_memory_id_text,
            resolution_outcome=resolution_outcome,
            tie_fields=tie_fields,
        )
        claim_conflicts.append(
            {
                "group_key": f"{conflict.get('subject_key')}|{conflict.get('relation')}",
                "entity_key": conflict.get("subject_key"),
                "subject_key": conflict.get("subject_key"),
                "relation": conflict.get("relation"),
                "claim_count": len(claims),
                "connected_agent_ids": sorted(connected_agent_ids),
                "chat_session_ids": sorted(chat_session_ids),
                "cross_session": len(chat_session_ids) > 1,
                "claims": claims,
                "merge_preview": {
                    "resolution_strategy": conflict.get("resolution_strategy"),
                    "resolution_outcome": resolution_outcome,
                    "chosen_memory_id": chosen_memory_id,
                    "chosen_value": (conflict.get("value_by_id") or {}).get(chosen_memory_id) if chosen_memory_id else None,
                    "abstained_memory_ids": conflict.get("abstained_current_ids", []),
                    "tied_memory_ids": conflict.get("tied_current_ids", []),
                    "tie_fields": tie_fields,
                    "ignored_tie_breakers": conflict.get("ignored_tie_breakers", []),
                    "resolution_basis": resolution_basis,
                    "decisive_claim_lineage": _claim_decisive_lineage(
                        claims=claims,
                        chosen_memory_id=chosen_memory_id_text,
                        resolution_basis=resolution_basis,
                    ),
                    "losing_claim_contrast": _claim_losing_contrast(
                        claims=claims,
                        resolution_outcome=resolution_outcome,
                        chosen_memory_id=chosen_memory_id_text,
                        resolution_basis=resolution_basis,
                    ),
                    "losing_claim_parent_action": _claim_losing_parent_action(
                        claims=claims,
                        resolution_outcome=resolution_outcome,
                        chosen_memory_id=chosen_memory_id_text,
                    ),
                    "resolution_trace": _claim_resolution_trace(
                        claims=claims,
                        resolution_outcome=resolution_outcome,
                    ),
                    "rule_summary": (
                        "Choose the highest authority, then trust, then freshest updated_at/created_at; abstain on exact ties."
                    ),
                    "read_only_preview": True,
                },
            }
        )
    return claim_conflicts


def workspace_source_report(
    store: Any,
    *,
    db_path: Path,
    policy_path: Path | None,
    registry_path: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    store.init()
    workspace_profile = workspace_status_for_paths(
        db_path=db_path,
        policy_path=policy_path,
        registry_path=registry_path,
    )
    workspace = workspace_profile.get("matched") or workspace_profile.get("current")
    workspace_id = workspace.get("id") if isinstance(workspace, dict) else None
    workspace_root = workspace.get("root") if isinstance(workspace, dict) else None
    repo_name = Path(str(workspace_root)).name if workspace_root else None
    workspace_continuity = _workspace_continuity_descriptor(db_path=db_path)
    imported_origin = _imported_origin_descriptor(workspace_continuity)
    rows = store.conn.execute(
        """
        SELECT
          w.receipt_id,
          w.memory_id,
          w.actor_uri,
          w.session_id,
          w.parent_action_id,
          w.source_uri,
          w.event_hash,
          w.merkle_root,
          w.receipt_hash,
          w.treeship_statement_json,
          w.created_at,
          m.type AS memory_type,
          m.scope AS memory_scope,
          m.source_kind,
          m.status AS memory_status
        FROM memory_write_receipts w
        LEFT JOIN memories m ON m.id = w.memory_id
        ORDER BY w.created_at DESC, w.rowid DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    sources: list[dict[str, Any]] = []
    source_rows_by_memory_id: dict[str, list[dict[str, Any]]] = {}
    agents: dict[str, dict[str, Any]] = {}
    action_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        actor_uri = row["actor_uri"]
        agent_id = _agent_id_from_actor_uri(actor_uri)
        treeship_statement = json.loads(row["treeship_statement_json"])
        treeship_attestation = treeship_statement.get("attestation")
        treeship_subject_key, treeship_subject_type = _treeship_subject_lineage(
            treeship_statement,
            treeship_attestation if isinstance(treeship_attestation, dict) else None,
        )
        proof_lineage = {
            "receipt_id": row["receipt_id"],
            "memory_id": row["memory_id"],
            "event_hash": row["event_hash"],
            "merkle_root": row["merkle_root"],
            "receipt_hash": row["receipt_hash"],
            "treeship_statement_kind": treeship_statement.get("kind"),
            "treeship_attestation_status": (
                treeship_attestation.get("status") if isinstance(treeship_attestation, dict) else None
            ),
            "treeship_system": (
                treeship_attestation.get("system") if isinstance(treeship_attestation, dict) else None
            ),
            "treeship_artifact_id": (
                treeship_attestation.get("artifact_id") if isinstance(treeship_attestation, dict) else None
            ),
            "treeship_subject_key": treeship_subject_key,
            "treeship_subject_type": treeship_subject_type,
            "treeship_payload_digest": (
                treeship_attestation.get("payload_digest") if isinstance(treeship_attestation, dict) else None
            ),
            "treeship_signed_at": (
                treeship_attestation.get("signed_at") if isinstance(treeship_attestation, dict) else None
            ),
        }
        source_identity = _source_identity_descriptor(
            agent_id=agent_id,
            session_id=row["session_id"],
            source_uri=row["source_uri"],
            workspace=workspace if isinstance(workspace, dict) else None,
            workspace_id=workspace_id,
        )
        identity_anchor = _identity_anchor(
            agent_id=agent_id,
            actor_uri=actor_uri,
            session_id=row["session_id"],
            source_uri=row["source_uri"],
            workspace_id=workspace_id,
            repo_name=repo_name,
        )
        parent_action = _parent_action_descriptor(
            store,
            row["parent_action_id"],
            action_cache=action_cache,
        )
        restore_lineage = _restore_lineage_descriptor(
            imported_origin,
            source_receipt_created_at=row["created_at"],
        )
        source = {
            "agent_id": agent_id,
            "actor_uri": actor_uri,
            "chat_session_id": row["session_id"],
            "workspace_id": workspace_id,
            "memory_id": row["memory_id"],
            "memory_type": row["memory_type"],
            "memory_scope": row["memory_scope"],
            "source_kind": row["source_kind"],
            "trust_status": row["memory_status"],
            "source_uri": row["source_uri"],
            "parent_action_id": row["parent_action_id"],
            "parent_action": parent_action,
            "source_identity": source_identity,
            "identity_anchor": identity_anchor,
            "proof_lineage": proof_lineage,
            "restore_lineage": restore_lineage,
            "created_at": row["created_at"],
        }
        if restore_lineage is not None and restore_lineage.get("kind") == "imported_snapshot_write":
            source["imported_origin"] = dict(imported_origin)
        sources.append(source)
        source_rows_by_memory_id.setdefault(str(row["memory_id"]), []).append(source)
        agent = agents.setdefault(
            agent_id,
            {
                "agent_id": agent_id,
                "tool": agent_id,
                "actor_uri": actor_uri,
                "workspace_id": workspace_id,
                "workspace_root": workspace_root,
                "repo_root": workspace_root,
                "repo_name": repo_name,
                "memory_count": 0,
                "chat_session_ids": [],
                "source_uris": [],
                "identity_anchor": identity_anchor,
                "identity_resolution": {
                    **_identity_resolution(anchor=identity_anchor, chat_session_ids=[]),
                },
                "latest_parent_action": None,
                "latest_imported_origin": None,
                "latest_restore_lineage": None,
                "latest_proof_lineage": None,
                "latest_origin_kind": source_identity["origin_kind"],
                "latest_origin_summary": source_identity["origin_summary"],
                "last_seen_at": None,
            },
        )
        agent["memory_count"] += 1
        if row["session_id"] not in agent["chat_session_ids"]:
            agent["chat_session_ids"].append(row["session_id"])
        if row["source_uri"] and row["source_uri"] not in agent["source_uris"]:
            agent["source_uris"].append(row["source_uri"])
        agent["identity_resolution"] = _identity_resolution(
            anchor=identity_anchor,
            chat_session_ids=agent["chat_session_ids"],
        )
        if agent["latest_proof_lineage"] is None:
            agent["latest_parent_action"] = dict(parent_action) if isinstance(parent_action, dict) else None
            agent["latest_imported_origin"] = dict(source["imported_origin"]) if isinstance(source.get("imported_origin"), dict) else None
            agent["latest_restore_lineage"] = dict(restore_lineage) if isinstance(restore_lineage, dict) else None
            agent["latest_proof_lineage"] = proof_lineage
            agent["last_seen_at"] = row["created_at"]
    identity_resolution_by_key = {
        str(agent.get("identity_anchor", {}).get("key") or ""): dict(agent.get("identity_resolution") or {})
        for agent in agents.values()
    }
    for source in sources:
        identity_key = str(source.get("identity_anchor", {}).get("key") or "")
        source["identity_resolution"] = dict(identity_resolution_by_key.get(identity_key) or {})
    claim_conflicts = _workspace_claim_conflicts(store, source_rows_by_memory_id=source_rows_by_memory_id)
    return {
        "schema": "zerker.workspace_sources.v1",
        "workspace_profile": workspace_profile,
        "workspace_id": workspace_id,
        "workspace_continuity": workspace_continuity,
        "connected_agent_count": len(agents),
        "chat_session_count": len({source["chat_session_id"] for source in sources}),
        "source_count": len(sources),
        "claim_conflict_count": len(claim_conflicts),
        "connected_agents": sorted(agents.values(), key=lambda item: item["agent_id"]),
        "claim_conflicts": claim_conflicts,
        "sources": sources,
    }
