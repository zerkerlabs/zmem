import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.bench import judge_longmemeval, llm_answerer, locomo_to_zmem, longmemeval_to_zmem, score_locomo


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


if __name__ == "__main__":
    unittest.main()
