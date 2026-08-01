from __future__ import annotations

import hashlib
import json
import os
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CONSOLIDATION_LEVEL_SCHEMA = "zerker.consolidation_levels.v1"
CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA = "zerker.consolidation_lineage_fixture.v1"
CONSOLIDATION_LINEAGE_KIND = "source-child-to-summary"
CONSOLIDATION_JOB_SCHEMA = "zerker.consolidation_job.v1"
CONSOLIDATION_RECALL_PLAN_SCHEMA = "zerker.consolidation_recall_plan.v1"
CONSOLIDATION_RECALL_PLAN_REPORT_SCHEMA = "zerker.consolidation_recall_plan_report.v1"
CONSOLIDATION_RECALL_PLAN_LEDGER_REPORT_SCHEMA = "zerker.consolidation_recall_plan_ledger_report.v1"
CONSOLIDATION_PROFILE_AGGREGATION_FIXTURE_SCHEMA = "zerker.consolidation_profile_aggregation_fixture.v1"
CONSOLIDATION_PROFILE_AGGREGATION_REPORT_SCHEMA = "zerker.consolidation_profile_aggregation_report.v1"
CONSOLIDATION_PROFILE_PLANNER_REPORT_SCHEMA = "zerker.consolidation_profile_planner_report.v1"
CONSOLIDATION_PROFILE_PLANNER_LEDGER_REPORT_SCHEMA = "zerker.consolidation_profile_planner_ledger_report.v1"
CONSOLIDATION_SUMMARY_SCHEMA = "zerker.consolidation_summary.v1"
CONSOLIDATION_AUDIT_RECORD_SCHEMA = "zerker.consolidation_audit_record.v1"
CONSOLIDATION_AUDIT_REPORT_SCHEMA = "zerker.consolidation_audit_report.v1"
CONSOLIDATION_LINEAGE_REPORT_SCHEMA = "zerker.consolidation_lineage_report.v1"
CONSOLIDATION_REVERSE_LINEAGE_REPORT_SCHEMA = "zerker.consolidation_reverse_lineage_report.v1"
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
    source_children_materialized: bool
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
                "source_children_materialized": self.source_children_materialized,
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
            source_children_materialized=True,
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
            source_children_materialized=True,
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
            source_children_materialized=False,
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
            source_children_materialized=True,
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


def consolidation_profile_aggregation_fixture() -> dict[str, Any]:
    return {
        "schema": CONSOLIDATION_PROFILE_AGGREGATION_FIXTURE_SCHEMA,
        "fixture_id": "local-consolidation-profile-aggregation-fixture-v1",
        "levels_schema": CONSOLIDATION_LEVEL_SCHEMA,
        "levels": consolidation_levels(),
        "targets": [
            {
                "candidate_id": "candidate:profile-project:person:mallory",
                "subject_id": "person:mallory",
                "subject_kind": "person",
                "scope": "project:zmem/profile-project/person:mallory",
                "summary_level": "profile_project",
                "source_level": "week",
                "min_source_children": 2,
                "source_children_stable": True,
                "source_children_materialized": True,
                "has_open_recall_gap": True,
            },
            {
                "candidate_id": "candidate:profile-project:project:zmem",
                "subject_id": "project:zmem",
                "subject_kind": "project",
                "scope": "project:zmem/profile-project/project:zmem",
                "summary_level": "profile_project",
                "source_level": "week",
                "min_source_children": 2,
                "source_children_stable": True,
                "source_children_materialized": True,
                "has_open_recall_gap": True,
            },
            {
                "candidate_id": "candidate:profile-project:person:ada",
                "subject_id": "person:ada",
                "subject_kind": "person",
                "scope": "project:zmem/profile-project/person:ada",
                "summary_level": "profile_project",
                "source_level": "week",
                "min_source_children": 2,
                "source_children_stable": True,
                "source_children_materialized": True,
                "has_open_recall_gap": True,
            },
        ],
        "claims": [
            {
                "claim_id": "claim:mallory:week25:deploy-owner",
                "summary_id": "summary:week:2026-w25:zmem",
                "subject_id": "person:mallory",
                "subject_kind": "person",
                "facet": "deploy-owner",
                "statement": "Mallory owned deploy approvals during the first launch week.",
            },
            {
                "claim_id": "claim:mallory:week26:deploy-owner",
                "summary_id": "summary:week:2026-w26:zmem",
                "subject_id": "person:mallory",
                "subject_kind": "person",
                "facet": "deploy-owner",
                "statement": "Mallory still owned deploy approvals during the following week.",
            },
            {
                "claim_id": "claim:mallory:week26:rollback-contact",
                "summary_id": "summary:week:2026-w26:zmem",
                "subject_id": "person:mallory",
                "subject_kind": "person",
                "facet": "rollback-contact",
                "statement": "Mallory became the rollback contact for payment-routing work.",
            },
            {
                "claim_id": "claim:zmem:week25:benchmark-status",
                "summary_id": "summary:week:2026-w25:zmem",
                "subject_id": "project:zmem",
                "subject_kind": "project",
                "facet": "benchmark-status",
                "statement": "ZMem still lacked reproduced benchmark deltas in week 25.",
            },
            {
                "claim_id": "claim:zmem:week26:benchmark-status",
                "summary_id": "summary:week:2026-w26:zmem",
                "subject_id": "project:zmem",
                "subject_kind": "project",
                "facet": "benchmark-status",
                "statement": "ZMem still required reproduced benchmark deltas in week 26.",
            },
            {
                "claim_id": "claim:zmem:week26:proof-wedge",
                "summary_id": "summary:week:2026-w26:zmem",
                "subject_id": "project:zmem",
                "subject_kind": "project",
                "facet": "proof-wedge",
                "statement": "ZMem kept the proof-backed local-first memory wedge in week 26.",
            },
            {
                "claim_id": "claim:ada:week26:reviewer",
                "summary_id": "summary:week:2026-w26:zmem",
                "subject_id": "person:ada",
                "subject_kind": "person",
                "facet": "reviewer",
                "statement": "Ada reviewed the launch-week consolidation notes.",
            },
        ],
    }


