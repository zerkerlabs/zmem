from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store import sha256_text, stable_json
from .treeship import to_treeship_statement


def artifact_id(value: dict[str, Any], *, prefix: str = "zmem") -> str:
    return f"{prefix}_{sha256_text(stable_json(value))[:16]}"


def default_export_path(value: dict[str, Any], *, fmt: str, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or Path.cwd() / ".zerker" / "exports"
    return out_dir / f"{artifact_id(value)}.{fmt}.json"


def default_snapshot_path(snapshot: dict[str, Any], *, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or Path.cwd() / ".zerker" / "exports"
    return out_dir / f"{artifact_id(snapshot, prefix='zmem_snapshot')}.snapshot.json"


def default_bundle_path(bundle: dict[str, Any], *, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or Path.cwd() / ".zerker" / "exports"
    return out_dir / f"{artifact_id(bundle, prefix='zmem_bundle')}.bundle.json"


def export_receipt(receipt: dict[str, Any], *, fmt: str, out: Path | None = None, out_dir: Path | None = None) -> dict[str, Any]:
    if fmt == "json":
        payload = receipt
    elif fmt == "treeship":
        payload = to_treeship_statement(receipt)
    else:
        raise ValueError(f"unsupported export format: {fmt}")

    path = out or default_export_path(payload, fmt=fmt, out_dir=out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "artifact_id": artifact_id(payload),
        "format": fmt,
        "path": str(path),
        "sha256": sha256_text(stable_json(payload)),
        "payload": payload,
    }


def export_snapshot(snapshot: dict[str, Any], *, out: Path | None = None, out_dir: Path | None = None) -> dict[str, Any]:
    path = out or default_snapshot_path(snapshot, out_dir=out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "artifact_id": artifact_id(snapshot, prefix="zmem_snapshot"),
        "format": "snapshot",
        "path": str(path),
        "sha256": sha256_text(stable_json(snapshot)),
        "payload": snapshot,
    }


def export_bundle(bundle: dict[str, Any], *, out: Path | None = None, out_dir: Path | None = None) -> dict[str, Any]:
    path = out or default_bundle_path(bundle, out_dir=out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "artifact_id": artifact_id(bundle, prefix="zmem_bundle"),
        "format": "bundle",
        "path": str(path),
        "sha256": sha256_text(stable_json(bundle)),
        "payload": bundle,
    }
