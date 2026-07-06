from __future__ import annotations

from pathlib import Path
from typing import Any

from .consolidation import (
    consolidation_audit_report,
    consolidation_levels,
    consolidation_summary_lineage_report,
    consolidation_summary_reverse_lineage_report,
    latest_consolidation_summaries,
)


CONSOLIDATION_UNWIND_PLAN_SCHEMA = "zerker.consolidation_unwind_plan.v1"
CONSOLIDATION_RETRY_GUIDANCE_SCHEMA = "zerker.consolidation_retry_guidance.v1"
CONSOLIDATION_RETRY_GROUP_REPORT_SCHEMA = "zerker.consolidation_retry_group_report.v1"


def consolidation_unwind_plan(
    job_ledger_path: Path,
    summary_ledger_path: Path,
    child_id: str,
) -> dict[str, Any]:
    reverse_report = consolidation_summary_reverse_lineage_report(summary_ledger_path, child_id)
    latest_summaries = latest_consolidation_summaries(summary_ledger_path)
    audit_report = consolidation_audit_report(job_ledger_path, summary_ledger_path)
    audit_by_summary_id = _audit_records_by_summary_id(audit_report["records"])
    level_ranks = {level["id"]: level["rank"] for level in consolidation_levels()}

    child_kind = "source_child"
    nested_child_lineage: dict[str, Any] | None = None
    child_lineage_blockers: list[str] = []
    if child_id in latest_summaries:
        child_kind = "nested_summary"
        nested_child_lineage = consolidation_summary_lineage_report(summary_ledger_path, child_id)
        child_lineage_blockers.extend(nested_child_lineage["missing_summary_ids"])
        child_lineage_blockers.extend(nested_child_lineage["cycle_summary_ids"])
    elif not reverse_report["direct_summary_ids"]:
        child_kind = "orphan_child"

    dependency_ids_by_summary_id: dict[str, set[str]] = {}
    path_count_by_summary_id: dict[str, int] = {}
    first_path_position_by_summary_id: dict[str, tuple[int, int]] = {}
    for path_index, path in enumerate(reverse_report["paths"]):
        summary_ids = path["summary_ids"]
        for summary_index, summary_id in enumerate(summary_ids):
            dependency_ids_by_summary_id.setdefault(summary_id, set())
            path_count_by_summary_id[summary_id] = path_count_by_summary_id.get(summary_id, 0) + 1
            first_path_position_by_summary_id.setdefault(summary_id, (path_index, summary_index))
            if summary_index > 0:
                dependency_ids_by_summary_id[summary_id].add(summary_ids[summary_index - 1])

    impacted_summary_ids = sorted(
        reverse_report["transitive_summary_ids"],
        key=lambda summary_id: (
            level_ranks.get(latest_summaries[summary_id]["summary_level"], 999),
            first_path_position_by_summary_id.get(summary_id, (999, 999)),
            summary_id,
        ),
    )
    order_index = {summary_id: index for index, summary_id in enumerate(impacted_summary_ids)}

    blocked_summary_ids = set(reverse_report["cycle_summary_ids"])
    steps: list[dict[str, Any]] = []
    for step_number, summary_id in enumerate(impacted_summary_ids, start=1):
        summary = latest_summaries[summary_id]
        audit_record = audit_by_summary_id.get(summary_id)
        audit_status = audit_record["audit_status"] if audit_record else "unknown"
        if audit_status != "verified":
            blocked_summary_ids.add(summary_id)
        dependency_ids = sorted(
            dependency_ids_by_summary_id.get(summary_id, set()),
            key=lambda dependency_id: order_index.get(dependency_id, 999),
        )
        steps.append(
            {
                "step": step_number,
                "summary_id": summary_id,
                "summary_level": summary["summary_level"],
                "job_id": summary["job_id"],
                "audit_status": audit_status,
                "action": (
                    "review-before-rematerialize" if audit_status != "verified" else "review-and-rematerialize"
                ),
                "depends_on_summary_ids": dependency_ids,
                "source_child_ids": list(summary["source_child_ids"]),
                "path_count": path_count_by_summary_id.get(summary_id, 0),
                "is_direct_parent": summary_id in reverse_report["direct_summary_ids"],
                "is_root_summary": summary_id in reverse_report["root_summary_ids"],
                "non_blocking": summary["non_blocking"],
                "reversible": summary["reversible"],
            }
        )

    return {
        "schema": CONSOLIDATION_UNWIND_PLAN_SCHEMA,
        "child_id": child_id,
        "child_kind": child_kind,
        "direct_summary_ids": list(reverse_report["direct_summary_ids"]),
        "impacted_summary_ids": impacted_summary_ids,
        "root_summary_ids": list(reverse_report["root_summary_ids"]),
        "cycle_summary_ids": list(reverse_report["cycle_summary_ids"]),
        "blocked_summary_ids": sorted(blocked_summary_ids),
        "blocked_child_summary_ids": list(dict.fromkeys(child_lineage_blockers)),
        "nested_child_lineage": (
            None
            if nested_child_lineage is None
            else {
                "summary_id": nested_child_lineage["summary_id"],
                "leaf_source_child_ids": list(nested_child_lineage["leaf_source_child_ids"]),
                "missing_summary_ids": list(nested_child_lineage["missing_summary_ids"]),
                "cycle_summary_ids": list(nested_child_lineage["cycle_summary_ids"]),
            }
        ),
        "paths": list(reverse_report["paths"]),
        "steps": steps,
    }