def consolidation_profile_aggregation_report(fixture: dict[str, Any]) -> dict[str, Any]:
    if fixture.get("schema") != CONSOLIDATION_PROFILE_AGGREGATION_FIXTURE_SCHEMA:
        raise ValueError("unsupported consolidation profile aggregation fixture schema")
    _validate_levels_fixture(fixture.get("levels", []))

    claims_by_subject_id: dict[str, list[dict[str, Any]]] = {}
    for claim in fixture.get("claims", []):
        claims_by_subject_id.setdefault(claim["subject_id"], []).append(deepcopy(claim))

    records: list[dict[str, Any]] = []
    ready_candidates: list[dict[str, Any]] = []
    for target in fixture.get("targets", []):
        subject_claims = claims_by_subject_id.get(target["subject_id"], [])
        source_summary_ids = _dedupe_preserving_order(claim["summary_id"] for claim in subject_claims)
        facet_ids = _dedupe_preserving_order(claim["facet"] for claim in subject_claims)
        claim_ids = [claim["claim_id"] for claim in subject_claims]
        decision = _profile_aggregation_decision(target, source_summary_ids)
        candidate = None
        if decision == "ready":
            candidate = {
                "candidate_id": target["candidate_id"],
                "scope": target["scope"],
                "summary_level": target["summary_level"],
                "source_level": target["source_level"],
                "source_child_ids": source_summary_ids,
                "trigger": {
                    "kind": "profile-fact-aggregation",
                    "min_source_children": target["min_source_children"],
                    "source_children_stable": target["source_children_stable"],
                    "source_children_materialized": target["source_children_materialized"],
                    "has_open_recall_gap": target["has_open_recall_gap"],
                },
            }
            ready_candidates.append(deepcopy(candidate))
        records.append(
            {
                "candidate_id": target["candidate_id"],
                "subject_id": target["subject_id"],
                "subject_kind": target["subject_kind"],
                "scope": target["scope"],
                "summary_level": target["summary_level"],
                "source_level": target["source_level"],
                "source_summary_ids": source_summary_ids,
                "source_summary_count": len(source_summary_ids),
                "facet_ids": facet_ids,
                "facet_count": len(facet_ids),
                "claim_ids": claim_ids,
                "claim_count": len(claim_ids),
                "decision_reason": decision,
                "candidate": candidate,
            }
        )

    return {
        "schema": CONSOLIDATION_PROFILE_AGGREGATION_REPORT_SCHEMA,
        "fixture_id": fixture["fixture_id"],
        "record_count": len(records),
        "ready_candidate_count": len(ready_candidates),
        "skipped_candidate_count": len(records) - len(ready_candidates),
        "ready_candidates": ready_candidates,
        "records": records,
    }


def merge_profile_aggregation_candidates_into_recall_planner(
    planner_fixture: dict[str, Any],
    aggregation_report: dict[str, Any],
) -> dict[str, Any]:
    if planner_fixture.get("schema") != CONSOLIDATION_RECALL_PLAN_SCHEMA:
        raise ValueError("unsupported consolidation recall plan schema")
    if aggregation_report.get("schema") != CONSOLIDATION_PROFILE_AGGREGATION_REPORT_SCHEMA:
        raise ValueError("unsupported consolidation profile aggregation report schema")
    _validate_levels_fixture(planner_fixture.get("levels", []))

    merged_fixture = deepcopy(planner_fixture)
    existing_candidates_by_id = {
        candidate["candidate_id"]: deepcopy(candidate) for candidate in merged_fixture.get("candidates", [])
    }
    for candidate_payload in aggregation_report.get("ready_candidates", []):
        _candidate_from_dict(candidate_payload)
        existing_candidate = existing_candidates_by_id.get(candidate_payload["candidate_id"])
        if existing_candidate is None:
            merged_fixture.setdefault("candidates", []).append(deepcopy(candidate_payload))
            existing_candidates_by_id[candidate_payload["candidate_id"]] = deepcopy(candidate_payload)
            continue
        if existing_candidate != candidate_payload:
            raise ValueError(
                f"consolidation planner candidate id collision: {candidate_payload['candidate_id']}"
            )
    return merged_fixture


def consolidation_profile_aggregation_planner_report(
    planner_fixture: dict[str, Any],
    aggregation_fixture: dict[str, Any],
    *,
    planned_at: str,
    existing_jobs: list[ConsolidationJobRecord] | None = None,
) -> dict[str, Any]:
    aggregation_report = consolidation_profile_aggregation_report(aggregation_fixture)
    return _consolidation_profile_planner_report_from_aggregation_report(
        planner_fixture,
        aggregation_report,
        planned_at=planned_at,
        existing_jobs=existing_jobs,
        schema=CONSOLIDATION_PROFILE_PLANNER_REPORT_SCHEMA,
    )


def consolidation_profile_aggregation_planner_ledger_report(
    planner_fixture: dict[str, Any],
    aggregation_fixture: dict[str, Any],
    *,
    planned_at: str,
    job_ledger_path: Path,
    summary_ledger_path: Path,
) -> dict[str, Any]:
    aggregation_report = consolidation_profile_aggregation_report(aggregation_fixture)
    latest_summaries = latest_consolidation_summaries(summary_ledger_path)
    existing_jobs = load_consolidation_job_records(job_ledger_path)
    summary_audit_state = _summary_audit_state_by_summary_id(
        consolidation_audit_report(job_ledger_path, summary_ledger_path)["records"]
    )
    report = _consolidation_profile_planner_report_from_aggregation_report(
        planner_fixture,
        _profile_aggregation_report_with_summary_ledger_state(
            aggregation_report,
            latest_summaries=latest_summaries,
            summary_audit_state=summary_audit_state,
        ),
        planned_at=planned_at,
        existing_jobs=existing_jobs,
        schema=CONSOLIDATION_PROFILE_PLANNER_LEDGER_REPORT_SCHEMA,
    )
    report["job_history_count"] = len(existing_jobs)
    report["materialized_summary_count"] = len(latest_summaries)
    return report


def _consolidation_profile_planner_report_from_aggregation_report(
    planner_fixture: dict[str, Any],
    aggregation_report: dict[str, Any],
    *,
    planned_at: str,
    existing_jobs: list[ConsolidationJobRecord] | None,
    schema: str,
) -> dict[str, Any]:
    merged_fixture = merge_profile_aggregation_candidates_into_recall_planner(
        planner_fixture,
        aggregation_report,
    )
    planner_report = consolidation_recall_plan_report(
        merged_fixture,
        planned_at=planned_at,
        existing_jobs=existing_jobs,
    )
    planner_records_by_candidate_id = {
        record["candidate_id"]: deepcopy(record) for record in planner_report["records"]
    }

    profile_planned_jobs: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    queued_candidate_count = 0
    blocked_ready_candidate_count = 0
    for aggregation_record in aggregation_report["records"]:
        candidate_payload = aggregation_record["candidate"]
        planner_record = None
        planner_decision = "not-applicable"
        planner_decision_reason = "aggregation-not-ready"
        planner_planned_job_id = None
        planner_retrying_terminal_job = False
        planner_latest_matching_job = None
        if candidate_payload is not None:
            planner_record = planner_records_by_candidate_id.get(aggregation_record["candidate_id"])
            if planner_record is None:
                raise ValueError(
                    "merged consolidation planner report is missing a ready aggregation candidate"
                )
            planner_decision = planner_record["decision"]
            planner_decision_reason = planner_record["decision_reason"]
            planner_planned_job_id = planner_record["planned_job_id"]
            planner_retrying_terminal_job = planner_record["retrying_terminal_job"]
            planner_latest_matching_job = deepcopy(planner_record["latest_matching_job"])
            if planner_record["planned_job_id"] is not None:
                queued_candidate_count += 1
                profile_planned_jobs.append(
                    next(
                        deepcopy(job)
                        for job in planner_report["planned_jobs"]
                        if job["job_id"] == planner_record["planned_job_id"]
                    )
                )
            else:
                blocked_ready_candidate_count += 1
        records.append(
            {
                **deepcopy(aggregation_record),
                "planner_decision": planner_decision,
                "planner_decision_reason": planner_decision_reason,
                "planner_planned_job_id": planner_planned_job_id,
                "planner_retrying_terminal_job": planner_retrying_terminal_job,
                "planner_latest_matching_job": planner_latest_matching_job,
            }
        )

    return {
        "schema": schema,
        "fixture_id": aggregation_report["fixture_id"],
        "planner_id": planner_fixture["planner_id"],
        "planned_at": planned_at,
        "record_count": len(records),
        "ready_candidate_count": aggregation_report["ready_candidate_count"],
        "queued_candidate_count": queued_candidate_count,
        "blocked_ready_candidate_count": blocked_ready_candidate_count,
        "skipped_candidate_count": aggregation_report["skipped_candidate_count"],
        "planned_jobs": profile_planned_jobs,
        "records": records,
    }


