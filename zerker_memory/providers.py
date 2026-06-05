from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .adapters import Mem0RestAdapter, MemoryAdapter, ZepRestAdapter


PROVIDERS_SCHEMA = "zerker.providers.v1"
SUPPORTED_PROVIDERS = ("mem0", "zep")
SUPPORTED_IMPORT_SCOPES = ("global", "project")
SUPPORTED_IMPORT_TYPES = ("semantic", "procedural")


def default_provider_config_path() -> Path:
    return Path.cwd() / ".zerker" / "providers.json"


def provider_config_template() -> dict[str, Any]:
    return {
        "schema": PROVIDERS_SCHEMA,
        "providers": {
            "mem0": {
                "enabled": True,
                "base_url": "http://localhost:8888",
                "api_key_env": "MEM0_API_KEY",
                "governance": {
                    "allowed_scopes": ["global", "project"],
                    "allowed_types": ["semantic", "procedural"],
                    "import_trust": 0.45,
                    "import_authority": "none",
                    "import_status": "quarantined",
                    "labels": ["governance:external"],
                },
            },
            "zep": {
                "enabled": False,
                "base_url": "http://localhost:8000",
                "api_key_env": "ZEP_API_KEY",
                "search_path": "/api/v1/search",
                "governance": {
                    "allowed_scopes": ["global", "project"],
                    "allowed_types": ["semantic", "procedural"],
                    "import_trust": 0.45,
                    "import_authority": "none",
                    "import_status": "quarantined",
                    "labels": ["governance:external"],
                },
            }
        },
    }


