from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONSOLIDATION_LEVEL_SCHEMA = "zerker.consolidation_levels.v1"
CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA = "zerker.consolidation_lineage_fixture.v1"
CONSOLIDATION_LINEAGE_KIND = "source-child-to-summary"
CONSOLIDATION_JOB_SCHEMA = "zerker.consolidation_job.v1"
CONSOLIDATION_RECALL_PLAN_SCHEMA = "zerker.consolidation_recall_plan.v1"
CONSOLIDATION_SUMMARY_SCHEMA = "zerker.consolidation_summary.v1"
CONSOLIDATION_JOB_STATUSES = ("pending", "running", "completed", "failed", "cancelled")

_LEVELS: tuple[dict[str, Any], ...] = (
    {
        "id": "turn",
        "rank": 0,
        "label": "turn",
        "description": "A single agent/user exchange or tool-observation unit.",
    },
    {
        "id": "session",
        "rank": 1,
        "label": "session",
        "description": "A bounded work session made from turn-level children.",
    },
    {
        "id": "day",
        "rank": 2,
        "label": "day",
        "description": "A calendar-day rollup made from sessions or selected turns.",
    },
    {
        "id": "week",
        "rank": 3,
        "label": "week",
        "description": "A week-level rollup made from daily or session summaries.",
    },
    {
        "id": "profile_project",
        "rank": 4,
        "label": "profile/project",
        "description": "Stable project or user-profile knowledge distilled from lower-level summaries.",
    },
)


@dataclass(frozen=True)
class ConsolidationJobRecord:
    job_id: str
    status: str
    scope: str
    summary_level: str
    source_level: str
    source_child_ids: tuple[str, ...]
    output_summary_ids: tuple[str, ...]
    non_blocking: bool
    reversible: bool
    lineage_kind: str
    summarizer: dict[str, Any]
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CONSOLIDATION_JOB_SCHEMA,
            "job_id": self.job_id,
            "status": self.status,
            "scope": self.scope,
            "summary_level": self.summary_level,
            "source_level": self.source_level,
            "source_child_ids": list(self.source_child_ids),
            "output_summary_ids": list(self.output_summary_ids),
            "non_blocking": self.non_blocking,
            "reversible": self.reversible,
            "lineage_kind": self.lineage_kind,
            "summarizer": deepcopy(self.summarizer),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


@dataclass(frozen=True)
class ConsolidationPlanCandidate:
    candidate_id: str
    scope: str
    summary_level: str
    source_level: str
    source_child_ids: tuple[str, ...]
    min_source_children: int
    source_children_stable: bool
    has_open_recall_gap: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "scope": self.scope,
            "summary_level": self.summary_level,
            "source_level": self.source_level,
            "source_child_ids": list(self.source_child_ids),
            "trigger": {
                "kind": "child-count-stability-recall-gap",
                "min_source_children": self.min_source_children,
                "source_children_stable": self.source_children_stable,
                "has_open_recall_gap": self.has_open_recall_gap,
            },
        }


def consolidation_levels() -> list[dict[str, Any]]:
    return deepcopy(list(_LEVELS))


def consolidation_lineage_fixture() -> dict[str, Any]:
    return {
        "schema": CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA,
        "fixture_id": "local-consolidation-lineage-fixture-v1",
        "levels_schema": CONSOLIDATION_LEVEL_SCHEMA,
        "levels": consolidation_levels(),
        "summarizer": {
            "kind": "deterministic-fixture",
            "hosted_llm": False,
            "model_id": None,
        },
        "summaries": [
            {
                "summary_id": "summary:session:2026-06-22:payments-routing",
                "summary_level": "session",
                "source_level": "turn",
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "reversible": True,
                "source_child_ids": [
                    "memory:turn:001",
                    "memory:turn:002",
                    "memory:turn:003",
                ],
                "summary_content": "Payment routing work established owners, deploy gates, and next checks.",
            },
            {
                "summary_id": "summary:day:2026-06-22:zmem-launch",
                "summary_level": "day",
                "source_level": "session",
                "lineage_kind": CONSOLIDATION_LINEAGE_KIND,
                "reversible": True,
                "source_child_ids": [
                    "summary:session:2026-06-22:payments-routing",
                    "summary:session:2026-06-22:benchmark-summary",
                ],
                "summary_content": "Daily launch work preserved benchmark status and payment-routing context.",
            },
        ],
    }