def _profile_aggregation_report_with_summary_ledger_state(
    aggregation_report: dict[str, Any],
    *,
    latest_summaries: dict[str, dict[str, Any]],
    summary_audit_state: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    materialized_summary_ids = set(latest_summaries)
    adjusted_report = deepcopy(aggregation_report)
    adjusted_ready_candidates: list[dict[str, Any]] = []

    for record in adjusted_report["records"]:
        source_summary_ids = list(record.get("source_summary_ids", []))
        record["source_summary_dependencies"] = _source_summary_dependencies(
            source_summary_ids,
            latest_summaries=latest_summaries,
            summary_audit_state=summary_audit_state,
        )
        record["materialized_source_summary_ids"] = [
            summary_id for summary_id in source_summary_ids if summary_id in materialized_summary_ids
        ]
        record["missing_source_summary_ids"] = [
            summary_id for summary_id in source_summary_ids if summary_id not in materialized_summary_ids
        ]
        record["source_summary_audit_statuses"] = {
            summary_id: summary_audit_state.get(summary_id, {}).get("audit_status", "unknown")
            for summary_id in record["materialized_source_summary_ids"]
        }
        record["verified_source_summary_ids"] = [
            summary_id
            for summary_id in record["materialized_source_summary_ids"]
            if record["source_summary_audit_statuses"][summary_id] == "verified"
        ]
        record["unverified_source_summary_ids"] = [
            summary_id
            for summary_id in record["materialized_source_summary_ids"]
            if record["source_summary_audit_statuses"][summary_id] != "verified"
        ]
        record["source_summary_gate_reason"] = _source_summary_gate_reason(record)
        candidate = record.get("candidate")
        if candidate is None:
            continue
        candidate["trigger"]["source_children_materialized"] = (
            record["source_summary_gate_reason"] == "all-source-summaries-verified"
        )
        candidate["trigger"]["source_children_verified"] = not record["unverified_source_summary_ids"]
        adjusted_ready_candidates.append(deepcopy(candidate))

    adjusted_report["ready_candidates"] = adjusted_ready_candidates
    return adjusted_report


def _summary_audit_state_by_summary_id(audit_records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for record in audit_records:
        summaries_by_id = {
            summary["summary_id"]: summary for summary in record.get("summaries", [])
        }
        summary_ids = _dedupe_preserving_order(
            list(record.get("expected_output_summary_ids", []))
            + list(record.get("materialized_summary_ids", []))
        )
        for summary_id in summary_ids:
            summary_view = summaries_by_id.get(summary_id, {})
            state[summary_id] = {
                "job_id": record["job_id"],
                "job_status": record["status"],
                "job_completed_at": record.get("completed_at"),
                "audit_status": record["audit_status"],
                "summary_level": record["summary_level"],
                "source_level": record["source_level"],
                "source_child_ids": list(record.get("source_child_ids", [])),
                "source_child_count": len(record.get("source_child_ids", [])),
                "non_blocking": record.get("non_blocking"),
                "lineage_kind": record.get("lineage_kind"),
                "reversible": record.get("reversible"),
                "expected_output_summary_ids": list(record.get("expected_output_summary_ids", [])),
                "materialized_summary_ids": list(record.get("materialized_summary_ids", [])),
                "missing_output_summary_ids": list(record.get("missing_output_summary_ids", [])),
                "unexpected_output_summary_ids": list(record.get("unexpected_output_summary_ids", [])),
                "summary_scope_mismatches": list(record.get("summary_scope_mismatches", [])),
                "summary_mismatch_reasons": list(
                    record.get("summary_mismatch_reasons", {}).get(summary_id, [])
                ),
                "materialized_job_id": summary_view.get("job_id"),
                "materialized_created_at": summary_view.get("created_at"),
            }
    return state


def _recall_plan_fixture_with_summary_ledger_state(
    fixture: dict[str, Any],
    *,
    latest_summaries: dict[str, dict[str, Any]],
    summary_audit_state: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    adjusted_fixture = deepcopy(fixture)
    adjusted_candidates: list[dict[str, Any]] = []
    candidate_records: list[dict[str, Any]] = []

    for candidate_payload in fixture.get("candidates", []):
        candidate = deepcopy(candidate_payload)
        source_summary_ids = list(candidate.get("source_child_ids", [])) if candidate["source_level"] != "turn" else []
        if source_summary_ids:
            source_summary_dependencies = _source_summary_dependencies(
                source_summary_ids,
                latest_summaries=latest_summaries,
                summary_audit_state=summary_audit_state,
            )
            materialized_source_summary_ids = [
                summary_id for summary_id in source_summary_ids if summary_id in latest_summaries
            ]
            missing_source_summary_ids = [
                summary_id for summary_id in source_summary_ids if summary_id not in latest_summaries
            ]
            source_summary_audit_statuses = {
                summary_id: summary_audit_state.get(summary_id, {}).get("audit_status", "unknown")
                for summary_id in materialized_source_summary_ids
            }
            verified_source_summary_ids = [
                summary_id
                for summary_id in materialized_source_summary_ids
                if source_summary_audit_statuses[summary_id] == "verified"
            ]
            unverified_source_summary_ids = [
                summary_id
                for summary_id in materialized_source_summary_ids
                if source_summary_audit_statuses[summary_id] != "verified"
            ]
            source_summary_gate_reason = _source_summary_gate_reason(
                {
                    "missing_source_summary_ids": missing_source_summary_ids,
                    "unverified_source_summary_ids": unverified_source_summary_ids,
                }
            )
            candidate["trigger"]["source_children_materialized"] = (
                source_summary_gate_reason == "all-source-summaries-verified"
            )
            candidate["trigger"]["source_children_verified"] = not unverified_source_summary_ids
        else:
            source_summary_dependencies = []
            materialized_source_summary_ids = []
            missing_source_summary_ids = []
            verified_source_summary_ids = []
            unverified_source_summary_ids = []
            source_summary_audit_statuses = {}
            source_summary_gate_reason = "leaf-source-children"

        adjusted_candidates.append(candidate)
        candidate_records.append(
            {
                "candidate_id": candidate["candidate_id"],
                "materialized_source_summary_ids": materialized_source_summary_ids,
                "missing_source_summary_ids": missing_source_summary_ids,
                "verified_source_summary_ids": verified_source_summary_ids,
                "unverified_source_summary_ids": unverified_source_summary_ids,
                "source_summary_audit_statuses": source_summary_audit_statuses,
                "source_summary_gate_reason": source_summary_gate_reason,
                "source_summary_dependencies": source_summary_dependencies,
            }
        )

    adjusted_fixture["candidates"] = adjusted_candidates
    return adjusted_fixture, candidate_records


def _source_summary_gate_reason(record: dict[str, Any]) -> str:
    if record["missing_source_summary_ids"]:
        return "missing-source-summaries"
    if record["unverified_source_summary_ids"]:
        return "unverified-source-summaries"
    return "all-source-summaries-verified"


def _source_summary_dependencies(
    source_summary_ids: list[str],
    *,
    latest_summaries: dict[str, dict[str, Any]],
    summary_audit_state: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    dependencies: list[dict[str, Any]] = []
    for summary_id in source_summary_ids:
        summary = latest_summaries.get(summary_id)
        audit_state = summary_audit_state.get(summary_id, {})
        materialized = summary is not None
        audit_status = audit_state.get("audit_status", "missing" if not materialized else "unknown")
        if materialized and audit_status == "verified":
            gate_status = "verified"
        elif materialized:
            gate_status = "unverified"
        else:
            gate_status = "missing"
        dependencies.append(
            {
                "summary_id": summary_id,
                "materialized": materialized,
                "gate_status": gate_status,
                "audit_status": audit_status,
                "job_id": audit_state.get("job_id"),
                "job_status": audit_state.get("job_status"),
                "job_completed_at": audit_state.get("job_completed_at"),
                "summary_level": (summary or {}).get("summary_level") or audit_state.get("summary_level"),
                "source_level": (summary or {}).get("source_level") or audit_state.get("source_level"),
                "source_child_ids": list((summary or {}).get("source_child_ids") or audit_state.get("source_child_ids", [])),
                "source_child_count": (summary or {}).get("source_child_count", audit_state.get("source_child_count", 0)),
                "non_blocking": (summary or {}).get("non_blocking", audit_state.get("non_blocking")),
                "lineage_kind": (summary or {}).get("lineage_kind") or audit_state.get("lineage_kind"),
                "reversible": (summary or {}).get("reversible", audit_state.get("reversible")),
                "expected_output_summary_ids": list(audit_state.get("expected_output_summary_ids", [])),
                "materialized_summary_ids": list(audit_state.get("materialized_summary_ids", [])),
                "missing_output_summary_ids": list(audit_state.get("missing_output_summary_ids", [])),
                "unexpected_output_summary_ids": list(audit_state.get("unexpected_output_summary_ids", [])),
                **(
                    {
                        "materialized_job_id": (summary or {}).get("job_id")
                        or audit_state.get("materialized_job_id")
                    }
                    if ((summary or {}).get("job_id") or audit_state.get("materialized_job_id"))
                    else {}
                ),
                **(
                    {
                        "materialized_created_at": (summary or {}).get("created_at")
                        or audit_state.get("materialized_created_at")
                    }
                    if ((summary or {}).get("created_at") or audit_state.get("materialized_created_at"))
                    else {}
                ),
                **(
                    {"source_child_digests": deepcopy(summary.get("source_child_digests"))}
                    if isinstance((summary or {}).get("source_child_digests"), dict)
                    else {}
                ),
                "content_digest": (summary or {}).get("content_digest"),
                **(
                    {"mismatch_reasons": list(audit_state.get("summary_mismatch_reasons", []))}
                    if audit_state.get("summary_mismatch_reasons")
                    else {}
                ),
                **(
                    {"summary_scope_mismatches": list(audit_state.get("summary_scope_mismatches", []))}
                    if audit_state.get("summary_scope_mismatches")
                    else {}
                ),
            }
        )
    return dependencies


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
    _append_json_line(path, job.to_dict())


def _append_json_line(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"consolidation ledger cannot be a symlink: {path}")
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    original_size = os.fstat(fd).st_size
    try:
        payload = (json.dumps(dict(value), sort_keys=True) + "\n").encode("utf-8")
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("failed to append consolidation ledger record")
            view = view[written:]
        os.fsync(fd)
    except BaseException:
        try:
            os.ftruncate(fd, original_size)
            os.fsync(fd)
        except OSError as rollback_error:
            raise OSError(
                f"failed to restore consolidation ledger after an interrupted append: {path}"
            ) from rollback_error
        raise
    finally:
        os.close(fd)


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
        latest_job = matching_jobs.get(_job_candidate_signature(candidate))
        decision = _candidate_queue_decision(candidate, latest_job)
        if not decision["queue"]:
            continue
        planned_jobs.append(_planned_job_for_candidate(candidate, planned_at=planned_at, planner_id=fixture["planner_id"]))
    return planned_jobs


def consolidation_recall_plan_report(
    fixture: dict[str, Any],
    *,
    planned_at: str,
    existing_jobs: list[ConsolidationJobRecord] | None = None,
) -> dict[str, Any]:
    if fixture.get("schema") != CONSOLIDATION_RECALL_PLAN_SCHEMA:
        raise ValueError("unsupported consolidation recall plan schema")
    _validate_levels_fixture(fixture.get("levels", []))

    matching_jobs = _latest_jobs_by_candidate_signature(existing_jobs or [])
    planned_jobs: list[ConsolidationJobRecord] = []
    records: list[dict[str, Any]] = []
    for candidate_payload in fixture.get("candidates", []):
        candidate = _candidate_from_dict(candidate_payload)
        latest_job = matching_jobs.get(_job_candidate_signature(candidate))
        decision = _candidate_queue_decision(candidate, latest_job)
        planned_job = None
        if decision["queue"]:
            planned_job = _planned_job_for_candidate(candidate, planned_at=planned_at, planner_id=fixture["planner_id"])
            planned_jobs.append(planned_job)
        records.append(
            {
                **candidate.to_dict(),
                "decision": "queued" if decision["queue"] else "skipped",
                "decision_reason": decision["reason"],
                "retrying_terminal_job": decision["retrying_terminal_job"],
                "planned_job_id": None if planned_job is None else planned_job.job_id,
                "latest_matching_job": _job_report_view(latest_job),
            }
        )

    return {
        "schema": CONSOLIDATION_RECALL_PLAN_REPORT_SCHEMA,
        "planner_id": fixture["planner_id"],
        "planned_at": planned_at,
        "candidate_count": len(records),
        "queued_job_count": len(planned_jobs),
        "skipped_candidate_count": len(records) - len(planned_jobs),
        "planned_jobs": [job.to_dict() for job in planned_jobs],
        "records": records,
    }


def consolidation_recall_plan_ledger_report(
    fixture: dict[str, Any],
    *,
    planned_at: str,
    job_ledger_path: Path,
    summary_ledger_path: Path,
) -> dict[str, Any]:
    if fixture.get("schema") != CONSOLIDATION_RECALL_PLAN_SCHEMA:
        raise ValueError("unsupported consolidation recall plan schema")
    _validate_levels_fixture(fixture.get("levels", []))

    latest_summaries = latest_consolidation_summaries(summary_ledger_path)
    existing_jobs = load_consolidation_job_records(job_ledger_path)
    summary_audit_state = _summary_audit_state_by_summary_id(
        consolidation_audit_report(job_ledger_path, summary_ledger_path)["records"]
    )
    adjusted_fixture, candidate_records = _recall_plan_fixture_with_summary_ledger_state(
        fixture,
        latest_summaries=latest_summaries,
        summary_audit_state=summary_audit_state,
    )
    planner_report = consolidation_recall_plan_report(
        adjusted_fixture,
        planned_at=planned_at,
        existing_jobs=existing_jobs,
    )
    candidate_records_by_id = {
        record["candidate_id"]: deepcopy(record) for record in candidate_records
    }

    records: list[dict[str, Any]] = []
    for planner_record in planner_report["records"]:
        candidate_record = candidate_records_by_id.get(planner_record["candidate_id"])
        if candidate_record is None:
            raise ValueError("ledger-backed consolidation planner report is missing a candidate record")
        records.append(
            {
                **deepcopy(planner_record),
                "materialized_source_summary_ids": candidate_record["materialized_source_summary_ids"],
                "missing_source_summary_ids": candidate_record["missing_source_summary_ids"],
                "verified_source_summary_ids": candidate_record["verified_source_summary_ids"],
                "unverified_source_summary_ids": candidate_record["unverified_source_summary_ids"],
                "source_summary_audit_statuses": deepcopy(candidate_record["source_summary_audit_statuses"]),
                "source_summary_gate_reason": candidate_record["source_summary_gate_reason"],
                "source_summary_dependencies": deepcopy(candidate_record["source_summary_dependencies"]),
            }
        )

    return {
        **planner_report,
        "schema": CONSOLIDATION_RECALL_PLAN_LEDGER_REPORT_SCHEMA,
        "job_history_count": len(existing_jobs),
        "materialized_summary_count": len(latest_summaries),
        "records": records,
    }


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


def append_consolidation_summary_record(
    path: Path,
    job: ConsolidationJobRecord,
    summary: dict[str, Any],
) -> None:
    _validate_summary_record(job, summary)
    _append_json_line(path, summary)


def load_consolidation_summary_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            summary_id = payload.get("summary_id")
            if not isinstance(summary_id, str) or not summary_id:
                raise ValueError("consolidation summary record requires summary_id")
            if payload.get("schema") != CONSOLIDATION_SUMMARY_SCHEMA:
                raise ValueError("unsupported consolidation summary record schema")
            source_child_ids = payload.get("source_child_ids")
            if not isinstance(source_child_ids, list) or not source_child_ids:
                raise ValueError("consolidation summary record requires source_child_ids")
            if len(source_child_ids) != len(set(source_child_ids)):
                raise ValueError("consolidation summary record source_child_ids must be unique")
            records.append(deepcopy(payload))
    return records


def latest_consolidation_summaries(path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in load_consolidation_summary_records(path):
        latest[record["summary_id"]] = record
    return latest


def consolidation_audit_report(
    job_ledger_path: Path,
    summary_ledger_path: Path,
) -> dict[str, Any]:
    job_history = load_consolidation_job_records(job_ledger_path)
    summary_history = load_consolidation_summary_records(summary_ledger_path)
    latest_jobs: dict[str, ConsolidationJobRecord] = {}
    job_records_by_id: dict[str, list[ConsolidationJobRecord]] = {}
    for job in job_history:
        latest_jobs[job.job_id] = job
        job_records_by_id.setdefault(job.job_id, []).append(job)
    latest_summaries: dict[str, dict[str, Any]] = {}
    summary_record_counts: dict[str, int] = {}
    for summary in summary_history:
        latest_summaries[summary["summary_id"]] = summary
        summary_record_counts[summary["summary_id"]] = summary_record_counts.get(summary["summary_id"], 0) + 1
    duplicate_summary_ids = sorted(
        summary_id for summary_id, count in summary_record_counts.items() if count > 1
    )
    orphan_summaries = [summary for summary in summary_history if summary["job_id"] not in latest_jobs]
    invalid_job_history_ids = sorted(
        job_id
        for job_id, records in job_records_by_id.items()
        if not _valid_consolidation_job_history(records)
    )
    summaries_by_job: dict[str, list[dict[str, Any]]] = {}
    for summary in latest_summaries.values():
        summaries_by_job.setdefault(summary["job_id"], []).append(deepcopy(summary))

    records: list[dict[str, Any]] = []
    verified_record_count = 0
    incomplete_record_count = 0
    for job in latest_jobs.values():
        job_summaries = list(summaries_by_job.get(job.job_id, []))
        seen_summary_ids = {summary["summary_id"] for summary in job_summaries}
        for summary_id in job.output_summary_ids:
            summary = latest_summaries.get(summary_id)
            if summary is None or summary_id in seen_summary_ids:
                continue
            job_summaries.append(deepcopy(summary))
            seen_summary_ids.add(summary_id)
        records.append(
            _consolidation_audit_record(
                job,
                job_summaries,
                duplicate_summary_ids={
                    summary_id
                    for summary_id in duplicate_summary_ids
                    if summary_id in seen_summary_ids
                    and job.summarizer.get("kind") == "deterministic-live-ledger-v1"
                },
                invalid_job_history=job.job_id in invalid_job_history_ids,
            )
        )
        if records[-1]["audit_status"] == "verified":
            verified_record_count += 1
        else:
            incomplete_record_count += 1

    incomplete_record_count += len(orphan_summaries)

    return {
        "schema": CONSOLIDATION_AUDIT_REPORT_SCHEMA,
        "job_count": len(latest_jobs),
        "completed_job_count": sum(1 for job in latest_jobs.values() if job.status == "completed"),
        "summary_record_count": len(latest_summaries),
        "summary_history_record_count": len(summary_history),
        "duplicate_summary_record_count": len(summary_history) - len(latest_summaries),
        "duplicate_summary_ids": duplicate_summary_ids,
        "orphan_summary_count": len(orphan_summaries),
        "orphan_summary_ids": sorted(summary["summary_id"] for summary in orphan_summaries),
        "invalid_job_history_count": len(invalid_job_history_ids),
        "invalid_job_history_ids": invalid_job_history_ids,
        "verified_record_count": verified_record_count,
        "incomplete_record_count": incomplete_record_count,
        "records": records,
    }


def _valid_consolidation_job_history(records: list[ConsolidationJobRecord]) -> bool:
    if not records or records[0].status != "pending":
        return False
    statuses = [record.status for record in records]
    if len(statuses) != len(set(statuses)):
        return False
    allowed_transitions = {
        "pending": {"running", "completed", "failed", "cancelled"},
        "running": {"completed", "failed", "cancelled"},
        "completed": set(),
        "failed": set(),
        "cancelled": set(),
    }
    if any(
        current.status not in allowed_transitions[previous.status]
        for previous, current in zip(records, records[1:])
    ):
        return False
    immutable = _consolidation_job_immutable_fields(records[0])
    return all(_consolidation_job_immutable_fields(record) == immutable for record in records[1:])


def _consolidation_job_immutable_fields(job: ConsolidationJobRecord) -> tuple[Any, ...]:
    return (
        job.job_id,
        job.scope,
        job.summary_level,
        job.source_level,
        job.source_child_ids,
        job.non_blocking,
        job.reversible,
        job.lineage_kind,
        json.dumps(job.summarizer, sort_keys=True, separators=(",", ":")),
        job.created_at,
    )


def consolidation_summary_lineage_report(
    summary_ledger_path: Path,
    summary_id: str,
) -> dict[str, Any]:
    latest_summaries = latest_consolidation_summaries(summary_ledger_path)
    root_summary = latest_summaries.get(summary_id)
    if root_summary is None:
        raise KeyError(summary_id)

    node = _build_consolidation_lineage_node(
        root_summary,
        latest_summaries=latest_summaries,
        ancestry=(),
    )
    return {
        "schema": CONSOLIDATION_LINEAGE_REPORT_SCHEMA,
        "summary_id": summary_id,
        "summary_level": root_summary["summary_level"],
        "source_level": root_summary["source_level"],
        "leaf_source_child_ids": list(node["leaf_source_child_ids"]),
        "transitive_summary_ids": list(node["transitive_summary_ids"]),
        "missing_summary_ids": list(node["missing_summary_ids"]),
        "cycle_summary_ids": list(node["cycle_summary_ids"]),
        "reversible": root_summary["reversible"],
        "lineage_kind": root_summary["lineage_kind"],
        "node": node,
    }


def consolidation_summary_reverse_lineage_report(
    summary_ledger_path: Path,
    child_id: str,
) -> dict[str, Any]:
    latest_summaries = latest_consolidation_summaries(summary_ledger_path)
    summaries_by_id = {summary["summary_id"]: summary for summary in latest_summaries.values()}
    parent_index = _reverse_summary_parent_index(latest_summaries)
    direct_parent_summaries = parent_index.get(child_id, [])
    paths: list[dict[str, Any]] = []
    transitive_summary_ids: list[str] = []
    root_summary_ids: list[str] = []
    cycle_summary_ids: list[str] = []

    for direct_parent in direct_parent_summaries:
        _collect_reverse_lineage_paths(
            direct_parent,
            summaries_by_id=summaries_by_id,
            parent_index=parent_index,
            ancestry=(),
            paths=paths,
            transitive_summary_ids=transitive_summary_ids,
            root_summary_ids=root_summary_ids,
            cycle_summary_ids=cycle_summary_ids,
        )

    return {
        "schema": CONSOLIDATION_REVERSE_LINEAGE_REPORT_SCHEMA,
        "child_id": child_id,
        "direct_summary_ids": [summary["summary_id"] for summary in direct_parent_summaries],
        "transitive_summary_ids": list(dict.fromkeys(transitive_summary_ids)),
        "root_summary_ids": list(dict.fromkeys(root_summary_ids)),
        "cycle_summary_ids": list(dict.fromkeys(cycle_summary_ids)),
        "paths": paths,
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
        source_children_materialized=trigger.get("source_children_materialized", True),
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


def _candidate_queue_decision(
    candidate: ConsolidationPlanCandidate,
    latest_job: ConsolidationJobRecord | None,
) -> dict[str, Any]:
    if len(candidate.source_child_ids) < candidate.min_source_children:
        return {"queue": False, "reason": "insufficient-source-children", "retrying_terminal_job": False}
    if not candidate.source_children_stable:
        return {"queue": False, "reason": "source-children-not-stable", "retrying_terminal_job": False}
    if candidate.source_level != "turn" and not candidate.source_children_materialized:
        return {"queue": False, "reason": "source-summaries-not-materialized", "retrying_terminal_job": False}
    if not candidate.has_open_recall_gap:
        return {"queue": False, "reason": "no-open-recall-gap", "retrying_terminal_job": False}
    if latest_job is None:
        return {"queue": True, "reason": "ready", "retrying_terminal_job": False}
    if latest_job.status in {"pending", "running", "completed"}:
        return {
            "queue": False,
            "reason": f"existing-{latest_job.status}-job",
            "retrying_terminal_job": False,
        }
    return {
        "queue": True,
        "reason": f"retry-after-{latest_job.status}-job",
        "retrying_terminal_job": True,
    }


def _profile_aggregation_decision(target: dict[str, Any], source_summary_ids: list[str]) -> str:
    if len(source_summary_ids) < target["min_source_children"]:
        return "insufficient-source-summaries"
    if not target["source_children_stable"]:
        return "source-children-not-stable"
    if not target["source_children_materialized"]:
        return "source-summaries-not-materialized"
    if not target["has_open_recall_gap"]:
        return "no-open-recall-gap"
    return "ready"


def _dedupe_preserving_order(values: Any) -> list[Any]:
    return list(dict.fromkeys(values))


def _planned_job_for_candidate(
    candidate: ConsolidationPlanCandidate,
    *,
    planned_at: str,
    planner_id: str,
) -> ConsolidationJobRecord:
    return create_consolidation_job(
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
            "planner_id": planner_id,
            "candidate_id": candidate.candidate_id,
        },
    )


def _job_report_view(job: ConsolidationJobRecord | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "job_id": job.job_id,
        "status": job.status,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
        "output_summary_ids": list(job.output_summary_ids),
        "error": job.error,
    }


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


def _validate_summary_record(job: ConsolidationJobRecord, summary: dict[str, Any]) -> None:
    _validate_job_record(job)
    if job.status != "completed":
        raise ValueError("consolidation summary ledger requires a completed job")
    if summary.get("schema") != CONSOLIDATION_SUMMARY_SCHEMA:
        raise ValueError("unsupported consolidation summary record schema")
    summary_id = summary.get("summary_id")
    if not isinstance(summary_id, str) or not summary_id:
        raise ValueError("consolidation summary record requires summary_id")
    if tuple(job.output_summary_ids) != (summary_id,):
        raise ValueError("consolidation summary record must match completed job output_summary_ids")
    if summary.get("job_id") != job.job_id:
        raise ValueError("consolidation summary record must match completed job_id")
    if summary.get("scope") != job.scope:
        raise ValueError("consolidation summary record must match completed job scope")
    if summary.get("summary_level") != job.summary_level:
        raise ValueError("consolidation summary record must match completed job summary_level")
    if summary.get("source_level") != job.source_level:
        raise ValueError("consolidation summary record must match completed job source_level")
    source_child_ids = summary.get("source_child_ids")
    if source_child_ids != list(job.source_child_ids):
        raise ValueError("consolidation summary record must match completed job source_child_ids")
    if summary.get("source_child_count") != len(job.source_child_ids):
        raise ValueError("consolidation summary record must match source_child_count")
    if summary.get("lineage_kind") != job.lineage_kind:
        raise ValueError("consolidation summary record must match completed job lineage_kind")
    if summary.get("non_blocking") is not True:
        raise ValueError("consolidation summary records must stay non-blocking")
    if summary.get("reversible") is not True:
        raise ValueError("consolidation summary records must stay reversible")
    if summary.get("summarizer", {}).get("hosted_llm"):
        raise ValueError("consolidation summary records cannot require a hosted LLM")
    source_child_digests = summary.get("source_child_digests")
    if not isinstance(source_child_digests, dict) or set(source_child_digests) != set(job.source_child_ids):
        raise ValueError("consolidation summary record requires source_child_digests for every source child")
    if not isinstance(summary.get("summary_text"), str) or not summary["summary_text"].strip():
        raise ValueError("consolidation summary record requires summary_text")
    if not isinstance(summary.get("content_digest"), str) or not summary["content_digest"].startswith("sha256:"):
        raise ValueError("consolidation summary record requires sha256 content_digest")
    live_binding_mismatches = _live_summary_binding_mismatch_reasons(summary, job)
    if live_binding_mismatches:
        raise ValueError(
            "consolidation summary live binding mismatch: " + ", ".join(live_binding_mismatches)
        )


def _consolidation_audit_record(
    job: ConsolidationJobRecord,
    summaries: list[dict[str, Any]],
    *,
    duplicate_summary_ids: set[str] | None = None,
    invalid_job_history: bool = False,
) -> dict[str, Any]:
    duplicate_summary_ids = duplicate_summary_ids or set()
    expected_output_summary_ids = list(job.output_summary_ids)
    ordered_summaries = sorted(summaries, key=lambda summary: summary["summary_id"])
    materialized_summary_ids = [summary["summary_id"] for summary in ordered_summaries]
    missing_output_summary_ids = [
        summary_id for summary_id in expected_output_summary_ids if summary_id not in materialized_summary_ids
    ]
    unexpected_output_summary_ids = [
        summary_id for summary_id in materialized_summary_ids if summary_id not in expected_output_summary_ids
    ]
    summary_scope_mismatches: list[str] = []
    summary_mismatch_reasons: dict[str, list[str]] = {}
    for summary in ordered_summaries:
        mismatch_reasons = _summary_mismatch_reasons(summary, job)
        if summary["summary_id"] in duplicate_summary_ids:
            mismatch_reasons.append("duplicate-summary-record")
        if not mismatch_reasons:
            continue
        summary_scope_mismatches.append(summary["summary_id"])
        summary_mismatch_reasons[summary["summary_id"]] = mismatch_reasons

    if job.status != "completed":
        audit_status = "not-materialized" if not materialized_summary_ids else "unexpected-summary"
    elif missing_output_summary_ids:
        audit_status = "missing-summary"
    elif unexpected_output_summary_ids or summary_scope_mismatches or invalid_job_history:
        audit_status = "mismatch"
    else:
        audit_status = "verified"

    return {
        "schema": CONSOLIDATION_AUDIT_RECORD_SCHEMA,
        "job_id": job.job_id,
        "scope": job.scope,
        "status": job.status,
        "completed_at": job.completed_at,
        "summary_level": job.summary_level,
        "source_level": job.source_level,
        "source_child_ids": list(job.source_child_ids),
        "expected_output_summary_ids": expected_output_summary_ids,
        "materialized_summary_ids": materialized_summary_ids,
        "missing_output_summary_ids": missing_output_summary_ids,
        "unexpected_output_summary_ids": unexpected_output_summary_ids,
        "summary_scope_mismatches": summary_scope_mismatches,
        "summary_mismatch_reasons": summary_mismatch_reasons,
        "invalid_job_history": invalid_job_history,
        "non_blocking": job.non_blocking,
        "reversible": job.reversible,
        "lineage_kind": job.lineage_kind,
        "audit_status": audit_status,
        "summaries": [
            {
                "summary_id": summary["summary_id"],
                "job_id": summary["job_id"],
                "content_digest": summary["content_digest"],
                "source_child_count": summary["source_child_count"],
                "source_child_ids": list(summary["source_child_ids"]),
                "created_at": summary["created_at"],
            }
            for summary in ordered_summaries
        ],
    }


def _summary_mismatch_reasons(summary: dict[str, Any], job: ConsolidationJobRecord) -> list[str]:
    mismatch_reasons: list[str] = []
    if summary.get("job_id") != job.job_id:
        mismatch_reasons.append("job-id-mismatch")
    if summary.get("scope") != job.scope:
        mismatch_reasons.append("scope-mismatch")
    if summary.get("summary_level") != job.summary_level:
        mismatch_reasons.append("summary-level-mismatch")
    if summary.get("source_level") != job.source_level:
        mismatch_reasons.append("source-level-mismatch")
    if summary.get("source_child_ids") != list(job.source_child_ids):
        mismatch_reasons.append("source-child-ids-mismatch")
    if summary.get("source_child_count") != len(job.source_child_ids):
        mismatch_reasons.append("source-child-count-mismatch")
    if not _summary_has_valid_source_child_digests(summary, job):
        mismatch_reasons.append("source-child-digests-mismatch")
    if not _summary_has_valid_content_digest(summary):
        mismatch_reasons.append("content-digest-mismatch")
    created_at = summary.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        mismatch_reasons.append("created-at-missing")
    elif job.completed_at is not None and created_at < job.completed_at:
        mismatch_reasons.append("created-at-before-job-completed")
    if summary.get("non_blocking") is not True:
        mismatch_reasons.append("non-blocking-required")
    if summary.get("lineage_kind") != job.lineage_kind:
        mismatch_reasons.append("lineage-kind-mismatch")
    if summary.get("reversible") is not True:
        mismatch_reasons.append("reversible-required")
    if summary.get("summarizer", {}).get("hosted_llm"):
        mismatch_reasons.append("hosted-llm-disallowed")
    mismatch_reasons.extend(_live_summary_binding_mismatch_reasons(summary, job))
    return mismatch_reasons


def _live_summary_binding_mismatch_reasons(
    summary: Mapping[str, Any],
    job: ConsolidationJobRecord,
) -> list[str]:
    summarizer = job.summarizer
    is_live = summarizer.get("kind") == "deterministic-live-ledger-v1" or any(
        key in summary for key in ("source_preview", "admission", "review", "canonical_memory_written")
    )
    if not is_live:
        return []
    mismatches: list[str] = []
    preview_binding = summarizer.get("preview_binding")
    admission = summarizer.get("admission")
    review = summarizer.get("review")
    if summarizer.get("kind") != "deterministic-live-ledger-v1" or summarizer.get("hosted_llm") is not False:
        mismatches.append("live-summarizer-contract-mismatch")
    expected_content_digest = summarizer.get("output_summary_content_digest")
    if (
        not isinstance(expected_content_digest, str)
        or not expected_content_digest.startswith("sha256:")
        or summary.get("content_digest") != expected_content_digest
    ):
        mismatches.append("summary-content-commitment-mismatch")
    if not isinstance(preview_binding, dict) or summary.get("source_preview") != preview_binding:
        mismatches.append("source-preview-binding-mismatch")
    if not isinstance(admission, dict) or summary.get("admission") != admission:
        mismatches.append("admission-contract-mismatch")
    if not isinstance(review, dict) or summary.get("review") != review:
        mismatches.append("review-binding-mismatch")
    if summary.get("canonical_memory_written") is not False:
        mismatches.append("canonical-memory-boundary-mismatch")
    if isinstance(preview_binding, dict) and summary.get("source_child_digests") != preview_binding.get(
        "source_content_digests"
    ):
        mismatches.append("source-preview-digests-mismatch")
    summary_admission = summary.get("admission")
    admission_contracts = [
        contract for contract in (admission, summary_admission) if isinstance(contract, dict)
    ]
    if len(admission_contracts) != 2 or any(
        any(
            (
                contract.get("status") != "quarantined",
                contract.get("trust") != 0.0,
                contract.get("authority") != "none",
                contract.get("canonical_memory_write_allowed") is not False,
                contract.get("non_blocking") is not True,
                contract.get("reversible") is not True,
            )
        )
        for contract in admission_contracts
    ):
        mismatches.append("admission-safety-boundary-mismatch")
    return mismatches


def _summary_has_valid_source_child_digests(
    summary: dict[str, Any],
    job: ConsolidationJobRecord,
) -> bool:
    source_child_digests = summary.get("source_child_digests")
    if not isinstance(source_child_digests, dict):
        return False
    if set(source_child_digests) != set(job.source_child_ids):
        return False
    return all(
        isinstance(source_child_digests[child_id], str) and source_child_digests[child_id].startswith("sha256:")
        for child_id in job.source_child_ids
    )


def _summary_has_valid_content_digest(summary: dict[str, Any]) -> bool:
    summary_text = summary.get("summary_text")
    content_digest = summary.get("content_digest")
    if not isinstance(summary_text, str) or not summary_text.strip():
        return False
    if not isinstance(content_digest, str) or not content_digest.startswith("sha256:"):
        return False
    return content_digest == _sha256_text(summary_text)


def _build_consolidation_lineage_node(
    summary: dict[str, Any],
    *,
    latest_summaries: dict[str, dict[str, Any]],
    ancestry: tuple[str, ...],
) -> dict[str, Any]:
    summary_id = summary["summary_id"]
    next_ancestry = ancestry + (summary_id,)
    leaf_source_child_ids: list[str] = []
    transitive_summary_ids = [summary_id]
    missing_summary_ids: list[str] = []
    cycle_summary_ids: list[str] = []
    children: list[dict[str, Any]] = []

    for child_id in summary["source_child_ids"]:
        if child_id in next_ancestry:
            cycle_summary_ids.append(child_id)
            children.append(
                {
                    "kind": "cycle_summary",
                    "summary_id": child_id,
                }
            )
            continue
        child_summary = latest_summaries.get(child_id)
        if child_summary is not None:
            child_node = _build_consolidation_lineage_node(
                child_summary,
                latest_summaries=latest_summaries,
                ancestry=next_ancestry,
            )
            children.append(child_node)
            leaf_source_child_ids.extend(child_node["leaf_source_child_ids"])
            transitive_summary_ids.extend(child_node["transitive_summary_ids"])
            missing_summary_ids.extend(child_node["missing_summary_ids"])
            cycle_summary_ids.extend(child_node["cycle_summary_ids"])
            continue
        if child_id.startswith("summary:"):
            missing_summary_ids.append(child_id)
            children.append(
                {
                    "kind": "missing_summary",
                    "summary_id": child_id,
                }
            )
            continue
        leaf_source_child_ids.append(child_id)
        children.append(
            {
                "kind": "source_child",
                "child_id": child_id,
            }
        )

    return {
        "kind": "summary",
        "summary_id": summary_id,
        "job_id": summary["job_id"],
        "created_at": summary["created_at"],
        "summarizer": deepcopy(summary.get("summarizer", {})),
        "non_blocking": summary["non_blocking"],
        "reversible": summary["reversible"],
        "summary_level": summary["summary_level"],
        "source_level": summary["source_level"],
        "source_child_ids": list(summary["source_child_ids"]),
        "source_child_digests": deepcopy(summary.get("source_child_digests", {})),
        "content_digest": summary["content_digest"],
        "leaf_source_child_ids": list(dict.fromkeys(leaf_source_child_ids)),
        "transitive_summary_ids": list(dict.fromkeys(transitive_summary_ids)),
        "missing_summary_ids": list(dict.fromkeys(missing_summary_ids)),
        "cycle_summary_ids": list(dict.fromkeys(cycle_summary_ids)),
        "children": children,
    }


def _reverse_summary_parent_index(
    latest_summaries: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    parent_index: dict[str, list[dict[str, Any]]] = {}
    for summary in latest_summaries.values():
        for child_id in summary["source_child_ids"]:
            parent_index.setdefault(child_id, []).append(summary)
    return parent_index


def _collect_reverse_lineage_paths(
    summary: dict[str, Any],
    *,
    summaries_by_id: dict[str, dict[str, Any]],
    parent_index: dict[str, list[dict[str, Any]]],
    ancestry: tuple[str, ...],
    paths: list[dict[str, Any]],
    transitive_summary_ids: list[str],
    root_summary_ids: list[str],
    cycle_summary_ids: list[str],
) -> None:
    summary_id = summary["summary_id"]
    chain = ancestry + (summary_id,)
    transitive_summary_ids.append(summary_id)
    parent_summaries = parent_index.get(summary_id, [])

    if not parent_summaries:
        root_summary_ids.append(summary_id)
        paths.append(
            {
                "summary_ids": list(chain),
                "summary_levels": [summaries_by_id[item]["summary_level"] for item in chain],
                "summary_nodes": [_reverse_lineage_summary_node(summaries_by_id[item]) for item in chain],
                "root_summary_id": summary_id,
            }
        )
        return

    followed_parent = False
    for parent_summary in parent_summaries:
        parent_summary_id = parent_summary["summary_id"]
        if parent_summary_id in chain:
            cycle_summary_ids.append(parent_summary_id)
            paths.append(
                {
                    "summary_ids": list(chain),
                    "summary_levels": [summaries_by_id[item]["summary_level"] for item in chain],
                    "summary_nodes": [_reverse_lineage_summary_node(summaries_by_id[item]) for item in chain],
                    "cycle_summary_id": parent_summary_id,
                }
            )
            continue
        followed_parent = True
        _collect_reverse_lineage_paths(
            parent_summary,
            summaries_by_id=summaries_by_id,
            parent_index=parent_index,
            ancestry=chain,
            paths=paths,
            transitive_summary_ids=transitive_summary_ids,
            root_summary_ids=root_summary_ids,
            cycle_summary_ids=cycle_summary_ids,
        )

    if not followed_parent:
        root_summary_ids.append(summary_id)
        paths.append(
            {
                "summary_ids": list(chain),
                "summary_levels": [summaries_by_id[item]["summary_level"] for item in chain],
                "summary_nodes": [_reverse_lineage_summary_node(summaries_by_id[item]) for item in chain],
                "root_summary_id": summary_id,
            }
        )


def _reverse_lineage_summary_node(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary_id": summary["summary_id"],
        "job_id": summary["job_id"],
        "created_at": summary["created_at"],
        "summarizer": deepcopy(summary.get("summarizer", {})),
        "non_blocking": summary["non_blocking"],
        "reversible": summary["reversible"],
        "summary_level": summary["summary_level"],
        "source_level": summary["source_level"],
        "source_child_ids": list(summary["source_child_ids"]),
        "source_child_digests": deepcopy(summary.get("source_child_digests", {})),
        "content_digest": summary["content_digest"],
    }
