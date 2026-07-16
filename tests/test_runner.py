import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zerker_memory.retrieval_providers import RerankerProviderResult
from zerker_memory.runner import build_context, run_with_memory
from zerker_memory.store import MemoryStore, approx_memory_tokens


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = MemoryStore(self.tmp_path / "memory.sqlite")
        self.store.init()

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_writes_context_and_preserves_exit_code(self):
        self.store.remember(
            "Production deploys require approval",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "context.json"
        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="deploy service to production",
            agent_id="codex",
            risk="high",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["schema"], "zerker.run.v1")
        self.assertTrue(receipt["context_retained"])
        self.assertTrue(context_path.exists())
        context = json.loads(context_path.read_text())
        self.assertEqual(context["schema"], "zerker.memory_context.v1")
        self.assertEqual(len(context["memories"]), 1)
        self.assertEqual(context["memories"][0]["type"], "policy")

    def test_default_run_context_is_private_and_removed_after_command(self):
        mode_path = self.tmp_path / "context-mode.txt"
        command = [
            "python3",
            "-c",
            (
                "import os, pathlib, stat; "
                "path = pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']); "
                f"pathlib.Path({str(mode_path)!r}).write_text(str(stat.S_IMODE(path.stat().st_mode))); "
                "assert stat.S_IMODE(path.stat().st_mode) == 0o600"
            ),
        ]

        receipt = run_with_memory(
            self.store,
            command,
            task="inspect private governed context",
            agent_id="codex",
            risk="low",
        )

        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(int(mode_path.read_text(encoding="utf-8")), 0o600)
        self.assertFalse(receipt["context_retained"])
        self.assertFalse(Path(receipt["context_path"]).exists())

    def test_default_run_context_is_removed_when_command_cannot_start(self):
        original_mkstemp = tempfile.mkstemp

        def private_mkstemp(*args, **kwargs):
            return original_mkstemp(*args, dir=self.tmp_path, **kwargs)

        with mock.patch("zerker_memory.runner.tempfile.mkstemp", side_effect=private_mkstemp):
            with self.assertRaises(FileNotFoundError):
                run_with_memory(
                    self.store,
                    [str(self.tmp_path / "missing-command")],
                    task="fail before command start",
                    agent_id="codex",
                    risk="low",
                )

        self.assertEqual(list(self.tmp_path.glob("zerker-memory-*.json")), [])

    def test_build_context_separates_instructional_and_recall_memory_and_surfaces_budget_receipts(self):
        policy = self.store.remember(
            "Lifecycle context marker policy deploy approval required",
            memory_type="policy",
            scope="project",
            source_kind="human",
        )
        procedural = self.store.remember(
            "Lifecycle context marker procedural deploy approval checklist",
            memory_type="procedural",
            scope="project",
            source_kind="human",
        )
        episodic = self.store.remember(
            "Lifecycle context marker episodic deploy approval incident recap",
            memory_type="episodic",
            scope="project",
            source_kind="human",
        )
        semantic = self.store.remember(
            "Lifecycle context marker semantic " + ("deploy approval owner detail " * 80),
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        withheld = self.store.remember(
            "Lifecycle context marker policy deploy approval skip approvals",
            memory_type="policy",
            scope="project",
            source_kind="agent",
        )
        budget = (
            approx_memory_tokens(policy)
            + approx_memory_tokens(procedural)
            + approx_memory_tokens(episodic)
        )

        receipt = self.store.inject(
            "lifecycle context marker deploy approval",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)

        self.assertEqual([memory["id"] for memory in context["memory_classes"]["policy"]], [policy.id])
        self.assertEqual([memory["id"] for memory in context["memory_classes"]["procedural"]], [procedural.id])
        self.assertEqual([memory["id"] for memory in context["memory_classes"]["episodic"]], [episodic.id])
        self.assertEqual(context["memory_classes"]["semantic"], [])
        self.assertEqual(context["budget_dropped"][0]["memory_id"], semantic.id)
        self.assertEqual(context["withheld"][0]["memory_id"], withheld.id)
        self.assertEqual(context["memory_type_summary"]["instruction_types"], ["policy", "procedural"])
        self.assertEqual(context["memory_type_summary"]["recall_types"], ["episodic", "semantic"])
        self.assertTrue(
            any("procedural" in instruction and "episodic" in instruction for instruction in context["instructions"])
        )
        self.assertEqual(context["temporal"]["injected_temporal_graph"][policy.id]["temporal_state"], "current")
        self.assertEqual(context["temporal"]["withheld_temporal_graph"][withheld.id]["temporal_state"], "learned")
        self.assertEqual(context["temporal"]["budget_dropped_temporal_graph"][semantic.id]["temporal_state"], "current")

    def test_build_context_preserves_learned_and_future_temporal_id_groups(self):
        learned = self.store.remember(
            "Release freeze owner is Mallory.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
        )
        future = self.store.remember(
            "Roadmap owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            status="active",
        )
        future_timestamp = "2099-01-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (future_timestamp, future_timestamp, future.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (future_timestamp, future.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]

        self.assertEqual(temporal["learned_memory_ids"], [learned.id])
        self.assertEqual(temporal["future_memory_ids"], [future.id])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["withheld_temporal_graph"][learned.id]["temporal_state"], "learned")
        self.assertEqual(temporal["selected_temporal_graph"][future.id]["temporal_state"], "future")

    def test_build_context_preserves_explicit_temporal_state_group_graphs(self):
        learned = self.store.remember(
            "Release freeze owner is Mallory.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        future = self.store.remember(
            "Roadmap owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-05T00:00:00Z", "2024-01-05T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2099-01-01T00:00:00Z", "2099-01-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'PROPOSED'",
            ("2024-01-05T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2099-01-01T00:00:00Z", future.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]

        self.assertCountEqual(list(temporal["history_temporal_graph"]), [learned.id, stale.id, current.id])
        self.assertEqual(list(temporal["current_temporal_graph"]), [current.id])
        self.assertEqual(list(temporal["superseded_temporal_graph"]), [stale.id])
        self.assertEqual(list(temporal["learned_temporal_graph"]), [learned.id])
        self.assertEqual(list(temporal["future_temporal_graph"]), [future.id])
        self.assertEqual(temporal["history_temporal_graph"][learned.id]["temporal_state"], "learned")
        self.assertEqual(temporal["history_temporal_graph"][stale.id]["temporal_state"], "superseded")
        self.assertEqual(temporal["history_temporal_graph"][current.id]["temporal_state"], "current")
        self.assertEqual(temporal["current_temporal_graph"][current.id]["temporal_state"], "current")
        self.assertEqual(temporal["superseded_temporal_graph"][stale.id]["temporal_resolution_kind"], "supersession")
        self.assertIsNone(temporal["learned_temporal_graph"][learned.id]["valid_from"])
        self.assertEqual(temporal["future_temporal_graph"][future.id]["valid_from"], "2099-01-01T00:00:00Z")

    def test_build_context_preserves_unlearned_temporal_id_groups_when_present(self):
        receipt = {
            "action_id": "act_temporal_context",
            "task": "temporal passthrough",
            "risk": "low",
            "merkle_root": "root_fixture",
            "policy_checks": [],
            "memories": [],
            "retrieval": {
                "temporal": {
                    "temporal_projection_at": "2024-02-20T00:00:00Z",
                    "history_memory_ids": ["mem_rejected"],
                    "current_memory_ids": [],
                    "future_memory_ids": [],
                    "unlearned_memory_ids": ["mem_rejected"],
                    "learned_memory_ids": [],
                    "superseded_memory_ids": [],
                    "history_temporal_graph": {
                        "mem_rejected": {
                            "memory_id": "mem_rejected",
                            "temporal_state": "unlearned",
                        }
                    },
                    "current_temporal_graph": {},
                    "future_temporal_graph": {},
                    "superseded_temporal_graph": {},
                    "unlearned_temporal_graph": {
                        "mem_rejected": {
                            "memory_id": "mem_rejected",
                            "temporal_state": "unlearned",
                        }
                    },
                    "learned_temporal_graph": {},
                    "resolved_current_memory_ids": [],
                    "dropped_current_memory_ids": [],
                    "abstained_current_memory_ids": [],
                    "conflict_sets": [],
                    "abstention": {
                        "applied": False,
                        "reason": None,
                        "abstained_ids": [],
                        "conflict_reasons": [],
                    },
                }
            },
        }

        context = build_context(receipt)

        self.assertEqual(context["temporal"]["history_memory_ids"], ["mem_rejected"])
        self.assertEqual(context["temporal"]["future_memory_ids"], [])
        self.assertEqual(context["temporal"]["learned_memory_ids"], [])
        self.assertEqual(context["temporal"]["unlearned_memory_ids"], ["mem_rejected"])
        self.assertEqual(context["temporal"]["history_temporal_graph"]["mem_rejected"]["temporal_state"], "unlearned")
        self.assertEqual(context["temporal"]["unlearned_temporal_graph"]["mem_rejected"]["temporal_state"], "unlearned")

    def test_build_context_preserves_current_vs_history_temporal_envelopes(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("previous status page owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]

        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        self.assertEqual(temporal["selection_strategy"], "historical_preferred_v1")
        self.assertEqual(temporal["selection_reason"], "history-query-terms")
        self.assertEqual(temporal["selected_ids"], [stale.id, current.id])
        self.assertEqual(temporal["history_memory_ids"], [stale.id, current.id])
        self.assertEqual(temporal["current_memory_ids"], [current.id])
        self.assertEqual(temporal["superseded_memory_ids"], [stale.id])
        self.assertNotIn(unrelated.id, temporal["selected_temporal_graph"])
        self.assertEqual(temporal["injected_temporal_graph"][stale.id]["temporal_state"], "superseded")
        self.assertEqual(temporal["injected_temporal_graph"][stale.id]["temporal_resolution_kind"], "supersession")
        self.assertEqual(
            temporal["injected_temporal_graph"][stale.id]["temporal_resolution_reasons"],
            ["active-child-candidate"],
        )
        self.assertEqual(temporal["injected_temporal_graph"][stale.id]["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(temporal["injected_temporal_graph"][current.id]["temporal_state"], "current")
        self.assertIsNone(temporal["injected_temporal_graph"][current.id]["temporal_resolution_kind"])
        self.assertEqual(temporal["injected_temporal_graph"][current.id]["temporal_resolution_reasons"], [])

    def test_build_context_preserves_temporal_serial_metadata_for_current_vs_history_envelopes(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("previous status page owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        stale_serial = receipt_temporal["history_temporal_graph"][stale.id]["serial"]
        current_serial = receipt_temporal["history_temporal_graph"][current.id]["serial"]

        self.assertEqual(temporal["selected_ids"], [stale.id, current.id])
        self.assertNotIn(unrelated.id, temporal["selected_temporal_graph"])
        self.assertLess(stale_serial, current_serial)
        self.assertEqual(temporal["history_temporal_graph"][stale.id]["serial"], stale_serial)
        self.assertEqual(temporal["history_temporal_graph"][current.id]["serial"], current_serial)
        self.assertLess(
            temporal["history_temporal_graph"][stale.id]["serial"],
            temporal["history_temporal_graph"][current.id]["serial"],
        )
        self.assertEqual(temporal["selected_temporal_graph"][stale.id]["serial"], stale_serial)
        self.assertEqual(temporal["selected_temporal_graph"][current.id]["serial"], current_serial)
        self.assertEqual(temporal["injected_temporal_graph"][stale.id]["serial"], stale_serial)
        self.assertEqual(temporal["injected_temporal_graph"][current.id]["serial"], current_serial)
        self.assertEqual(temporal["injected_temporal_graph"][stale.id]["temporal_state"], "superseded")
        self.assertEqual(temporal["injected_temporal_graph"][current.id]["temporal_state"], "current")

    def test_build_context_preserves_current_vs_history_ordering_metadata(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("previous status page owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]

        self.assertEqual(temporal["selected_ids"], [stale.id, current.id])
        self.assertEqual(current_ordering, receipt_temporal["current_ordering"])
        self.assertEqual(history_ordering, receipt_temporal["history_ordering"])
        self.assertFalse(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "retrieval_rank")
        self.assertEqual(current_ordering["source"], "baseline")
        self.assertEqual(current_ordering["reason"], "current-only-retrieval-rank")
        self.assertEqual(
            current_ordering["selected_current_rankings"],
            [{"memory_id": current.id, "rank": 2}],
        )
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [{"memory_id": current.id, "rank": 2, "selected": True}],
        )
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "history-query-terms")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [
                {"memory_id": stale.id, "rank": 1},
                {"memory_id": current.id, "rank": 2},
            ],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [
                {"memory_id": stale.id, "rank": 1, "selected": True},
                {"memory_id": current.id, "rank": 2, "selected": True},
            ],
        )
        self.assertNotIn(unrelated.id, temporal["selected_temporal_graph"])

    def test_build_context_preserves_current_only_identity_ordering_metadata(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("current status page owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]

        self.assertEqual(temporal["selected_ids"], [current.id])
        self.assertEqual(current_ordering, receipt_temporal["current_ordering"])
        self.assertEqual(history_ordering, receipt_temporal["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "retrieval_rank")
        self.assertEqual(current_ordering["source"], "baseline")
        self.assertEqual(current_ordering["reason"], "current-only-retrieval-rank")
        self.assertEqual(
            current_ordering["selected_current_rankings"],
            [{"memory_id": current.id, "rank": 2}],
        )
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [{"memory_id": current.id, "rank": 2, "selected": True}],
        )
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "current-query-terms")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        self.assertEqual(temporal["selected_temporal_graph"][current.id]["temporal_state"], "current")
        self.assertNotIn(unrelated.id, temporal["selected_temporal_graph"])
        self.assertNotIn(stale.id, temporal["selected_temporal_graph"])

    def test_build_context_preserves_bitemporal_identity_metadata_for_current_vs_history_envelopes(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("previous status page owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        history_graph = temporal["history_temporal_graph"]
        selected_graph = temporal["selected_temporal_graph"]

        self.assertEqual(temporal["selected_ids"], [stale.id, current.id])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertNotIn(unrelated.id, selected_graph)

        self.assertEqual(history_graph[stale.id]["learned_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["superseded_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["superseded_by_ids"], [current.id])
        self.assertEqual(history_graph[stale.id]["temporal_state"], "superseded")
        self.assertEqual(history_graph[stale.id]["temporal_resolution_kind"], "supersession")

        self.assertEqual(history_graph[current.id]["learned_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[current.id]["valid_from"], "2024-02-01T00:00:00Z")
        self.assertIsNone(history_graph[current.id]["valid_to"])
        self.assertIsNone(history_graph[current.id]["superseded_at"])
        self.assertEqual(history_graph[current.id]["superseded_by_ids"], [])
        self.assertEqual(history_graph[current.id]["temporal_state"], "current")
        self.assertIsNone(history_graph[current.id]["temporal_resolution_kind"])

        self.assertEqual(selected_graph[stale.id]["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(selected_graph[stale.id]["superseded_by_ids"], [current.id])
        self.assertEqual(selected_graph[current.id]["valid_from"], "2024-02-01T00:00:00Z")
        self.assertEqual(selected_graph[current.id]["temporal_state"], "current")

        self.assertEqual(history_graph[stale.id], receipt_temporal["history_temporal_graph"][stale.id])
        self.assertEqual(history_graph[current.id], receipt_temporal["history_temporal_graph"][current.id])
        self.assertEqual(selected_graph[stale.id], receipt_temporal["selected_temporal_graph"][stale.id])
        self.assertEqual(selected_graph[current.id], receipt_temporal["selected_temporal_graph"][current.id])

    def test_build_context_preserves_full_bitemporal_identity_temporal_graph(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("previous status page owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        temporal_graph = temporal["temporal_graph"]

        self.assertCountEqual(list(temporal_graph), [stale.id, current.id])
        self.assertNotIn(unrelated.id, temporal_graph)
        self.assertEqual(temporal_graph[stale.id]["learned_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(temporal_graph[stale.id]["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(temporal_graph[stale.id]["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(temporal_graph[stale.id]["superseded_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(temporal_graph[stale.id]["superseded_by_ids"], [current.id])
        self.assertEqual(temporal_graph[stale.id]["temporal_state"], "superseded")
        self.assertEqual(temporal_graph[current.id]["learned_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(temporal_graph[current.id]["valid_from"], "2024-02-01T00:00:00Z")
        self.assertIsNone(temporal_graph[current.id]["valid_to"])
        self.assertIsNone(temporal_graph[current.id]["superseded_at"])
        self.assertEqual(temporal_graph[current.id]["superseded_by_ids"], [])
        self.assertEqual(temporal_graph[current.id]["temporal_state"], "current")
        self.assertEqual(temporal_graph, receipt_temporal["temporal_graph"])

    def test_build_context_preserves_bitemporal_identity_metadata_for_current_vs_future_envelopes(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        future = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[current.id],
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2099-01-01T00:00:00Z", "2099-01-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2099-01-01T00:00:00Z", future.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("status page owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        current_graph = temporal["current_temporal_graph"]
        future_graph = temporal["future_temporal_graph"]
        selected_graph = temporal["selected_temporal_graph"]

        self.assertEqual(temporal["selected_ids"], [future.id])
        self.assertEqual(temporal["current_memory_ids"], [current.id])
        self.assertEqual(temporal["future_memory_ids"], [future.id])
        self.assertNotIn(unrelated.id, current_graph)
        self.assertNotIn(unrelated.id, future_graph)
        self.assertNotIn(unrelated.id, selected_graph)

        self.assertEqual(current_graph[current.id]["learned_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(current_graph[current.id]["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(current_graph[current.id]["valid_to"], "2099-01-01T00:00:00Z")
        self.assertEqual(current_graph[current.id]["superseded_at"], "2099-01-01T00:00:00Z")
        self.assertEqual(current_graph[current.id]["superseded_by_ids"], [future.id])
        self.assertEqual(current_graph[current.id]["temporal_state"], "current")
        self.assertEqual(current_graph[current.id]["current_resolution"], "selected")
        self.assertIsNone(current_graph[current.id]["temporal_resolution_kind"])

        self.assertEqual(future_graph[future.id]["learned_at"], "2099-01-01T00:00:00Z")
        self.assertEqual(future_graph[future.id]["valid_from"], "2099-01-01T00:00:00Z")
        self.assertIsNone(future_graph[future.id]["valid_to"])
        self.assertIsNone(future_graph[future.id]["superseded_at"])
        self.assertEqual(future_graph[future.id]["superseded_by_ids"], [])
        self.assertEqual(future_graph[future.id]["status_at_query"], "future")
        self.assertEqual(future_graph[future.id]["temporal_state"], "future")
        self.assertIsNone(future_graph[future.id]["current_resolution"])
        self.assertIsNone(future_graph[future.id]["temporal_resolution_kind"])

        self.assertEqual(selected_graph[future.id]["valid_from"], "2099-01-01T00:00:00Z")
        self.assertEqual(selected_graph[future.id]["temporal_state"], "future")

        self.assertEqual(current_graph[current.id], receipt_temporal["current_temporal_graph"][current.id])
        self.assertEqual(future_graph[future.id], receipt_temporal["future_temporal_graph"][future.id])
        self.assertEqual(selected_graph[future.id], receipt_temporal["selected_temporal_graph"][future.id])

    def test_build_context_preserves_bitemporal_identity_metadata_for_learned_only_query_envelopes(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        learned = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'PROPOSED'",
            ("2024-02-01T00:00:00Z", learned.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            learned_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "learned temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        learned_graph = temporal["learned_temporal_graph"]

        self.assertEqual(temporal["history_memory_ids"], [learned.id])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [learned.id])
        self.assertEqual(temporal["selected_ids"], [learned.id])
        self.assertEqual(temporal["selection_strategy"], "learned_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-learned-only-filter")
        self.assertNotIn(unrelated.id, history_graph)
        self.assertNotIn(current.id, history_graph)
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_graph[learned.id]["learned_at"], "2024-02-01T00:00:00Z")
        self.assertIsNone(history_graph[learned.id]["valid_from"])
        self.assertIsNone(history_graph[learned.id]["valid_to"])
        self.assertIsNone(history_graph[learned.id]["superseded_at"])
        self.assertEqual(history_graph[learned.id]["superseded_by_ids"], [])
        self.assertEqual(history_graph[learned.id]["status_at_query"], "quarantined")
        self.assertEqual(history_graph[learned.id]["temporal_state"], "learned")
        self.assertIsNone(history_graph[learned.id]["current_resolution"])
        self.assertIsNone(history_graph[learned.id]["temporal_resolution_kind"])
        self.assertEqual(history_graph[learned.id]["temporal_resolution_reasons"], [])

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-learned-only-filter")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [{"memory_id": learned.id, "rank": 1}],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [{"memory_id": learned.id, "rank": 1, "selected": True}],
        )
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "learned_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [current.id, learned.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [learned.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(learned_graph[learned.id], snapshot["learned_temporal_graph"][learned.id])
        self.assertEqual(history_graph[learned.id], snapshot["history_temporal_graph"][learned.id])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_learned_empty_subset(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            learned_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "learned temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertTrue(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "learned_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-learned-only-filter")

        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["temporal_graph"], {})
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-learned-only-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "learned_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])

    def test_build_context_preserves_query_at_no_search_identity_snapshot_controls_for_learned_empty_subset(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            learned_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "learned no-search temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertTrue(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "learned_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-learned-only-filter")
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["temporal_graph"], {})
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-learned-only-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "learned_only")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])

    def test_build_context_preserves_query_at_no_search_learned_scope_bitemporal_fields(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        learned = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'PROPOSED'",
            ("2024-02-01T00:00:00Z", learned.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            learned_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "learned no-search temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        learned_graph = temporal["learned_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertTrue(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["history_memory_ids"], [learned.id])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [learned.id])
        self.assertEqual(temporal["selected_ids"], [learned.id])
        self.assertEqual(temporal["selection_strategy"], "learned_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-learned-only-filter")
        self.assertNotIn(unrelated.id, history_graph)
        self.assertNotIn(current.id, history_graph)
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_graph[learned.id]["learned_at"], "2024-02-01T00:00:00Z")
        self.assertIsNone(history_graph[learned.id]["valid_from"])
        self.assertIsNone(history_graph[learned.id]["valid_to"])
        self.assertIsNone(history_graph[learned.id]["superseded_at"])
        self.assertIsNone(history_graph[learned.id]["unlearned_at"])
        self.assertEqual(history_graph[learned.id]["superseded_by_ids"], [])
        self.assertEqual(history_graph[learned.id]["status_at_query"], "quarantined")
        self.assertEqual(history_graph[learned.id]["temporal_state"], "learned")
        self.assertIsNone(history_graph[learned.id]["current_resolution"])
        self.assertIsNone(history_graph[learned.id]["temporal_resolution_kind"])
        self.assertEqual(history_graph[learned.id]["temporal_resolution_reasons"], [])

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-learned-only-filter")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [{"memory_id": learned.id, "rank": 1}],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [{"memory_id": learned.id, "rank": 1, "selected": True}],
        )
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "learned_only")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, current.id, learned.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [learned.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(learned_graph[learned.id], snapshot["learned_temporal_graph"][learned.id])
        self.assertEqual(history_graph[learned.id], snapshot["history_temporal_graph"][learned.id])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_unlearned_empty_subset(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            unlearned_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "unlearned temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertTrue(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "unlearned_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-unlearned-only-filter")

        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-unlearned-only-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "unlearned_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(temporal["conflict_sets"], [])
        self.assertFalse(temporal["abstention"]["applied"])
        self.assertNotIn(unrelated.id, temporal["history_temporal_graph"])
        self.assertNotIn(stale.id, temporal["history_temporal_graph"])
        self.assertNotIn(current.id, temporal["history_temporal_graph"])

    def test_build_context_preserves_query_at_no_search_identity_snapshot_controls_for_unlearned_empty_subset(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            unlearned_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "unlearned no-search temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertTrue(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "unlearned_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-unlearned-only-filter")
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-unlearned-only-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "unlearned_only")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(temporal["conflict_sets"], [])
        self.assertFalse(temporal["abstention"]["applied"])

    def test_build_context_preserves_unlearned_selection_metadata_for_query_at_subset(self):
        revoked = self.store.remember(
            "Release checklist owner was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            status="active",
        )
        forgotten = self.store.remember(
            "Temporary outage snack was ramen.",
            memory_type="episodic",
            scope="project",
            source_kind="human",
            status="active",
        )
        rejected = self.store.remember(
            "Release freeze owner is Mallory.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", revoked.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z", forgotten.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-03T00:00:00Z", "2024-01-03T00:00:00Z", rejected.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", revoked.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-02T00:00:00Z", forgotten.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'PROPOSED'",
            ("2024-01-03T00:00:00Z", rejected.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        self.store.revoke(revoked.id, actor_id="reviewer", reason="source evidence was wrong")
        self.store.forget(forgotten.id, actor_id="reviewer")
        self.store.reject(rejected.id, actor_id="reviewer", reason="superseded staffing plan")
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'REVOKED'",
            ("2024-02-10T00:00:00Z", revoked.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'FORGOTTEN'",
            ("2024-02-11T00:00:00Z", forgotten.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'REJECTED'",
            ("2024-02-12T00:00:00Z", rejected.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            unlearned_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "unlearned temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        unlearned_graph = temporal["unlearned_temporal_graph"]

        self.assertEqual(temporal["history_memory_ids"], [revoked.id, forgotten.id, rejected.id])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [revoked.id, forgotten.id, rejected.id])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["selected_ids"], [revoked.id, forgotten.id, rejected.id])
        self.assertEqual(temporal["selection_strategy"], "unlearned_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-unlearned-only-filter")
        self.assertNotIn(current.id, history_graph)
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-unlearned-only-filter")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [
                {"memory_id": revoked.id, "rank": 1},
                {"memory_id": forgotten.id, "rank": 2},
                {"memory_id": rejected.id, "rank": 3},
            ],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [
                {"memory_id": revoked.id, "rank": 1, "selected": True},
                {"memory_id": forgotten.id, "rank": 2, "selected": True},
                {"memory_id": rejected.id, "rank": 3, "selected": True},
            ],
        )
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "unlearned_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [revoked.id, forgotten.id, rejected.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [revoked.id, forgotten.id, rejected.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])

        self.assertEqual(history_graph[revoked.id]["temporal_resolution_reasons"], ["revoked"])
        self.assertEqual(history_graph[forgotten.id]["temporal_resolution_reasons"], ["forgotten"])
        self.assertEqual(history_graph[rejected.id]["temporal_resolution_reasons"], ["deprecated"])
        self.assertEqual(history_graph[revoked.id]["learned_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[revoked.id]["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[revoked.id]["valid_to"], "2024-02-10T00:00:00Z")
        self.assertEqual(history_graph[revoked.id]["unlearned_at"], "2024-02-10T00:00:00Z")
        self.assertIsNone(history_graph[revoked.id]["superseded_at"])
        self.assertEqual(history_graph[forgotten.id]["learned_at"], "2024-01-02T00:00:00Z")
        self.assertEqual(history_graph[forgotten.id]["valid_from"], "2024-01-02T00:00:00Z")
        self.assertEqual(history_graph[forgotten.id]["valid_to"], "2024-02-11T00:00:00Z")
        self.assertEqual(history_graph[forgotten.id]["unlearned_at"], "2024-02-11T00:00:00Z")
        self.assertIsNone(history_graph[forgotten.id]["superseded_at"])
        self.assertEqual(history_graph[rejected.id]["learned_at"], "2024-01-03T00:00:00Z")
        self.assertIsNone(history_graph[rejected.id]["valid_from"])
        self.assertEqual(history_graph[rejected.id]["valid_to"], "2024-02-12T00:00:00Z")
        self.assertEqual(history_graph[rejected.id]["unlearned_at"], "2024-02-12T00:00:00Z")
        self.assertIsNone(history_graph[rejected.id]["superseded_at"])
        self.assertEqual(unlearned_graph[revoked.id], snapshot["unlearned_temporal_graph"][revoked.id])
        self.assertEqual(unlearned_graph[forgotten.id], snapshot["unlearned_temporal_graph"][forgotten.id])
        self.assertEqual(unlearned_graph[rejected.id], snapshot["unlearned_temporal_graph"][rejected.id])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_selected_current_subset(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            current_resolution="selected",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "selected current temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]
        selected_graph = temporal["selected_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "selected")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [current.id])
        self.assertEqual(temporal["selection_strategy"], "current_only_v1")
        self.assertEqual(temporal["selection_reason"], "default-current-only")
        self.assertEqual(
            temporal["current_history_receipt_metadata"],
            {
                "filter": "current_resolution:selected",
                "base_history_memory_ids": [stale.id, current.id],
                "base_current_memory_ids": [current.id],
                "included_history_memory_ids": [current.id],
                "included_current_memory_ids": [current.id],
                "omitted_history_memory_ids": [stale.id],
                "omitted_current_memory_ids": [],
            },
        )

        self.assertEqual(temporal["history_memory_ids"], [current.id])
        self.assertEqual(temporal["current_memory_ids"], [current.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [current.id])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertNotIn(stale.id, history_graph)
        self.assertEqual(history_graph[current.id]["temporal_state"], "current")
        self.assertEqual(history_graph[current.id]["current_resolution"], "selected")
        self.assertEqual(current_graph[current.id], snapshot["current_temporal_graph"][current.id])
        self.assertEqual(selected_graph[current.id], snapshot["selected_temporal_graph"][current.id])
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]

        self.assertEqual(current_ordering, snapshot["current_ordering"])
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "retrieval_rank")
        self.assertEqual(current_ordering["source"], "baseline")
        self.assertEqual(current_ordering["reason"], "current-only-retrieval-rank")
        self.assertEqual(
            current_ordering["selected_current_rankings"],
            [{"memory_id": current.id, "rank": 2}],
        )
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [{"memory_id": current.id, "rank": 2, "selected": True}],
        )
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "default-current-only")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])

    def test_build_context_preserves_query_at_selected_snapshot_receipt_metadata_for_empty_current_conflict(self):
        first = self.store.remember(
            "Incident owner is Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            trust=0.95,
            authority="medium",
            status="active",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, second.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            current_resolution="selected",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "selected current empty temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["current_resolution"], "selected")
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:selected")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [first.id, second.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [first.id, second.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertNotIn("selection_strategy", temporal)
        self.assertNotIn("current_ordering", temporal)

    def test_build_context_preserves_query_at_no_search_selected_scope_identity_bitemporal_fields(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            current_resolution="selected",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search selected current temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]
        selected_graph = temporal["selected_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertEqual(temporal["current_resolution"], "selected")
        self.assertEqual(temporal["history_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(temporal["current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["selected_ids"], [unrelated.id, current.id])
        self.assertEqual(temporal["selection_strategy"], "current_only_v1")
        self.assertEqual(temporal["selection_reason"], "default-current-only")
        self.assertNotIn(stale.id, history_graph)
        self.assertEqual(history_graph, current_graph)
        self.assertEqual(history_graph, selected_graph)
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:selected")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [stale.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]
        self.assertEqual(current_ordering, snapshot["current_ordering"])
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "retrieval_rank")
        self.assertEqual(current_ordering["source"], "baseline")
        self.assertEqual(current_ordering["reason"], "current-only-retrieval-rank")
        self.assertCountEqual(
            current_ordering["selected_current_rankings"],
            [
                {"memory_id": unrelated.id, "rank": 2},
                {"memory_id": current.id, "rank": 3},
            ],
        )
        self.assertCountEqual(
            current_ordering["considered_current_rankings"],
            [
                {"memory_id": unrelated.id, "rank": 2, "selected": True},
                {"memory_id": current.id, "rank": 3, "selected": True},
            ],
        )
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "default-current-only")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        self.assertEqual(history_graph[unrelated.id]["temporal_state"], "current")
        self.assertEqual(history_graph[unrelated.id]["learned_at"], "2024-01-15T00:00:00Z")
        self.assertEqual(history_graph[unrelated.id]["valid_from"], "2024-01-15T00:00:00Z")
        self.assertIsNone(history_graph[unrelated.id]["valid_to"])
        self.assertIsNone(history_graph[unrelated.id]["superseded_at"])
        self.assertEqual(history_graph[unrelated.id]["superseded_by_ids"], [])
        self.assertEqual(history_graph[unrelated.id]["current_resolution"], "selected")
        self.assertIsNone(history_graph[unrelated.id]["temporal_resolution_kind"])
        self.assertEqual(history_graph[unrelated.id]["temporal_resolution_reasons"], [])
        self.assertEqual(history_graph[current.id]["temporal_state"], "current")
        self.assertEqual(history_graph[current.id]["learned_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[current.id]["valid_from"], "2024-02-01T00:00:00Z")
        self.assertIsNone(history_graph[current.id]["valid_to"])
        self.assertIsNone(history_graph[current.id]["superseded_at"])
        self.assertEqual(history_graph[current.id]["superseded_by_ids"], [])
        self.assertEqual(history_graph[current.id]["current_resolution"], "selected")
        self.assertIsNone(history_graph[current.id]["temporal_resolution_kind"])
        self.assertEqual(history_graph[current.id]["temporal_resolution_reasons"], [])
        self.assertEqual(current_graph[current.id], snapshot["current_temporal_graph"][current.id])
        self.assertEqual(selected_graph[current.id], snapshot["selected_temporal_graph"][current.id])

    def test_build_context_preserves_query_at_no_search_selected_scope_pre_activation_identity_metadata(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        future = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[current.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-01-20T00:00:00Z",
            scope="project",
            current_resolution="selected",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search selected pre-activation temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]
        selected_graph = temporal["selected_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-01-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertEqual(temporal["current_resolution"], "selected")
        self.assertEqual(temporal["history_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(temporal["current_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["selected_ids"], [current.id, unrelated.id])
        self.assertEqual(temporal["selection_strategy"], "current_only_v1")
        self.assertEqual(temporal["selection_reason"], "default-current-only")
        self.assertNotIn(future.id, history_graph)
        self.assertEqual(history_graph, current_graph)
        self.assertEqual(history_graph, selected_graph)
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:selected")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]
        self.assertEqual(current_ordering, snapshot["current_ordering"])
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "retrieval_rank")
        self.assertEqual(current_ordering["source"], "baseline")
        self.assertEqual(current_ordering["reason"], "current-only-retrieval-rank")
        self.assertEqual(
            current_ordering["selected_current_rankings"],
            [
                {"memory_id": current.id, "rank": 1},
                {"memory_id": unrelated.id, "rank": 2},
            ],
        )
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [
                {"memory_id": current.id, "rank": 1, "selected": True},
                {"memory_id": unrelated.id, "rank": 2, "selected": True},
            ],
        )
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "default-current-only")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        self.assertEqual(history_graph[current.id]["temporal_state"], "current")
        self.assertEqual(history_graph[current.id]["learned_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[current.id]["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[current.id]["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[current.id]["superseded_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[current.id]["superseded_by_ids"], [future.id])
        self.assertEqual(history_graph[current.id]["status_at_query"], "active")
        self.assertEqual(history_graph[current.id]["current_resolution"], "selected")
        self.assertEqual(history_graph[unrelated.id]["temporal_state"], "current")
        self.assertEqual(history_graph[unrelated.id]["learned_at"], "2024-01-15T00:00:00Z")
        self.assertEqual(history_graph[unrelated.id]["valid_from"], "2024-01-15T00:00:00Z")
        self.assertIsNone(history_graph[unrelated.id]["valid_to"])
        self.assertIsNone(history_graph[unrelated.id]["superseded_at"])
        self.assertEqual(history_graph[unrelated.id]["superseded_by_ids"], [])
        self.assertEqual(history_graph[unrelated.id]["status_at_query"], "active")
        self.assertEqual(history_graph[unrelated.id]["current_resolution"], "selected")

    def test_build_context_preserves_query_at_default_identity_receipt_metadata(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "default identity temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["history_memory_ids"], [stale.id, current.id])
        self.assertEqual(temporal["current_memory_ids"], [current.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [current.id])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:all")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertEqual(history_graph[stale.id], snapshot["history_temporal_graph"][stale.id])
        self.assertEqual(history_graph[current.id], snapshot["history_temporal_graph"][current.id])
        self.assertEqual(current_graph[current.id], snapshot["current_temporal_graph"][current.id])

    def test_build_context_preserves_query_at_default_no_search_identity_receipt_metadata(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at("2024-02-20T00:00:00Z", scope="project")
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "default no-search identity temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertCountEqual(temporal["history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(temporal["current_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(temporal["resolved_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:all")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(receipt_metadata["included_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["included_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(history_graph[stale.id], snapshot["history_temporal_graph"][stale.id])
        self.assertEqual(history_graph[current.id], snapshot["history_temporal_graph"][current.id])
        self.assertEqual(current_graph[unrelated.id], snapshot["current_temporal_graph"][unrelated.id])
        self.assertEqual(current_graph[current.id], snapshot["current_temporal_graph"][current.id])

    def test_build_context_preserves_query_at_default_no_search_identity_bitemporal_fields(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at("2024-02-20T00:00:00Z", scope="project")
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "default no-search identity temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        unrelated_envelope = temporal["history_temporal_graph"][unrelated.id]
        stale_envelope = temporal["history_temporal_graph"][stale.id]
        current_envelope = temporal["history_temporal_graph"][current.id]

        self.assertCountEqual(temporal["history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(temporal["current_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(temporal["resolved_current_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(list(temporal["history_temporal_graph"]), [unrelated.id, stale.id, current.id])
        self.assertCountEqual(list(temporal["current_temporal_graph"]), [unrelated.id, current.id])
        self.assertEqual(list(temporal["superseded_temporal_graph"]), [stale.id])

        self.assertEqual(unrelated_envelope["learned_at"], "2024-01-15T00:00:00Z")
        self.assertEqual(unrelated_envelope["valid_from"], "2024-01-15T00:00:00Z")
        self.assertIsNone(unrelated_envelope["valid_to"])
        self.assertIsNone(unrelated_envelope["superseded_at"])
        self.assertEqual(unrelated_envelope["superseded_by_ids"], [])
        self.assertEqual(unrelated_envelope["temporal_state"], "current")
        self.assertEqual(unrelated_envelope["current_resolution"], "selected")
        self.assertIsInstance(unrelated_envelope["serial"], int)

        self.assertEqual(stale_envelope["learned_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(stale_envelope["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(stale_envelope["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(stale_envelope["superseded_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(stale_envelope["superseded_by_ids"], [current.id])
        self.assertEqual(stale_envelope["temporal_state"], "superseded")
        self.assertEqual(stale_envelope["temporal_resolution_kind"], "supersession")
        self.assertEqual(stale_envelope["temporal_resolution_reasons"], ["active-child-candidate"])
        self.assertIsNone(stale_envelope["current_resolution"])
        self.assertIsInstance(stale_envelope["serial"], int)

        self.assertEqual(current_envelope["learned_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(current_envelope["valid_from"], "2024-02-01T00:00:00Z")
        self.assertIsNone(current_envelope["valid_to"])
        self.assertIsNone(current_envelope["superseded_at"])
        self.assertEqual(current_envelope["superseded_by_ids"], [])
        self.assertEqual(current_envelope["temporal_state"], "current")
        self.assertIsNone(current_envelope["temporal_resolution_kind"])
        self.assertEqual(current_envelope["temporal_resolution_reasons"], [])
        self.assertEqual(current_envelope["current_resolution"], "selected")
        self.assertIsInstance(current_envelope["serial"], int)

        self.assertEqual(temporal["superseded_temporal_graph"][stale.id], stale_envelope)
        self.assertEqual(temporal["current_temporal_graph"][unrelated.id], unrelated_envelope)
        self.assertEqual(temporal["current_temporal_graph"][current.id], current_envelope)
        self.assertEqual(temporal["history_temporal_graph"][stale.id], snapshot["history_temporal_graph"][stale.id])
        self.assertEqual(temporal["current_temporal_graph"][unrelated.id], snapshot["current_temporal_graph"][unrelated.id])
        self.assertEqual(temporal["current_temporal_graph"][current.id], snapshot["current_temporal_graph"][current.id])

    def test_build_context_preserves_query_at_abstained_snapshot_controls_for_current_contradiction(self):
        first = self.store.remember(
            "Incident owner is Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        second = self.store.remember(
            "Incident owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            trust=0.95,
            authority="medium",
            status="active",
        )
        unrelated = self.store.remember(
            "Runbook owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="incident owner",
            current_resolution="abstained",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "abstained current temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]
        abstained_graph = temporal["abstained_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "incident owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "abstained")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertCountEqual(temporal["history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(temporal["current_memory_ids"], [first.id, second.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertCountEqual(temporal["abstained_current_memory_ids"], [first.id, second.id])
        abstained_ids = list(temporal["abstained_current_memory_ids"])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        self.assertEqual(temporal["selection_strategy"], "abstained_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-abstained-current-filter")
        self.assertEqual(temporal["selected_ids"], abstained_ids)
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:abstained")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["included_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["included_current_memory_ids"], [first.id, second.id])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertCountEqual(list(history_graph), [first.id, second.id])
        self.assertCountEqual(list(current_graph), [first.id, second.id])
        self.assertCountEqual(list(abstained_graph), [first.id, second.id])

        self.assertEqual(history_graph[first.id]["temporal_state"], "current")
        self.assertEqual(history_graph[first.id]["current_resolution"], "abstained")
        self.assertEqual(history_graph[first.id]["temporal_resolution_kind"], "contradiction")
        self.assertEqual(history_graph[first.id]["temporal_resolution_reasons"], ["lexical-current-conflict"])
        self.assertEqual(history_graph[second.id]["temporal_state"], "current")
        self.assertEqual(history_graph[second.id]["current_resolution"], "abstained")
        self.assertEqual(history_graph[second.id]["temporal_resolution_kind"], "contradiction")
        self.assertEqual(history_graph[second.id]["temporal_resolution_reasons"], ["lexical-current-conflict"])
        self.assertEqual(current_graph[first.id], snapshot["current_temporal_graph"][first.id])
        self.assertEqual(current_graph[second.id], snapshot["current_temporal_graph"][second.id])
        self.assertEqual(abstained_graph[first.id], snapshot["abstained_temporal_graph"][first.id])
        self.assertEqual(abstained_graph[second.id], snapshot["abstained_temporal_graph"][second.id])
        self.assertTrue(temporal["abstention"]["applied"])
        self.assertEqual(temporal["abstention"]["reason"], "unresolved-current-conflict")
        self.assertCountEqual(temporal["abstention"]["abstained_ids"], [first.id, second.id])
        self.assertEqual(len(temporal["conflict_sets"]), 1)
        self.assertEqual(temporal["conflict_sets"][0]["resolution_outcome"], "abstained")
        self.assertCountEqual(temporal["conflict_sets"][0]["abstained_current_ids"], [first.id, second.id])
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]
        self.assertEqual(current_ordering, snapshot["current_ordering"])
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "current_conflict_abstention_rank")
        self.assertEqual(current_ordering["source"], "temporal_current_conflict_abstention")
        self.assertEqual(current_ordering["reason"], "explicit-abstained-current-filter")
        self.assertEqual(
            current_ordering["selected_current_rankings"],
            [{"memory_id": memory_id, "rank": index} for index, memory_id in enumerate(abstained_ids, start=1)],
        )
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [
                {"memory_id": memory_id, "rank": index, "selected": True}
                for index, memory_id in enumerate(abstained_ids, start=1)
            ],
        )
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "explicit-abstained-current-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])

    def test_build_context_preserves_hidden_query_at_abstained_snapshot_controls_for_current_contradiction(self):
        first = self.store.remember(
            "Incident owner is Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        second = self.store.remember(
            "Incident owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            trust=0.95,
            authority="medium",
            status="active",
        )
        unrelated = self.store.remember(
            "Runbook owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="incident owner",
            include_abstained_current=False,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "hidden abstained current temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "incident owner")
        self.assertFalse(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertCountEqual(temporal["abstained_current_memory_ids"], [first.id, second.id])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        self.assertNotIn("selection_strategy", temporal)
        self.assertNotIn("selection_reason", temporal)
        self.assertNotIn("current_ordering", temporal)
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "include_abstained_current:false")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [first.id, second.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [first.id, second.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertNotIn(unrelated.id, temporal["conflict_sets"][0]["abstained_current_ids"])
        self.assertTrue(temporal["abstention"]["applied"])
        self.assertEqual(temporal["abstention"]["reason"], "unresolved-current-conflict")
        self.assertCountEqual(temporal["abstention"]["abstained_ids"], [first.id, second.id])
        self.assertEqual(len(temporal["conflict_sets"]), 1)
        self.assertEqual(temporal["conflict_sets"][0]["resolution_outcome"], "abstained")
        self.assertCountEqual(temporal["conflict_sets"][0]["abstained_current_ids"], [first.id, second.id])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_abstained_empty_subset(self):
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            current_resolution="abstained",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "abstained identity temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "abstained")
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["selection_strategy"], "abstained_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-abstained-current-filter")
        self.assertEqual(temporal["selected_ids"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:abstained")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]
        self.assertEqual(current_ordering, snapshot["current_ordering"])
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "current_conflict_abstention_rank")
        self.assertEqual(current_ordering["source"], "temporal_current_conflict_abstention")
        self.assertEqual(current_ordering["reason"], "explicit-abstained-current-filter")
        self.assertEqual(current_ordering["selected_current_rankings"], [])
        self.assertEqual(current_ordering["considered_current_rankings"], [])
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "explicit-abstained-current-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_superseded_history_subset(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            superseded_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "superseded history temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        superseded_graph = temporal["superseded_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertTrue(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])

        self.assertEqual(temporal["history_memory_ids"], [stale.id])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [stale.id])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertNotIn(current.id, history_graph)
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-superseded-only-filter")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [{"memory_id": stale.id, "rank": 1}],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [{"memory_id": stale.id, "rank": 1, "selected": True}],
        )
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "superseded_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [stale.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])

        self.assertEqual(history_graph[stale.id]["temporal_state"], "superseded")
        self.assertEqual(history_graph[stale.id]["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["superseded_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["superseded_by_ids"], [current.id])
        self.assertEqual(history_graph[stale.id]["current_resolution"], None)
        self.assertEqual(history_graph[stale.id]["temporal_resolution_kind"], "supersession")
        self.assertEqual(history_graph[stale.id]["temporal_resolution_reasons"], ["active-child-candidate"])
        self.assertEqual(superseded_graph[stale.id], snapshot["superseded_temporal_graph"][stale.id])
        self.assertEqual(history_graph[stale.id], snapshot["history_temporal_graph"][stale.id])

    def test_build_context_preserves_query_at_no_search_superseded_identity_receipt_metadata(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            superseded_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search superseded temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        superseded_graph = temporal["superseded_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertTrue(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["history_memory_ids"], [stale.id])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [stale.id])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertNotIn(current.id, history_graph)
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]

        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-superseded-only-filter")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [{"memory_id": stale.id, "rank": 1}],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [{"memory_id": stale.id, "rank": 1, "selected": True}],
        )
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "superseded_only")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, stale.id, current.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [stale.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(history_graph[stale.id]["temporal_state"], "superseded")
        self.assertEqual(history_graph[stale.id]["learned_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["valid_from"], "2024-01-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["valid_to"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["superseded_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[stale.id]["superseded_by_ids"], [current.id])
        self.assertEqual(history_graph[stale.id]["current_resolution"], None)
        self.assertEqual(history_graph[stale.id]["temporal_resolution_kind"], "supersession")
        self.assertEqual(history_graph[stale.id]["temporal_resolution_reasons"], ["active-child-candidate"])
        self.assertEqual(history_graph[stale.id]["valid_to"], history_graph[stale.id]["superseded_at"])
        self.assertEqual(superseded_graph[stale.id], snapshot["superseded_temporal_graph"][stale.id])
        self.assertEqual(history_graph[stale.id], snapshot["history_temporal_graph"][stale.id])

    def test_build_context_preserves_query_at_no_search_superseded_identity_empty_predecessor_guard(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        future = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[current.id],
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-01-20T00:00:00Z",
            scope="project",
            superseded_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search superseded temporal empty passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-01-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertTrue(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["selected_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "superseded_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-superseded-only-filter")
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-superseded-only-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "superseded_only")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [unrelated.id, current.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [unrelated.id, current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(temporal["conflict_sets"], [])
        self.assertFalse(temporal["abstention"]["applied"])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_future_subset(self):
        learned = self.store.remember(
            "Release freeze owner is Mallory.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
        )
        current = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        future = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[current.id],
            status="active",
        )
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-05T00:00:00Z", "2024-01-05T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'PROPOSED'",
            ("2024-01-05T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-01-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            future_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "future temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        future_graph = temporal["future_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-01-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertTrue(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [future.id])
        self.assertEqual(temporal["selection_strategy"], "future_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-future-only-filter")

        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [future.id])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-future-only-filter")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [{"memory_id": future.id, "rank": 1}],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [{"memory_id": future.id, "rank": 1, "selected": True}],
        )
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "future_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertNotIn(learned.id, future_graph)
        self.assertNotIn(current.id, future_graph)
        self.assertNotIn(unrelated.id, future_graph)

        self.assertEqual(future_graph[future.id]["temporal_state"], "future")
        self.assertEqual(future_graph[future.id]["valid_from"], "2024-02-01T00:00:00Z")
        self.assertEqual(future_graph[future.id]["superseded_by_ids"], [])
        self.assertIsNone(future_graph[future.id]["current_resolution"])
        self.assertIsNone(future_graph[future.id]["temporal_resolution_kind"])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_future_empty_subset(self):
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            future_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "future temporal empty passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertTrue(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "future_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-future-only-filter")
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-future-only-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "future_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])

    def test_build_context_preserves_query_at_no_search_identity_snapshot_controls_for_future_subset(self):
        learned = self.store.remember(
            "Release freeze owner is Mallory.",
            memory_type="semantic",
            scope="project",
            source_kind="agent",
        )
        current = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        future = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[current.id],
            status="active",
        )
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-05T00:00:00Z", "2024-01-05T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'PROPOSED'",
            ("2024-01-05T00:00:00Z", learned.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", future.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-01-20T00:00:00Z",
            scope="project",
            future_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search future temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        future_graph = temporal["future_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-01-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertTrue(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [future.id])
        self.assertEqual(temporal["selection_strategy"], "future_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-future-only-filter")
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [future.id])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-future-only-filter")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [{"memory_id": future.id, "rank": 1}],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [{"memory_id": future.id, "rank": 1, "selected": True}],
        )
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "future_only")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [learned.id, current.id, unrelated.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [learned.id, current.id, unrelated.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [current.id, unrelated.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertNotIn(learned.id, future_graph)
        self.assertNotIn(current.id, future_graph)
        self.assertNotIn(unrelated.id, future_graph)
        self.assertEqual(future_graph[future.id]["temporal_state"], "future")
        self.assertEqual(future_graph[future.id]["learned_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(future_graph[future.id]["valid_from"], "2024-02-01T00:00:00Z")
        self.assertIsNone(future_graph[future.id]["valid_to"])
        self.assertIsNone(future_graph[future.id]["superseded_at"])
        self.assertIsNone(future_graph[future.id]["unlearned_at"])
        self.assertEqual(future_graph[future.id]["superseded_by_ids"], [])
        self.assertEqual(future_graph[future.id]["status_at_query"], "future")
        self.assertIsNone(future_graph[future.id]["current_resolution"])
        self.assertIsNone(future_graph[future.id]["temporal_resolution_kind"])
        self.assertEqual(future_graph[future.id]["temporal_resolution_reasons"], [])
        self.assertNotIn("query_current_candidate_rank", future_graph[future.id])

    def test_build_context_preserves_query_at_no_search_identity_snapshot_controls_for_future_empty_subset(self):
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            future_only=True,
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search future temporal empty passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "all")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertTrue(temporal["future_only"])
        self.assertEqual(temporal["selected_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "future_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-future-only-filter")
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        history_ordering = temporal["history_ordering"]
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "historical_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_selection")
        self.assertEqual(history_ordering["reason"], "explicit-future-only-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "future_only")
        self.assertEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])

    def test_build_context_preserves_temporal_omitted_subset_envelopes(self):
        policy_path = self.tmp_path / "policy.json"
        policy_path.write_text('{"schema":"zerker.policy.v1","deny_labels":["secret"]}', encoding="utf-8")
        store = MemoryStore(self.tmp_path / "temporal-policy.sqlite", policy_path=policy_path)
        store.init()
        withheld = store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            labels=["secret"],
        )
        stale = store.remember(
            "Incident owner was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = store.remember(
            "Incident owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", withheld.id),
        )
        store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", withheld.id),
        )
        store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        store.conn.commit()

        withheld_receipt = store.inject(
            "who is the status page owner",
            agent_id="codex",
            risk="low",
            scope="project",
        )
        withheld_context = build_context(withheld_receipt)
        withheld_temporal = withheld_context["temporal"]

        self.assertEqual(withheld_receipt["withheld"][0]["memory_id"], withheld.id)
        self.assertEqual(withheld_temporal["withheld_temporal_graph"][withheld.id]["temporal_state"], "current")
        self.assertEqual(withheld_temporal["withheld_temporal_graph"][withheld.id]["valid_from"], "2024-02-01T00:00:00Z")

        budget_receipt = store.inject(
            "when did the incident owner change then",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=max(approx_memory_tokens(stale), approx_memory_tokens(current)),
        )
        budget_context = build_context(budget_receipt)
        budget_temporal = budget_context["temporal"]

        self.assertEqual(budget_receipt["retrieval"]["packing"]["budget_dropped"][0]["memory_id"], current.id)
        self.assertEqual(budget_temporal["injected_temporal_graph"][stale.id]["temporal_state"], "superseded")
        self.assertEqual(budget_temporal["budget_dropped_temporal_graph"][current.id]["temporal_state"], "current")
        self.assertEqual(budget_temporal["budget_dropped_temporal_graph"][current.id]["valid_from"], "2024-02-01T00:00:00Z")

    def test_build_context_preserves_current_conflict_abstention_without_injected_memories(self):
        first = self.store.remember(
            "Incident owner is Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            trust=0.95,
            authority="medium",
            status="active",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, second.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("incident owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        conflict = next(item for item in temporal["conflict_sets"] if item["reason"] == "lexical-current-conflict")

        self.assertEqual(context["memories"], [])
        self.assertEqual(temporal["selection_strategy"], "current_conflict_abstained_v1")
        self.assertEqual(temporal["selection_reason"], "lexical-current-conflict-abstained")
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertCountEqual(temporal["current_memory_ids"], [first.id, second.id])
        self.assertCountEqual(temporal["abstained_current_memory_ids"], [first.id, second.id])
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertCountEqual(list(temporal["abstained_temporal_graph"]), [first.id, second.id])
        self.assertEqual(temporal["abstained_temporal_graph"][first.id]["temporal_state"], "current")
        self.assertEqual(temporal["abstained_temporal_graph"][first.id]["current_resolution"], "abstained")
        self.assertEqual(temporal["abstained_temporal_graph"][first.id]["temporal_resolution_kind"], "contradiction")
        self.assertEqual(
            temporal["abstained_temporal_graph"][first.id]["temporal_resolution_reasons"],
            ["lexical-current-conflict"],
        )
        self.assertEqual(
            temporal["abstained_temporal_graph"][first.id]["current_conflict_reasons"],
            ["lexical-current-conflict"],
        )
        self.assertEqual(temporal["abstained_temporal_graph"][second.id]["temporal_state"], "current")
        self.assertEqual(temporal["abstained_temporal_graph"][second.id]["current_resolution"], "abstained")
        self.assertEqual(temporal["abstained_temporal_graph"][second.id]["temporal_resolution_kind"], "contradiction")
        self.assertEqual(
            temporal["abstained_temporal_graph"][second.id]["temporal_resolution_reasons"],
            ["lexical-current-conflict"],
        )
        self.assertEqual(
            temporal["abstained_temporal_graph"][second.id]["current_conflict_reasons"],
            ["lexical-current-conflict"],
        )
        self.assertEqual(temporal["injected_temporal_graph"], {})
        self.assertTrue(temporal["abstention"]["applied"])
        self.assertEqual(temporal["abstention"]["reason"], "unresolved-current-conflict")
        self.assertEqual(temporal["abstention"]["conflict_reasons"], ["lexical-current-conflict"])
        self.assertCountEqual(temporal["abstention"]["abstained_ids"], [first.id, second.id])
        current_ordering = temporal["current_ordering"]

        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "current_conflict_abstention_rank")
        self.assertEqual(current_ordering["source"], "temporal_current_conflict_abstention")
        self.assertEqual(current_ordering["reason"], "lexical-current-conflict-abstained")
        self.assertEqual(current_ordering["selected_current_rankings"], [])
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [{"memory_id": memory_id, "rank": index, "selected": False} for index, memory_id in enumerate(conflict["current_ids"], start=1)],
        )
        self.assertEqual(conflict["resolution_outcome"], "abstained")
        self.assertEqual(conflict["chosen_current_id"], None)
        self.assertCountEqual(conflict["abstained_current_ids"], [first.id, second.id])

    def test_build_context_preserves_temporal_serial_metadata_for_abstained_current_conflict(self):
        first = self.store.remember(
            "Incident owner is Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            trust=0.95,
            authority="medium",
            status="active",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, second.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("incident owner", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        first_serial = receipt_temporal["abstained_temporal_graph"][first.id]["serial"]
        second_serial = receipt_temporal["abstained_temporal_graph"][second.id]["serial"]

        self.assertLess(first_serial, second_serial)
        self.assertEqual(temporal["current_temporal_graph"][first.id]["serial"], first_serial)
        self.assertEqual(temporal["current_temporal_graph"][second.id]["serial"], second_serial)
        self.assertEqual(temporal["abstained_temporal_graph"][first.id]["serial"], first_serial)
        self.assertEqual(temporal["abstained_temporal_graph"][second.id]["serial"], second_serial)
        self.assertEqual(temporal["abstained_temporal_graph"][first.id]["current_resolution"], "abstained")
        self.assertEqual(temporal["abstained_temporal_graph"][second.id]["current_resolution"], "abstained")

    def test_build_context_preserves_dropped_current_conflict_subset(self):
        first = self.store.remember(
            "Deploy target is Render.",
            memory_type="semantic",
            scope="project",
            source_kind="document",
            authority="low",
            status="active",
        )
        second = self.store.remember(
            "Deploy target is Railway.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            authority="high",
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("deploy target", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        conflict = next(item for item in temporal["conflict_sets"] if item["reason"] == "lexical-current-conflict")

        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        self.assertCountEqual(temporal["current_memory_ids"], [first.id, second.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [second.id])
        self.assertEqual(temporal["dropped_current_memory_ids"], [first.id])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(list(temporal["dropped_current_temporal_graph"]), [first.id])
        self.assertEqual(temporal["dropped_current_temporal_graph"][first.id]["temporal_state"], "current")
        self.assertEqual(temporal["dropped_current_temporal_graph"][first.id]["current_resolution"], "dropped")
        self.assertEqual(
            temporal["dropped_current_temporal_graph"][first.id]["temporal_resolution_kind"],
            "contradiction",
        )
        self.assertEqual(
            temporal["dropped_current_temporal_graph"][first.id]["temporal_resolution_reasons"],
            ["lexical-current-conflict"],
        )
        self.assertEqual(
            temporal["dropped_current_temporal_graph"][first.id]["current_conflict_reasons"],
            ["lexical-current-conflict"],
        )
        current_ordering = temporal["current_ordering"]

        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "current_conflict_resolution_rank")
        self.assertEqual(current_ordering["source"], "temporal_current_conflict_resolution")
        self.assertEqual(current_ordering["reason"], "lexical-current-conflict-deterministic-resolution")
        self.assertEqual(current_ordering["selected_current_rankings"], [{"memory_id": second.id, "rank": 1}])
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [
                {"memory_id": second.id, "rank": 1, "selected": True},
                {"memory_id": first.id, "rank": 2, "selected": False},
            ],
        )
        self.assertEqual(list(temporal["injected_temporal_graph"]), [second.id])
        self.assertEqual(temporal["injected_temporal_graph"][second.id]["temporal_state"], "current")
        self.assertEqual(temporal["injected_temporal_graph"][second.id]["current_resolution"], "selected")
        self.assertEqual(temporal["injected_temporal_graph"][second.id]["temporal_resolution_kind"], "contradiction")
        self.assertEqual(
            temporal["injected_temporal_graph"][second.id]["temporal_resolution_reasons"],
            ["lexical-current-conflict"],
        )
        self.assertFalse(temporal["abstention"]["applied"])
        self.assertEqual(conflict["resolution_outcome"], "resolved")
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["dropped_current_ids"], [first.id])

    def test_build_context_preserves_temporal_serial_metadata_for_dropped_current_conflict(self):
        first = self.store.remember(
            "Deploy target is Render.",
            memory_type="semantic",
            scope="project",
            source_kind="document",
            authority="low",
            status="active",
        )
        second = self.store.remember(
            "Deploy target is Railway.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            authority="high",
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject("deploy target", agent_id="codex", risk="low", scope="project")
        context = build_context(receipt)
        temporal = context["temporal"]
        receipt_temporal = receipt["retrieval"]["temporal"]
        dropped_serial = receipt_temporal["dropped_current_temporal_graph"][first.id]["serial"]
        selected_serial = receipt_temporal["injected_temporal_graph"][second.id]["serial"]

        self.assertLess(dropped_serial, selected_serial)
        self.assertEqual(temporal["current_temporal_graph"][first.id]["serial"], dropped_serial)
        self.assertEqual(temporal["current_temporal_graph"][second.id]["serial"], selected_serial)
        self.assertEqual(temporal["dropped_current_temporal_graph"][first.id]["serial"], dropped_serial)
        self.assertEqual(temporal["injected_temporal_graph"][second.id]["serial"], selected_serial)
        self.assertEqual(temporal["dropped_current_temporal_graph"][first.id]["current_resolution"], "dropped")
        self.assertEqual(temporal["injected_temporal_graph"][second.id]["current_resolution"], "selected")

    def test_build_context_preserves_query_at_dropped_snapshot_controls_for_current_conflict(self):
        first = self.store.remember(
            "Deploy target is Render.",
            memory_type="semantic",
            scope="project",
            source_kind="document",
            authority="low",
            status="active",
        )
        second = self.store.remember(
            "Deploy target is Railway.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            authority="high",
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="deploy target",
            current_resolution="dropped",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "dropped current temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "deploy target")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "dropped")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["history_memory_ids"], [first.id])
        self.assertEqual(temporal["current_memory_ids"], [first.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [first.id])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["selection_strategy"], "dropped_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-dropped-current-filter")
        self.assertEqual(temporal["selected_ids"], [first.id])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:dropped")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [first.id, second.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [first.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [first.id])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [second.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [second.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(list(temporal["history_temporal_graph"]), [first.id])
        self.assertEqual(list(temporal["current_temporal_graph"]), [first.id])
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(list(temporal["dropped_current_temporal_graph"]), [first.id])
        self.assertEqual(
            temporal["dropped_current_temporal_graph"][first.id],
            snapshot["dropped_current_temporal_graph"][first.id],
        )
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]
        self.assertEqual(current_ordering, snapshot["current_ordering"])
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "current_conflict_resolution_rank")
        self.assertEqual(current_ordering["source"], "temporal_current_conflict_resolution")
        self.assertEqual(current_ordering["reason"], "explicit-dropped-current-filter")
        self.assertEqual(current_ordering["selected_current_rankings"], [{"memory_id": first.id, "rank": 1}])
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [
                {"memory_id": first.id, "rank": 1, "selected": True},
                {"memory_id": second.id, "rank": 2, "selected": False},
            ],
        )
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "explicit-dropped-current-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])

    def test_build_context_preserves_query_at_no_search_dropped_scope_contradiction_bitemporal_fields(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        first = self.store.remember(
            "Deploy target is Render.",
            memory_type="semantic",
            scope="project",
            source_kind="document",
            authority="low",
            status="active",
        )
        second = self.store.remember(
            "Deploy target is Railway.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            authority="high",
            status="active",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", second.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            current_resolution="dropped",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search dropped current temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]
        dropped_graph = temporal["dropped_current_temporal_graph"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertEqual(temporal["current_resolution"], "dropped")
        self.assertEqual(temporal["history_memory_ids"], [first.id])
        self.assertEqual(temporal["current_memory_ids"], [first.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [first.id])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertNotIn(second.id, history_graph)
        self.assertEqual(history_graph, current_graph)
        self.assertEqual(history_graph, dropped_graph)
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:dropped")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, first.id, second.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, first.id, second.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [first.id])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [first.id])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [unrelated.id, second.id])
        self.assertCountEqual(receipt_metadata["omitted_current_memory_ids"], [unrelated.id, second.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        self.assertEqual(history_graph[first.id]["temporal_state"], "current")
        self.assertEqual(history_graph[first.id]["learned_at"], "2024-02-01T00:00:00Z")
        self.assertEqual(history_graph[first.id]["valid_from"], "2024-02-01T00:00:00Z")
        self.assertIsNone(history_graph[first.id]["valid_to"])
        self.assertIsNone(history_graph[first.id]["superseded_at"])
        self.assertEqual(history_graph[first.id]["superseded_by_ids"], [])
        self.assertEqual(history_graph[first.id]["current_resolution"], "dropped")
        self.assertEqual(history_graph[first.id]["temporal_resolution_kind"], "contradiction")
        self.assertEqual(history_graph[first.id]["temporal_resolution_reasons"], ["lexical-current-conflict"])
        self.assertEqual(history_graph[first.id]["current_conflict_reasons"], ["lexical-current-conflict"])
        self.assertEqual(current_graph[first.id], snapshot["current_temporal_graph"][first.id])
        self.assertEqual(dropped_graph[first.id], snapshot["dropped_current_temporal_graph"][first.id])

    def test_build_context_preserves_query_at_no_search_abstained_scope_contradiction_bitemporal_fields(self):
        unrelated = self.store.remember(
            "Alice owns the billing exporter.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        first = self.store.remember(
            "Incident owner is Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            trust=0.95,
            authority="medium",
            status="active",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (shared_timestamp, shared_timestamp, second.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-15T00:00:00Z", unrelated.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, first.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            (shared_timestamp, second.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            current_resolution="abstained",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "no-search abstained current temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]
        history_graph = temporal["history_temporal_graph"]
        current_graph = temporal["current_temporal_graph"]
        abstained_graph = temporal["abstained_temporal_graph"]
        abstained_ids = list(temporal["abstained_current_memory_ids"])

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertNotIn("search_query", temporal)
        self.assertEqual(temporal["current_resolution"], "abstained")
        self.assertCountEqual(temporal["history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(temporal["current_memory_ids"], [first.id, second.id])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertCountEqual(temporal["abstained_current_memory_ids"], [first.id, second.id])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertNotIn(unrelated.id, history_graph)
        self.assertEqual(history_graph, current_graph)
        self.assertEqual(history_graph, abstained_graph)
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        self.assertEqual(temporal["future_temporal_graph"], {})
        self.assertEqual(temporal["superseded_temporal_graph"], {})
        self.assertEqual(temporal["unlearned_temporal_graph"], {})
        self.assertEqual(temporal["learned_temporal_graph"], {})
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:abstained")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [unrelated.id, first.id, second.id])
        self.assertCountEqual(receipt_metadata["base_current_memory_ids"], [unrelated.id, first.id, second.id])
        self.assertCountEqual(receipt_metadata["included_history_memory_ids"], [first.id, second.id])
        self.assertCountEqual(receipt_metadata["included_current_memory_ids"], [first.id, second.id])
        self.assertEqual(receipt_metadata["omitted_history_memory_ids"], [unrelated.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [unrelated.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        for memory_id in (first.id, second.id):
            envelope = history_graph[memory_id]
            self.assertEqual(envelope["temporal_state"], "current")
            self.assertEqual(envelope["learned_at"], shared_timestamp)
            self.assertEqual(envelope["valid_from"], shared_timestamp)
            self.assertIsNone(envelope["valid_to"])
            self.assertIsNone(envelope["superseded_at"])
            self.assertEqual(envelope["superseded_by_ids"], [])
            self.assertEqual(envelope["current_resolution"], "abstained")
            self.assertEqual(envelope["temporal_resolution_kind"], "contradiction")
            self.assertEqual(envelope["temporal_resolution_reasons"], ["lexical-current-conflict"])
            self.assertEqual(envelope["current_conflict_reasons"], ["lexical-current-conflict"])
            self.assertEqual(current_graph[memory_id], snapshot["current_temporal_graph"][memory_id])
            self.assertEqual(abstained_graph[memory_id], snapshot["abstained_temporal_graph"][memory_id])
        self.assertTrue(temporal["abstention"]["applied"])
        self.assertEqual(temporal["abstention"]["reason"], "unresolved-current-conflict")
        self.assertCountEqual(temporal["abstention"]["abstained_ids"], [first.id, second.id])
        self.assertEqual(temporal["selection_strategy"], "abstained_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-abstained-current-filter")
        self.assertEqual(temporal["selected_ids"], abstained_ids)
        self.assertEqual(len(temporal["conflict_sets"]), 1)
        self.assertEqual(temporal["conflict_sets"][0]["resolution_outcome"], "abstained")
        self.assertCountEqual(temporal["conflict_sets"][0]["abstained_current_ids"], [first.id, second.id])

    def test_build_context_preserves_query_at_identity_snapshot_controls_for_dropped_empty_subset(self):
        stale = self.store.remember(
            "Status page owner is Alice.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-january",
            session_id="session://january",
        )
        current = self.store.remember(
            "Status page owner is Alice Chen.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            actor_uri="agent://codex/session-february",
            session_id="session://february",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE events SET created_at = ? WHERE memory_id = ? AND event_type = 'OBSERVED'",
            ("2024-02-01T00:00:00Z", current.id),
        )
        self.store.conn.commit()

        snapshot = self.store.query_at(
            "2024-02-20T00:00:00Z",
            scope="project",
            search_query="status page owner",
            current_resolution="dropped",
        )
        context = build_context(
            {
                "action_id": "act_temporal_context",
                "task": "dropped current empty temporal passthrough",
                "risk": "low",
                "merkle_root": "root_fixture",
                "policy_checks": [],
                "memories": [],
                "retrieval": {"temporal": snapshot},
            }
        )
        temporal = context["temporal"]

        self.assertEqual(temporal["query_at"], "2024-02-20T00:00:00Z")
        self.assertEqual(temporal["scope"], "project")
        self.assertEqual(temporal["search_query"], "status page owner")
        self.assertTrue(temporal["include_abstained_current"])
        self.assertEqual(temporal["current_resolution"], "dropped")
        self.assertFalse(temporal["learned_only"])
        self.assertFalse(temporal["unlearned_only"])
        self.assertFalse(temporal["superseded_only"])
        self.assertFalse(temporal["future_only"])
        self.assertEqual(temporal["history_memory_ids"], [])
        self.assertEqual(temporal["current_memory_ids"], [])
        self.assertEqual(temporal["resolved_current_memory_ids"], [])
        self.assertEqual(temporal["dropped_current_memory_ids"], [])
        self.assertEqual(temporal["abstained_current_memory_ids"], [])
        self.assertEqual(temporal["future_memory_ids"], [])
        self.assertEqual(temporal["superseded_memory_ids"], [])
        self.assertEqual(temporal["unlearned_memory_ids"], [])
        self.assertEqual(temporal["learned_memory_ids"], [])
        self.assertEqual(temporal["history_temporal_graph"], {})
        self.assertEqual(temporal["current_temporal_graph"], {})
        self.assertEqual(temporal["selected_temporal_graph"], {})
        self.assertEqual(temporal["abstained_temporal_graph"], {})
        self.assertEqual(temporal["dropped_current_temporal_graph"], {})
        self.assertEqual(temporal["selection_strategy"], "dropped_only_v1")
        self.assertEqual(temporal["selection_reason"], "explicit-dropped-current-filter")
        self.assertEqual(temporal["selected_ids"], [])
        receipt_metadata = temporal["current_history_receipt_metadata"]
        self.assertEqual(receipt_metadata["filter"], "current_resolution:dropped")
        self.assertCountEqual(receipt_metadata["base_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["base_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata["included_history_memory_ids"], [])
        self.assertEqual(receipt_metadata["included_current_memory_ids"], [])
        self.assertCountEqual(receipt_metadata["omitted_history_memory_ids"], [stale.id, current.id])
        self.assertEqual(receipt_metadata["omitted_current_memory_ids"], [current.id])
        self.assertEqual(receipt_metadata, snapshot["current_history_receipt_metadata"])
        current_ordering = temporal["current_ordering"]
        history_ordering = temporal["history_ordering"]
        self.assertEqual(current_ordering, snapshot["current_ordering"])
        self.assertEqual(history_ordering, snapshot["history_ordering"])
        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "current_conflict_resolution_rank")
        self.assertEqual(current_ordering["source"], "temporal_current_conflict_resolution")
        self.assertEqual(current_ordering["reason"], "explicit-dropped-current-filter")
        self.assertEqual(current_ordering["selected_current_rankings"], [])
        self.assertEqual(current_ordering["considered_current_rankings"], [])
        self.assertFalse(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
        self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
        self.assertEqual(history_ordering["reason"], "explicit-dropped-current-filter")
        self.assertEqual(history_ordering["selected_history_rankings"], [])
        self.assertEqual(history_ordering["considered_history_rankings"], [])

    def test_history_query_context_includes_superseded_memory_when_requested(self):
        parent = self.store.remember(
            "Status page owner used to be Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        child = self.store.remember(
            "Status page owner is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[parent.id],
        )
        context_path = self.tmp_path / "history-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="who was the previous status page owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [parent.id, child.id])

    def test_original_history_context_budget_keeps_earliest_and_latest_current_states(self):
        first = self.store.remember(
            "Deploy target is Heroku.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.3,
            authority="low",
        )
        second = self.store.remember(
            "Deploy target changed to Render.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
            authority="high",
        )
        third = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", third.id),
        )
        self.store.conn.commit()

        budget = approx_memory_tokens(first) + approx_memory_tokens(third)
        receipt = self.store.inject(
            "what was the original deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, third.id])

    def test_chronology_query_context_preserves_temporal_order(self):
        parent = self.store.remember(
            "Deployment approver was Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        child = self.store.remember(
            "Deployment approver is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[parent.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", parent.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", child.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "chronology-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="when did the deployment approver change then",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [parent.id, child.id])

    def test_build_context_multi_hop_budget_prefers_two_specific_hops_over_generic_overview(self):
        overview = self.store.remember(
            "Project Atlas owner Morgan rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "DeployWindow rollback policy is canary first for Project Atlas.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Project Atlas owner is Morgan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

        receipt = self.store.inject(
            "What is the Project Atlas owner DeployWindow rollback policy?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
            retrieval_config={"multi_hop": {"enabled": True, "max_subqueries": 4, "per_subquery_limit": 5}},
        )

        context = build_context(receipt)
        self.assertEqual([memory["id"] for memory in context["memories"]], [rollback.id, owner.id])
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")
        self.assertEqual(context["budget_dropped"][0]["multi_hop_fusion_rank"], 2)
        self.assertEqual(
            context["budget_dropped"][0]["multi_hop_outranked_reason"],
            "multi-hop-fusion-ranked-lower",
        )

    def test_build_context_auto_multi_hop_budget_prefers_two_specific_hops_over_generic_overview(self):
        overview = self.store.remember(
            "Project Atlas owner Morgan rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "DeployWindow rollback policy is canary first for Project Atlas.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Project Atlas owner is Morgan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

        receipt = self.store.inject(
            "What is the Project Atlas owner DeployWindow rollback policy?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
        self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
        self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fallback-compound-query")
        self.assertEqual([memory["id"] for memory in context["memories"]], [rollback.id, owner.id])
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")
        self.assertEqual(context["budget_dropped"][0]["multi_hop_fusion_rank"], 2)
        self.assertEqual(
            context["budget_dropped"][0]["multi_hop_outranked_reason"],
            "multi-hop-fusion-ranked-lower",
        )

    def test_build_context_auto_multi_hop_semantic_budget_prefers_specific_facts_over_generic_overview(self):
        overview = self.store.remember(
            "Project Atlas owner Morgan rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "DeployWindow rollback policy is canary first for Project Atlas.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Project Atlas owner is Morgan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

        receipt = self.store.inject(
            "Who is responsible for Project Atlas plus its DeployWindow rollback plan?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual(receipt["retrieval"]["search_mode"], "semantic")
        self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
        self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
        self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "semantic-compound-query")
        self.assertEqual([memory["id"] for memory in context["memories"]], [rollback.id, owner.id])
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")
        self.assertEqual(context["budget_dropped"][0]["multi_hop_fusion_rank"], 2)
        self.assertEqual(
            context["budget_dropped"][0]["multi_hop_outranked_reason"],
            "multi-hop-fusion-ranked-lower",
        )

    def test_build_context_auto_multi_hop_fts_identifier_query_recovers_specific_rollback_fact(self):
        overview = self.store.remember(
            "Project Atlas owner Morgan DeployWindow rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "DeployWindow rollback policy is canary first for Project Atlas.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Project Atlas owner is Morgan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(overview) + approx_memory_tokens(rollback)

        receipt = self.store.inject(
            "Project Atlas owner DeployWindow rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
        self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
        self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fts-identifier-compound-query")
        self.assertEqual([memory["id"] for memory in context["memories"]], [rollback.id, owner.id])
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")
        self.assertEqual(context["budget_dropped"][0]["multi_hop_fusion_rank"], 3)

    def test_build_context_auto_multi_hop_fts_entity_intent_query_recovers_specific_rollback_fact(self):
        overview = self.store.remember(
            "Project Atlas owner rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for Project Atlas.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Project Atlas owner is Morgan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(overview) + approx_memory_tokens(rollback)

        receipt = self.store.inject(
            "Project Atlas owner rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
        self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
        self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fts-entity-intent-compound-query")
        self.assertEqual([memory["id"] for memory in context["memories"]], [rollback.id, owner.id])
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")
        self.assertEqual(context["budget_dropped"][0]["multi_hop_fusion_rank"], 3)

    def test_build_context_auto_multi_hop_fts_deploy_target_query_recovers_target_and_rollback_facts(self):
        overview = self.store.remember(
            "Deploy target rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for deploy target Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        target = self.store.remember(
            "Deploy target is Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(target)

        receipt = self.store.inject(
            "deploy target rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertEqual(receipt["retrieval"]["query_lookup"]["selected_search_basis"], "direct-deploy-target-core")
        self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
        self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
        self.assertEqual(
            receipt["retrieval"]["multi_hop"]["activation_reason"],
            "fts-direct-deploy-target-compound-query",
        )
        self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, target.id})
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")

    def test_build_context_auto_multi_hop_fts_direct_subject_query_recovers_specific_rollback_fact(self):
        overview = self.store.remember(
            "Status page owner rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for status page.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Status page maintainer is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

        receipt = self.store.inject(
            "status page owner rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertEqual(receipt["retrieval"]["query_lookup"]["selected_search_basis"], "direct-subject")
        self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
        self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
        self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
        self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, owner.id})
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")

    def test_build_context_auto_multi_hop_owner_relation_status_page_queries_skip_generic_subject_only_decoys(self):
        query_cases = (
            ("role-relation-owner", "who owns the status page rollback policy notes"),
            ("role-relation-on-point", "who is on point for the status page rollback policy notes"),
            ("role-relation-responsible", "who is responsible for the status page rollback policy notes"),
            ("role-relation-in-charge", "who is in charge of the status page rollback policy notes"),
        )
        for expected_basis, query in query_cases:
            with self.subTest(query=query):
                store = MemoryStore(self.tmp_path / f"{expected_basis}-status-page-runner.sqlite")
                store.init()
                overview = store.remember(
                    "Status page owner rollback policy notes.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.99,
                )
                rollback = store.remember(
                    "Rollback policy is canary first for status page.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                owner = store.remember(
                    "Status page maintainer is Priya.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                decoy = store.remember(
                    "Status page dashboard is public.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.97,
                )
                budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

                receipt = store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=budget,
                )

                context = build_context(receipt)
                retrieval = receipt["retrieval"]
                self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], expected_basis)
                self.assertNotIn("status page", [subquery["query"] for subquery in retrieval["multi_hop"]["subqueries"]])
                self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, owner.id})
                self.assertEqual([item["memory_id"] for item in context["budget_dropped"]], [overview.id])
                self.assertNotIn(decoy.id, receipt["retrieved_memory_ids"])

    def test_build_context_auto_multi_hop_owner_relation_status_page_phrase_alias_queries_recover_owner_and_skip_generic_subject_only_decoys(self):
        query_cases = (
            ("role-relation-owner", "who owns the status page routing contact rollback policy notes"),
            ("role-relation-on-point", "who is on point for the status page routing contact rollback policy notes"),
            ("role-relation-responsible", "who is responsible for the status page routing contact rollback policy notes"),
            ("role-relation-in-charge", "who is in charge of the status page routing contact rollback policy notes"),
            ("role-relation-owner", "who owns the status page routing escalation contact rollback policy notes"),
            ("role-relation-on-point", "who is on point for the status page routing escalation contact rollback policy notes"),
            ("role-relation-responsible", "who is responsible for the status page routing escalation contact rollback policy notes"),
            ("role-relation-in-charge", "who is in charge of the status page routing escalation contact rollback policy notes"),
        )
        for index, (expected_basis, query) in enumerate(query_cases, start=1):
            with self.subTest(query=query):
                store = MemoryStore(self.tmp_path / f"{expected_basis}-status-page-phrase-alias-runner-{index}.sqlite")
                store.init()
                overview = store.remember(
                    "Status page owner routing contact rollback policy notes.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.99,
                )
                rollback = store.remember(
                    "Rollback policy is canary first for status page.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                owner = store.remember(
                    "Status page maintainer is Priya.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                decoy = store.remember(
                    "Status page dashboard is public.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.97,
                )
                budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

                receipt = store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=budget,
                )

                context = build_context(receipt)
                retrieval = receipt["retrieval"]
                self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], expected_basis)
                self.assertNotIn("status page routing contact owner", [subquery["query"] for subquery in retrieval["multi_hop"]["subqueries"]])
                self.assertNotIn(
                    "status page routing escalation contact owner",
                    [subquery["query"] for subquery in retrieval["multi_hop"]["subqueries"]],
                )
                self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, owner.id})
                self.assertEqual([item["memory_id"] for item in context["budget_dropped"]], [overview.id])
                self.assertNotIn(decoy.id, receipt["retrieved_memory_ids"])

    def test_build_context_auto_multi_hop_direct_subject_owner_phrase_alias_queries_drop_overview_before_specific_facts(self):
        query_cases = (
            (
                "status page owner routing contact rollback policy notes",
                "Status page owner routing contact rollback policy notes.",
            ),
            (
                "status page owner routing escalation contact rollback policy notes",
                "Status page owner routing escalation contact rollback policy notes.",
            ),
        )
        for index, (query, overview_text) in enumerate(query_cases, start=1):
            with self.subTest(query=query):
                store = MemoryStore(self.tmp_path / f"direct-owner-phrase-alias-runner-{index}.sqlite")
                store.init()
                overview = store.remember(
                    overview_text,
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.99,
                )
                rollback = store.remember(
                    "Rollback policy is canary first for status page.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                owner = store.remember(
                    "Status page maintainer is Priya.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                contact = store.remember(
                    "Status page escalation contact is Nia.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                decoy = store.remember(
                    "Status page dashboard is public.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.97,
                )
                budget = (
                    approx_memory_tokens(rollback)
                    + approx_memory_tokens(owner)
                    + approx_memory_tokens(contact)
                )

                receipt = store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=budget,
                )

                context = build_context(receipt)
                retrieval = receipt["retrieval"]
                self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "direct-subject")
                self.assertIn(
                    "status page escalation contact",
                    [subquery["query"] for subquery in retrieval["multi_hop"]["subqueries"]],
                )
                self.assertEqual(
                    {memory["id"] for memory in context["memories"]},
                    {rollback.id, owner.id, contact.id},
                )
                self.assertEqual([item["memory_id"] for item in context["budget_dropped"]], [overview.id])
                self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")
                self.assertNotIn(decoy.id, receipt["retrieved_memory_ids"])

    def test_build_context_auto_multi_hop_direct_subject_owner_phrase_alias_queries_reserve_owner_and_contact_under_two_fact_budget(self):
        query_cases = (
            (
                "status page owner routing contact rollback policy notes",
                "Status page owner routing contact rollback policy notes.",
            ),
            (
                "status page owner routing escalation contact rollback policy notes",
                "Status page owner routing escalation contact rollback policy notes.",
            ),
        )
        for index, (query, overview_text) in enumerate(query_cases, start=1):
            with self.subTest(query=query):
                store = MemoryStore(self.tmp_path / f"direct-owner-phrase-alias-two-fact-{index}.sqlite")
                store.init()
                overview = store.remember(
                    overview_text,
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.99,
                )
                rollback = store.remember(
                    "Rollback policy is canary first for status page.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                owner = store.remember(
                    "Status page maintainer is Priya.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                contact = store.remember(
                    "Status page escalation contact is Nia.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )

                receipt = store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=approx_memory_tokens(owner) + approx_memory_tokens(rollback),
                )

                context = build_context(receipt)
                packing = receipt["retrieval"]["packing"]
                self.assertEqual({memory["id"] for memory in context["memories"]}, {owner.id, contact.id})
                self.assertEqual(
                    [item["memory_id"] for item in context["budget_dropped"]],
                    [rollback.id, overview.id],
                )
                self.assertEqual(
                    packing["reservation"],
                    {
                        "strategy": "mixed_owner_contact_role_pair_v1",
                        "reason": "mixed-owner-contact-keep-role-facts-before-rollback",
                        "requested_ids": [owner.id, contact.id],
                        "applied_ids": [owner.id, contact.id],
                        "applied": True,
                        "blocked_reason": None,
                    },
                )

    def test_build_context_auto_multi_hop_fts_direct_subject_phrase_alias_query_recovers_specific_rollback_fact(self):
        overview = self.store.remember(
            "Status page routing contact rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for status page.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        contact = self.store.remember(
            "Status page escalation contact is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(contact)

        receipt = self.store.inject(
            "status page routing contact rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertEqual(receipt["retrieval"]["query_lookup"]["selected_search_basis"], "direct-subject")
        self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
        self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
        self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
        self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, contact.id})
        self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")

    def test_build_context_auto_multi_hop_direct_subject_phrase_alias_queries_skip_generic_subject_only_decoys(self):
        overview = self.store.remember(
            "Status page routing contact rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for status page.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        contact = self.store.remember(
            "Status page escalation contact is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        decoy = self.store.remember(
            "Status page dashboard is public.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.97,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(contact)

        receipt = self.store.inject(
            "status page routing contact rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        retrieval = receipt["retrieval"]
        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "direct-subject")
        self.assertNotIn("status page", [subquery["query"] for subquery in retrieval["multi_hop"]["subqueries"]])
        self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, contact.id})
        self.assertEqual([item["memory_id"] for item in context["budget_dropped"]], [overview.id])
        self.assertNotIn(decoy.id, receipt["retrieved_memory_ids"])

    def test_build_context_auto_multi_hop_direct_subject_phrase_alias_escalation_contact_queries_skip_generic_subject_only_decoys(self):
        overview = self.store.remember(
            "Status page routing escalation contact rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for status page.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        contact = self.store.remember(
            "Status page escalation contact is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        decoy = self.store.remember(
            "Status page dashboard is public.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.97,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(contact)

        receipt = self.store.inject(
            "status page routing escalation contact rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        retrieval = receipt["retrieval"]
        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "direct-subject")
        self.assertNotIn("status page", [subquery["query"] for subquery in retrieval["multi_hop"]["subqueries"]])
        self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, contact.id})
        self.assertEqual([item["memory_id"] for item in context["budget_dropped"]], [overview.id])
        self.assertNotIn(decoy.id, receipt["retrieved_memory_ids"])

    def test_build_context_auto_multi_hop_fts_deployment_approval_contact_query_recovers_specific_rollback_fact(self):
        overview = self.store.remember(
            "Deployment approval contact rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for deployment approvals.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        contact = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(contact)

        for query, expected_basis in (
            ("deployment approval contact rollback policy notes", "direct-subject"),
            ("deployment approvals contact rollback policy notes", "direct-subject-alias"),
        ):
            with self.subTest(query=query):
                receipt = self.store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=budget,
                )

                context = build_context(receipt)
                self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
                self.assertEqual(receipt["retrieval"]["query_lookup"]["selected_search_basis"], expected_basis)
                self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
                self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
                self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
                self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, contact.id})
                self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
                self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")

    def test_build_context_auto_multi_hop_fts_deployment_approval_contact_query_without_overview_uses_phrase_alias_parent(self):
        rollback = self.store.remember(
            "Rollback policy is canary first for deployment approvals.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        contact = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(contact)

        receipt = self.store.inject(
            "deployment approvals contact rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        retrieval = receipt["retrieval"]

        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "direct-subject-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertTrue(retrieval["multi_hop"]["enabled"])
        self.assertTrue(retrieval["multi_hop"]["auto_enabled"])
        self.assertEqual(retrieval["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
        self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, contact.id})
        self.assertEqual(context["budget_dropped"], [])

    def test_build_context_auto_multi_hop_fts_deployment_approval_owner_query_without_overview_uses_phrase_alias_parent(self):
        rollback = self.store.remember(
            "Rollback policy is canary first for deployment approvals.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

        receipt = self.store.inject(
            "deployment approvals owner rollback policy notes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        retrieval = receipt["retrieval"]

        self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "direct-subject-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertTrue(retrieval["multi_hop"]["enabled"])
        self.assertTrue(retrieval["multi_hop"]["auto_enabled"])
        self.assertEqual(retrieval["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
        self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, owner.id})
        self.assertEqual(context["budget_dropped"], [])

    def test_build_context_auto_multi_hop_fts_deployment_approval_owner_query_recovers_specific_rollback_fact(self):
        overview = self.store.remember(
            "Deployment approval owner rollback policy notes.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        rollback = self.store.remember(
            "Rollback policy is canary first for deployment approvals.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        owner = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

        for query, expected_basis in (
            ("deployment approval owner rollback policy notes", "direct-subject"),
            ("deployment approvals owner rollback policy notes", "direct-subject-alias"),
        ):
            with self.subTest(query=query):
                receipt = self.store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=budget,
                )

                context = build_context(receipt)
                self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
                self.assertEqual(receipt["retrieval"]["query_lookup"]["selected_search_basis"], expected_basis)
                self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
                self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
                self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
                self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, owner.id})
                self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
                self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")

    def test_build_context_auto_multi_hop_owner_relation_deployment_approval_queries_recover_specific_rollback_fact(self):
        query_cases = (
            ("role-relation-owner", "who owns deployment approvals rollback policy notes"),
            ("role-relation-on-point", "who is on point for deployment approvals rollback policy notes"),
            ("role-relation-responsible", "who is responsible for deployment approvals rollback policy notes"),
            ("role-relation-in-charge", "who is in charge of deployment approvals rollback policy notes"),
        )
        for expected_basis, query in query_cases:
            with self.subTest(query=query):
                store = MemoryStore(self.tmp_path / f"{expected_basis}-runner.sqlite")
                overview = store.remember(
                    "Deployment approvals owner rollback policy notes.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.99,
                )
                rollback = store.remember(
                    "Rollback policy is canary first for deployment approvals.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                owner = store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope="project",
                    source_kind="human",
                    trust=0.95,
                )
                budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

                receipt = store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=budget,
                )

                context = build_context(receipt)
                self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
                self.assertEqual(receipt["retrieval"]["query_lookup"]["selected_search_basis"], expected_basis)
                self.assertTrue(receipt["retrieval"]["multi_hop"]["enabled"])
                self.assertTrue(receipt["retrieval"]["multi_hop"]["auto_enabled"])
                self.assertEqual(receipt["retrieval"]["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
                self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, owner.id})
                self.assertEqual(context["budget_dropped"][0]["memory_id"], overview.id)
                self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "multi_hop_fusion_rank")

    def test_benchmark_chronology_context_puts_explicit_change_event_before_timeline_support(self):
        stale = self.store.remember(
            "On Monday, the deployment approver was Noor.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "On Tuesday, the deployment approver changed to Imani.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z", current.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "benchmark-chronology-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="When did the deployment approver change then?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [current.id, stale.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["temporal"]["selected_ids"], [stale.id, current.id])
        self.assertEqual(retrieval["temporal"]["injection_strategy"], "chronology_mutation_anchor_first_v1")
        self.assertEqual(retrieval["temporal"]["injection_preferred_ids"], [current.id, stale.id])
        self.assertEqual(retrieval["temporal"]["selected_mutation_anchor_id"], current.id)
        self.assertEqual(context["temporal"]["history_ordering"], retrieval["temporal"]["history_ordering"])
        self.assertEqual(
            retrieval["temporal"]["history_ordering"],
            {
                "applied": True,
                "pass_through": False,
                "basis": "chronological_timeline_selection_rank",
                "source": "temporal_chronological_timeline_selection",
                "reason": "chronology-query-terms",
                "selected_history_rankings": [
                    {"memory_id": stale.id, "rank": 1},
                    {"memory_id": current.id, "rank": 2},
                ],
                "considered_history_rankings": [
                    {"memory_id": stale.id, "rank": 1, "selected": True},
                    {"memory_id": current.id, "rank": 2, "selected": True},
                ],
            },
        )

    def test_multi_event_chronology_context_budget_keeps_explicit_change_events_before_support(self):
        support = self.store.remember(
            "On Monday, the deployment approver was Noor.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        earlier_change = self.store.remember(
            "On Tuesday, the deployment approver changed to Imani.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[support.id],
        )
        latest_change = self.store.remember(
            "On Wednesday, the deployment approver changed to Jules.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[earlier_change.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", support.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z", earlier_change.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-03T00:00:00Z", "2024-01-03T00:00:00Z", latest_change.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "multi-event-chronology-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="When did the deployment approver change then?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        budget = approx_memory_tokens(earlier_change) + approx_memory_tokens(latest_change)
        memory_receipt = self.store.inject(
            "When did the deployment approver change then?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )
        context = build_context(memory_receipt)

        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual([memory["id"] for memory in context["memories"]], [latest_change.id, earlier_change.id])
        retrieval = memory_receipt["retrieval"]
        self.assertEqual(
            retrieval["temporal"]["injection_preferred_ids"],
            [latest_change.id, earlier_change.id, support.id],
        )
        self.assertEqual(
            retrieval["temporal"]["selected_mutation_anchor_ids"],
            [latest_change.id, earlier_change.id],
        )
        self.assertEqual(retrieval["packing"]["injected_ids"], [latest_change.id, earlier_change.id])

    def test_history_shift_context_keeps_support_before_multiple_anchor_candidates(self):
        opening = self.store.remember(
            "The infra channel handled the opening ping.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        support = self.store.remember(
            "Avery covered the overnight rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        later = self.store.remember(
            "Blair took the next rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        notes_anchor = self.store.remember(
            "Status page shift notes live in docs/status.md.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        handoff_anchor = self.store.remember(
            "The status page changed after the shift handoff.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "history-multi-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who handled the status page before the shift?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [support.id, notes_anchor.id, handoff_anchor.id],
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selected_ids"],
            [support.id, notes_anchor.id, handoff_anchor.id],
        )

    def test_default_query_context_keeps_only_resolved_current_conflict(self):
        first = self.store.remember(
            "Incident owner is Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "conflict-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="incident owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])

    def test_default_query_context_abstains_on_unresolved_cross_provenance_current_conflict(self):
        first = self.store.remember(
            "Incident owner is Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            trust=0.95,
            authority="medium",
            status="active",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "conflict-abstained-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="who is the incident owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(context["memories"], [])
        self.assertTrue(receipt["memory_receipt"]["retrieval"]["temporal"]["abstention"]["applied"])

    def test_question_lookup_context_prefers_later_same_provenance_restatement(self):
        first = self.store.remember(
            "Incident owner is Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "question-lookup-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="who is the incident owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["query_lookup_basis"], "question-wrapper")

    def test_relation_question_context_prefers_later_same_provenance_restatement(self):
        first = self.store.remember(
            "Deploy service uses staging",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy service uses production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "relation-question-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="which env does the deploy service use",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "deploy service uses")
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["query_lookup_relation"], "uses")

    def test_relation_question_context_prefers_later_same_provenance_short_value_restatement(self):
        first = self.store.remember(
            "Deploy service uses DB",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy service uses UI",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "relation-question-short-value-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what does deploy service use",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["query_lookup_basis"], "role-relation-uses")
        self.assertEqual(conflict["query_lookup_relation"], "uses")
        self.assertEqual(conflict["value_by_id"][first.id], "db")
        self.assertEqual(conflict["value_by_id"][second.id], "ui")

    def test_inverse_relation_question_context_prefers_later_same_provenance_restatement(self):
        first = self.store.remember(
            "Deploy service uses staging",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy service uses production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "inverse-relation-question-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what is used by the deploy service",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "deploy service uses")
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["query_lookup_basis"], "inverse-relation-uses-by")
        self.assertEqual(conflict["query_lookup_relation"], "uses")

    def test_required_by_question_context_prefers_later_same_provenance_restatement(self):
        first = self.store.remember(
            "Deploy service requires staging secret",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy service requires production secret",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "required-by-question-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what is required by the deploy service",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "deploy service requires")
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["query_lookup_basis"], "inverse-relation-requires-by")
        self.assertEqual(conflict["query_lookup_relation"], "requires")

    def test_short_subject_required_by_question_context_prefers_later_same_provenance_restatement(self):
        first = self.store.remember(
            "UI requires auth token",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "UI requires access token",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "short-subject-required-by-question-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what is required by ui",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "ui requires")
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["search_terms"],
            ["ui", "requires"],
        )
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["query_lookup_key"], "ui")
        self.assertEqual(conflict["query_lookup_basis"], "inverse-relation-requires-by")
        self.assertEqual(conflict["query_lookup_relation"], "requires")
        self.assertEqual(conflict["value_by_id"][first.id], "auth token")
        self.assertEqual(conflict["value_by_id"][second.id], "access token")

    def test_short_subject_passive_history_and_current_contexts_keep_temporal_relation_receipts(self):
        cases = [
            (
                "used-by-history",
                "DB uses replica slot",
                "DB uses failover slot",
                "what was used by db before",
                "inverse-relation-uses-by",
                "db uses",
                "history-subject-core",
                "history",
            ),
            (
                "required-by-history",
                "UI requires auth token",
                "UI requires access token",
                "what was required by ui before",
                "inverse-relation-requires-by",
                "ui requires",
                "history-subject-core",
                "history",
            ),
            (
                "used-by-current",
                "DB uses replica slot",
                "DB uses failover slot",
                "what is currently used by db",
                "inverse-relation-uses-by",
                "db uses",
                "current-subject-core",
                "current",
            ),
            (
                "required-by-current",
                "UI requires auth token",
                "UI requires access token",
                "what is currently required by ui",
                "inverse-relation-requires-by",
                "ui requires",
                "current-subject-core",
                "current",
            ),
        ]

        for label, first_text, second_text, task, expected_basis, expected_query, expected_search_basis, mode in cases:
            with self.subTest(label=label):
                scope = f"runner-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-temporal-passive-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], expected_search_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], expected_query)
                if mode == "history":
                    self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id])
                    self.assertEqual(retrieval["query_lookup"]["history"]["matched_terms"], ["before"])
                    self.assertEqual(retrieval["query_lookup"]["history"]["core_terms"], expected_query.split())
                    self.assertEqual(retrieval["temporal"]["selection_reason"], "history-query-terms")
                    self.assertEqual(retrieval["temporal"]["selected_ids"], [first.id, second.id])
                    self.assertEqual(retrieval["temporal"]["selected_superseded_ids"], [first.id])
                    self.assertEqual(retrieval["temporal"]["selected_current_ids"], [second.id])
                else:
                    self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
                    self.assertEqual(retrieval["query_lookup"]["current"]["matched_terms"], ["currently"])
                    self.assertEqual(retrieval["query_lookup"]["current"]["core_terms"], expected_query.split())
                    self.assertEqual(retrieval["temporal"]["selection_reason"], "current-query-terms")
                    self.assertEqual(retrieval["temporal"]["selected_ids"], [second.id])
                    self.assertEqual(retrieval["temporal"]["selected_current_ids"], [second.id])

    def test_short_subject_passive_update_history_contexts_keep_temporal_relation_receipts(self):
        cases = [
            (
                "used-update-history",
                "DB uses replica slot",
                "DB uses failover slot",
                "what did db use change from",
                "role-relation-uses",
                "db uses",
                "db",
            ),
            (
                "required-update-history",
                "UI requires auth token",
                "UI requires access token",
                "what did ui require change from",
                "role-relation-requires",
                "ui requires",
                "ui",
            ),
        ]

        for label, first_text, second_text, task, expected_basis, expected_query, expected_lookup_key in cases:
            with self.subTest(label=label):
                scope = f"runner-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-temporal-passive-update-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                conflict = next(
                    item for item in retrieval["temporal"]["conflict_sets"] if item["reason"] == "subject-lookup-restatement"
                )

                self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id])
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["lookup_key"], expected_lookup_key)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], expected_query)
                self.assertEqual(retrieval["query_lookup"]["update"]["matched_terms"], ["change"])
                self.assertEqual(retrieval["query_lookup"]["update"]["direction"], "history")
                self.assertEqual(retrieval["query_lookup"]["update"]["direction_terms"], ["from"])
                self.assertEqual(retrieval["query_lookup"]["update"]["core_terms"], expected_query.split())
                self.assertEqual(retrieval["temporal"]["selection_reason"], "update-history-query-terms")
                self.assertEqual(retrieval["temporal"]["selected_ids"], [first.id, second.id])
                self.assertEqual(retrieval["temporal"]["selected_superseded_ids"], [first.id])
                self.assertEqual(retrieval["temporal"]["selected_current_ids"], [second.id])
                self.assertEqual(conflict["chosen_current_id"], second.id)
                self.assertEqual(conflict["query_lookup_basis"], expected_basis)
                self.assertEqual(conflict["query_lookup_key"], expected_lookup_key)

    def test_passive_chronology_context_backfills_generic_change_anchor_support(self):
        cases = [
            (
                "used-by-chronology-support",
                "DB uses replica slot",
                "DB uses failover slot",
                "DB usage changed after failover drill",
                "when did what is used by db change then",
                "inverse-relation-uses-by",
                "db uses",
            ),
            (
                "required-by-chronology-support",
                "UI requires auth token",
                "UI requires access token",
                "UI requirements changed after auth hardening",
                "when did what is required by ui change then",
                "inverse-relation-requires-by",
                "ui requires",
            ),
        ]

        for label, first_text, second_text, support_text, task, expected_basis, expected_query in cases:
            with self.subTest(label=label):
                scope = f"runner-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                support = self.store.remember(
                    support_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    trust=0.99,
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", support.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-chronology-support-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                temporal = retrieval["temporal"]

                self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id, support.id])
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "chronology-subject-core")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], expected_query)
                self.assertEqual(retrieval["chronology_support"]["selected_candidate_ids"], [support.id])
                self.assertEqual(retrieval["query_lookup"]["chronology"]["support_candidate_ids"], [support.id])
                self.assertEqual(temporal["selection_reason"], "chronology-query-terms")
                self.assertEqual(temporal["selected_ids"], [first.id, second.id, support.id])
                self.assertEqual(temporal["selected_superseded_ids"], [first.id])
                self.assertEqual(temporal["selected_current_ids"], [second.id, support.id])
                self.assertEqual(temporal["injection_strategy"], "chronology_relation_current_anchor_first_v1")
                self.assertEqual(temporal["selected_relation_current_id"], second.id)
                self.assertEqual(temporal["selected_relation_support_ids"], [support.id])
                self.assertEqual(temporal["selected_current_support_ids"], [support.id])

    def test_passive_history_context_backfills_generic_change_anchor_support(self):
        cases = [
            (
                "used-by-history-support",
                "DB uses replica slot",
                "DB uses failover slot",
                "DB usage changed after failover drill",
                "what was used by db before",
                "inverse-relation-uses-by",
                "db uses",
            ),
            (
                "required-by-history-support",
                "UI requires auth token",
                "UI requires access token",
                "UI requirements changed after auth hardening",
                "what was required by ui before",
                "inverse-relation-requires-by",
                "ui requires",
            ),
        ]

        for label, first_text, second_text, support_text, task, expected_basis, expected_query in cases:
            with self.subTest(label=label):
                scope = f"runner-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                support = self.store.remember(
                    support_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    trust=0.99,
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", support.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-history-support-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                temporal = retrieval["temporal"]

                self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id, support.id])
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], expected_query)
                self.assertEqual(retrieval["history_support"]["selected_candidate_ids"], [support.id])
                self.assertEqual(retrieval["query_lookup"]["history"]["support_candidate_ids"], [support.id])
                self.assertEqual(temporal["selection_reason"], "history-query-terms")
                self.assertEqual(temporal["selected_ids"], [first.id, second.id, support.id])
                self.assertEqual(temporal["selected_superseded_ids"], [first.id])
                self.assertEqual(temporal["selected_current_ids"], [second.id, support.id])
                self.assertEqual(temporal["injection_strategy"], "history_relation_current_anchor_first_v1")
                self.assertEqual(temporal["selected_relation_current_id"], second.id)
                self.assertEqual(temporal["selected_relation_support_ids"], [support.id])
                self.assertEqual(temporal["selected_current_support_ids"], [support.id])

    def test_passive_update_history_context_backfills_generic_change_anchor_support(self):
        cases = [
            (
                "used-update-history-support",
                "DB uses replica slot",
                "DB uses failover slot",
                "DB usage changed after failover drill",
                "what did db use change from",
                "role-relation-uses",
                "db uses",
            ),
            (
                "required-update-history-support",
                "UI requires auth token",
                "UI requires access token",
                "UI requirements changed after auth hardening",
                "what did ui require change from",
                "role-relation-requires",
                "ui requires",
            ),
        ]

        for label, first_text, second_text, support_text, task, expected_basis, expected_query in cases:
            with self.subTest(label=label):
                scope = f"runner-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                support = self.store.remember(
                    support_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    trust=0.99,
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", support.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-update-history-support-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                temporal = retrieval["temporal"]

                self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id, support.id])
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], expected_query)
                self.assertEqual(retrieval["update_history_support"]["selected_candidate_ids"], [support.id])
                self.assertEqual(retrieval["query_lookup"]["update"]["support_candidate_ids"], [support.id])
                self.assertEqual(temporal["selection_reason"], "update-history-query-terms")
                self.assertEqual(temporal["selected_ids"], [first.id, second.id, support.id])
                self.assertEqual(temporal["selected_superseded_ids"], [first.id])
                self.assertEqual(temporal["selected_current_ids"], [second.id, support.id])
                self.assertEqual(temporal["injection_strategy"], "update_history_relation_current_anchor_first_v1")
                self.assertEqual(temporal["selected_relation_current_id"], second.id)
                self.assertEqual(temporal["selected_relation_support_ids"], [support.id])
                self.assertEqual(temporal["selected_current_support_ids"], [support.id])

    def test_passive_update_current_context_backfills_generic_change_anchor_support(self):
        cases = [
            (
                "used-update-current-support",
                "DB uses failover slot",
                "DB usage changed after failover drill",
                "what did db use change to",
                "role-relation-uses",
                "db uses",
            ),
            (
                "required-update-current-support",
                "UI requires access token",
                "UI requirements changed after auth hardening",
                "what did ui require change to",
                "role-relation-requires",
                "ui requires",
            ),
        ]

        for label, current_text, support_text, task, expected_basis, expected_query in cases:
            with self.subTest(label=label):
                scope = f"runner-{label}"
                current = self.store.remember(
                    current_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                support = self.store.remember(
                    support_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    trust=0.99,
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", support.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-update-current-support-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                temporal = retrieval["temporal"]

                self.assertEqual([memory["id"] for memory in context["memories"]], [current.id, support.id])
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-subject-core")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], expected_query)
                self.assertEqual(retrieval["update_current_support"]["selected_candidate_ids"], [support.id])
                self.assertEqual(retrieval["query_lookup"]["update"]["support_candidate_ids"], [support.id])
                self.assertEqual(temporal["selection_reason"], "default-current-only")
                self.assertEqual(temporal["selected_ids"], [current.id, support.id])
                self.assertEqual(temporal["selected_current_ids"], [current.id, support.id])

    def test_passive_update_current_context_pair_budget_prefers_explicit_relation_plus_support_anchor(self):
        current = self.store.remember(
            "DB uses failover slot",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        support = self.store.remember(
            "DB usage changed after failover drill",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
        )
        decoy = self.store.remember(
            "DB uses, incident log tracking is documented",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )

        receipt = self.store.inject(
            "what did db use change to",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(current) + approx_memory_tokens(decoy),
            retrieval_config={"embedding": {"enabled": False}, "reranker": {"enabled": False}},
        )
        context = build_context(receipt)
        retrieval = receipt["retrieval"]
        temporal = retrieval["temporal"]

        self.assertEqual([memory["id"] for memory in context["memories"]], [current.id, support.id])
        self.assertEqual([memory["id"] for memory in receipt["memories"]], [current.id, support.id])
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "db uses")
        self.assertEqual(retrieval["update_current_support"]["selected_candidate_ids"], [support.id])
        self.assertEqual(retrieval["query_lookup"]["update"]["support_candidate_ids"], [support.id])
        self.assertEqual(temporal["selection_reason"], "default-current-only")
        self.assertEqual(temporal["injection_strategy"], "update_current_relation_support_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_relation_current_id"], current.id)
        self.assertEqual(temporal["selected_relation_support_ids"], [support.id])
        self.assertEqual(temporal["selected_current_support_ids"], [support.id])
        self.assertEqual(retrieval["packing"]["reservation"]["strategy"], "update_current_support_pair_v1")
        self.assertEqual(retrieval["packing"]["reservation"]["requested_ids"], [current.id, support.id])
        self.assertEqual(retrieval["packing"]["reservation"]["applied_ids"], [current.id, support.id])
        self.assertEqual(context["budget_dropped"][0]["memory_id"], decoy.id)
        self.assertFalse(context["budget_dropped"][0]["reserved_by_strategy"])
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion_reason"],
            "update-current-support-pair-reserved",
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion"],
            {
                "reason": "update-current-support-pair-reserved",
                "detail": "explicit-current-relation-plus-support-anchor-kept",
                "selected_current_id": current.id,
                "selected_support_ids": [support.id],
                "selected_pair_ids": [current.id, support.id],
            },
        )
        self.assertEqual(context["temporal"]["current_ordering"], retrieval["temporal"]["current_ordering"])

    def test_point_at_question_context_abstains_on_cross_provenance_tie(self):
        first = self.store.remember(
            "API gateway points to staging",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "API gateway points to production",
            memory_type="semantic",
            scope="project",
            source_kind="system",
            trust=0.95,
            authority="medium",
            status="active",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "point-at-conflict-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what does the api gateway point at",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(context["memories"], [])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "api gateway points")
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["query_lookup"]["lookup_basis"], "role-relation-points-at")
        self.assertTrue(receipt["memory_receipt"]["retrieval"]["temporal"]["abstention"]["applied"])

    def test_object_led_runs_on_question_context_filters_decoy(self):
        self.store.remember(
            "Canary worker runs Kubernetes conformance checks",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deploy service runs on Kubernetes",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "object-led-runs-on-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what runs on kubernetes",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "runs on kubernetes")
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["search_terms"],
            ["runs", "on", "kubernetes"],
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["lookup_basis"],
            "object-relation-runs-on",
        )
        self.assertEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [target.id])

    def test_direct_runs_on_query_context_preserves_short_target_terms_and_filters_decoy(self):
        self.store.remember(
            "Deploy service runs DB migration smoke tests",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deploy service runs on DB",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "direct-runs-on-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="deploy service runs on db",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "deploy service runs on db")
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["search_terms"],
            ["deploy", "service", "runs", "on", "db"],
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["lookup_basis"],
            "canonical-relation-runs-on",
        )
        self.assertEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [target.id])

    def test_direct_uses_query_context_preserves_short_target_terms_and_filters_decoy(self):
        self.store.remember(
            "Deploy service uses staging migration smoke tests",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deploy service uses DB",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "direct-uses-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="deploy service uses db",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "deploy service uses db")
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["search_terms"],
            ["deploy", "service", "uses", "db"],
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["lookup_basis"],
            "canonical-relation-uses",
        )
        self.assertEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [target.id])

    def test_generic_db_question_context_uses_semantic_alias_core_variant(self):
        self.store.remember(
            "Analytics warehouse is BigQuery",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Primary database is PostgreSQL",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "generic-db-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what db do we use",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "database")
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_terms"], ["database"])
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["selected_search_basis"],
            "semantic-alias-core",
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["semantic_aliases"]["matched_aliases"],
            [{"token": "db", "canonical": "database"}],
        )
        self.assertEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [target.id])

    def test_owner_paraphrase_context_uses_direct_owner_alias_search_variant(self):
        self.store.remember(
            "Status page notes mention Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Status page maintainer is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "owner-paraphrase-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="who owns the status page",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "role-relation-owner-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "status page maintainer")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertFalse(retrieval["embedding"]["enabled"])

    def test_owner_question_context_replaces_weak_fts_mention_with_hybrid_semantic_backfill(self):
        self.store.remember(
            "Status page owner docs mention Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Status page maintainer is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "owner-hybrid-backfill-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="who owns the status page",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_mode"], "fts")
        self.assertTrue(receipt["memory_receipt"]["retrieval"]["hybrid"]["applied"])
        self.assertTrue(receipt["memory_receipt"]["retrieval"]["embedding"]["auto_enabled"])

    def test_deploy_target_context_replaces_weak_fts_mention_with_destination_fact(self):
        self.store.remember(
            "Deploy target docs mention Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deploy destination is Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "deploy-target-hybrid-backfill-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "direct-deploy-target-core")
        self.assertTrue(retrieval["hybrid"]["applied"])
        self.assertTrue(retrieval["embedding"]["auto_enabled"])

    def test_current_deploy_target_query_context_ignores_current_modifier_during_hybrid_backfill(self):
        self.store.remember(
            "Deploy target docs mention Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deploy destination is Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-deploy-target-hybrid-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="current deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
        self.assertEqual(retrieval["query_lookup"]["current"]["matched_terms"], ["current"])
        self.assertTrue(retrieval["hybrid"]["applied"])
        self.assertEqual(retrieval["hybrid"]["effective_query"], "deploy target")
        self.assertEqual(retrieval["hybrid"]["semantic_probe"]["ignored_query_terms"], ["current"])
        self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [target.id])
        self.assertTrue(retrieval["embedding"]["auto_enabled"])

    def test_previous_deploy_target_query_context_ignores_history_modifier_during_hybrid_backfill(self):
        decoy = self.store.remember(
            "Deploy target docs mention Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        stale = self.store.remember(
            "Deploy destination is Staging",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        context_path = self.tmp_path / "previous-deploy-target-hybrid-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what was the previous deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
        self.assertEqual(retrieval["query_lookup"]["history"]["matched_terms"], ["previous"])
        self.assertTrue(retrieval["hybrid"]["applied"])
        self.assertEqual(retrieval["hybrid"]["effective_query"], "deploy target")
        self.assertEqual(retrieval["hybrid"]["semantic_probe"]["ignored_query_terms"], ["previous"])
        self.assertEqual(retrieval["hybrid"]["kept_lexical_candidate_ids"], [current.id])
        self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [stale.id])
        self.assertEqual(retrieval["hybrid"]["dropped_lexical_candidate_ids"], [decoy.id])
        self.assertEqual(
            retrieval["temporal"]["selection_reason"],
            "history-query-terms",
        )
        self.assertTrue(retrieval["embedding"]["auto_enabled"])

    def test_direct_owner_query_context_abstains_after_low_confidence_semantic_rescue(self):
        first = self.store.remember(
            "Status page notes mention Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Status page dashboard is public",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "direct-owner-abstention-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="status page owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(context["memories"], [])
        semantic_rescue = receipt["memory_receipt"]["retrieval"]["query_lookup"]["semantic_rescue"]
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_mode"], "none")
        self.assertTrue(semantic_rescue["abstention"]["applied"])
        self.assertCountEqual(semantic_rescue["abstention"]["dropped_candidate_ids"], [first.id, second.id])

    def test_current_owner_query_context_uses_current_subject_core_alias_search_variant(self):
        self.store.remember(
            "Status page notes mention Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Status page maintainer is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-owner-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="current status page owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "status page maintainer")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(
            retrieval["query_lookup"]["current"]["search_alias_variants"],
            [{"canonical": "owner", "search_term": "maintainer", "query": "status page maintainer"}],
        )

    def test_original_owner_query_context_uses_earliest_history_alias_search_variant(self):
        first = self.store.remember(
            "Status page maintainer is Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Status page maintainer is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[first.id],
        )
        third = self.store.remember(
            "Status page maintainer is Morgan",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[second.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", third.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "original-owner-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="original status page owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id, third.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "status page maintainer")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(
            retrieval["query_lookup"]["history"]["search_alias_variants"],
            [{"canonical": "owner", "search_term": "maintainer", "query": "status page maintainer"}],
        )
        self.assertEqual(retrieval["temporal"]["selection_reason"], "earliest-history-query-terms")

    def test_direct_requires_query_context_preserves_short_target_terms_and_filters_decoy(self):
        self.store.remember(
            "Deploy job requires release review checklist",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deploy job requires UI",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "direct-requires-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="deploy job requires ui",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(receipt["memory_receipt"]["retrieval"]["search_query"], "deploy job requires ui")
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["search_terms"],
            ["deploy", "job", "requires", "ui"],
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["lookup_basis"],
            "canonical-relation-requires",
        )
        self.assertEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [target.id])

    def test_default_subject_lookup_context_prefers_later_restatement(self):
        first = self.store.remember(
            "Incident owner is Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Incident owner is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "subject-lookup-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="incident owner",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)

    def test_on_point_question_context_prefers_later_same_provenance_restatement(self):
        first = self.store.remember(
            "Status page owner is Avery",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Status page owner is Blair",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "on-point-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who's on point for the status page now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["search_query"], "status page owner")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-on-point")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        conflict = next(
            item
            for item in retrieval["temporal"]["conflict_sets"]
            if item["reason"] == "subject-lookup-restatement"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)
        self.assertEqual(conflict["query_lookup_basis"], "role-relation-on-point")

    def test_responsible_question_context_uses_owner_relation_planning_with_maintainer_paraphrase(self):
        self.store.remember(
            "Status page notes mention Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Status page maintainer is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "responsible-owner-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who's responsible for the status page now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["search_query"], "status page maintainer")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-responsible")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "status page maintainer")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(retrieval["query_lookup"]["current"]["core_terms"], ["status", "page", "owner"])
        self.assertEqual(
            retrieval["query_lookup"]["current"]["search_alias_variants"],
            [{"canonical": "owner", "search_term": "maintainer", "query": "status page maintainer"}],
        )
        self.assertEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [target.id])

    def test_previous_responsible_question_context_uses_history_owner_alias_search_variant(self):
        stale = self.store.remember(
            "Status page maintainer is Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page maintainer is Priya",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        context_path = self.tmp_path / "previous-responsible-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="who was the previous person responsible for the status page",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-responsible")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "status page maintainer")

    def test_previously_in_charge_question_context_uses_phrase_alias_history_variant(self):
        stale = self.store.remember(
            "Earlier escalation contact was Jules.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Escalation contact changed to Rowan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Routing summary needs a weekly cleanup.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "previously-in-charge-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who was previously in charge of routing?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-in-charge")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "escalation contact")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(retrieval["temporal"]["selection_reason"], "history-query-terms")

    def test_previously_in_charge_history_context_prefers_explicit_current_before_generic_anchor(self):
        stale = self.store.remember(
            "Earlier escalation contact was Jules.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Escalation contact changed to Rowan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Escalation contact changed after the weekly review.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        context_path = self.tmp_path / "previously-in-charge-current-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who was previously in charge of routing?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        temporal = receipt["memory_receipt"]["retrieval"]["temporal"]
        self.assertEqual(temporal["injection_strategy"], "history_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_update_current_id"], current.id)
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])

    def test_update_history_responsible_question_context_uses_owner_alias_search_variant(self):
        stale = self.store.remember(
            "Status page maintainer is Alex",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Status page maintainer changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "update-history-responsible-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the person responsible for the status page change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-responsible")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "status page maintainer")
        self.assertEqual(retrieval["temporal"]["selection_reason"], "update-history-query-terms")

    def test_current_routing_owner_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Routing checklist lives in /srv/runbook.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Escalation contact changed to Rowan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Routing summary needs a weekly cleanup.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-routing-owner-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who owns routing now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-owner")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "escalation contact")

    def test_current_routing_escalation_contact_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Routing checklist lives in /srv/runbook.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Escalation contact changed to Rowan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Routing summary needs a weekly cleanup.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-routing-escalation-contact-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who is the routing escalation contact now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "escalation contact")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_contact_for_routing_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Routing checklist lives in /srv/runbook.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Escalation contact changed to Rowan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Routing summary needs a weekly cleanup.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-contact-for-routing-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who is the contact for routing now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "escalation contact")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_deployment_approval_contact_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Deployment contact doc mentions Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-deployment-approval-contact-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who is the deployment approval contact now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_reordered_deployment_approval_contact_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Deployment contact doc mentions Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-reordered-deployment-approval-contact-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who is the approval contact for deployments now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_deployment_approver_for_deployments_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Deployment contact doc mentions Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-deployment-approver-for-deployments-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who is the approver for deployments now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_who_approves_deployments_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Deployment contact doc mentions Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-who-approves-deployments-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who approves deployments now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_singular_deployment_approval_question_context_uses_phrase_alias_search_variant(self):
        cases = [
            ("approves-singular", "Who approves deployment now?"),
            ("approver-for-singular", "Who is the approver for deployment now?"),
        ]

        for label, query in cases:
            with self.subTest(label=label):
                scope = f"runner-current-singular-deployment-approval-{label}"
                self.store.remember(
                    "Deployment contact doc mentions Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                target = self.store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                context_path = self.tmp_path / f"current-singular-deployment-approval-{label}.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=query,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(retrieval["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
                self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_deployment_sign_off_question_context_uses_phrase_alias_search_variant(self):
        cases = [
            ("signs-off-singular", "Who signs off on deployment now?"),
            ("signs-off-plural", "Who signs off on deployments now?"),
        ]

        for label, query in cases:
            with self.subTest(label=label):
                scope = f"runner-current-deployment-sign-off-{label}"
                self.store.remember(
                    "Deployment contact doc mentions Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                target = self.store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                context_path = self.tmp_path / f"current-deployment-sign-off-{label}.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=query,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(retrieval["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
                self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_deployment_signoff_responsible_question_context_uses_phrase_alias_search_variant(self):
        self.store.remember(
            "Deployment contact doc mentions Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        target = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-deployment-signoff-responsible-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who is responsible for deployment signoff now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-responsible")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_deployment_approval_role_question_context_uses_phrase_alias_search_variant(self):
        cases = [
            ("owner", "Who owns deployment approvals now?", "role-relation-owner"),
            ("responsible", "Who is responsible for deployment approvals now?", "role-relation-responsible"),
            ("in-charge", "Who is in charge of deployment approvals now?", "role-relation-in-charge"),
        ]

        for label, query, expected_lookup_basis in cases:
            with self.subTest(label=label):
                scope = f"deployment-approval-role-context-{label}"
                self.store.remember(
                    "Deployment contact doc mentions Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                target = self.store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                context_path = self.tmp_path / f"current-deployment-approval-role-{label}-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=query,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(retrieval["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_lookup_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
                self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])

    def test_current_deployment_approval_person_question_context_infers_owner_role_before_phrase_alias(self):
        stale = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        current = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Deployment approval owner notes mention the checklist.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-deployment-approval-person-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who handles deployment approvals now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertEqual(retrieval["query_lookup"]["current"]["role_inferred"], "owner")
        self.assertEqual(retrieval["query_lookup"]["current"]["role_inference_reason"], "who-wrapper-person-role")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(retrieval["temporal"]["selection_reason"], "current-query-terms")
        self.assertEqual(retrieval["temporal"]["selected_ids"], [current.id])

    def test_current_deployment_signoff_handles_question_context_infers_owner_role_before_phrase_alias(self):
        cases = (
            ("compact", "Who handles deployment signoff now?"),
            ("hyphenated", "Who handles deployment sign-off now?"),
        )

        for label, task in cases:
            with self.subTest(label=label):
                scope = f"deployment-signoff-handles-context-{label}"
                stale = self.store.remember(
                    "Deployment approver was Alex.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.remember(
                    "Deployment approver changed to Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    parents=[stale.id],
                )
                current = self.store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.remember(
                    "Deployment contact doc mentions Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                context_path = self.tmp_path / f"current-deployment-signoff-handles-{label}-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                self.assertEqual([memory["id"] for memory in context["memories"]], [current.id])
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(retrieval["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "current-term")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
                self.assertEqual(retrieval["query_lookup"]["current"]["role_inferred"], "owner")
                self.assertEqual(retrieval["query_lookup"]["current"]["role_inference_reason"], "who-wrapper-person-role")
                self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
                self.assertEqual(retrieval["temporal"]["selection_reason"], "current-query-terms")
                self.assertEqual(retrieval["temporal"]["selected_ids"], [current.id])

    def test_current_deployment_signoff_person_on_point_question_context_uses_relation_phrase_alias_route(self):
        cases = (
            ("compact", "Who is the person on point for deployment signoff now?"),
            ("hyphenated", "Who is the person on point for deployment sign-off now?"),
        )

        for label, task in cases:
            with self.subTest(label=label):
                scope = f"deployment-signoff-person-on-point-context-{label}"
                stale = self.store.remember(
                    "Deployment approver was Alex.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.remember(
                    "Deployment approver changed to Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    parents=[stale.id],
                )
                current = self.store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.remember(
                    "Deployment contact doc mentions Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                context_path = self.tmp_path / f"current-deployment-signoff-person-on-point-{label}-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                self.assertEqual([memory["id"] for memory in context["memories"]], [current.id])
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(retrieval["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-on-point")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
                self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
                self.assertEqual(retrieval["temporal"]["selection_reason"], "current-query-terms")
                self.assertEqual(retrieval["temporal"]["selected_ids"], [current.id])

    def test_current_deployment_signoff_on_point_question_context_uses_relation_phrase_alias_route(self):
        cases = (
            ("compact", "Who is on point for deployment signoff now?"),
            ("hyphenated", "Who is on point for deployment sign-off now?"),
        )

        for label, task in cases:
            with self.subTest(label=label):
                scope = f"deployment-signoff-on-point-context-{label}"
                stale = self.store.remember(
                    "Deployment approver was Alex.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.remember(
                    "Deployment approver changed to Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    parents=[stale.id],
                )
                current = self.store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.remember(
                    "Deployment contact doc mentions Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                context_path = self.tmp_path / f"current-deployment-signoff-on-point-{label}-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                self.assertEqual([memory["id"] for memory in context["memories"]], [current.id])
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(retrieval["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-on-point")
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core-phrase-alias")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
                self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
                self.assertEqual(retrieval["temporal"]["selection_reason"], "current-query-terms")
                self.assertEqual(retrieval["temporal"]["selected_ids"], [current.id])

    def test_build_context_no_overview_deployment_approval_owner_wrapper_compound_queries_use_phrase_alias_parent(self):
        query_cases = (
            ("role-relation-owner", "who owns deployment approvals rollback policy notes"),
            ("role-relation-on-point", "who is on point for deployment approvals rollback policy notes"),
            ("role-relation-responsible", "who is responsible for deployment approvals rollback policy notes"),
            ("role-relation-in-charge", "who is in charge of deployment approvals rollback policy notes"),
        )

        for index, (expected_basis, query) in enumerate(query_cases, start=1):
            with self.subTest(query=query):
                scope = f"deployment-approval-owner-wrapper-runner-no-overview-{index}"
                rollback = self.store.remember(
                    "Rollback policy is canary first for deployment approvals.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    trust=0.95,
                )
                owner = self.store.remember(
                    "Deployment approver is Priya.",
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                    trust=0.95,
                )
                budget = approx_memory_tokens(rollback) + approx_memory_tokens(owner)

                receipt = self.store.inject(
                    query,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_budget_tokens=budget,
                )

                context = build_context(receipt)
                retrieval = receipt["retrieval"]

                self.assertEqual(receipt["retrieval"]["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], f"{expected_basis}-phrase-alias")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
                self.assertTrue(retrieval["multi_hop"]["enabled"])
                self.assertTrue(retrieval["multi_hop"]["auto_enabled"])
                self.assertEqual(retrieval["multi_hop"]["activation_reason"], "fts-direct-subject-compound-query")
                self.assertEqual({memory["id"] for memory in context["memories"]}, {rollback.id, owner.id})
                self.assertEqual(context["budget_dropped"], [])

    def test_update_history_deployment_approval_owner_question_context_infers_owner_role_before_phrase_alias(self):
        stale = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        self.store.remember(
            "Deployment approval owner notes mention the checklist.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "update-history-deployment-approval-owner-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who did deployment approvals change from?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "question-wrapper")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertEqual(retrieval["query_lookup"]["update"]["role_inferred"], "owner")
        self.assertEqual(retrieval["query_lookup"]["update"]["role_inference_reason"], "who-wrapper-person-role")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(retrieval["temporal"]["selection_reason"], "update-history-query-terms")

    def test_update_history_context_prefers_explicit_current_before_generic_anchor(self):
        stale = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Deployment approver changed after CAB review.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        context_path = self.tmp_path / "update-history-current-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who did deployment approvals change from?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        temporal = receipt["memory_receipt"]["retrieval"]["temporal"]
        self.assertEqual(temporal["injection_strategy"], "update_history_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_update_current_id"], current.id)
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])

    def test_update_history_context_rrf_promotes_explicit_current_over_high_authority_generic_anchor(self):
        stale = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Deployment approver changed after CAB review.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )
        context_path = self.tmp_path / "update-history-current-anchor-rrf-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who did deployment approvals change from?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        retrieval = receipt["memory_receipt"]["retrieval"]
        temporal = retrieval["temporal"]
        self.assertTrue(temporal["fusion"]["applied"])
        self.assertEqual(temporal["fusion"]["signal"], "temporal_update_pair_rrf_score_v1")
        self.assertEqual(temporal["fusion"]["basis"], "update_pair")
        self.assertEqual(
            [candidate["memory_id"] for candidate in retrieval["candidates"]],
            [stale.id, current.id, generic_anchor.id],
        )
        candidate_by_id = {candidate["memory_id"]: candidate for candidate in retrieval["candidates"]}
        self.assertEqual(candidate_by_id[current.id]["temporal_fusion_rank"], 2)
        self.assertEqual(candidate_by_id[generic_anchor.id]["temporal_fusion_rank"], 3)
        self.assertEqual(
            candidate_by_id[current.id]["temporal_fusion_sources"],
            ["baseline", "temporal_selection", "temporal_injection", "temporal_update_pair"],
        )
        self.assertEqual(
            retrieval["baseline_ranking"]["temporal_fusion_signal"],
            "temporal_update_pair_rrf_score_v1",
        )

    def test_update_history_relation_context_prefers_plain_current_relation_before_generic_anchor(self):
        stale = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "API gateway points to production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
            parents=[stale.id],
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        context_path = self.tmp_path / "update-history-relation-current-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the api gateway point at change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-points-at")
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["injection_strategy"], "update_history_relation_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_relation_current_id"], current.id)
        self.assertEqual(temporal["selected_relation_support_ids"], [generic_anchor.id])
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])

    def test_update_history_relation_context_rrf_promotes_explicit_current_relation_over_high_authority_generic_anchor(self):
        stale = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "API gateway points to the production control plane in us-east-1.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
            authority="low",
            parents=[stale.id],
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )
        budget = approx_memory_tokens(stale) + approx_memory_tokens(current)

        receipt = self.store.inject(
            "what did the api gateway point at change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )
        context = build_context(receipt)
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["retrieval"]
        temporal = retrieval["temporal"]
        self.assertTrue(temporal["fusion"]["applied"])
        self.assertEqual(temporal["fusion"]["signal"], "temporal_update_relation_pair_rrf_score_v1")
        self.assertEqual(
            [candidate["memory_id"] for candidate in retrieval["candidates"]],
            [stale.id, current.id, generic_anchor.id],
        )
        self.assertEqual(
            retrieval["baseline_ranking"]["temporal_fusion_signal"],
            "temporal_update_relation_pair_rrf_score_v1",
        )
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["memory_id"], generic_anchor.id)

    def test_recent_history_deployment_approval_owner_question_context_infers_owner_role_before_phrase_alias(self):
        stale = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[stale.id],
        )
        self.store.remember(
            "Deployment approval owner notes mention the checklist.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "recent-history-deployment-approval-owner-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who previously handled deployment approvals?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "question-wrapper")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertEqual(retrieval["query_lookup"]["history"]["role_inferred"], "owner")
        self.assertEqual(retrieval["query_lookup"]["history"]["role_inference_reason"], "who-wrapper-person-role")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(retrieval["temporal"]["selection_reason"], "history-query-terms")

    def test_history_shift_question_context_uses_observation_support_before_anchor(self):
        support = self.store.remember(
            "Avery covered the first rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        later = self.store.remember(
            "Blair took the next rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        anchor = self.store.remember(
            "Status page shift notes live in docs/status.md.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "history-shift-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who handled the status page before the shift?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [support.id, anchor.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "semantic")
        self.assertTrue(retrieval["query_lookup"]["history"]["observation_support"]["applied"])
        self.assertEqual(
            retrieval["query_lookup"]["history"]["observation_support"]["selected_support_candidate_ids"],
            [support.id],
        )
        self.assertEqual(retrieval["temporal"]["selection_strategy"], "history_observation_support_v1")
        self.assertEqual(retrieval["temporal"]["selected_ids"], [support.id, anchor.id])

    def test_history_shift_context_prefers_person_rotation_support_over_generic_handled_observation(self):
        opening = self.store.remember(
            "The infra channel handled the opening ping.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        support = self.store.remember(
            "Avery covered the overnight rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        later = self.store.remember(
            "Blair took the next rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        anchor = self.store.remember(
            "Status page shift notes live in docs/status.md.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "history-shift-benchmark-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who handled the status page before the shift?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [support.id, anchor.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(
            retrieval["query_lookup"]["history"]["observation_support"]["selected_support_candidate_ids"],
            [support.id],
        )
        self.assertEqual(retrieval["temporal"]["selected_ids"], [support.id, anchor.id])
        self.assertEqual(context["temporal"]["history_ordering"], retrieval["temporal"]["history_ordering"])
        self.assertEqual(
            retrieval["temporal"]["history_ordering"],
            {
                "applied": True,
                "pass_through": False,
                "basis": "history_observation_support_selection_rank",
                "source": "temporal_history_observation_support_selection",
                "reason": "history-observation-support-query-terms",
                "selected_history_rankings": [
                    {"memory_id": support.id, "rank": 1},
                    {"memory_id": anchor.id, "rank": 2},
                ],
                "considered_history_rankings": [
                    {"memory_id": support.id, "rank": 1, "selected": True},
                    {"memory_id": anchor.id, "rank": 2, "selected": True},
                    {"memory_id": later.id, "rank": 3, "selected": False},
                    {"memory_id": opening.id, "rank": 4, "selected": False},
                ],
            },
        )

    def test_history_shift_context_trims_low_signal_extra_anchor_before_budget_pressure(self):
        opening = self.store.remember(
            "The infra channel handled the opening ping.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
        )
        support = self.store.remember(
            "Avery covered the overnight rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.75,
        )
        later = self.store.remember(
            "Blair took the next rotation.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        notes_anchor = self.store.remember(
            "Status page shift notes live in docs/status.md.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        handoff_anchor = self.store.remember(
            "The status page changed after the shift handoff.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.9,
        )
        extra_anchor = self.store.remember(
            "Status page shift handoff checklist lives in docs/handoff.md.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )

        receipt = self.store.inject(
            "Who handled the status page before the shift?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=(
                approx_memory_tokens(support)
                + approx_memory_tokens(notes_anchor)
                + approx_memory_tokens(handoff_anchor)
            ),
        )
        context = build_context(receipt)
        retrieval = receipt["retrieval"]

        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [support.id, notes_anchor.id, handoff_anchor.id],
        )
        self.assertEqual(context["budget_dropped"], [])
        self.assertEqual(
            retrieval["query_lookup"]["history"]["observation_support"]["selected_anchor_candidate_ids"],
            [notes_anchor.id, handoff_anchor.id],
        )
        self.assertEqual(
            retrieval["query_lookup"]["history"]["observation_support"]["excluded_anchor_candidate_ids"],
            [extra_anchor.id],
        )
        self.assertEqual(context["temporal"]["history_ordering"], retrieval["temporal"]["history_ordering"])
        self.assertIn(
            {"memory_id": extra_anchor.id, "rank": 4, "selected": False},
            retrieval["temporal"]["history_ordering"]["considered_history_rankings"],
        )
        self.assertEqual(
            retrieval["temporal"]["selection_exclusions"],
            [
                {
                    "memory_id": extra_anchor.id,
                    "reason": "history-observation-anchor-not-selected",
                    "detail": "earliest-and-strongest-observation-anchor-chain-selected",
                    "selection_strategy": "history_observation_support_v1",
                    "selected_anchor_candidate_ids": [notes_anchor.id, handoff_anchor.id],
                    "anchor_candidate_ids": [notes_anchor.id, handoff_anchor.id, extra_anchor.id],
                    "anchor_selection_strategy": "observation_anchor_earliest_plus_strongest_v1",
                }
            ],
        )
        self.assertCountEqual(
            receipt["retrieved_memory_ids"],
            [support.id, notes_anchor.id, handoff_anchor.id, opening.id],
        )
        self.assertNotIn(extra_anchor.id, receipt["retrieved_memory_ids"])
        self.assertEqual(
            retrieval["query_lookup"]["history"]["observation_support"]["ordered_support_candidate_ids"],
            [support.id, later.id, opening.id],
        )

    def test_before_update_routing_owner_question_context_uses_phrase_alias_history_variant(self):
        stale = self.store.remember(
            "Earlier escalation contact was Jules.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Escalation contact changed to Rowan.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Routing summary needs a weekly cleanup.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "before-update-routing-owner-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who owned routing before the update?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-owner")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "escalation contact")
        self.assertEqual(retrieval["temporal"]["selection_reason"], "history-query-terms")

    def test_chronology_deployment_approval_contact_question_context_uses_phrase_alias_search_variant(self):
        parent = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        child = self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            parents=[parent.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", parent.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", child.id),
        )
        self.store.conn.commit()
        self.store.remember(
            "Approval contact change note then rollout checklist.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "chronology-deployment-approval-contact-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="When did the deployment approval contact change then?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [child.id, parent.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["search_mode"], "fts")
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "chronology-subject-core-phrase-alias")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deployment approver")
        self.assertFalse(retrieval["query_lookup"]["semantic_rescue"]["applied"])
        self.assertEqual(retrieval["temporal"]["selection_reason"], "chronology-query-terms")
        self.assertEqual(retrieval["temporal"]["injection_strategy"], "chronology_mutation_anchor_first_v1")
        self.assertEqual(retrieval["temporal"]["injection_preferred_ids"], [child.id, parent.id])

    def test_temporal_wrapped_relation_update_history_context_stays_lexical_across_relation_families(self):
        cases = [
            (
                "points-at",
                "API gateway points to staging",
                "API gateway points to production",
                "what did the api gateway point at change from",
                "role-relation-points-at",
                "api gateway points",
            ),
            (
                "deploys-to",
                "Deploy service deploys to staging",
                "Deploy service deploys to production",
                "what did the deploy service deploy to change from",
                "role-relation-deploys-to",
                "deploy service deploys",
            ),
            (
                "runs-on",
                "Deploy service runs on Nomad",
                "Deploy service runs on Kubernetes",
                "what did the deploy service run on change from",
                "role-relation-runs-on",
                "deploy service runs",
            ),
            (
                "belongs-to",
                "Project Atlas belongs to platform",
                "Project Atlas belongs to infrastructure",
                "what did project atlas belong to change from",
                "role-relation-belongs-to",
                "project atlas belongs",
            ),
        ]

        for label, first_text, second_text, task, expected_basis, expected_query in cases:
            with self.subTest(label=label):
                scope = f"project-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-update-history-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(
                    [memory["id"] for memory in context["memories"]],
                    retrieval["temporal"]["selected_ids"],
                )
                self.assertEqual(retrieval["temporal"]["selected_ids"], [first.id, second.id])
                self.assertEqual(retrieval["temporal"]["selected_superseded_ids"], [first.id])
                self.assertEqual(retrieval["temporal"]["selected_current_ids"], [second.id])
                self.assertEqual(retrieval["search_mode"], "fts")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core")
                self.assertEqual(retrieval["query_lookup"]["selected_search_query"], expected_query)
                self.assertEqual(retrieval["temporal"]["selection_reason"], "update-history-query-terms")

    def test_temporal_wrapped_relation_chronology_context_marks_stale_current_chain(self):
        cases = [
            (
                "points-at",
                "API gateway points to staging",
                "API gateway points to production",
                "when did the api gateway point at change then",
                "role-relation-points-at",
            ),
            (
                "deploys-to",
                "Deploy service deploys to staging",
                "Deploy service deploys to production",
                "when did the deploy service deploy to change then",
                "role-relation-deploys-to",
            ),
            (
                "runs-on",
                "Deploy service runs on Nomad",
                "Deploy service runs on Kubernetes",
                "when did the deploy service run on change then",
                "role-relation-runs-on",
            ),
            (
                "belongs-to",
                "Project Atlas belongs to platform",
                "Project Atlas belongs to infrastructure",
                "when did project atlas belong to change then",
                "role-relation-belongs-to",
            ),
        ]

        for label, first_text, second_text, task, expected_basis in cases:
            with self.subTest(label=label):
                scope = f"chronology-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-chronology-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id])
                self.assertEqual(retrieval["temporal"]["selected_ids"], [first.id, second.id])
                self.assertEqual(retrieval["temporal"]["selected_superseded_ids"], [first.id])
                self.assertEqual(retrieval["temporal"]["selected_current_ids"], [second.id])
                self.assertEqual(retrieval["temporal"]["selection_reason"], "chronology-query-terms")
                self.assertEqual(retrieval["temporal"]["selection_order"], "chronological_asc")
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)

    def test_chronology_relation_context_prefers_plain_current_relation_before_generic_anchor(self):
        stale = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        current = self.store.remember(
            "API gateway points to production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
            parents=[stale.id],
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", current.id),
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", generic_anchor.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "chronology-relation-current-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="when did the api gateway point at change then",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "chronology-subject-core")
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["injection_strategy"], "chronology_relation_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_relation_current_id"], current.id)
        self.assertEqual(temporal["selected_relation_support_ids"], [generic_anchor.id])
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])
        self.assertEqual(context["temporal"]["history_ordering"], temporal["history_ordering"])
        self.assertEqual(
            temporal["history_ordering"],
            {
                "applied": True,
                "pass_through": False,
                "basis": "chronological_timeline_selection_rank",
                "source": "temporal_chronological_timeline_selection",
                "reason": "chronology-query-terms",
                "selected_history_rankings": [
                    {"memory_id": stale.id, "rank": 1},
                    {"memory_id": current.id, "rank": 2},
                    {"memory_id": generic_anchor.id, "rank": 3},
                ],
                "considered_history_rankings": [
                    {"memory_id": stale.id, "rank": 1, "selected": True},
                    {"memory_id": current.id, "rank": 2, "selected": True},
                    {"memory_id": generic_anchor.id, "rank": 3, "selected": True},
                ],
            },
        )

    def test_chronology_relation_context_budget_falls_back_to_stale_and_current_when_support_chain_exceeds_budget(self):
        stale = self.store.remember(
            "API gateway points to canary.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.3,
            authority="low",
        )
        middle = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
            authority="high",
            parents=[stale.id],
        )
        current = self.store.remember(
            "API gateway points to production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
            parents=[middle.id],
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", middle.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-04-01T00:00:00Z", "2024-04-01T00:00:00Z", generic_anchor.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject(
            "when did the api gateway point at change then",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(stale) + approx_memory_tokens(current),
        )

        context = build_context(receipt)
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        self.assertCountEqual(
            [item["memory_id"] for item in context["budget_dropped"]],
            [middle.id, generic_anchor.id],
        )
        retrieval = receipt["retrieval"]
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["injection_strategy"], "chronology_relation_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_relation_current_id"], current.id)
        self.assertEqual(temporal["selected_relation_support_ids"], [generic_anchor.id])
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])
        self.assertEqual(
            retrieval["packing"]["reservation"]["requested_ids"],
            [stale.id, current.id, generic_anchor.id],
        )
        self.assertEqual(
            retrieval["packing"]["reservation"]["fallback_requested_ids"],
            [stale.id, current.id],
        )
        self.assertTrue(retrieval["packing"]["reservation"]["fallback_applied"])

    def test_build_context_chronology_budget_records_reserved_support_chain_exclusion_reason(self):
        stale = self.store.remember(
            "API gateway points to canary.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.3,
            authority="low",
        )
        middle = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
            authority="high",
            parents=[stale.id],
        )
        current = self.store.remember(
            "API gateway points to production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
            parents=[middle.id],
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", stale.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", middle.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-04-01T00:00:00Z", "2024-04-01T00:00:00Z", generic_anchor.id),
        )
        self.store.conn.commit()
        budget = (
            approx_memory_tokens(stale)
            + approx_memory_tokens(current)
            + approx_memory_tokens(generic_anchor)
        )

        receipt = self.store.inject(
            "when did the api gateway point at change then",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        retrieval = receipt["retrieval"]
        self.assertEqual(retrieval["packing"]["reservation"]["strategy"], "chronology_relation_support_chain_v1")
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion_reason"],
            "chronology-support-chain-reserved",
        )
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion"],
            {
                "reason": "chronology-support-chain-reserved",
                "detail": "selected-stale-current-support-chain-kept",
                "selected_stale_id": stale.id,
                "selected_current_id": current.id,
                "selected_support_ids": [generic_anchor.id],
                "selected_chain_ids": [stale.id, current.id, generic_anchor.id],
            },
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion_reason"],
            "chronology-support-chain-reserved",
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion"]["selected_chain_ids"],
            [stale.id, current.id, generic_anchor.id],
        )

    def test_temporal_wrapped_relation_history_context_abstains_on_cross_provenance_conflict(self):
        cases = [
            (
                "points-at-update-history",
                "API gateway points to staging",
                "API gateway points to production",
                "what did the api gateway point at change from",
                "update-history-cross-provenance-conflict-abstained",
                "role-relation-points-at",
            ),
            (
                "deploys-to-update-history",
                "Deploy service deploys to staging",
                "Deploy service deploys to production",
                "what did the deploy service deploy to change from",
                "update-history-cross-provenance-conflict-abstained",
                "role-relation-deploys-to",
            ),
            (
                "runs-on-update-history",
                "Deploy service runs on Nomad",
                "Deploy service runs on Kubernetes",
                "what did the deploy service run on change from",
                "update-history-cross-provenance-conflict-abstained",
                "role-relation-runs-on",
            ),
            (
                "belongs-to-update-history",
                "Project Atlas belongs to platform",
                "Project Atlas belongs to infrastructure",
                "what did project atlas belong to change from",
                "update-history-cross-provenance-conflict-abstained",
                "role-relation-belongs-to",
            ),
            (
                "points-at-chronology",
                "API gateway points to staging",
                "API gateway points to production",
                "when did the api gateway point at change then",
                "chronology-cross-provenance-conflict-abstained",
                "role-relation-points-at",
            ),
            (
                "deploys-to-chronology",
                "Deploy service deploys to staging",
                "Deploy service deploys to production",
                "when did the deploy service deploy to change then",
                "chronology-cross-provenance-conflict-abstained",
                "role-relation-deploys-to",
            ),
            (
                "runs-on-chronology",
                "Deploy service runs on Nomad",
                "Deploy service runs on Kubernetes",
                "when did the deploy service run on change then",
                "chronology-cross-provenance-conflict-abstained",
                "role-relation-runs-on",
            ),
            (
                "belongs-to-chronology",
                "Project Atlas belongs to platform",
                "Project Atlas belongs to infrastructure",
                "when did project atlas belong to change then",
                "chronology-cross-provenance-conflict-abstained",
                "role-relation-belongs-to",
            ),
        ]

        for label, first_text, second_text, task, expected_reason, expected_basis in cases:
            with self.subTest(label=label):
                scope = f"runner-{label}"
                first = self.store.remember(
                    first_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="human",
                )
                second = self.store.remember(
                    second_text,
                    memory_type="semantic",
                    scope=scope,
                    source_kind="system",
                    trust=0.95,
                    authority="medium",
                    status="active",
                )
                first_timestamp = "2024-01-01T00:00:00Z" if "chronology" in label else "2024-02-01T00:00:00Z"
                second_timestamp = "2024-02-01T00:00:00Z"
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    (first_timestamp, first_timestamp, first.id),
                )
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
                    (second_timestamp, second_timestamp, second.id),
                )
                self.store.conn.commit()
                context_path = self.tmp_path / f"{label}-cross-provenance-context.json"

                receipt = run_with_memory(
                    self.store,
                    ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
                    task=task,
                    agent_id="codex",
                    risk="low",
                    scope=scope,
                    context_path=context_path,
                )

                self.assertEqual(receipt["exit_code"], 0)
                context = json.loads(context_path.read_text())
                retrieval = receipt["memory_receipt"]["retrieval"]
                self.assertEqual(context["memories"], [])
                self.assertEqual(retrieval["temporal"]["selection_strategy"], "history_conflict_abstained_v1")
                self.assertEqual(retrieval["temporal"]["selection_reason"], expected_reason)
                self.assertTrue(retrieval["temporal"]["abstention"]["applied"])
                self.assertEqual(retrieval["temporal"]["abstention"]["reason"], "unresolved-cross-provenance-history")
                self.assertCountEqual(retrieval["temporal"]["abstention"]["abstained_ids"], [first.id, second.id])
                self.assertEqual(retrieval["query_lookup"]["lookup_basis"], expected_basis)
                history_ordering = retrieval["temporal"]["history_ordering"]
                self.assertEqual(context["temporal"]["history_ordering"], history_ordering)
                self.assertTrue(history_ordering["applied"])
                self.assertFalse(history_ordering["pass_through"])
                self.assertEqual(history_ordering["basis"], "history_conflict_abstention_rank")
                self.assertEqual(history_ordering["source"], "temporal_history_conflict_abstention")
                self.assertEqual(history_ordering["reason"], expected_reason)
                self.assertEqual(history_ordering["selected_history_rankings"], [])
                self.assertCountEqual(
                    [item["memory_id"] for item in history_ordering["considered_history_rankings"]],
                    [first.id, second.id],
                )
                if "chronology" in label:
                    self.assertEqual(
                        history_ordering["considered_history_rankings"],
                        [
                            {"memory_id": first.id, "rank": 1, "selected": False},
                            {"memory_id": second.id, "rank": 2, "selected": False},
                        ],
                    )
                history_conflict = next(
                    item
                    for item in retrieval["temporal"]["conflict_sets"]
                    if item["reason"] == "subject-lookup-cross-provenance-conflict"
                )
                self.assertCountEqual(history_conflict["abstained_current_ids"], [first.id, second.id])

    def test_default_query_context_keeps_explicit_update_current_memory(self):
        first = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "explicit-update-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "explicit-update-candidate"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)

    def test_update_question_context_keeps_explicit_update_current_memory(self):
        first = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "update-question-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the deploy target change to",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id])
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["selected_search_basis"],
            "update-subject-core",
        )
        conflict = next(
            item
            for item in receipt["memory_receipt"]["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "explicit-update-candidate"
        )
        self.assertEqual(conflict["chosen_current_id"], second.id)

    def test_update_history_question_context_prefers_previous_state_but_keeps_current_visible(self):
        first = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "update-history-question-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the deploy target change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id])
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["selected_search_basis"],
            "update-history-subject-core",
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selection_reason"],
            "update-history-query-terms",
        )

    def test_build_context_update_history_budget_records_reserved_anchor_pair_exclusion_reason(self):
        first = self.store.remember(
            "Deploy target is Heroku.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.3,
            authority="low",
        )
        second = self.store.remember(
            "Deploy target changed to Render.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
            authority="high",
        )
        third = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", third.id),
        )
        self.store.conn.commit()
        budget = approx_memory_tokens(second) + approx_memory_tokens(third)

        receipt = self.store.inject(
            "what did the deploy target change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id, third.id])
        retrieval = receipt["retrieval"]
        self.assertEqual(retrieval["packing"]["reservation"]["strategy"], "update_history_anchor_pair_v1")
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion_reason"],
            "update-history-anchor-pair-reserved",
        )
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion"],
            {
                "reason": "update-history-anchor-pair-reserved",
                "detail": "selected-stale-current-anchor-pair-kept",
                "selected_stale_id": second.id,
                "selected_current_id": third.id,
                "selected_pair_ids": [second.id, third.id],
            },
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion_reason"],
            "update-history-anchor-pair-reserved",
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion"]["selected_pair_ids"],
            [second.id, third.id],
        )

    def test_recent_history_context_budget_falls_back_to_previous_and_latest_current_when_support_chain_exceeds_budget(self):
        first = self.store.remember(
            "Deploy target is Heroku.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="policy",
        )
        second = self.store.remember(
            "Deploy target changed to Render.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.2,
            authority="low",
            parents=[first.id],
        )
        current = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
            parents=[second.id],
        )
        generic_anchor = self.store.remember(
            "Deploy target changed after CAB review.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-04-01T00:00:00Z", "2024-04-01T00:00:00Z", generic_anchor.id),
        )
        self.store.conn.commit()

        receipt = self.store.inject(
            "what was the previous deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(second) + approx_memory_tokens(current),
        )
        context = build_context(receipt)
        retrieval = receipt["retrieval"]
        temporal = retrieval["temporal"]
        budget_dropped_ids = [item["memory_id"] for item in context["budget_dropped"]]

        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id, current.id])
        self.assertEqual(temporal["selection_strategy"], "historical_preferred_v1")
        self.assertEqual(temporal["selection_reason"], "history-query-terms")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])
        self.assertEqual(retrieval["packing"]["reservation"]["applied_ids"], [second.id, current.id])
        self.assertTrue(retrieval["packing"]["reservation"]["fallback_applied"])
        self.assertEqual(
            retrieval["packing"]["reservation"]["fallback_requested_ids"],
            [second.id, current.id],
        )
        self.assertCountEqual(budget_dropped_ids, [first.id, generic_anchor.id])
        self.assertNotIn(current.id, budget_dropped_ids)

    def test_update_history_destination_query_context_canonicalizes_alias_to_target(self):
        first = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "update-history-destination-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the deploy destination change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
        self.assertEqual(retrieval["query_lookup"]["update"]["raw_core_terms"], ["deploy", "destination"])
        self.assertEqual(
            retrieval["query_lookup"]["update"]["matched_aliases"],
            [{"token": "destination", "canonical": "target"}],
        )
        self.assertTrue(retrieval["query_lookup"]["update"]["alias_expanded"])

    def test_update_history_deploy_target_context_ignores_change_from_during_hybrid_backfill(self):
        decoy = self.store.remember(
            "Deploy target docs mention Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        stale = self.store.remember(
            "Deploy destination is Staging",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            parents=[stale.id],
        )
        context_path = self.tmp_path / "update-history-deploy-target-hybrid-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the deploy target change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
        self.assertEqual(retrieval["query_lookup"]["update"]["matched_terms"], ["change"])
        self.assertEqual(retrieval["query_lookup"]["update"]["direction_terms"], ["from"])
        self.assertTrue(retrieval["hybrid"]["applied"])
        self.assertEqual(retrieval["hybrid"]["effective_query"], "deploy target")
        self.assertEqual(retrieval["hybrid"]["semantic_probe"]["ignored_query_terms"], ["change", "from"])
        self.assertEqual(retrieval["hybrid"]["kept_lexical_candidate_ids"], [current.id])
        self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [stale.id])

    def test_update_history_deploy_destination_context_ignores_change_from_during_hybrid_backfill(self):
        decoy = self.store.remember(
            "Deploy target docs mention Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        stale = self.store.remember(
            "Deploy destination is Staging",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            parents=[stale.id],
        )
        context_path = self.tmp_path / "update-history-deploy-destination-hybrid-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the deploy destination change from",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-history-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
        self.assertEqual(retrieval["query_lookup"]["update"]["raw_core_terms"], ["deploy", "destination"])
        self.assertEqual(retrieval["query_lookup"]["update"]["core_terms"], ["deploy", "target"])
        self.assertTrue(retrieval["hybrid"]["applied"])
        self.assertEqual(retrieval["hybrid"]["effective_query"], "deploy target")
        self.assertEqual(retrieval["hybrid"]["semantic_probe"]["ignored_query_terms"], ["change", "from"])
        self.assertEqual(retrieval["hybrid"]["kept_lexical_candidate_ids"], [current.id])
        self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [stale.id])

    def test_update_current_deploy_target_context_ignores_switch_to_during_hybrid_backfill(self):
        decoy = self.store.remember(
            "Deploy target docs mention Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        target = self.store.remember(
            "Deploy destination is Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deploy target switched to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
        )
        context_path = self.tmp_path / "update-current-deploy-target-switch-hybrid-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the deploy target switch to",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
        self.assertEqual(retrieval["query_lookup"]["update"]["matched_terms"], ["switch"])
        self.assertEqual(retrieval["query_lookup"]["update"]["direction_terms"], ["to"])
        self.assertTrue(retrieval["hybrid"]["applied"])
        self.assertEqual(retrieval["hybrid"]["effective_query"], "deploy target")
        self.assertEqual(retrieval["hybrid"]["semantic_probe"]["ignored_query_terms"], ["switch", "to"])
        self.assertEqual(retrieval["hybrid"]["kept_lexical_candidate_ids"], [current.id])
        self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [target.id])
        self.assertEqual(retrieval["temporal"]["selected_ids"], [target.id, current.id])

    def test_update_current_deploy_destination_context_ignores_update_to_during_hybrid_backfill(self):
        decoy = self.store.remember(
            "Deploy target docs mention Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )
        target = self.store.remember(
            "Deploy destination is Production",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deploy target updated to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
        )
        context_path = self.tmp_path / "update-current-deploy-destination-update-hybrid-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the deploy destination update to",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-subject-core")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
        self.assertEqual(retrieval["query_lookup"]["update"]["matched_terms"], ["update"])
        self.assertEqual(retrieval["query_lookup"]["update"]["raw_core_terms"], ["deploy", "destination"])
        self.assertEqual(retrieval["query_lookup"]["update"]["core_terms"], ["deploy", "target"])
        self.assertEqual(
            retrieval["query_lookup"]["update"]["matched_aliases"],
            [{"token": "destination", "canonical": "target"}],
        )
        self.assertTrue(retrieval["hybrid"]["applied"])
        self.assertEqual(retrieval["hybrid"]["effective_query"], "deploy target")
        self.assertEqual(retrieval["hybrid"]["semantic_probe"]["ignored_query_terms"], ["update", "to"])
        self.assertEqual(retrieval["hybrid"]["kept_lexical_candidate_ids"], [current.id])
        self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [target.id])
        self.assertEqual(retrieval["temporal"]["selected_ids"], [target.id, current.id])

    def test_build_context_current_deploy_target_budget_prefers_semantic_backfill_state(self):
        current = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
        )
        target = self.store.remember(
            "Deploy destination is Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )

        receipt = self.store.inject(
            "what is the deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(current),
        )
        context = build_context(receipt)
        retrieval = receipt["retrieval"]

        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(retrieval["packing"]["injected_ids"], [target.id])
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["memory_id"], current.id)

    def test_build_context_current_deploy_target_budget_prefers_semantic_backfill_state_without_embedding_or_reranker(self):
        current = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
        )
        target = self.store.remember(
            "Deploy destination is Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )

        receipt = self.store.inject(
            "what is the deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(current),
            retrieval_config={"embedding": {"enabled": False}, "reranker": {"enabled": False}},
        )
        context = build_context(receipt)
        retrieval = receipt["retrieval"]

        self.assertEqual([memory["id"] for memory in context["memories"]], [target.id])
        self.assertEqual(retrieval["packing"]["injected_ids"], [target.id])
        self.assertFalse(retrieval["embedding"]["enabled"])
        self.assertFalse(retrieval["reranker"]["enabled"])
        self.assertTrue(retrieval["baseline_ranking"]["hybrid_semantic_signal_applied"])
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["memory_id"], current.id)
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["packing_rank_basis"], "hybrid_semantic_rank")
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["hybrid_semantic_rank"], 2)
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["hybrid_outranked_reason"],
            "hybrid-semantic-backfill-ranked-lower",
        )
        self.assertEqual(context["budget_dropped"][0]["memory_id"], current.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "hybrid_semantic_rank")
        self.assertEqual(context["budget_dropped"][0]["hybrid_semantic_rank"], 2)
        self.assertEqual(
            context["budget_dropped"][0]["hybrid_outranked_reason"],
            "hybrid-semantic-backfill-ranked-lower",
        )

    def test_build_context_update_current_deploy_target_family_pair_budget_keeps_canonical_hybrid_pair(self):
        scenarios = (
            (
                "what did the deploy target switch to",
                "Deploy target switched to Production.",
                ["switch"],
            ),
            (
                "what did the deploy destination update to",
                "Deploy target updated to Production.",
                ["update"],
            ),
        )
        for task, current_text, matched_terms in scenarios:
            with self.subTest(task=task):
                with tempfile.TemporaryDirectory() as tmpdir:
                    store = MemoryStore(Path(tmpdir) / "memory.sqlite")
                    store.init()
                    store.remember(
                        "Deploy target docs mention Production",
                        memory_type="semantic",
                        scope="project",
                        source_kind="human",
                        trust=0.95,
                    )
                    target = store.remember(
                        "Deploy destination is Production",
                        memory_type="semantic",
                        scope="project",
                        source_kind="human",
                        trust=0.7,
                    )
                    current = store.remember(
                        current_text,
                        memory_type="semantic",
                        scope="project",
                        source_kind="human",
                        trust=0.8,
                    )

                    receipt = store.inject(
                        task,
                        agent_id="codex",
                        risk="low",
                        scope="project",
                        context_budget_tokens=approx_memory_tokens(target) + approx_memory_tokens(current),
                        retrieval_config={"embedding": {"enabled": False}, "reranker": {"enabled": False}},
                    )
                    context = build_context(receipt)
                    retrieval = receipt["retrieval"]

                    self.assertEqual([memory["id"] for memory in context["memories"]], [target.id, current.id])
                    self.assertEqual(context["budget_dropped"], [])
                    self.assertEqual(retrieval["packing"]["injected_ids"], [target.id, current.id])
                    self.assertEqual(retrieval["packing"]["budget_dropped"], [])
                    self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-subject-core")
                    self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
                    self.assertEqual(retrieval["query_lookup"]["update"]["matched_terms"], matched_terms)
                    self.assertEqual(retrieval["query_lookup"]["update"]["direction_terms"], ["to"])
                    self.assertFalse(retrieval["embedding"]["enabled"])
                    self.assertFalse(retrieval["reranker"]["enabled"])
                    self.assertTrue(retrieval["baseline_ranking"]["hybrid_semantic_signal_applied"])
                    self.assertTrue(retrieval["hybrid"]["applied"])
                    self.assertEqual(retrieval["hybrid"]["kept_lexical_candidate_ids"], [current.id])
                    self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [target.id])
                    self.assertEqual(retrieval["temporal"]["selected_ids"], [target.id, current.id])

    def test_build_context_update_current_deploy_target_change_move_pair_budget_keeps_canonical_hybrid_pair(self):
        scenarios = (
            (
                "what did the deploy target change to",
                "Deploy target changed to Production.",
                ["change"],
            ),
            (
                "where did the deploy destination move to",
                "Deploy target moved to Production.",
                ["move"],
            ),
        )
        for task, current_text, matched_terms in scenarios:
            with self.subTest(task=task):
                with tempfile.TemporaryDirectory() as tmpdir:
                    store = MemoryStore(Path(tmpdir) / "memory.sqlite")
                    store.init()
                    store.remember(
                        "Deploy target docs mention Production",
                        memory_type="semantic",
                        scope="project",
                        source_kind="human",
                        trust=0.95,
                    )
                    target = store.remember(
                        "Deploy destination is Production",
                        memory_type="semantic",
                        scope="project",
                        source_kind="human",
                        trust=0.7,
                    )
                    current = store.remember(
                        current_text,
                        memory_type="semantic",
                        scope="project",
                        source_kind="human",
                        trust=0.8,
                    )

                    receipt = store.inject(
                        task,
                        agent_id="codex",
                        risk="low",
                        scope="project",
                        context_budget_tokens=approx_memory_tokens(target) + approx_memory_tokens(current),
                        retrieval_config={"embedding": {"enabled": False}, "reranker": {"enabled": False}},
                    )
                    context = build_context(receipt)
                    retrieval = receipt["retrieval"]

                    self.assertEqual([memory["id"] for memory in context["memories"]], [target.id, current.id])
                    self.assertEqual(context["budget_dropped"], [])
                    self.assertEqual(retrieval["packing"]["injected_ids"], [target.id, current.id])
                    self.assertEqual(retrieval["packing"]["budget_dropped"], [])
                    self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "update-subject-core")
                    self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "deploy target")
                    self.assertEqual(retrieval["query_lookup"]["update"]["matched_terms"], matched_terms)
                    self.assertEqual(retrieval["query_lookup"]["update"]["direction_terms"], ["to"])
                    self.assertFalse(retrieval["embedding"]["enabled"])
                    self.assertFalse(retrieval["reranker"]["enabled"])
                    self.assertTrue(retrieval["baseline_ranking"]["hybrid_semantic_signal_applied"])
                    self.assertTrue(retrieval["hybrid"]["applied"])
                    self.assertEqual(retrieval["hybrid"]["kept_lexical_candidate_ids"], [current.id])
                    self.assertEqual(retrieval["hybrid"]["introduced_candidate_ids"], [target.id])
                    self.assertEqual(retrieval["temporal"]["selected_ids"], [target.id, current.id])

    def test_build_context_preserves_provider_reranker_budget_drop_metadata(self):
        broad = self.store.remember(
            "Runner provider reranker budget marker broad alpha beta gamma delta",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        exact = self.store.remember(
            "Runner provider reranker budget marker",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.01,
        )
        self.store.promote(broad.id)
        self.store.promote(exact.id)
        provider_result = RerankerProviderResult(
            provider_id="cohere:rerank-v3.5",
            model_id="rerank-v3.5",
            reranker_id="rerank-v3.5",
            scores=[0.1, 0.9],
            latency_ms=8.25,
            network_call=True,
            score_hashes=["sha256:broad-score", "sha256:exact-score"],
        )
        provider_config = {
            "schema": "zerker.retrieval_providers.v1",
            "embedding": {
                "default": "local:pseudo",
                "providers": {
                    "local:pseudo": {
                        "enabled": True,
                        "network": False,
                        "model_id": "zmem-pseudo-embedding-v1",
                    }
                },
            },
            "reranker": {
                "default": "local:deterministic",
                "providers": {
                    "local:deterministic": {
                        "enabled": True,
                        "network": False,
                        "reranker_id": "zmem-deterministic-rerank-v1",
                    },
                    "cohere:rerank-v3.5": {
                        "enabled": True,
                        "network": True,
                        "reranker_id": "rerank-v3.5",
                        "api_key_env": "COHERE_API_KEY",
                    },
                },
            },
        }

        with mock.patch.dict("os.environ", {"COHERE_API_KEY": "cohere-test-secret"}):
            with mock.patch("zerker_memory.store.rerank_texts", return_value=provider_result):
                receipt = self.store.inject(
                    "runner provider reranker budget marker",
                    agent_id="codex",
                    risk="low",
                    scope="project",
                    context_budget_tokens=approx_memory_tokens(exact),
                    retrieval_config={
                        "reranker": {
                            "enabled": True,
                            "provider_id": "cohere:rerank-v3.5",
                            "reranker_id": "rerank-v3.5",
                        }
                    },
                    retrieval_provider_config=provider_config,
                    allow_network_providers=True,
                )

        context = build_context(receipt)
        current_ordering = context["temporal"]["current_ordering"]

        self.assertEqual([memory["id"] for memory in context["memories"]], [exact.id])
        self.assertTrue(current_ordering["applied"])
        self.assertTrue(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "reranker_rank")
        self.assertEqual(current_ordering["source"], "reranker")
        self.assertEqual(current_ordering["reason"], "current-only-reranker-pass-through")
        self.assertEqual(
            current_ordering["selected_current_rankings"],
            [
                {"memory_id": broad.id, "rank": 1},
                {"memory_id": exact.id, "rank": 2},
            ],
        )
        self.assertEqual(context["budget_dropped"][0]["memory_id"], broad.id)
        self.assertEqual(context["budget_dropped"][0]["packing_rank_basis"], "reranker_rank")
        self.assertEqual(context["budget_dropped"][0]["reranker_rank"], 1)
        self.assertEqual(context["budget_dropped"][0]["reranker_rank_delta"], -1)
        self.assertTrue(context["budget_dropped"][0]["reranker_promoted"])
        self.assertFalse(context["budget_dropped"][0]["reranker_outranked"])
        self.assertIsNone(context["budget_dropped"][0]["reranker_outranked_reason"])

    def test_before_target_history_deploy_context_uses_subject_entity_expansion(self):
        support = self.store.remember(
            "Blue Finch shipped on Staging before the cutover.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Blue Finch deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Routing note: current environment details live in the release checklist.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "before-target-history-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="What did Blue Finch deploy to before it moved to Production?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [support.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-target-subject-entity")
        self.assertEqual(retrieval["query_lookup"]["selected_search_query"], "blue finch")
        self.assertTrue(retrieval["query_lookup"]["target_history"]["applied"])
        self.assertEqual(retrieval["query_lookup"]["target_history"]["mutation_terms"], ["moved"])
        self.assertEqual(retrieval["query_lookup"]["target_history"]["target_query"], "production")
        self.assertEqual(retrieval["temporal"]["selection_strategy"], "target_history_support_preferred_v1")
        self.assertEqual(retrieval["temporal"]["selection_reason"], "history-target-query-terms")
        self.assertEqual(
            retrieval["temporal"]["selection_order"],
            "chronological_support_then_current_target",
        )
        self.assertEqual(retrieval["temporal"]["selected_ids"], [support.id, current.id])
        self.assertEqual(retrieval["temporal"]["selected_current_anchor_id"], current.id)

    def test_before_target_history_context_prefers_explicit_support_pair_over_generic_current_anchor(self):
        support = self.store.remember(
            "Blue Finch shipped on Staging before the cutover.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
        )
        current = self.store.remember(
            "Blue Finch deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Blue Finch changed after freeze.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )
        context_path = self.tmp_path / "before-target-history-generic-current-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="What did Blue Finch deploy to before it moved to Production?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [support.id, current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertCountEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [support.id, current.id, generic_anchor.id])
        self.assertEqual(retrieval["temporal"]["selection_strategy"], "target_history_support_preferred_v1")
        self.assertEqual(retrieval["temporal"]["selected_ids"], [support.id, current.id])
        self.assertEqual(retrieval["temporal"]["selected_current_anchor_id"], current.id)
        self.assertEqual(retrieval["temporal"]["selected_target_current_id"], current.id)
        self.assertEqual(retrieval["temporal"]["selected_target_support_ids"], [support.id])
        self.assertTrue(retrieval["temporal"]["fusion"]["applied"])
        self.assertEqual(context["temporal"]["history_ordering"], retrieval["temporal"]["history_ordering"])
        self.assertEqual(
            retrieval["temporal"]["history_ordering"],
            {
                "applied": True,
                "pass_through": False,
                "basis": "target_history_support_selection_rank",
                "source": "temporal_target_history_support_selection",
                "reason": "history-target-query-terms",
                "selected_history_rankings": [
                    {"memory_id": support.id, "rank": 1},
                    {"memory_id": current.id, "rank": 2},
                ],
                "considered_history_rankings": [
                    {"memory_id": support.id, "rank": 1, "selected": True},
                    {"memory_id": current.id, "rank": 2, "selected": True},
                    {"memory_id": generic_anchor.id, "rank": 3, "selected": False},
                ],
            },
        )
        self.assertEqual(
            retrieval["baseline_ranking"]["temporal_fusion_signal"],
            "temporal_support_rrf_score_v1",
        )
        self.assertEqual(
            retrieval["temporal"]["selection_exclusions"][0]["reason"],
            "target-history-current-anchor-not-selected",
        )
        self.assertEqual(retrieval["temporal"]["selection_exclusions"][0]["memory_id"], generic_anchor.id)
        self.assertEqual(
            context["temporal"]["selection_exclusions"],
            retrieval["temporal"]["selection_exclusions"],
        )
        candidate_by_id = {candidate["memory_id"]: candidate for candidate in retrieval["candidates"]}
        self.assertEqual([candidate["memory_id"] for candidate in retrieval["candidates"]], [support.id, current.id, generic_anchor.id])
        self.assertEqual(candidate_by_id[support.id]["temporal_fusion_rank"], 1)
        self.assertEqual(
            candidate_by_id[generic_anchor.id]["temporal_selection_exclusion"]["detail"],
            "explicit-target-history-support-pair-selected",
        )

    def test_before_target_history_context_preserves_support_vs_generic_selection_exclusion_roles(self):
        support_one = self.store.remember(
            "Blue Finch shipped on Staging before the cutover.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
        )
        support_two = self.store.remember(
            "Blue Finch was routed through the staging deploy target before the migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.5,
        )
        current = self.store.remember(
            "Blue Finch deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Blue Finch changed after freeze.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )
        context_path = self.tmp_path / "before-target-history-multi-support-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="What did Blue Finch deploy to before it moved to Production?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        retrieval = receipt["memory_receipt"]["retrieval"]
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["selection_strategy"], "target_history_support_preferred_v1")
        self.assertEqual(context["temporal"]["selection_exclusions"], temporal["selection_exclusions"])

        selected_support_id = temporal["selected_target_support_ids"][0]
        excluded_support_id = support_one.id if selected_support_id == support_two.id else support_two.id
        exclusions_by_id = {
            item["memory_id"]: item
            for item in context["temporal"]["selection_exclusions"]
        }

        self.assertEqual(exclusions_by_id[excluded_support_id]["candidate_role"], "history-support")
        self.assertEqual(
            exclusions_by_id[excluded_support_id]["reason"],
            "target-history-support-candidate-not-selected",
        )
        self.assertEqual(exclusions_by_id[generic_anchor.id]["candidate_role"], "generic-current")
        self.assertEqual(
            exclusions_by_id[generic_anchor.id]["reason"],
            "target-history-current-anchor-not-selected",
        )
        self.assertEqual(exclusions_by_id[generic_anchor.id]["selected_target_current_id"], current.id)

    def test_before_target_history_context_budget_drop_records_blocked_selected_pair_metadata(self):
        support = self.store.remember(
            "Blue Finch shipped on Staging before the cutover. " + ("detail " * 80),
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
        )
        current = self.store.remember(
            "Blue Finch deploy target changed to Production. " + ("state " * 80),
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Blue Finch changed after freeze.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )

        receipt = self.store.inject(
            "What did Blue Finch deploy to before it moved to Production?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(support) + approx_memory_tokens(current) - 1,
        )

        context = build_context(receipt)
        retrieval = receipt["retrieval"]
        self.assertEqual([memory["id"] for memory in context["memories"]], [support.id])
        self.assertCountEqual(receipt["retrieved_memory_ids"], [support.id, current.id, generic_anchor.id])
        self.assertEqual(receipt["injected_memory_ids"], [support.id])
        self.assertEqual(retrieval["packing"]["reservation"]["strategy"], "target_history_support_chain_v1")
        self.assertEqual(retrieval["packing"]["reservation"]["blocked_reason"], "reservation-exceeds-budget")
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion_reason"],
            "target-history-support-pair-blocked",
        )
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion"],
            {
                "reason": "target-history-support-pair-blocked",
                "detail": "selected-target-support-current-pair-exceeds-budget",
                "blocked_reason": "reservation-exceeds-budget",
                "blocked_pair_member_role": "target-current",
                "selected_target_current_id": current.id,
                "selected_target_support_ids": [support.id],
                "selected_pair_ids": [support.id, current.id],
            },
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion_reason"],
            "target-history-support-pair-blocked",
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion"]["selected_pair_ids"],
            [support.id, current.id],
        )

    def test_before_target_history_context_exact_pair_budget_keeps_generic_decoy_out_of_packing(self):
        support = self.store.remember(
            "Blue Finch shipped on Staging before the cutover.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
        )
        current = self.store.remember(
            "Blue Finch deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Blue Finch changed after freeze. " + ("note " * 80),
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )

        receipt = self.store.inject(
            "What did Blue Finch deploy to before it moved to Production?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(support) + approx_memory_tokens(current),
        )

        context = build_context(receipt)
        retrieval = receipt["retrieval"]
        self.assertEqual([memory["id"] for memory in context["memories"]], [support.id, current.id])
        self.assertEqual(context["budget_dropped"], [])
        self.assertEqual(
            retrieval["temporal"]["selection_exclusions"],
            [
                {
                    "memory_id": generic_anchor.id,
                    "reason": "target-history-current-anchor-not-selected",
                    "detail": "explicit-target-history-support-pair-selected",
                    "selection_strategy": "target_history_support_preferred_v1",
                    "candidate_role": "generic-current",
                    "selected_target_current_id": current.id,
                    "selected_target_support_ids": [support.id],
                    "selected_target_pair_ids": [support.id, current.id],
                }
            ],
        )
        self.assertEqual(context["temporal"]["selection_exclusions"], retrieval["temporal"]["selection_exclusions"])
        self.assertEqual(retrieval["packing"]["reservation"]["strategy"], "target_history_support_chain_v1")
        self.assertEqual(retrieval["packing"]["reservation"]["applied_ids"], [support.id, current.id])
        self.assertEqual(
            [item["memory_id"] for item in retrieval["packing"]["candidate_priorities"]],
            [support.id, current.id],
        )
        self.assertNotIn(
            generic_anchor.id,
            {item["memory_id"] for item in retrieval["packing"]["candidate_priorities"]},
        )

    def test_before_target_history_context_prefers_explicit_current_target_before_generic_anchor(self):
        stale = self.store.remember(
            "Blue Finch deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Blue Finch deploy target moved to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
        )
        generic_anchor = self.store.remember(
            "Blue Finch changed after freeze.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        context_path = self.tmp_path / "before-target-history-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="What did Blue Finch deploy to before it moved to Production?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        temporal = receipt["memory_receipt"]["retrieval"]["temporal"]
        self.assertEqual(temporal["injection_strategy"], "history_target_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_target_current_id"], current.id)
        self.assertEqual(temporal["selected_target_support_ids"], [generic_anchor.id])

    def test_current_target_context_prefers_update_fact_over_release_note_decoy(self):
        decoy = self.store.remember(
            "What deploy target follows the Blue Finch release note now is not stated in this routing note.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        self.store.remember(
            "Blue Finch deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        current = self.store.remember(
            "Blue Finch deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        context_path = self.tmp_path / "current-target-release-note-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="What deploy target follows the Blue Finch release note now?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [current.id])
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "current-subject-core")
        self.assertEqual(
            retrieval["query_lookup"]["current"]["update_anchor_terms"],
            ["target", "follows", "blue", "finch", "release", "note"],
        )
        self.assertCountEqual(receipt["memory_receipt"]["retrieved_memory_ids"], [decoy.id, current.id])
        self.assertEqual(retrieval["temporal"]["selection_strategy"], "current_update_preferred_v1")
        self.assertEqual(retrieval["temporal"]["selection_reason"], "current-update-query-terms")
        self.assertEqual(retrieval["temporal"]["selected_ids"], [current.id])
        self.assertEqual(retrieval["temporal"]["selected_current_anchor_id"], current.id)
        current_ordering = retrieval["temporal"]["current_ordering"]

        self.assertTrue(current_ordering["applied"])
        self.assertFalse(current_ordering["pass_through"])
        self.assertEqual(current_ordering["basis"], "current_update_preference_rank")
        self.assertEqual(current_ordering["source"], "temporal_current_update_preference")
        self.assertEqual(current_ordering["reason"], "current-update-explicit-anchor-selection")
        self.assertEqual(current_ordering["selected_current_rankings"], [{"memory_id": current.id, "rank": 1}])
        self.assertEqual(
            current_ordering["considered_current_rankings"],
            [
                {"memory_id": current.id, "rank": 1, "selected": True},
                {"memory_id": decoy.id, "rank": 2, "selected": False},
            ],
        )

    def test_build_context_current_deployment_approval_now_prefers_direct_fact_over_update_anchor(self):
        stale = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        update_current = self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
        )
        current = self.store.remember(
            "Deployment approver is Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
        )

        receipt = self.store.inject(
            "Who is on point for deployment approvals now?",
            agent_id="codex",
            risk="low",
            scope="project",
        )

        context = build_context(receipt)
        temporal = receipt["retrieval"]["temporal"]
        self.assertEqual([memory["id"] for memory in context["memories"]], [current.id])
        self.assertCountEqual(receipt["retrieved_memory_ids"], [stale.id, update_current.id, current.id])
        self.assertEqual(receipt["injected_memory_ids"], [current.id])
        self.assertEqual(temporal["selection_strategy"], "current_only_v1")
        self.assertEqual(temporal["selection_reason"], "current-query-terms")
        self.assertEqual(
            temporal["selection_exclusions"],
            [
                {
                    "memory_id": update_current.id,
                    "reason": "explicit-update-anchor-not-selected",
                    "detail": "direct-current-restatement-selected",
                    "selection_strategy": "current_only_v1",
                    "chosen_current_id": current.id,
                    "matching_current_value_ids": [current.id],
                    "update_current_value": "priya",
                    "update_pattern": "changed_to",
                }
            ],
        )
        self.assertEqual(
            temporal["conflict_sets"][0]["stale_ids"],
            [update_current.id, stale.id],
        )
        self.assertEqual(
            temporal["conflict_sets"][0]["resolution_strategy"],
            "explicit_update_current_value_restatement_prefers_direct_fact_v1",
        )
        candidate_by_id = {candidate["memory_id"]: candidate for candidate in receipt["retrieval"]["candidates"]}
        self.assertEqual(
            candidate_by_id[update_current.id]["temporal_selection_exclusion_reason"],
            "explicit-update-anchor-not-selected",
        )
        self.assertIsNone(candidate_by_id[stale.id]["temporal_selection_exclusion"])

    def test_original_history_question_context_prefers_earliest_state_but_keeps_current_visible(self):
        first = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        second = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
        )
        shared_timestamp = "2024-02-01T00:00:00Z"
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (shared_timestamp, shared_timestamp, first.id, second.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "original-history-question-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what was the original deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id])
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["query_lookup"]["selected_search_basis"],
            "history-subject-core",
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selection_reason"],
            "earliest-history-query-terms",
        )

    def test_original_history_question_context_orders_multi_update_chain_from_earliest(self):
        first = self.store.remember(
            "Deploy target is Heroku.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.3,
            authority="low",
        )
        second = self.store.remember(
            "Deploy target changed to Render.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
            authority="high",
        )
        third = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", third.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "original-history-question-chain-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what was the original deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        history_ordering = receipt["memory_receipt"]["retrieval"]["temporal"]["history_ordering"]
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id, third.id])
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selection_strategy"],
            "earliest_history_preferred_v1",
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selection_reason"],
            "earliest-history-query-terms",
        )
        self.assertEqual(context["temporal"]["history_ordering"], history_ordering)
        self.assertTrue(history_ordering["applied"])
        self.assertFalse(history_ordering["pass_through"])
        self.assertEqual(history_ordering["basis"], "earliest_history_selection_rank")
        self.assertEqual(history_ordering["source"], "temporal_earliest_history_selection")
        self.assertEqual(history_ordering["reason"], "earliest-history-query-terms")
        self.assertEqual(
            history_ordering["selected_history_rankings"],
            [
                {"memory_id": first.id, "rank": 1},
                {"memory_id": second.id, "rank": 2},
                {"memory_id": third.id, "rank": 3},
            ],
        )
        self.assertEqual(
            history_ordering["considered_history_rankings"],
            [
                {"memory_id": first.id, "rank": 1, "selected": True},
                {"memory_id": second.id, "rank": 2, "selected": True},
                {"memory_id": third.id, "rank": 3, "selected": True},
            ],
        )

    def test_original_history_context_prefers_explicit_current_before_generic_anchor(self):
        stale = self.store.remember(
            "Deployment approver was Alex.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deployment approver changed to Priya.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
            parents=[stale.id],
        )
        generic_anchor = self.store.remember(
            "Deployment approver changed after CAB review.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        context_path = self.tmp_path / "original-history-current-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="Who was the original deployment approver?",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        temporal = receipt["memory_receipt"]["retrieval"]["temporal"]
        self.assertEqual(temporal["injection_strategy"], "earliest_history_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_update_current_id"], current.id)
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])

    def test_original_target_history_context_prefers_explicit_current_relation_before_generic_anchor(self):
        stale = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deploy target is Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
            parents=[stale.id],
        )
        generic_anchor = self.store.remember(
            "Deploy target changed after CAB review.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        context_path = self.tmp_path / "original-target-history-current-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what was the original deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "history-subject-core")
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["injection_strategy"], "earliest_history_relation_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_relation_current_id"], current.id)
        self.assertEqual(temporal["selected_relation_support_ids"], [generic_anchor.id])
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])

    def test_original_target_history_context_rrf_promotes_explicit_current_relation_over_high_authority_generic_anchor(self):
        stale = self.store.remember(
            "Deploy target is Staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "Deploy target is the production control plane in us-east-1.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
            authority="low",
            parents=[stale.id],
        )
        generic_anchor = self.store.remember(
            "Deploy target changed after CAB review.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )
        budget = approx_memory_tokens(stale) + approx_memory_tokens(current)

        receipt = self.store.inject(
            "what was the original deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )
        context = build_context(receipt)

        self.assertEqual([memory["id"] for memory in context["memories"]], [stale.id, current.id])
        retrieval = receipt["retrieval"]
        temporal = retrieval["temporal"]
        self.assertTrue(temporal["fusion"]["applied"])
        self.assertEqual(temporal["fusion"]["signal"], "temporal_earliest_relation_pair_rrf_score_v1")
        self.assertEqual(
            [candidate["memory_id"] for candidate in retrieval["candidates"]],
            [stale.id, current.id, generic_anchor.id],
        )
        self.assertEqual(
            retrieval["baseline_ranking"]["temporal_fusion_signal"],
            "temporal_earliest_relation_pair_rrf_score_v1",
        )
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["memory_id"], generic_anchor.id)

    def test_build_context_original_history_budget_records_reserved_anchor_pair_exclusion_reason(self):
        first = self.store.remember(
            "Deploy target is Heroku.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.3,
            authority="low",
        )
        second = self.store.remember(
            "Deploy target changed to Render.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
            authority="high",
        )
        third = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", third.id),
        )
        self.store.conn.commit()
        budget = approx_memory_tokens(first) + approx_memory_tokens(third)

        receipt = self.store.inject(
            "what was the original deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=budget,
        )

        context = build_context(receipt)
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, third.id])
        retrieval = receipt["retrieval"]
        self.assertEqual(retrieval["packing"]["reservation"]["strategy"], "earliest_history_anchor_pair_v1")
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion_reason"],
            "earliest-history-anchor-pair-reserved",
        )
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion"],
            {
                "reason": "earliest-history-anchor-pair-reserved",
                "detail": "selected-earliest-current-anchor-pair-kept",
                "selected_stale_id": first.id,
                "selected_current_id": third.id,
                "selected_pair_ids": [first.id, third.id],
            },
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion_reason"],
            "earliest-history-anchor-pair-reserved",
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion"]["selected_pair_ids"],
            [first.id, third.id],
        )

    def test_recent_history_relation_context_prefers_plain_current_relation_before_generic_anchor(self):
        stale = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "API gateway points to production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.6,
            parents=[stale.id],
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        context_path = self.tmp_path / "recent-history-relation-current-anchor-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what did the api gateway point at before",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id, generic_anchor.id],
        )
        retrieval = receipt["memory_receipt"]["retrieval"]
        self.assertEqual(retrieval["query_lookup"]["selected_search_basis"], "role-relation-points-at")
        self.assertEqual(retrieval["query_lookup"]["lookup_basis"], "role-relation-points-at")
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["injection_strategy"], "history_relation_current_anchor_first_v1")
        self.assertEqual(temporal["selected_current_anchor_id"], current.id)
        self.assertEqual(temporal["selected_relation_current_id"], current.id)
        self.assertEqual(temporal["selected_relation_support_ids"], [generic_anchor.id])
        self.assertEqual(temporal["selected_current_support_ids"], [generic_anchor.id])

    def test_recent_history_relation_context_rrf_promotes_explicit_current_relation_over_high_authority_generic_anchor(self):
        stale = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.7,
        )
        current = self.store.remember(
            "API gateway points to the production control plane in us-east-1.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.4,
            authority="low",
            parents=[stale.id],
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="high",
        )
        receipt = self.store.inject(
            "what did the api gateway point at before",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=approx_memory_tokens(stale) + approx_memory_tokens(current),
        )
        context = build_context(receipt)
        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [stale.id, current.id],
        )
        retrieval = receipt["retrieval"]
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["fusion"]["signal"], "temporal_history_relation_pair_rrf_score_v1")
        self.assertEqual(
            [candidate["memory_id"] for candidate in retrieval["candidates"]],
            [stale.id, current.id, generic_anchor.id],
        )
        self.assertEqual(retrieval["baseline_ranking"]["temporal_fusion_signal"], "temporal_history_relation_pair_rrf_score_v1")
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["memory_id"], generic_anchor.id)

    def test_recent_history_relation_context_budget_keeps_selected_support_chain_when_it_fits(self):
        first = self.store.remember(
            "API gateway points to canary.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.3,
            authority="low",
        )
        second = self.store.remember(
            "API gateway points to staging.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.95,
            authority="high",
            parents=[first.id],
        )
        current = self.store.remember(
            "API gateway points to production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
            parents=[second.id],
        )
        generic_anchor = self.store.remember(
            "API gateway points changed after migration.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", current.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-04-01T00:00:00Z", "2024-04-01T00:00:00Z", generic_anchor.id),
        )
        self.store.conn.commit()
        receipt = self.store.inject(
            "what did the api gateway point at before",
            agent_id="codex",
            risk="low",
            scope="project",
            context_budget_tokens=(
                approx_memory_tokens(second)
                + approx_memory_tokens(current)
                + approx_memory_tokens(generic_anchor)
            ),
        )
        context = build_context(receipt)

        self.assertEqual(
            [memory["id"] for memory in context["memories"]],
            [second.id, current.id, generic_anchor.id],
        )
        retrieval = receipt["retrieval"]
        temporal = retrieval["temporal"]
        self.assertEqual(temporal["injection_strategy"], "history_relation_current_anchor_first_v1")
        self.assertEqual(temporal["selected_relation_support_ids"], [generic_anchor.id])
        self.assertEqual(
            retrieval["packing"]["reservation"]["requested_ids"],
            [second.id, current.id, generic_anchor.id],
        )
        self.assertEqual(retrieval["packing"]["budget_dropped"][0]["memory_id"], first.id)
        self.assertEqual(
            retrieval["packing"]["budget_dropped"][0]["reservation_exclusion_reason"],
            "history-support-chain-reserved",
        )
        self.assertEqual(
            context["budget_dropped"][0]["reservation_exclusion"],
            {
                "reason": "history-support-chain-reserved",
                "detail": "selected-stale-current-support-chain-kept",
                "selected_stale_id": second.id,
                "selected_current_id": current.id,
                "selected_support_ids": [generic_anchor.id],
                "selected_chain_ids": [second.id, current.id, generic_anchor.id],
            },
        )

    def test_recent_history_question_context_orders_latest_superseded_before_older_stale_states(self):
        first = self.store.remember(
            "Deploy target is Heroku.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.99,
            authority="policy",
        )
        second = self.store.remember(
            "Deploy target changed to Render.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.2,
            authority="low",
        )
        third = self.store.remember(
            "Deploy target changed to Production.",
            memory_type="semantic",
            scope="project",
            source_kind="human",
            trust=0.8,
            authority="medium",
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", first.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z", second.id),
        )
        self.store.conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z", third.id),
        )
        self.store.conn.commit()
        context_path = self.tmp_path / "recent-history-question-chain-context.json"

        receipt = run_with_memory(
            self.store,
            ["python3", "-c", "import os, pathlib; assert pathlib.Path(os.environ['ZERKER_MEMORY_CONTEXT']).exists()"],
            task="what was the previous deploy target",
            agent_id="codex",
            risk="low",
            scope="project",
            context_path=context_path,
        )

        self.assertEqual(receipt["exit_code"], 0)
        context = json.loads(context_path.read_text())
        self.assertEqual([memory["id"] for memory in context["memories"]], [second.id, first.id, third.id])
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selection_order"],
            "chronological_desc_prefer_latest_superseded",
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selected_stale_anchor_id"],
            second.id,
        )


if __name__ == "__main__":
    unittest.main()
