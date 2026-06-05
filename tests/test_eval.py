import unittest

from zerker_memory.eval import run_eval


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


if __name__ == "__main__":
    unittest.main()
