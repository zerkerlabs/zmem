#!/usr/bin/env python3
"""Summarize persisted ZMem benchmark matrix evidence without replaying a run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SUMMARY_SCHEMA = "zerker.benchmark_evidence_summary.v1"
MATRIX_SCHEMA = "zerker.benchmark_matrix.v1"
COMPARISON_SCHEMA = "zerker.benchmark_comparison.v1"


def load_summary(path: Path) -> dict[str, Any]:
    matrix_path = _matrix_path(path)
    matrix_dir = matrix_path.parent
    matrix = _read_json(matrix_path)
    comparison_path = _linked_path(matrix_dir, str(matrix.get("comparison_path") or "benchmark-comparison.json"))
    comparison = _read_json(comparison_path) if comparison_path.exists() else None

    declared_matrix_hash = matrix.get("matrix_hash")
    actual_matrix_hash = _artifact_hash(matrix, "matrix_hash")
    declared_comparison_hash = matrix.get("comparison_hash")
    actual_comparison_hash = _artifact_hash(comparison, "comparison_hash") if comparison else None

    checks = {
        "matrix_schema": matrix.get("schema") == MATRIX_SCHEMA,
        "matrix_hash": declared_matrix_hash == actual_matrix_hash,
        "comparison_present": comparison is not None,
        "comparison_schema": comparison is not None and comparison.get("schema") == COMPARISON_SCHEMA,
        "comparison_hash": comparison is not None and comparison.get("comparison_hash") == actual_comparison_hash,
        "matrix_links_comparison": comparison is not None
        and declared_comparison_hash == comparison.get("comparison_hash"),
    }

    return {
        "schema": SUMMARY_SCHEMA,
        "ok": all(checks.values()),
        "artifact_type": "matrix",
        "matrix_dir": str(matrix_dir),
        "run_id": matrix.get("run_id"),
        "benchmark": matrix.get("benchmark"),
        "dataset": matrix.get("dataset"),
        "split": matrix.get("split"),
        "seed": matrix.get("seed"),
        "context_budget_tokens": matrix.get("context_budget_tokens"),
        "retrieval_modes": matrix.get("retrieval_modes", []),
        "question_summary": matrix.get("question_summary", {}),
        "mode_summaries": [_mode_summary(mode_run) for mode_run in matrix.get("mode_runs", [])],
        "artifacts": {
            "matrix": {
                "path": str(matrix_path),
                "file_sha256": _file_hash(matrix_path),
                "declared_hash": declared_matrix_hash,
                "computed_hash": actual_matrix_hash,
            },
            "comparison": {
                "path": str(comparison_path),
                "file_sha256": _file_hash(comparison_path) if comparison_path.exists() else None,
                "declared_hash": comparison.get("comparison_hash") if comparison else None,
                "computed_hash": actual_comparison_hash,
            },
        },
        "checks": checks,
        "claim_boundary": {
            "public_benchmark_claim": False,
            "claimable_as": "local proof-backed benchmark evidence, not an official LoCoMo/LongMemEval ranking",
        },
    }


def _matrix_path(path: Path) -> Path:
    if path.is_dir():
        return path / "benchmark-matrix.json"
    return path


def _linked_path(matrix_dir: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    candidates = (matrix_dir / path, path, matrix_dir / path.name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _mode_summary(mode_run: dict[str, Any]) -> dict[str, Any]:
    summary = mode_run.get("summary", {}) if isinstance(mode_run.get("summary"), dict) else {}
    return {
        "retrieval_mode": mode_run.get("retrieval_mode"),
        "accuracy": summary.get("accuracy"),
        "question_count": summary.get("question_count"),
        "result_hash": mode_run.get("result_hash"),
        "aggregate_merkle_root": mode_run.get("aggregate_merkle_root"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_hash(payload: dict[str, Any] | None, hash_key: str) -> str | None:
    if payload is None:
        return None
    canonical = dict(payload)
    canonical.pop(hash_key, None)
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path, help="Matrix directory or benchmark-matrix.json path")
    parser.add_argument("--compact", action="store_true", help="Emit one-line JSON")
    args = parser.parse_args()

    indent = None if args.compact else 2
    print(json.dumps(load_summary(args.matrix), indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
