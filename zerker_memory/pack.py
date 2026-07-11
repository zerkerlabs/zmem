from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from activegraph.packs import Pack, behavior
from pydantic import BaseModel

from zerker_memory import __version__
from zerker_memory.integrations.activegraph import PERSIST_EVENT_TYPES, persist, recall


class ZMemSettings(BaseModel):
    db_path: str | None = None
    retrieval_mode: Literal["fts", "semantic", "hybrid"] = "fts"
    treeship_enabled: bool = False


def _event_envelope(event: Any, graph: Any, ctx: Any) -> dict[str, Any]:
    runtime = getattr(ctx, "_runtime", None)
    run_id = str(getattr(runtime, "run_id", None) or getattr(graph, "run_id", "default"))
    payload = dict(getattr(event, "payload", {}) or {})
    payload.setdefault("session_id", run_id)
    payload.setdefault("run_id", run_id)
    return {
        "id": str(getattr(event, "id", "ag_evt_unknown")),
        "type": str(getattr(event, "type", "")),
        "session_id": run_id,
        "run_id": run_id,
        "payload": payload,
    }


def _settings(ctx: Any) -> ZMemSettings:
    settings = getattr(ctx, "settings", None)
    return settings if isinstance(settings, ZMemSettings) else ZMemSettings()


def _db_path(settings: ZMemSettings) -> Path | None:
    return Path(settings.db_path).expanduser() if settings.db_path else None


@behavior(name="persist", on=sorted(PERSIST_EVENT_TYPES))
def persist_behavior(event: Any, graph: Any, ctx: Any) -> None:
    settings = _settings(ctx)
    persist(
        _event_envelope(event, graph, ctx),
        db_path=_db_path(settings),
        treeship_enabled=settings.treeship_enabled,
    )


@behavior(name="recall", on=["llm.requested"])
def recall_behavior(event: Any, graph: Any, ctx: Any) -> None:
    settings = _settings(ctx)
    recall(
        _event_envelope(event, graph, ctx),
        db_path=_db_path(settings),
        retrieval_mode=settings.retrieval_mode,
        treeship_enabled=settings.treeship_enabled,
    )


pack = Pack(
    name="zmem",
    version=__version__,
    description="Cross-session governed memory for ActiveGraph agents.",
    behaviors=(persist_behavior, recall_behavior),
    settings_schema=ZMemSettings,
)


def ZMemPack() -> Pack:
    """Backward-compatible constructor for the pre-1.9 entry point name."""

    return pack


__all__ = ["pack", "ZMemPack", "ZMemSettings"]