def consolidation_recall_planner_fixture() -> dict[str, Any]:
    candidates = [
        ConsolidationPlanCandidate(
            candidate_id="candidate:session:2026-06-23:zmem-alpha",
            scope="project:zmem/session:alpha",
            summary_level="session",
            source_level="turn",
            source_child_ids=("memory:turn:101", "memory:turn:102", "memory:turn:103"),
            min_source_children=3,
            source_children_stable=True,
            has_open_recall_gap=True,
        ),
        ConsolidationPlanCandidate(
            candidate_id="candidate:day:2026-06-23:zmem",
            scope="project:zmem/day:2026-06-23",
            summary_level="day",
            source_level="session",
            source_child_ids=(
                "summary:session:2026-06-23:zmem-alpha",
                "summary:session:2026-06-23:zmem-beta",
            ),
            min_source_children=2,
            source_children_stable=True,
            has_open_recall_gap=True,
        ),
        ConsolidationPlanCandidate(
            candidate_id="candidate:week:2026-w26:zmem",
            scope="project:zmem/week:2026-w26",
            summary_level="week",
            source_level="day",
            source_child_ids=(
                "summary:day:2026-06-22:zmem",
                "summary:day:2026-06-23:zmem",
            ),
            min_source_children=2,
            source_children_stable=False,
            has_open_recall_gap=True,
        ),
        ConsolidationPlanCandidate(
            candidate_id="candidate:profile-project:zmem",
            scope="project:zmem/profile-project",
            summary_level="profile_project",
            source_level="week",
            source_child_ids=(
                "summary:week:2026-w25:zmem",
                "summary:week:2026-w26:zmem",
            ),
            min_source_children=2,
            source_children_stable=True,
            has_open_recall_gap=False,
        ),
    ]
    return {
        "schema": CONSOLIDATION_RECALL_PLAN_SCHEMA,
        "planner_id": "local-consolidation-recall-planner-v1",
        "levels_schema": CONSOLIDATION_LEVEL_SCHEMA,
        "levels": consolidation_levels(),
        "candidates": [candidate.to_dict() for candidate in candidates],
        "queue_rule": {
            "kind": "deterministic-local",
            "queue_when": [
                "source_child_count >= min_source_children",
                "source_children_stable is true",
                "has_open_recall_gap is true",
                "latest matching job is absent or terminal retryable",
            ],
            "skip_latest_statuses": ["pending", "running", "completed"],
            "retry_latest_statuses": ["failed", "cancelled"],
            "hosted_llm": False,
        },
    }


def source_child_ids_for_summary(fixture: dict[str, Any], summary_id: str) -> list[str]:
    for summary in fixture.get("summaries", []):
        if summary.get("summary_id") == summary_id:
            return list(summary["source_child_ids"])
    raise KeyError(summary_id)


def summary_ids_for_source_child(fixture: dict[str, Any], child_id: str) -> list[str]:
    return [
        summary["summary_id"]
        for summary in fixture.get("summaries", [])
        if child_id in summary.get("source_child_ids", [])
    ]


def validate_consolidation_lineage_fixture(fixture: dict[str, Any]) -> bool:
    if fixture.get("schema") != CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA:
        return False

    levels = fixture.get("levels", [])
    level_ranks = {level.get("id"): level.get("rank") for level in levels}
    expected_level_ids = [level["id"] for level in _LEVELS]
    if [level.get("id") for level in levels] != expected_level_ids:
        return False

    summary_ids = set()
    for summary in fixture.get("summaries", []):
        summary_id = summary.get("summary_id")
        source_child_ids = summary.get("source_child_ids")
        summary_level = summary.get("summary_level")
        source_level = summary.get("source_level")
        if not summary_id or summary_id in summary_ids:
            return False
        if not isinstance(source_child_ids, list) or not source_child_ids:
            return False
        if len(source_child_ids) != len(set(source_child_ids)):
            return False
        if summary_id in source_child_ids:
            return False
        if summary.get("lineage_kind") != CONSOLIDATION_LINEAGE_KIND:
            return False
        if summary.get("reversible") is not True:
            return False
        if source_level not in level_ranks or summary_level not in level_ranks:
            return False
        if level_ranks[source_level] >= level_ranks[summary_level]:
            return False
        summary_ids.add(summary_id)

    return bool(summary_ids)


