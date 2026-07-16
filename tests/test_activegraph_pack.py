import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from zerker_memory.bench.activegraph_runner import run_locomo_activegraph_benchmark, score_trace
from zerker_memory.integrations.activegraph import enable_precall_recall, handle_event
from zerker_memory.store import MemoryStore


class ActiveGraphPackTest(unittest.TestCase):
    def test_pack_manifest_matches_activegraph_contract(self):
        manifest = (Path(__file__).resolve().parents[1] / "pack" / "pack.yaml").read_text(encoding="utf-8")

        self.assertIn("name: zmem", manifest)
        self.assertIn("entry_point: zerker_memory.pack:pack", manifest)
        self.assertIn("  - zmem.persist", manifest)
        self.assertIn("  - zmem.recall", manifest)
        self.assertIn("benchmark_stages:", manifest)
        self.assertIn("ZMEM_RETRIEVAL_MODE:", manifest)
        self.assertIn('default: "fts"', manifest)

    def test_persist_and_recall_use_activegraph_scope_and_causal_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            persisted = handle_event(
                {
                    "id": "ag_evt_write_1",
                    "type": "object.created",
                    "session_id": "session-a",
                    "run_id": "run-a",
                    "payload": {"content": "The release target is Production."},
                },
                store=store,
            )
            recalled = handle_event(
                {
                    "id": "ag_evt_read_1",
                    "type": "llm.requested",
                    "session_id": "session-a",
                    "run_id": "run-b",
                    "payload": {"query": "What is the release target?"},
                },
                store=store,
            )

            self.assertEqual(persisted.scope, "ag:session-a")
            self.assertIsNotNone(persisted.memory_id)
            self.assertEqual(recalled.scope, "ag:session-a")
            self.assertIn("The release target is Production.", recalled.payload["prepend_context"])
            receipt = store.memory_write_receipt(persisted.memory_id)
            self.assertEqual(
                receipt["treeship_statement"]["object"]["caused_by_event"],
                "ag_evt_write_1",
            )

    @patch("zerker_memory.integrations.activegraph.MemoryStore")
    def test_runtime_owned_store_connections_are_closed(self, memory_store):
        owned = memory_store.return_value
        owned.remember.return_value = SimpleNamespace(
            id="mem_owned",
            content_hash="sha256:owned",
            type="semantic",
            scope="ag:owned",
            to_dict=lambda: {"id": "mem_owned"},
        )
        handle_event(
            {
                "id": "ag_evt_owned_write",
                "type": "object.created",
                "session_id": "owned",
                "payload": {"content": "The owned store is closed after persistence."},
            },
            db_path=Path("owned.sqlite"),
        )
        owned.conn.close.assert_called_once_with()

        owned.reset_mock()
        owned.inject.return_value = {
            "action_id": "act_owned",
            "task_hash": "sha256:task",
            "merkle_root": "sha256:root",
            "memories": [],
            "retrieval": {},
        }
        handle_event(
            {
                "id": "ag_evt_owned_read",
                "type": "llm.requested",
                "session_id": "owned",
                "payload": {"query": "What happens to the owned store?"},
            },
            db_path=Path("owned.sqlite"),
        )
        owned.conn.close.assert_called_once_with()

    def test_precall_host_hook_injects_memory_into_recorded_activegraph_prompt(self):
        try:
            from activegraph import Graph, Runtime, clear_registry, llm_behavior, register
            from activegraph.llm import LLMResponse
        except ModuleNotFoundError:
            self.skipTest("activegraph optional dependency is not installed")

        from decimal import Decimal

        class CaptureProvider:
            default_model = "zmem-capture-model"

            def __init__(self):
                self.calls = []

            def recognizes_model(self, _name):
                return True

            def supports_native_structured_output(self, _model):
                return False

            def count_tokens(self, *, system, messages, model):
                return len(system) + sum(len(message.content) for message in messages)

            def estimate_cost(self, *, input_tokens, output_tokens, model):
                return Decimal("0")

            def complete(self, **kwargs):
                self.calls.append(kwargs)
                return LLMResponse(
                    raw_text="ok",
                    parsed=None,
                    input_tokens=1,
                    output_tokens=1,
                    cost_usd=Decimal("0"),
                    latency_seconds=0.0,
                    model=kwargs["model"],
                    finish_reason="end_turn",
                )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            store = MemoryStore(db_path)
            store.remember(
                "The release target is Production.",
                memory_type="semantic",
                scope="ag:host-run",
                source_kind="human",
            )
            store.conn.close()

            previous_registry = clear_registry()
            try:
                @llm_behavior(
                    name="answer_release_question",
                    on=["object.created"],
                    model="zmem-capture-model",
                )
                def answer_release_question(event, graph, ctx, llm_output):
                    return None

                self.assertIs(
                    enable_precall_recall(answer_release_question, db_path=db_path),
                    answer_release_question,
                )
                self.assertIs(
                    enable_precall_recall(answer_release_question, db_path=db_path),
                    answer_release_question,
                )
                provider = CaptureProvider()
                graph = Graph(run_id="host-run")
                runtime = Runtime(
                    graph,
                    behaviors=[answer_release_question],
                    llm_provider=provider,
                )
                graph.add_object("question", {"query": "What is the release target?"})
                runtime.run_until_idle()
            finally:
                clear_registry()
                for registered_behavior in previous_registry:
                    register(registered_behavior)

        self.assertEqual(len(provider.calls), 1)
        sent_content = provider.calls[0]["messages"][0].content
        self.assertIn("ZMem recall receipt: act_", sent_content)
        self.assertIn("The release target is Production.", sent_content)
        requested = next(event for event in graph.events if event.type == "llm.requested")
        recorded_content = requested.payload["prompt"]["messages"][0]["content"]
        self.assertEqual(recorded_content, sent_content)

    def test_runnable_host_example_persists_then_recalls_across_runs(self):
        try:
            import activegraph  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("activegraph optional dependency is not installed")

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite"
            results = []
            for _ in range(2):
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(repo_root / "examples" / "activegraph_host.py"),
                        "--db",
                        str(db_path),
                    ],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
                result = json.loads(completed.stdout)
                self.assertTrue(result["ok"])
                self.assertNotEqual(result["write_run_id"], result["read_run_id"])
                self.assertTrue(result["checks"]["causal_pointer_preserved"])
                self.assertTrue(result["checks"]["memory_recalled_before_call"])
                self.assertTrue(result["checks"]["recorded_prompt_matches_provider"])
                self.assertEqual(result["answer"], "The release target is Production.")
                results.append(result)

            self.assertNotEqual(results[0]["persisted_memory_id"], results[1]["persisted_memory_id"])

            store = MemoryStore(db_path)
            memories = store.list_memories(scope=results[-1]["scope"])
            store.conn.close()
            self.assertTrue(any(memory.id == results[-1]["persisted_memory_id"] for memory in memories))

    def test_locomo_activegraph_runner_writes_compact_trace_without_bundles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = tmp_path / "locomo.jsonl"
            records = []
            for index in range(5):
                records.append(
                    {
                        "question_id": f"q{index}",
                        "sample_id": f"s{index}",
                        "split": "dev",
                        "category": "single_hop",
                        "history": [f"Answer {index}"],
                        "question": f"What is answer {index}?",
                        "answer": f"Answer {index}",
                        "supporting_facts": [f"Answer {index}"],
                    }
                )
            dataset.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

            result = run_locomo_activegraph_benchmark(
                dataset,
                run_id="smoke",
                out=tmp_path / "runs",
                retrieval_mode="fts",
                split="dev",
            )
            run_dir = Path(result["run_dir"])
            trace_path = run_dir / "trace.jsonl"
            scored_path = run_dir / "scored_receipt.json"

            self.assertTrue((run_dir / "activegraph.sqlite").exists())
            self.assertTrue((run_dir / "memory.sqlite").exists())
            self.assertTrue(trace_path.exists())
            self.assertEqual(len(trace_path.read_text(encoding="utf-8").splitlines()), 5)
            self.assertTrue(scored_path.exists())
            self.assertEqual(list(run_dir.rglob("*.bundle.json")), [])
            self.assertEqual(result["event_count"], 20)
            self.assertEqual(result["event_batch_size"], 128)
            self.assertEqual(result["event_commit_count"], 1)
            with sqlite3.connect(run_dir / "activegraph.sqlite") as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 20)

            scored = score_trace(trace_path)
            self.assertEqual(scored["question_count"], 5)
            self.assertFalse(scored["public_benchmark_claim"])
            self.assertEqual(scored["aggregate_merkle_root"], result["scored_receipt"]["aggregate_merkle_root"])
            self.assertEqual(result["scored_receipt"]["activegraph_event_log"]["commit_count"], 1)

    def test_activegraph_runner_ingests_shared_conversation_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = tmp_path / "shared.jsonl"
            history = ["Kestrel owner is Priya.", "Kestrel deploy window is Friday."]
            records = [
                {
                    "question_id": "owner",
                    "sample_id": "kestrel",
                    "split": "dev",
                    "category": "single_hop",
                    "history": history,
                    "question": "Who owns Kestrel?",
                    "answer": history[0],
                    "supporting_facts": [history[0]],
                },
                {
                    "question_id": "window",
                    "sample_id": "kestrel",
                    "split": "dev",
                    "category": "single_hop",
                    "history": history,
                    "question": "When is the Kestrel deploy window?",
                    "answer": history[1],
                    "supporting_facts": [history[1]],
                },
            ]
            dataset.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

            result = run_locomo_activegraph_benchmark(
                dataset,
                run_id="shared",
                out=tmp_path / "runs",
                retrieval_mode="fts",
                split="dev",
            )
            store = MemoryStore(Path(result["memory_db"]))
            memories = store.list_memories(scope="bench:activegraph:kestrel")
            store.conn.close()

            self.assertEqual(result["conversation_count"], 1)
            self.assertEqual(result["history_memory_count"], 2)
            self.assertEqual(len(memories), 2)
            self.assertEqual(result["event_count"], 8)
            self.assertEqual(result["event_commit_count"], 1)


if __name__ == "__main__":
    unittest.main()
