import json
import sys
import tempfile
import unittest
from pathlib import Path

from zerker_memory.runner import verify_memory_context
from zerker_memory.scheduled import audit_cold_start, run_scheduled_agent
from zerker_memory.store import MemoryStore


class ScheduledAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = MemoryStore(self.root / "memory.sqlite")
        self.store.init()

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    def test_first_run_reports_unknown_and_binds_audit_into_context_and_proof(self):
        context_path = self.root / "context.json"
        result = run_scheduled_agent(
            self.store,
            [sys.executable, "-c", "raise SystemExit(0)"],
            session_id="cron://daily-signal",
            agent_id="hermes",
            task="Collect the daily signal",
            risk="low",
            scope="project:zmem",
            context_path=context_path,
        )

        context = json.loads(context_path.read_text(encoding="utf-8"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["cold_start"]["state"], "unknown")
        self.assertEqual(result["cold_start"]["reason"], "no-prior-session-state")
        self.assertTrue(result["cold_start"]["receipt_verification"]["ok"])
        self.assertEqual(context["continuity"]["audit_id"], result["cold_start"]["audit_id"])
        self.assertEqual(context["continuity"]["state"], "unknown")
        self.assertTrue(verify_memory_context(context))
        self.assertEqual(
            result["run"]["memory_context"]["context_digest"],
            context["context_digest"],
        )
        self.assertTrue(result["proof"]["verification"]["ok"])
        self.assertEqual(
            result["proof"]["checkpoint_receipt_hash"],
            result["checkpoint"]["receipt"]["receipt_hash"],
        )

    def test_old_checkpoint_reports_stale(self):
        self.store.checkpoint_session(
            "cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
        )

        audit = audit_cold_start(
            self.store,
            session_id="cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
            stale_after_seconds=60,
            evaluated_at="2099-01-01T00:00:00Z",
        )

        self.assertEqual(audit["state"], "stale")
        self.assertEqual(audit["reason"], "wall-clock-gap-exceeded")
        self.assertGreater(audit["gap_seconds"], 60)
        self.assertEqual(audit["prior_state"]["event_type"], "SESSION_CHECKPOINTED")
        self.assertTrue(audit["receipt_verification"]["ok"])

    def test_uncheckpointed_prior_run_reports_unknown(self):
        self.store.start_session(
            "cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
        )

        audit = audit_cold_start(
            self.store,
            session_id="cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
            stale_after_seconds=86_400,
        )

        self.assertEqual(audit["state"], "unknown")
        self.assertEqual(audit["reason"], "prior-session-not-checkpointed")

    def test_deleted_latest_snapshot_is_unknown_but_deleting_an_older_snapshot_does_not_hide_checkpoint(self):
        snapshot = self.store.snapshot_session(
            "cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
        )
        self.store.soft_delete_session_snapshot_payload(
            snapshot["session_snapshot_id"],
            actor_id="operator",
        )
        missing = audit_cold_start(
            self.store,
            session_id="cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
            stale_after_seconds=86_400,
        )
        self.assertEqual(missing["state"], "unknown")
        self.assertEqual(missing["reason"], "latest-snapshot-payload-unavailable")

        checkpoint = self.store.checkpoint_session(
            "cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
        )
        current = audit_cold_start(
            self.store,
            session_id="cron://daily-signal",
            actor_id="hermes",
            scope="project:zmem",
            stale_after_seconds=86_400,
        )
        self.assertEqual(current["state"], "current")
        self.assertEqual(current["prior_state"]["lifecycle_id"], checkpoint["checkpoint_id"])

    def test_nonzero_command_is_checkpointed_and_proved(self):
        result = run_scheduled_agent(
            self.store,
            [sys.executable, "-c", "raise SystemExit(7)"],
            session_id="cron://daily-signal",
            agent_id="hermes",
            task="Collect the daily signal",
            risk="low",
        )

        self.assertEqual(result["run"]["exit_code"], 7)
        self.assertTrue(result["proof"]["verification"]["ok"])
        event_types = [row["event_type"] for row in self.store.conn.execute("SELECT event_type FROM events ORDER BY seq")]
        self.assertIn("SESSION_CHECKPOINTED", event_types)
        self.assertEqual(event_types[-1], "SCHEDULED_RUN_PROVED")


if __name__ == "__main__":
    unittest.main()