def create_consolidation_job(
    *,
    scope: str,
    summary_level: str,
    source_level: str,
    source_child_ids: list[str],
    created_at: str,
    job_id: str | None = None,
    summarizer: dict[str, Any] | None = None,
) -> ConsolidationJobRecord:
    summarizer_config = deepcopy(
        summarizer
        or {
            "kind": "local-placeholder",
            "hosted_llm": False,
            "model_id": None,
        }
    )
    job = ConsolidationJobRecord(
        job_id=job_id or f"consolidation-job:{uuid.uuid4()}",
        status="pending",
        scope=scope,
        summary_level=summary_level,
        source_level=source_level,
        source_child_ids=tuple(source_child_ids),
        output_summary_ids=(),
        non_blocking=True,
        reversible=True,
        lineage_kind=CONSOLIDATION_LINEAGE_KIND,
        summarizer=summarizer_config,
        created_at=created_at,
        updated_at=created_at,
    )
    _validate_job_record(job)
    return job


def transition_consolidation_job(
    job: ConsolidationJobRecord,
    *,
    status: str,
    updated_at: str,
    output_summary_ids: list[str] | None = None,
    error: str | None = None,
) -> ConsolidationJobRecord:
    next_job = ConsolidationJobRecord(
        job_id=job.job_id,
        status=status,
        scope=job.scope,
        summary_level=job.summary_level,
        source_level=job.source_level,
        source_child_ids=job.source_child_ids,
        output_summary_ids=tuple(output_summary_ids or job.output_summary_ids),
        non_blocking=job.non_blocking,
        reversible=job.reversible,
        lineage_kind=job.lineage_kind,
        summarizer=deepcopy(job.summarizer),
        created_at=job.created_at,
        updated_at=updated_at,
        started_at=(job.started_at or updated_at) if status == "running" else job.started_at,
        completed_at=updated_at if status in {"completed", "failed", "cancelled"} else None,
        error=error,
    )
    _validate_job_record(next_job)
    return next_job


def append_consolidation_job_record(path: Path, job: ConsolidationJobRecord) -> None:
    _validate_job_record(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(job.to_dict(), sort_keys=True))
        handle.write("\n")


