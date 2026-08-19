import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Import the seed module from scripts/ (added to sys.path for the test).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seed_review_state  # noqa: E402


class SeedReviewStateTest(unittest.TestCase):
    def test_seed_fills_review_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "zmem-ci.db")
            result = seed_review_state.seed(db)
            self.assertGreaterEqual(result["queued"], 2)
            self.assertGreaterEqual(result["active"], 1)

            # The dashboard reads the same DB; `queue` must list the quarantined items.
            out = subprocess.run(
                [sys.executable, "-m", "zerker_memory", "--db", db, "queue"],
                capture_output=True,
                text=True,
                check=True,
            )
            # At least the two proposed agent memories are awaiting review.
            self.assertIn("seed", out.stdout.lower())


if __name__ == "__main__":
    unittest.main()