def write_provider_config_template(path: Path, *, force: bool) -> dict[str, Any]:
    if path.exists() and not force:
        return {"ok": True, "written": False, "path": str(path), "reason": "already exists"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(provider_config_template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "written": True, "path": str(path)}


def load_provider_config(path: Path | None = None) -> dict[str, Any]:
    path = path or default_provider_config_path()
    if not path.exists():
        return provider_config_template()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != PROVIDERS_SCHEMA:
        raise ValueError("unsupported provider config schema")
    if not isinstance(data.get("providers"), dict):
        raise ValueError("provider config missing providers object")
    return data


def provider_settings(config: dict[str, Any], provider: str) -> dict[str, Any]:
    providers = config.get("providers", {})
    settings = providers.get(provider, {})
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        raise ValueError(f"provider settings must be an object: {provider}")
    return settings


def provider_import_settings(
    provider: str,
    *,
    config_path: Path | None = None,
    memory_type: str,
    scope: str,
) -> dict[str, Any]:
    config = load_provider_config(config_path)
    settings = provider_settings(config, provider)
    governance = settings.get("governance") or {}
    if not isinstance(governance, dict):
        raise ValueError(f"provider governance must be an object: {provider}")
    allowed_scopes = _string_list(governance.get("allowed_scopes"), default=SUPPORTED_IMPORT_SCOPES)
    allowed_types = _string_list(governance.get("allowed_types"), default=SUPPORTED_IMPORT_TYPES)
    if scope not in allowed_scopes:
        raise ValueError(f"provider {provider} import blocked for scope: {scope}")
    if memory_type not in allowed_types:
        raise ValueError(f"provider {provider} import blocked for type: {memory_type}")
    labels = _string_list(governance.get("labels"), default=())
    return {
        "trust": _float_or_none(governance.get("import_trust")),
        "authority": _string_or_none(governance.get("import_authority")),
        "status": _string_or_none(governance.get("import_status")),
        "labels": labels,
        "allowed_scopes": allowed_scopes,
        "allowed_types": allowed_types,
    }


def configured_api_key(settings: dict[str, Any]) -> str | None:
    if isinstance(settings.get("api_key"), str) and settings["api_key"]:
        return settings["api_key"]
    api_key_env = settings.get("api_key_env")
    if isinstance(api_key_env, str) and api_key_env:
        return os.getenv(api_key_env)
    return None


def provider_live_smoke(
    provider: str,
    *,
    config_path: Path | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    query: str = "zerker provider doctor",
    user_id: str | None = None,
    limit: int = 1,
    allow_disabled: bool = False,
) -> dict[str, Any]:
    adapter = build_provider_adapter(
        provider,
        config_path=config_path,
        base_url=base_url,
        api_key=api_key,
        allow_disabled=allow_disabled,
    )
    results = adapter.search(query, user_id=user_id, limit=limit)
    return {
        "schema": "zerker.provider_live_smoke.v1",
        "provider": provider,
        "ok": True,
        "query": query,
        "user_id": user_id,
        "result_count": len(results),
    }


def build_provider_adapter(
    provider: str,
    *,
    config_path: Path | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    allow_disabled: bool = False,
) -> MemoryAdapter:
    config = load_provider_config(config_path)
    settings = provider_settings(config, provider)
    if settings.get("enabled") is False and not allow_disabled:
        raise ValueError(f"provider disabled: {provider}")
    if provider == "mem0":
        return Mem0RestAdapter(
            base_url=base_url or settings.get("base_url"),
            api_key=api_key or configured_api_key(settings),
        )
    if provider == "zep":
        return ZepRestAdapter(
            base_url=base_url or settings.get("base_url"),
            api_key=api_key or configured_api_key(settings),
            search_path=settings.get("search_path"),
        )
    raise ValueError(f"unsupported provider: {provider}")


def provider_doctor(
    config_path: Path | None = None,
    *,
    live: bool = False,
    live_query: str = "zerker provider doctor",
    live_user_id: str | None = None,
    live_limit: int = 1,
    live_overrides: dict[str, dict[str, str | None]] | None = None,
    selected_providers: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    path = config_path or default_provider_config_path()
    exists = path.exists()
    config = load_provider_config(path)
    requested = _selected_providers(selected_providers)
    checks: list[dict[str, Any]] = [
        {
            "name": "providers_config",
            "ok": True,
            "details": str(path) if exists else f"{path} not found; using defaults",
        }
    ]
    provider_names = requested or sorted(config.get("providers", {}).keys())
    for provider in provider_names:
        settings = provider_settings(config, provider)
        if not isinstance(settings, dict):
            checks.append({"name": f"{provider}_config", "ok": False, "details": "settings must be an object"})
            continue
        enabled = settings.get("enabled") is not False
        base_url = settings.get("base_url")
        api_key_env = settings.get("api_key_env")
        api_key_ready = bool(configured_api_key(settings))
        checks.append(
            {
                "name": f"{provider}_config",
                "ok": (not enabled) or bool(base_url),
                "details": {
                    "enabled": enabled,
                    "base_url": base_url,
                    "api_key_env": api_key_env,
                    "api_key_ready": api_key_ready,
                    "governance": _governance_details(settings),
                    **({"search_path": settings["search_path"]} if isinstance(settings.get("search_path"), str) else {}),
                },
            }
        )
        overrides = (live_overrides or {}).get(provider, {})
        explicitly_selected = provider in requested
        if live and (enabled or explicitly_selected or _has_live_override(overrides)):
            checks.append(
                _live_check(
                    provider,
                    path,
                    query=live_query,
                    user_id=live_user_id,
                    limit=live_limit,
                    overrides=overrides,
                    allow_disabled=explicitly_selected or _has_live_override(overrides),
                )
            )
    return {
        "schema": "zerker.provider_doctor.v1",
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }


def _live_check(
    provider: str,
    path: Path,
    *,
    query: str,
    user_id: str | None,
    limit: int,
    overrides: dict[str, str | None],
    allow_disabled: bool,
) -> dict[str, Any]:
    live_query = overrides.get("query") or query
    live_user_id = overrides.get("user_id") if overrides.get("user_id") is not None else user_id
    try:
        result = provider_live_smoke(
            provider,
            config_path=path,
            base_url=overrides.get("base_url"),
            api_key=overrides.get("api_key"),
            query=live_query,
            user_id=live_user_id,
            limit=limit,
            allow_disabled=allow_disabled,
        )
        return {
            "name": f"{provider}_live",
            "ok": result["ok"],
            "details": {
                "query": result["query"],
                "user_id": result["user_id"],
                "result_count": result["result_count"],
                **({"allow_disabled": True} if allow_disabled else {}),
                **({"base_url": overrides["base_url"]} if overrides.get("base_url") else {}),
            },
        }
    except Exception as exc:
        return {"name": f"{provider}_live", "ok": False, "details": str(exc)}


def _has_live_override(overrides: dict[str, str | None]) -> bool:
    return any(overrides.get(key) for key in ("base_url", "api_key", "query", "user_id"))


def _selected_providers(selected_providers: list[str] | tuple[str, ...] | None) -> list[str]:
    if not selected_providers:
        return []
    normalized: list[str] = []
    for provider in selected_providers:
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unsupported provider selection: {provider}")
        if provider not in normalized:
            normalized.append(provider)
    return normalized


def _governance_details(settings: dict[str, Any]) -> dict[str, Any]:
    governance = settings.get("governance") or {}
    if not isinstance(governance, dict):
        return {"error": "governance must be an object"}
    return {
        "allowed_scopes": _string_list(governance.get("allowed_scopes"), default=SUPPORTED_IMPORT_SCOPES),
        "allowed_types": _string_list(governance.get("allowed_types"), default=SUPPORTED_IMPORT_TYPES),
        "import_trust": _float_or_none(governance.get("import_trust")),
        "import_authority": _string_or_none(governance.get("import_authority")) or "none",
        "import_status": _string_or_none(governance.get("import_status")) or "quarantined",
        "labels": _string_list(governance.get("labels"), default=()),
    }


def _string_list(value: Any, *, default: tuple[str, ...] | list[str]) -> list[str]:
    if value is None:
        return [str(item) for item in default]
    if not isinstance(value, list):
        raise ValueError("provider governance list must be an array")
    return [str(item) for item in value]


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