def load_consolidation_job_records(path: Path) -> list[ConsolidationJobRecord]:
    if not path.exists():
        return []
    records: list[ConsolidationJobRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("schema") != CONSOLIDATION_JOB_SCHEMA:
                raise ValueError("unsupported consolidation job record schema")
            record = ConsolidationJobRecord(
                job_id=payload["job_id"],
                status=payload["status"],
                scope=payload["scope"],
                summary_level=payload["summary_level"],
                source_level=payload["source_level"],
                source_child_ids=tuple(payload["source_child_ids"]),
                output_summary_ids=tuple(payload.get("output_summary_ids", [])),
                non_blocking=payload["non_blocking"],
                reversible=payload["reversible"],
                lineage_kind=payload["lineage_kind"],
                summarizer=deepcopy(payload["summarizer"]),
                created_at=payload["created_at"],
                updated_at=payload["updated_at"],
                started_at=payload.get("started_at"),
                completed_at=payload.get("completed_at"),
                error=payload.get("error"),
            )
            _validate_job_record(record)
            records.append(record)
    return records


def latest_consolidation_jobs(path: Path) -> dict[str, ConsolidationJobRecord]:
    latest: dict[str, ConsolidationJobRecord] = {}
    for record in load_consolidation_job_records(path):
        latest[record.job_id] = record
    return latest


def plan_consolidation_jobs(
    fixture: dict[str, Any],
    *,
    planned_at: str,
    existing_jobs: list[ConsolidationJobRecord] | None = None,
) -> list[ConsolidationJobRecord]:
    if fixture.get("schema") != CONSOLIDATION_RECALL_PLAN_SCHEMA:
        raise ValueError("unsupported consolidation recall plan schema")
    _validate_levels_fixture(fixture.get("levels", []))

    matching_jobs = _latest_jobs_by_candidate_signature(existing_jobs or [])
    planned_jobs: list[ConsolidationJobRecord] = []
    for candidate_payload in fixture.get("candidates", []):
        candidate = _candidate_from_dict(candidate_payload)
        if len(candidate.source_child_ids) < candidate.min_source_children:
            continue
        if not candidate.source_children_stable:
            continue
        if not candidate.has_open_recall_gap:
            continue
        latest_job = matching_jobs.get(_job_candidate_signature(candidate))
        if latest_job and latest_job.status in {"pending", "running", "completed"}:
            continue
        planned_jobs.append(
            create_consolidation_job(
                scope=candidate.scope,
                summary_level=candidate.summary_level,
                source_level=candidate.source_level,
                source_child_ids=list(candidate.source_child_ids),
                created_at=planned_at,
                job_id=f"consolidation-job:planned:{candidate.candidate_id}",
                summarizer={
                    "kind": "local-recall-planner-placeholder",
                    "hosted_llm": False,
                    "model_id": None,
                    "planner_id": fixture["planner_id"],
                    "candidate_id": candidate.candidate_id,
                },
            )
        )
    return planned_jobs


def materialize_consolidation_summary(
    job: ConsolidationJobRecord,
    *,
    source_children: list[dict[str, str]],
    completed_at: str,
    summary_id: str | None = None,
) -> tuple[ConsolidationJobRecord, dict[str, Any]]:
    if job.status not in {"pending", "running"}:
        raise ValueError("only pending or running consolidation jobs can materialize summaries")

    normalized_children = _normalize_summary_source_children(job, source_children)
    source_child_digests = {
        child["child_id"]: _sha256_text(child["content"]) for child in normalized_children
    }
    resolved_summary_id = summary_id or _deterministic_summary_id(job, source_child_digests)
    summary_text = _render_summary_text(job, normalized_children)
    completed_job = transition_consolidation_job(
        job,
        status="completed",
        updated_at=completed_at,
        output_summary_ids=[resolved_summary_id],
    )
    return completed_job, {
        "schema": CONSOLIDATION_SUMMARY_SCHEMA,
        "summary_id": resolved_summary_id,
        "job_id": completed_job.job_id,
        "scope": completed_job.scope,
        "summary_level": completed_job.summary_level,
        "source_level": completed_job.source_level,
        "source_child_ids": [child["child_id"] for child in normalized_children],
        "source_child_count": len(normalized_children),
        "source_child_digests": source_child_digests,
        "summary_text": summary_text,
        "content_digest": _sha256_text(summary_text),
        "non_blocking": completed_job.non_blocking,
        "reversible": completed_job.reversible,
        "lineage_kind": completed_job.lineage_kind,
        "summarizer": deepcopy(completed_job.summarizer),
        "created_at": completed_at,
    }


def _candidate_from_dict(payload: dict[str, Any]) -> ConsolidationPlanCandidate:
    trigger = payload.get("trigger", {})
    candidate = ConsolidationPlanCandidate(
        candidate_id=payload["candidate_id"],
        scope=payload["scope"],
        summary_level=payload["summary_level"],
        source_level=payload["source_level"],
        source_child_ids=tuple(payload["source_child_ids"]),
        min_source_children=trigger["min_source_children"],
        source_children_stable=trigger["source_children_stable"],
        has_open_recall_gap=trigger["has_open_recall_gap"],
    )
    _validate_plan_candidate(candidate)
    return candidate


def _validate_levels_fixture(levels: list[dict[str, Any]]) -> None:
    expected_level_ids = [level["id"] for level in _LEVELS]
    if [level.get("id") for level in levels] != expected_level_ids:
        raise ValueError("consolidation planner levels must match consolidation levels")


def _validate_plan_candidate(candidate: ConsolidationPlanCandidate) -> None:
    level_ranks = {level["id"]: level["rank"] for level in _LEVELS}
    if not candidate.candidate_id:
        raise ValueError("consolidation plan candidate requires a candidate_id")
    if not candidate.scope:
        raise ValueError("consolidation plan candidate requires a scope")
    if candidate.summary_level not in level_ranks or candidate.source_level not in level_ranks:
        raise ValueError("consolidation plan candidate levels must be known")
    if level_ranks[candidate.source_level] >= level_ranks[candidate.summary_level]:
        raise ValueError("consolidation plan candidates must roll up to a higher level")
    if not candidate.source_child_ids:
        raise ValueError("consolidation plan candidate requires source child ids")
    if len(candidate.source_child_ids) != len(set(candidate.source_child_ids)):
        raise ValueError("consolidation plan candidate source child ids must be unique")
    if candidate.min_source_children < 1:
        raise ValueError("consolidation plan candidate min_source_children must be positive")


def _job_candidate_signature(candidate: ConsolidationPlanCandidate) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        candidate.scope,
        candidate.summary_level,
        candidate.source_level,
        candidate.source_child_ids,
    )