def consolidation_retry_guidance(
    job_ledger_path: Path,
    summary_ledger_path: Path,
    child_id: str,
) -> dict[str, Any]:
    unwind_plan = consolidation_unwind_plan(job_ledger_path, summary_ledger_path, child_id)
    unwind_steps = list(unwind_plan["steps"])
    impacted_summary_ids = list(unwind_plan["impacted_summary_ids"])
    root_summary_ids = list(unwind_plan["root_summary_ids"])
    blocked_summary_ids = list(unwind_plan["blocked_summary_ids"])
    child_kind = unwind_plan["child_kind"]
    if not unwind_steps and child_kind == "orphan_child":
        supplemental_steps = _missing_summary_retry_steps(job_ledger_path, summary_ledger_path, child_id)
        if supplemental_steps:
            unwind_steps = supplemental_steps
            child_kind = "source_child"
            impacted_summary_ids = [step["summary_id"] for step in supplemental_steps]
            root_summary_ids = [step["summary_id"] for step in supplemental_steps if step["is_root_summary"]]
            blocked_summary_ids = [
                step["summary_id"] for step in supplemental_steps if step["audit_status"] != "verified"
            ]
    child_retry_action = _child_retry_action(child_kind)
    child_repair_required = child_kind == "nested_summary"

    ready_summary_ids: list[str] = []
    guidance_steps: list[dict[str, Any]] = []
    for step in unwind_steps:
        blocked_by_summary_ids = list(step["depends_on_summary_ids"])
        blocking_reasons: list[str] = []
        if step["summary_id"] in unwind_plan["cycle_summary_ids"]:
            blocking_reasons.append("cycle-detected")
        if child_repair_required:
            blocking_reasons.append("nested-child-summary-needs-repair")
        blocking_reasons.extend(_audit_blocking_reasons(step["audit_status"]))
        retry_action = _retry_action_for_step(
            audit_status=step["audit_status"],
            blocked_by_summary_ids=blocked_by_summary_ids,
            blocking_reasons=blocking_reasons,
        )
        retryable_now = not blocked_by_summary_ids and not blocking_reasons
        if retryable_now:
            ready_summary_ids.append(step["summary_id"])
        guidance_steps.append(
            {
                **step,
                "retryable_now": retryable_now,
                "retry_action": retry_action,
                "blocked_by_summary_ids": blocked_by_summary_ids,
                "blocking_reasons": blocking_reasons,
            }
        )

    return {
        "schema": CONSOLIDATION_RETRY_GUIDANCE_SCHEMA,
        "child_id": child_id,
        "child_kind": child_kind,
        "child_retry_action": child_retry_action,
        "child_repair_required": child_repair_required,
        "impacted_summary_ids": impacted_summary_ids,
        "root_summary_ids": root_summary_ids,
        "ready_summary_ids": ready_summary_ids,
        "blocked_summary_ids": blocked_summary_ids,
        "blocked_child_summary_ids": list(unwind_plan["blocked_child_summary_ids"]),
        "steps": guidance_steps,
    }


