from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fails closed below.
    fcntl = None  # type: ignore[assignment]

from .consolidation import (
    ConsolidationJobRecord,
    append_consolidation_job_record,
    append_consolidation_summary_record,
    consolidation_audit_report,
    create_consolidation_job,
    load_consolidation_job_records,
    load_consolidation_summary_records,
    materialize_consolidation_summary,
)
from .consolidation_live import (
    build_live_consolidation_preview,
    validate_live_consolidation_preview,
    verified_live_event_state,
)
from .paths import expand_user_path
from .store import MemoryStore, now_iso, sha256_text, stable_json


LIVE_CONSOLIDATION_MATERIALIZATION_SCHEMA = "zerker.live_consolidation_materialization.v1"
CONSOLIDATION_LEDGER_RECOVERY_SCHEMA = "zerker.consolidation_ledger_recovery.v1"
LIVE_SUMMARIZER_KIND = "deterministic-live-ledger-v1"
ISO_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def materialize_live_consolidation_candidate(
    db_path: Path,
    preview: Mapping[str, Any],
    *,
    candidate_id: str,
    actor_id: str,
    confirmed_preview_id: str,
    job_ledger_path: Path | None = None,
    summary_ledger_path: Path | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    canonical_preview = validate_live_consolidation_preview(preview)
    if confirmed_preview_id != canonical_preview["confirmation_id"]:
        raise ValueError("consolidation preview confirmation mismatch")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("consolidation actor_id must be a non-empty string")
    timestamp = completed_at or now_iso()
    if not ISO_UTC_PATTERN.match(timestamp):
        raise ValueError("consolidation completed_at must use ISO 8601 UTC form like 2025-01-01T00:00:00Z")

    path = expand_user_path(db_path)
    if path.resolve() != Path(canonical_preview["database"]).resolve():
        raise ValueError("consolidation preview database path mismatch")
    selected = _selected_candidate(canonical_preview, candidate_id)
    if selected.get("decision") != "ready-for-review":
        raise ValueError("consolidation candidate is not ready for review")

    resolved_job_ledger = expand_user_path(job_ledger_path or default_job_ledger_path(path))
    resolved_summary_ledger = expand_user_path(
        summary_ledger_path or default_summary_ledger_path(path)
    )
    _validate_ledger_destinations(path, resolved_job_ledger, resolved_summary_ledger)
    source_set_hash = str(selected["source_set_hash"])
    job_id = f"consolidation-job:live:{source_set_hash[:24]}"
    summary_id = f"summary:session:live:{source_set_hash[:16]}"
    binding = _preview_binding(canonical_preview, selected)
    admission = _admission_contract(selected)
    with _consolidation_ledger_locks((resolved_job_ledger, resolved_summary_ledger)):
        ledger_recovery = {
            "commit_marker": "newline",
            "job": _recover_uncommitted_ledger_tail(resolved_job_ledger, ledger_kind="job"),
            "summary": _recover_uncommitted_ledger_tail(
                resolved_summary_ledger,
                ledger_kind="summary",
            ),
        }
        try:
            with _locked_source_snapshot(path, canonical_preview, selected) as snapshot:
                source_children, event_root_before, source_store = snapshot
                existing_jobs = load_consolidation_job_records(resolved_job_ledger)
                summary_records = load_consolidation_summary_records(resolved_summary_ledger)
                matching_summaries = [
                    summary for summary in summary_records if summary["summary_id"] == summary_id
                ]
                if len(matching_summaries) > 1:
                    raise ValueError("consolidation summary ledger contains duplicate bound summaries")
                existing_summary = matching_summaries[0] if matching_summaries else None
                latest_matching = _latest_matching_job(existing_jobs, selected)

                if latest_matching is None:
                    if any(job.job_id == job_id for job in existing_jobs):
                        raise ValueError("consolidation job id is already bound to another source set")
                    if existing_summary is not None:
                        raise ValueError("consolidation summary exists without its bound job")
                    pending, completed, summary = _new_bound_records(
                        selected,
                        binding=binding,
                        admission=admission,
                        source_children=source_children,
                        job_id=job_id,
                        summary_id=summary_id,
                        actor_id=actor_id.strip(),
                        timestamp=timestamp,
                    )
                    _prepare_private_ledger(resolved_job_ledger)
                    _prepare_private_ledger(resolved_summary_ledger)
                    append_consolidation_job_record(resolved_job_ledger, pending)
                    append_consolidation_summary_record(resolved_summary_ledger, completed, summary)
                    append_consolidation_job_record(resolved_job_ledger, completed)
                    status = "materialized"
                    appended_job_records = 2
                    appended_summary_records = 1
                else:
                    _validate_job_binding(latest_matching, binding, admission)
                    _validate_existing_review(
                        latest_matching,
                        actor_id=actor_id.strip(),
                        confirmation_id=canonical_preview["confirmation_id"],
                    )
                    if latest_matching.status not in {"pending", "completed"}:
                        raise ValueError(
                            f"matching consolidation job is {latest_matching.status}; "
                            "audit it before retrying"
                        )
                    pending, completed, summary = _records_from_existing_job(
                        latest_matching,
                        selected,
                        binding=binding,
                        admission=admission,
                        source_children=source_children,
                        summary_id=summary_id,
                    )
                    if latest_matching.status == "completed" and stable_json(
                        latest_matching.to_dict()
                    ) != stable_json(completed.to_dict()):
                        raise ValueError(
                            "completed consolidation job does not match its deterministic binding"
                        )
                    if existing_summary is not None:
                        _validate_summary_binding(existing_summary, completed, binding, admission)
                        summary = existing_summary
                    _prepare_private_ledger(resolved_job_ledger)
                    _prepare_private_ledger(resolved_summary_ledger)
                    appended_job_records = 0
                    appended_summary_records = 0
                    if existing_summary is None:
                        append_consolidation_summary_record(
                            resolved_summary_ledger,
                            completed,
                            summary,
                        )
                        appended_summary_records = 1
                    if latest_matching.status == "pending":
                        append_consolidation_job_record(resolved_job_ledger, completed)
                        appended_job_records = 1
                    status = (
                        "already_materialized"
                        if appended_job_records == 0 and appended_summary_records == 0
                        else "recovered"
                    )

                event_root_after = str(verified_live_event_state(source_store)["event_merkle_root"])
                if event_root_after != event_root_before:
                    raise ValueError("consolidation source state changed during materialization")
                audit_record = _verified_audit_record(
                    resolved_job_ledger,
                    resolved_summary_ledger,
                    completed.job_id,
                )
                return _materialization_result(
                    status=status,
                    path=path,
                    job_ledger_path=resolved_job_ledger,
                    summary_ledger_path=resolved_summary_ledger,
                    preview=canonical_preview,
                    candidate=selected,
                    job=completed,
                    summary=summary,
                    audit_record=audit_record,
                    event_merkle_root_before=event_root_before,
                    event_merkle_root_after=event_root_after,
                    appended_job_records=appended_job_records,
                    appended_summary_records=appended_summary_records,
                    ledger_recovery=ledger_recovery,
                )
        except Exception as exc:
            recovery_receipts = [
                str(recovery["receipt_path"])
                for recovery in (ledger_recovery["job"], ledger_recovery["summary"])
                if recovery.get("recovered")
            ]
            if recovery_receipts:
                raise ValueError(
                    f"{exc}; durable ledger recovery receipt(s): {', '.join(recovery_receipts)}"
                ) from exc
            raise


def render_live_consolidation_materialization_summary(
    result: Mapping[str, Any],
    *,
    artifact_path: Path | None = None,
) -> str:
    lines = [
        "ZMem consolidation materialization",
        f"Status: {result.get('status')}",
        f"Preview: {(result.get('preview_binding') or {}).get('preview_id')}",
        f"Confirmation: {(result.get('preview_binding') or {}).get('confirmation_id')}",
        f"Candidate: {(result.get('preview_binding') or {}).get('candidate_id')}",
        f"Job: {result.get('job_id')}",
        f"Summary: {result.get('summary_id')}",
        f"Ledger audit: {(result.get('audit') or {}).get('audit_status')}",
        "Ledger tail recovered: "
        + (
            "yes"
            if any(
                bool(((result.get("ledger_recovery") or {}).get(kind) or {}).get("recovered"))
                for kind in ("job", "summary")
            )
            else "no"
        ),
        "Canonical memory written: no",
        "Admission: quarantined, trust 0, authority none",
    ]
    if artifact_path is not None:
        lines.append(f"Result file: {artifact_path}")
    return "\n".join(lines) + "\n"


def render_consolidation_audit_summary(report: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "ZMem consolidation audit",
            f"Jobs: {report.get('job_count', 0)}",
            f"Completed: {report.get('completed_job_count', 0)}",
            f"Summaries: {report.get('summary_record_count', 0)}",
            f"Verified: {report.get('verified_record_count', 0)}",
            f"Incomplete: {report.get('incomplete_record_count', 0)}",
            f"Duplicate summaries: {report.get('duplicate_summary_record_count', 0)}",
            f"Orphan summaries: {report.get('orphan_summary_count', 0)}",
            f"Invalid job histories: {report.get('invalid_job_history_count', 0)}",
        ]
    ) + "\n"