def _existing_job_signature(job: ConsolidationJobRecord) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        job.scope,
        job.summary_level,
        job.source_level,
        job.source_child_ids,
    )


def _latest_jobs_by_candidate_signature(
    jobs: list[ConsolidationJobRecord],
) -> dict[tuple[str, str, str, tuple[str, ...]], ConsolidationJobRecord]:
    latest: dict[tuple[str, str, str, tuple[str, ...]], ConsolidationJobRecord] = {}
    for job in jobs:
        latest[_existing_job_signature(job)] = job
    return latest


def _validate_job_record(job: ConsolidationJobRecord) -> None:
    level_ranks = {level["id"]: level["rank"] for level in _LEVELS}
    if job.status not in CONSOLIDATION_JOB_STATUSES:
        raise ValueError(f"unsupported consolidation job status: {job.status}")
    if not job.job_id:
        raise ValueError("consolidation job requires a job_id")
    if not job.scope:
        raise ValueError("consolidation job requires a scope")
    if not job.source_child_ids:
        raise ValueError("consolidation job requires at least one source child id")
    if len(job.source_child_ids) != len(set(job.source_child_ids)):
        raise ValueError("consolidation job source child ids must be unique")
    if len(job.output_summary_ids) != len(set(job.output_summary_ids)):
        raise ValueError("consolidation job output summary ids must be unique")
    if job.source_level not in level_ranks or job.summary_level not in level_ranks:
        raise ValueError("consolidation job levels must be known")
    if level_ranks[job.source_level] >= level_ranks[job.summary_level]:
        raise ValueError("consolidation jobs must roll up to a higher level")
    if job.lineage_kind != CONSOLIDATION_LINEAGE_KIND:
        raise ValueError("consolidation job lineage kind must be source-child-to-summary")
    if job.non_blocking is not True:
        raise ValueError("consolidation jobs must stay non-blocking")
    if job.reversible is not True:
        raise ValueError("consolidation jobs must stay reversible")
    if job.summarizer.get("hosted_llm"):
        raise ValueError("consolidation jobs cannot require a hosted LLM")
    if job.status == "pending" and job.output_summary_ids:
        raise ValueError("pending consolidation jobs cannot already have output summary ids")
    if job.status in {"completed", "failed", "cancelled"} and job.completed_at is None:
        raise ValueError("terminal consolidation jobs require completed_at")
    if job.status == "completed" and not job.output_summary_ids:
        raise ValueError("completed consolidation jobs require output summary ids")


def _normalize_summary_source_children(
    job: ConsolidationJobRecord,
    source_children: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not source_children:
        raise ValueError("consolidation summary materialization requires source children")

    normalized: list[dict[str, str]] = []
    for child in source_children:
        child_id = child.get("child_id")
        content = child.get("content")
        if not isinstance(child_id, str) or not child_id:
            raise ValueError("consolidation summary source children require child_id")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("consolidation summary source children require non-empty content")
        normalized.append({"child_id": child_id, "content": content.strip()})

    expected_child_ids = list(job.source_child_ids)
    actual_child_ids = [child["child_id"] for child in normalized]
    if actual_child_ids != expected_child_ids:
        raise ValueError("consolidation summary source children must match the job source_child_ids order")
    return normalized


def _render_summary_text(job: ConsolidationJobRecord, source_children: list[dict[str, str]]) -> str:
    child_lines = " ".join(f"[{child['child_id']}] {child['content']}" for child in source_children)
    return (
        f"{job.summary_level.replace('_', '/')} summary for {job.scope} "
        f"from {len(source_children)} {job.source_level} items: {child_lines}"
    )


def _deterministic_summary_id(
    job: ConsolidationJobRecord,
    source_child_digests: dict[str, str],
) -> str:
    identity = {
        "scope": job.scope,
        "summary_level": job.summary_level,
        "source_level": job.source_level,
        "source_child_ids": list(job.source_child_ids),
        "source_child_digests": source_child_digests,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"summary:{job.summary_level}:{digest}"


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