def consolidation_retry_group_report(
    job_ledger_path: Path,
    summary_ledger_path: Path,
    child_ids: list[str],
) -> dict[str, Any]:
    requested_child_ids = _unique_child_ids(child_ids)
    guidance_reports = [
        consolidation_retry_guidance(job_ledger_path, summary_ledger_path, child_id)
        for child_id in requested_child_ids
    ]
    child_order = {child_id: index for index, child_id in enumerate(requested_child_ids)}
    level_ranks = {level["id"]: level["rank"] for level in consolidation_levels()}

    groups_by_summary_id: dict[str, dict[str, Any]] = {}
    for guidance in guidance_reports:
        child_id = guidance["child_id"]
        for step in guidance["steps"]:
            summary_id = step["summary_id"]
            group = groups_by_summary_id.get(summary_id)
            if group is None:
                group = {
                    "summary_id": summary_id,
                    "summary_level": step["summary_level"],
                    "job_id": step["job_id"],
                    "audit_status": step["audit_status"],
                    "child_ids": [],
                    "child_kinds": [],
                    "ready_child_ids": [],
                    "blocked_child_ids": [],
                    "direct_child_ids": [],
                    "root_child_ids": [],
                    "retry_actions": [],
                    "blocked_by_summary_ids": [],
                    "blocking_reasons": [],
                    "non_blocking": step["non_blocking"],
                    "reversible": step["reversible"],
                }
                groups_by_summary_id[summary_id] = group
            _append_unique(group["child_ids"], child_id)
            _append_unique(group["child_kinds"], guidance["child_kind"])
            if step["retryable_now"]:
                _append_unique(group["ready_child_ids"], child_id)
            else:
                _append_unique(group["blocked_child_ids"], child_id)
            if step["is_direct_parent"]:
                _append_unique(group["direct_child_ids"], child_id)
            if step["is_root_summary"]:
                _append_unique(group["root_child_ids"], child_id)
            _append_unique(group["retry_actions"], step["retry_action"])
            for dependency_id in step["blocked_by_summary_ids"]:
                _append_unique(group["blocked_by_summary_ids"], dependency_id)
            for reason in step["blocking_reasons"]:
                _append_unique(group["blocking_reasons"], reason)

    groups = sorted(
        groups_by_summary_id.values(),
        key=lambda group: (
            level_ranks.get(group["summary_level"], 999),
            group["summary_id"],
        ),
    )
    ready_summary_ids: list[str] = []
    blocked_summary_ids: list[str] = []
    for group in groups:
        group["child_ids"].sort(key=child_order.__getitem__)
        group["ready_child_ids"].sort(key=child_order.__getitem__)
        group["blocked_child_ids"].sort(key=child_order.__getitem__)
        group["direct_child_ids"].sort(key=child_order.__getitem__)
        group["root_child_ids"].sort(key=child_order.__getitem__)
        group["shared_dependency_group"] = len(group["child_ids"]) > 1
        group["dependency_group_status"] = (
            "retryable-now" if len(group["ready_child_ids"]) == len(group["child_ids"]) else "blocked"
        )
        if group["dependency_group_status"] == "retryable-now":
            ready_summary_ids.append(group["summary_id"])
        else:
            blocked_summary_ids.append(group["summary_id"])

    return {
        "schema": CONSOLIDATION_RETRY_GROUP_REPORT_SCHEMA,
        "requested_child_ids": requested_child_ids,
        "child_report_count": len(guidance_reports),
        "impacted_summary_count": len(groups),
        "shared_impacted_summary_count": sum(1 for group in groups if group["shared_dependency_group"]),
        "ready_summary_ids": ready_summary_ids,
        "blocked_summary_ids": blocked_summary_ids,
        "child_reports": [
            {
                "child_id": guidance["child_id"],
                "child_kind": guidance["child_kind"],
                "child_retry_action": guidance["child_retry_action"],
                "child_repair_required": guidance["child_repair_required"],
                "impacted_summary_ids": list(guidance["impacted_summary_ids"]),
                "ready_summary_ids": list(guidance["ready_summary_ids"]),
                "blocked_summary_ids": list(guidance["blocked_summary_ids"]),
                "blocked_child_summary_ids": list(guidance["blocked_child_summary_ids"]),
            }
            for guidance in guidance_reports
        ],
        "groups": groups,
    }


