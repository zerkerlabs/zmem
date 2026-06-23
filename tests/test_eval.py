import unittest

from zerker_memory.eval import run_cto_smoke, run_eval


class EvalHarnessTest(unittest.TestCase):
    def test_eval_harness_passes_core_scenarios(self):
        result = run_eval()
        self.assertTrue(result["ok"])
        self.assertEqual(result["failed"], 0)
        self.assertGreaterEqual(result["passed"], 8)
        names = {item["name"] for item in result["results"]}
        self.assertIn("snapshot_restore", names)
        self.assertIn("bt_recovery_explanation", names)
        self.assertIn("bt_groot2_export", names)

    def test_cto_smoke_covers_all_seeded_audit_rows(self):
        result = run_cto_smoke()
        self.assertTrue(result["ok"])
        self.assertEqual(result["failed"], 0)
        self.assertEqual(
            set(result["audit_rows"]),
            {
                "ZQA-001",
                "ZQA-002",
                "ZQA-003",
                "ZQA-004",
                "ZQA-005",
                "ZQA-006",
                "ZQA-007",
                "ZQA-008",
                "ZQA-009",
                "ZQA-010",
                "ZQA-011",
                "ZQA-012",
                "ZQA-013",
                "ZQA-014",
                "ZQA-015",
                "ZQA-016",
            },
        )
        names = {item["name"] for item in result["results"]}
        self.assertIn("cto_capture_scope_and_source", names)
        self.assertIn("cto_lifecycle_semantics", names)


if __name__ == "__main__":
    unittest.main()
