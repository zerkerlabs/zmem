import tempfile
import unittest
from pathlib import Path

from zerker_memory.failure_memory import inspect_failure_memory, record_failure_memory
from zerker_memory.store import MemoryStore


class FailureMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp_dir.name) / "memory.sqlite")
        self.store.init()

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    def test_agent_failure_memory_is_typed_receipted_and_quarantined(self):
        result = record_failure_memory(
            self.store,
            expected_result="Transfer exactly 10 credits",
            observed_result="API returned 200 but transferred 100 credits",
            correction="Read the settled ledger amount before reporting success",
            invalidation="Invalidate when the ledger amount differs from the requested amount",
            confidence=0.98,
            scope="project:payments",
            actor_id="payments-agent",
            action_id="act_transfer_1",
            session_id="cron://payments",
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["review_required"])
        self.assertEqual(result["memory"]["type"], "episodic")
        self.assertEqual(result["memory"]["status"], "quarantined")
        self.assertEqual(result["failure"]["action_id"], "act_transfer_1")
        self.assertTrue(result["write_receipt_verification"]["ok"])

        inspected = inspect_failure_memory(self.store, result["memory"]["id"])
        self.assertTrue(inspected["ok"])
        self.assertTrue(inspected["content_hash_verified"])
        self.assertEqual(inspected["failure"], result["failure"])
        self.assertTrue(inspected["write_receipt_verification"]["ok"])

    def test_failure_memory_can_reference_invalidated_memories_without_mutating_them(self):
        stale = self.store.remember(
            "The settled amount always matches the requested amount.",
            memory_type="semantic",
            scope="project:payments",
            source_kind="human",
        )

        result = record_failure_memory(
            self.store,
            expected_result="Requested and settled amount match",
            observed_result="Settled amount was ten times larger",
            correction="Compare requested and settled amount",
            invalidation="The old invariant is disproven by the settled ledger",
            confidence=1.0,
            scope="project:payments",
            actor_id="payments-agent",
            invalidated_memory_ids=[stale.id],
        )

        self.assertEqual(result["failure"]["invalidation"]["memory_ids"], [stale.id])
        self.assertEqual(self.store.get(stale.id).status, "active")

    def test_failure_memory_rejects_invalid_confidence_and_missing_targets(self):
        with self.assertRaisesRegex(ValueError, "confidence"):
            record_failure_memory(
                self.store,
                expected_result="Expected",
                observed_result="Observed",
                correction="Correct",
                invalidation="Invalidate",
                confidence=1.1,
                scope="project",
                actor_id="agent",
            )
        with self.assertRaises(KeyError):
            record_failure_memory(
                self.store,
                expected_result="Expected",
                observed_result="Observed",
                correction="Correct",
                invalidation="Invalidate",
                confidence=0.5,
                scope="project",
                actor_id="agent",
                invalidated_memory_ids=["mem_missing"],
            )


if __name__ == "__main__":
    unittest.main()
