import unittest

from zerker_memory.consolidation import (
    CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA,
    CONSOLIDATION_LINEAGE_KIND,
    consolidation_levels,
    consolidation_lineage_fixture,
    source_child_ids_for_summary,
    summary_ids_for_source_child,
    validate_consolidation_lineage_fixture,
)


class ConsolidationFixtureTest(unittest.TestCase):
    def test_levels_define_ordered_hierarchical_contract(self):
        levels = consolidation_levels()

        self.assertEqual(
            [level["id"] for level in levels],
            ["turn", "session", "day", "week", "profile_project"],
        )
        self.assertEqual([level["rank"] for level in levels], [0, 1, 2, 3, 4])
        self.assertEqual(levels[-1]["label"], "profile/project")

    def test_lineage_fixture_is_reversible_from_summary_to_sources(self):
        fixture = consolidation_lineage_fixture()
        summary_id = "summary:session:2026-06-22:payments-routing"

        self.assertEqual(fixture["schema"], CONSOLIDATION_LINEAGE_FIXTURE_SCHEMA)
        self.assertTrue(validate_consolidation_lineage_fixture(fixture))
        self.assertEqual(
            source_child_ids_for_summary(fixture, summary_id),
            ["memory:turn:001", "memory:turn:002", "memory:turn:003"],
        )
        self.assertEqual(summary_ids_for_source_child(fixture, "memory:turn:002"), [summary_id])
        self.assertIn(
            "summary:day:2026-06-22:zmem-launch",
            summary_ids_for_source_child(fixture, summary_id),
        )

    def test_fixture_has_no_hosted_summarizer_dependency(self):
        fixture = consolidation_lineage_fixture()

        self.assertEqual(
            {summary["lineage_kind"] for summary in fixture["summaries"]},
            {CONSOLIDATION_LINEAGE_KIND},
        )
        self.assertEqual(fixture["summarizer"]["kind"], "deterministic-fixture")
        self.assertFalse(fixture["summarizer"]["hosted_llm"])
        self.assertIsNone(fixture["summarizer"]["model_id"])


if __name__ == "__main__":
    unittest.main()