def _audit_records_by_summary_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        for summary_id in record.get("materialized_summary_ids", []):
            indexed[summary_id] = record
    return indexed


def _child_retry_action(child_kind: str) -> str:
    if child_kind == "nested_summary":
        return "repair-child-summary-first"
    if child_kind == "orphan_child":
        return "no-dependent-summaries"
    return "repair-source-child-first"


def _audit_blocking_reasons(audit_status: str) -> list[str]:
    if audit_status == "verified":
        return []
    if audit_status == "missing-summary":
        return []
    return [f"audit:{audit_status}"]


def _retry_action_for_step(
    *,
    audit_status: str,
    blocked_by_summary_ids: list[str],
    blocking_reasons: list[str],
) -> str:
    if "cycle-detected" in blocking_reasons:
        return "break-cycle-before-retry"
    if "nested-child-summary-needs-repair" in blocking_reasons:
        return "wait-for-child-summary-repair"
    if blocked_by_summary_ids:
        return "wait-for-dependent-summary-repair"
    if audit_status == "verified":
        return "rematerialize-local-summary"
    if audit_status == "missing-summary":
        return "recreate-missing-summary"
    if audit_status == "mismatch":
        return "review-mismatched-summary"
    if audit_status == "unexpected-summary":
        return "review-unexpected-summary"
    if audit_status == "not-materialized":
        return "materialize-pending-summary"
    return "inspect-summary-state"


def _missing_summary_retry_steps(
    job_ledger_path: Path,
    summary_ledger_path: Path,
    child_id: str,
) -> list[dict[str, Any]]:
    audit_report = consolidation_audit_report(job_ledger_path, summary_ledger_path)
    level_ranks = {level["id"]: level["rank"] for level in consolidation_levels()}
    candidate_records = [
        record
        for record in audit_report["records"]
        if record["audit_status"] == "missing-summary" and child_id in record["source_child_ids"]
    ]
    candidate_records.sort(
        key=lambda record: (
            level_ranks.get(record["summary_level"], 999),
            record["job_id"],
        )
    )

    steps: list[dict[str, Any]] = []
    for step_number, record in enumerate(candidate_records, start=1):
        for summary_id in record["expected_output_summary_ids"]:
            steps.append(
                {
                    "step": step_number,
                    "summary_id": summary_id,
                    "summary_level": record["summary_level"],
                    "job_id": record["job_id"],
                    "audit_status": record["audit_status"],
                    "action": "review-before-rematerialize",
                    "depends_on_summary_ids": [],
                    "source_child_ids": list(record["source_child_ids"]),
                    "path_count": 1,
                    "is_direct_parent": True,
                    "is_root_summary": True,
                    "non_blocking": record["non_blocking"],
                    "reversible": record["reversible"],
                }
            )
    return steps


def _unique_child_ids(child_ids: list[str]) -> list[str]:
    normalized: list[str] = []
    for child_id in child_ids:
        if not isinstance(child_id, str) or not child_id:
            raise ValueError("child_ids must contain non-empty strings")
        _append_unique(normalized, child_id)
    return normalized


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
