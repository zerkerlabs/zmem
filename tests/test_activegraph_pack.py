import json
import tempfile
import unittest
from pathlib import Path

from zerker_memory.bench.activegraph_runner import run_locomo_activegraph_benchmark, score_trace
from zerker_memory.integrations.activegraph import handle_event
from zerker_memory.store import MemoryStore


class ActiveGraphPackTest(unittest.TestCase):
    def test_pack_manifest_matches_activegraph_contract(self):
        manifest = (Path(__file__).resolve().parents[1] / "pack" / "pack.yaml").read_text(encoding="utf-8")

        self.assertIn("name: zmem", manifest)
        self.assertIn("entry_point: zerker_memory.integrations.activegraph", manifest)
        self.assertIn("  - zmem.persist", manifest)
        self.assertIn("  - zmem.recall", manifest)
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

            scored = score_trace(trace_path)
            self.assertEqual(scored["question_count"], 5)
            self.assertFalse(scored["public_benchmark_claim"])
            self.assertEqual(scored["aggregate_merkle_root"], result["scored_receipt"]["aggregate_merkle_root"])


if __name__ == "__main__":
    unittest.main()