def load_consolidation_artifact(path: Path) -> dict[str, Any]:
    value = json.loads(expand_user_path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("consolidation artifact must be a JSON object")
    return value


def write_consolidation_artifact(
    path: Path,
    value: Mapping[str, Any],
    *,
    force: bool = False,
    protected_paths: tuple[Path, ...] = (),
) -> Path:
    destination = expand_user_path(path)
    validate_consolidation_artifact_destination(
        destination,
        protected_paths=protected_paths,
        force=force,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(value), indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, destination)
        destination.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def validate_consolidation_artifact_destination(
    path: Path,
    *,
    protected_paths: tuple[Path, ...] = (),
    force: bool = False,
) -> None:
    destination = expand_user_path(path)
    _validate_regular_destination(destination, label="consolidation artifact")
    for protected in protected_paths:
        if _paths_alias(destination, expand_user_path(protected)):
            raise ValueError(f"consolidation artifact cannot replace protected path: {protected}")
    if destination.exists() and not force:
        raise FileExistsError(f"consolidation artifact already exists: {destination}")


def default_job_ledger_path(db_path: Path) -> Path:
    return expand_user_path(db_path).parent / "consolidation" / "jobs.jsonl"


def default_summary_ledger_path(db_path: Path) -> Path:
    return expand_user_path(db_path).parent / "consolidation" / "summaries.jsonl"


def default_materialization_result_path(db_path: Path, result: Mapping[str, Any]) -> Path:
    return (
        expand_user_path(db_path).parent
        / "consolidation"
        / "results"
        / f"{result['result_id']}.json"
    )


def _selected_candidate(preview: Mapping[str, Any], candidate_id: str) -> dict[str, Any]:
    matches = [candidate for candidate in preview["candidates"] if candidate["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise ValueError(f"consolidation candidate not found: {candidate_id}")
    return matches[0]


@contextmanager
def _locked_source_snapshot(
    path: Path,
    preview: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> Iterator[tuple[list[dict[str, str]], str, MemoryStore]]:
    store = MemoryStore.open_locked_read_snapshot(path)
    try:
        held_event_state = verified_live_event_state(store)
        fresh = build_live_consolidation_preview(
            path,
            scope=str(preview["scope"]),
            min_source_children=int(preview["min_source_children"]),
            evaluated_at=str(preview["evaluated_at"]),
        )
        if not fresh.get("ok"):
            raise ValueError("consolidation preview revalidation failed")
        if fresh.get("preview_hash") != preview.get("preview_hash"):
            raise ValueError("consolidation preview is stale: live source state changed")
        if held_event_state["event_merkle_root"] != fresh.get("event_merkle_root"):
            raise ValueError("consolidation preview is stale: event root changed during revalidation")
        fresh_candidate = _selected_candidate(fresh, str(candidate["candidate_id"]))
        if stable_json(fresh_candidate) != stable_json(dict(candidate)):
            raise ValueError("consolidation candidate changed during revalidation")

        source_children: list[dict[str, str]] = []
        for memory_id in candidate["source_memory_ids"]:
            row = store.conn.execute(
                "SELECT id, content FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"consolidation source disappeared: {memory_id}")
            content = str(row["content"])
            digest = f"sha256:{sha256_text(content)}"
            if digest != candidate["source_content_digests"].get(memory_id):
                raise ValueError(f"consolidation source digest changed: {memory_id}")
            source_children.append({"child_id": str(memory_id), "content": content})
        yield source_children, str(held_event_state["event_merkle_root"]), store
    finally:
        store.conn.rollback()
        store.conn.close()


def _new_bound_records(
    candidate: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    admission: Mapping[str, Any],
    source_children: list[dict[str, str]],
    job_id: str,
    summary_id: str,
    actor_id: str,
    timestamp: str,
) -> tuple[ConsolidationJobRecord, ConsolidationJobRecord, dict[str, Any]]:
    summarizer = {
        "kind": LIVE_SUMMARIZER_KIND,
        "hosted_llm": False,
        "model_id": None,
        "preview_binding": dict(binding),
        "admission": dict(admission),
        "review": {
            "actor_id": actor_id,
            "confirmed_preview_id": binding["confirmation_id"],
            "reviewed_at": timestamp,
        },
    }
    draft_pending = _pending_job(
        candidate,
        job_id=job_id,
        created_at=timestamp,
        summarizer=summarizer,
    )
    _, draft_summary = materialize_consolidation_summary(
        draft_pending,
        source_children=source_children,
        completed_at=timestamp,
        summary_id=summary_id,
    )
    summarizer["output_summary_content_digest"] = draft_summary["content_digest"]
    pending = _pending_job(
        candidate,
        job_id=job_id,
        created_at=timestamp,
        summarizer=summarizer,
    )
    completed, summary = _bound_summary(
        pending,
        candidate,
        binding=binding,
        admission=admission,
        source_children=source_children,
        completed_at=timestamp,
        summary_id=summary_id,
    )
    return pending, completed, summary


def _records_from_existing_job(
    existing: ConsolidationJobRecord,
    candidate: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    admission: Mapping[str, Any],
    source_children: list[dict[str, str]],
    summary_id: str,
) -> tuple[ConsolidationJobRecord, ConsolidationJobRecord, dict[str, Any]]:
    pending = _pending_job(
        candidate,
        job_id=existing.job_id,
        created_at=existing.created_at,
        summarizer=existing.summarizer,
    )
    if existing.status == "pending" and stable_json(existing.to_dict()) != stable_json(pending.to_dict()):
        raise ValueError("pending consolidation job does not match its deterministic binding")
    completed_at = existing.completed_at or existing.created_at
    completed, summary = _bound_summary(
        pending,
        candidate,
        binding=binding,
        admission=admission,
        source_children=source_children,
        completed_at=completed_at,
        summary_id=summary_id,
    )
    return pending, completed, summary


def _pending_job(
    candidate: Mapping[str, Any],
    *,
    job_id: str,
    created_at: str,
    summarizer: Mapping[str, Any],
) -> ConsolidationJobRecord:
    return create_consolidation_job(
        scope=str(candidate["scope"]),
        summary_level=str(candidate["summary_level"]),
        source_level=str(candidate["source_level"]),
        source_child_ids=list(candidate["source_memory_ids"]),
        created_at=created_at,
        job_id=job_id,
        summarizer=dict(summarizer),
    )


def _bound_summary(
    pending: ConsolidationJobRecord,
    candidate: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    admission: Mapping[str, Any],
    source_children: list[dict[str, str]],
    completed_at: str,
    summary_id: str,
) -> tuple[ConsolidationJobRecord, dict[str, Any]]:
    completed, summary = materialize_consolidation_summary(
        pending,
        source_children=source_children,
        completed_at=completed_at,
        summary_id=summary_id,
    )
    summary["source_child_digests"] = dict(candidate["source_content_digests"])
    summary["source_preview"] = dict(binding)
    summary["admission"] = dict(admission)
    summary["review"] = dict(pending.summarizer["review"])
    summary["canonical_memory_written"] = False
    _validate_summary_binding(summary, completed, binding, admission)
    return completed, summary


def _latest_matching_job(
    jobs: list[ConsolidationJobRecord],
    candidate: Mapping[str, Any],
) -> ConsolidationJobRecord | None:
    expected = (
        candidate["scope"],
        candidate["summary_level"],
        candidate["source_level"],
        tuple(candidate["source_memory_ids"]),
    )
    latest = None
    for job in jobs:
        actual = (job.scope, job.summary_level, job.source_level, tuple(job.source_child_ids))
        if actual == expected:
            latest = job
    return latest


def _preview_binding(preview: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "preview_schema": preview["schema"],
        "preview_id": preview["preview_id"],
        "preview_hash": preview["preview_hash"],
        "confirmation_id": preview["confirmation_id"],
        "confirmation_hash": preview["confirmation_hash"],
        "database": preview["database"],
        "evaluated_at": preview["evaluated_at"],
        "event_merkle_root": preview["event_merkle_root"],
        "candidate_id": candidate["candidate_id"],
        "source_set_hash": candidate["source_set_hash"],
        "source_memory_ids": list(candidate["source_memory_ids"]),
        "source_content_digests": dict(candidate["source_content_digests"]),
        "source_receipt_hashes": dict(candidate["source_receipt_hashes"]),
    }


def _admission_contract(candidate: Mapping[str, Any]) -> dict[str, Any]:
    output = candidate["output_contract"]
    return {
        "status": output["required_initial_status"],
        "trust": output["required_initial_trust"],
        "authority": output["required_initial_authority"],
        "trust_ceiling": output["trust_ceiling"],
        "authority_ceiling": output["authority_ceiling"],
        "non_blocking": True,
        "reversible": True,
        "canonical_memory_write_allowed": False,
    }


def _validate_job_binding(
    job: ConsolidationJobRecord,
    binding: Mapping[str, Any],
    admission: Mapping[str, Any],
) -> None:
    summarizer = job.summarizer
    if summarizer.get("kind") != LIVE_SUMMARIZER_KIND or summarizer.get("hosted_llm") is not False:
        raise ValueError("matching consolidation job has an incompatible summarizer contract")
    if stable_json(summarizer.get("preview_binding")) != stable_json(dict(binding)):
        raise ValueError("matching consolidation job has a different preview binding")
    if stable_json(summarizer.get("admission")) != stable_json(dict(admission)):
        raise ValueError("matching consolidation job has a different admission contract")
    content_digest = summarizer.get("output_summary_content_digest")
    if not isinstance(content_digest, str) or not content_digest.startswith("sha256:"):
        raise ValueError("matching consolidation job is missing its summary content commitment")


def _validate_existing_review(
    job: ConsolidationJobRecord,
    *,
    actor_id: str,
    confirmation_id: str,
) -> None:
    review = job.summarizer.get("review")
    if not isinstance(review, dict):
        raise ValueError("matching consolidation job is missing its review binding")
    if review.get("actor_id") != actor_id:
        raise ValueError("matching consolidation job was confirmed by a different actor")
    if review.get("confirmed_preview_id") != confirmation_id:
        raise ValueError("matching consolidation job has a different preview confirmation")
    if not isinstance(review.get("reviewed_at"), str) or not ISO_UTC_PATTERN.match(review["reviewed_at"]):
        raise ValueError("matching consolidation job has an invalid review timestamp")


def _validate_summary_binding(
    summary: Mapping[str, Any],
    job: ConsolidationJobRecord,
    binding: Mapping[str, Any],
    admission: Mapping[str, Any],
) -> None:
    _validate_job_binding(job, binding, admission)
    if stable_json(summary.get("source_preview")) != stable_json(dict(binding)):
        raise ValueError("consolidation summary preview binding mismatch")
    if stable_json(summary.get("admission")) != stable_json(dict(admission)):
        raise ValueError("consolidation summary admission contract mismatch")
    if summary.get("canonical_memory_written") is not False:
        raise ValueError("consolidation summary canonical-memory boundary mismatch")
    if summary.get("source_child_digests") != binding["source_content_digests"]:
        raise ValueError("consolidation summary source digests mismatch")
    if summary.get("content_digest") != job.summarizer.get("output_summary_content_digest"):
        raise ValueError("consolidation summary content commitment mismatch")
    review = summary.get("review")
    job_review = job.summarizer.get("review")
    if not isinstance(review, dict) or stable_json(review) != stable_json(job_review):
        raise ValueError("consolidation summary review binding mismatch")


def _verified_audit_record(
    job_ledger_path: Path,
    summary_ledger_path: Path,
    job_id: str,
) -> dict[str, Any]:
    report = consolidation_audit_report(job_ledger_path, summary_ledger_path)
    record = next((item for item in report["records"] if item["job_id"] == job_id), None)
    if record is None or record.get("audit_status") != "verified":
        raise ValueError("consolidation ledger audit did not verify the materialized summary")
    return record


def _validate_ledger_destinations(db_path: Path, job_ledger: Path, summary_ledger: Path) -> None:
    _validate_regular_destination(job_ledger, label="consolidation job ledger")
    _validate_regular_destination(summary_ledger, label="consolidation summary ledger")
    if _paths_alias(job_ledger, summary_ledger):
        raise ValueError("consolidation job and summary ledgers must use different paths")
    for ledger in (job_ledger, summary_ledger):
        for protected in database_protected_paths(db_path):
            if _paths_alias(ledger, protected):
                raise ValueError(f"consolidation ledger cannot alias the memory database: {ledger}")


def database_protected_paths(db_path: Path) -> tuple[Path, ...]:
    path = expand_user_path(db_path)
    bases = (path, path.resolve(strict=False))
    protected: list[Path] = []
    for base in bases:
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(f"{base}{suffix}")
            if candidate not in protected:
                protected.append(candidate)
    return tuple(protected)


def _validate_regular_destination(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} cannot be a symlink: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")


def _paths_alias(left: Path, right: Path) -> bool:
    if left.resolve(strict=False) == right.resolve(strict=False):
        return True
    if left.exists() and right.exists():
        try:
            return os.path.samefile(left, right)
        except OSError:
            return False
    return False


def _prepare_private_ledger(path: Path) -> None:
    parent_existed = path.parent.exists()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not parent_existed:
        path.parent.chmod(0o700)
    _validate_regular_destination(path, label="consolidation ledger")
    if path.exists():
        if path.stat().st_mode & 0o077:
            raise ValueError(f"consolidation ledger permissions must be private (0600): {path}")
        return
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    os.close(fd)


def consolidation_ledger_recovery_dir(path: Path) -> Path:
    ledger = expand_user_path(path)
    return ledger.parent / f".{ledger.name}.recovery"


def _recover_uncommitted_ledger_tail(path: Path, *, ledger_kind: str) -> dict[str, Any]:
    if ledger_kind not in {"job", "summary"}:
        raise ValueError(f"unsupported consolidation ledger kind: {ledger_kind}")
    if not path.exists():
        return {"recovered": False, "truncated_bytes": 0}
    if path.is_symlink():
        raise ValueError(f"consolidation ledger cannot be a symlink: {path}")

    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        file_stat = os.fstat(fd)
        if file_stat.st_mode & 0o077:
            raise ValueError(f"consolidation ledger permissions must be private (0600): {path}")
        size = file_stat.st_size
        planned = _planned_recovery_receipt(path, ledger_kind=ledger_kind)
        if planned is not None and size == planned["committed_size"]:
            completed = _completed_recovery_receipt(planned)
            receipt_path = _recovery_receipt_path(path, completed["recovery_id"])
            _write_recovery_receipt(receipt_path, completed)
            return _ledger_recovery_result(completed, receipt_path)
        if planned is not None and size != planned["original_size"]:
            raise ValueError(
                f"consolidation ledger size no longer matches planned recovery: {path}"
            )
        if size == 0:
            return {"recovered": False, "truncated_bytes": 0}
        os.lseek(fd, size - 1, os.SEEK_SET)
        if os.read(fd, 1) == b"\n":
            return {"recovered": False, "truncated_bytes": 0}

        committed_size = _last_committed_ledger_size(fd, size)
        tail = _read_ledger_range(fd, committed_size, size - committed_size)
        recovery_base = {
            "schema": CONSOLIDATION_LEDGER_RECOVERY_SCHEMA,
            "ledger_kind": ledger_kind,
            "ledger_path": str(path.resolve()),
            "commit_marker": "newline",
            "original_size": size,
            "committed_size": committed_size,
            "truncated_bytes": size - committed_size,
            "tail_sha256": f"sha256:{hashlib.sha256(tail).hexdigest()}",
        }
        recovery_id = f"consolidation-ledger-recovery:{sha256_text(stable_json(recovery_base))[:24]}"
        pending = _with_recovery_record_hash(
            {
                **recovery_base,
                "recovery_id": recovery_id,
                "status": "planned",
                "planned_record_hash": None,
            }
        )
        if planned is not None and stable_json(planned) != stable_json(pending):
            raise ValueError(f"consolidation ledger recovery receipt mismatch: {path}")
        receipt_path = _recovery_receipt_path(path, recovery_id)
        _write_recovery_receipt(receipt_path, pending)
        try:
            os.ftruncate(fd, committed_size)
            os.fsync(fd)
            completed = _completed_recovery_receipt(pending)
            _write_recovery_receipt(receipt_path, completed)
        except Exception as exc:
            raise OSError(
                f"consolidation ledger recovery interrupted; inspect {receipt_path}"
            ) from exc
        return _ledger_recovery_result(completed, receipt_path)
    finally:
        os.close(fd)


def _planned_recovery_receipt(path: Path, *, ledger_kind: str) -> dict[str, Any] | None:
    recovery_dir = consolidation_ledger_recovery_dir(path)
    if not recovery_dir.exists():
        return None
    if recovery_dir.is_symlink() or not recovery_dir.is_dir():
        raise ValueError(f"consolidation recovery path must be a directory: {recovery_dir}")
    planned: list[dict[str, Any]] = []
    for receipt_path in sorted(recovery_dir.glob("*.json")):
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise ValueError(f"invalid consolidation recovery receipt path: {receipt_path}")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("schema") != CONSOLIDATION_LEDGER_RECOVERY_SCHEMA:
            raise ValueError(f"invalid consolidation recovery receipt schema: {receipt_path}")
        if not _valid_recovery_record_hash(receipt):
            raise ValueError(f"invalid consolidation recovery receipt hash: {receipt_path}")
        if receipt.get("ledger_path") != str(path.resolve()) or receipt.get("ledger_kind") != ledger_kind:
            raise ValueError(f"consolidation recovery receipt binding mismatch: {receipt_path}")
        if receipt.get("status") == "planned":
            planned.append(receipt)
        elif receipt.get("status") != "completed":
            raise ValueError(f"invalid consolidation recovery receipt status: {receipt_path}")
    if len(planned) > 1:
        raise ValueError(f"multiple planned consolidation ledger recoveries: {path}")
    return planned[0] if planned else None


def _last_committed_ledger_size(fd: int, size: int) -> int:
    cursor = size
    while cursor > 0:
        start = max(0, cursor - 8192)
        os.lseek(fd, start, os.SEEK_SET)
        chunk = os.read(fd, cursor - start)
        newline = chunk.rfind(b"\n")
        if newline >= 0:
            return start + newline + 1
        cursor = start
    return 0


def _read_ledger_range(fd: int, start: int, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    os.lseek(fd, start, os.SEEK_SET)
    while remaining:
        chunk = os.read(fd, min(remaining, 8192))
        if not chunk:
            raise OSError("failed to read uncommitted consolidation ledger tail")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _recovery_receipt_path(path: Path, recovery_id: str) -> Path:
    safe_id = recovery_id.replace(":", "-")
    return consolidation_ledger_recovery_dir(path) / f"{safe_id}.json"


def _completed_recovery_receipt(planned: Mapping[str, Any]) -> dict[str, Any]:
    completed = dict(planned)
    completed["status"] = "completed"
    completed["planned_record_hash"] = planned["record_hash"]
    completed["record_hash"] = None
    return _with_recovery_record_hash(completed)


def _with_recovery_record_hash(record: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(record)
    value["record_hash"] = None
    value["record_hash"] = sha256_text(stable_json(value))
    return value


def _valid_recovery_record_hash(record: Mapping[str, Any]) -> bool:
    expected = record.get("record_hash")
    if not isinstance(expected, str):
        return False
    value = dict(record)
    value["record_hash"] = None
    return expected == sha256_text(stable_json(value))


def _write_recovery_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    parent_existed = path.parent.exists()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not parent_existed:
        path.parent.chmod(0o700)
    elif path.parent.stat().st_mode & 0o077:
        raise ValueError(f"consolidation recovery directory must be private (0700): {path.parent}")
    write_consolidation_artifact(path, receipt, force=True)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _ledger_recovery_result(receipt: Mapping[str, Any], receipt_path: Path) -> dict[str, Any]:
    return {
        "recovered": True,
        "recovery_id": receipt["recovery_id"],
        "receipt_path": str(receipt_path.resolve()),
        "receipt_status": receipt["status"],
        "truncated_bytes": receipt["truncated_bytes"],
        "tail_sha256": receipt["tail_sha256"],
    }


@contextmanager
def _consolidation_ledger_locks(ledger_paths: tuple[Path, ...]) -> Iterator[None]:
    ordered = sorted({path.resolve(strict=False) for path in ledger_paths}, key=str)
    with ExitStack() as stack:
        for path in ordered:
            stack.enter_context(_consolidation_ledger_lock(path))
        yield


@contextmanager
def _consolidation_ledger_lock(job_ledger_path: Path) -> Iterator[None]:
    if fcntl is None:
        raise ValueError("consolidation materialization requires local file-lock support")
    lock_path = job_ledger_path.with_name(f"{job_ledger_path.name}.lock")
    parent_existed = lock_path.parent.exists()
    lock_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not parent_existed:
        lock_path.parent.chmod(0o700)
    _validate_regular_destination(lock_path, label="consolidation ledger lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _materialization_result(
    *,
    status: str,
    path: Path,
    job_ledger_path: Path,
    summary_ledger_path: Path,
    preview: Mapping[str, Any],
    candidate: Mapping[str, Any],
    job: ConsolidationJobRecord,
    summary: Mapping[str, Any],
    audit_record: Mapping[str, Any],
    event_merkle_root_before: str,
    event_merkle_root_after: str,
    appended_job_records: int,
    appended_summary_records: int,
    ledger_recovery: Mapping[str, Any],
) -> dict[str, Any]:
    result = {
        "schema": LIVE_CONSOLIDATION_MATERIALIZATION_SCHEMA,
        "result_id": None,
        "result_hash": None,
        "status": status,
        "database": str(path.resolve()),
        "job_ledger_path": str(job_ledger_path.resolve()),
        "summary_ledger_path": str(summary_ledger_path.resolve()),
        "preview_binding": _preview_binding(preview, candidate),
        "job_id": job.job_id,
        "job_record_hash": sha256_text(stable_json(job.to_dict())),
        "summary_id": summary["summary_id"],
        "summary_content_digest": summary["content_digest"],
        "summary_record_hash": sha256_text(stable_json(dict(summary))),
        "source_count": candidate["source_count"],
        "admission": dict(summary["admission"]),
        "review": dict(summary["review"]),
        "audit": dict(audit_record),
        "database_event_merkle_root_before": event_merkle_root_before,
        "database_event_merkle_root_after": event_merkle_root_after,
        "ledger_writes": {
            "job_records_appended": appended_job_records,
            "summary_records_appended": appended_summary_records,
        },
        "ledger_recovery": dict(ledger_recovery),
        "canonical_memory_written": False,
        "semantic_truth_guaranteed": False,
    }
    digest_payload = dict(result)
    digest_payload["result_id"] = None
    digest_payload["result_hash"] = None
    result_hash = sha256_text(stable_json(digest_payload))
    result["result_hash"] = result_hash
    result["result_id"] = f"consolidation-result:{result_hash[:24]}"
    return result
