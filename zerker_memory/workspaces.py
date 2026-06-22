from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .store import now_iso, sha256_text


WORKSPACE_REGISTRY_SCHEMA = "zerker.workspace_registry.v1"
WORKSPACE_REGISTRY_ENV = "ZMEM_WORKSPACE_REGISTRY"


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
