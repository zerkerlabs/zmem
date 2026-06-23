import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.bench import (
    judge_longmemeval,
    llm_answerer,
    locomo_to_zmem,
    longmemeval_to_zmem,
    score_locomo,
    summarize_evidence,
)


class BenchScriptsTest(unittest.TestCase):
    def test_longmemeval_converter_preserves_dated_support_turns(self):
        records = longmemeval_to_zmem.convert(
            [
                {
                    "question_id": "q1",
                    "question_type": "temporal",
                    "question": "Who owned deploys?",
                    "answer": "Mina",
                    "haystack_dates": ["2026-06-20"],
                    "haystack_sessions": [
                        [
                            {"role": "user", "content": "Deploy owner is Mina.", "has_answer": True},
                            {"role": "assistant", "content": "Noted.", "has_answer": False},
                        ]
                    ],
                }
            ]
        )

        self.assertEqual(records[0]["question_id"], "q1")
        self.assertEqual(records[0]["category"], "temporal")
        self.assertEqual(records[0]["history"][0], "user (2026-06-20): Deploy owner is Mina.")
        self.assertEqual(records[0]["supporting_facts"], ["user (2026-06-20): Deploy owner is Mina."])
        self.assertFalse(records[0]["should_abstain"])

    def test_locomo_converter_maps_evidence_dia_ids_to_history_content(self):
        records = locomo_to_zmem.convert(
            [
                {
                    "sample_id": "conv1",
                    "conversation": {
                        "session_1_date_time": "2026-06-20",
                        "session_1": [
                            {"dia_id": "d1", "speaker": "A", "text": "Release owner is Nia."},
                            {"dia_id": "d2", "speaker": "B", "text": "Ok."},
                        ],
                    },
                    "qa": [
                        {
                            "category": 2,
                            "question": "Who owns release?",
                            "answer": "Nia",
                            "evidence": ["d1"],
                        }
                    ],
                }
            ]
        )

        self.assertEqual(records[0]["question_id"], "conv1#0")
        self.assertEqual(records[0]["category"], "temporal_reasoning")
        self.assertEqual(records[0]["supporting_facts"], ["[d1] (2026-06-20) A: Release owner is Nia."])
        self.assertFalse(records[0]["should_abstain"])

    def test_locomo_scorer_handles_abstention_and_token_f1(self):
        self.assertEqual(score_locomo.score_row({"category": "5", "hypothesis": "I don't know"}), (1.0, 1.0))
        f1, em = score_locomo.score_row(
            {
                "category": "single_hop",
                "hypothesis": "Nia owns the release",
                "reference": "Release owner is Nia",
            }
        )

        self.assertGreater(f1, 0.0)
        self.assertLess(f1, 1.0)
        self.assertEqual(em, 0.0)

    def test_longmemeval_judge_label_parser_is_pure(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "judge.log"
            log_path.write_text("autoeval_label: correct\nnoise\nautoeval_label='incorrect'\n", encoding="utf-8")

            self.assertEqual(judge_longmemeval.parse_labels(log_path), ["correct", "incorrect"])
            self.assertTrue(judge_longmemeval.label_is_correct("yes"))
            self.assertFalse(judge_longmemeval.label_is_correct("incorrect"))

    def test_llm_answerer_requires_explicit_openai_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                llm_answerer.generate_hypothesis("question", ["memory"])

    def test_evidence_summary_checks_matrix_and_comparison_hashes_without_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix_dir = Path(tmp) / "matrix"
            matrix_dir.mkdir()
            comparison = {
                "schema": "zerker.benchmark_comparison.v1",
                "ok": True,
                "question_summary": {"visible_delta_question_count": 0},
            }
            comparison["comparison_hash"] = _content_hash(comparison, "comparison_hash")
            (matrix_dir / "benchmark-comparison.json").write_text(
                json.dumps(comparison, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            matrix = {
                "schema": "zerker.benchmark_matrix.v1",
                "ok": True,
                "run_id": "fixture-matrix",
                "benchmark": "longmemeval",
                "dataset": "fixtures/longmemeval.jsonl",
                "split": "dev",
                "seed": 42,
                "context_budget_tokens": 200,
                "retrieval_modes": ["fts", "pseudo-embedding-rerank"],
                "comparison_path": "some/repo-relative/matrix/benchmark-comparison.json",
                "comparison_hash": comparison["comparison_hash"],
                "question_summary": {"visible_delta_question_count": 0},
                "mode_runs": [
                    {
                        "retrieval_mode": "fts",
                        "result_hash": "result-a",
                        "aggregate_merkle_root": "root-a",
                        "summary": {"accuracy": 1.0, "question_count": 1},
                    }
                ],
            }
            matrix["matrix_hash"] = _content_hash(matrix, "matrix_hash")
            (matrix_dir / "benchmark-matrix.json").write_text(
                json.dumps(matrix, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            summary = summarize_evidence.load_summary(matrix_dir)

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["schema"], "zerker.benchmark_evidence_summary.v1")
            self.assertEqual(summary["run_id"], "fixture-matrix")
            self.assertEqual(summary["benchmark"], "longmemeval")
            self.assertFalse(summary["claim_boundary"]["public_benchmark_claim"])
            self.assertEqual(summary["mode_summaries"][0]["result_hash"], "result-a")
            self.assertEqual(summary["artifacts"]["matrix"]["declared_hash"], matrix["matrix_hash"])

            matrix["seed"] = 43
            (matrix_dir / "benchmark-matrix.json").write_text(
                json.dumps(matrix, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tampered = summarize_evidence.load_summary(matrix_dir)

            self.assertFalse(tampered["ok"])
            self.assertFalse(tampered["checks"]["matrix_hash"])


def _content_hash(payload: dict, hash_key: str) -> str:
    canonical = dict(payload)
    canonical.pop(hash_key, None)
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
