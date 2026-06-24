import json
import tempfile
import unittest
from pathlib import Path

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
        self.assertTrue(context_path.exists())
        context = json.loads(context_path.read_text())
        self.assertEqual(context["schema"], "zerker.memory_context.v1")
        self.assertEqual(len(context["memories"]), 1)
        self.assertEqual(context["memories"][0]["type"], "policy")

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
        self.assertIn(overview.id, [item["memory_id"] for item in context["budget_dropped"]])

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
        self.store.remember(
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
        self.store.remember(
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
        self.store.remember(
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
        self.store.remember(
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
        self.store.remember(
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
                shared_timestamp = "2024-02-01T00:00:00Z"
                self.store.conn.execute(
                    "UPDATE memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
                    (shared_timestamp, shared_timestamp, first.id, second.id),
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
        self.assertEqual(
            retrieval["baseline_ranking"]["temporal_fusion_signal"],
            "temporal_support_rrf_score_v1",
        )
        self.assertEqual(
            retrieval["temporal"]["selection_exclusions"][0]["reason"],
            "target-history-current-anchor-not-selected",
        )
        self.assertEqual(retrieval["temporal"]["selection_exclusions"][0]["memory_id"], generic_anchor.id)
        candidate_by_id = {candidate["memory_id"]: candidate for candidate in retrieval["candidates"]}
        self.assertEqual([candidate["memory_id"] for candidate in retrieval["candidates"]], [support.id, current.id, generic_anchor.id])
        self.assertEqual(candidate_by_id[support.id]["temporal_fusion_rank"], 1)
        self.assertEqual(
            candidate_by_id[generic_anchor.id]["temporal_selection_exclusion"]["detail"],
            "explicit-target-history-support-pair-selected",
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
        self.assertEqual([memory["id"] for memory in context["memories"]], [first.id, second.id, third.id])
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selection_strategy"],
            "earliest_history_preferred_v1",
        )
        self.assertEqual(
            receipt["memory_receipt"]["retrieval"]["temporal"]["selection_reason"],
            "earliest-history-query-terms",
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
