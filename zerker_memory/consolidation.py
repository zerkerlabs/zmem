from __future__ import annotations

from copy import deepcopy
from typing import Any


CONSOLIDATION_LEVEL_SCHEMA = "zerker.consolidation_levels.v1"
CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA = "zerker.consolidation_lineage_fixture.v1"
CONSOLIDATION_LINEAGE_KIND = "source-child-to-summary"

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
