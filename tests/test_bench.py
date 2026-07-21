import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zerker_memory.retrieval_providers import EmbeddingProviderResult
from zerker_memory.bench import (
    BENCHMARK_COMPARISON_SCHEMA,
    BENCHMARK_MATRIX_COMPARISON_SCHEMA,
    BENCHMARK_OPTIONAL_RETRIEVAL_MODES,
    BENCHMARK_RETRIEVAL_CONFIG_SCHEMA,
    BENCHMARK_RETRIEVAL_MODES,
    BENCHMARK_RETRIEVAL_RUN_MODES,
    BENCHMARK_SCORE_SUMMARY_SCHEMA,
    _comparison_question_summary,
    compare_benchmark_matrices,
    _render_matrix_report_text,
    compare_benchmark_results,
    benchmark_retrieval_config_hash,
    list_benchmarks,
    render_benchmark_dashboard,
    render_benchmark_report,
    render_public_benchmark_page,
    resolve_benchmark_retrieval_config,
    run_beam_benchmark,
    run_benchmark_matrix,
    run_locomo_benchmark,
    run_longmemeval_benchmark,
    run_synthetic_benchmark,
    verify_benchmark_artifact,
    verify_benchmark_result,
    write_benchmark_comparison_artifacts,
    write_benchmark_matrix_comparison_artifacts,
)
from zerker_memory.cli import (
    _append_benchmark_efficiency_delta_lines,
    _append_benchmark_memory_count_delta_lines,
    _append_benchmark_question_summary_lines,
    build_parser,
    main,
)
from zerker_memory.store import sha256_text, stable_json


class BenchmarkHarnessTest(unittest.TestCase):
    def test_benchmark_summary_bounds_long_question_id_lists(self):
        lines: list[str] = []

        _append_benchmark_question_summary_lines(
            lines,
            {
                "question_count": 12,
                "visible_delta_question_count": 0,
                "stable_misses": {"count": 0, "question_ids": []},
                "stable_wins": {"count": 12, "question_ids": [f"q-{index}" for index in range(12)]},
            },
        )

        self.assertIn("Stable win ids: q-0, q-1, q-2, q-3, q-4, q-5, q-6, q-7, q-8, q-9 ... (+2 more)", lines)
        self.assertNotIn("q-10", "\n".join(lines))

    def test_benchmark_summary_bounds_per_question_delta_rows(self):
        lines: list[str] = []
        summary = {
            "memory_count_deltas": [
                {
                    "question_id": f"q-{index}",
                    "retrieval_mode": "fts-multihop",
                    "retrieved_memory_count_delta": 1,
                    "injected_memory_count_delta": 1,
                    "withheld_memory_count_delta": 0,
                }
                for index in range(12)
            ],
            "efficiency_deltas": [
                {
                    "question_id": f"q-{index}",
                    "retrieval_mode": "fts-multihop",
                    "retrieval_latency_ms_delta": 1.0,
                    "total_tokens_delta": 2,
                }
                for index in range(13)
            ],
        }

        _append_benchmark_memory_count_delta_lines(lines, summary)
        _append_benchmark_efficiency_delta_lines(lines, summary)

        rendered = "\n".join(lines)
        self.assertIn("Memory count delta q-9", rendered)
        self.assertNotIn("Memory count delta q-10", rendered)
        self.assertIn("Memory count deltas omitted: 2", rendered)
        self.assertIn("Efficiency delta q-9", rendered)
        self.assertNotIn("Efficiency delta q-10", rendered)
        self.assertIn("Efficiency deltas omitted: 3", rendered)

    def test_list_benchmarks_includes_supported_adapters(self):
        result = list_benchmarks()

        self.assertEqual(result["schema"], "zerker.benchmark_list.v1")
        self.assertIn("synthetic", {benchmark["name"] for benchmark in result["benchmarks"]})
        self.assertIn("longmemeval", {benchmark["name"] for benchmark in result["benchmarks"]})
        self.assertIn("locomo", {benchmark["name"] for benchmark in result["benchmarks"]})
        self.assertIn("beam", {benchmark["name"] for benchmark in result["benchmarks"]})

    def test_beam_official_directory_adapter_records_scale_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            conversation_dir = Path(tmp) / "chats" / "100K" / "1"
            probing_dir = conversation_dir / "probing_questions"
            probing_dir.mkdir(parents=True)
            (conversation_dir / "chat.json").write_text(
                json.dumps(
                    [
                        {
                            "batch_number": 1,
                            "time_anchor": "March-15-2024",
                            "turns": [
                                [
                                    {"role": "user", "id": 0, "content": "Tell me about the notebook."},
                                    {
                                        "role": "assistant",
                                        "id": 1,
                                        "content": "Which notebook do you mean?",
                                    },
                                    {
                                        "role": "user",
                                        "id": 2,
                                        "content": "The Kestrel deployment notebook is cobalt blue.",
                                    },
                                ]
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (probing_dir / "probing_questions.json").write_text(
                json.dumps(
                    {
                        "information_extraction": [
                            {
                                "question": "What color is the Kestrel deployment notebook?",
                                "answer": "cobalt blue",
                                "difficulty": "easy",
                                "source_chat_ids": [2],
                                "rubric": ["cobalt blue"],
                            }
                        ],
                        "abstention": [
                            {
                                "question": "What material is the notebook made from?",
                                "ideal_response": "The chat does not say.",
                                "difficulty": "easy",
                                "rubric": ["not stated"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = run_beam_benchmark(
                Path(tmp) / "bench",
                conversation_dir,
                run_id="beam-smoke",
                retrieval_mode="fts-adaptive",
                write_trace=True,
            )
            result_path = Path(result["result_path"])
            payload = json.loads(result_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["benchmark"], "beam")
            self.assertEqual(payload["split"], "100K")
            self.assertEqual(payload["scale"]["conversation_count"], 1)
            self.assertEqual(payload["scale"]["message_count"], 3)
            self.assertEqual(payload["scale"]["source_reference_coverage"], 1.0)
            self.assertEqual(payload["summary"]["question_count"], 2)
            self.assertEqual(payload["summary"]["scoring"], "local-evidence-recall")
            self.assertFalse(payload["summary"]["public_benchmark_claim"])
            self.assertTrue(all(question["correct"] for question in payload["questions"]))
            self.assertEqual(
                payload["questions"][0]["benchmark_metadata"]["source_chat_ids"],
                ["2"],
            )
            self.assertTrue((result_path.parent / "trace.jsonl").exists())
            self.assertTrue(verify_benchmark_result(result_path)["ok"])

    def test_synthetic_run_writes_proof_bearing_layout_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_synthetic_benchmark(Path(tmp), seed=0, run_id="proof-run")
            run_dir = Path(result["run_dir"])

            self.assertTrue(result["ok"])
            self.assertTrue((run_dir / "benchmark-run.json").exists())
            self.assertTrue((run_dir / "benchmark-result.json").exists())
            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "snapshots" / "before.snapshot.json").exists())
            self.assertTrue((run_dir / "snapshots" / "after.snapshot.json").exists())
            self.assertEqual(len(list((run_dir / "questions").glob("*.json"))), 4)
            self.assertEqual(len(list((run_dir / "receipts").glob("*.bundle.json"))), 4)

            verify = verify_benchmark_result(run_dir / "benchmark-result.json")

            self.assertTrue(verify["ok"])
            self.assertTrue(all(check["ok"] for check in verify["checks"]))
            self.assertEqual(result["summary"]["accuracy"], 0.75)

    def test_synthetic_trace_run_writes_receipt_with_token_efficiency(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_synthetic_benchmark(Path(tmp), seed=0, run_id="trace-receipt", write_trace=True)
            run_dir = Path(result["run_dir"])

            receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

            self.assertFalse(receipt["public_benchmark_claim"])
            self.assertEqual(receipt["run_id"], "trace-receipt")
            self.assertEqual(receipt["retrieval_mode"], "fts")
            self.assertEqual(receipt["token_efficiency"], summary["token_efficiency"])
            self.assertEqual(receipt["trace_sha256"], sha256_text((run_dir / "trace.jsonl").read_text(encoding="utf-8")))

    def test_longmemeval_matrix_trace_receipt_preserves_summary_hashes_and_mode_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="lme-trace-matrix",
                write_trace=True,
            )

            self._assert_matrix_trace_receipt(
                matrix,
                dataset=dataset,
                expected_dataset_name="xiaowu0162/longmemeval-cleaned",
            )

    def test_locomo_matrix_trace_receipt_preserves_summary_hashes_and_mode_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-trace-matrix",
                write_trace=True,
            )

            self._assert_matrix_trace_receipt(
                matrix,
                dataset=dataset,
                expected_dataset_name="snap-research/locomo",
            )

    def test_benchmark_matrix_writes_score_summary_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="score-summary-matrix")
            matrix_dir = Path(matrix["matrix_dir"])
            score_summary_path = matrix_dir / "score-summary.json"

            score_summary = json.loads(score_summary_path.read_text(encoding="utf-8"))

            self.assertEqual(score_summary["schema"], BENCHMARK_SCORE_SUMMARY_SCHEMA)
            self.assertEqual(score_summary["artifact_type"], "matrix")
            self.assertEqual(score_summary["run_id"], matrix["run_id"])
            self.assertEqual(score_summary["benchmark"], "synthetic")
            self.assertEqual(score_summary["dataset"], "synthetic")
            self.assertEqual(score_summary["matrix_hash"], matrix["matrix_hash"])
            self.assertEqual(score_summary["comparison_hash"], matrix["comparison_hash"])
            self.assertEqual(score_summary["claim_status"], "local synthetic proof")
            self.assertEqual(score_summary["verification_status"], matrix["verification_status"])
            self.assertEqual(
                score_summary["comparison_verification_status"],
                matrix["comparison_verification_status"],
            )
            self.assertEqual(score_summary["question_summary"], matrix["summary"]["question_summary"])
            self.assertEqual(score_summary["budget_context_question_count"], 0)
            self.assertEqual(
                [mode["retrieval_mode"] for mode in score_summary["modes"]],
                list(BENCHMARK_RETRIEVAL_MODES),
            )
            expected_best_mode = max(
                score_summary["modes"],
                key=lambda mode: (
                    float(mode.get("accuracy", 0.0)),
                    -float(mode.get("p95_retrieval_latency_ms", 0.0)),
                ),
            )["retrieval_mode"]
            self.assertEqual(score_summary["best_mode"], expected_best_mode)
            abstention_mode = next(
                mode for mode in score_summary["modes"] if mode["retrieval_mode"] == "pseudo-embedding-rerank"
            )
            self.assertEqual(abstention_mode["question_count"], 4)
            self.assertIn("f1", abstention_mode)
            self.assertIn("recall_at_k", abstention_mode)
            self.assertEqual(abstention_mode["abstention"]["question_count"], 1)
            self.assertEqual(abstention_mode["abstention"]["accuracy"], 1.0)
            self.assertIn("abstention", abstention_mode["category_summaries"])
            self.assertEqual(
                abstention_mode["category_summaries"]["abstention"]["budget_dropped_memory_count"],
                0,
            )

    def test_benchmark_report_surfaces_memory_counts_hashes_and_proof_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_synthetic_benchmark(Path(tmp), seed=0, run_id="report-proof")
            run_dir = Path(result["run_dir"])
            report_text = (run_dir / "report.md").read_text(encoding="utf-8")
            summary = result["summary"]

            self.assertIn("- Retrieval mode: `fts`", report_text)
            self.assertIn("## Category Performance", report_text)
            self.assertIn("### multi_hop", report_text)
            self.assertIn(f"- Retrieved memories: `{summary['retrieved_memory_count']}`", report_text)
            self.assertIn(f"- Injected memories: `{summary['injected_memory_count']}`", report_text)
            self.assertIn(f"- Withheld memories: `{summary['withheld_memory_count']}`", report_text)
            self.assertIn(f"- Total tokens: `{summary['total_tokens']}`", report_text)
            self.assertIn("- Retrieval latency p50/p95/p99 ms:", report_text)
            self.assertIn("- Retrieved / injected / withheld memories:", report_text)
            self.assertIn("- Retrieved memory ids:", report_text)
            self.assertIn("- Injected memory ids:", report_text)
            self.assertIn("- Withheld memory ids:", report_text)
            self.assertIn("- Should abstain:", report_text)
            self.assertIn("- Supporting evidence:", report_text)
            self.assertIn("- Outcome reason:", report_text)
            self.assertIn("- Final answer:", report_text)
            self.assertIn("- Outcome reasons:", report_text)
            self.assertIn("- Failure reasons:", report_text)
            self.assertIn("- Retrieved memories:", report_text)
            self.assertIn("- Injected memories:", report_text)
            self.assertIn("Production deploys require human approval", report_text)
            self.assertIn("- Question hash:", report_text)
            self.assertIn("- Receipt bundle hash:", report_text)
            self.assertIn("- Receipt Merkle root:", report_text)

    def test_parser_accepts_bench_commands(self):
        parser = build_parser()

        args = parser.parse_args(
            [
                "bench",
                "run",
                "synthetic",
                "--out",
                "/tmp/bench",
                "--seed",
                "0",
                "--run-id",
                "abc",
                "--retrieval-provider-config",
                "providers.json",
            ]
        )
        self.assertEqual(args.command, "bench")
        self.assertEqual(args.bench_command, "run")
        self.assertEqual(args.benchmark, "synthetic")
        self.assertEqual(str(args.out), "/tmp/bench")
        self.assertEqual(args.seed, 0)
        self.assertEqual(args.run_id, "abc")
        self.assertEqual(str(args.retrieval_provider_config), "providers.json")

        args = parser.parse_args(["bench", "verify", "/tmp/bench/abc/benchmark-result.json"])
        self.assertEqual(args.bench_command, "verify")
        self.assertEqual(str(args.result_json), "/tmp/bench/abc/benchmark-result.json")

        args = parser.parse_args(["bench", "compare", "/tmp/bench/a.json", "/tmp/bench/b.json", "--out", "/tmp/bench"])
        self.assertEqual(args.bench_command, "compare")
        self.assertEqual([str(path) for path in args.result_jsons], ["/tmp/bench/a.json", "/tmp/bench/b.json"])
        self.assertEqual(str(args.out), "/tmp/bench")

        args = parser.parse_args(["bench", "compare-matrices", "/tmp/bench/a", "/tmp/bench/b", "--out", "/tmp/bench"])
        self.assertEqual(args.bench_command, "compare-matrices")
        self.assertEqual([str(path) for path in args.matrix_jsons], ["/tmp/bench/a", "/tmp/bench/b"])
        self.assertEqual(str(args.out), "/tmp/bench")

        args = parser.parse_args(["bench", "dashboard", "/tmp/bench/matrix", "--out", "/tmp/bench/dashboard.html"])
        self.assertEqual(args.bench_command, "dashboard")
        self.assertEqual(str(args.matrix), "/tmp/bench/matrix")
        self.assertEqual(str(args.out), "/tmp/bench/dashboard.html")

        args = parser.parse_args(["bench", "public-page", "/tmp/bench/matrix", "--out", "/tmp/bench/public.html"])
        self.assertEqual(args.bench_command, "public-page")
        self.assertEqual(str(args.matrix), "/tmp/bench/matrix")
        self.assertEqual(str(args.out), "/tmp/bench/public.html")

        args = parser.parse_args(
            [
                "bench",
                "matrix",
                "synthetic",
                "--out",
                "/tmp/bench",
                "--run-id",
                "matrix",
                "--retrieval-provider-config",
                "providers.json",
            ]
        )
        self.assertEqual(args.bench_command, "matrix")
        self.assertEqual(args.benchmark, "synthetic")
        self.assertEqual(str(args.out), "/tmp/bench")
        self.assertEqual(args.run_id, "matrix")
        self.assertEqual(str(args.retrieval_provider_config), "providers.json")

    def test_parser_accepts_bench_summary_only_flags(self):
        parser = build_parser()

        args = parser.parse_args(["bench", "report", "/tmp/bench/run", "--summary-only"])
        self.assertEqual(args.bench_command, "report")
        self.assertTrue(args.summary_only)

        args = parser.parse_args(["bench", "dashboard", "/tmp/bench/matrix", "--summary-only"])
        self.assertEqual(args.bench_command, "dashboard")
        self.assertTrue(args.summary_only)

        args = parser.parse_args(["bench", "public-page", "/tmp/bench/matrix", "--summary-only"])
        self.assertEqual(args.bench_command, "public-page")
        self.assertTrue(args.summary_only)

        args = parser.parse_args(["bench", "compare", "/tmp/a.json", "/tmp/b.json", "--summary-only"])
        self.assertEqual(args.bench_command, "compare")
        self.assertTrue(args.summary_only)

        args = parser.parse_args(["bench", "compare-matrices", "/tmp/a", "/tmp/b", "--summary-only"])
        self.assertEqual(args.bench_command, "compare-matrices")
        self.assertTrue(args.summary_only)

        args = parser.parse_args(["bench", "matrix", "synthetic", "--out", "/tmp/bench", "--summary-only"])
        self.assertEqual(args.bench_command, "matrix")
        self.assertTrue(args.summary_only)

    def test_parser_accepts_bench_retrieval_mode(self):
        parser = build_parser()

        args = parser.parse_args(
            [
                "bench",
                "run",
                "synthetic",
                "--out",
                "/tmp/bench",
                "--retrieval-mode",
                "pseudo-embedding-rerank",
            ]
        )

        self.assertEqual(args.bench_command, "run")
        self.assertEqual(args.retrieval_mode, "pseudo-embedding-rerank")

        args = parser.parse_args(
            [
                "bench",
                "run",
                "synthetic",
                "--out",
                "/tmp/bench",
                "--retrieval-mode",
                "fts-multihop",
            ]
        )

        self.assertEqual(args.retrieval_mode, "fts-multihop")

        args = parser.parse_args(
            [
                "bench",
                "run",
                "synthetic",
                "--out",
                "/tmp/bench",
                "--retrieval-mode",
                "provider-embedding",
                "--retrieval-provider-config",
                "providers.json",
                "--allow-network-providers",
            ]
        )

        self.assertEqual(args.retrieval_mode, "provider-embedding")
        self.assertEqual(str(args.retrieval_provider_config), "providers.json")
        self.assertTrue(args.allow_network_providers)

        args = parser.parse_args(
            [
                "bench",
                "matrix",
                "longmemeval",
                "--dataset",
                "/tmp/longmemeval.jsonl",
                "--out",
                "/tmp/bench",
                "--context-budget-tokens",
                "200",
            ]
        )

        self.assertEqual(args.bench_command, "matrix")
        self.assertEqual(args.context_budget_tokens, 200)

    def test_fts_multihop_config_is_stable_and_only_enables_multi_hop(self):
        first = resolve_benchmark_retrieval_config("fts-multihop")
        second = resolve_benchmark_retrieval_config("fts-multihop")

        self.assertIn("fts-multihop", BENCHMARK_RETRIEVAL_MODES)
        self.assertEqual(benchmark_retrieval_config_hash(first), benchmark_retrieval_config_hash(second))
        self.assertEqual(first["schema"], BENCHMARK_RETRIEVAL_CONFIG_SCHEMA)
        self.assertEqual(first["store"], "sqlite-fts")
        self.assertTrue(first["multi_hop"]["enabled"])
        self.assertFalse(first["embedding"]["enabled"])
        self.assertFalse(first["reranker"]["enabled"])
        self.assertEqual(first["multi_hop"]["decomposer_id"], "zmem-local-query-decomposer-v1")

    def test_fts_adaptive_config_defers_multi_hop_activation_to_store_routing(self):
        first = resolve_benchmark_retrieval_config("fts-adaptive")
        second = resolve_benchmark_retrieval_config("fts-adaptive")

        self.assertIn("fts-adaptive", BENCHMARK_OPTIONAL_RETRIEVAL_MODES)
        self.assertIn("fts-adaptive", BENCHMARK_RETRIEVAL_RUN_MODES)
        self.assertNotIn("fts-adaptive", BENCHMARK_RETRIEVAL_MODES)
        self.assertEqual(benchmark_retrieval_config_hash(first), benchmark_retrieval_config_hash(second))
        self.assertEqual(first["routing"], {"strategy": "store-auto-v1"})
        self.assertNotIn("multi_hop", first)
        self.assertFalse(first["embedding"]["enabled"])
        self.assertFalse(first["reranker"]["enabled"])

        parser = build_parser()
        args = parser.parse_args(
            [
                "bench",
                "matrix",
                "locomo",
                "--dataset",
                "/tmp/locomo.jsonl",
                "--out",
                "/tmp/bench",
                "--mode",
                "fts-adaptive",
            ]
        )
        self.assertEqual(args.mode, "fts-adaptive")

    def test_dense_hybrid_benchmark_indexes_locally_and_records_proof(self):
        def fake_embed(provider_entry, texts, *, input_type="document", allow_model_download=False, **_kwargs):
            vectors = [[1.0, 0.0] for _text in texts]
            return EmbeddingProviderResult(
                provider_id=provider_entry.provider_id,
                model_id=provider_entry.model_id or "BAAI/bge-small-en-v1.5",
                dims=2,
                normalized=True,
                vectors=vectors,
                latency_ms=0.1,
                network_call=False,
                vector_hashes=[f"sha256:vector-{index}" for index, _vector in enumerate(vectors)],
                model_digest="sha256:test-model",
            )

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("zerker_memory.retrieval_providers.embed_texts", side_effect=fake_embed):
                result = run_synthetic_benchmark(
                    Path(tmp),
                    seed=0,
                    run_id="dense-hybrid-run",
                    retrieval_mode="dense-hybrid",
                )
            result_payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
            first_proof = result_payload["questions"][0]["retrieval_proof"]

        self.assertIn("dense-hybrid", BENCHMARK_OPTIONAL_RETRIEVAL_MODES)
        self.assertNotIn("dense-hybrid", BENCHMARK_RETRIEVAL_MODES)
        self.assertTrue(result_payload["retrieval_config"]["dense"]["enabled"])
        self.assertEqual(result_payload["retrieval_config"]["routing"], {"strategy": "store-auto-v1"})
        self.assertIsNone(result_payload["retrieval_provider_config"]["config_path"])
        self.assertEqual(result_payload["retrieval_reproducibility"], "model-hash-pinned-local")
        self.assertTrue(first_proof["dense_enabled"])
        self.assertFalse(first_proof["dense_fallback"])
        self.assertEqual(first_proof["dense_model_digest"], "sha256:test-model")
        self.assertEqual(first_proof["dense_fusion_strategy"], "reciprocal_rank_fusion_v1")
        self.assertEqual(
            first_proof["dense_conflict_resolution_boundary"],
            "dense-only-candidates-cannot-trigger-lexical-conflicts-v1",
        )
        self.assertTrue(first_proof["dense_lexical_recall_preserved"])
        self.assertFalse(first_proof["network_calls_enabled"])

    def test_fts_adaptive_benchmark_proof_records_store_auto_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "locomo-adaptive.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "question_id": "adaptive-owner-rollback",
                        "sample_id": "adaptive-dialog",
                        "split": "dev",
                        "category": "multi_hop",
                        "history": [
                            "Deployment approvals owner rollback policy notes.",
                            "Rollback policy is canary first for deployment approvals.",
                            "Deployment approver is Priya.",
                        ],
                        "question": "who owns deployment approvals rollback policy notes",
                        "answer": "Priya owns deployment approvals; rollback is canary first.",
                        "supporting_facts": [
                            "Rollback policy is canary first for deployment approvals.",
                            "Deployment approver is Priya.",
                        ],
                        "should_abstain": False,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_locomo_benchmark(
                Path(tmp) / "bench",
                dataset,
                "dev",
                run_id="adaptive",
                retrieval_mode="fts-adaptive",
                compact_artifacts=True,
            )
            payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
            question = payload["questions"][0]

            self.assertTrue(question["correct"])
            self.assertTrue(question["retrieval_proof"]["multi_hop_enabled"])
            self.assertTrue(question["retrieval_proof"]["multi_hop_auto_enabled"])
            self.assertEqual(
                question["retrieval_proof"]["multi_hop_activation_reason"],
                "fts-direct-subject-compound-query",
            )
            self.assertTrue(verify_benchmark_result(Path(result["result_path"]))["ok"])

    def test_fts_adaptive_benchmark_proof_records_store_auto_suppression(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "locomo-adaptive-suppressed.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "question_id": "adaptive-atlas-rollback",
                        "sample_id": "adaptive-atlas-dialog",
                        "split": "dev",
                        "category": "multi_hop",
                        "history": [
                            "Project Atlas owner Morgan rollback policy notes.",
                            "DeployWindow rollback policy is canary first for Project Atlas.",
                            "Project Atlas owner is Morgan.",
                        ],
                        "question": "Who is responsible for Project Atlas and its DeployWindow rollback plan?",
                        "answer": "Morgan is responsible; the rollback plan is canary first.",
                        "supporting_facts": [
                            "DeployWindow rollback policy is canary first for Project Atlas.",
                            "Project Atlas owner is Morgan.",
                        ],
                        "should_abstain": False,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_locomo_benchmark(
                Path(tmp) / "bench",
                dataset,
                "dev",
                run_id="adaptive-suppressed",
                retrieval_mode="fts-adaptive",
                compact_artifacts=True,
            )
            payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
            proof = payload["questions"][0]["retrieval_proof"]

            self.assertFalse(proof["multi_hop_enabled"])
            self.assertFalse(proof["multi_hop_auto_enabled"])
            self.assertTrue(proof["multi_hop_auto_evaluated"])
            self.assertIsNone(proof["multi_hop_activation_reason"])
            self.assertEqual(
                proof["multi_hop_suppression_reason"],
                "semantic-query-lacks-composition-signal",
            )
            self.assertTrue(verify_benchmark_result(Path(result["result_path"]))["ok"])

    def test_compact_locomo_repeats_use_stable_memory_ids_and_ranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "locomo-repeat.jsonl"
            support = "Caroline passed the adoption agency interviews last Friday."
            dataset.write_text(
                json.dumps(
                    {
                        "question_id": "repeatable-retrieval",
                        "sample_id": "repeatable-dialog",
                        "split": "dev",
                        "category": "temporal_reasoning",
                        "history": [
                            "Caroline prepared adoption paperwork earlier in the month.",
                            support,
                        ],
                        "question": "When did Caroline pass the adoption agency interviews?",
                        "answer": "last Friday",
                        "supporting_facts": [support],
                        "should_abstain": False,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            payloads = []
            for run_id in ("repeat-a", "repeat-b"):
                result = run_locomo_benchmark(
                    Path(tmp) / "bench",
                    dataset,
                    "dev",
                    run_id=run_id,
                    retrieval_mode="fts-adaptive",
                    compact_artifacts=True,
                )
                self.assertTrue(verify_benchmark_result(Path(result["result_path"]))["ok"])
                payloads.append(json.loads(Path(result["result_path"]).read_text(encoding="utf-8")))

            first = payloads[0]["questions"][0]
            second = payloads[1]["questions"][0]
            self.assertEqual(first["retrieved_memory_ids"], second["retrieved_memory_ids"])
            self.assertEqual(first["injected_memory_ids"], second["injected_memory_ids"])
            self.assertEqual(
                [memory["content_hash"] for memory in first["retrieved_memories"]],
                [memory["content_hash"] for memory in second["retrieved_memories"]],
            )
            self.assertEqual(
                first["retrieval_proof"]["candidate_rank_hash"],
                second["retrieval_proof"]["candidate_rank_hash"],
            )

    def test_synthetic_pseudo_embedding_mode_is_recorded_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_synthetic_benchmark(
                Path(tmp),
                seed=0,
                run_id="pseudo-run",
                retrieval_mode="pseudo-embedding",
            )
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            manifest = json.loads((run_dir / "benchmark-run.json").read_text(encoding="utf-8"))

            self.assertEqual(result_payload["retrieval_mode"], "pseudo-embedding")
            self.assertEqual(result_payload["retrieval_config_schema"], BENCHMARK_RETRIEVAL_CONFIG_SCHEMA)
            self.assertEqual(result_payload["retrieval_config"], manifest["retrieval_config"])
            self.assertEqual(result_payload["retrieval_config_hash"], manifest["retrieval_config_hash"])
            self.assertTrue(result_payload["retrieval_config"]["embedding"]["enabled"])
            self.assertFalse(result_payload["retrieval_config"]["reranker"]["enabled"])
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])
            for question in result_payload["questions"]:
                proof = question["retrieval_proof"]
                self.assertEqual(proof["mode"], "pseudo-embedding")
                self.assertEqual(proof["config_hash"], result_payload["retrieval_config_hash"])
                self.assertTrue(proof["embedding_enabled"])
                self.assertFalse(proof["reranker_enabled"])
                self.assertEqual(proof["embedding_model_id"], "zmem-pseudo-embedding-v1")

    def test_synthetic_run_records_redacted_provider_config_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "providers.json"
            config_path.write_text(json.dumps(self._provider_config()), encoding="utf-8")

            result = run_synthetic_benchmark(
                tmp_path / "bench",
                seed=0,
                run_id="provider-meta",
                retrieval_provider_config_path=config_path,
            )
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            manifest = json.loads((run_dir / "benchmark-run.json").read_text(encoding="utf-8"))
            provider_meta = result_payload["retrieval_provider_config"]

            self.assertEqual(provider_meta, manifest["retrieval_provider_config"])
            self.assertEqual(provider_meta, result["retrieval_provider_config"])
            self.assertEqual(provider_meta["schema"], "zerker.benchmark_retrieval_provider_config.v1")
            self.assertEqual(provider_meta["config_path"], str(config_path))
            self.assertTrue(provider_meta["config_hash"].startswith("sha256:"))
            self.assertFalse(provider_meta["network_calls_enabled"])
            self.assertEqual(
                provider_meta["redacted_config"]["config"]["embedding"]["providers"]["openai:text-embedding-3-small"][
                    "api_key"
                ],
                "<redacted>",
            )
            self.assertNotIn("sk-test-secret", json.dumps(result_payload))
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])

    def test_provider_embedding_benchmark_requires_network_allow_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "providers.json"
            config_path.write_text(json.dumps(self._provider_config(openai_enabled=True)), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "--allow-network-providers"):
                run_synthetic_benchmark(
                    Path(tmp) / "bench",
                    seed=0,
                    run_id="provider-no-allow",
                    retrieval_mode="provider-embedding",
                    retrieval_provider_config_path=config_path,
                )

    def test_provider_embedding_benchmark_records_observed_reproducibility_with_mocked_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "providers.json"
            config_path.write_text(json.dumps(self._provider_config(openai_enabled=True)), encoding="utf-8")
            provider_result = EmbeddingProviderResult(
                provider_id="openai:text-embedding-3-small",
                model_id="text-embedding-3-small",
                dims=2,
                normalized=True,
                vectors=[[1.0, 0.0], [1.0, 0.0], [0.2, 0.8], [0.1, 0.9]],
                latency_ms=7.5,
                network_call=True,
                vector_hashes=["sha256:q", "sha256:a", "sha256:b", "sha256:c"],
            )

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-secret"}):
                with mock.patch("zerker_memory.store.embed_texts", return_value=provider_result):
                    result = run_synthetic_benchmark(
                        tmp_path / "bench",
                        seed=0,
                        run_id="provider-observed",
                        retrieval_mode="provider-embedding",
                        retrieval_provider_config_path=config_path,
                        allow_network_providers=True,
                    )
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            first_question = result_payload["questions"][0]

            self.assertEqual(result_payload["retrieval_mode"], "provider-embedding")
            self.assertEqual(result_payload["retrieval_reproducibility"], "provider-observed")
            self.assertTrue(result_payload["retrieval_provider_config"]["network_calls_enabled"])
            self.assertTrue(first_question["retrieval_proof"]["network_calls_enabled"])
            self.assertEqual(first_question["retrieval_proof"]["retrieval_reproducibility"], "provider-observed")
            self.assertEqual(
                first_question["retrieval_proof"]["embedding_provider_id"],
                "openai:text-embedding-3-small",
            )
            self.assertNotIn("sk-test-secret", json.dumps(result_payload))
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])

    def test_synthetic_pseudo_embedding_rerank_records_receipt_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_synthetic_benchmark(
                Path(tmp),
                seed=0,
                run_id="rerank-run",
                retrieval_mode="pseudo-embedding-rerank",
            )
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            first_question = result_payload["questions"][0]
            question_payload = json.loads((run_dir / first_question["question_path"]).read_text(encoding="utf-8"))
            bundle_payload = json.loads((run_dir / first_question["receipt_bundle_path"]).read_text(encoding="utf-8"))
            receipt_retrieval = bundle_payload["receipt"]["retrieval"]
            proof = first_question["retrieval_proof"]

            self.assertEqual(result_payload["retrieval_mode"], "pseudo-embedding-rerank")
            self.assertEqual(proof, question_payload["proof"]["retrieval"])
            self.assertTrue(proof["embedding_enabled"])
            self.assertTrue(proof["reranker_enabled"])
            self.assertEqual(proof["embedding_model_id"], "zmem-pseudo-embedding-v1")
            self.assertEqual(proof["reranker_id"], "zmem-deterministic-rerank-v1")
            self.assertEqual(proof["receipt_retrieval_hash"], question_payload["retrieval_proof"]["receipt_retrieval_hash"])
            self.assertEqual(receipt_retrieval["embedding"]["model_id"], proof["embedding_model_id"])
            self.assertEqual(receipt_retrieval["reranker"]["reranker_id"], proof["reranker_id"])
            self.assertTrue(proof["candidate_rank_hash"])
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])

    def test_synthetic_fts_multihop_records_proof_fields_and_receipt_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_synthetic_benchmark(
                Path(tmp),
                seed=0,
                run_id="multihop-run",
                retrieval_mode="fts-multihop",
            )
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            first_question = result_payload["questions"][0]
            bundle_payload = json.loads((run_dir / first_question["receipt_bundle_path"]).read_text(encoding="utf-8"))
            receipt_retrieval = bundle_payload["receipt"]["retrieval"]
            proof = first_question["retrieval_proof"]

            self.assertEqual(result_payload["retrieval_mode"], "fts-multihop")
            self.assertTrue(proof["multi_hop_enabled"])
            self.assertEqual(proof["multi_hop_strategy"], "local_query_decomposition_v1")
            self.assertEqual(proof["decomposer_id"], "zmem-local-query-decomposer-v1")
            self.assertEqual(proof["decomposition_hash"], receipt_retrieval["multi_hop"]["decomposition_hash"])
            self.assertFalse(proof["embedding_enabled"])
            self.assertFalse(proof["reranker_enabled"])
            self.assertTrue(proof["candidate_rank_hash"])
            self.assertTrue(receipt_retrieval["multi_hop"]["enabled"])
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])

    def test_synthetic_richer_multihop_question_runs_and_records_decomposition_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_synthetic_benchmark(
                Path(tmp),
                seed=0,
                run_id="rich-multihop-run",
                retrieval_mode="fts-multihop",
            )
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            rich_question = next(
                question
                for question in result_payload["questions"]
                if question["question_id"] == "synthetic-multihop-kestrel-locker"
            )
            question_payload = json.loads((run_dir / rich_question["question_path"]).read_text(encoding="utf-8"))
            bundle_payload = json.loads((run_dir / rich_question["receipt_bundle_path"]).read_text(encoding="utf-8"))
            receipt_retrieval = bundle_payload["receipt"]["retrieval"]
            support_id = question_payload["expected_supporting_memory_ids"][0]
            support_candidate = next(
                candidate for candidate in receipt_retrieval["candidates"] if candidate["memory_id"] == support_id
            )

            self.assertTrue(rich_question["correct"])
            self.assertEqual(rich_question["category"], "multi_hop")
            self.assertIn(support_id, question_payload["injected_memory_ids"])
            self.assertTrue(rich_question["retrieval_proof"]["candidate_rank_hash"])
            self.assertTrue(rich_question["retrieval_proof"]["multi_hop_enabled"])
            self.assertEqual(
                rich_question["retrieval_proof"]["decomposition_hash"],
                receipt_retrieval["multi_hop"]["decomposition_hash"],
            )
            self.assertIsNone(support_candidate["pre_multi_hop_rank"])
            self.assertIsNotNone(support_candidate["introduced_by_subquery_id"])
            self.assertIn(support_id, receipt_retrieval["multi_hop"]["merge"]["introduced_candidate_ids"])
            self.assertTrue(receipt_retrieval["multi_hop"]["subqueries"])
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])

    def test_synthetic_richer_multihop_question_has_weak_fts_parent_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            fts = run_synthetic_benchmark(out, seed=0, run_id="fts", retrieval_mode="fts")
            multihop = run_synthetic_benchmark(out, seed=0, run_id="fts-mh", retrieval_mode="fts-multihop")
            fts_payload = json.loads(Path(fts["result_path"]).read_text(encoding="utf-8"))
            multihop_payload = json.loads(Path(multihop["result_path"]).read_text(encoding="utf-8"))
            fts_question = next(
                question
                for question in fts_payload["questions"]
                if question["question_id"] == "synthetic-multihop-kestrel-locker"
            )
            multihop_question = next(
                question
                for question in multihop_payload["questions"]
                if question["question_id"] == "synthetic-multihop-kestrel-locker"
            )

            self.assertFalse(fts_question["correct"])
            self.assertTrue(multihop_question["correct"])
            self.assertEqual(fts_question["score"], 0.0)
            self.assertEqual(multihop_question["score"], 1.0)

    def test_compare_surfaces_retrieval_modes_without_dataset_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            fts = run_synthetic_benchmark(out, seed=0, run_id="fts", retrieval_mode="fts")
            pseudo = run_synthetic_benchmark(out, seed=0, run_id="pseudo", retrieval_mode="pseudo-embedding")
            rerank = run_synthetic_benchmark(
                out,
                seed=0,
                run_id="rerank",
                retrieval_mode="pseudo-embedding-rerank",
            )

            comparison = compare_benchmark_results(
                [Path(fts["result_path"]), Path(pseudo["result_path"]), Path(rerank["result_path"])]
            )

            self.assertTrue(comparison["ok"])
            self.assertEqual(
                [run["retrieval_mode"] for run in comparison["runs"]],
                ["fts", "pseudo-embedding", "pseudo-embedding-rerank"],
            )
            self.assertFalse(comparison["compatibility"]["same_retrieval_mode"])
            self.assertFalse(comparison["compatibility"]["same_retrieval_config_hash"])
            self.assertEqual(comparison["compatibility"]["comparison_axis"], "retrieval_mode")
            self.assertEqual(comparison["compatibility"]["warnings"], [])

    def test_compare_surfaces_fts_vs_fts_multihop(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            fts = run_synthetic_benchmark(out, seed=0, run_id="fts", retrieval_mode="fts")
            multihop = run_synthetic_benchmark(out, seed=0, run_id="fts-mh", retrieval_mode="fts-multihop")

            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])

            self.assertTrue(comparison["ok"])
            self.assertEqual([run["retrieval_mode"] for run in comparison["runs"]], ["fts", "fts-multihop"])
            self.assertFalse(comparison["compatibility"]["same_retrieval_mode"])
            self.assertEqual(comparison["compatibility"]["comparison_axis"], "retrieval_mode")

    def test_compare_reports_legacy_null_artifact_paths_as_verification_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            legacy = run_synthetic_benchmark(out, seed=0, run_id="legacy", retrieval_mode="fts")
            current = run_synthetic_benchmark(out, seed=0, run_id="current", retrieval_mode="fts-multihop")
            legacy_path = Path(legacy["result_path"])
            legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
            legacy_payload["paths"]["snapshots"]["after"] = None
            legacy_payload["paths"]["report"] = None
            legacy_payload["proof"]["artifact_hashes"]["snapshots"]["after"] = None
            legacy_payload["proof"]["artifact_hashes"]["report"] = None
            legacy_payload["proof"]["artifact_hashes"]["receipt_bundles"] = {}
            legacy_payload["proof"]["receipt_bundles_omitted"] = True
            for question in legacy_payload["questions"]:
                (legacy_path.parent / question["receipt_bundle_path"]).unlink()
            legacy_payload["result_hash"] = sha256_text(
                stable_json({key: value for key, value in legacy_payload.items() if key != "result_hash"})
            )
            legacy_path.write_text(json.dumps(legacy_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            comparison = compare_benchmark_results([legacy_path, Path(current["result_path"])])

            self.assertFalse(comparison["ok"])
            self.assertEqual(comparison["proof"]["verification_status"], "failed")
            self.assertIn(
                "aggregate_merkle_root",
                comparison["proof"]["verification_failures"][0]["failed_checks"],
            )

    def test_compare_preserves_question_level_evidence_and_memory_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            fts = run_synthetic_benchmark(out, seed=0, run_id="fts", retrieval_mode="fts")
            multihop = run_synthetic_benchmark(out, seed=0, run_id="fts-mh", retrieval_mode="fts-multihop")

            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            question = next(
                question
                for question in comparison["questions"]
                if question["question_id"] == "synthetic-multihop-kestrel-locker"
            )

            self.assertEqual(len(question["runs"]), 2)
            self.assertEqual([run["retrieval_mode"] for run in question["runs"]], ["fts", "fts-multihop"])
            self.assertTrue(question["runs"][0]["artifacts"]["question_hash"])
            self.assertTrue(question["runs"][0]["proof"]["receipt_merkle_root"])
            self.assertIsInstance(question["runs"][0]["retrieved_memory_ids"], list)
            self.assertIsInstance(question["runs"][0]["injected_memory_ids"], list)
            self.assertIsInstance(question["runs"][0]["withheld_memory_ids"], list)
            self.assertIsInstance(question["runs"][0]["retrieved_memories"], list)
            self.assertIsInstance(question["runs"][0]["injected_memories"], list)
            self.assertIsInstance(question["runs"][0]["withheld_memories"], list)
            self.assertIn("content", question["runs"][0]["retrieved_memories"][0])
            self.assertIn("final_answer", question["runs"][0])
            self.assertIn("outcome_reason", question["runs"][0])
            self.assertIn("supporting_evidence_status", question["runs"][0])
            self.assertTrue(question["deltas"][0]["correct_changed"])
            self.assertTrue(question["deltas"][0]["final_answer_changed"])
            self.assertTrue(question["deltas"][0]["outcome_reason_changed"])
            self.assertEqual(
                question["deltas"][0]["baseline_final_answer"],
                "I don't know",
            )
            self.assertEqual(
                question["deltas"][0]["final_answer"],
                "Kestrel Node locker code is 4182.",
            )
            self.assertEqual(question["deltas"][0]["outcome_reason"], "correct_supported_answer")
            self.assertTrue(question["deltas"][0]["retrieved_memories_added"])
            self.assertIn("locker code is 4182", question["deltas"][0]["retrieved_memories_added"][0]["content"])

    def test_compare_repeat_runs_have_no_memory_identity_or_content_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            first = run_synthetic_benchmark(out, seed=0, run_id="same-a", retrieval_mode="fts")
            second = run_synthetic_benchmark(out, seed=0, run_id="same-b", retrieval_mode="fts")

            comparison = compare_benchmark_results([Path(first["result_path"]), Path(second["result_path"])])
            question = next(
                question
                for question in comparison["questions"]
                if question["question_id"] == "synthetic-policy-recall"
            )

            self.assertEqual(question["deltas"][0]["retrieved_memory_ids_added"], [])
            self.assertEqual(question["deltas"][0]["retrieved_memory_ids_removed"], [])
            self.assertEqual(question["deltas"][0]["retrieved_memories_added"], [])
            self.assertEqual(question["deltas"][0]["retrieved_memories_removed"], [])
            self.assertEqual(question["deltas"][0]["injected_memories_added"], [])
            self.assertEqual(question["deltas"][0]["injected_memories_removed"], [])

    def test_compare_surfaces_category_level_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            fts = run_synthetic_benchmark(out, seed=0, run_id="fts", retrieval_mode="fts")
            multihop = run_synthetic_benchmark(out, seed=0, run_id="fts-mh", retrieval_mode="fts-multihop")

            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            multi_hop = next(category for category in comparison["categories"] if category["category"] == "multi_hop")

            self.assertEqual([run["retrieval_mode"] for run in multi_hop["runs"]], ["fts", "fts-multihop"])
            self.assertEqual(multi_hop["runs"][0]["accuracy"], 0.0)
            self.assertEqual(multi_hop["runs"][1]["accuracy"], 1.0)
            self.assertEqual(multi_hop["deltas"][0]["accuracy_delta"], 1.0)
            self.assertEqual(multi_hop["deltas"][0]["passed_delta"], 1)
            self.assertEqual(multi_hop["deltas"][0]["failed_delta"], -1)
            self.assertIn("p95_retrieval_latency_ms", multi_hop["runs"][0])
            self.assertIn("total_tokens", multi_hop["runs"][0])
            self.assertIn("retrieved_memory_count", multi_hop["runs"][0])
            self.assertIn("p95_retrieval_latency_ms_delta", multi_hop["deltas"][0])
            self.assertIn("total_tokens_delta", multi_hop["deltas"][0])
            self.assertIn("retrieved_memory_count_delta", multi_hop["deltas"][0])

    def test_benchmark_retrieval_config_hash_is_stable(self):
        first = resolve_benchmark_retrieval_config("pseudo-embedding", {"split": "dev"})
        second = resolve_benchmark_retrieval_config("pseudo-embedding", {"split": "dev"})
        rerank = resolve_benchmark_retrieval_config("pseudo-embedding-rerank", {"split": "dev"})

        self.assertEqual(benchmark_retrieval_config_hash(first), benchmark_retrieval_config_hash(second))
        self.assertNotEqual(benchmark_retrieval_config_hash(first), benchmark_retrieval_config_hash(rerank))
        self.assertEqual(first["schema"], BENCHMARK_RETRIEVAL_CONFIG_SCHEMA)

    def test_parser_accepts_longmemeval_dataset_and_split(self):
        parser = build_parser()

        args = parser.parse_args(
            [
                "bench",
                "run",
                "longmemeval",
                "--dataset",
                "/tmp/local.jsonl",
                "--split",
                "small",
                "--out",
                "/tmp/bench",
                "--seed",
                "7",
                "--run-id",
                "abc",
            ]
        )

        self.assertEqual(args.command, "bench")
        self.assertEqual(args.bench_command, "run")
        self.assertEqual(args.benchmark, "longmemeval")
        self.assertEqual(str(args.dataset), "/tmp/local.jsonl")
        self.assertEqual(args.split, "small")
        self.assertEqual(args.seed, 7)

        args = parser.parse_args(
            [
                "bench",
                "run",
                "locomo",
                "--dataset",
                "/tmp/local.jsonl",
                "--split",
                "dev",
                "--out",
                "/tmp/bench",
                "--seed",
                "3",
                "--run-id",
                "locomo-abc",
            ]
        )

        self.assertEqual(args.benchmark, "locomo")
        self.assertEqual(str(args.dataset), "/tmp/local.jsonl")
        self.assertEqual(args.split, "dev")
        self.assertEqual(args.seed, 3)

    def test_cli_runs_and_verifies_synthetic_benchmark(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"

            run = self._main_json(["bench", "run", "synthetic", "--out", str(out), "--seed", "0", "--run-id", "cli-run"])
            self.assertTrue(run["ok"])

            verify = self._main_json(["bench", "verify", str(out / "cli-run" / "benchmark-result.json")])
            self.assertTrue(verify["ok"])

    def test_compare_two_synthetic_runs_returns_stable_proof_backed_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            first = run_synthetic_benchmark(out, seed=0, run_id="compare-a")
            second = run_synthetic_benchmark(out, seed=1, run_id="compare-b")
            first_path = Path(first["result_path"])
            second_path = Path(second["result_path"])

            comparison = compare_benchmark_results([first_path, second_path])
            comparison_again = compare_benchmark_results([first_path, second_path])

            self.assertEqual(comparison["schema"], BENCHMARK_COMPARISON_SCHEMA)
            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison["result_count"], 2)
            self.assertEqual(len(comparison["runs"]), 2)
            self.assertEqual(len(comparison["deltas"]), 1)
            self.assertEqual(comparison["deltas"][0]["baseline_index"], 0)
            self.assertEqual(comparison["deltas"][0]["index"], 1)
            self.assertEqual(comparison["deltas"][0]["metrics"]["accuracy"]["delta"], 0.0)
            self.assertEqual(
                comparison["proof"]["input_aggregate_roots"],
                [first["proof"]["aggregate_merkle_root"], second["proof"]["aggregate_merkle_root"]],
            )
            self.assertEqual(comparison["proof"]["verification_status"], "ok")
            self.assertEqual(comparison["comparison_hash"], comparison_again["comparison_hash"])

    def test_comparison_question_summary_counts_stable_wins_and_misses(self):
        question_summary = _comparison_question_summary(
            [
                {
                    "question_id": "stable-win",
                    "runs": [
                        {"correct": True, "final_answer": "A", "outcome_reason": "correct_supported_answer"},
                        {"correct": True, "final_answer": "A", "outcome_reason": "correct_supported_answer"},
                    ],
                    "deltas": [{"correct_changed": False, "final_answer_changed": False, "outcome_reason_changed": False}],
                },
                {
                    "question_id": "stable-miss",
                    "runs": [
                        {"correct": False, "final_answer": "none", "outcome_reason": "false_abstention_missing_injection"},
                        {"correct": False, "final_answer": "none", "outcome_reason": "false_abstention_missing_injection"},
                    ],
                    "deltas": [{"correct_changed": False, "final_answer_changed": False, "outcome_reason_changed": False}],
                },
                {
                    "question_id": "visible-delta",
                    "runs": [
                        {"correct": False, "final_answer": "old", "outcome_reason": "wrong_supported_answer"},
                        {"correct": True, "final_answer": "new", "outcome_reason": "correct_supported_answer"},
                    ],
                    "deltas": [{"correct_changed": True, "final_answer_changed": True, "outcome_reason_changed": True}],
                },
            ]
        )

        self.assertEqual(question_summary["question_count"], 3)
        self.assertEqual(question_summary["visible_delta_question_count"], 1)
        self.assertEqual(question_summary["stable_misses"]["count"], 1)
        self.assertEqual(question_summary["stable_misses"]["question_ids"], ["stable-miss"])
        self.assertEqual(question_summary["stable_wins"]["count"], 1)
        self.assertEqual(question_summary["stable_wins"]["question_ids"], ["stable-win"])

    def test_cli_compare_returns_json_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            run_synthetic_benchmark(out, seed=0, run_id="cli-compare-a")
            run_synthetic_benchmark(out, seed=1, run_id="cli-compare-b")

            comparison = self._main_json(
                [
                    "bench",
                    "compare",
                    str(out / "cli-compare-a" / "benchmark-result.json"),
                    str(out / "cli-compare-b" / "benchmark-result.json"),
                ]
            )

            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison["result_count"], 2)

    def test_compare_out_writes_standalone_comparison_json_report_and_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            compare_out = Path(tmp) / "comparison"
            run_synthetic_benchmark(out, seed=0, run_id="compare-out-a", retrieval_mode="fts")
            run_synthetic_benchmark(out, seed=0, run_id="compare-out-b", retrieval_mode="fts-multihop")

            comparison = self._main_json(
                [
                    "bench",
                    "compare",
                    str(out / "compare-out-a" / "benchmark-result.json"),
                    str(out / "compare-out-b" / "benchmark-result.json"),
                    "--out",
                    str(compare_out),
                ]
            )

            comparison_path = compare_out / "benchmark-comparison.json"
            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison["comparison_path"], str(comparison_path))
            self.assertTrue(comparison_path.exists())
            self.assertTrue((compare_out / "comparison-report.md").exists())
            self.assertTrue((compare_out / "comparison-dashboard.html").exists())

    def test_cli_verify_accepts_comparison_json_and_matrix_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="verify-matrix")
            matrix_dir = Path(matrix["matrix_dir"])

            comparison_verify = self._main_json(["bench", "verify", str(matrix_dir / "benchmark-comparison.json")])
            matrix_verify = self._main_json(["bench", "verify", str(matrix_dir)])

            self.assertTrue(comparison_verify["ok"])
            self.assertEqual(comparison_verify["artifact_type"], "comparison")
            self.assertTrue(matrix_verify["ok"])
            self.assertEqual(matrix_verify["artifact_type"], "matrix")

    def test_verify_accepts_matrix_with_cwd_relative_stored_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous_cwd = Path.cwd()
            os.chdir(tmp)
            try:
                matrix = run_benchmark_matrix(Path("bench"), "synthetic", seed=0, run_id="relative-matrix")
                matrix_verify = verify_benchmark_artifact(Path(matrix["matrix_path"]))
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(matrix_verify["ok"])
            self.assertEqual(matrix_verify["artifact_type"], "matrix")

    def test_synthetic_matrix_artifacts_store_relative_paths_and_reopen_from_another_cwd(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            os.chdir(tmp_path)
            try:
                matrix = run_benchmark_matrix(Path("bench"), "synthetic", seed=0, run_id="relative-matrix-artifact")
            finally:
                os.chdir(previous_cwd)

            matrix_path = Path(matrix["matrix_path"])
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            stored_result_paths = [run["result_path"] for run in matrix_payload["mode_runs"]]
            verify = verify_benchmark_artifact(matrix_path)
            report = render_benchmark_report(matrix_path)
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")
            mode_proofs = self._comparison_run_proof_hops(matrix_payload["comparison"])

            self.assertEqual(matrix_payload["matrix_path"], "benchmark-matrix.json")
            self.assertEqual(matrix_payload["comparison_path"], "benchmark-comparison.json")
            self.assertEqual(matrix_payload["report_path"], "matrix-report.md")
            self.assertEqual(
                stored_result_paths,
                [f"{mode}/benchmark-result.json" for mode in BENCHMARK_RETRIEVAL_MODES],
            )
            self.assertEqual(
                matrix_payload["proof"]["input_result_paths"],
                [f"{mode}/benchmark-result.json" for mode in BENCHMARK_RETRIEVAL_MODES],
            )
            self.assertTrue(all(not Path(path).is_absolute() for path in stored_result_paths))
            self.assertTrue(verify["ok"])
            self.assertEqual(report["artifact_type"], "matrix")
            self.assertTrue(dashboard["ok"])
            self.assertTrue(page["ok"])
            self.assertIn("benchmark-comparison.json", report_text)
            self.assertIn("fts/benchmark-result.json", report_text)
            self.assertIn("benchmark-comparison.json", dashboard_html)
            self.assertIn("benchmark-matrix.json", dashboard_html)
            self.assertIn("benchmark-matrix.json", page_html)
            self._assert_rendered_mode_proof_hops(mode_proofs, dashboard_html)
            self._assert_rendered_mode_proof_hops(mode_proofs, page_html)

    def test_local_dataset_comparison_artifacts_store_relative_run_paths_and_reopen_from_another_cwd(self):
        previous_cwd = Path.cwd()
        cases = (
            (
                "longmemeval",
                self._write_longmemeval_jsonl,
                run_longmemeval_benchmark,
                "small",
            ),
            (
                "locomo",
                self._write_locomo_jsonl,
                run_locomo_benchmark,
                "dev",
            ),
        )

        for benchmark, dataset_writer, runner, split in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                comparison_artifact_path = tmp_path / "comparison" / "benchmark-comparison.json"

                os.chdir(tmp_path)
                try:
                    fts = runner(
                        Path("bench"),
                        dataset,
                        split,
                        seed=0,
                        run_id=f"{benchmark}-relative-a",
                        retrieval_mode="fts",
                    )
                    multihop = runner(
                        Path("bench"),
                        dataset,
                        split,
                        seed=0,
                        run_id=f"{benchmark}-relative-b",
                        retrieval_mode="fts-multihop",
                    )
                    comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
                    write_benchmark_comparison_artifacts(comparison, Path("comparison"))
                finally:
                    os.chdir(previous_cwd)

                comparison_payload = json.loads(comparison_artifact_path.read_text(encoding="utf-8"))
                stored_paths = [run["path"] for run in comparison_payload["runs"]]
                verify = verify_benchmark_artifact(comparison_artifact_path)
                report = render_benchmark_report(comparison_artifact_path)
                dashboard = render_benchmark_dashboard(comparison_artifact_path)
                report_text = Path(report["report_path"]).read_text(encoding="utf-8")
                dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
                proof_hops = self._comparison_run_proof_hops(comparison_payload)

                self.assertEqual(stored_paths, [f"../bench/{benchmark}-relative-a/benchmark-result.json", f"../bench/{benchmark}-relative-b/benchmark-result.json"])
                self.assertTrue(all(not Path(path).is_absolute() for path in stored_paths))
                self.assertTrue(verify["ok"])
                self.assertEqual(verify["artifact_type"], "comparison")
                self.assertEqual(report["artifact_type"], "comparison")
                self.assertTrue(dashboard["ok"])
                self.assertEqual(dashboard["artifact_type"], "comparison")
                self.assertEqual(report["summary"]["question_summary"], comparison_payload["question_summary"])
                self.assertEqual(dashboard["summary"]["question_summary"], comparison_payload["question_summary"])
                self.assertIn(str(dataset), report_text)
                self.assertIn(str(dataset), dashboard_html)
                self.assertIn(split, report_text)
                self.assertIn(split, dashboard_html)
                self._assert_rendered_comparison_proof_hops(proof_hops, report_text)
                self._assert_rendered_comparison_proof_hops(proof_hops, dashboard_html)

    def test_local_dataset_matrix_artifacts_store_relative_paths_and_reopen_from_another_cwd(self):
        previous_cwd = Path.cwd()
        cases = (
            (
                "longmemeval",
                self._write_longmemeval_jsonl,
                "small",
            ),
            (
                "locomo",
                self._write_locomo_jsonl,
                "dev",
            ),
        )

        for benchmark, dataset_writer, split in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)

                os.chdir(tmp_path)
                try:
                    matrix = run_benchmark_matrix(
                        Path("bench"),
                        benchmark,
                        dataset=dataset,
                        split=split,
                        seed=0,
                        run_id=f"{benchmark}-relative-matrix",
                    )
                finally:
                    os.chdir(previous_cwd)

                matrix_path = Path(matrix["matrix_path"])
                matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
                stored_result_paths = [run["result_path"] for run in matrix_payload["mode_runs"]]
                stored_run_dirs = [run["run_dir"] for run in matrix_payload["mode_runs"]]
                stored_report_paths = [run["report_path"] for run in matrix_payload["mode_runs"]]
                verify = verify_benchmark_artifact(matrix_path)
                report = render_benchmark_report(matrix_path)
                dashboard = render_benchmark_dashboard(matrix_path)
                page = render_public_benchmark_page(matrix_path)
                report_text = Path(report["report_path"]).read_text(encoding="utf-8")
                dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
                page_html = Path(page["page_path"]).read_text(encoding="utf-8")

                self.assertEqual(matrix_payload["comparison_path"], "benchmark-comparison.json")
                self.assertEqual(matrix_payload["report_path"], "matrix-report.md")
                self.assertEqual(
                    matrix_payload["proof"]["input_result_paths"],
                    [f"{mode}/benchmark-result.json" for mode in BENCHMARK_RETRIEVAL_MODES],
                )
                self.assertEqual(
                    stored_result_paths,
                    [f"{mode}/benchmark-result.json" for mode in BENCHMARK_RETRIEVAL_MODES],
                )
                self.assertEqual(stored_run_dirs, list(BENCHMARK_RETRIEVAL_MODES))
                self.assertEqual(
                    stored_report_paths,
                    [f"{mode}/report.md" for mode in BENCHMARK_RETRIEVAL_MODES],
                )
                self.assertTrue(all(not Path(path).is_absolute() for path in stored_result_paths))
                self.assertTrue(all(not Path(path).is_absolute() for path in stored_run_dirs))
                self.assertTrue(all(not Path(path).is_absolute() for path in stored_report_paths))
                self.assertTrue(verify["ok"])
                self.assertEqual(verify["artifact_type"], "matrix")
                self.assertEqual(report["artifact_type"], "matrix")
                self.assertTrue(dashboard["ok"])
                self.assertTrue(page["ok"])
                self.assertIn(str(dataset), report_text)
                self.assertIn(str(dataset), dashboard_html)
                self.assertIn(str(dataset), page_html)
                self.assertIn(split, report_text)
                self.assertIn(split, dashboard_html)
                self.assertIn(split, page_html)
                self.assertIn("benchmark-comparison.json", report_text)
                self.assertIn("benchmark-comparison.json", dashboard_html)
                self.assertIn("benchmark-matrix.json", page_html)

    def test_longmemeval_matrix_comparison_artifacts_preserve_mode_level_proof_hops(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            first = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-matrix-a",
            )
            second = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-matrix-b",
            )

            comparison = compare_benchmark_matrices([Path(first["matrix_path"]), Path(second["matrix_path"])])
            artifacts = write_benchmark_matrix_comparison_artifacts(comparison, compare_out)
            comparison_path = Path(artifacts["comparison_path"])
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            verify = verify_benchmark_artifact(comparison_path)
            report = render_benchmark_report(comparison_path)
            dashboard = render_benchmark_dashboard(comparison_path)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertEqual(comparison_payload["schema"], BENCHMARK_MATRIX_COMPARISON_SCHEMA)
            self.assertTrue(comparison_payload["ok"])
            self.assertEqual(comparison_payload["matrix_count"], 2)
            self.assertEqual(comparison_payload["mode_count"], len(BENCHMARK_RETRIEVAL_MODES))
            self.assertEqual(
                comparison_payload["compatibility"]["compared_retrieval_modes"],
                list(BENCHMARK_RETRIEVAL_MODES),
            )
            self.assertEqual(comparison_payload["target"]["benchmark"], "longmemeval")
            self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
            self.assertEqual(comparison_payload["target"]["split"], "small")
            self.assertTrue(verify["ok"])
            self.assertEqual(verify["artifact_type"], "matrix_comparison")
            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertEqual(dashboard["summary"]["benchmark"], "longmemeval")
            self.assertEqual(dashboard["summary"]["dataset"], str(dataset))
            self.assertEqual(
                [mode["retrieval_mode"] for mode in dashboard["summary"]["mode_comparisons"]],
                list(BENCHMARK_RETRIEVAL_MODES),
            )
            self.assertIn("## Compared Matrices", report_text)
            self.assertIn("## Retrieval Modes", report_text)
            self.assertIn("longmemeval-matrix-a", report_text)
            self.assertIn("longmemeval-matrix-b", report_text)
            self.assertIn("Retrieval Modes", dashboard_html)
            self.assertIn("longmemeval-matrix-a", dashboard_html)
            self.assertIn("longmemeval-matrix-b", dashboard_html)
            for mode_comparison in comparison_payload["mode_comparisons"]:
                self.assertEqual(len(mode_comparison["matrix_runs"]), 2)
                first_mode_run = mode_comparison["matrix_runs"][0]
                second_mode_run = mode_comparison["matrix_runs"][1]
                self.assertEqual(first_mode_run["retrieval_mode"], mode_comparison["retrieval_mode"])
                self.assertEqual(second_mode_run["retrieval_mode"], mode_comparison["retrieval_mode"])
                self.assertTrue(first_mode_run["result_hash"])
                self.assertTrue(second_mode_run["result_hash"])
                self.assertTrue(first_mode_run["aggregate_merkle_root"])
                self.assertTrue(second_mode_run["aggregate_merkle_root"])
                self.assertEqual(mode_comparison["proof"]["verification_status"], "ok")

    def test_cli_compare_matrices_summary_only_surfaces_mode_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            first = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="summary-matrix-a",
            )
            second = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="summary-matrix-b",
            )

            output = self._main_text(
                [
                    "bench",
                    "compare-matrices",
                    str(first["matrix_path"]),
                    str(second["matrix_path"]),
                    "--summary-only",
                ]
            )

            self.assertIn("Benchmark matrix comparison", output)
            self.assertIn("Matrix count: 2", output)
            self.assertIn("Benchmark: longmemeval", output)
            self.assertIn("Dataset: ", output)
            self.assertIn("Mode comparison fts:", output)
            self.assertIn("Mode comparison fts-multihop:", output)

    def test_cli_compare_matrices_summary_only_surfaces_richer_local_dataset_question_summaries(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                "analysis",
                [
                    "Mode comparison fts: verification=ok visible_deltas=0 stable_wins=8 stable_misses=0",
                    "Mode comparison fts-multihop: verification=ok visible_deltas=0 stable_wins=8 stable_misses=0",
                    "Mode comparison pseudo-embedding: verification=ok visible_deltas=0 stable_wins=8 stable_misses=0",
                    "Mode comparison pseudo-embedding-rerank: verification=ok visible_deltas=0 stable_wins=8 stable_misses=0",
                ],
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                "dev",
                [
                    "Mode comparison fts: verification=ok visible_deltas=0 stable_wins=4 stable_misses=1",
                    "Mode comparison fts-multihop: verification=ok visible_deltas=0 stable_wins=5 stable_misses=0",
                    "Mode comparison pseudo-embedding: verification=ok visible_deltas=0 stable_wins=4 stable_misses=1",
                    "Mode comparison pseudo-embedding-rerank: verification=ok visible_deltas=0 stable_wins=4 stable_misses=1",
                ],
            ),
        )

        for benchmark, dataset_writer, split, expected_mode_lines in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                first = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-matrix-a",
                )
                second = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-matrix-b",
                )

                output = self._main_text(
                    [
                        "bench",
                        "compare-matrices",
                        str(first["matrix_path"]),
                        str(second["matrix_path"]),
                        "--summary-only",
                    ]
                )

                self.assertIn("Benchmark matrix comparison", output)
                self.assertIn("Verification: ok", output)
                self.assertIn("Matrix count: 2", output)
                self.assertIn(f"Benchmark: {benchmark}", output)
                self.assertIn(f"Dataset: {dataset}", output)
                self.assertIn(f"Split: {split}", output)
                for expected_mode_line in expected_mode_lines:
                    self.assertIn(expected_mode_line, output)

    def test_cli_compare_matrices_summary_only_surfaces_budget_context_and_delta_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            first = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="summary-matrix-budget-a",
                context_budget_tokens=200,
            )
            second = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="summary-matrix-budget-b",
                context_budget_tokens=200,
            )
            comparison_path = tmp_path / "matrix-comparison-budget" / "benchmark-matrix-comparison.json"

            output = self._main_text(
                [
                    "bench",
                    "compare-matrices",
                    str(first["matrix_path"]),
                    str(second["matrix_path"]),
                    "--out",
                    str(comparison_path),
                    "--summary-only",
                ]
            )

            persisted_comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            anchor_mode = next(
                mode for mode in persisted_comparison["mode_comparisons"] if mode["retrieval_mode"] == "fts"
            )
            budget_context_ids = [
                question["question_id"]
                for question in anchor_mode["comparison"]["questions"]
                if any(run.get("budget_dropped_memories") for run in question.get("runs", []))
            ]
            expected_memory_count_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieved_memory_count_delta": delta.get("retrieved_memory_count_delta"),
                    "injected_memory_count_delta": delta.get("injected_memory_count_delta"),
                    "withheld_memory_count_delta": delta.get("withheld_memory_count_delta"),
                }
                for question in anchor_mode["comparison"]["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieved_memory_count_delta",
                        "injected_memory_count_delta",
                        "withheld_memory_count_delta",
                    )
                )
            ]
            expected_efficiency_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieval_latency_ms_delta": delta.get("retrieval_latency_ms_delta"),
                    "total_tokens_delta": delta.get("total_tokens_delta"),
                }
                for question in anchor_mode["comparison"]["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieval_latency_ms_delta",
                        "total_tokens_delta",
                    )
                )
            ]

            self.assertIn("Benchmark matrix comparison", output)
            self.assertIn("Verification: ok", output)
            self.assertIn("Matrix count: 2", output)
            self.assertIn("Benchmark: locomo", output)
            self.assertIn(f"Dataset: {dataset}", output)
            self.assertIn("Split: dev", output)
            self.assertIn("Context budget tokens: 200", output)
            self.assertIn(
                "Mode comparison fts budget context ids: " + ", ".join(budget_context_ids),
                output,
            )
            for delta in expected_memory_count_deltas:
                self.assertIn(
                    "Mode comparison fts memory count delta "
                    f"{delta['question_id']}: "
                    f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                    f"injected={delta['injected_memory_count_delta']:+d} "
                    f"withheld={delta['withheld_memory_count_delta']:+d}",
                    output,
                )
            for delta in expected_efficiency_deltas:
                self.assertIn(
                    "Mode comparison fts efficiency delta "
                    f"{delta['question_id']}: retrieval_latency_ms=",
                    output,
                )
            for matrix_run in anchor_mode["matrix_runs"]:
                self.assertIn(
                    "Mode comparison fts proof hop "
                    f"{matrix_run['matrix_run_id']}: result_hash={matrix_run['result_hash']} "
                    f"aggregate_merkle_root={matrix_run['aggregate_merkle_root']}",
                    output,
                )
            self.assertIn(f"Comparison JSON: {comparison_path}", output)
            self.assertIn("Report: ", output)
            self.assertIn("Dashboard: ", output)

    def test_cli_matrix_comparison_verify_report_and_dashboard_summary_only_surface_delta_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "matrix-comparison"
            first = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="verify-matrix-budget-a",
                context_budget_tokens=200,
            )
            second = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="verify-matrix-budget-b",
                context_budget_tokens=200,
            )
            comparison = self._main_json(
                [
                    "bench",
                    "compare-matrices",
                    str(first["matrix_path"]),
                    str(second["matrix_path"]),
                    "--out",
                    str(compare_out),
                ]
            )
            comparison_path = Path(comparison["comparison_path"])
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            anchor_mode = next(
                mode for mode in comparison_payload["mode_comparisons"] if mode["retrieval_mode"] == "fts"
            )
            budget_context_ids = [
                question["question_id"]
                for question in anchor_mode["comparison"]["questions"]
                if any(run.get("budget_dropped_memories") for run in question.get("runs", []))
            ]
            expected_memory_count_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieved_memory_count_delta": delta.get("retrieved_memory_count_delta"),
                    "injected_memory_count_delta": delta.get("injected_memory_count_delta"),
                    "withheld_memory_count_delta": delta.get("withheld_memory_count_delta"),
                }
                for question in anchor_mode["comparison"]["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieved_memory_count_delta",
                        "injected_memory_count_delta",
                        "withheld_memory_count_delta",
                    )
                )
            ]
            expected_efficiency_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieval_latency_ms_delta": delta.get("retrieval_latency_ms_delta"),
                    "total_tokens_delta": delta.get("total_tokens_delta"),
                }
                for question in anchor_mode["comparison"]["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieval_latency_ms_delta",
                        "total_tokens_delta",
                    )
                )
            ]

            verify_output = self._main_text(["bench", "verify", str(comparison_path), "--summary-only"])
            report_output = self._main_text(["bench", "report", str(comparison_path), "--summary-only"])
            dashboard_output = self._main_text(["bench", "dashboard", str(comparison_path), "--summary-only"])

            for output in (verify_output, report_output, dashboard_output):
                self.assertIn("Artifact: matrix_comparison", output)
                self.assertIn("Verification: ok", output)
                self.assertIn("Context budget tokens: 200", output)
                self.assertIn(
                    "Mode comparison fts budget context ids: " + ", ".join(budget_context_ids),
                    output,
                )
                for delta in expected_memory_count_deltas:
                    self.assertIn(
                        "Mode comparison fts memory count delta "
                        f"{delta['question_id']}: "
                        f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                        f"injected={delta['injected_memory_count_delta']:+d} "
                        f"withheld={delta['withheld_memory_count_delta']:+d}",
                        output,
                    )
                for delta in expected_efficiency_deltas:
                    latency_delta = delta["retrieval_latency_ms_delta"]
                    token_delta = delta["total_tokens_delta"]
                    latency_display = f"{latency_delta:+.3f}" if isinstance(latency_delta, float) else f"{latency_delta:+d}"
                    token_display = f"{token_delta:+.3f}" if isinstance(token_delta, float) else f"{token_delta:+d}"
                    self.assertIn(
                        "Mode comparison fts efficiency delta "
                        f"{delta['question_id']}: retrieval_latency_ms={latency_display} "
                        f"total_tokens={token_display}",
                        output,
                    )
                for matrix_run in anchor_mode["matrix_runs"]:
                    self.assertIn(
                        "Mode comparison fts proof hop "
                        f"{matrix_run['matrix_run_id']}: result_hash={matrix_run['result_hash']} "
                        f"aggregate_merkle_root={matrix_run['aggregate_merkle_root']}",
                        output,
                    )

    def test_richer_same_adapter_matrix_comparison_report_and_dashboard_surfaces_mode_summaries(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                "analysis",
                {
                    "fts": (0, 8, 0),
                    "fts-multihop": (0, 8, 0),
                    "pseudo-embedding": (0, 8, 0),
                    "pseudo-embedding-rerank": (0, 8, 0),
                },
                (),
                (),
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                "dev",
                {
                    "fts": (0, 4, 1),
                    "fts-multihop": (0, 5, 0),
                    "pseudo-embedding": (0, 4, 1),
                    "pseudo-embedding-rerank": (0, 4, 1),
                },
                ("locomo-multihop-rich",),
                ("fts", "pseudo-embedding", "pseudo-embedding-rerank"),
            ),
        )

        for benchmark, dataset_writer, split, expected_by_mode, stable_miss_ids, spotlight_modes in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                first = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-matrix-a",
                )
                second = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-matrix-b",
                )

                comparison = compare_benchmark_matrices([Path(first["matrix_path"]), Path(second["matrix_path"])])
                artifacts = write_benchmark_matrix_comparison_artifacts(comparison, compare_out)
                comparison_path = Path(artifacts["comparison_path"])
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                report = render_benchmark_report(comparison_path)
                dashboard = render_benchmark_dashboard(comparison_path)
                report_text = Path(report["report_path"]).read_text(encoding="utf-8")
                dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

                self.assertEqual(comparison_payload["target"]["benchmark"], benchmark)
                self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
                self.assertEqual(comparison_payload["target"]["split"], split)
                self.assertEqual(report["artifact_type"], "matrix_comparison")
                self.assertEqual(report["verification_status"], "ok")
                self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
                self.assertEqual(dashboard["summary"]["benchmark"], benchmark)
                self.assertEqual(dashboard["summary"]["dataset"], str(dataset))
                self.assertEqual(dashboard["summary"]["split"], split)
                self.assertIn("## Compared Matrices", report_text)
                self.assertIn("## Retrieval Modes", report_text)
                self.assertIn("Retrieval Modes", dashboard_html)
                self.assertIn(f"{benchmark}-rich-matrix-a", report_text)
                self.assertIn(f"{benchmark}-rich-matrix-b", report_text)
                self.assertIn(f"{benchmark}-rich-matrix-a", dashboard_html)
                self.assertIn(f"{benchmark}-rich-matrix-b", dashboard_html)

                for mode_comparison in comparison_payload["mode_comparisons"]:
                    retrieval_mode = mode_comparison["retrieval_mode"]
                    question_summary = mode_comparison["question_summary"]
                    expected_visible_deltas, expected_stable_wins, expected_stable_misses = expected_by_mode[
                        retrieval_mode
                    ]

                    self.assertEqual(mode_comparison["proof"]["verification_status"], "ok")
                    self.assertEqual(
                        (
                            question_summary["visible_delta_question_count"],
                            question_summary["stable_wins"]["count"],
                            question_summary["stable_misses"]["count"],
                        ),
                        (expected_visible_deltas, expected_stable_wins, expected_stable_misses),
                    )
                    self.assertIn(f"### {retrieval_mode}", report_text)
                    self.assertIn(f"- Stable wins: `{expected_stable_wins}`", report_text)
                    self.assertIn(f"- Stable misses: `{expected_stable_misses}`", report_text)
                    self.assertIn(str(expected_stable_wins), dashboard_html)
                    self.assertIn(str(expected_stable_misses), dashboard_html)
                    for matrix_run in mode_comparison["matrix_runs"]:
                        self.assertIn(matrix_run["matrix_run_id"], report_text)
                        self.assertIn(matrix_run["result_hash"], report_text)
                        self.assertIn(matrix_run["aggregate_merkle_root"], report_text)
                        self.assertIn(matrix_run["matrix_run_id"], dashboard_html)
                        self.assertIn(matrix_run["result_hash"], dashboard_html)
                        self.assertIn(matrix_run["aggregate_merkle_root"], dashboard_html)

                if not stable_miss_ids:
                    self.assertNotIn("Stable Miss Spotlight", report_text)
                    self.assertNotIn("Stable Miss Spotlight", dashboard_html)
                else:
                    for stable_miss_id in stable_miss_ids:
                        self.assertIn(stable_miss_id, report_text)
                        self.assertIn(stable_miss_id, dashboard_html)
                    for mode in spotlight_modes:
                        self.assertIn(f"Stable Miss Spotlight: {mode}", dashboard_html)

    def test_cli_richer_same_adapter_matrix_comparison_reopen_preserves_mode_summaries_from_another_cwd(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                "analysis",
                {
                    "fts": (0, 8, 0),
                    "fts-multihop": (0, 8, 0),
                    "pseudo-embedding": (0, 8, 0),
                    "pseudo-embedding-rerank": (0, 8, 0),
                },
                (),
                (),
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                "dev",
                {
                    "fts": (0, 4, 1),
                    "fts-multihop": (0, 5, 0),
                    "pseudo-embedding": (0, 4, 1),
                    "pseudo-embedding-rerank": (0, 4, 1),
                },
                ("locomo-multihop-rich",),
                ("fts", "pseudo-embedding", "pseudo-embedding-rerank"),
            ),
        )

        for benchmark, dataset_writer, split, expected_by_mode, stable_miss_ids, spotlight_modes in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                first = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-matrix-a",
                )
                second = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-matrix-b",
                )

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    comparison = self._main_json(
                        [
                            "bench",
                            "compare-matrices",
                            os.path.relpath(first["matrix_path"], other_cwd),
                            os.path.relpath(second["matrix_path"], other_cwd),
                            "--out",
                            os.path.relpath(compare_out, other_cwd),
                        ]
                    )
                    verify = self._main_json(
                        [
                            "bench",
                            "verify",
                            comparison["comparison_path"],
                        ]
                    )
                    report = self._main_json(
                        [
                            "bench",
                            "report",
                            comparison["comparison_path"],
                        ]
                    )
                    dashboard = self._main_json(
                        [
                            "bench",
                            "dashboard",
                            comparison["comparison_path"],
                        ]
                    )
                finally:
                    os.chdir(previous_cwd)

                comparison_path = Path(comparison["comparison_path"])
                if not comparison_path.is_absolute():
                    comparison_path = (other_cwd / comparison_path).resolve()
                report_path = Path(report["report_path"])
                if not report_path.is_absolute():
                    report_path = (other_cwd / report_path).resolve()
                dashboard_path = Path(dashboard["dashboard_path"])
                if not dashboard_path.is_absolute():
                    dashboard_path = (other_cwd / dashboard_path).resolve()
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                direct_verify = verify_benchmark_artifact(comparison_path)
                report_text = report_path.read_text(encoding="utf-8")
                dashboard_html = dashboard_path.read_text(encoding="utf-8")
                report_summary_by_mode = {
                    mode["retrieval_mode"]: mode for mode in report["summary"]["mode_comparisons"]
                }
                dashboard_summary_by_mode = {
                    mode["retrieval_mode"]: mode for mode in dashboard["summary"]["mode_comparisons"]
                }

                self.assertTrue(verify["ok"])
                self.assertTrue(direct_verify["ok"])
                self.assertEqual(verify["artifact_type"], "matrix_comparison")
                self.assertEqual(direct_verify["artifact_type"], "matrix_comparison")
                self.assertEqual(verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(direct_verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(self._failed_check_names(verify), set())
                self.assertEqual(self._failed_check_names(direct_verify), set())
                self.assertEqual(report["artifact_type"], "matrix_comparison")
                self.assertEqual(report["verification_status"], "ok")
                self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
                self.assertEqual(dashboard["summary"]["benchmark"], benchmark)
                self.assertEqual(dashboard["summary"]["dataset"], str(dataset))
                self.assertEqual(dashboard["summary"]["split"], split)
                self.assertIn("## Compared Matrices", report_text)
                self.assertIn("## Retrieval Modes", report_text)
                self.assertIn("Retrieval Modes", dashboard_html)
                self.assertIn(f"{benchmark}-rich-matrix-a", report_text)
                self.assertIn(f"{benchmark}-rich-matrix-b", report_text)
                self.assertIn(f"{benchmark}-rich-matrix-a", dashboard_html)
                self.assertIn(f"{benchmark}-rich-matrix-b", dashboard_html)

                for mode_comparison in comparison_payload["mode_comparisons"]:
                    retrieval_mode = mode_comparison["retrieval_mode"]
                    question_summary = mode_comparison["question_summary"]
                    expected_visible_deltas, expected_stable_wins, expected_stable_misses = expected_by_mode[
                        retrieval_mode
                    ]

                    self.assertEqual(mode_comparison["proof"]["verification_status"], "ok")
                    self.assertEqual(report_summary_by_mode[retrieval_mode]["verification_status"], "ok")
                    self.assertEqual(dashboard_summary_by_mode[retrieval_mode]["verification_status"], "ok")
                    self.assertEqual(
                        (
                            question_summary["visible_delta_question_count"],
                            question_summary["stable_wins"]["count"],
                            question_summary["stable_misses"]["count"],
                        ),
                        (expected_visible_deltas, expected_stable_wins, expected_stable_misses),
                    )
                    self.assertEqual(
                        report_summary_by_mode[retrieval_mode]["question_summary"],
                        dashboard_summary_by_mode[retrieval_mode]["question_summary"],
                    )
                    self.assertEqual(
                        report_summary_by_mode[retrieval_mode]["question_summary"]["visible_delta_question_count"],
                        expected_visible_deltas,
                    )
                    self.assertEqual(
                        report_summary_by_mode[retrieval_mode]["question_summary"]["stable_wins"]["count"],
                        expected_stable_wins,
                    )
                    self.assertEqual(
                        report_summary_by_mode[retrieval_mode]["question_summary"]["stable_misses"]["count"],
                        expected_stable_misses,
                    )
                    self.assertIn(f"### {retrieval_mode}", report_text)
                    self.assertIn(f"- Stable wins: `{expected_stable_wins}`", report_text)
                    self.assertIn(f"- Stable misses: `{expected_stable_misses}`", report_text)
                    self.assertIn(str(expected_stable_wins), dashboard_html)
                    self.assertIn(str(expected_stable_misses), dashboard_html)
                    for matrix_run in mode_comparison["matrix_runs"]:
                        self.assertIn(matrix_run["matrix_run_id"], report_text)
                        self.assertIn(matrix_run["result_hash"], report_text)
                        self.assertIn(matrix_run["aggregate_merkle_root"], report_text)
                        self.assertIn(matrix_run["matrix_run_id"], dashboard_html)
                        self.assertIn(matrix_run["result_hash"], dashboard_html)
                        self.assertIn(matrix_run["aggregate_merkle_root"], dashboard_html)

                if not stable_miss_ids:
                    self.assertNotIn("Stable Miss Spotlight", report_text)
                    self.assertNotIn("Stable Miss Spotlight", dashboard_html)
                else:
                    for stable_miss_id in stable_miss_ids:
                        self.assertIn(stable_miss_id, report_text)
                        self.assertIn(stable_miss_id, dashboard_html)
                    for mode in spotlight_modes:
                        self.assertIn(f"Stable Miss Spotlight: {mode}", dashboard_html)

    def test_cli_richer_same_adapter_public_page_reopen_preserves_question_summary_from_another_cwd(self):
        cases = (
            ("longmemeval", self._write_richer_longmemeval_jsonl, "analysis"),
            ("locomo", self._write_richer_locomo_jsonl, "dev"),
        )

        for benchmark, dataset_writer, split in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                matrix = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-public-page-matrix",
                )
                expected_question_summary = matrix["summary"]["question_summary"]
                expected_categories = matrix["summary"]["categories"]
                stable_win_ids = ", ".join(expected_question_summary["stable_wins"]["question_ids"]) or "none"
                stable_miss_question_ids = expected_question_summary["stable_misses"]["question_ids"]
                stable_miss_ids = ", ".join(expected_question_summary["stable_misses"]["question_ids"]) or "none"
                stable_miss_questions = [
                    question
                    for question in matrix["comparison"]["questions"]
                    if question["question_id"] in stable_miss_question_ids
                ]
                stable_miss_evidence_text = None
                if stable_miss_questions:
                    for run in stable_miss_questions[0].get("runs", []):
                        for key in ("retrieved_memories", "injected_memories", "withheld_memories"):
                            for item in run.get(key, []):
                                if isinstance(item, dict) and item.get("content"):
                                    stable_miss_evidence_text = item["content"]
                                    break
                            if stable_miss_evidence_text:
                                break
                        if stable_miss_evidence_text:
                            break
                changed_questions = [
                    question
                    for question in matrix["comparison"]["questions"]
                    if any(
                        delta.get("correct_changed")
                        or delta.get("final_answer_changed")
                        or delta.get("outcome_reason_changed")
                        or delta.get("retrieved_memories_added")
                        or delta.get("retrieved_memories_removed")
                        or delta.get("injected_memories_added")
                        or delta.get("injected_memories_removed")
                        or delta.get("withheld_memories_added")
                        or delta.get("withheld_memories_removed")
                        for delta in question.get("deltas", [])
                        if isinstance(delta, dict)
                    )
                ]
                delta_evidence_text = None
                if changed_questions:
                    for delta in changed_questions[0].get("deltas", []):
                        if not isinstance(delta, dict):
                            continue
                        for key in (
                            "retrieved_memories_added",
                            "retrieved_memories_removed",
                            "injected_memories_added",
                            "injected_memories_removed",
                            "withheld_memories_added",
                            "withheld_memories_removed",
                        ):
                            for item in delta.get(key, []):
                                if isinstance(item, dict) and item.get("content"):
                                    delta_evidence_text = item["content"]
                                    break
                            if delta_evidence_text:
                                break
                        if delta_evidence_text:
                            break
                    if delta_evidence_text is None:
                        for key in ("baseline_final_answer", "final_answer"):
                            value = changed_questions[0]["deltas"][0].get(key)
                            if value:
                                delta_evidence_text = value
                                break

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    page = self._main_json(
                        [
                            "bench",
                            "public-page",
                            os.path.relpath(Path(matrix["matrix_path"]).parent, other_cwd),
                        ]
                    )
                finally:
                    os.chdir(previous_cwd)

                page_path = Path(page["page_path"])
                if not page_path.is_absolute():
                    page_path = (other_cwd / page_path).resolve()
                page_html = page_path.read_text(encoding="utf-8")

                self.assertTrue(page["ok"])
                self.assertEqual(page["claim_status"], "local scaffold evidence")
                self.assertEqual(page["summary"]["benchmark"], benchmark)
                self.assertEqual(page["summary"]["dataset"], str(dataset))
                self.assertEqual(page["summary"]["split"], split)
                self.assertEqual(page["summary"]["dataset_version"], "local-dataset")
                self.assertEqual(page["summary"]["dataset_hash"], matrix["dataset_hash"])
                self.assertEqual(page["summary"]["filtered_dataset_hash"], matrix["filtered_dataset_hash"])
                self.assertEqual(page["summary"]["mode_proofs"], matrix["summary"]["mode_proofs"])
                self.assertEqual(page["summary"]["categories"], expected_categories)
                self.assertEqual(page["summary"]["question_summary"], expected_question_summary)

                self._assert_rendered_mode_proof_hops(matrix["summary"]["mode_proofs"], page_html)
                self.assertIn("Question Stability", page_html)
                self.assertIn("Category Performance", page_html)
                self.assertIn("Per-mode category performance", page_html)
                self.assertIn("Failure reasons", page_html)
                self.assertIn("Stable Win Question IDs", page_html)
                self.assertIn("Stable Miss Question IDs", page_html)
                self.assertIn(str(expected_question_summary["question_count"]), page_html)
                self.assertIn(str(expected_question_summary["visible_delta_question_count"]), page_html)
                self.assertIn(str(expected_question_summary["stable_wins"]["count"]), page_html)
                self.assertIn(str(expected_question_summary["stable_misses"]["count"]), page_html)
                self.assertIn(stable_win_ids, page_html)
                self.assertIn(stable_miss_ids, page_html)
                for category in expected_categories:
                    self.assertIn(category["category"], page_html)
                if any(category["deltas"] for category in expected_categories):
                    self.assertIn("Accuracy deltas vs baseline", page_html)
                if expected_question_summary["stable_misses"]["count"] == 0:
                    self.assertNotIn("Stable Miss Spotlight", page_html)
                else:
                    self.assertIn("Stable Miss Spotlight", page_html)
                    self.assertIn("Per-mode memory context", page_html)
                    if stable_miss_evidence_text:
                        self.assertIn(stable_miss_evidence_text, page_html)
                if changed_questions:
                    self.assertIn("Question Evidence", page_html)
                    self.assertIn("Deltas vs baseline", page_html)
                    self.assertIn("Answer delta", page_html)
                    self.assertIn("Retrieved evidence +/-", page_html)
                    self.assertIn(changed_questions[0]["question_id"], page_html)
                    if delta_evidence_text:
                        self.assertIn(delta_evidence_text, page_html)

    def test_cli_compare_matrices_from_another_cwd_preserves_mixed_input_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            longmemeval_dataset = self._write_longmemeval_jsonl(tmp_path)
            locomo_dataset = self._write_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()
            longmemeval_matrix = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=longmemeval_dataset,
                split="small",
                seed=0,
                run_id="longmemeval-mixed-matrix",
            )
            locomo_matrix = run_benchmark_matrix(
                out,
                "locomo",
                dataset=locomo_dataset,
                split="dev",
                seed=0,
                run_id="locomo-mixed-matrix",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_cwd)
                comparison = self._main_json(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(longmemeval_matrix["matrix_path"], other_cwd),
                        os.path.relpath(locomo_matrix["matrix_path"], other_cwd),
                        "--out",
                        os.path.relpath(compare_out, other_cwd),
                    ]
                )
                summary_output = self._main_text(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(longmemeval_matrix["matrix_path"], other_cwd),
                        os.path.relpath(locomo_matrix["matrix_path"], other_cwd),
                        "--summary-only",
                    ]
                )
                report = self._main_json(["bench", "report", comparison["comparison_path"]])
                dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
                report_text = Path(report["report_path"]).read_text(encoding="utf-8")
                dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            finally:
                os.chdir(previous_cwd)

            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison["compatibility"]["comparison_axis"], "matrix_run")
            self.assertEqual(
                comparison["compatibility"]["warnings"],
                [
                    "benchmarks differ",
                    "dataset hashes differ",
                    "filtered dataset hashes differ",
                    "splits differ",
                ],
            )
            self.assertEqual(
                [mode["comparison"]["compatibility"]["comparison_axis"] for mode in comparison["mode_comparisons"]],
                ["mixed_inputs"] * len(BENCHMARK_RETRIEVAL_MODES),
            )
            self.assertIn("Comparison axis: matrix_run", summary_output)
            self.assertIn(
                "Compatibility warnings: benchmarks differ, dataset hashes differ, filtered dataset hashes differ, splits differ",
                summary_output,
            )
            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertIsNone(report["summary"]["benchmark"])
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertIsNone(dashboard["summary"]["benchmark"])
            self.assertIsNone(dashboard["summary"]["dataset"])
            self.assertIn("- Benchmark: `mixed`", report_text)
            self.assertIn("- Dataset: `mixed`", report_text)
            self.assertIn("- Compatibility warnings: `benchmarks differ, dataset hashes differ, filtered dataset hashes differ, splits differ`", report_text)
            self.assertIn("Compatibility Warnings", dashboard_html)
            self.assertIn("benchmarks differ", dashboard_html)
            self.assertIn("dataset hashes differ", dashboard_html)
            self.assertIn("filtered dataset hashes differ", dashboard_html)
            self.assertIn("splits differ", dashboard_html)

    def test_verify_matrix_comparison_fails_when_payload_is_tampered_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            first = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="tamper-matrix-a",
            )
            second = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="tamper-matrix-b",
            )
            comparison = compare_benchmark_matrices([Path(first["matrix_path"]), Path(second["matrix_path"])])
            artifacts = write_benchmark_matrix_comparison_artifacts(comparison, tmp_path / "comparison")
            comparison_path = Path(artifacts["comparison_path"])
            payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            payload["mode_comparisons"][0]["question_summary"]["stable_wins"]["count"] = 999
            payload["comparison_hash"] = sha256_text(
                stable_json({key: value for key, value in payload.items() if key != "comparison_hash"})
            )
            comparison_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            verify = verify_benchmark_artifact(comparison_path)

            self.assertFalse(verify["ok"])
            self.assertEqual(verify["artifact_type"], "matrix_comparison")
            self.assertIn("reconstructed_payload", self._failed_check_names(verify))

    def test_synthetic_matrix_runs_all_local_retrieval_modes_and_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="local-matrix")
            matrix_dir = Path(matrix["matrix_dir"])
            stored_comparison = json.loads(
                self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"]).read_text(encoding="utf-8")
            )

            self.assertTrue(matrix["ok"])
            self.assertEqual(matrix["retrieval_modes"], list(BENCHMARK_RETRIEVAL_MODES))
            self.assertEqual(
                [run["retrieval_mode"] for run in matrix["mode_runs"]],
                list(BENCHMARK_RETRIEVAL_MODES),
            )
            self.assertTrue((matrix_dir / "benchmark-matrix.json").exists())
            self.assertTrue((matrix_dir / "benchmark-comparison.json").exists())
            self.assertTrue((matrix_dir / "matrix-report.md").exists())
            for retrieval_mode in BENCHMARK_RETRIEVAL_MODES:
                mode_dir = matrix_dir / retrieval_mode
                self.assertTrue((mode_dir / "benchmark-run.json").exists())
                self.assertTrue((mode_dir / "benchmark-result.json").exists())
                self.assertTrue((mode_dir / "report.md").exists())

            comparison = compare_benchmark_results(
                [matrix_dir / retrieval_mode / "benchmark-result.json" for retrieval_mode in BENCHMARK_RETRIEVAL_MODES]
            )

            self.assertEqual(matrix["comparison_hash"], stored_comparison["comparison_hash"])
            self.assertEqual(matrix["proof"]["comparison_hash"], stored_comparison["comparison_hash"])
            self.assertEqual(matrix["comparison"]["compatibility"]["comparison_axis"], "retrieval_mode")
            self.assertEqual(matrix["question_summary"], matrix["comparison"]["question_summary"])
            self.assertIn("stable_misses", matrix["question_summary"])
            self.assertIn("stable_wins", matrix["question_summary"])
            self.assertEqual(len(matrix["summary"]["mode_proofs"]), len(BENCHMARK_RETRIEVAL_MODES))
            for mode_run, mode_proof in zip(matrix["mode_runs"], matrix["summary"]["mode_proofs"]):
                self.assertEqual(mode_proof["retrieval_mode"], mode_run["retrieval_mode"])
                self.assertEqual(mode_proof["result_hash"], mode_run["result_hash"])
                self.assertEqual(mode_proof["aggregate_merkle_root"], mode_run["aggregate_merkle_root"])
                self.assertTrue(mode_run["result_hash"])
                self.assertTrue(mode_run["aggregate_merkle_root"])
            self.assertNotEqual(matrix["comparison_hash"], comparison["comparison_hash"])

    def test_single_mode_matrix_does_not_self_compare_duplicate_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(
                Path(tmp),
                "synthetic",
                seed=0,
                run_id="single-mode-matrix",
                mode="fts",
            )
            matrix_path = Path(matrix["matrix_path"])
            comparison_path = self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"])
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))

            self.assertEqual(comparison["result_count"], 1)
            self.assertEqual(len(comparison["runs"]), 1)
            self.assertEqual(comparison["deltas"], [])
            self.assertEqual(len(comparison["proof"]["input_result_hashes"]), 1)
            self.assertTrue(all(len(question["runs"]) == 1 for question in comparison["questions"]))
            self.assertTrue(all(question["deltas"] == [] for question in comparison["questions"]))
            self.assertTrue(verify_benchmark_artifact(comparison_path)["ok"])
            self.assertTrue(verify_benchmark_artifact(matrix_path)["ok"])
            with self.assertRaisesRegex(ValueError, "at least two"):
                compare_benchmark_results([Path(matrix["mode_runs"][0]["result_path"])])

    def test_comparison_report_surfaces_verification_summary_and_question_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            fts = run_synthetic_benchmark(out, seed=0, run_id="report-a", retrieval_mode="fts")
            multihop = run_synthetic_benchmark(out, seed=0, run_id="report-b", retrieval_mode="fts-multihop")
            compare_out = Path(tmp) / "comparison" / "benchmark-comparison.json"
            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            write_benchmark_comparison_artifacts(comparison, compare_out, write_dashboard=False)

            report = render_benchmark_report(compare_out)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")

            self.assertEqual(report["artifact_type"], "comparison")
            self.assertIn("- Comparison artifact verification: `ok`", report_text)
            self.assertIn("- Comparison failed checks: `none`", report_text)
            self.assertIn("## Compared Runs", report_text)
            self.assertIn("## Category Performance", report_text)
            self.assertIn("## Question Evidence", report_text)
            self.assertIn("synthetic-multihop-kestrel-locker", report_text)
            self.assertIn("Retrieved evidence +/-", report_text)

    def test_comparison_report_surfaces_failed_verification_when_comparison_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="tampered-comparison-report")
            comparison_path = self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"])
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["question_summary"]["stable_wins"]["count"] = 999
            comparison["comparison_hash"] = sha256_text(
                stable_json({key: value for key, value in comparison.items() if key != "comparison_hash"})
            )
            comparison_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            report = render_benchmark_report(comparison_path)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")

            self.assertEqual(report["artifact_type"], "comparison")
            self.assertIn("- Comparison artifact verification: `failed`", report_text)
            self.assertIn("- Comparison failed checks: `reconstructed_payload`", report_text)

    def test_verify_comparison_fails_when_payload_is_tampered_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="tamper-comparison")
            comparison_path = self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"])
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["question_summary"]["stable_wins"]["count"] = 999
            comparison["comparison_hash"] = sha256_text(
                stable_json({key: value for key, value in comparison.items() if key != "comparison_hash"})
            )
            comparison_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            verify = verify_benchmark_artifact(comparison_path)

            self.assertFalse(verify["ok"])
            self.assertIn("reconstructed_payload", self._failed_check_names(verify))

    def test_verify_matrix_fails_when_mode_run_summary_is_tampered_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="tamper-matrix")
            matrix_path = Path(matrix["matrix_path"])
            payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            payload["mode_runs"][0]["summary"]["accuracy"] = 0.123
            payload["matrix_hash"] = sha256_text(
                stable_json({key: value for key, value in payload.items() if key != "matrix_hash"})
            )
            matrix_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            verify = verify_benchmark_artifact(matrix_path)

            self.assertFalse(verify["ok"])
            self.assertIn("mode_runs", self._failed_check_names(verify))

    def test_longmemeval_matrix_runs_jsonl_fixture_across_all_local_retrieval_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)

            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-local-matrix",
            )

            self._assert_local_dataset_matrix(matrix, "longmemeval", dataset, "small", question_count=2)

    def test_locomo_matrix_runs_jsonl_fixture_across_all_local_retrieval_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_jsonl(tmp_path)

            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-local-matrix",
            )

            self._assert_local_dataset_matrix(matrix, "locomo", dataset, "dev", question_count=2)

    def test_longmemeval_matrix_rendered_surfaces_preserve_local_dataset_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-matrix-surfaces",
            )
            matrix_path = Path(matrix["matrix_path"])
            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")

            self.assertEqual(dashboard["summary"]["benchmark"], "longmemeval")
            self.assertEqual(dashboard["summary"]["dataset"], str(dataset))
            self.assertEqual(dashboard["summary"]["split"], "small")
            self.assertEqual(dashboard["summary"]["dataset_version"], "local-dataset")
            self.assertEqual(dashboard["summary"]["dataset_hash"], matrix["dataset_hash"])
            self.assertEqual(dashboard["summary"]["filtered_dataset_hash"], matrix["filtered_dataset_hash"])
            self.assertEqual(page["summary"]["benchmark"], "longmemeval")
            self.assertEqual(page["summary"]["dataset"], str(dataset))
            self.assertEqual(page["summary"]["split"], "small")
            self.assertEqual(page["summary"]["dataset_version"], "local-dataset")
            self.assertEqual(page["summary"]["dataset_hash"], matrix["dataset_hash"])
            self.assertEqual(page["summary"]["filtered_dataset_hash"], matrix["filtered_dataset_hash"])
            self.assertIn("- Split: `small`", report_text)
            self.assertIn("- Dataset version: `local-dataset`", report_text)
            self.assertIn(matrix["dataset_hash"], report_text)
            self.assertIn(matrix["filtered_dataset_hash"], report_text)
            self.assertIn(str(dataset), dashboard_html)
            self.assertIn("small", dashboard_html)
            self.assertIn("local-dataset", dashboard_html)
            self.assertIn(matrix["dataset_hash"], dashboard_html)
            self.assertIn(matrix["filtered_dataset_hash"], dashboard_html)
            self.assertIn(str(dataset), page_html)
            self.assertIn("small", page_html)
            self.assertIn("local-dataset", page_html)
            self.assertIn(matrix["dataset_hash"], page_html)
            self.assertIn(matrix["filtered_dataset_hash"], page_html)

    def test_longmemeval_rendered_surfaces_preserve_per_mode_proof_hops(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-proof-hop-smoke",
            )
            matrix_path = Path(matrix["matrix_path"])
            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")
            mode_proofs = self._assert_mode_proofs_match_result_payloads(matrix)

            self.assertEqual(dashboard["summary"]["mode_proofs"], mode_proofs)
            self.assertEqual(page["summary"]["mode_proofs"], mode_proofs)
            for mode_proof in mode_proofs:
                self.assertIn(f"- Result hash: `{mode_proof['result_hash']}`", report_text)
                self.assertIn(f"- Aggregate Merkle root: `{mode_proof['aggregate_merkle_root']}`", report_text)

            self._assert_rendered_mode_proof_hops(mode_proofs, dashboard_html)
            self._assert_rendered_mode_proof_hops(mode_proofs, page_html)

    def test_longmemeval_standalone_comparison_artifacts_preserve_proof_hops(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            fts = run_longmemeval_benchmark(
                out,
                dataset,
                "small",
                seed=0,
                run_id="longmemeval-compare-fts",
                retrieval_mode="fts",
            )
            multihop = run_longmemeval_benchmark(
                out,
                dataset,
                "small",
                seed=0,
                run_id="longmemeval-compare-multihop",
                retrieval_mode="fts-multihop",
            )

            fts_result = json.loads(Path(fts["result_path"]).read_text(encoding="utf-8"))
            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            artifacts = write_benchmark_comparison_artifacts(comparison, compare_out)
            comparison_path = Path(artifacts["comparison_path"])
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = Path(artifacts["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(artifacts["dashboard_path"]).read_text(encoding="utf-8")
            proof_hops = self._comparison_run_proof_hops(comparison_payload)

            self.assertEqual(comparison_payload["target"]["benchmark"], "longmemeval")
            self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
            self.assertEqual(comparison_payload["target"]["split"], "small")
            self.assertEqual(comparison_payload["target"]["dataset_version"], "local-dataset")
            self.assertEqual(comparison_payload["target"]["dataset_hash"], fts_result["dataset_hash"])
            self.assertEqual(comparison_payload["target"]["filtered_dataset_hash"], fts_result["filtered_dataset_hash"])
            self.assertIn("- Benchmark: `longmemeval`", report_text)
            self.assertIn(f"- Dataset: `{dataset}`", report_text)
            self.assertIn("- Split: `small`", report_text)
            self.assertIn("- Dataset version: `local-dataset`", report_text)
            self.assertIn(comparison_payload["target"]["dataset_hash"], report_text)
            self.assertIn(comparison_payload["target"]["filtered_dataset_hash"], report_text)
            self.assertIn(str(dataset), dashboard_html)
            self.assertIn("small", dashboard_html)
            self.assertIn("local-dataset", dashboard_html)
            self.assertIn(comparison_payload["target"]["dataset_hash"], dashboard_html)
            self.assertIn(comparison_payload["target"]["filtered_dataset_hash"], dashboard_html)
            self._assert_rendered_comparison_proof_hops(proof_hops, report_text)
            self._assert_rendered_comparison_proof_hops(proof_hops, dashboard_html)

    def test_cli_longmemeval_compare_and_report_preserve_proof_hops_from_persisted_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            fts = run_longmemeval_benchmark(
                out,
                dataset,
                "small",
                seed=0,
                run_id="longmemeval-cli-compare-fts",
                retrieval_mode="fts",
            )
            multihop = run_longmemeval_benchmark(
                out,
                dataset,
                "small",
                seed=0,
                run_id="longmemeval-cli-compare-multihop",
                retrieval_mode="fts-multihop",
            )

            fts_result = json.loads(Path(fts["result_path"]).read_text(encoding="utf-8"))
            multihop_result = json.loads(Path(multihop["result_path"]).read_text(encoding="utf-8"))

            comparison = self._main_json(
                [
                    "bench",
                    "compare",
                    str(fts["result_path"]),
                    str(multihop["result_path"]),
                    "--out",
                    str(compare_out),
                ]
            )
            comparison_path = Path(comparison["comparison_path"])
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report = self._main_json(["bench", "report", str(comparison_path)])
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            proof_hops = self._comparison_run_proof_hops(comparison_payload)

            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison_payload["proof"]["verification_status"], "ok")
            self.assertEqual(report["artifact_type"], "comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["question_summary"], comparison_payload["question_summary"])
            self.assertEqual(
                proof_hops,
                [
                    {
                        "retrieval_mode": fts_result["retrieval_mode"],
                        "result_hash": fts_result["result_hash"],
                        "aggregate_merkle_root": fts_result["proof"]["aggregate_merkle_root"],
                    },
                    {
                        "retrieval_mode": multihop_result["retrieval_mode"],
                        "result_hash": multihop_result["result_hash"],
                        "aggregate_merkle_root": multihop_result["proof"]["aggregate_merkle_root"],
                    },
                ],
            )
            self.assertEqual(comparison_payload["target"]["benchmark"], "longmemeval")
            self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
            self.assertEqual(comparison_payload["target"]["split"], "small")
            self.assertIn("- Comparison artifact verification: `ok`", report_text)
            self.assertEqual(report_text.count("- Result verification: `ok`"), 2)
            self._assert_rendered_comparison_proof_hops(proof_hops, report_text)

    def test_locomo_rendered_surfaces_preserve_per_mode_proof_hops(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-proof-hop-smoke",
            )
            matrix_path = Path(matrix["matrix_path"])
            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")
            mode_proofs = self._assert_mode_proofs_match_result_payloads(matrix)

            self.assertEqual(dashboard["summary"]["mode_proofs"], mode_proofs)
            self.assertEqual(page["summary"]["mode_proofs"], mode_proofs)
            for mode_proof in mode_proofs:
                self.assertIn(f"- Result hash: `{mode_proof['result_hash']}`", report_text)
                self.assertIn(f"- Aggregate Merkle root: `{mode_proof['aggregate_merkle_root']}`", report_text)

            self._assert_rendered_mode_proof_hops(mode_proofs, dashboard_html)
            self._assert_rendered_mode_proof_hops(mode_proofs, page_html)

    def test_synthetic_matrix_propagates_provider_config_metadata_to_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "providers.json"
            config_path.write_text(json.dumps(self._provider_config()), encoding="utf-8")

            matrix = run_benchmark_matrix(
                tmp_path,
                "synthetic",
                seed=0,
                run_id="provider-matrix",
                retrieval_provider_config_path=config_path,
            )
            matrix_dir = Path(matrix["matrix_dir"])
            expected_hash = matrix["mode_runs"][0]["retrieval_provider_config"]["config_hash"]

            self.assertTrue(matrix["ok"])
            self.assertEqual(
                {run["retrieval_provider_config"]["config_hash"] for run in matrix["mode_runs"]},
                {expected_hash},
            )
            self.assertEqual(
                {run["retrieval_provider_config"]["config_hash"] for run in matrix["comparison"]["runs"]},
                {expected_hash},
            )
            self.assertNotIn("sk-test-secret", (matrix_dir / "benchmark-matrix.json").read_text(encoding="utf-8"))
            self.assertNotIn("sk-test-secret", (matrix_dir / "benchmark-comparison.json").read_text(encoding="utf-8"))

    def test_cli_matrix_returns_proof_friendly_comparison_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"

            matrix = self._main_json(["bench", "matrix", "synthetic", "--out", str(out), "--run-id", "cli-matrix"])

            self.assertTrue(matrix["ok"])
            self.assertTrue(matrix["comparison_hash"])
            self.assertEqual(matrix["proof"]["comparison_hash"], matrix["comparison_hash"])
            self.assertEqual(
                [run["retrieval_mode"] for run in matrix["mode_runs"]],
                list(BENCHMARK_RETRIEVAL_MODES),
            )
            self.assertTrue((out / "cli-matrix" / "benchmark-comparison.json").exists())

    def test_matrix_report_surfaces_latency_tokens_and_question_evidence_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="matrix-report")
            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")

            self.assertIn("- Matrix artifact verification: `ok`", report_text)
            self.assertIn("- Matrix failed checks: `none`", report_text)
            self.assertIn("- Comparison artifact verification: `ok`", report_text)
            self.assertIn("- Comparison failed checks: `none`", report_text)
            self.assertIn("- Category rows: `4`", report_text)
            self.assertIn("- Retrieved / injected / withheld memories:", report_text)
            self.assertIn("- Retrieval latency p50/p95/p99 ms:", report_text)
            self.assertIn("- Total tokens:", report_text)
            self.assertIn("- Retrieval config hash:", report_text)
            self.assertIn("- Question evidence rows: `4`", report_text)
            self.assertIn("## Question Evidence", report_text)
            self.assertIn("Retrieved evidence +/-", report_text)
            self.assertIn("Final answer delta", report_text)
            self.assertIn("latency delta `", report_text)
            self.assertIn("latency p50/p95/p99 ms", report_text)
            self.assertIn("tokens `", report_text)

    def test_local_dataset_matrix_report_surfaces_category_performance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-category-report",
            )
            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")

            self.assertIn("## Category Performance", report_text)
            self.assertIn("### single_session_user_recall", report_text)
            self.assertIn("### abstention", report_text)
            self.assertIn("- fts:", report_text)
            self.assertIn("- fts-multihop:", report_text)

    def test_cli_local_dataset_matrix_report_reopens_from_another_cwd_with_comparison_details(self):
        previous_cwd = Path.cwd()
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                "analysis",
                {
                    "visible_deltas": 3,
                    "stable_wins": 5,
                    "stable_misses": 0,
                    "changed_question_id": "lme-knowledge-update-release-note-decoy",
                    "budget_context_line": (
                        "Budget-dropped stable context ids: "
                        "lme-temporal-change-when, lme-knowledge-update-stale-decoy, "
                        "lme-knowledge-update-history-wording-gap"
                    ),
                    "evidence_text": "Blue Finch shipped on Staging before the cutover.",
                },
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                "dev",
                {
                    "visible_deltas": 2,
                    "stable_wins": 2,
                    "stable_misses": 1,
                    "changed_question_id": "locomo-temporal-rich",
                    "budget_context_line": (
                        "Budget-dropped stable context ids: "
                        "locomo-temporal-rich, locomo-multihop-rich, locomo-routing-owner-history-gap"
                    ),
                    "evidence_text": "The review moved again to Friday afternoon.",
                },
            ),
        )

        for benchmark, dataset_writer, split, expected in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()

                os.chdir(tmp_path)
                try:
                    matrix = run_benchmark_matrix(
                        Path("bench"),
                        benchmark,
                        dataset=dataset,
                        split=split,
                        seed=0,
                        run_id=f"{benchmark}-report-reopen",
                        context_budget_tokens=200,
                    )
                finally:
                    os.chdir(previous_cwd)

                matrix_path = Path(matrix["matrix_path"]).resolve()
                report_output = ""
                report = {}
                try:
                    os.chdir(other_cwd)
                    report_output = self._main_text(["bench", "report", str(matrix_path), "--summary-only"])
                    report = self._main_json(["bench", "report", str(matrix_path)])
                finally:
                    os.chdir(previous_cwd)

                report_path = Path(report["report_path"])
                if not report_path.is_absolute():
                    report_path = (other_cwd / report_path).resolve()
                report_text = report_path.read_text(encoding="utf-8")
                first_mode = matrix["summary"]["mode_proofs"][0]

                self.assertEqual(report["artifact_type"], "matrix")
                self.assertEqual(report["verification_status"], "ok")
                self.assertEqual(report["comparison_verification_status"], "ok")
                self.assertIn("Benchmark report", report_output)
                self.assertIn("Artifact: matrix", report_output)
                self.assertIn("Verification: ok", report_output)
                self.assertIn("Comparison verification: ok", report_output)
                self.assertIn(f"Benchmark: {benchmark}", report_output)
                self.assertIn(f"Dataset: {dataset}", report_output)
                self.assertIn(f"Split: {split}", report_output)
                self.assertIn(f"Visible deltas: {expected['visible_deltas']}", report_output)
                self.assertIn(f"Stable wins: {expected['stable_wins']}", report_output)
                self.assertIn(f"Stable misses: {expected['stable_misses']}", report_output)
                self.assertIn(expected["budget_context_line"], report_output)
                self.assertIn(
                    f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                    f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                    report_output,
                )

                self.assertIn(f"# ZMem {benchmark} Benchmark Matrix", report_text)
                self.assertIn(f"- Dataset: `{dataset}`", report_text)
                self.assertIn(f"- Split: `{split}`", report_text)
                self.assertIn("- Comparison artifact verification: `ok`", report_text)
                self.assertIn("- Retrieval latency p50/p95/p99 ms:", report_text)
                self.assertIn("- Total tokens:", report_text)
                self.assertIn(f"- Result hash: `{first_mode['result_hash']}`", report_text)
                self.assertIn(f"- Aggregate Merkle root: `{first_mode['aggregate_merkle_root']}`", report_text)
                self.assertIn("## Question Evidence", report_text)
                self.assertIn(expected["changed_question_id"], report_text)
                self.assertIn("latency delta `", report_text)
                self.assertIn("Retrieved evidence +/-", report_text)
                self.assertIn("Budget-dropped evidence +/-", report_text)
                self.assertIn(expected["evidence_text"], report_text)

    def test_benchmark_dashboard_renders_standalone_matrix_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="dashboard-matrix")

            dashboard = render_benchmark_dashboard(Path(matrix["matrix_path"]))
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["matrix_hash"], matrix["matrix_hash"])
            self.assertEqual(dashboard["comparison_hash"], matrix["comparison_hash"])
            self.assertIn("ZMem Benchmark Dashboard", html_text)
            self.assertIn("Standalone benchmark artifact generated from benchmark-matrix.json.", html_text)
            self.assertIn("Matrix Verify", html_text)
            self.assertIn("Comparison Verify", html_text)
            self.assertIn("Matrix Failed Checks", html_text)
            self.assertIn("Comparison Failed Checks", html_text)
            self.assertIn(matrix["matrix_hash"], html_text)
            self.assertIn(matrix["comparison_hash"], html_text)
            for retrieval_mode in BENCHMARK_RETRIEVAL_MODES:
                self.assertIn(retrieval_mode, html_text)
            self.assertNotIn("Release packet", html_text)
            self.assertNotIn("Launch assets", html_text)

    def test_matrix_report_surfaces_failed_verification_summary_when_matrix_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="tampered-report")
            matrix_path = Path(matrix["matrix_path"])
            payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            payload["mode_runs"][0]["summary"]["accuracy"] = 0.123
            payload["matrix_hash"] = sha256_text(
                stable_json({key: value for key, value in payload.items() if key != "matrix_hash"})
            )
            matrix_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            report_text = _render_matrix_report_text(payload)

            self.assertIn("- Matrix artifact verification: `failed`", report_text)
            self.assertIn("- Matrix failed checks: `mode_runs, score_summary`", report_text)
            self.assertIn("- Comparison artifact verification: `ok`", report_text)

    def test_matrix_report_surfaces_per_mode_result_hash_and_aggregate_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="proof-summary-report")
            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")
            first_mode = matrix["mode_runs"][0]

            self.assertIn(f"- Result hash: `{first_mode['result_hash']}`", report_text)
            self.assertIn(f"- Aggregate Merkle root: `{first_mode['aggregate_merkle_root']}`", report_text)

    def test_dashboard_surfaces_failed_verification_summary_when_matrix_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="tampered-dashboard")
            matrix_path = Path(matrix["matrix_path"])
            payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            payload["mode_runs"][0]["summary"]["accuracy"] = 0.123
            payload["matrix_hash"] = sha256_text(
                stable_json({key: value for key, value in payload.items() if key != "matrix_hash"})
            )
            matrix_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            dashboard = render_benchmark_dashboard(matrix_path)
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertIn("Matrix Failed Checks", html_text)
            self.assertIn("mode_runs", html_text)
            self.assertIn(">failed<", html_text)

    def test_dashboard_surfaces_per_mode_result_hash_and_aggregate_root_in_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="dashboard-proof-hops")

            dashboard = render_benchmark_dashboard(Path(matrix["matrix_path"]))
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            first_mode = matrix["summary"]["mode_proofs"][0]

            self.assertIn("Per-Mode Proof Hops", html_text)
            self.assertIn("Result hash", html_text)
            self.assertIn("Aggregate Merkle root", html_text)
            self.assertIn(first_mode["retrieval_mode"], html_text)
            self.assertIn(first_mode["result_hash"], html_text)
            self.assertIn(first_mode["aggregate_merkle_root"], html_text)

    def test_benchmark_dashboard_surfaces_question_evidence_and_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="dashboard-question-evidence")

            dashboard = render_benchmark_dashboard(Path(matrix["matrix_path"]))
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertIn("Question Evidence", html_text)
            self.assertIn("synthetic-multihop-kestrel-locker", html_text)
            self.assertIn("Per-mode evidence", html_text)
            self.assertIn("Deltas vs baseline", html_text)
            self.assertIn("Outcome reason", html_text)
            self.assertIn("Outcome reason delta", html_text)
            self.assertIn("Final answer", html_text)
            self.assertIn("Answer delta", html_text)
            self.assertIn("Retrieval latency delta", html_text)
            self.assertIn("latency delta ", html_text)
            self.assertIn("Retrieved evidence +/-", html_text)
            self.assertIn("Correct changed", html_text)
            self.assertIn("What locker code follows the Kestrel Node handoff checklist?", html_text)
            self.assertIn("locker code is 4182", html_text)

    def test_locomo_matrix_report_and_dashboard_surface_content_level_question_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-rich-deltas",
            )

            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")
            dashboard = render_benchmark_dashboard(Path(matrix["matrix_path"]))
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertIn("## Question Evidence", report_text)
            self.assertIn("locomo-multihop-rich", report_text)
            self.assertIn("Kestrel Node locker code is 4182.", report_text)
            self.assertIn("locomo-multihop-rich", html_text)
            self.assertIn("Question Evidence", html_text)
            self.assertIn("Retrieval latency delta", html_text)
            self.assertIn("latency delta ", html_text)
            self.assertIn("Retrieved evidence +/-", html_text)
            self.assertIn("Kestrel Node locker code is 4182.", html_text)

    def test_local_dataset_dashboard_surfaces_category_performance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-category-dashboard",
            )

            dashboard = render_benchmark_dashboard(Path(matrix["matrix_path"]))
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertIn("Category Performance", html_text)
            self.assertIn("Per-mode category performance", html_text)
            self.assertIn("Accuracy deltas vs baseline", html_text)
            self.assertIn("P95 ms", html_text)
            self.assertIn("Tokens", html_text)
            self.assertIn("Retrieved", html_text)
            self.assertIn("Failure reasons", html_text)
            self.assertIn("single_session_user_recall", html_text)
            self.assertIn("abstention", html_text)
            self.assertIn("provisional-local", html_text)

    def test_richer_longmemeval_matrix_and_dashboard_surfaces_current_update_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="longmemeval-rich-gap-dashboard",
            )

            report_text = self._resolve_matrix_artifact_path(matrix, matrix["report_path"]).read_text(encoding="utf-8")
            dashboard = render_benchmark_dashboard(Path(matrix["matrix_path"]))
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertIn("### knowledge_update", report_text)
            self.assertIn("- fts: `1.000` (6/6)", report_text)
            self.assertIn("failure reasons `none`", report_text)
            self.assertIn("## Question Evidence", report_text)
            self.assertIn("lme-knowledge-update-release-note-decoy", report_text)
            self.assertIn("- Stable miss spotlight rows: `0`", report_text)
            self.assertIn("Category Performance", html_text)
            self.assertIn("knowledge_update", html_text)
            self.assertIn("Question Evidence", html_text)
            self.assertIn("lme-knowledge-update-release-note-decoy", html_text)
            self.assertNotIn("Stable Miss Spotlight", html_text)
            self.assertNotIn("false_abstention_missing_retrieval", html_text)

            fts_run = next(mode_run for mode_run in matrix["mode_runs"] if mode_run["retrieval_mode"] == "fts")
            fts_multihop_run = next(
                mode_run for mode_run in matrix["mode_runs"] if mode_run["retrieval_mode"] == "fts-multihop"
            )
            knowledge_update = fts_run["summary"]["category_summaries"]["knowledge_update"]
            self.assertEqual(knowledge_update["accuracy"], 1.0)
            self.assertEqual(knowledge_update["failure_reason_counts"], {})
            self.assertEqual(
                fts_multihop_run["summary"]["category_summaries"]["knowledge_update"]["accuracy"],
                1.0,
            )

    def test_matrix_report_and_dashboard_surface_stable_miss_spotlight_without_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="stable-miss-spotlight")
            matrix_path = Path(matrix["matrix_path"])
            spotlight_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "synthetic-policy-recall"
            )

            for run in spotlight_question["runs"]:
                run["correct"] = False
                run["score"] = 0.0
                run["outcome_reason"] = "false_abstention_missing_injection"
                run["final_answer"] = "I don't know"
                run["injected_memory_ids"] = []
            matrix_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            report_text = _render_matrix_report_text(matrix)
            dashboard = render_benchmark_dashboard(matrix_path)
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertIn("- Stable miss spotlight rows: `1`", report_text)
            self.assertIn("## Stable Miss Spotlight", report_text)
            self.assertIn("synthetic-policy-recall", report_text)
            self.assertIn("false_abstention_missing_injection=4", report_text)
            self.assertIn("Stable Miss Spotlight", html_text)
            self.assertIn("synthetic-policy-recall", html_text)
            self.assertIn("Questions every compared mode still missed.", html_text)
            stable_section = html_text.split("Stable Miss Spotlight", 1)[1]
            stable_section = stable_section.split("Question Evidence", 1)[0]
            self.assertNotIn("Deltas vs baseline", stable_section)

    def test_public_page_surfaces_stable_miss_memory_context_without_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="stable-miss-public-page")
            matrix_path = Path(matrix["matrix_path"])
            spotlight_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "synthetic-policy-recall"
            )

            expected_evidence_text = None
            for run in spotlight_question["runs"]:
                if expected_evidence_text is None:
                    for memory in run.get("retrieved_memories", []):
                        if isinstance(memory, dict) and memory.get("content"):
                            expected_evidence_text = memory["content"]
                            break
                run["correct"] = False
                run["score"] = 0.0
                run["outcome_reason"] = "false_abstention_missing_injection"
                run["final_answer"] = "I don't know"
                run["injected_memory_ids"] = []
                run["injected_memories"] = []
            matrix_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            page = render_public_benchmark_page(matrix_path)
            html_text = Path(page["page_path"]).read_text(encoding="utf-8")

            self.assertTrue(page["ok"])
            self.assertIn("Stable Miss Spotlight", html_text)
            self.assertIn("Per-mode memory context", html_text)
            self.assertIn("Keep stable misses inspectable with the full per-mode retrieved, injected, and withheld", html_text)
            if expected_evidence_text:
                self.assertIn(expected_evidence_text, html_text)
            stable_section = html_text.split("Stable Miss Spotlight", 1)[1]
            stable_section = stable_section.split("Question Evidence", 1)[0]
            self.assertNotIn("Deltas vs baseline", stable_section)

    def test_benchmark_dashboard_renders_standalone_comparison_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            fts = run_synthetic_benchmark(out, seed=0, run_id="dashboard-a", retrieval_mode="fts")
            multihop = run_synthetic_benchmark(out, seed=0, run_id="dashboard-b", retrieval_mode="fts-multihop")
            comparison_path = Path(tmp) / "comparison.json"
            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            write_benchmark_comparison_artifacts(comparison, comparison_path, write_report=False)

            dashboard = render_benchmark_dashboard(comparison_path)
            report = render_benchmark_report(comparison_path)
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["artifact_type"], "comparison")
            self.assertEqual(dashboard["comparison_hash"], comparison["comparison_hash"])
            self.assertEqual(dashboard["summary"]["question_summary"], comparison["question_summary"])
            self.assertEqual(report["summary"]["question_summary"], comparison["question_summary"])
            self.assertIn("ZMem Benchmark Comparison", html_text)
            self.assertIn("Standalone benchmark artifact generated from benchmark-comparison.json.", html_text)
            self.assertIn("Comparison Verify", html_text)
            self.assertIn("Comparison Failed Checks", html_text)
            self.assertIn("Category Performance", html_text)
            self.assertIn("Question Evidence", html_text)
            self.assertIn("synthetic-multihop-kestrel-locker", html_text)

    def test_longmemeval_standalone_comparison_surfaces_shared_dataset_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            fts = run_longmemeval_benchmark(
                out,
                dataset,
                "small",
                seed=0,
                run_id="lme-compare-a",
                retrieval_mode="fts",
            )
            multihop = run_longmemeval_benchmark(
                out,
                dataset,
                "small",
                seed=0,
                run_id="lme-compare-b",
                retrieval_mode="fts-multihop",
            )
            comparison_path = tmp_path / "comparison" / "benchmark-comparison.json"
            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            write_benchmark_comparison_artifacts(comparison, comparison_path)

            report_text = comparison_path.with_name("comparison-report.md").read_text(encoding="utf-8")
            html_text = comparison_path.with_name("comparison-dashboard.html").read_text(encoding="utf-8")

            self.assertEqual(comparison["target"]["benchmark"], "longmemeval")
            self.assertEqual(comparison["target"]["dataset"], str(dataset))
            self.assertEqual(comparison["target"]["split"], "small")
            self.assertEqual(comparison["target"]["dataset_hash"], comparison["runs"][0]["dataset_hash"])
            self.assertEqual(
                comparison["target"]["filtered_dataset_hash"],
                comparison["runs"][0]["filtered_dataset_hash"],
            )
            self.assertIn("- Benchmark: `longmemeval`", report_text)
            self.assertIn(f"- Dataset: `{dataset}`", report_text)
            self.assertIn("- Split: `small`", report_text)
            self.assertIn(comparison["target"]["filtered_dataset_hash"], report_text)
            self.assertIn("longmemeval", html_text)
            self.assertIn(str(dataset), html_text)
            self.assertIn("small", html_text)
            self.assertIn(comparison["target"]["dataset_hash"], html_text)
            self.assertIn(comparison["target"]["filtered_dataset_hash"], html_text)

    def test_locomo_standalone_comparison_artifacts_preserve_proof_hops(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            fts = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="locomo-compare-a",
                retrieval_mode="fts",
            )
            multihop = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="locomo-compare-b",
                retrieval_mode="fts-multihop",
            )
            fts_result = json.loads(Path(fts["result_path"]).read_text(encoding="utf-8"))
            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            artifacts = write_benchmark_comparison_artifacts(comparison, compare_out)
            comparison_path = Path(artifacts["comparison_path"])
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = Path(artifacts["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(artifacts["dashboard_path"]).read_text(encoding="utf-8")
            proof_hops = self._comparison_run_proof_hops(comparison_payload)

            self.assertEqual(comparison_payload["target"]["benchmark"], "locomo")
            self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
            self.assertEqual(comparison_payload["target"]["split"], "dev")
            self.assertEqual(comparison_payload["target"]["dataset_version"], "local-dataset")
            self.assertEqual(comparison_payload["target"]["dataset_hash"], fts_result["dataset_hash"])
            self.assertEqual(comparison_payload["target"]["filtered_dataset_hash"], fts_result["filtered_dataset_hash"])
            self.assertIn("- Benchmark: `locomo`", report_text)
            self.assertIn(f"- Dataset: `{dataset}`", report_text)
            self.assertIn("- Split: `dev`", report_text)
            self.assertIn("- Dataset version: `local-dataset`", report_text)
            self.assertIn(comparison_payload["target"]["dataset_hash"], report_text)
            self.assertIn(comparison_payload["target"]["filtered_dataset_hash"], report_text)
            self.assertIn(str(dataset), dashboard_html)
            self.assertIn("dev", dashboard_html)
            self.assertIn("local-dataset", dashboard_html)
            self.assertIn(comparison_payload["target"]["dataset_hash"], dashboard_html)
            self.assertIn(comparison_payload["target"]["filtered_dataset_hash"], dashboard_html)
            self._assert_rendered_comparison_proof_hops(proof_hops, report_text)
            self._assert_rendered_comparison_proof_hops(proof_hops, dashboard_html)

    def test_cli_locomo_compare_and_report_preserve_proof_hops_from_persisted_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            fts = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="locomo-cli-compare-fts",
                retrieval_mode="fts",
            )
            multihop = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="locomo-cli-compare-multihop",
                retrieval_mode="fts-multihop",
            )

            fts_result = json.loads(Path(fts["result_path"]).read_text(encoding="utf-8"))
            multihop_result = json.loads(Path(multihop["result_path"]).read_text(encoding="utf-8"))

            comparison = self._main_json(
                [
                    "bench",
                    "compare",
                    str(fts["result_path"]),
                    str(multihop["result_path"]),
                    "--out",
                    str(compare_out),
                ]
            )
            comparison_path = Path(comparison["comparison_path"])
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report = self._main_json(["bench", "report", str(comparison_path)])
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            proof_hops = self._comparison_run_proof_hops(comparison_payload)

            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison_payload["proof"]["verification_status"], "ok")
            self.assertEqual(report["artifact_type"], "comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["question_summary"], comparison_payload["question_summary"])
            self.assertEqual(
                proof_hops,
                [
                    {
                        "retrieval_mode": fts_result["retrieval_mode"],
                        "result_hash": fts_result["result_hash"],
                        "aggregate_merkle_root": fts_result["proof"]["aggregate_merkle_root"],
                    },
                    {
                        "retrieval_mode": multihop_result["retrieval_mode"],
                        "result_hash": multihop_result["result_hash"],
                        "aggregate_merkle_root": multihop_result["proof"]["aggregate_merkle_root"],
                    },
                ],
            )
            self.assertEqual(comparison_payload["target"]["benchmark"], "locomo")
            self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
            self.assertEqual(comparison_payload["target"]["split"], "dev")
            self.assertIn("- Comparison artifact verification: `ok`", report_text)
            self.assertEqual(report_text.count("- Result verification: `ok`"), 2)
            self._assert_rendered_comparison_proof_hops(proof_hops, report_text)

    def test_richer_longmemeval_standalone_comparison_surfaces_current_update_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            fts = run_longmemeval_benchmark(
                out,
                dataset,
                "analysis",
                seed=0,
                run_id="lme-rich-compare-a",
                retrieval_mode="fts",
            )
            multihop = run_longmemeval_benchmark(
                out,
                dataset,
                "analysis",
                seed=0,
                run_id="lme-rich-compare-b",
                retrieval_mode="fts-multihop",
            )
            comparison_path = tmp_path / "comparison" / "benchmark-comparison.json"
            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            write_benchmark_comparison_artifacts(comparison, comparison_path)

            dashboard = render_benchmark_dashboard(comparison_path)
            report_text = comparison_path.with_name("comparison-report.md").read_text(encoding="utf-8")
            html_text = comparison_path.with_name("comparison-dashboard.html").read_text(encoding="utf-8")

            self.assertEqual(comparison["target"]["benchmark"], "longmemeval")
            self.assertEqual(comparison["target"]["dataset"], str(dataset))
            self.assertEqual(comparison["target"]["split"], "analysis")
            self.assertEqual(comparison["question_summary"]["visible_delta_question_count"], 1)
            self.assertEqual(comparison["question_summary"]["stable_misses"]["count"], 0)
            self.assertEqual(comparison["question_summary"]["stable_wins"]["count"], 7)
            self.assertEqual(dashboard["summary"]["question_summary"], comparison["question_summary"])
            self.assertIn("- Comparison artifact verification: `ok`", report_text)
            self.assertIn("- Stable wins: `7`", report_text)
            self.assertIn("- Stable misses: `0`", report_text)
            self.assertIn("- Visible delta questions: `1`", report_text)
            self.assertIn("## Question Evidence", report_text)
            self.assertIn("lme-knowledge-update-release-note-decoy", report_text)
            self.assertIn("latency delta `", report_text)
            self.assertIn("Blue Finch deploy target is Staging.", report_text)
            self.assertIn("### knowledge_update", report_text)
            self.assertIn("### current_conflict_abstention", report_text)
            self.assertIn("longmemeval", html_text)
            self.assertIn(str(dataset), html_text)
            self.assertIn("analysis", html_text)
            self.assertIn("knowledge_update", html_text)
            self.assertIn("current_conflict_abstention", html_text)
            self.assertNotIn("Stable Miss Spotlight", html_text)
            self.assertIn("Question Evidence", html_text)
            self.assertIn("lme-knowledge-update-release-note-decoy", html_text)
            self.assertIn("Blue Finch deploy target is Staging.", html_text)
            self.assertNotIn("lme-routing-owner-wording-gap", html_text)

    def test_richer_locomo_standalone_comparison_surfaces_content_level_question_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            fts = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="locomo-rich-compare-a",
                retrieval_mode="fts",
            )
            multihop = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="locomo-rich-compare-b",
                retrieval_mode="fts-multihop",
            )
            comparison_path = tmp_path / "comparison" / "benchmark-comparison.json"
            comparison = compare_benchmark_results([Path(fts["result_path"]), Path(multihop["result_path"])])
            write_benchmark_comparison_artifacts(comparison, comparison_path)

            report_text = comparison_path.with_name("comparison-report.md").read_text(encoding="utf-8")
            html_text = comparison_path.with_name("comparison-dashboard.html").read_text(encoding="utf-8")

            self.assertEqual(comparison["target"]["benchmark"], "locomo")
            self.assertEqual(comparison["target"]["dataset"], str(dataset))
            self.assertEqual(comparison["target"]["split"], "dev")
            self.assertGreaterEqual(comparison["question_summary"]["visible_delta_question_count"], 1)
            self.assertEqual(comparison["question_summary"]["stable_misses"]["count"], 0)
            self.assertIn(
                "locomo-abstention-rich",
                comparison["question_summary"]["stable_wins"]["question_ids"],
            )
            self.assertEqual(
                comparison["question_summary"]["stable_wins"]["question_ids"],
                [
                    "locomo-temporal-rich",
                    "locomo-routing-owner-wording-gap",
                    "locomo-routing-owner-history-gap",
                    "locomo-abstention-rich",
                ],
            )
            self.assertIn("- Comparison artifact verification: `ok`", report_text)
            self.assertIn("Visible delta questions", report_text)
            self.assertIn("## Question Evidence", report_text)
            self.assertIn("locomo-multihop-rich", report_text)
            self.assertIn("latency delta `", report_text)
            self.assertIn("Kestrel Node locker code is 4182.", report_text)
            self.assertIn("ZMem Benchmark Comparison", html_text)
            self.assertNotIn("Stable Miss Spotlight", html_text)
            self.assertIn("locomo-multihop-rich", html_text)
            self.assertIn("Question Evidence", html_text)
            self.assertIn("Retrieved evidence +/-", html_text)
            self.assertIn("Kestrel Node locker code is 4182.", html_text)

    def test_cli_richer_standalone_comparison_reopen_preserves_stable_miss_evidence_from_another_cwd(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                run_longmemeval_benchmark,
                "analysis",
                (1, 7, 0),
                (),
                (
                    "Blue Finch deploy target is Staging.",
                ),
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                run_locomo_benchmark,
                "dev",
                (1, 4, 0),
                (),
                (
                    "Kestrel Node locker code is 4182.",
                ),
            ),
        )

        for benchmark, dataset_writer, runner, split, expected_summary, stable_miss_ids, evidence_texts in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                fts = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-rich-reopen-a",
                    retrieval_mode="fts",
                )
                multihop = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-rich-reopen-b",
                    retrieval_mode="fts-multihop",
                )

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    comparison = self._main_json(
                        [
                            "bench",
                            "compare",
                            os.path.relpath(fts["result_path"], other_cwd),
                            os.path.relpath(multihop["result_path"], other_cwd),
                            "--out",
                            os.path.relpath(compare_out, other_cwd),
                        ]
                    )
                    report = self._main_json(["bench", "report", comparison["comparison_path"]])
                    dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
                finally:
                    os.chdir(previous_cwd)

                comparison_path = Path(comparison["comparison_path"])
                if not comparison_path.is_absolute():
                    comparison_path = (other_cwd / comparison_path).resolve()
                report_path = Path(report["report_path"])
                if not report_path.is_absolute():
                    report_path = (other_cwd / report_path).resolve()
                dashboard_path = Path(dashboard["dashboard_path"])
                if not dashboard_path.is_absolute():
                    dashboard_path = (other_cwd / dashboard_path).resolve()

                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                report_text = report_path.read_text(encoding="utf-8")
                dashboard_html = dashboard_path.read_text(encoding="utf-8")
                stored_paths = [run["path"] for run in comparison_payload["runs"]]

                self.assertTrue(comparison["ok"])
                self.assertTrue(all(not Path(path).is_absolute() for path in stored_paths))
                self.assertEqual(report["artifact_type"], "comparison")
                self.assertEqual(report["verification_status"], "ok")
                self.assertEqual(report["summary"]["benchmark"], benchmark)
                self.assertEqual(report["summary"]["dataset"], str(dataset))
                self.assertEqual(report["summary"]["split"], split)
                self.assertEqual(report["summary"]["question_summary"], comparison_payload["question_summary"])
                self.assertEqual(dashboard["artifact_type"], "comparison")
                self.assertTrue(dashboard["ok"])
                self.assertEqual(dashboard["summary"]["benchmark"], benchmark)
                self.assertEqual(dashboard["summary"]["dataset"], str(dataset))
                self.assertEqual(dashboard["summary"]["split"], split)
                self.assertEqual(dashboard["summary"]["question_summary"], comparison_payload["question_summary"])
                self.assertEqual(
                    (
                        comparison_payload["question_summary"]["visible_delta_question_count"],
                        comparison_payload["question_summary"]["stable_wins"]["count"],
                        comparison_payload["question_summary"]["stable_misses"]["count"],
                    ),
                    expected_summary,
                )
                self.assertEqual(
                    comparison_payload["question_summary"]["stable_misses"]["question_ids"],
                    list(stable_miss_ids),
                )
                self.assertIn("- Comparison artifact verification: `ok`", report_text)
                self.assertIn(str(dataset), report_text)
                self.assertIn(str(dataset), dashboard_html)
                self.assertIn(split, report_text)
                self.assertIn(split, dashboard_html)
                self.assertNotIn("Stable Miss Spotlight", report_text)
                self.assertNotIn("Stable Miss Spotlight", dashboard_html)
                for evidence_text in evidence_texts:
                    self.assertIn(evidence_text, report_text)
                    self.assertIn(evidence_text, dashboard_html)

    def test_comparison_dashboard_surfaces_failed_verification_summary_when_comparison_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="tampered-comparison-dashboard")
            comparison_path = self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"])
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["question_summary"]["stable_wins"]["count"] = 999
            comparison["comparison_hash"] = sha256_text(
                stable_json({key: value for key, value in comparison.items() if key != "comparison_hash"})
            )
            comparison_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            dashboard = render_benchmark_dashboard(comparison_path)
            html_text = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")

            self.assertEqual(dashboard["artifact_type"], "comparison")
            self.assertIn("Comparison Failed Checks", html_text)
            self.assertIn("reconstructed_payload", html_text)
            self.assertIn(">failed<", html_text)

    def test_longmemeval_report_surfaces_temporal_update_and_conflict_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            result = run_longmemeval_benchmark(
                tmp_path / "bench",
                dataset,
                "analysis",
                seed=0,
                run_id="longmemeval-analysis-report",
            )

            report_text = Path(result["report_path"]).read_text(encoding="utf-8")

            self.assertIn("### temporal_reasoning", report_text)
            self.assertIn("### knowledge_update", report_text)
            self.assertIn("### current_conflict_abstention", report_text)
            self.assertIn("- Should abstain: `true`", report_text)
            self.assertIn("- Supporting evidence:", report_text)
            self.assertIn("- Outcome reason:", report_text)
            self.assertIn("- Query: `deploy target`", report_text)
            self.assertIn("- Final answer: `Production.`", report_text)
            self.assertIn("- Query: `What deploy target follows the Blue Finch release note now?`", report_text)
            self.assertIn("- Outcome reason: `correct_supported_answer`", report_text)
            self.assertIn("- Query: `What did Blue Finch deploy to before it moved to Production?`", report_text)
            self.assertIn("- Final answer: `Staging.`", report_text)
            self.assertIn("- Outcome reason: `correct_supported_answer`", report_text)
            self.assertIn("- Query: `Who owns routing now?`", report_text)
            self.assertIn("Escalation contact changed to Rowan.", report_text)
            self.assertIn("- Query: `Who's on point for the status page now?`", report_text)
            self.assertIn("- Final answer: `Blair.`", report_text)
            self.assertIn("- Outcome reason: `correct_supported_answer`", report_text)
            self.assertEqual(result["summary"]["category_summaries"]["knowledge_update"]["accuracy"], 1.0)
            self.assertEqual(
                result["summary"]["category_summaries"]["knowledge_update"]["failure_reason_counts"],
                {},
            )

    def test_longmemeval_budget_constrained_run_surfaces_budget_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            result = run_longmemeval_benchmark(
                tmp_path / "bench",
                dataset,
                "analysis",
                seed=0,
                run_id="longmemeval-budget-report",
                retrieval_mode="fts",
                context_budget_tokens=200,
            )

            result_payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
            history_question_payload = next(
                question
                for question in result_payload["questions"]
                if question["question_id"] == "lme-knowledge-update-history-wording-gap"
            )
            stale_decoy_question_payload = next(
                question
                for question in result_payload["questions"]
                if question["question_id"] == "lme-knowledge-update-stale-decoy"
            )
            temporal_question_payload = next(
                question
                for question in result_payload["questions"]
                if question["question_id"] == "lme-temporal-change-when"
            )
            report_text = Path(result["report_path"]).read_text(encoding="utf-8")

            self.assertEqual(result_payload["context_budget_tokens"], 200)
            self.assertEqual(result_payload["summary"]["budget_dropped_memory_count"], 3)
            self.assertEqual(history_question_payload["metrics"]["context_budget_tokens"], 200)
            self.assertEqual(history_question_payload["metrics"]["budget_dropped_count"], 1)
            self.assertEqual(history_question_payload["metrics"]["packed_context_tokens"], 124)
            self.assertEqual(history_question_payload["metrics"]["available_context_tokens"], 247)
            self.assertEqual(len(history_question_payload["budget_dropped_memory_ids"]), 1)
            self.assertEqual(
                [memory["content"] for memory in history_question_payload["budget_dropped_memories"]],
                ["Blue Finch deploy target changed to Production."],
            )
            self.assertEqual(stale_decoy_question_payload["metrics"]["budget_dropped_count"], 1)
            self.assertEqual(
                [memory["content"] for memory in stale_decoy_question_payload["budget_dropped_memories"]],
                ["The previous deploy target was Staging."],
            )
            self.assertEqual(temporal_question_payload["metrics"]["budget_dropped_count"], 1)
            self.assertEqual(
                [memory["content"] for memory in temporal_question_payload["budget_dropped_memories"]],
                ["On Monday, the deployment approver was Noor."],
            )
            self.assertIn("- Context budget tokens: `200`", report_text)
            self.assertIn("- Budget-dropped memories: `3`", report_text)
            self.assertIn("- Budget-dropped memory ids:", report_text)
            self.assertIn("Blue Finch deploy target changed to Production.", report_text)
            self.assertIn("The previous deploy target was Staging.", report_text)
            self.assertIn("On Monday, the deployment approver was Noor.", report_text)

    def test_longmemeval_temporal_matrix_reflects_recovered_shift_gap_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_temporal_stable_miss_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="longmemeval-temporal-stable-miss",
            )

            matrix_path = Path(matrix["matrix_path"])
            report = render_benchmark_report(matrix_path)
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")

            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 0,
                    "question_ids": [],
                },
                "stable_wins": {
                    "count": 2,
                    "question_ids": ["lme-temporal-change-when", "lme-temporal-history-shift-gap"],
                },
            }
            recovered_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "lme-temporal-history-shift-gap"
            )

            self.assertEqual(matrix["question_summary"], expected_question_summary)
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(all(run["correct"] is True for run in recovered_question["runs"]))
            self.assertTrue(
                all(run["outcome_reason"] == "correct_supported_answer" for run in recovered_question["runs"])
            )
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["retrieved_memories"]]
                    == [
                        "Status page shift notes live in docs/status.md.",
                        "The infra channel handled the opening ping.",
                        "Avery covered the overnight rotation.",
                    ]
                    for run in recovered_question["runs"]
                )
            )
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["injected_memories"]]
                    == [
                        "Avery covered the overnight rotation.",
                        "Status page shift notes live in docs/status.md.",
                    ]
                    for run in recovered_question["runs"]
                )
            )
            self.assertTrue(all(run["withheld_memories"] == [] for run in recovered_question["runs"]))
            self.assertTrue(all(run["budget_dropped_memories"] == [] for run in recovered_question["runs"]))
            self.assertIn("Recovered Stable Win Spotlight", report_text)
            self.assertIn("Recovered Stable Win Spotlight", dashboard_html)
            self.assertIn("Recovered Stable Win Spotlight", page_html)
            self.assertNotIn("Stable Miss Spotlight", report_text)
            self.assertNotIn("Stable Miss Spotlight", dashboard_html)
            self.assertNotIn("Stable Miss Spotlight", page_html)
            self.assertIn("lme-temporal-history-shift-gap", report_text)
            self.assertIn("lme-temporal-history-shift-gap", dashboard_html)
            self.assertIn("lme-temporal-history-shift-gap", page_html)
            self.assertIn("Avery covered the overnight rotation.", report_text)
            self.assertIn("Avery covered the overnight rotation.", dashboard_html)
            self.assertIn("Avery covered the overnight rotation.", page_html)

    def test_budget_constrained_longmemeval_matrix_preserves_budget_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="budget-matrix",
                context_budget_tokens=200,
            )

            report = render_benchmark_report(Path(matrix["matrix_path"]))
            dashboard = render_benchmark_dashboard(Path(matrix["matrix_path"]))
            page = render_public_benchmark_page(Path(matrix["matrix_path"]))
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")

            self.assertEqual(matrix["context_budget_tokens"], 200)
            self.assertEqual(report["summary"]["context_budget_tokens"], 200)
            self.assertEqual(page["summary"]["context_budget_tokens"], 200)
            self.assertEqual(
                matrix["summary"]["question_summary"],
                {
                    "question_count": 8,
                    "visible_delta_question_count": 3,
                    "stable_misses": {
                        "count": 0,
                        "question_ids": [],
                    },
                    "stable_wins": {
                        "count": 5,
                        "question_ids": [
                            "lme-temporal-change-when",
                            "lme-knowledge-update-current-target",
                            "lme-knowledge-update-ambiguous-restatement",
                            "lme-routing-owner-wording-gap",
                            "lme-current-conflict-abstain",
                        ],
                    },
                },
            )
            self.assertIn("- Context budget tokens: `200`", report_text)
            self.assertIn("- Budget-dropped evidence +/-:", report_text)
            self.assertIn("Budget dropped", dashboard_html)
            self.assertIn("Budget-dropped", page_html)

    def test_cli_budget_constrained_longmemeval_matrix_reopen_preserves_budget_dropped_evidence_from_another_cwd(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()

            os.chdir(tmp_path)
            try:
                matrix = run_benchmark_matrix(
                    Path("bench"),
                    "longmemeval",
                    dataset=dataset,
                    split="analysis",
                    seed=0,
                    run_id="longmemeval-budget-matrix",
                    context_budget_tokens=200,
                )
            finally:
                os.chdir(previous_cwd)

            matrix_path = Path(matrix["matrix_path"])
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            expected_mode_proofs = matrix["summary"]["mode_proofs"]
            expected_question_summary = {
                "question_count": 8,
                "visible_delta_question_count": 3,
                "stable_misses": {
                    "count": 0,
                    "question_ids": [],
                },
                "stable_wins": {
                    "count": 5,
                    "question_ids": [
                        "lme-temporal-change-when",
                        "lme-knowledge-update-current-target",
                        "lme-knowledge-update-ambiguous-restatement",
                        "lme-routing-owner-wording-gap",
                        "lme-current-conflict-abstain",
                    ],
                },
            }
            expected_budget_context_question_ids = [
                "lme-temporal-change-when",
                "lme-knowledge-update-stale-decoy",
                "lme-knowledge-update-history-wording-gap",
            ]
            changed_question = next(
                question
                for question in matrix_payload["comparison"]["questions"]
                if question["question_id"] == "lme-knowledge-update-release-note-decoy"
            )
            resolved_matrix_path = matrix_path.resolve()
            resolved_matrix_dir = resolved_matrix_path.parent

            try:
                os.chdir(other_cwd)
                report_output = self._main_text(["bench", "report", str(resolved_matrix_path), "--summary-only"])
                dashboard_output = self._main_text(["bench", "dashboard", str(resolved_matrix_path), "--summary-only"])
                page_output = self._main_text(["bench", "public-page", str(resolved_matrix_dir), "--summary-only"])
                report = self._main_json(["bench", "report", str(resolved_matrix_path)])
                dashboard = self._main_json(["bench", "dashboard", str(resolved_matrix_path)])
                page = self._main_json(["bench", "public-page", str(resolved_matrix_dir)])
            finally:
                os.chdir(previous_cwd)

            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            page_path = Path(page["page_path"])
            if not page_path.is_absolute():
                page_path = (other_cwd / page_path).resolve()

            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            page_html = page_path.read_text(encoding="utf-8")

            self.assertEqual(matrix_payload["context_budget_tokens"], 200)
            self.assertEqual(matrix_payload["comparison_path"], "benchmark-comparison.json")
            self.assertEqual(matrix_payload["report_path"], "matrix-report.md")
            self.assertEqual(
                matrix_payload["proof"]["input_result_paths"],
                [f"{mode}/benchmark-result.json" for mode in BENCHMARK_RETRIEVAL_MODES],
            )
            self.assertTrue(all(not Path(run["result_path"]).is_absolute() for run in matrix_payload["mode_runs"]))
            self.assertEqual(matrix_payload["question_summary"], expected_question_summary)
            self.assertEqual(report["artifact_type"], "matrix")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["comparison_verification_status"], "ok")
            self.assertEqual(report["summary"]["context_budget_tokens"], 200)
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(report["summary"]["budget_context_question_count"], 3)
            self.assertEqual(report["summary"]["budget_context_question_ids"], expected_budget_context_question_ids)
            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["matrix_path"], str(resolved_matrix_path))
            self.assertEqual(dashboard["summary"]["context_budget_tokens"], 200)
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(dashboard["summary"]["budget_context_question_count"], 3)
            self.assertEqual(dashboard["summary"]["budget_context_question_ids"], expected_budget_context_question_ids)
            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["context_budget_tokens"], 200)
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(page["summary"]["budget_context_question_count"], 3)
            self.assertEqual(page["summary"]["budget_context_question_ids"], expected_budget_context_question_ids)
            self.assertEqual(page["summary"]["mode_proofs"], expected_mode_proofs)
            self.assertEqual(changed_question["question_id"], "lme-knowledge-update-release-note-decoy")

            expected_budget_context_line = (
                "Budget-dropped stable context ids: "
                "lme-temporal-change-when, lme-knowledge-update-stale-decoy, "
                "lme-knowledge-update-history-wording-gap"
            )
            self.assertIn(expected_budget_context_line, report_output)
            self.assertIn(expected_budget_context_line, dashboard_output)
            self.assertIn(expected_budget_context_line, page_output)
            self.assertIn("- Context budget tokens: `200`", report_text)
            self.assertIn("- Budget-dropped evidence +/-:", report_text)
            self.assertIn("Budget dropped", dashboard_html)
            self.assertIn("Budget-dropped", page_html)
            self.assertIn("Question Evidence", page_html)
            self.assertIn("Question Evidence", dashboard_html)
            self.assertIn("Retrieval latency delta", dashboard_html)
            self.assertIn("Retrieval latency delta", page_html)
            self.assertIn("latency delta ", dashboard_html)
            self.assertIn("latency delta ", page_html)
            self.assertIn(changed_question["question_id"], report_text)
            self.assertIn(changed_question["question_id"], dashboard_html)
            self.assertIn(changed_question["question_id"], page_html)

            for proof in expected_mode_proofs:
                self.assertIn(proof["result_hash"], report_text)
                self.assertIn(proof["aggregate_merkle_root"], report_text)
                self.assertIn(proof["result_hash"], dashboard_html)
                self.assertIn(proof["aggregate_merkle_root"], dashboard_html)
                self.assertIn(proof["result_hash"], page_html)
                self.assertIn(proof["aggregate_merkle_root"], page_html)

            self._assert_rendered_mode_proof_hops(expected_mode_proofs, dashboard_html)
            self._assert_rendered_mode_proof_hops(expected_mode_proofs, page_html)

    def test_cli_longmemeval_temporal_matrix_reopen_reflects_recovered_shift_gap_truth(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_temporal_stable_miss_jsonl(tmp_path)
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()

            os.chdir(tmp_path)
            try:
                matrix = run_benchmark_matrix(
                    Path("bench"),
                    "longmemeval",
                    dataset=dataset,
                    split="analysis",
                    seed=0,
                    run_id="longmemeval-temporal-stable-miss-reopen",
                )
            finally:
                os.chdir(previous_cwd)

            matrix_path = Path(matrix["matrix_path"])
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            resolved_matrix_path = matrix_path.resolve()
            resolved_matrix_dir = resolved_matrix_path.parent
            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 0,
                    "question_ids": [],
                },
                "stable_wins": {
                    "count": 2,
                    "question_ids": ["lme-temporal-change-when", "lme-temporal-history-shift-gap"],
                },
            }

            try:
                os.chdir(other_cwd)
                verify = self._main_json(["bench", "verify", str(resolved_matrix_path)])
                report_output = self._main_text(["bench", "report", str(resolved_matrix_path), "--summary-only"])
                dashboard_output = self._main_text(["bench", "dashboard", str(resolved_matrix_path), "--summary-only"])
                page_output = self._main_text(["bench", "public-page", str(resolved_matrix_dir), "--summary-only"])
                report = self._main_json(["bench", "report", str(resolved_matrix_path)])
                dashboard = self._main_json(["bench", "dashboard", str(resolved_matrix_path)])
                page = self._main_json(["bench", "public-page", str(resolved_matrix_dir)])
            finally:
                os.chdir(previous_cwd)

            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            page_path = Path(page["page_path"])
            if not page_path.is_absolute():
                page_path = (other_cwd / page_path).resolve()

            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            page_html = page_path.read_text(encoding="utf-8")

            self.assertTrue(verify["ok"])
            self.assertEqual(verify["artifact_type"], "matrix")
            self.assertEqual(matrix_payload["question_summary"], expected_question_summary)
            self.assertEqual(report["artifact_type"], "matrix")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            expected_spotlight_line = (
                "Recovered stable win spotlight ids: "
                "lme-temporal-change-when, lme-temporal-history-shift-gap"
            )
            self.assertIn(expected_spotlight_line, report_output)
            self.assertIn(expected_spotlight_line, dashboard_output)
            self.assertIn(expected_spotlight_line, page_output)
            self.assertIn("Recovered Stable Win Spotlight", report_text)
            self.assertIn("Recovered Stable Win Spotlight", dashboard_html)
            self.assertIn("Recovered Stable Win Spotlight", page_html)
            self.assertNotIn("Stable Miss Spotlight", report_text)
            self.assertNotIn("Stable Miss Spotlight", dashboard_html)
            self.assertNotIn("Stable Miss Spotlight", page_html)
            self.assertIn("lme-temporal-history-shift-gap", report_text)
            self.assertIn("lme-temporal-history-shift-gap", dashboard_html)
            self.assertIn("lme-temporal-history-shift-gap", page_html)
            self.assertIn("Avery covered the overnight rotation.", report_text)
            self.assertIn("Avery covered the overnight rotation.", dashboard_html)
            self.assertIn("Avery covered the overnight rotation.", page_html)

    def test_budget_constrained_longmemeval_stable_miss_matrix_preserves_stable_miss_and_budget_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_stable_miss_budget_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="longmemeval-stable-miss-budget",
                context_budget_tokens=200,
            )

            matrix_path = Path(matrix["matrix_path"])
            report = render_benchmark_report(matrix_path)
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")

            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["lme-routing-owner-history-gap"],
                },
                "stable_wins": {
                    "count": 1,
                    "question_ids": ["lme-temporal-change-when"],
                },
            }
            stable_miss_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "lme-routing-owner-history-gap"
            )
            budget_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "lme-temporal-change-when"
            )

            self.assertEqual(matrix["context_budget_tokens"], 200)
            self.assertEqual(matrix["question_summary"], expected_question_summary)
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(all(run["correct"] is False for run in stable_miss_question["runs"]))
            self.assertTrue(
                all(run["outcome_reason"] == "false_abstention_missing_retrieval" for run in stable_miss_question["runs"])
            )
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["retrieved_memories"]] == ["Routing checklist lives in /srv/runbook."]
                    for run in stable_miss_question["runs"]
                )
            )
            self.assertTrue(all(run["withheld_memories"] == [] for run in stable_miss_question["runs"]))
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["budget_dropped_memories"]]
                    == ["On Monday, the deployment approver was Noor."]
                    for run in budget_question["runs"]
                )
            )
            self.assertIn("## Stable Miss Spotlight", report_text)
            self.assertIn("lme-routing-owner-history-gap", report_text)
            self.assertIn("Routing checklist lives in /srv/runbook.", report_text)
            self.assertIn("false_abstention_missing_retrieval=4", report_text)
            self.assertIn("## Budget-Dropped Stable Context", report_text)
            self.assertIn("On Monday, the deployment approver was Noor.", report_text)
            self.assertIn("Budget-Dropped Stable Context", dashboard_html)
            self.assertIn("Stable Miss Spotlight", dashboard_html)
            self.assertIn("lme-routing-owner-history-gap", dashboard_html)
            self.assertIn("Routing checklist lives in /srv/runbook.", dashboard_html)
            self.assertIn("Budget dropped", dashboard_html)
            self.assertIn("On Monday, the deployment approver was Noor.", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context", page_html)
            self.assertIn("Stable Miss Spotlight", page_html)
            self.assertIn("lme-routing-owner-history-gap", page_html)
            self.assertIn("Routing checklist lives in /srv/runbook.", page_html)
            self.assertIn("Budget-dropped", page_html)
            self.assertIn("On Monday, the deployment approver was Noor.", page_html)

    def test_cli_budget_constrained_longmemeval_stable_miss_matrix_reopen_preserves_stable_miss_and_budget_dropped_evidence(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_stable_miss_budget_jsonl(tmp_path)
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()

            os.chdir(tmp_path)
            try:
                matrix = run_benchmark_matrix(
                    Path("bench"),
                    "longmemeval",
                    dataset=dataset,
                    split="analysis",
                    seed=0,
                    run_id="longmemeval-stable-miss-budget-reopen",
                    context_budget_tokens=200,
                )
            finally:
                os.chdir(previous_cwd)

            matrix_path = Path(matrix["matrix_path"])
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            resolved_matrix_path = matrix_path.resolve()
            resolved_matrix_dir = resolved_matrix_path.parent
            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["lme-routing-owner-history-gap"],
                },
                "stable_wins": {
                    "count": 1,
                    "question_ids": ["lme-temporal-change-when"],
                },
            }

            try:
                os.chdir(other_cwd)
                verify = self._main_json(["bench", "verify", str(resolved_matrix_path)])
                report = self._main_json(["bench", "report", str(resolved_matrix_path)])
                dashboard = self._main_json(["bench", "dashboard", str(resolved_matrix_path)])
                page = self._main_json(["bench", "public-page", str(resolved_matrix_dir)])
            finally:
                os.chdir(previous_cwd)

            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            page_path = Path(page["page_path"])
            if not page_path.is_absolute():
                page_path = (other_cwd / page_path).resolve()

            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            page_html = page_path.read_text(encoding="utf-8")

            self.assertTrue(verify["ok"])
            self.assertEqual(verify["artifact_type"], "matrix")
            self.assertEqual(matrix_payload["question_summary"], expected_question_summary)
            self.assertEqual(report["artifact_type"], "matrix")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertIn("Stable Miss Spotlight", report_text)
            self.assertIn("lme-routing-owner-history-gap", report_text)
            self.assertIn("Routing checklist lives in /srv/runbook.", report_text)
            self.assertIn("Budget-Dropped Stable Context", report_text)
            self.assertIn("On Monday, the deployment approver was Noor.", report_text)
            self.assertIn("Budget-Dropped Stable Context", dashboard_html)
            self.assertIn("Stable Miss Spotlight", dashboard_html)
            self.assertIn("lme-routing-owner-history-gap", dashboard_html)
            self.assertIn("Routing checklist lives in /srv/runbook.", dashboard_html)
            self.assertIn("On Monday, the deployment approver was Noor.", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context", page_html)
            self.assertIn("Stable Miss Spotlight", page_html)
            self.assertIn("lme-routing-owner-history-gap", page_html)
            self.assertIn("Routing checklist lives in /srv/runbook.", page_html)
            self.assertIn("On Monday, the deployment approver was Noor.", page_html)

    def test_budget_constrained_locomo_temporal_stable_miss_matrix_preserves_stable_miss_and_budget_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_temporal_stable_miss_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="locomo-temporal-stable-miss",
                context_budget_tokens=200,
            )

            matrix_path = Path(matrix["matrix_path"])
            report = render_benchmark_report(matrix_path)
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")

            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["locomo-temporal-now-budget-control"],
                },
                "stable_wins": {
                    "count": 1,
                    "question_ids": ["locomo-temporal-change-when"],
                },
            }
            stable_miss_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "locomo-temporal-now-budget-control"
            )
            budget_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "locomo-temporal-change-when"
            )

            self.assertEqual(matrix["context_budget_tokens"], 200)
            self.assertEqual(matrix["question_summary"], expected_question_summary)
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(all(run["correct"] is False for run in stable_miss_question["runs"]))
            self.assertTrue(
                all(run["outcome_reason"] == "false_abstention_missing_injection" for run in stable_miss_question["runs"])
            )
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["retrieved_memories"]]
                    == [
                        "user: Mira moved her design review to Thursday.",
                        "user: The review moved again to Friday afternoon.",
                    ]
                    for run in stable_miss_question["runs"]
                )
            )
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["injected_memories"]]
                    == ["user: Mira moved her design review to Thursday."]
                    for run in stable_miss_question["runs"]
                )
            )
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["budget_dropped_memories"]]
                    == ["user: The review moved again to Friday afternoon."]
                    for run in stable_miss_question["runs"]
                )
            )
            self.assertTrue(all(run["correct"] is True for run in budget_question["runs"]))
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["budget_dropped_memories"]]
                    == ["user: On Monday, the deployment approver was Noor."]
                    for run in budget_question["runs"]
                )
            )
            self.assertIn("## Stable Miss Spotlight", report_text)
            self.assertIn("locomo-temporal-now-budget-control", report_text)
            self.assertIn("user: The review moved again to Friday afternoon.", report_text)
            self.assertIn("false_abstention_missing_injection=4", report_text)
            self.assertIn("## Budget-Dropped Stable Context", report_text)
            self.assertIn("user: On Monday, the deployment approver was Noor.", report_text)
            self.assertIn("Budget-Dropped Stable Context", dashboard_html)
            self.assertIn("Stable Miss Spotlight", dashboard_html)
            self.assertIn("locomo-temporal-now-budget-control", dashboard_html)
            self.assertIn("user: The review moved again to Friday afternoon.", dashboard_html)
            self.assertIn("Budget-dropped", dashboard_html)
            self.assertIn("user: On Monday, the deployment approver was Noor.", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context", page_html)
            self.assertIn("Stable Miss Spotlight", page_html)
            self.assertIn("locomo-temporal-now-budget-control", page_html)
            self.assertIn("user: The review moved again to Friday afternoon.", page_html)
            self.assertIn("Budget-dropped", page_html)
            self.assertIn("user: On Monday, the deployment approver was Noor.", page_html)

    def test_cli_budget_constrained_locomo_temporal_stable_miss_matrix_reopen_preserves_stable_miss_and_budget_dropped_evidence(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_temporal_stable_miss_jsonl(tmp_path)
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()

            os.chdir(tmp_path)
            try:
                matrix = run_benchmark_matrix(
                    Path("bench"),
                    "locomo",
                    dataset=dataset,
                    split="analysis",
                    seed=0,
                    run_id="locomo-temporal-stable-miss-reopen",
                    context_budget_tokens=200,
                )
            finally:
                os.chdir(previous_cwd)

            matrix_path = Path(matrix["matrix_path"])
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            resolved_matrix_path = matrix_path.resolve()
            resolved_matrix_dir = resolved_matrix_path.parent
            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["locomo-temporal-now-budget-control"],
                },
                "stable_wins": {
                    "count": 1,
                    "question_ids": ["locomo-temporal-change-when"],
                },
            }

            try:
                os.chdir(other_cwd)
                verify = self._main_json(["bench", "verify", str(resolved_matrix_path)])
                report = self._main_json(["bench", "report", str(resolved_matrix_path)])
                dashboard = self._main_json(["bench", "dashboard", str(resolved_matrix_path)])
                page = self._main_json(["bench", "public-page", str(resolved_matrix_dir)])
            finally:
                os.chdir(previous_cwd)

            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            page_path = Path(page["page_path"])
            if not page_path.is_absolute():
                page_path = (other_cwd / page_path).resolve()

            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            page_html = page_path.read_text(encoding="utf-8")

            self.assertTrue(verify["ok"])
            self.assertEqual(verify["artifact_type"], "matrix")
            self.assertEqual(matrix_payload["question_summary"], expected_question_summary)
            self.assertEqual(report["artifact_type"], "matrix")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertIn("Stable Miss Spotlight", report_text)
            self.assertIn("locomo-temporal-now-budget-control", report_text)
            self.assertIn("user: The review moved again to Friday afternoon.", report_text)
            self.assertIn("Budget-Dropped Stable Context", report_text)
            self.assertIn("user: On Monday, the deployment approver was Noor.", report_text)
            self.assertIn("Budget-Dropped Stable Context", dashboard_html)
            self.assertIn("Stable Miss Spotlight", dashboard_html)
            self.assertIn("locomo-temporal-now-budget-control", dashboard_html)
            self.assertIn("user: The review moved again to Friday afternoon.", dashboard_html)
            self.assertIn("user: On Monday, the deployment approver was Noor.", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context", page_html)
            self.assertIn("Stable Miss Spotlight", page_html)
            self.assertIn("locomo-temporal-now-budget-control", page_html)
            self.assertIn("user: The review moved again to Friday afternoon.", page_html)
            self.assertIn("user: On Monday, the deployment approver was Noor.", page_html)

    def test_cli_budget_constrained_locomo_temporal_stable_miss_matrix_comparison_surfaces_mode_stable_ids_and_evidence(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_temporal_stable_miss_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()
            first = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="locomo-temporal-compare-a",
                context_budget_tokens=200,
            )
            second = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="locomo-temporal-compare-b",
                context_budget_tokens=200,
            )

            try:
                os.chdir(other_cwd)
                summary_output = self._main_text(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--summary-only",
                    ]
                )
                comparison = self._main_json(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--out",
                        os.path.relpath(compare_out, other_cwd),
                    ]
                )
                report_output = self._main_text(["bench", "report", comparison["comparison_path"], "--summary-only"])
                dashboard_output = self._main_text(
                    ["bench", "dashboard", comparison["comparison_path"], "--summary-only"]
                )
                report = self._main_json(["bench", "report", comparison["comparison_path"]])
                dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
            finally:
                os.chdir(previous_cwd)

            comparison_path = Path(comparison["comparison_path"])
            if not comparison_path.is_absolute():
                comparison_path = (other_cwd / comparison_path).resolve()
            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()

            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            anchor_mode = next(
                mode for mode in comparison_payload["mode_comparisons"] if mode["retrieval_mode"] == "fts"
            )
            expected_anchor_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["locomo-temporal-now-budget-control"],
                },
                "stable_wins": {
                    "count": 1,
                    "question_ids": ["locomo-temporal-change-when"],
                },
            }
            expected_mode_line = (
                "Mode comparison fts: verification=ok visible_deltas=0 stable_wins=1 stable_misses=1"
            )
            expected_miss_ids_line = (
                "Mode comparison fts stable miss ids: locomo-temporal-now-budget-control"
            )
            expected_win_ids_line = "Mode comparison fts stable win ids: locomo-temporal-change-when"

            self.assertEqual(anchor_mode["question_summary"], expected_anchor_summary)
            for output in (summary_output, report_output, dashboard_output):
                self.assertIn(expected_mode_line, output)
                self.assertIn(expected_miss_ids_line, output)
                self.assertIn(expected_win_ids_line, output)

            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertEqual(dashboard["summary"]["mode_comparisons"][0]["verification_status"], "ok")
            self.assertIn("Stable miss question ids: `locomo-temporal-now-budget-control`", report_text)
            self.assertIn("user: The review moved again to Friday afternoon.", report_text)
            self.assertIn("user: On Monday, the deployment approver was Noor.", report_text)
            self.assertIn("Stable Miss Spotlight: fts", dashboard_html)
            self.assertIn("locomo-temporal-now-budget-control", dashboard_html)
            self.assertIn("user: The review moved again to Friday afternoon.", dashboard_html)
            self.assertIn("user: On Monday, the deployment approver was Noor.", dashboard_html)

    def test_cli_compare_matrices_preserves_recovered_stable_win_spotlight_in_persisted_artifacts(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_temporal_stable_miss_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()
            first = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="lme-recovered-win-compare-a",
            )
            second = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="lme-recovered-win-compare-b",
            )

            try:
                os.chdir(other_cwd)
                summary_output = self._main_text(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--summary-only",
                    ]
                )
                comparison = self._main_json(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--out",
                        os.path.relpath(compare_out, other_cwd),
                    ]
                )
                report_output = self._main_text(["bench", "report", comparison["comparison_path"], "--summary-only"])
                dashboard_output = self._main_text(
                    ["bench", "dashboard", comparison["comparison_path"], "--summary-only"]
                )
                report = self._main_json(["bench", "report", comparison["comparison_path"]])
                dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
            finally:
                os.chdir(previous_cwd)

            comparison_path = Path(comparison["comparison_path"])
            if not comparison_path.is_absolute():
                comparison_path = (other_cwd / comparison_path).resolve()
            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()

            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            anchor_mode = next(
                mode for mode in comparison_payload["mode_comparisons"] if mode["retrieval_mode"] == "fts"
            )
            expected_anchor_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 0,
                    "question_ids": [],
                },
                "stable_wins": {
                    "count": 2,
                    "question_ids": ["lme-temporal-change-when", "lme-temporal-history-shift-gap"],
                },
            }
            expected_mode_line = (
                "Mode comparison fts: verification=ok visible_deltas=0 stable_wins=2 stable_misses=0"
            )
            expected_win_ids_line = (
                "Mode comparison fts stable win ids: "
                "lme-temporal-change-when, lme-temporal-history-shift-gap"
            )

            self.assertEqual(anchor_mode["question_summary"], expected_anchor_summary)
            for output in (summary_output, report_output, dashboard_output):
                self.assertIn(expected_mode_line, output)
                self.assertIn(expected_win_ids_line, output)

            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertEqual(dashboard["summary"]["mode_comparisons"][0]["verification_status"], "ok")
            self.assertIn(
                "Stable win question ids: `lme-temporal-change-when, lme-temporal-history-shift-gap`",
                report_text,
            )
            self.assertIn("Recovered stable win `lme-temporal-history-shift-gap`", report_text)
            self.assertIn("Avery covered the overnight rotation.", report_text)
            self.assertIn("Recovered Stable Win Spotlight: fts", dashboard_html)
            self.assertIn("lme-temporal-history-shift-gap", dashboard_html)
            self.assertIn("Avery covered the overnight rotation.", dashboard_html)
            self.assertNotIn("<h2>Stable Miss Spotlight: fts</h2>", dashboard_html)

    def test_budget_constrained_locomo_stable_miss_matrix_preserves_stable_miss_and_budget_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_stable_miss_budget_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="locomo-stable-miss-budget",
                context_budget_tokens=200,
            )

            matrix_path = Path(matrix["matrix_path"])
            report = render_benchmark_report(matrix_path)
            dashboard = render_benchmark_dashboard(matrix_path)
            page = render_public_benchmark_page(matrix_path)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")

            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["locomo-routing-history-stable-miss"],
                },
                "stable_wins": {
                    "count": 1,
                    "question_ids": ["locomo-routing-now-budget-control"],
                },
            }
            stable_miss_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "locomo-routing-history-stable-miss"
            )
            budget_question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "locomo-routing-now-budget-control"
            )

            self.assertEqual(matrix["context_budget_tokens"], 200)
            self.assertEqual(matrix["question_summary"], expected_question_summary)
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(all(run["correct"] is False for run in stable_miss_question["runs"]))
            self.assertTrue(
                all(run["outcome_reason"] == "false_abstention_missing_retrieval" for run in stable_miss_question["runs"])
            )
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["retrieved_memories"]]
                    == ["user: Routing summary needs a weekly cleanup."]
                    for run in stable_miss_question["runs"]
                )
            )
            self.assertTrue(all(run["withheld_memories"] == [] for run in stable_miss_question["runs"]))
            self.assertTrue(all(run["correct"] is True for run in budget_question["runs"]))
            self.assertTrue(
                all(
                    [memory["content"] for memory in run["budget_dropped_memories"]]
                    == ["user: Earlier escalation contact was Jules."]
                    for run in budget_question["runs"]
                )
            )
            self.assertIn("## Stable Miss Spotlight", report_text)
            self.assertIn("locomo-routing-history-stable-miss", report_text)
            self.assertIn("user: Routing summary needs a weekly cleanup.", report_text)
            self.assertIn("false_abstention_missing_retrieval=4", report_text)
            self.assertIn("## Budget-Dropped Stable Context", report_text)
            self.assertIn("user: Earlier escalation contact was Jules.", report_text)
            self.assertIn("Budget-Dropped Stable Context", dashboard_html)
            self.assertIn("Stable Miss Spotlight", dashboard_html)
            self.assertIn("locomo-routing-history-stable-miss", dashboard_html)
            self.assertIn("user: Routing summary needs a weekly cleanup.", dashboard_html)
            self.assertIn("Budget dropped", dashboard_html)
            self.assertIn("user: Earlier escalation contact was Jules.", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context", page_html)
            self.assertIn("Stable Miss Spotlight", page_html)
            self.assertIn("locomo-routing-history-stable-miss", page_html)
            self.assertIn("user: Routing summary needs a weekly cleanup.", page_html)
            self.assertIn("Budget-dropped", page_html)
            self.assertIn("user: Earlier escalation contact was Jules.", page_html)

    def test_cli_budget_constrained_locomo_stable_miss_matrix_reopen_preserves_stable_miss_and_budget_dropped_evidence(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_stable_miss_budget_jsonl(tmp_path)
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()

            os.chdir(tmp_path)
            try:
                matrix = run_benchmark_matrix(
                    Path("bench"),
                    "locomo",
                    dataset=dataset,
                    split="analysis",
                    seed=0,
                    run_id="locomo-stable-miss-budget-reopen",
                    context_budget_tokens=200,
                )
            finally:
                os.chdir(previous_cwd)

            matrix_path = Path(matrix["matrix_path"])
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            resolved_matrix_path = matrix_path.resolve()
            resolved_matrix_dir = resolved_matrix_path.parent
            expected_question_summary = {
                "question_count": 2,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["locomo-routing-history-stable-miss"],
                },
                "stable_wins": {
                    "count": 1,
                    "question_ids": ["locomo-routing-now-budget-control"],
                },
            }

            try:
                os.chdir(other_cwd)
                verify = self._main_json(["bench", "verify", str(resolved_matrix_path)])
                report = self._main_json(["bench", "report", str(resolved_matrix_path)])
                dashboard = self._main_json(["bench", "dashboard", str(resolved_matrix_path)])
                page = self._main_json(["bench", "public-page", str(resolved_matrix_dir)])
            finally:
                os.chdir(previous_cwd)

            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            page_path = Path(page["page_path"])
            if not page_path.is_absolute():
                page_path = (other_cwd / page_path).resolve()

            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            page_html = page_path.read_text(encoding="utf-8")

            self.assertTrue(verify["ok"])
            self.assertEqual(verify["artifact_type"], "matrix")
            self.assertEqual(matrix_payload["question_summary"], expected_question_summary)
            self.assertEqual(report["artifact_type"], "matrix")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertIn("Stable Miss Spotlight", report_text)
            self.assertIn("locomo-routing-history-stable-miss", report_text)
            self.assertIn("user: Routing summary needs a weekly cleanup.", report_text)
            self.assertIn("Budget-Dropped Stable Context", report_text)
            self.assertIn("user: Earlier escalation contact was Jules.", report_text)
            self.assertIn("Budget-Dropped Stable Context", dashboard_html)
            self.assertIn("Stable Miss Spotlight", dashboard_html)
            self.assertIn("locomo-routing-history-stable-miss", dashboard_html)
            self.assertIn("user: Routing summary needs a weekly cleanup.", dashboard_html)
            self.assertIn("user: Earlier escalation contact was Jules.", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context", page_html)
            self.assertIn("Stable Miss Spotlight", page_html)
            self.assertIn("locomo-routing-history-stable-miss", page_html)
            self.assertIn("user: Routing summary needs a weekly cleanup.", page_html)
            self.assertIn("user: Earlier escalation contact was Jules.", page_html)

    def test_cli_budget_constrained_locomo_matrix_reopen_preserves_budget_dropped_evidence_from_another_cwd(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()

            os.chdir(tmp_path)
            try:
                matrix = run_benchmark_matrix(
                    Path("bench"),
                    "locomo",
                    dataset=dataset,
                    split="dev",
                    seed=0,
                    run_id="locomo-budget-matrix",
                    context_budget_tokens=200,
                )
            finally:
                os.chdir(previous_cwd)

            matrix_path = Path(matrix["matrix_path"])
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            expected_mode_proofs = matrix["summary"]["mode_proofs"]
            expected_question_summary = {
                "question_count": 5,
                "visible_delta_question_count": 2,
                "stable_misses": {
                    "count": 1,
                    "question_ids": ["locomo-temporal-rich"],
                },
                "stable_wins": {
                    "count": 2,
                    "question_ids": [
                        "locomo-routing-owner-wording-gap",
                        "locomo-abstention-rich",
                    ],
                },
            }
            budget_evidence = "The review moved again to Friday afternoon."
            stable_win_evidence = "Earlier escalation contact was Jules."
            expected_budget_context_question_ids = [
                "locomo-temporal-rich",
                "locomo-multihop-rich",
                "locomo-routing-owner-history-gap",
            ]
            changed_question = next(
                question
                for question in matrix_payload["comparison"]["questions"]
                if question["question_id"] == "locomo-temporal-rich"
            )
            resolved_matrix_path = matrix_path.resolve()
            resolved_matrix_dir = resolved_matrix_path.parent

            try:
                os.chdir(other_cwd)
                report_output = self._main_text(["bench", "report", str(resolved_matrix_path), "--summary-only"])
                dashboard_output = self._main_text(
                    ["bench", "dashboard", str(resolved_matrix_path), "--summary-only"]
                )
                page_output = self._main_text(["bench", "public-page", str(resolved_matrix_dir), "--summary-only"])
                report = self._main_json(
                    ["bench", "report", str(resolved_matrix_path)]
                )
                dashboard = self._main_json(
                    ["bench", "dashboard", str(resolved_matrix_path)]
                )
                page = self._main_json(
                    ["bench", "public-page", str(resolved_matrix_dir)]
                )
            finally:
                os.chdir(previous_cwd)

            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            page_path = Path(page["page_path"])
            if not page_path.is_absolute():
                page_path = (other_cwd / page_path).resolve()

            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            page_html = page_path.read_text(encoding="utf-8")

            self.assertEqual(matrix_payload["context_budget_tokens"], 200)
            self.assertEqual(matrix_payload["comparison_path"], "benchmark-comparison.json")
            self.assertEqual(matrix_payload["report_path"], "matrix-report.md")
            self.assertEqual(
                matrix_payload["proof"]["input_result_paths"],
                [f"{mode}/benchmark-result.json" for mode in BENCHMARK_RETRIEVAL_MODES],
            )
            self.assertTrue(
                all(not Path(run["result_path"]).is_absolute() for run in matrix_payload["mode_runs"])
            )
            self.assertEqual(matrix_payload["question_summary"], expected_question_summary)
            self.assertEqual(report["artifact_type"], "matrix")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["comparison_verification_status"], "ok")
            self.assertEqual(report["summary"]["context_budget_tokens"], 200)
            self.assertEqual(report["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(report["summary"]["budget_context_question_count"], 3)
            self.assertEqual(report["summary"]["budget_context_question_ids"], expected_budget_context_question_ids)
            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["matrix_path"], str(resolved_matrix_path))
            self.assertEqual(dashboard["summary"]["context_budget_tokens"], 200)
            self.assertEqual(dashboard["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(dashboard["summary"]["budget_context_question_count"], 3)
            self.assertEqual(
                dashboard["summary"]["budget_context_question_ids"],
                expected_budget_context_question_ids,
            )
            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["context_budget_tokens"], 200)
            self.assertEqual(page["summary"]["question_summary"], expected_question_summary)
            self.assertEqual(page["summary"]["budget_context_question_count"], 3)
            self.assertEqual(page["summary"]["budget_context_question_ids"], expected_budget_context_question_ids)
            self.assertEqual(page["summary"]["mode_proofs"], expected_mode_proofs)
            self.assertEqual(changed_question["question_id"], "locomo-temporal-rich")

            expected_budget_context_line = (
                "Budget-dropped stable context ids: "
                "locomo-temporal-rich, locomo-multihop-rich, locomo-routing-owner-history-gap"
            )
            self.assertIn(expected_budget_context_line, report_output)
            self.assertIn(expected_budget_context_line, dashboard_output)
            self.assertIn(expected_budget_context_line, page_output)
            self.assertIn("- Context budget tokens: `200`", report_text)
            self.assertIn("- Budget-dropped evidence +/-:", report_text)
            self.assertIn("Budget dropped", dashboard_html)
            self.assertIn("Budget-dropped context", dashboard_html)
            self.assertIn("Budget-dropped", page_html)
            self.assertIn("Question Evidence", page_html)
            self.assertIn("Retrieval latency delta", dashboard_html)
            self.assertIn("Retrieval latency delta", page_html)
            self.assertIn("latency delta ", dashboard_html)
            self.assertIn("latency delta ", page_html)
            self.assertIn(changed_question["question_id"], page_html)
            self.assertIn(budget_evidence, report_text)
            self.assertIn(budget_evidence, dashboard_html)
            self.assertIn(budget_evidence, page_html)
            self.assertIn(stable_win_evidence, report_text)
            self.assertIn(stable_win_evidence, dashboard_html)
            self.assertIn(stable_win_evidence, page_html)

            for proof in expected_mode_proofs:
                self.assertIn(proof["result_hash"], report_text)
                self.assertIn(proof["aggregate_merkle_root"], report_text)
                self.assertIn(proof["result_hash"], dashboard_html)
                self.assertIn(proof["aggregate_merkle_root"], dashboard_html)
                self.assertIn(proof["result_hash"], page_html)
                self.assertIn(proof["aggregate_merkle_root"], page_html)

            self._assert_rendered_mode_proof_hops(expected_mode_proofs, dashboard_html)
            self._assert_rendered_mode_proof_hops(expected_mode_proofs, page_html)

    def test_cli_budget_constrained_locomo_matrix_comparison_reopen_preserves_mode_summaries_and_budget_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()
            first = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-budget-matrix-a",
                context_budget_tokens=200,
            )
            second = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-budget-matrix-b",
                context_budget_tokens=200,
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_cwd)
                comparison = self._main_json(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--out",
                        os.path.relpath(compare_out, other_cwd),
                    ]
                )
                report = self._main_json(["bench", "report", comparison["comparison_path"]])
                dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
            finally:
                os.chdir(previous_cwd)

            comparison_path = Path(comparison["comparison_path"])
            if not comparison_path.is_absolute():
                comparison_path = (other_cwd / comparison_path).resolve()
            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            report_summary_by_mode = {
                mode["retrieval_mode"]: mode for mode in report["summary"]["mode_comparisons"]
            }
            dashboard_summary_by_mode = {
                mode["retrieval_mode"]: mode for mode in dashboard["summary"]["mode_comparisons"]
            }
            expected_by_mode = {
                "fts": (0, 3, 2),
                "fts-multihop": (0, 3, 2),
                "pseudo-embedding": (0, 2, 3),
                "pseudo-embedding-rerank": (0, 2, 3),
            }
            budget_evidence = "The review moved again to Friday afternoon."
            multihop_gap_evidence = "Kestrel Node locker code is 4182."
            stable_win_evidence = "Earlier escalation contact was Jules."

            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison_payload["target"]["benchmark"], "locomo")
            self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
            self.assertEqual(comparison_payload["target"]["split"], "dev")
            self.assertEqual(comparison_payload["target"]["context_budget_tokens"], 200)
            self.assertTrue(all(not Path(matrix["path"]).is_absolute() for matrix in comparison_payload["matrices"]))
            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["context_budget_tokens"], 200)
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertEqual(dashboard["summary"]["context_budget_tokens"], 200)
            self.assertIn("- Context budget tokens: `200`", report_text)
            self.assertIn("Budget-dropped memories:", report_text)
            self.assertIn("Stable miss question ids:", report_text)
            self.assertIn("Budget dropped", dashboard_html)
            self.assertIn("Budget-dropped context", dashboard_html)
            self.assertIn("Stable Miss Spotlight: fts", dashboard_html)
            self.assertIn("Stable Miss Spotlight: pseudo-embedding", dashboard_html)
            self.assertIn("Stable Miss Spotlight: pseudo-embedding-rerank", dashboard_html)
            self.assertIn("Mode Proof Hops: fts", dashboard_html)

            for mode_comparison in comparison_payload["mode_comparisons"]:
                retrieval_mode = mode_comparison["retrieval_mode"]
                expected_visible_deltas, expected_stable_wins, expected_stable_misses = expected_by_mode[
                    retrieval_mode
                ]
                question_summary = mode_comparison["question_summary"]

                self.assertEqual(mode_comparison["proof"]["verification_status"], "ok")
                self.assertEqual(report_summary_by_mode[retrieval_mode]["verification_status"], "ok")
                self.assertEqual(dashboard_summary_by_mode[retrieval_mode]["verification_status"], "ok")
                self.assertEqual(
                    (
                        question_summary["visible_delta_question_count"],
                        question_summary["stable_wins"]["count"],
                        question_summary["stable_misses"]["count"],
                    ),
                    (expected_visible_deltas, expected_stable_wins, expected_stable_misses),
                )
                self.assertEqual(
                    report_summary_by_mode[retrieval_mode]["question_summary"],
                    dashboard_summary_by_mode[retrieval_mode]["question_summary"],
                )
                self.assertEqual(report_summary_by_mode[retrieval_mode]["question_summary"], question_summary)
                self.assertIn(f"### {retrieval_mode}", report_text)
                self.assertIn(f"- Stable wins: `{expected_stable_wins}`", report_text)
                self.assertIn(f"- Stable misses: `{expected_stable_misses}`", report_text)
                self.assertIn(str(expected_stable_wins), dashboard_html)
                self.assertIn(str(expected_stable_misses), dashboard_html)
                for matrix_run in mode_comparison["matrix_runs"]:
                    self.assertIn(matrix_run["matrix_run_id"], report_text)
                    self.assertIn(matrix_run["result_hash"], report_text)
                    self.assertIn(matrix_run["aggregate_merkle_root"], report_text)
                    self.assertIn(matrix_run["matrix_run_id"], dashboard_html)
                    self.assertIn(matrix_run["result_hash"], dashboard_html)
                    self.assertIn(matrix_run["aggregate_merkle_root"], dashboard_html)

            self.assertIn("locomo-temporal-rich", report_text)
            self.assertIn("locomo-multihop-rich", report_text)
            self.assertIn("locomo-routing-owner-history-gap", report_text)
            self.assertIn("locomo-temporal-rich", dashboard_html)
            self.assertIn("locomo-multihop-rich", dashboard_html)
            self.assertIn("locomo-routing-owner-history-gap", dashboard_html)
            self.assertIn(budget_evidence, report_text)
            self.assertIn(budget_evidence, dashboard_html)
            self.assertIn(multihop_gap_evidence, report_text)
            self.assertIn(multihop_gap_evidence, dashboard_html)
            self.assertIn(stable_win_evidence, report_text)
            self.assertIn(stable_win_evidence, dashboard_html)

    def test_cli_richer_locomo_matrix_comparison_reopen_preserves_recovered_wins_stable_misses_and_budget_context_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()
            first = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-rich-matrix-a",
                context_budget_tokens=200,
            )
            second = run_benchmark_matrix(
                out,
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-rich-matrix-b",
                context_budget_tokens=200,
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_cwd)
                summary_output = self._main_text(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--summary-only",
                    ]
                )
                comparison = self._main_json(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--out",
                        os.path.relpath(compare_out, other_cwd),
                    ]
                )
                report_output = self._main_text(["bench", "report", comparison["comparison_path"], "--summary-only"])
                dashboard_output = self._main_text(
                    ["bench", "dashboard", comparison["comparison_path"], "--summary-only"]
                )
                report = self._main_json(["bench", "report", comparison["comparison_path"]])
                dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
            finally:
                os.chdir(previous_cwd)

            comparison_path = Path(comparison["comparison_path"])
            if not comparison_path.is_absolute():
                comparison_path = (other_cwd / comparison_path).resolve()
            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()

            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            report_summary_by_mode = {
                mode["retrieval_mode"]: mode for mode in report["summary"]["mode_comparisons"]
            }
            dashboard_summary_by_mode = {
                mode["retrieval_mode"]: mode for mode in dashboard["summary"]["mode_comparisons"]
            }
            anchor_mode = next(
                mode for mode in comparison_payload["mode_comparisons"] if mode["retrieval_mode"] == "fts"
            )
            expected_anchor_summary = {
                "question_count": 5,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 2,
                    "question_ids": ["locomo-temporal-rich", "locomo-multihop-rich"],
                },
                "stable_wins": {
                    "count": 3,
                    "question_ids": [
                        "locomo-routing-owner-wording-gap",
                        "locomo-routing-owner-history-gap",
                        "locomo-abstention-rich",
                    ],
                },
            }
            expected_mode_line = (
                "Mode comparison fts: verification=ok visible_deltas=0 stable_wins=3 stable_misses=2"
            )
            expected_win_ids_line = (
                "Mode comparison fts stable win ids: "
                "locomo-routing-owner-wording-gap, locomo-routing-owner-history-gap, locomo-abstention-rich"
            )
            expected_miss_ids_line = (
                "Mode comparison fts stable miss ids: locomo-temporal-rich, locomo-multihop-rich"
            )
            expected_budget_context_ids = [
                "locomo-temporal-rich",
                "locomo-routing-owner-history-gap",
            ]
            expected_budget_context_ids_line = (
                "Mode comparison fts budget context ids: "
                "locomo-temporal-rich, locomo-routing-owner-history-gap"
            )
            expected_proof_hop_lines = [
                (
                    "Mode comparison fts proof hop "
                    f"{matrix_run['matrix_run_id']}: result_hash={matrix_run['result_hash']} "
                    f"aggregate_merkle_root={matrix_run['aggregate_merkle_root']}"
                )
                for matrix_run in anchor_mode["matrix_runs"]
            ]

            self.assertEqual(anchor_mode["question_summary"], expected_anchor_summary)
            self.assertEqual(report_summary_by_mode["fts"]["question_summary"], expected_anchor_summary)
            self.assertEqual(dashboard_summary_by_mode["fts"]["question_summary"], expected_anchor_summary)
            self.assertEqual(report_summary_by_mode["fts"]["budget_context_question_ids"], expected_budget_context_ids)
            self.assertEqual(dashboard_summary_by_mode["fts"]["budget_context_question_ids"], expected_budget_context_ids)
            self.assertEqual(
                report_summary_by_mode["fts"]["matrix_run_proofs"],
                [
                    {
                        "matrix_run_id": matrix_run["matrix_run_id"],
                        "result_hash": matrix_run["result_hash"],
                        "aggregate_merkle_root": matrix_run["aggregate_merkle_root"],
                    }
                    for matrix_run in anchor_mode["matrix_runs"]
                ],
            )
            self.assertEqual(
                dashboard_summary_by_mode["fts"]["matrix_run_proofs"],
                report_summary_by_mode["fts"]["matrix_run_proofs"],
            )
            for output in (summary_output, report_output, dashboard_output):
                self.assertIn(expected_mode_line, output)
                self.assertIn(expected_win_ids_line, output)
                self.assertIn(expected_miss_ids_line, output)
                self.assertIn(expected_budget_context_ids_line, output)
                for proof_hop_line in expected_proof_hop_lines:
                    self.assertIn(proof_hop_line, output)

            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertEqual(dashboard["summary"]["mode_comparisons"][0]["verification_status"], "ok")
            self.assertIn(
                "Stable win question ids: "
                "`locomo-routing-owner-wording-gap, locomo-routing-owner-history-gap, locomo-abstention-rich`",
                report_text,
            )
            self.assertIn(
                "Stable miss question ids: `locomo-temporal-rich, locomo-multihop-rich`",
                report_text,
            )
            self.assertIn(
                "Budget-dropped stable context question ids: "
                "`locomo-temporal-rich, locomo-routing-owner-history-gap`",
                report_text,
            )
            self.assertIn("Recovered stable win `locomo-routing-owner-history-gap`", report_text)
            self.assertIn("Stable miss `locomo-temporal-rich`", report_text)
            self.assertIn("Stable miss `locomo-multihop-rich`", report_text)
            self.assertIn("Earlier escalation contact was Jules.", report_text)
            self.assertIn("The review moved again to Friday afternoon.", report_text)
            self.assertIn("Kestrel Node locker code is 4182.", report_text)
            self.assertIn("Recovered Stable Win Spotlight: fts", dashboard_html)
            self.assertIn("Stable Miss Spotlight: fts", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context: fts", dashboard_html)
            self.assertIn("locomo-routing-owner-history-gap", dashboard_html)
            self.assertIn("locomo-temporal-rich", dashboard_html)
            self.assertIn("locomo-multihop-rich", dashboard_html)
            self.assertIn("Earlier escalation contact was Jules.", dashboard_html)
            self.assertIn("The review moved again to Friday afternoon.", dashboard_html)
            self.assertIn("Kestrel Node locker code is 4182.", dashboard_html)

    def test_cli_richer_longmemeval_matrix_comparison_reopen_preserves_recovered_wins_and_budget_context_together(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()
            first = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="longmemeval-rich-matrix-a",
                context_budget_tokens=200,
            )
            second = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="longmemeval-rich-matrix-b",
                context_budget_tokens=200,
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_cwd)
                summary_output = self._main_text(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--summary-only",
                    ]
                )
                comparison = self._main_json(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--out",
                        os.path.relpath(compare_out, other_cwd),
                    ]
                )
                report_output = self._main_text(["bench", "report", comparison["comparison_path"], "--summary-only"])
                dashboard_output = self._main_text(
                    ["bench", "dashboard", comparison["comparison_path"], "--summary-only"]
                )
                report = self._main_json(["bench", "report", comparison["comparison_path"]])
                dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
            finally:
                os.chdir(previous_cwd)

            comparison_path = Path(comparison["comparison_path"])
            if not comparison_path.is_absolute():
                comparison_path = (other_cwd / comparison_path).resolve()
            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()

            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            anchor_mode = next(
                mode for mode in comparison_payload["mode_comparisons"] if mode["retrieval_mode"] == "fts"
            )
            expected_anchor_summary = {
                "question_count": 8,
                "visible_delta_question_count": 0,
                "stable_misses": {
                    "count": 0,
                    "question_ids": [],
                },
                "stable_wins": {
                    "count": 8,
                    "question_ids": [
                        "lme-temporal-change-when",
                        "lme-knowledge-update-current-target",
                        "lme-knowledge-update-stale-decoy",
                        "lme-knowledge-update-ambiguous-restatement",
                        "lme-knowledge-update-release-note-decoy",
                        "lme-knowledge-update-history-wording-gap",
                        "lme-routing-owner-wording-gap",
                        "lme-current-conflict-abstain",
                    ],
                },
            }
            expected_mode_line = (
                "Mode comparison fts: verification=ok visible_deltas=0 stable_wins=8 stable_misses=0"
            )
            expected_win_ids_line = (
                "Mode comparison fts stable win ids: "
                "lme-temporal-change-when, lme-knowledge-update-current-target, "
                "lme-knowledge-update-stale-decoy, lme-knowledge-update-ambiguous-restatement, "
                "lme-knowledge-update-release-note-decoy, lme-knowledge-update-history-wording-gap, "
                "lme-routing-owner-wording-gap, lme-current-conflict-abstain"
            )

            self.assertEqual(anchor_mode["question_summary"], expected_anchor_summary)
            for output in (summary_output, report_output, dashboard_output):
                self.assertIn(expected_mode_line, output)
                self.assertIn(expected_win_ids_line, output)

            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertEqual(dashboard["summary"]["mode_comparisons"][0]["verification_status"], "ok")
            self.assertIn(
                "Stable win question ids: "
                "`lme-temporal-change-when, lme-knowledge-update-current-target, "
                "lme-knowledge-update-stale-decoy, lme-knowledge-update-ambiguous-restatement, "
                "lme-knowledge-update-release-note-decoy, lme-knowledge-update-history-wording-gap, "
                "lme-routing-owner-wording-gap, lme-current-conflict-abstain`",
                report_text,
            )
            self.assertIn(
                "Budget-dropped stable context question ids: "
                "`lme-temporal-change-when, lme-knowledge-update-stale-decoy, "
                "lme-knowledge-update-history-wording-gap`",
                report_text,
            )
            self.assertIn("Recovered stable win `lme-temporal-change-when`", report_text)
            self.assertIn("Recovered stable win `lme-knowledge-update-history-wording-gap`", report_text)
            self.assertIn("On Monday, the deployment approver was Noor.", report_text)
            self.assertIn("Blue Finch shipped on Staging before the cutover.", report_text)
            self.assertIn("Recovered Stable Win Spotlight: fts", dashboard_html)
            self.assertNotIn("<h2>Stable Miss Spotlight: fts</h2>", dashboard_html)
            self.assertIn("Budget-Dropped Stable Context: fts", dashboard_html)
            self.assertIn("lme-temporal-change-when", dashboard_html)
            self.assertIn("lme-knowledge-update-history-wording-gap", dashboard_html)
            self.assertIn("On Monday, the deployment approver was Noor.", dashboard_html)
            self.assertIn("Blue Finch shipped on Staging before the cutover.", dashboard_html)

    def test_cli_budget_constrained_longmemeval_matrix_comparison_reopen_preserves_mode_summaries_and_budget_dropped_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            compare_out = tmp_path / "comparison"
            other_cwd = tmp_path / "other-cwd"
            other_cwd.mkdir()
            first = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="longmemeval-budget-matrix-a",
                context_budget_tokens=200,
            )
            second = run_benchmark_matrix(
                out,
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="longmemeval-budget-matrix-b",
                context_budget_tokens=200,
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_cwd)
                comparison = self._main_json(
                    [
                        "bench",
                        "compare-matrices",
                        os.path.relpath(first["matrix_path"], other_cwd),
                        os.path.relpath(second["matrix_path"], other_cwd),
                        "--out",
                        os.path.relpath(compare_out, other_cwd),
                    ]
                )
                report = self._main_json(["bench", "report", comparison["comparison_path"]])
                dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
            finally:
                os.chdir(previous_cwd)

            comparison_path = Path(comparison["comparison_path"])
            if not comparison_path.is_absolute():
                comparison_path = (other_cwd / comparison_path).resolve()
            report_path = Path(report["report_path"])
            if not report_path.is_absolute():
                report_path = (other_cwd / report_path).resolve()
            dashboard_path = Path(dashboard["dashboard_path"])
            if not dashboard_path.is_absolute():
                dashboard_path = (other_cwd / dashboard_path).resolve()
            comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            report_summary_by_mode = {
                mode["retrieval_mode"]: mode for mode in report["summary"]["mode_comparisons"]
            }
            dashboard_summary_by_mode = {
                mode["retrieval_mode"]: mode for mode in dashboard["summary"]["mode_comparisons"]
            }
            expected_by_mode = {
                "fts": (0, 8, 0),
                "fts-multihop": (0, 7, 1),
                "pseudo-embedding": (0, 7, 1),
                "pseudo-embedding-rerank": (0, 7, 1),
            }

            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison_payload["target"]["benchmark"], "longmemeval")
            self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
            self.assertEqual(comparison_payload["target"]["split"], "analysis")
            self.assertEqual(comparison_payload["target"]["context_budget_tokens"], 200)
            self.assertTrue(all(not Path(matrix["path"]).is_absolute() for matrix in comparison_payload["matrices"]))
            self.assertEqual(report["artifact_type"], "matrix_comparison")
            self.assertEqual(report["verification_status"], "ok")
            self.assertEqual(report["summary"]["context_budget_tokens"], 200)
            self.assertEqual(dashboard["artifact_type"], "matrix_comparison")
            self.assertEqual(dashboard["summary"]["context_budget_tokens"], 200)
            self.assertIn("- Context budget tokens: `200`", report_text)
            self.assertIn("- Budget-dropped stable context question ids:", report_text)
            self.assertIn("On Monday, the deployment approver was Noor.", report_text)
            self.assertIn("Mode Proof Hops: fts", dashboard_html)

            for mode_comparison in comparison_payload["mode_comparisons"]:
                retrieval_mode = mode_comparison["retrieval_mode"]
                expected_visible_deltas, expected_stable_wins, expected_stable_misses = expected_by_mode[
                    retrieval_mode
                ]
                question_summary = mode_comparison["question_summary"]

                self.assertEqual(mode_comparison["proof"]["verification_status"], "ok")
                self.assertEqual(report_summary_by_mode[retrieval_mode]["verification_status"], "ok")
                self.assertEqual(dashboard_summary_by_mode[retrieval_mode]["verification_status"], "ok")
                self.assertEqual(
                    (
                        question_summary["visible_delta_question_count"],
                        question_summary["stable_wins"]["count"],
                        question_summary["stable_misses"]["count"],
                    ),
                    (expected_visible_deltas, expected_stable_wins, expected_stable_misses),
                )
                self.assertEqual(
                    report_summary_by_mode[retrieval_mode]["question_summary"],
                    dashboard_summary_by_mode[retrieval_mode]["question_summary"],
                )
                self.assertEqual(report_summary_by_mode[retrieval_mode]["question_summary"], question_summary)
                self.assertIn(f"### {retrieval_mode}", report_text)
                self.assertIn(f"- Stable wins: `{expected_stable_wins}`", report_text)
                self.assertIn(f"- Stable misses: `{expected_stable_misses}`", report_text)
                self.assertIn(str(expected_stable_wins), dashboard_html)
                self.assertIn(str(expected_stable_misses), dashboard_html)
                for matrix_run in mode_comparison["matrix_runs"]:
                    self.assertIn(matrix_run["matrix_run_id"], report_text)
                    self.assertIn(matrix_run["result_hash"], report_text)
                    self.assertIn(matrix_run["aggregate_merkle_root"], report_text)
                    self.assertIn(matrix_run["matrix_run_id"], dashboard_html)
                    self.assertIn(matrix_run["result_hash"], dashboard_html)
                    self.assertIn(matrix_run["aggregate_merkle_root"], dashboard_html)

    def test_cli_richer_matrix_comparison_verify_reopens_from_another_cwd_with_summary_parity(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                "analysis",
                {
                    "question_count": 8,
                    "visible_delta_question_count": 0,
                    "stable_misses": {"count": 0, "question_ids": []},
                    "stable_wins": {
                        "count": 8,
                        "question_ids": [
                            "lme-temporal-change-when",
                            "lme-knowledge-update-current-target",
                            "lme-knowledge-update-stale-decoy",
                            "lme-knowledge-update-ambiguous-restatement",
                            "lme-knowledge-update-release-note-decoy",
                            "lme-knowledge-update-history-wording-gap",
                            "lme-routing-owner-wording-gap",
                            "lme-current-conflict-abstain",
                        ],
                    },
                },
                [
                    "lme-temporal-change-when",
                    "lme-knowledge-update-stale-decoy",
                    "lme-knowledge-update-history-wording-gap",
                ],
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                "dev",
                {
                    "question_count": 5,
                    "visible_delta_question_count": 0,
                    "stable_misses": {
                        "count": 2,
                        "question_ids": ["locomo-temporal-rich", "locomo-multihop-rich"],
                    },
                    "stable_wins": {
                        "count": 3,
                        "question_ids": [
                            "locomo-routing-owner-wording-gap",
                            "locomo-routing-owner-history-gap",
                            "locomo-abstention-rich",
                        ],
                    },
                },
                [
                    "locomo-temporal-rich",
                    "locomo-routing-owner-history-gap",
                ],
            ),
        )

        for benchmark, dataset_writer, split, expected_anchor_summary, expected_budget_context_ids in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                first = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-verify-matrix-a",
                    context_budget_tokens=200,
                )
                second = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-rich-verify-matrix-b",
                    context_budget_tokens=200,
                )

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    comparison = self._main_json(
                        [
                            "bench",
                            "compare-matrices",
                            os.path.relpath(first["matrix_path"], other_cwd),
                            os.path.relpath(second["matrix_path"], other_cwd),
                            "--out",
                            os.path.relpath(compare_out, other_cwd),
                        ]
                    )
                    verify_summary_output = self._main_text(
                        ["bench", "verify", comparison["comparison_path"], "--summary-only"]
                    )
                    verify = self._main_json(["bench", "verify", comparison["comparison_path"]])
                finally:
                    os.chdir(previous_cwd)

                comparison_path = Path(comparison["comparison_path"])
                if not comparison_path.is_absolute():
                    comparison_path = (other_cwd / comparison_path).resolve()
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                direct_verify = verify_benchmark_artifact(comparison_path)
                anchor_mode = next(
                    mode for mode in comparison_payload["mode_comparisons"] if mode["retrieval_mode"] == "fts"
                )
                verify_summary_by_mode = {
                    mode["retrieval_mode"]: mode for mode in verify["summary"]["mode_comparisons"]
                }
                direct_verify_summary_by_mode = {
                    mode["retrieval_mode"]: mode for mode in direct_verify["summary"]["mode_comparisons"]
                }
                expected_mode_line = (
                    "Mode comparison fts: verification=ok "
                    f"visible_deltas={expected_anchor_summary['visible_delta_question_count']} "
                    f"stable_wins={expected_anchor_summary['stable_wins']['count']} "
                    f"stable_misses={expected_anchor_summary['stable_misses']['count']}"
                )
                expected_proof_hop_lines = [
                    (
                        "Mode comparison fts proof hop "
                        f"{matrix_run['matrix_run_id']}: result_hash={matrix_run['result_hash']} "
                        f"aggregate_merkle_root={matrix_run['aggregate_merkle_root']}"
                    )
                    for matrix_run in anchor_mode["matrix_runs"]
                ]

                self.assertTrue(comparison["ok"])
                self.assertTrue(verify["ok"])
                self.assertTrue(direct_verify["ok"])
                self.assertEqual(verify["artifact_type"], "matrix_comparison")
                self.assertEqual(direct_verify["artifact_type"], "matrix_comparison")
                self.assertEqual(verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(direct_verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(self._failed_check_names(verify), set())
                self.assertEqual(self._failed_check_names(direct_verify), set())
                self.assertEqual(verify["summary"]["benchmark"], benchmark)
                self.assertEqual(verify["summary"]["dataset"], str(dataset))
                self.assertEqual(verify["summary"]["split"], split)
                self.assertEqual(verify["summary"]["context_budget_tokens"], 200)
                self.assertEqual(verify["summary"]["verification_status"], "ok")
                self.assertEqual(verify_summary_by_mode["fts"]["question_summary"], expected_anchor_summary)
                self.assertEqual(
                    verify_summary_by_mode["fts"]["budget_context_question_ids"],
                    expected_budget_context_ids,
                )
                self.assertEqual(
                    verify_summary_by_mode["fts"]["matrix_run_proofs"],
                    [
                        {
                            "matrix_run_id": matrix_run["matrix_run_id"],
                            "result_hash": matrix_run["result_hash"],
                            "aggregate_merkle_root": matrix_run["aggregate_merkle_root"],
                        }
                        for matrix_run in anchor_mode["matrix_runs"]
                    ],
                )
                self.assertEqual(direct_verify["summary"], verify["summary"])
                self.assertEqual(
                    direct_verify_summary_by_mode["fts"]["question_summary"],
                    expected_anchor_summary,
                )

                self.assertIn("Benchmark verify", verify_summary_output)
                self.assertIn("Artifact: matrix_comparison", verify_summary_output)
                self.assertIn("Verification: ok", verify_summary_output)
                self.assertIn("Failed checks: none", verify_summary_output)
                self.assertIn(expected_mode_line, verify_summary_output)
                if expected_anchor_summary["stable_wins"]["question_ids"]:
                    self.assertIn(
                        "Mode comparison fts stable win ids: "
                        + ", ".join(expected_anchor_summary["stable_wins"]["question_ids"]),
                        verify_summary_output,
                    )
                if expected_anchor_summary["stable_misses"]["question_ids"]:
                    self.assertIn(
                        "Mode comparison fts stable miss ids: "
                        + ", ".join(expected_anchor_summary["stable_misses"]["question_ids"]),
                        verify_summary_output,
                    )
                self.assertIn(
                    "Mode comparison fts budget context ids: " + ", ".join(expected_budget_context_ids),
                    verify_summary_output,
                )
                for proof_hop_line in expected_proof_hop_lines:
                    self.assertIn(proof_hop_line, verify_summary_output)

    def test_cli_budget_constrained_matrix_comparison_verify_reopens_from_another_cwd(self):
        cases = (
            ("longmemeval", self._write_richer_longmemeval_jsonl, "analysis", {"fts": (0, 8, 0)}),
            ("locomo", self._write_richer_locomo_jsonl, "dev", {"fts": (0, 3, 2)}),
        )

        for benchmark, dataset_writer, split, expected_anchor_mode in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                first = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-budget-verify-matrix-a",
                    context_budget_tokens=200,
                )
                second = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-budget-verify-matrix-b",
                    context_budget_tokens=200,
                )

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    comparison = self._main_json(
                        [
                            "bench",
                            "compare-matrices",
                            os.path.relpath(first["matrix_path"], other_cwd),
                            os.path.relpath(second["matrix_path"], other_cwd),
                            "--out",
                            os.path.relpath(compare_out, other_cwd),
                        ]
                    )
                    verify_summary_output = self._main_text(
                        ["bench", "verify", comparison["comparison_path"], "--summary-only"]
                    )
                    verify = self._main_json(["bench", "verify", comparison["comparison_path"]])
                finally:
                    os.chdir(previous_cwd)

                comparison_path = Path(comparison["comparison_path"])
                if not comparison_path.is_absolute():
                    comparison_path = (other_cwd / comparison_path).resolve()
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                direct_verify = verify_benchmark_artifact(comparison_path)
                anchor_mode = next(
                    mode for mode in comparison_payload["mode_comparisons"] if mode["retrieval_mode"] == "fts"
                )

                self.assertTrue(comparison["ok"])
                self.assertTrue(verify["ok"])
                self.assertTrue(direct_verify["ok"])
                self.assertEqual(verify["artifact_type"], "matrix_comparison")
                self.assertEqual(direct_verify["artifact_type"], "matrix_comparison")
                self.assertEqual(verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(direct_verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(self._failed_check_names(verify), set())
                self.assertEqual(self._failed_check_names(direct_verify), set())
                self.assertTrue(all(not Path(matrix["path"]).is_absolute() for matrix in comparison_payload["matrices"]))
                self.assertEqual(comparison_payload["target"]["benchmark"], benchmark)
                self.assertEqual(comparison_payload["target"]["dataset"], str(dataset))
                self.assertEqual(comparison_payload["target"]["split"], split)
                self.assertEqual(comparison_payload["target"]["context_budget_tokens"], 200)
                self.assertEqual(len(comparison_payload["mode_comparisons"]), len(BENCHMARK_RETRIEVAL_MODES))
                self.assertEqual(
                    (
                        anchor_mode["question_summary"]["visible_delta_question_count"],
                        anchor_mode["question_summary"]["stable_wins"]["count"],
                        anchor_mode["question_summary"]["stable_misses"]["count"],
                    ),
                    expected_anchor_mode[anchor_mode["retrieval_mode"]],
                )
                self.assertIn("Benchmark verify", verify_summary_output)
                self.assertIn("Artifact: matrix_comparison", verify_summary_output)
                self.assertIn("Verification: ok", verify_summary_output)
                self.assertIn("Failed checks: none", verify_summary_output)
                self.assertIn(
                    "Mode comparison fts: verification=ok "
                    f"visible_deltas={expected_anchor_mode['fts'][0]} "
                    f"stable_wins={expected_anchor_mode['fts'][1]} "
                    f"stable_misses={expected_anchor_mode['fts'][2]}",
                    verify_summary_output,
                )

                stable_wins = anchor_mode["question_summary"]["stable_wins"]["question_ids"]
                if stable_wins:
                    self.assertIn(
                        "Mode comparison fts stable win ids: " + ", ".join(stable_wins),
                        verify_summary_output,
                    )

                stable_misses = anchor_mode["question_summary"]["stable_misses"]["question_ids"]
                if stable_misses:
                    self.assertIn(
                        "Mode comparison fts stable miss ids: " + ", ".join(stable_misses),
                        verify_summary_output,
                    )

                budget_context_ids = anchor_mode.get("budget_context_question_ids", [])
                if budget_context_ids:
                    self.assertIn(
                        "Mode comparison fts budget context ids: " + ", ".join(budget_context_ids),
                        verify_summary_output,
                    )

                for matrix_run in anchor_mode["matrix_runs"]:
                    self.assertIn(
                        "Mode comparison fts proof hop "
                        f"{matrix_run['matrix_run_id']}: result_hash={matrix_run['result_hash']} "
                        f"aggregate_merkle_root={matrix_run['aggregate_merkle_root']}",
                        verify_summary_output,
                    )

    def test_cli_budget_constrained_matrix_verify_reopens_from_another_cwd(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                "analysis",
                {
                    "question_count": 8,
                    "visible_delta_question_count": 3,
                    "stable_wins": {
                        "count": 5,
                        "question_ids": [
                            "lme-temporal-change-when",
                            "lme-knowledge-update-current-target",
                            "lme-knowledge-update-ambiguous-restatement",
                            "lme-routing-owner-wording-gap",
                            "lme-current-conflict-abstain",
                        ],
                    },
                    "stable_misses": {"count": 0, "question_ids": []},
                },
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                "dev",
                {
                    "question_count": 5,
                    "visible_delta_question_count": 2,
                    "stable_wins": {
                        "count": 2,
                        "question_ids": [
                            "locomo-routing-owner-wording-gap",
                            "locomo-abstention-rich",
                        ],
                    },
                    "stable_misses": {"count": 1, "question_ids": ["locomo-temporal-rich"]},
                },
            ),
        )

        for benchmark, dataset_writer, split, expected_question_summary in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                matrix = run_benchmark_matrix(
                    out,
                    benchmark,
                    dataset=dataset,
                    split=split,
                    seed=0,
                    run_id=f"{benchmark}-budget-verify-matrix",
                    context_budget_tokens=200,
                )

                matrix_path = Path(matrix["matrix_path"])
                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    verify = self._main_json(
                        ["bench", "verify", os.path.relpath(matrix_path, other_cwd)]
                    )
                finally:
                    os.chdir(previous_cwd)

                matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
                direct_verify = verify_benchmark_artifact(matrix_path)

                self.assertTrue(verify["ok"])
                self.assertTrue(direct_verify["ok"])
                self.assertEqual(verify["artifact_type"], "matrix")
                self.assertEqual(direct_verify["artifact_type"], "matrix")
                self.assertEqual(verify["matrix_hash"], matrix_payload["matrix_hash"])
                self.assertEqual(direct_verify["matrix_hash"], matrix_payload["matrix_hash"])
                self.assertEqual(verify["comparison_hash"], matrix_payload["comparison_hash"])
                self.assertEqual(direct_verify["comparison_hash"], matrix_payload["comparison_hash"])
                self.assertEqual(self._failed_check_names(verify), set())
                self.assertEqual(self._failed_check_names(direct_verify), set())
                self.assertEqual(matrix_payload["benchmark"], benchmark)
                self.assertEqual(matrix_payload["dataset"], str(dataset))
                self.assertEqual(matrix_payload["split"], split)
                self.assertEqual(matrix_payload["context_budget_tokens"], 200)
                self.assertTrue(
                    all(not Path(run["result_path"]).is_absolute() for run in matrix_payload["mode_runs"])
                )
                self.assertEqual(
                    matrix_payload["proof"]["input_result_paths"],
                    [f"{mode}/benchmark-result.json" for mode in BENCHMARK_RETRIEVAL_MODES],
                )
                self.assertEqual(matrix_payload["question_summary"], expected_question_summary)

    def test_cli_budget_constrained_standalone_comparison_reopen_preserves_budget_dropped_evidence(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                run_longmemeval_benchmark,
                "analysis",
                (2, 6, 0),
                "lme-knowledge-update-release-note-decoy",
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                run_locomo_benchmark,
                "dev",
                (1, 3, 1),
                "The review moved again to Friday afternoon.",
            ),
        )

        for benchmark, dataset_writer, runner, split, expected_summary, expected_marker in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                fts = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-budget-a",
                    retrieval_mode="fts",
                    context_budget_tokens=200,
                )
                multihop = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-budget-b",
                    retrieval_mode="fts-multihop",
                    context_budget_tokens=200,
                )

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    comparison = self._main_json(
                        [
                            "bench",
                            "compare",
                            os.path.relpath(fts["result_path"], other_cwd),
                            os.path.relpath(multihop["result_path"], other_cwd),
                            "--out",
                            os.path.relpath(compare_out, other_cwd),
                        ]
                    )
                    report = self._main_json(["bench", "report", comparison["comparison_path"]])
                    dashboard = self._main_json(["bench", "dashboard", comparison["comparison_path"]])
                finally:
                    os.chdir(previous_cwd)

                comparison_path = Path(comparison["comparison_path"])
                if not comparison_path.is_absolute():
                    comparison_path = (other_cwd / comparison_path).resolve()
                report_path = Path(report["report_path"])
                if not report_path.is_absolute():
                    report_path = (other_cwd / report_path).resolve()
                dashboard_path = Path(dashboard["dashboard_path"])
                if not dashboard_path.is_absolute():
                    dashboard_path = (other_cwd / dashboard_path).resolve()

                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                report_text = report_path.read_text(encoding="utf-8")
                dashboard_html = dashboard_path.read_text(encoding="utf-8")

                self.assertTrue(comparison["ok"])
                self.assertTrue(all(not Path(run["path"]).is_absolute() for run in comparison_payload["runs"]))
                self.assertEqual(comparison_payload["target"]["context_budget_tokens"], 200)
                self.assertEqual([run["context_budget_tokens"] for run in comparison_payload["runs"]], [200, 200])
                self.assertEqual(report["verification_status"], "ok")
                self.assertTrue(dashboard["ok"])
                self.assertEqual(report["summary"]["context_budget_tokens"], 200)
                self.assertEqual(dashboard["summary"]["context_budget_tokens"], 200)
                self.assertEqual(
                    (
                        comparison_payload["question_summary"]["visible_delta_question_count"],
                        comparison_payload["question_summary"]["stable_wins"]["count"],
                        comparison_payload["question_summary"]["stable_misses"]["count"],
                    ),
                    expected_summary,
                )
                self.assertIn("- Context budget tokens: `200`", report_text)
                self.assertIn("- Budget-dropped evidence +/-:", report_text)
                self.assertIn("latency delta `", report_text)
                self.assertIn("Budget dropped", dashboard_html)
                self.assertIn("Retrieval latency delta", dashboard_html)
                self.assertIn("latency delta ", dashboard_html)
                self.assertIn(expected_marker, report_text)
                self.assertIn(expected_marker, dashboard_html)

    def test_cli_standalone_comparison_verify_reopens_from_another_cwd_without_budget_context(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                run_longmemeval_benchmark,
                "analysis",
                {
                    "question_count": 8,
                    "visible_delta_question_count": 1,
                    "stable_wins": {
                        "count": 7,
                        "question_ids": [
                            "lme-temporal-change-when",
                            "lme-knowledge-update-current-target",
                            "lme-knowledge-update-stale-decoy",
                            "lme-knowledge-update-ambiguous-restatement",
                            "lme-knowledge-update-history-wording-gap",
                            "lme-routing-owner-wording-gap",
                            "lme-current-conflict-abstain",
                        ],
                    },
                    "stable_misses": {
                        "count": 0,
                        "question_ids": [],
                    },
                },
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                run_locomo_benchmark,
                "dev",
                {
                    "question_count": 5,
                    "visible_delta_question_count": 1,
                    "stable_wins": {
                        "count": 4,
                        "question_ids": [
                            "locomo-temporal-rich",
                            "locomo-routing-owner-wording-gap",
                            "locomo-routing-owner-history-gap",
                            "locomo-abstention-rich",
                        ],
                    },
                    "stable_misses": {
                        "count": 0,
                        "question_ids": [],
                    },
                },
            ),
        )

        for benchmark, dataset_writer, runner, split, expected_question_summary in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                fts = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-verify-a",
                    retrieval_mode="fts",
                )
                multihop = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-verify-b",
                    retrieval_mode="fts-multihop",
                )

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    comparison = self._main_json(
                        [
                            "bench",
                            "compare",
                            os.path.relpath(fts["result_path"], other_cwd),
                            os.path.relpath(multihop["result_path"], other_cwd),
                            "--out",
                            os.path.relpath(compare_out, other_cwd),
                        ]
                    )
                    report_summary_output = self._main_text(
                        ["bench", "report", comparison["comparison_path"], "--summary-only"]
                    )
                    dashboard_summary_output = self._main_text(
                        ["bench", "dashboard", comparison["comparison_path"], "--summary-only"]
                    )
                    verify_summary_output = self._main_text(
                        ["bench", "verify", comparison["comparison_path"], "--summary-only"]
                    )
                    verify = self._main_json(["bench", "verify", comparison["comparison_path"]])
                finally:
                    os.chdir(previous_cwd)

                comparison_path = Path(comparison["comparison_path"])
                if not comparison_path.is_absolute():
                    comparison_path = (other_cwd / comparison_path).resolve()
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                direct_verify = verify_benchmark_artifact(comparison_path)
                expected_mode_proofs = [
                    {
                        "retrieval_mode": run["retrieval_mode"],
                        "result_hash": run["result_hash"],
                        "aggregate_merkle_root": run["proof"]["aggregate_merkle_root"],
                    }
                    for run in comparison_payload["runs"]
                ]
                expected_proof_lines = [
                    (
                        "Mode proof "
                        f"{proof['retrieval_mode']}: "
                        f"result_hash={proof['result_hash']} "
                        f"aggregate_merkle_root={proof['aggregate_merkle_root']}"
                    )
                    for proof in expected_mode_proofs
                ]
                expected_memory_count_deltas = [
                    {
                        "question_id": question["question_id"],
                        "retrieval_mode": delta["retrieval_mode"],
                        "retrieved_memory_count_delta": delta.get("retrieved_memory_count_delta"),
                        "injected_memory_count_delta": delta.get("injected_memory_count_delta"),
                        "withheld_memory_count_delta": delta.get("withheld_memory_count_delta"),
                    }
                    for question in comparison_payload["questions"]
                    for delta in question.get("deltas", [])
                    if any(
                        delta.get(key) not in (None, 0)
                        for key in (
                            "retrieved_memory_count_delta",
                            "injected_memory_count_delta",
                            "withheld_memory_count_delta",
                        )
                    )
                ]
                expected_efficiency_deltas = [
                    {
                        "question_id": question["question_id"],
                        "retrieval_mode": delta["retrieval_mode"],
                        "retrieval_latency_ms_delta": delta.get("retrieval_latency_ms_delta"),
                        "total_tokens_delta": delta.get("total_tokens_delta"),
                    }
                    for question in comparison_payload["questions"]
                    for delta in question.get("deltas", [])
                    if any(
                        delta.get(key) not in (None, 0)
                        for key in (
                            "retrieval_latency_ms_delta",
                            "total_tokens_delta",
                        )
                    )
                ]

                self.assertTrue(comparison["ok"])
                self.assertTrue(verify["ok"])
                self.assertTrue(direct_verify["ok"])
                self.assertEqual(verify["artifact_type"], "comparison")
                self.assertEqual(direct_verify["artifact_type"], "comparison")
                self.assertEqual(verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(direct_verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(self._failed_check_names(verify), set())
                self.assertEqual(self._failed_check_names(direct_verify), set())
                self.assertEqual(verify["summary"]["benchmark"], benchmark)
                self.assertEqual(verify["summary"]["dataset"], str(dataset))
                self.assertEqual(verify["summary"]["split"], split)
                self.assertIsNone(verify["summary"]["context_budget_tokens"])
                self.assertEqual(verify["summary"]["verification_status"], "ok")
                self.assertEqual(verify["summary"]["question_summary"], expected_question_summary)
                self.assertEqual(verify["summary"]["budget_context_question_ids"], [])
                self.assertEqual(verify["summary"]["memory_count_deltas"], expected_memory_count_deltas)
                self.assertEqual(verify["summary"]["efficiency_deltas"], expected_efficiency_deltas)
                self.assertEqual(verify["summary"]["mode_proofs"], expected_mode_proofs)
                self.assertEqual(direct_verify["summary"], verify["summary"])

                self.assertIn("Benchmark verify", verify_summary_output)
                self.assertIn("Artifact: comparison", verify_summary_output)
                self.assertIn("Verification: ok", verify_summary_output)
                self.assertIn("Failed checks: none", verify_summary_output)
                self.assertNotIn("Context budget tokens:", verify_summary_output)
                self.assertNotIn("Budget-dropped stable context ids:", verify_summary_output)
                self.assertIn(
                    f"Stable wins: {expected_question_summary['stable_wins']['count']}",
                    verify_summary_output,
                )
                self.assertIn(
                    f"Stable misses: {expected_question_summary['stable_misses']['count']}",
                    verify_summary_output,
                )
                if expected_question_summary["stable_wins"]["question_ids"]:
                    self.assertIn(
                        "Stable win ids: "
                        + ", ".join(expected_question_summary["stable_wins"]["question_ids"]),
                        verify_summary_output,
                    )
                for delta in expected_memory_count_deltas:
                    self.assertIn(
                        "Memory count delta "
                        f"{delta['question_id']} ({delta['retrieval_mode']}): "
                        f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                        f"injected={delta['injected_memory_count_delta']:+d} "
                        f"withheld={delta['withheld_memory_count_delta']:+d}",
                        verify_summary_output,
                    )
                for delta in expected_efficiency_deltas:
                    latency_delta = delta["retrieval_latency_ms_delta"]
                    token_delta = delta["total_tokens_delta"]
                    latency_display = f"{latency_delta:+.3f}" if isinstance(latency_delta, float) else f"{latency_delta:+d}"
                    token_display = f"{token_delta:+.3f}" if isinstance(token_delta, float) else f"{token_delta:+d}"
                    expected_line = (
                        "Efficiency delta "
                        f"{delta['question_id']} ({delta['retrieval_mode']}): "
                        f"retrieval_latency_ms={latency_display} "
                        f"total_tokens={token_display}"
                    )
                    self.assertIn(
                        expected_line,
                        verify_summary_output,
                    )
                    self.assertIn(expected_line, report_summary_output)
                    self.assertIn(expected_line, dashboard_summary_output)
                for delta in expected_memory_count_deltas:
                    expected_line = (
                        "Memory count delta "
                        f"{delta['question_id']} ({delta['retrieval_mode']}): "
                        f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                        f"injected={delta['injected_memory_count_delta']:+d} "
                        f"withheld={delta['withheld_memory_count_delta']:+d}"
                    )
                    self.assertIn(expected_line, report_summary_output)
                    self.assertIn(expected_line, dashboard_summary_output)
                self.assertIn("Benchmark report", report_summary_output)
                self.assertIn("Artifact: comparison", report_summary_output)
                self.assertIn("Verification: ok", report_summary_output)
                self.assertIn("Benchmark dashboard", dashboard_summary_output)
                self.assertIn("Artifact: comparison", dashboard_summary_output)
                self.assertIn("Verification: ok", dashboard_summary_output)
                for proof_line in expected_proof_lines:
                    self.assertIn(proof_line, verify_summary_output)
                    self.assertIn(proof_line, report_summary_output)
                    self.assertIn(proof_line, dashboard_summary_output)

    def test_cli_budget_constrained_standalone_comparison_verify_reopens_from_another_cwd(self):
        cases = (
            (
                "longmemeval",
                self._write_richer_longmemeval_jsonl,
                run_longmemeval_benchmark,
                "analysis",
                {
                    "question_count": 8,
                    "visible_delta_question_count": 2,
                    "stable_wins": {
                        "count": 6,
                        "question_ids": [
                            "lme-temporal-change-when",
                            "lme-knowledge-update-current-target",
                            "lme-knowledge-update-stale-decoy",
                            "lme-knowledge-update-ambiguous-restatement",
                            "lme-routing-owner-wording-gap",
                            "lme-current-conflict-abstain",
                        ],
                    },
                    "stable_misses": {
                        "count": 0,
                        "question_ids": [],
                    },
                },
                [
                    "lme-temporal-change-when",
                    "lme-knowledge-update-stale-decoy",
                    "lme-knowledge-update-history-wording-gap",
                ],
            ),
            (
                "locomo",
                self._write_richer_locomo_jsonl,
                run_locomo_benchmark,
                "dev",
                {
                    "question_count": 5,
                    "visible_delta_question_count": 1,
                    "stable_wins": {
                        "count": 3,
                        "question_ids": [
                            "locomo-routing-owner-wording-gap",
                            "locomo-routing-owner-history-gap",
                            "locomo-abstention-rich",
                        ],
                    },
                    "stable_misses": {
                        "count": 1,
                        "question_ids": ["locomo-temporal-rich"],
                    },
                },
                [
                    "locomo-temporal-rich",
                    "locomo-multihop-rich",
                    "locomo-routing-owner-history-gap",
                ],
            ),
        )

        for benchmark, dataset_writer, runner, split, expected_question_summary, expected_budget_context_ids in cases:
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = dataset_writer(tmp_path)
                out = tmp_path / "bench"
                compare_out = tmp_path / "comparison"
                other_cwd = tmp_path / "other-cwd"
                other_cwd.mkdir()
                fts = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-budget-verify-a",
                    retrieval_mode="fts",
                    context_budget_tokens=200,
                )
                multihop = runner(
                    out,
                    dataset,
                    split,
                    seed=0,
                    run_id=f"{benchmark}-budget-verify-b",
                    retrieval_mode="fts-multihop",
                    context_budget_tokens=200,
                )

                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    comparison = self._main_json(
                        [
                            "bench",
                            "compare",
                            os.path.relpath(fts["result_path"], other_cwd),
                            os.path.relpath(multihop["result_path"], other_cwd),
                            "--out",
                            os.path.relpath(compare_out, other_cwd),
                        ]
                    )
                    report_summary_output = self._main_text(
                        ["bench", "report", comparison["comparison_path"], "--summary-only"]
                    )
                    dashboard_summary_output = self._main_text(
                        ["bench", "dashboard", comparison["comparison_path"], "--summary-only"]
                    )
                    verify_summary_output = self._main_text(
                        ["bench", "verify", comparison["comparison_path"], "--summary-only"]
                    )
                    verify = self._main_json(["bench", "verify", comparison["comparison_path"]])
                finally:
                    os.chdir(previous_cwd)

                comparison_path = Path(comparison["comparison_path"])
                if not comparison_path.is_absolute():
                    comparison_path = (other_cwd / comparison_path).resolve()
                comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
                direct_verify = verify_benchmark_artifact(comparison_path)
                expected_mode_proofs = [
                    {
                        "retrieval_mode": run["retrieval_mode"],
                        "result_hash": run["result_hash"],
                        "aggregate_merkle_root": run["proof"]["aggregate_merkle_root"],
                    }
                    for run in comparison_payload["runs"]
                ]
                expected_proof_lines = [
                    (
                        "Mode proof "
                        f"{proof['retrieval_mode']}: "
                        f"result_hash={proof['result_hash']} "
                        f"aggregate_merkle_root={proof['aggregate_merkle_root']}"
                    )
                    for proof in expected_mode_proofs
                ]
                expected_memory_count_deltas = [
                    {
                        "question_id": question["question_id"],
                        "retrieval_mode": delta["retrieval_mode"],
                        "retrieved_memory_count_delta": delta.get("retrieved_memory_count_delta"),
                        "injected_memory_count_delta": delta.get("injected_memory_count_delta"),
                        "withheld_memory_count_delta": delta.get("withheld_memory_count_delta"),
                    }
                    for question in comparison_payload["questions"]
                    for delta in question.get("deltas", [])
                    if any(
                        delta.get(key) not in (None, 0)
                        for key in (
                            "retrieved_memory_count_delta",
                            "injected_memory_count_delta",
                            "withheld_memory_count_delta",
                        )
                    )
                ]
                expected_efficiency_deltas = [
                    {
                        "question_id": question["question_id"],
                        "retrieval_mode": delta["retrieval_mode"],
                        "retrieval_latency_ms_delta": delta.get("retrieval_latency_ms_delta"),
                        "total_tokens_delta": delta.get("total_tokens_delta"),
                    }
                    for question in comparison_payload["questions"]
                    for delta in question.get("deltas", [])
                    if any(
                        delta.get(key) not in (None, 0)
                        for key in (
                            "retrieval_latency_ms_delta",
                            "total_tokens_delta",
                        )
                    )
                ]

                self.assertTrue(comparison["ok"])
                self.assertTrue(verify["ok"])
                self.assertTrue(direct_verify["ok"])
                self.assertEqual(verify["artifact_type"], "comparison")
                self.assertEqual(direct_verify["artifact_type"], "comparison")
                self.assertEqual(verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(direct_verify["comparison_hash"], comparison_payload["comparison_hash"])
                self.assertEqual(self._failed_check_names(verify), set())
                self.assertEqual(self._failed_check_names(direct_verify), set())
                self.assertEqual(verify["summary"]["benchmark"], benchmark)
                self.assertEqual(verify["summary"]["dataset"], str(dataset))
                self.assertEqual(verify["summary"]["split"], split)
                self.assertEqual(verify["summary"]["context_budget_tokens"], 200)
                self.assertEqual(verify["summary"]["verification_status"], "ok")
                self.assertEqual(verify["summary"]["question_summary"], expected_question_summary)
                self.assertEqual(
                    verify["summary"]["budget_context_question_ids"],
                    expected_budget_context_ids,
                )
                self.assertEqual(verify["summary"]["memory_count_deltas"], expected_memory_count_deltas)
                self.assertEqual(verify["summary"]["efficiency_deltas"], expected_efficiency_deltas)
                self.assertEqual(verify["summary"]["mode_proofs"], expected_mode_proofs)
                self.assertEqual(direct_verify["summary"], verify["summary"])

                self.assertIn("Benchmark verify", verify_summary_output)
                self.assertIn("Artifact: comparison", verify_summary_output)
                self.assertIn("Verification: ok", verify_summary_output)
                self.assertIn("Failed checks: none", verify_summary_output)
                self.assertIn("Context budget tokens: 200", verify_summary_output)
                self.assertIn(
                    f"Stable wins: {expected_question_summary['stable_wins']['count']}",
                    verify_summary_output,
                )
                self.assertIn(
                    f"Stable misses: {expected_question_summary['stable_misses']['count']}",
                    verify_summary_output,
                )
                self.assertIn(
                    "Budget-dropped stable context ids: " + ", ".join(expected_budget_context_ids),
                    verify_summary_output,
                )
                for delta in expected_memory_count_deltas:
                    self.assertIn(
                        "Memory count delta "
                        f"{delta['question_id']} ({delta['retrieval_mode']}): "
                        f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                        f"injected={delta['injected_memory_count_delta']:+d} "
                        f"withheld={delta['withheld_memory_count_delta']:+d}",
                        verify_summary_output,
                    )
                for delta in expected_efficiency_deltas:
                    latency_delta = delta["retrieval_latency_ms_delta"]
                    token_delta = delta["total_tokens_delta"]
                    latency_display = f"{latency_delta:+.3f}" if isinstance(latency_delta, float) else f"{latency_delta:+d}"
                    token_display = f"{token_delta:+.3f}" if isinstance(token_delta, float) else f"{token_delta:+d}"
                    expected_line = (
                        "Efficiency delta "
                        f"{delta['question_id']} ({delta['retrieval_mode']}): "
                        f"retrieval_latency_ms={latency_display} "
                        f"total_tokens={token_display}"
                    )
                    self.assertIn(
                        expected_line,
                        verify_summary_output,
                    )
                    self.assertIn(expected_line, report_summary_output)
                    self.assertIn(expected_line, dashboard_summary_output)
                for delta in expected_memory_count_deltas:
                    expected_line = (
                        "Memory count delta "
                        f"{delta['question_id']} ({delta['retrieval_mode']}): "
                        f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                        f"injected={delta['injected_memory_count_delta']:+d} "
                        f"withheld={delta['withheld_memory_count_delta']:+d}"
                    )
                    self.assertIn(expected_line, report_summary_output)
                    self.assertIn(expected_line, dashboard_summary_output)
                self.assertIn("Benchmark report", report_summary_output)
                self.assertIn("Artifact: comparison", report_summary_output)
                self.assertIn("Verification: ok", report_summary_output)
                self.assertIn("Context budget tokens: 200", report_summary_output)
                self.assertIn(
                    "Budget-dropped stable context ids: " + ", ".join(expected_budget_context_ids),
                    report_summary_output,
                )
                self.assertIn("Benchmark dashboard", dashboard_summary_output)
                self.assertIn("Artifact: comparison", dashboard_summary_output)
                self.assertIn("Verification: ok", dashboard_summary_output)
                self.assertIn("Context budget tokens: 200", dashboard_summary_output)
                self.assertIn(
                    "Budget-dropped stable context ids: " + ", ".join(expected_budget_context_ids),
                    dashboard_summary_output,
                )
                for proof_line in expected_proof_lines:
                    self.assertIn(proof_line, verify_summary_output)
                    self.assertIn(proof_line, report_summary_output)
                    self.assertIn(proof_line, dashboard_summary_output)

    def test_budget_constrained_locomo_history_gap_is_repeatable(self):
        observed = set()

        for attempt in range(3):
            with self.subTest(attempt=attempt), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                dataset = self._write_richer_locomo_jsonl(tmp_path)
                result = run_locomo_benchmark(
                    tmp_path / "bench",
                    dataset,
                    "dev",
                    seed=0,
                    run_id=f"locomo-budget-repeat-{attempt}",
                    retrieval_mode="fts-multihop",
                    context_budget_tokens=200,
                )
                result_payload = json.loads(Path(result["result_path"]).read_text(encoding="utf-8"))
                question_payload = next(
                    question
                    for question in result_payload["questions"]
                    if question["question_id"] == "locomo-routing-owner-history-gap"
                )
                observed.add(
                    (
                        question_payload["correct"],
                        question_payload["final_answer"],
                        question_payload["outcome_reason"],
                    )
                )

        self.assertEqual(observed, {(True, "Jules.", "correct_supported_answer")})

    def test_cli_dashboard_renders_from_matrix_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            run_benchmark_matrix(out, "synthetic", seed=0, run_id="cli-dashboard-matrix")

            dashboard = self._main_json(["bench", "dashboard", str(out / "cli-dashboard-matrix")])

            self.assertTrue(dashboard["ok"])
            self.assertTrue(Path(dashboard["dashboard_path"]).exists())
            self.assertEqual(Path(dashboard["dashboard_path"]).name, "benchmark-dashboard.html")

    def test_cli_longmemeval_dashboard_and_public_page_render_from_persisted_matrix_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="cli-longmemeval-matrix",
            )

            dashboard = self._main_json(["bench", "dashboard", str(tmp_path / "bench" / "cli-longmemeval-matrix")])
            page = self._main_json(["bench", "public-page", str(tmp_path / "bench" / "cli-longmemeval-matrix")])
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")
            mode_proofs = matrix["summary"]["mode_proofs"]

            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["summary"]["benchmark"], "longmemeval")
            self.assertEqual(dashboard["summary"]["dataset"], str(dataset))
            self.assertEqual(dashboard["summary"]["split"], "small")
            self.assertEqual(dashboard["summary"]["dataset_version"], "local-dataset")
            self.assertEqual(dashboard["summary"]["dataset_hash"], matrix["dataset_hash"])
            self.assertEqual(dashboard["summary"]["filtered_dataset_hash"], matrix["filtered_dataset_hash"])
            self.assertEqual(dashboard["summary"]["mode_proofs"], mode_proofs)

            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["benchmark"], "longmemeval")
            self.assertEqual(page["summary"]["dataset"], str(dataset))
            self.assertEqual(page["summary"]["split"], "small")
            self.assertEqual(page["summary"]["dataset_version"], "local-dataset")
            self.assertEqual(page["summary"]["dataset_hash"], matrix["dataset_hash"])
            self.assertEqual(page["summary"]["filtered_dataset_hash"], matrix["filtered_dataset_hash"])
            self.assertEqual(page["summary"]["mode_proofs"], mode_proofs)

            self._assert_rendered_mode_proof_hops(mode_proofs, dashboard_html)
            self._assert_rendered_mode_proof_hops(mode_proofs, page_html)
            self.assertIn(str(dataset), dashboard_html)
            self.assertIn("small", dashboard_html)
            self.assertIn(matrix["dataset_hash"], dashboard_html)
            self.assertIn(matrix["filtered_dataset_hash"], dashboard_html)
            self.assertIn(str(dataset), page_html)
            self.assertIn("small", page_html)
            self.assertIn(matrix["dataset_hash"], page_html)
            self.assertIn(matrix["filtered_dataset_hash"], page_html)

    def test_cli_locomo_dashboard_and_public_page_render_from_persisted_matrix_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_locomo_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="cli-locomo-matrix",
            )

            dashboard = self._main_json(["bench", "dashboard", str(tmp_path / "bench" / "cli-locomo-matrix")])
            page = self._main_json(["bench", "public-page", str(tmp_path / "bench" / "cli-locomo-matrix")])
            dashboard_html = Path(dashboard["dashboard_path"]).read_text(encoding="utf-8")
            page_html = Path(page["page_path"]).read_text(encoding="utf-8")
            mode_proofs = matrix["summary"]["mode_proofs"]

            self.assertTrue(dashboard["ok"])
            self.assertEqual(dashboard["summary"]["benchmark"], "locomo")
            self.assertEqual(dashboard["summary"]["dataset"], str(dataset))
            self.assertEqual(dashboard["summary"]["split"], "dev")
            self.assertEqual(dashboard["summary"]["dataset_version"], "local-dataset")
            self.assertEqual(dashboard["summary"]["dataset_hash"], matrix["dataset_hash"])
            self.assertEqual(dashboard["summary"]["filtered_dataset_hash"], matrix["filtered_dataset_hash"])
            self.assertEqual(dashboard["summary"]["mode_proofs"], mode_proofs)

            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local scaffold evidence")
            self.assertEqual(page["summary"]["benchmark"], "locomo")
            self.assertEqual(page["summary"]["dataset"], str(dataset))
            self.assertEqual(page["summary"]["split"], "dev")
            self.assertEqual(page["summary"]["dataset_version"], "local-dataset")
            self.assertEqual(page["summary"]["dataset_hash"], matrix["dataset_hash"])
            self.assertEqual(page["summary"]["filtered_dataset_hash"], matrix["filtered_dataset_hash"])
            self.assertEqual(page["summary"]["mode_proofs"], mode_proofs)

            self._assert_rendered_mode_proof_hops(mode_proofs, dashboard_html)
            self._assert_rendered_mode_proof_hops(mode_proofs, page_html)
            self.assertIn(str(dataset), dashboard_html)
            self.assertIn("dev", dashboard_html)
            self.assertIn(matrix["dataset_hash"], dashboard_html)
            self.assertIn(matrix["filtered_dataset_hash"], dashboard_html)
            self.assertIn(str(dataset), page_html)
            self.assertIn("dev", page_html)
            self.assertIn(matrix["dataset_hash"], page_html)
            self.assertIn(matrix["filtered_dataset_hash"], page_html)

    def test_cli_bench_compare_summary_only_surfaces_stable_miss_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            out = tmp_path / "bench"
            fts = run_longmemeval_benchmark(
                out,
                dataset,
                "analysis",
                seed=0,
                run_id="summary-a",
                retrieval_mode="fts",
            )
            multihop = run_longmemeval_benchmark(
                out,
                dataset,
                "analysis",
                seed=0,
                run_id="summary-b",
                retrieval_mode="fts-multihop",
            )
            comparison_path = tmp_path / "comparison" / "benchmark-comparison.json"

            output = self._main_text(
                [
                    "bench",
                    "compare",
                    str(fts["result_path"]),
                    str(multihop["result_path"]),
                    "--out",
                    str(comparison_path),
                    "--summary-only",
                ]
            )

            self.assertIn("Benchmark comparison", output)
            self.assertIn("Verification: ok", output)
            self.assertIn("Benchmark: longmemeval", output)
            self.assertIn(f"Dataset: {dataset}", output)
            self.assertIn("Split: analysis", output)
            persisted_comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            question_summary = persisted_comparison["question_summary"]
            self.assertIn(
                f"Visible deltas: {question_summary['visible_delta_question_count']}",
                output,
            )
            self.assertIn(
                f"Stable wins: {question_summary['stable_wins']['count']}",
                output,
            )
            self.assertIn(
                f"Stable misses: {question_summary['stable_misses']['count']}",
                output,
            )
            if question_summary["stable_wins"]["question_ids"]:
                self.assertIn(
                    "Stable win ids: " + ", ".join(question_summary["stable_wins"]["question_ids"]),
                    output,
                )
            if question_summary["stable_misses"]["question_ids"]:
                self.assertIn(
                    "Stable miss ids: " + ", ".join(question_summary["stable_misses"]["question_ids"]),
                    output,
                )
            expected_memory_count_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieved_memory_count_delta": delta.get("retrieved_memory_count_delta"),
                    "injected_memory_count_delta": delta.get("injected_memory_count_delta"),
                    "withheld_memory_count_delta": delta.get("withheld_memory_count_delta"),
                }
                for question in persisted_comparison["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieved_memory_count_delta",
                        "injected_memory_count_delta",
                        "withheld_memory_count_delta",
                    )
                )
            ]
            expected_efficiency_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieval_latency_ms_delta": delta.get("retrieval_latency_ms_delta"),
                    "total_tokens_delta": delta.get("total_tokens_delta"),
                }
                for question in persisted_comparison["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieval_latency_ms_delta",
                        "total_tokens_delta",
                    )
                )
            ]
            for delta in expected_memory_count_deltas:
                self.assertIn(
                    "Memory count delta "
                    f"{delta['question_id']} ({delta['retrieval_mode']}): "
                    f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                    f"injected={delta['injected_memory_count_delta']:+d} "
                    f"withheld={delta['withheld_memory_count_delta']:+d}",
                    output,
                )
            for delta in expected_efficiency_deltas:
                self.assertIn(
                    "Efficiency delta "
                    f"{delta['question_id']} ({delta['retrieval_mode']}): retrieval_latency_ms=",
                    output,
                )
            first_mode = persisted_comparison["runs"][0]
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['proof']['aggregate_merkle_root']}",
                output,
            )
            self.assertNotIn("Context budget tokens:", output)
            self.assertNotIn("Budget-dropped stable context ids:", output)
            self.assertIn(f"Comparison JSON: {comparison_path}", output)
            self.assertIn("Report: ", output)
            self.assertIn("Dashboard: ", output)

    def test_cli_bench_compare_summary_only_surfaces_budget_context_and_delta_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            out = tmp_path / "bench"
            fts = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="summary-budget-a",
                retrieval_mode="fts",
                context_budget_tokens=200,
            )
            multihop = run_locomo_benchmark(
                out,
                dataset,
                "dev",
                seed=0,
                run_id="summary-budget-b",
                retrieval_mode="fts-multihop",
                context_budget_tokens=200,
            )
            comparison_path = tmp_path / "comparison-budget" / "benchmark-comparison.json"

            output = self._main_text(
                [
                    "bench",
                    "compare",
                    str(fts["result_path"]),
                    str(multihop["result_path"]),
                    "--out",
                    str(comparison_path),
                    "--summary-only",
                ]
            )

            self.assertIn("Benchmark comparison", output)
            self.assertIn("Verification: ok", output)
            self.assertIn("Benchmark: locomo", output)
            self.assertIn(f"Dataset: {dataset}", output)
            self.assertIn("Split: dev", output)
            persisted_comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            question_summary = persisted_comparison["question_summary"]
            budget_context_ids = [
                question["question_id"]
                for question in persisted_comparison["questions"]
                if any(run.get("budget_dropped_memories") for run in question.get("runs", []))
            ]
            self.assertIn("Context budget tokens: 200", output)
            self.assertIn(
                f"Visible deltas: {question_summary['visible_delta_question_count']}",
                output,
            )
            self.assertIn(
                f"Stable wins: {question_summary['stable_wins']['count']}",
                output,
            )
            self.assertIn(
                f"Stable misses: {question_summary['stable_misses']['count']}",
                output,
            )
            if question_summary["stable_wins"]["question_ids"]:
                self.assertIn(
                    "Stable win ids: " + ", ".join(question_summary["stable_wins"]["question_ids"]),
                    output,
                )
            if question_summary["stable_misses"]["question_ids"]:
                self.assertIn(
                    "Stable miss ids: " + ", ".join(question_summary["stable_misses"]["question_ids"]),
                    output,
                )
            self.assertIn(
                "Budget-dropped stable context ids: " + ", ".join(budget_context_ids),
                output,
            )
            expected_memory_count_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieved_memory_count_delta": delta.get("retrieved_memory_count_delta"),
                    "injected_memory_count_delta": delta.get("injected_memory_count_delta"),
                    "withheld_memory_count_delta": delta.get("withheld_memory_count_delta"),
                }
                for question in persisted_comparison["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieved_memory_count_delta",
                        "injected_memory_count_delta",
                        "withheld_memory_count_delta",
                    )
                )
            ]
            expected_efficiency_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieval_latency_ms_delta": delta.get("retrieval_latency_ms_delta"),
                    "total_tokens_delta": delta.get("total_tokens_delta"),
                }
                for question in persisted_comparison["questions"]
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieval_latency_ms_delta",
                        "total_tokens_delta",
                    )
                )
            ]
            for delta in expected_memory_count_deltas:
                self.assertIn(
                    "Memory count delta "
                    f"{delta['question_id']} ({delta['retrieval_mode']}): "
                    f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                    f"injected={delta['injected_memory_count_delta']:+d} "
                    f"withheld={delta['withheld_memory_count_delta']:+d}",
                    output,
                )
            for delta in expected_efficiency_deltas:
                self.assertIn(
                    "Efficiency delta "
                    f"{delta['question_id']} ({delta['retrieval_mode']}): retrieval_latency_ms=",
                    output,
                )
            first_mode = persisted_comparison["runs"][0]
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['proof']['aggregate_merkle_root']}",
                output,
            )
            self.assertIn(f"Comparison JSON: {comparison_path}", output)
            self.assertIn("Report: ", output)
            self.assertIn("Dashboard: ", output)

    def test_cli_bench_report_dashboard_and_public_page_summary_only_surface_question_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_longmemeval_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "longmemeval",
                dataset=dataset,
                split="analysis",
                seed=0,
                run_id="summary-matrix",
            )
            matrix_path = Path(matrix["matrix_path"])
            comparison_path = self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"])
            first_mode = matrix["summary"]["mode_proofs"][0]

            report_output = self._main_text(["bench", "report", str(matrix_path), "--summary-only"])
            dashboard_output = self._main_text(["bench", "dashboard", str(matrix_path), "--summary-only"])
            page_output = self._main_text(["bench", "public-page", str(matrix_path), "--summary-only"])
            comparison_dashboard_output = self._main_text(["bench", "dashboard", str(comparison_path), "--summary-only"])

            self.assertIn("Benchmark report", report_output)
            self.assertIn("Artifact: matrix", report_output)
            self.assertIn("Verification: ok", report_output)
            self.assertIn("Comparison verification: ok", report_output)
            self.assertIn("Visible deltas: 1", report_output)
            self.assertIn("Stable wins: 7", report_output)
            self.assertIn("Stable misses: 0", report_output)
            self.assertIn(
                "Stable win ids: lme-temporal-change-when, lme-knowledge-update-current-target, "
                "lme-knowledge-update-stale-decoy, lme-knowledge-update-ambiguous-restatement, "
                "lme-knowledge-update-history-wording-gap, lme-routing-owner-wording-gap, "
                "lme-current-conflict-abstain",
                report_output,
            )
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                report_output,
            )

            self.assertIn("Benchmark dashboard", dashboard_output)
            self.assertIn("Artifact: matrix", dashboard_output)
            self.assertIn("Comparison verification: ok", dashboard_output)
            self.assertIn("Verification: ok", dashboard_output)
            self.assertIn("Visible deltas: 1", dashboard_output)
            self.assertIn("Stable wins: 7", dashboard_output)
            self.assertIn("Stable misses: 0", dashboard_output)
            self.assertIn(
                "Stable win ids: lme-temporal-change-when, lme-knowledge-update-current-target, "
                "lme-knowledge-update-stale-decoy, lme-knowledge-update-ambiguous-restatement, "
                "lme-knowledge-update-history-wording-gap, lme-routing-owner-wording-gap, "
                "lme-current-conflict-abstain",
                dashboard_output,
            )
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                dashboard_output,
            )

            self.assertIn("Benchmark dashboard", comparison_dashboard_output)
            self.assertIn("Artifact: comparison", comparison_dashboard_output)
            self.assertIn("Verification: ok", comparison_dashboard_output)
            self.assertIn("Visible deltas: 1", comparison_dashboard_output)
            self.assertIn("Stable wins: 7", comparison_dashboard_output)
            self.assertIn("Stable misses: 0", comparison_dashboard_output)
            self.assertIn(
                "Stable win ids: lme-temporal-change-when, lme-knowledge-update-current-target, "
                "lme-knowledge-update-stale-decoy, lme-knowledge-update-ambiguous-restatement, "
                "lme-knowledge-update-history-wording-gap, lme-routing-owner-wording-gap, "
                "lme-current-conflict-abstain",
                comparison_dashboard_output,
            )

            self.assertIn("Public benchmark page", page_output)
            self.assertIn("Claim status: local scaffold evidence", page_output)
            self.assertIn("Verification: ok", page_output)
            self.assertIn("Comparison verification: ok", page_output)
            self.assertIn("Visible deltas: 1", page_output)
            self.assertIn("Stable wins: 7", page_output)
            self.assertIn("Stable misses: 0", page_output)
            self.assertIn(
                "Stable win ids: lme-temporal-change-when, lme-knowledge-update-current-target, "
                "lme-knowledge-update-stale-decoy, lme-knowledge-update-ambiguous-restatement, "
                "lme-knowledge-update-history-wording-gap, lme-routing-owner-wording-gap, "
                "lme-current-conflict-abstain",
                page_output,
            )
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                page_output,
            )

    def test_cli_richer_locomo_summary_only_surfaces_matrix_and_comparison_question_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset = self._write_richer_locomo_jsonl(tmp_path)
            matrix = run_benchmark_matrix(
                tmp_path / "bench",
                "locomo",
                dataset=dataset,
                split="dev",
                seed=0,
                run_id="locomo-summary-matrix",
            )
            matrix_path = Path(matrix["matrix_path"])
            comparison_path = self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"])
            first_mode = matrix["summary"]["mode_proofs"][0]

            report_output = self._main_text(["bench", "report", str(matrix_path), "--summary-only"])
            dashboard_output = self._main_text(["bench", "dashboard", str(matrix_path), "--summary-only"])
            page_output = self._main_text(["bench", "public-page", str(matrix_path), "--summary-only"])
            comparison_report_output = self._main_text(["bench", "report", str(comparison_path), "--summary-only"])
            comparison_dashboard_output = self._main_text(
                ["bench", "dashboard", str(comparison_path), "--summary-only"]
            )

            self.assertIn("Benchmark report", report_output)
            self.assertIn("Artifact: matrix", report_output)
            self.assertIn("Verification: ok", report_output)
            self.assertIn("Comparison verification: ok", report_output)
            self.assertIn("Benchmark: locomo", report_output)
            self.assertIn("Split: dev", report_output)
            self.assertIn("Visible deltas: 1", report_output)
            self.assertIn("Stable wins: 4", report_output)
            self.assertIn("Stable misses: 0", report_output)
            self.assertIn(
                "Stable win ids: locomo-temporal-rich, locomo-routing-owner-wording-gap, "
                "locomo-routing-owner-history-gap, locomo-abstention-rich",
                report_output,
            )
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                report_output,
            )

            self.assertIn("Benchmark dashboard", dashboard_output)
            self.assertIn("Artifact: matrix", dashboard_output)
            self.assertIn("Comparison verification: ok", dashboard_output)
            self.assertIn("Verification: ok", dashboard_output)
            self.assertIn("Benchmark: locomo", dashboard_output)
            self.assertIn("Split: dev", dashboard_output)
            self.assertIn("Visible deltas: 1", dashboard_output)
            self.assertIn("Stable wins: 4", dashboard_output)
            self.assertIn("Stable misses: 0", dashboard_output)
            self.assertIn(
                "Stable win ids: locomo-temporal-rich, locomo-routing-owner-wording-gap, "
                "locomo-routing-owner-history-gap, locomo-abstention-rich",
                dashboard_output,
            )
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                dashboard_output,
            )

            self.assertIn("Public benchmark page", page_output)
            self.assertIn("Claim status: local scaffold evidence", page_output)
            self.assertIn("Verification: ok", page_output)
            self.assertIn("Comparison verification: ok", page_output)
            self.assertIn("Benchmark: locomo", page_output)
            self.assertIn("Split: dev", page_output)
            self.assertIn("Visible deltas: 1", page_output)
            self.assertIn("Stable wins: 4", page_output)
            self.assertIn("Stable misses: 0", page_output)
            self.assertIn(
                "Stable win ids: locomo-temporal-rich, locomo-routing-owner-wording-gap, "
                "locomo-routing-owner-history-gap, locomo-abstention-rich",
                page_output,
            )
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                page_output,
            )

            self.assertIn("Benchmark report", comparison_report_output)
            self.assertIn("Artifact: comparison", comparison_report_output)
            self.assertIn("Verification: ok", comparison_report_output)
            self.assertIn("Benchmark: locomo", comparison_report_output)
            self.assertIn("Split: dev", comparison_report_output)
            self.assertIn("Visible deltas: 1", comparison_report_output)
            self.assertIn("Stable wins: 4", comparison_report_output)
            self.assertIn("Stable misses: 0", comparison_report_output)
            self.assertIn(
                "Stable win ids: locomo-temporal-rich, locomo-routing-owner-wording-gap, "
                "locomo-routing-owner-history-gap, locomo-abstention-rich",
                comparison_report_output,
            )

            self.assertIn("Benchmark dashboard", comparison_dashboard_output)
            self.assertIn("Artifact: comparison", comparison_dashboard_output)
            self.assertIn("Verification: ok", comparison_dashboard_output)
            self.assertIn("Benchmark: locomo", comparison_dashboard_output)
            self.assertIn("Split: dev", comparison_dashboard_output)
            self.assertIn("Visible deltas: 1", comparison_dashboard_output)
            self.assertIn("Stable wins: 4", comparison_dashboard_output)
            self.assertIn("Stable misses: 0", comparison_dashboard_output)
            self.assertIn(
                "Stable win ids: locomo-temporal-rich, locomo-routing-owner-wording-gap, "
                "locomo-routing-owner-history-gap, locomo-abstention-rich",
                comparison_dashboard_output,
            )

    def test_cli_bench_matrix_summary_only_surfaces_latest_matrix_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            matrix_dir = tmp_path / "bench-cli"

            output = self._main_text(
                [
                    "bench",
                    "matrix",
                    "synthetic",
                    "--out",
                    str(matrix_dir),
                    "--run-id",
                    "summary-only-matrix",
                    "--summary-only",
                ]
            )
            matrix = json.loads(
                (matrix_dir / "summary-only-matrix" / "benchmark-matrix.json").read_text(encoding="utf-8")
            )
            first_mode = matrix["mode_runs"][0]
            question = next(
                question
                for question in matrix["comparison"]["questions"]
                if question["question_id"] == "synthetic-multihop-kestrel-locker"
            )
            expected_memory_count_deltas = [
                {
                    "question_id": question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieved_memory_count_delta": delta.get("retrieved_memory_count_delta"),
                    "injected_memory_count_delta": delta.get("injected_memory_count_delta"),
                    "withheld_memory_count_delta": delta.get("withheld_memory_count_delta"),
                }
                for delta in question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieved_memory_count_delta",
                        "injected_memory_count_delta",
                        "withheld_memory_count_delta",
                    )
                )
            ]
            expected_efficiency_deltas = [
                {
                    "question_id": comparison_question["question_id"],
                    "retrieval_mode": delta["retrieval_mode"],
                    "retrieval_latency_ms_delta": delta.get("retrieval_latency_ms_delta"),
                    "total_tokens_delta": delta.get("total_tokens_delta"),
                }
                for comparison_question in matrix["comparison"]["questions"]
                for delta in comparison_question.get("deltas", [])
                if any(
                    delta.get(key) not in (None, 0)
                    for key in (
                        "retrieval_latency_ms_delta",
                        "total_tokens_delta",
                    )
                )
            ]

            self.assertIn("Benchmark matrix", output)
            self.assertIn("Verification: ok", output)
            self.assertIn("Comparison verification: ok", output)
            self.assertIn("Benchmark: synthetic", output)
            self.assertIn("Dataset: synthetic", output)
            self.assertIn("Split: n/a", output)
            self.assertIn("Visible deltas: 1", output)
            self.assertIn("Stable wins: 3", output)
            self.assertIn("Stable misses: 0", output)
            self.assertIn(
                f"Mode proof {first_mode['retrieval_mode']}: result_hash={first_mode['result_hash']} "
                f"aggregate_merkle_root={first_mode['aggregate_merkle_root']}",
                output,
            )
            for delta in expected_memory_count_deltas:
                self.assertIn(
                    "Memory count delta "
                    f"{delta['question_id']} ({delta['retrieval_mode']}): "
                    f"retrieved={delta['retrieved_memory_count_delta']:+d} "
                    f"injected={delta['injected_memory_count_delta']:+d} "
                    f"withheld={delta['withheld_memory_count_delta']:+d}",
                    output,
                )
            for delta in expected_efficiency_deltas[:10]:
                latency_delta = delta["retrieval_latency_ms_delta"]
                token_delta = delta["total_tokens_delta"]
                latency_display = f"{latency_delta:+.3f}" if isinstance(latency_delta, float) else f"{latency_delta:+d}"
                token_display = f"{token_delta:+.3f}" if isinstance(token_delta, float) else f"{token_delta:+d}"
                self.assertIn(
                    "Efficiency delta "
                    f"{delta['question_id']} ({delta['retrieval_mode']}): "
                    f"retrieval_latency_ms={latency_display} "
                    f"total_tokens={token_display}",
                    output,
                )
            if len(expected_efficiency_deltas) > 10:
                self.assertIn(f"Efficiency deltas omitted: {len(expected_efficiency_deltas) - 10}", output)
            self.assertIn(
                f"Matrix JSON: {tmp_path / 'bench-cli' / 'summary-only-matrix' / 'benchmark-matrix.json'}",
                output,
            )
            self.assertIn(
                f"Comparison JSON: {tmp_path / 'bench-cli' / 'summary-only-matrix' / 'benchmark-comparison.json'}",
                output,
            )
            self.assertIn(
                f"Score summary JSON: {tmp_path / 'bench-cli' / 'summary-only-matrix' / 'score-summary.json'}",
                output,
            )
            self.assertIn(
                f"Report: {tmp_path / 'bench-cli' / 'summary-only-matrix' / 'matrix-report.md'}",
                output,
            )

    def test_public_benchmark_page_renders_proof_and_claim_guardrails(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="public-page-matrix")

            page = render_public_benchmark_page(Path(matrix["matrix_path"]))
            html_text = Path(page["page_path"]).read_text(encoding="utf-8")
            first_mode = matrix["summary"]["mode_proofs"][0]
            changed_questions = [
                question
                for question in matrix["comparison"]["questions"]
                if any(
                    delta.get("correct_changed")
                    or delta.get("final_answer_changed")
                    or delta.get("outcome_reason_changed")
                    or delta.get("retrieved_memories_added")
                    or delta.get("retrieved_memories_removed")
                    or delta.get("injected_memories_added")
                    or delta.get("injected_memories_removed")
                    or delta.get("withheld_memories_added")
                    or delta.get("withheld_memories_removed")
                    for delta in question.get("deltas", [])
                    if isinstance(delta, dict)
                )
            ]

            self.assertTrue(page["ok"])
            self.assertEqual(page["claim_status"], "local synthetic proof")
            self.assertEqual(page["matrix_hash"], matrix["matrix_hash"])
            self.assertEqual(page["comparison_hash"], matrix["comparison_hash"])
            self.assertEqual(page["summary"]["categories"], matrix["summary"]["categories"])
            self.assertEqual(page["summary"]["question_summary"], matrix["comparison"]["question_summary"])
            self.assertIn("Benchmark claims with receipts.", html_text)
            self.assertIn("Public ranking", html_text)
            self.assertIn("local synthetic proof", html_text)
            self.assertIn("not public leaderboard rankings", html_text)
            self.assertIn("Matrix verify", html_text)
            self.assertIn("Comparison verify", html_text)
            self.assertIn("Matrix failed checks", html_text)
            self.assertIn("Comparison failed checks", html_text)
            self.assertIn("Score summary artifact", html_text)
            self.assertIn("score-summary.json", html_text)
            self.assertIn("Category Performance", html_text)
            self.assertIn("Per-mode category performance", html_text)
            self.assertIn("Question Evidence", html_text)
            self.assertIn("Deltas vs baseline", html_text)
            self.assertIn("Answer delta", html_text)
            self.assertIn("Retrieval latency delta", html_text)
            self.assertIn("latency delta ", html_text)
            self.assertIn("Retrieved evidence +/-", html_text)
            self.assertIn("Per-Mode Proof Hops", html_text)
            self.assertIn(first_mode["retrieval_mode"], html_text)
            self.assertIn(first_mode["result_hash"], html_text)
            self.assertIn(first_mode["aggregate_merkle_root"], html_text)
            self.assertIn(matrix["matrix_hash"], html_text)
            self.assertIn(matrix["comparison_hash"], html_text)
            self.assertIn("zmem bench matrix synthetic", html_text)
            self.assertTrue(changed_questions)
            self.assertIn(changed_questions[0]["question_id"], html_text)
            self.assertIn("locker code is 4182", html_text)

    def test_public_benchmark_page_surfaces_failed_verification_summary_when_matrix_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = run_benchmark_matrix(Path(tmp), "synthetic", seed=0, run_id="tampered-public-page")
            matrix_path = Path(matrix["matrix_path"])
            payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            payload["mode_runs"][0]["summary"]["accuracy"] = 0.123
            payload["matrix_hash"] = sha256_text(
                stable_json({key: value for key, value in payload.items() if key != "matrix_hash"})
            )
            matrix_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            page = render_public_benchmark_page(matrix_path)
            html_text = Path(page["page_path"]).read_text(encoding="utf-8")

            self.assertIn("Matrix failed checks", html_text)
            self.assertIn("mode_runs", html_text)
            self.assertIn(">failed<", html_text)

    def test_cli_public_page_renders_from_matrix_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            run_benchmark_matrix(out, "synthetic", seed=0, run_id="cli-public-page-matrix")

            page = self._main_json(["bench", "public-page", str(out / "cli-public-page-matrix")])

            self.assertTrue(page["ok"])
            self.assertTrue(Path(page["page_path"]).exists())
            self.assertEqual(Path(page["page_path"]).name, "public-benchmarks.html")

    def test_compare_surfaces_failed_verification_when_result_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            run_synthetic_benchmark(out, seed=0, run_id="tamper-compare-a")
            run_synthetic_benchmark(out, seed=1, run_id="tamper-compare-b")
            tampered_path = out / "tamper-compare-b" / "benchmark-result.json"
            result = json.loads(tampered_path.read_text(encoding="utf-8"))
            result["proof"]["aggregate_merkle_root"] = "0" * 64
            tampered_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            comparison = compare_benchmark_results(
                [out / "tamper-compare-a" / "benchmark-result.json", tampered_path]
            )

            self.assertFalse(comparison["ok"])
            self.assertEqual(comparison["proof"]["verification_status"], "failed")
            self.assertFalse(comparison["runs"][1]["verification_ok"])
            self.assertIn("result_hash", comparison["runs"][1]["failed_checks"])
            self.assertIn("aggregate_merkle_root", comparison["runs"][1]["failed_checks"])

    def test_mixed_benchmark_compare_warns_without_rejecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"
            synthetic = run_synthetic_benchmark(out, seed=0, run_id="mixed-synthetic")
            dataset = self._write_longmemeval_jsonl(Path(tmp))
            longmemeval = run_longmemeval_benchmark(out, dataset, "small", seed=0, run_id="mixed-lme")

            comparison = compare_benchmark_results([Path(synthetic["result_path"]), Path(longmemeval["result_path"])])

            self.assertTrue(comparison["ok"])
            self.assertFalse(comparison["compatibility"]["same_benchmark"])
            self.assertIn("benchmarks differ", comparison["compatibility"]["warnings"])

    def test_longmemeval_missing_and_nonlocal_dataset_path_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"

            missing_dataset = self._main_json(
                ["bench", "run", "longmemeval", "--out", str(out)],
                expected_code=1,
            )
            self.assertIn("requires --dataset", missing_dataset["error"])

            url_dataset = self._main_json(
                [
                    "bench",
                    "run",
                    "longmemeval",
                    "--dataset",
                    "https://example.test/longmemeval.jsonl",
                    "--out",
                    str(out),
                ],
                expected_code=1,
            )
            self.assertIn("local file path", url_dataset["error"])

            missing_file = self._main_json(
                [
                    "bench",
                    "run",
                    "longmemeval",
                    "--dataset",
                    str(Path(tmp) / "missing.jsonl"),
                    "--out",
                    str(out),
                ],
                expected_code=1,
            )
            self.assertIn("not found", missing_file["error"])

    def test_longmemeval_jsonl_run_writes_proof_layout_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_longmemeval_jsonl(Path(tmp))
            result = run_longmemeval_benchmark(Path(tmp) / "bench", dataset, "small", seed=0, run_id="lme-run")
            run_dir = Path(result["run_dir"])

            self.assertTrue(result["ok"])
            self.assertTrue((run_dir / "benchmark-run.json").exists())
            self.assertTrue((run_dir / "benchmark-result.json").exists())
            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "snapshots" / "before.snapshot.json").exists())
            self.assertTrue((run_dir / "snapshots" / "after.snapshot.json").exists())
            self.assertEqual(len(list((run_dir / "questions").glob("*.json"))), 2)
            self.assertEqual(len(list((run_dir / "receipts").glob("*.bundle.json"))), 2)

            run_manifest = json.loads((run_dir / "benchmark-run.json").read_text(encoding="utf-8"))
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["split"], "small")
            self.assertNotEqual(run_manifest["dataset_hash"], run_manifest["filtered_dataset_hash"])
            self.assertEqual(result_payload["question_count"], 2)
            self.assertEqual({question["question_id"] for question in result_payload["questions"]}, {"lme-1", "lme-2"})
            question_payload = json.loads((run_dir / result_payload["questions"][0]["question_path"]).read_text(encoding="utf-8"))
            self.assertTrue(question_payload["retrieved_memories"])
            self.assertTrue(question_payload["injected_memories"])
            self.assertIn("content", question_payload["retrieved_memories"][0])
            self.assertIn("content_hash", question_payload["injected_memories"][0])
            self.assertIsInstance(question_payload["withheld_memories"], list)

            verify = verify_benchmark_result(run_dir / "benchmark-result.json")

            self.assertTrue(verify["ok"])
            self.assertTrue(all(check["ok"] for check in verify["checks"]))
            self.assertEqual(result["summary"]["accuracy"], 1.0)

    def test_llm_answerer_records_pending_judgment_instead_of_false_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_longmemeval_jsonl(Path(tmp))
            with mock.patch("zerker_memory.bench._generate_llm_hypothesis", return_value="Nia owns launch."):
                result = run_longmemeval_benchmark(
                    Path(tmp) / "bench",
                    dataset,
                    "small",
                    seed=0,
                    run_id="lme-llm-pending",
                    answerer="llm",
                    compact_artifacts=True,
                )
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            report = (run_dir / "report.md").read_text(encoding="utf-8")

        self.assertIsNone(result["summary"]["accuracy"])
        self.assertEqual(result["summary"]["judged"], 0)
        self.assertEqual(result["summary"]["pending"], 2)
        self.assertEqual(result["summary"]["failed"], 0)
        self.assertTrue(all(question["correct"] is None for question in result_payload["questions"]))
        self.assertTrue(all(question["score"] is None for question in result_payload["questions"]))
        self.assertTrue(all(question["outcome_reason"] == "pending_judge" for question in result_payload["questions"]))
        self.assertIn("Accuracy: `pending`", report)
        self.assertIn("Status: `pending`", report)

    def test_locomo_llm_answerer_records_pending_judgment(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_locomo_jsonl(Path(tmp))
            with mock.patch("zerker_memory.bench._generate_llm_hypothesis", return_value="A generated answer."):
                result = run_locomo_benchmark(
                    Path(tmp) / "bench",
                    dataset,
                    "dev",
                    seed=0,
                    run_id="locomo-llm-pending",
                    answerer="llm",
                    compact_artifacts=True,
                )

        self.assertIsNone(result["summary"]["accuracy"])
        self.assertEqual(result["summary"]["judged"], 0)
        self.assertEqual(result["summary"]["pending"], result["summary"]["question_count"])
        self.assertEqual(result["summary"]["failed"], 0)

    def test_longmemeval_shared_session_reuses_history_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "longmemeval-shared-session.jsonl"
            records = [
                {
                    "question_id": "lme-shared-1",
                    "session_id": "session-alpha",
                    "split": "small",
                    "category": "single_session_user_recall",
                    "history": ["The launch owner is Nia."],
                    "question": "Who owns launch?",
                    "answer": "Nia.",
                    "supporting_facts": ["The launch owner is Nia."],
                    "should_abstain": False,
                },
                {
                    "question_id": "lme-shared-2",
                    "session_id": "session-alpha",
                    "split": "small",
                    "category": "single_session_user_recall",
                    "history": ["The launch owner is Nia."],
                    "question": "Who is responsible for launch?",
                    "answer": "Nia.",
                    "supporting_facts": ["The launch owner is Nia."],
                    "should_abstain": False,
                },
            ]
            dataset.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")

            result = run_longmemeval_benchmark(Path(tmp) / "bench", dataset, "small", seed=0, run_id="lme-shared")
            run_dir = Path(result["run_dir"])
            after_snapshot = json.loads((run_dir / "snapshots" / "after.snapshot.json").read_text(encoding="utf-8"))
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))

            self.assertEqual(after_snapshot["memory_count"], 1)
            self.assertEqual(
                {
                    tuple(question["expected_supporting_memory_ids"])
                    for question in result_payload["questions"]
                },
                {(after_snapshot["memories"][0]["id"],)},
            )

    def test_compact_longmemeval_matrix_isolates_ephemeral_stores_by_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "longmemeval-compact-sessions.jsonl"
            records = [
                {
                    "question_id": "session-alpha-1",
                    "session_id": "session-alpha",
                    "split": "small",
                    "category": "single_session_user_recall",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who owns the dashboard?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
                {
                    "question_id": "session-beta-1",
                    "session_id": "session-beta",
                    "split": "small",
                    "category": "single_session_user_recall",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who owns the dashboard in beta?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
                {
                    "question_id": "session-alpha-2",
                    "session_id": "session-alpha",
                    "split": "small",
                    "category": "single_session_user_recall",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who is responsible for the dashboard?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
            ]
            dataset.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")

            run_benchmark_matrix(
                Path(tmp) / "bench",
                "longmemeval",
                dataset=dataset,
                split="small",
                seed=0,
                run_id="longmemeval-compact-sessions",
                mode="fts",
                compact_artifacts=True,
            )
            matrix_dir = Path(tmp) / "bench" / "longmemeval-compact-sessions"
            run_dir = matrix_dir / "fts"
            manifest = json.loads((run_dir / "benchmark-run.json").read_text(encoding="utf-8"))
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            supporting_ids = {
                question["question_id"]: question["expected_supporting_memory_ids"]
                for question in result_payload["questions"]
            }

            self.assertEqual(manifest["store_lifecycle"], "per-session-ephemeral")
            self.assertTrue(manifest["receipt_bundles_omitted"])
            self.assertTrue(manifest["run_database_omitted"])
            self.assertEqual(result_payload["store_lifecycle"], "per-session-ephemeral")
            self.assertTrue(result_payload["final_snapshot_omitted"])
            self.assertTrue(result_payload["run_database_omitted"])
            self.assertIsNone(result_payload["paths"]["database"])
            self.assertEqual(
                [question["question_id"] for question in result_payload["questions"]],
                [record["question_id"] for record in records],
            )
            self.assertEqual(supporting_ids["session-alpha-1"], supporting_ids["session-alpha-2"])
            self.assertNotEqual(supporting_ids["session-alpha-1"], supporting_ids["session-beta-1"])
            self.assertEqual(list(run_dir.rglob("*.sqlite")), [])
            self.assertEqual(list((run_dir / "receipts").glob("*.bundle.json")), [])
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])
            self.assertTrue(verify_benchmark_artifact(matrix_dir / "benchmark-matrix.json")["ok"])

    def test_cli_compact_longmemeval_run_uses_runnable_manifest_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_longmemeval_jsonl(Path(tmp))
            out = Path(tmp) / "bench"

            result = self._main_json(
                [
                    "bench",
                    "run",
                    "longmemeval",
                    "--dataset",
                    str(dataset),
                    "--split",
                    "small",
                    "--out",
                    str(out),
                    "--run-id",
                    "compact-cli",
                    "--compact-artifacts",
                ]
            )
            manifest = json.loads((out / "compact-cli" / "benchmark-run.json").read_text(encoding="utf-8"))

            self.assertTrue(result["ok"])
            self.assertEqual(result["store_lifecycle"], "per-session-ephemeral")
            self.assertIn("--compact-artifacts", manifest["command"])
            self.assertEqual(list((out / "compact-cli").rglob("*.sqlite")), [])

    def test_longmemeval_json_array_split_filtering_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset.json"
            dataset.write_text(json.dumps(self._longmemeval_records(), indent=2), encoding="utf-8")

            result = run_longmemeval_benchmark(Path(tmp) / "bench", dataset, "holdout", seed=0, run_id="holdout-run")
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))

            self.assertEqual(result_payload["question_count"], 1)
            self.assertEqual(result_payload["questions"][0]["question_id"], "lme-3")

    def test_longmemeval_category_summaries_are_provisional(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_longmemeval_jsonl(Path(tmp))
            result = run_longmemeval_benchmark(Path(tmp) / "bench", dataset, "small", seed=0, run_id="category-run")

            self.assertEqual(result["summary"]["scoring"], "provisional-local")
            self.assertEqual(result["summary"]["category_labels"], "provisional-local")
            for category_summary in result["summary"]["category_summaries"].values():
                self.assertEqual(category_summary["label_status"], "provisional-local")
                self.assertEqual(category_summary["scoring"], "provisional-local")
                self.assertIn("p95_retrieval_latency_ms", category_summary)
                self.assertIn("total_tokens", category_summary)
                self.assertIn("retrieved_memory_count", category_summary)

    def test_longmemeval_verify_fails_when_question_file_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_longmemeval_jsonl(Path(tmp))
            result = run_longmemeval_benchmark(Path(tmp) / "bench", dataset, "small", seed=0, run_id="tamper-lme")
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            question_path = run_dir / result_payload["questions"][0]["question_path"]
            question = json.loads(question_path.read_text(encoding="utf-8"))
            question["final_answer"] = "tampered"
            question_path.write_text(json.dumps(question, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            verify = verify_benchmark_result(run_dir / "benchmark-result.json")

            self.assertFalse(verify["ok"])
            self.assertIn("artifact_hashes", self._failed_check_names(verify))
            self.assertTrue(any(name.startswith("question:") for name in self._failed_check_names(verify)))

    def test_locomo_missing_and_nonlocal_dataset_path_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench"

            missing_dataset = self._main_json(
                ["bench", "run", "locomo", "--out", str(out)],
                expected_code=1,
            )
            self.assertIn("requires --dataset", missing_dataset["error"])

            url_dataset = self._main_json(
                [
                    "bench",
                    "run",
                    "locomo",
                    "--dataset",
                    "https://example.test/locomo.jsonl",
                    "--out",
                    str(out),
                ],
                expected_code=1,
            )
            self.assertIn("local file path", url_dataset["error"])

            missing_file = self._main_json(
                [
                    "bench",
                    "run",
                    "locomo",
                    "--dataset",
                    str(Path(tmp) / "missing.jsonl"),
                    "--out",
                    str(out),
                ],
                expected_code=1,
            )
            self.assertIn("not found", missing_file["error"])

    def test_locomo_jsonl_run_writes_proof_layout_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_locomo_jsonl(Path(tmp))
            result = run_locomo_benchmark(Path(tmp) / "bench", dataset, "dev", seed=0, run_id="locomo-run")
            run_dir = Path(result["run_dir"])

            self.assertTrue(result["ok"])
            self.assertTrue((run_dir / "benchmark-run.json").exists())
            self.assertTrue((run_dir / "benchmark-result.json").exists())
            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "snapshots" / "before.snapshot.json").exists())
            self.assertTrue((run_dir / "snapshots" / "after.snapshot.json").exists())
            self.assertEqual(len(list((run_dir / "questions").glob("*.json"))), 2)
            self.assertEqual(len(list((run_dir / "receipts").glob("*.bundle.json"))), 2)

            run_manifest = json.loads((run_dir / "benchmark-run.json").read_text(encoding="utf-8"))
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["benchmark"], "locomo")
            self.assertEqual(run_manifest["split"], "dev")
            self.assertNotEqual(run_manifest["dataset_hash"], run_manifest["filtered_dataset_hash"])
            self.assertEqual(result_payload["question_count"], 2)
            self.assertEqual({question["question_id"] for question in result_payload["questions"]}, {"locomo-1", "locomo-2"})

            verify = verify_benchmark_result(run_dir / "benchmark-result.json")

            self.assertTrue(verify["ok"])
            self.assertTrue(all(check["ok"] for check in verify["checks"]))
            self.assertEqual(result["summary"]["accuracy"], 1.0)
            self.assertEqual(result["summary"]["scoring"], "provisional-local")

    def test_locomo_shared_sample_reuses_history_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "locomo-shared-sample.jsonl"
            records = [
                {
                    "question_id": "locomo-shared-1",
                    "sample_id": "dialog-alpha",
                    "split": "dev",
                    "category": "single_hop",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who owns the dashboard?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
                {
                    "question_id": "locomo-shared-2",
                    "sample_id": "dialog-alpha",
                    "split": "dev",
                    "category": "single_hop",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who is responsible for the dashboard?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
            ]
            dataset.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")

            result = run_locomo_benchmark(Path(tmp) / "bench", dataset, "dev", seed=0, run_id="locomo-shared")
            run_dir = Path(result["run_dir"])
            after_snapshot = json.loads((run_dir / "snapshots" / "after.snapshot.json").read_text(encoding="utf-8"))
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))

            self.assertEqual(after_snapshot["memory_count"], 1)
            self.assertEqual(
                {
                    tuple(question["expected_supporting_memory_ids"])
                    for question in result_payload["questions"]
                },
                {(after_snapshot["memories"][0]["id"],)},
            )

    def test_compact_locomo_isolates_ephemeral_stores_by_conversation(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "locomo-compact-conversations.jsonl"
            records = [
                {
                    "question_id": "dialog-alpha-1",
                    "sample_id": "dialog-alpha",
                    "split": "dev",
                    "category": "single_hop",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who owns the dashboard?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
                {
                    "question_id": "dialog-beta-1",
                    "sample_id": "dialog-beta",
                    "split": "dev",
                    "category": "single_hop",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who owns the dashboard in beta?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
                {
                    "question_id": "dialog-alpha-2",
                    "sample_id": "dialog-alpha",
                    "split": "dev",
                    "category": "single_hop",
                    "history": ["The dashboard owner is Mina."],
                    "question": "Who is responsible for the dashboard?",
                    "answer": "Mina.",
                    "supporting_facts": ["The dashboard owner is Mina."],
                    "should_abstain": False,
                },
            ]
            dataset.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")

            result = run_locomo_benchmark(
                Path(tmp) / "bench",
                dataset,
                "dev",
                seed=0,
                run_id="locomo-compact-conversations",
                compact_artifacts=True,
            )
            run_dir = Path(result["run_dir"])
            manifest = json.loads((run_dir / "benchmark-run.json").read_text(encoding="utf-8"))
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
            supporting_ids = {
                question["question_id"]: question["expected_supporting_memory_ids"]
                for question in result_payload["questions"]
            }

            self.assertEqual(manifest["store_lifecycle"], "per-conversation-ephemeral")
            self.assertTrue(manifest["run_database_omitted"])
            self.assertEqual(result_payload["store_lifecycle"], "per-conversation-ephemeral")
            self.assertTrue(result_payload["run_database_omitted"])
            self.assertIsNone(result_payload["paths"]["database"])
            self.assertEqual([question["question_id"] for question in result_payload["questions"]], [record["question_id"] for record in records])
            self.assertEqual(supporting_ids["dialog-alpha-1"], supporting_ids["dialog-alpha-2"])
            self.assertNotEqual(supporting_ids["dialog-alpha-1"], supporting_ids["dialog-beta-1"])
            self.assertEqual(list(run_dir.rglob("*.sqlite")), [])
            self.assertTrue(verify_benchmark_result(run_dir / "benchmark-result.json")["ok"])

    def test_locomo_json_wrapper_split_filtering_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset.json"
            dataset.write_text(json.dumps({"records": self._locomo_records()}, indent=2), encoding="utf-8")

            result = run_locomo_benchmark(Path(tmp) / "bench", dataset, "holdout", seed=0, run_id="locomo-holdout")
            run_dir = Path(result["run_dir"])
            result_payload = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))

            self.assertEqual(result_payload["question_count"], 1)
            self.assertEqual(result_payload["questions"][0]["question_id"], "locomo-3")
            self.assertEqual(result_payload["questions"][0]["category_label_status"], "provisional-local")

    def test_cli_runs_and_verifies_locomo_benchmark(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = self._write_locomo_jsonl(Path(tmp))
            out = Path(tmp) / "bench"

            run = self._main_json(
                [
                    "bench",
                    "run",
                    "locomo",
                    "--dataset",
                    str(dataset),
                    "--split",
                    "dev",
                    "--out",
                    str(out),
                    "--seed",
                    "0",
                    "--run-id",
                    "cli-locomo",
                ]
            )
            self.assertTrue(run["ok"])

            verify = self._main_json(["bench", "verify", str(out / "cli-locomo" / "benchmark-result.json")])
            self.assertTrue(verify["ok"])

    def test_verify_fails_when_question_file_is_tampered(self):
        run_dir = self._tampered_run_dir()
        result = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
        question_path = run_dir / result["questions"][0]["question_path"]
        question = json.loads(question_path.read_text(encoding="utf-8"))
        question["final_answer"] = "tampered"
        question_path.write_text(json.dumps(question, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        verify = verify_benchmark_result(run_dir / "benchmark-result.json")

        self.assertFalse(verify["ok"])
        self.assertIn("artifact_hashes", self._failed_check_names(verify))
        self.assertTrue(any(name.startswith("question:") for name in self._failed_check_names(verify)))

    def test_verify_fails_when_bundle_is_tampered(self):
        run_dir = self._tampered_run_dir()
        result = json.loads((run_dir / "benchmark-result.json").read_text(encoding="utf-8"))
        bundle_path = run_dir / result["questions"][0]["receipt_bundle_path"]
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle["receipt"]["task"] = "tampered"
        bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        verify = verify_benchmark_result(run_dir / "benchmark-result.json")

        self.assertFalse(verify["ok"])
        self.assertIn("artifact_hashes", self._failed_check_names(verify))
        self.assertTrue(any(name.startswith("bundle:") for name in self._failed_check_names(verify)))

    def test_verify_fails_when_snapshot_is_tampered(self):
        run_dir = self._tampered_run_dir()
        snapshot_path = run_dir / "snapshots" / "after.snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["memory_count"] += 1
        snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        verify = verify_benchmark_result(run_dir / "benchmark-result.json")

        self.assertFalse(verify["ok"])
        self.assertIn("artifact_hashes", self._failed_check_names(verify))
        self.assertIn("snapshot:after", self._failed_check_names(verify))

    def test_verify_fails_when_report_is_tampered(self):
        run_dir = self._tampered_run_dir()
        report_path = run_dir / "report.md"
        report_path.write_text(report_path.read_text(encoding="utf-8") + "\nTampered.\n", encoding="utf-8")

        verify = verify_benchmark_result(run_dir / "benchmark-result.json")

        self.assertFalse(verify["ok"])
        self.assertIn("artifact_hashes", self._failed_check_names(verify))
        self.assertIn("aggregate_merkle_root", self._failed_check_names(verify))

    def test_verify_fails_when_aggregate_root_is_tampered(self):
        run_dir = self._tampered_run_dir()
        result_path = run_dir / "benchmark-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["proof"]["aggregate_merkle_root"] = "0" * 64
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        verify = verify_benchmark_result(result_path)

        self.assertFalse(verify["ok"])
        self.assertIn("result_hash", self._failed_check_names(verify))
        self.assertIn("aggregate_merkle_root", self._failed_check_names(verify))

    def test_verify_fails_when_question_path_is_missing(self):
        run_dir = self._tampered_run_dir()
        result_path = run_dir / "benchmark-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        del result["questions"][0]["question_path"]
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        verify = verify_benchmark_result(result_path)

        self.assertFalse(verify["ok"])
        self.assertIn("artifact_hashes", self._failed_check_names(verify))
        self.assertIn("question:synthetic-policy-recall", self._failed_check_names(verify))

    def _tampered_run_dir(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        result = run_synthetic_benchmark(Path(tmp.name), seed=0, run_id="tamper-run")
        return Path(result["run_dir"])

    def _main_json(self, argv, expected_code=0):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv)
        self.assertEqual(code, expected_code)
        return json.loads(output.getvalue())

    def _main_text(self, argv, expected_code=0):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv)
        self.assertEqual(code, expected_code)
        return output.getvalue()

    def _failed_check_names(self, verify):
        return {check["name"] for check in verify["checks"] if not check["ok"]}

    def _resolve_matrix_artifact_path(self, matrix, stored_path):
        path = Path(str(stored_path))
        if path.is_absolute():
            return path
        return Path(matrix["matrix_path"]).parent / path

    def _assert_matrix_trace_receipt(self, matrix, *, dataset: Path, expected_dataset_name: str):
        matrix_dir = Path(matrix["matrix_dir"])
        receipt = json.loads((matrix_dir / "receipt.json").read_text(encoding="utf-8"))
        summary = json.loads((matrix_dir / "summary.json").read_text(encoding="utf-8"))
        matrix_json = matrix_dir / "benchmark-matrix.json"
        comparison_json = matrix_dir / "benchmark-comparison.json"
        report_path = matrix_dir / "matrix-report.md"
        trace_path = matrix_dir / "trace.jsonl"
        expected_mode_commands = []
        expected_mode_metrics = []

        for mode_run in matrix["mode_runs"]:
            manifest = json.loads(
                (self._resolve_matrix_artifact_path(matrix, mode_run["result_path"]).parent / "benchmark-run.json").read_text(
                    encoding="utf-8"
                )
            )
            expected_mode_commands.append(
                {
                    "retrieval_mode": mode_run["retrieval_mode"],
                    "run_id": mode_run["run_id"],
                    "command": manifest["command"],
                    "result_hash": mode_run["result_hash"],
                    "aggregate_merkle_root": mode_run["aggregate_merkle_root"],
                }
            )
            mode_summary = mode_run["summary"]
            expected_mode_metrics.append(
                {
                    "retrieval_mode": mode_run["retrieval_mode"],
                    "accuracy": mode_summary.get("accuracy"),
                    "f1": mode_summary.get("f1"),
                    "recall_at_k": mode_summary.get("recall_at_k"),
                    "retrieved_memory_count": mode_summary.get("retrieved_memory_count"),
                    "injected_memory_count": mode_summary.get("injected_memory_count"),
                    "withheld_memory_count": mode_summary.get("withheld_memory_count"),
                    "total_tokens": mode_summary.get("total_tokens"),
                    "token_efficiency": mode_summary.get("token_efficiency"),
                    "p95_retrieval_latency_ms": mode_summary.get("p95_retrieval_latency_ms"),
                }
            )

        self.assertFalse(receipt["public_benchmark_claim"])
        self.assertEqual(receipt["run_id"], matrix["run_id"])
        self.assertEqual(receipt["benchmark"], matrix["benchmark"])
        self.assertEqual(receipt["dataset"], expected_dataset_name)
        self.assertEqual(receipt["split"], matrix["split"])
        self.assertEqual(receipt["dataset_sha256"], sha256_text(dataset.read_text(encoding="utf-8")))
        self.assertEqual(receipt["scores"], summary)
        self.assertIsNone(receipt["token_efficiency"])
        self.assertEqual(receipt["matrix_hash"], matrix["matrix_hash"])
        self.assertEqual(receipt["comparison_hash"], matrix["comparison_hash"])
        self.assertEqual(receipt["verification_status"], summary["verification_status"])
        self.assertEqual(receipt["comparison_verification_status"], summary["comparison_verification_status"])
        self.assertEqual(receipt["question_summary"], summary["question_summary"])
        self.assertEqual(receipt["mode_proofs"], summary["mode_proofs"])
        self.assertEqual(receipt["mode_metrics"], expected_mode_metrics)
        self.assertEqual(receipt["memory_count_deltas"], summary["memory_count_deltas"])
        self.assertEqual(receipt["efficiency_deltas"], summary["efficiency_deltas"])
        self.assertEqual(receipt["artifact_hashes"]["matrix"], sha256_text(matrix_json.read_text(encoding="utf-8")))
        self.assertEqual(receipt["artifact_hashes"]["comparison"], sha256_text(comparison_json.read_text(encoding="utf-8")))
        self.assertEqual(receipt["artifact_hashes"]["report"], sha256_text(report_path.read_text(encoding="utf-8")))
        self.assertEqual(
            receipt["artifact_hashes"]["score_summary"],
            sha256_text((matrix_dir / "score-summary.json").read_text(encoding="utf-8")),
        )
        self.assertEqual(receipt["artifact_hashes"]["summary"], sha256_text((matrix_dir / "summary.json").read_text(encoding="utf-8")))
        self.assertEqual(receipt["artifact_hashes"]["trace"], sha256_text(trace_path.read_text(encoding="utf-8")))
        self.assertEqual(receipt["proof_roots"]["comparison_file_hash"], matrix["proof"]["comparison_file_hash"])
        self.assertEqual(receipt["proof_roots"]["input_result_hashes"], matrix["proof"]["input_result_hashes"])
        self.assertEqual(receipt["proof_roots"]["input_aggregate_roots"], matrix["proof"]["input_aggregate_roots"])
        self.assertEqual(receipt["mode_commands"], expected_mode_commands)
        self.assertEqual(receipt["score_summary_path"], "score-summary.json")
        self.assertEqual(receipt["trace_sha256"], sha256_text(trace_path.read_text(encoding="utf-8")))

    def _assert_mode_proofs_match_result_payloads(self, matrix):
        mode_proofs = []
        for mode_run in matrix["mode_runs"]:
            result_payload = json.loads(
                self._resolve_matrix_artifact_path(matrix, mode_run["result_path"]).read_text(encoding="utf-8")
            )
            mode_proof = {
                "retrieval_mode": result_payload["retrieval_mode"],
                "result_hash": result_payload["result_hash"],
                "aggregate_merkle_root": result_payload["proof"]["aggregate_merkle_root"],
            }
            self.assertEqual(mode_run["retrieval_mode"], mode_proof["retrieval_mode"])
            self.assertEqual(mode_run["result_hash"], mode_proof["result_hash"])
            self.assertEqual(mode_run["aggregate_merkle_root"], mode_proof["aggregate_merkle_root"])
            mode_proofs.append(mode_proof)
        return mode_proofs

    def _assert_rendered_mode_proof_hops(self, mode_proofs, html_text):
        self.assertIn("Per-Mode Proof Hops", html_text)
        self.assertIn("Result hash", html_text)
        self.assertIn("Aggregate Merkle root", html_text)
        for mode_proof in mode_proofs:
            self.assertIn(mode_proof["retrieval_mode"], html_text)
            self.assertIn(mode_proof["result_hash"], html_text)
            self.assertIn(mode_proof["aggregate_merkle_root"], html_text)

    def _assert_rendered_comparison_proof_hops(self, proof_hops, rendered_text):
        self.assertIn("Result hash", rendered_text)
        self.assertIn("Aggregate Merkle root", rendered_text)
        for proof_hop in proof_hops:
            self.assertIn(proof_hop["retrieval_mode"], rendered_text)
            self.assertIn(proof_hop["result_hash"], rendered_text)
            self.assertIn(proof_hop["aggregate_merkle_root"], rendered_text)

    def _comparison_run_proof_hops(self, comparison_payload):
        proof_hops = []
        for run in comparison_payload["runs"]:
            proof_hops.append(
                {
                    "retrieval_mode": run["retrieval_mode"],
                    "result_hash": run["result_hash"],
                    "aggregate_merkle_root": run["proof"]["aggregate_merkle_root"],
                }
            )
        return proof_hops

    def _assert_local_dataset_matrix(self, matrix, benchmark, dataset, split, question_count):
        matrix_dir = Path(matrix["matrix_dir"])
        stored_comparison = json.loads(
            self._resolve_matrix_artifact_path(matrix, matrix["comparison_path"]).read_text(encoding="utf-8")
        )

        self.assertTrue(matrix["ok"])
        self.assertEqual(matrix["benchmark"], benchmark)
        self.assertEqual(matrix["dataset"], str(dataset))
        self.assertEqual(matrix["split"], split)
        self.assertEqual(matrix["dataset_version"], "local-dataset")
        self.assertTrue(matrix["dataset_hash"])
        self.assertTrue(matrix["filtered_dataset_hash"])
        self.assertEqual(matrix["retrieval_modes"], list(BENCHMARK_RETRIEVAL_MODES))
        self.assertEqual(
            [run["retrieval_mode"] for run in matrix["mode_runs"]],
            list(BENCHMARK_RETRIEVAL_MODES),
        )
        self.assertTrue((matrix_dir / "benchmark-matrix.json").exists())
        self.assertTrue((matrix_dir / "benchmark-comparison.json").exists())
        self.assertTrue((matrix_dir / "matrix-report.md").exists())

        result_paths = []
        for retrieval_mode in BENCHMARK_RETRIEVAL_MODES:
            mode_dir = matrix_dir / retrieval_mode
            result_path = mode_dir / "benchmark-result.json"
            result_paths.append(result_path)

            self.assertTrue((mode_dir / "benchmark-run.json").exists())
            self.assertTrue(result_path.exists())
            self.assertTrue((mode_dir / "report.md").exists())
            self.assertEqual(len(list((mode_dir / "questions").glob("*.json"))), question_count)
            self.assertEqual(len(list((mode_dir / "receipts").glob("*.bundle.json"))), question_count)

            run_manifest = json.loads((mode_dir / "benchmark-run.json").read_text(encoding="utf-8"))
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))
            verify = verify_benchmark_result(result_path)

            self.assertEqual(run_manifest["benchmark"], benchmark)
            self.assertEqual(run_manifest["dataset"], str(dataset))
            self.assertEqual(run_manifest["split"], split)
            self.assertEqual(run_manifest["retrieval_mode"], retrieval_mode)
            self.assertFalse(run_manifest["scoring"]["hosted_judge"])
            self.assertEqual(result_payload["benchmark"], benchmark)
            self.assertEqual(result_payload["dataset"], str(dataset))
            self.assertEqual(result_payload["split"], split)
            self.assertEqual(result_payload["retrieval_mode"], retrieval_mode)
            self.assertEqual(result_payload["question_count"], question_count)
            self.assertEqual(result_payload["summary"]["scoring"], "provisional-local")
            self.assertTrue(verify["ok"])

        comparison = compare_benchmark_results(result_paths)

        self.assertEqual(matrix["comparison_hash"], stored_comparison["comparison_hash"])
        self.assertEqual(matrix["proof"]["comparison_hash"], stored_comparison["comparison_hash"])
        self.assertEqual(matrix["comparison"]["comparison_hash"], stored_comparison["comparison_hash"])
        self.assertEqual(matrix["dataset_version"], comparison["target"]["dataset_version"])
        self.assertEqual(matrix["dataset_hash"], comparison["target"]["dataset_hash"])
        self.assertEqual(matrix["filtered_dataset_hash"], comparison["target"]["filtered_dataset_hash"])
        self.assertEqual(matrix["comparison"]["compatibility"]["comparison_axis"], "retrieval_mode")
        self.assertEqual(matrix["comparison"]["proof"]["verification_status"], "ok")
        self.assertEqual(matrix["proof"]["verification_status"], "ok")
        self.assertEqual(
            [run["retrieval_mode"] for run in matrix["comparison"]["runs"]],
            list(BENCHMARK_RETRIEVAL_MODES),
        )

    def _provider_config(self, *, openai_enabled=False):
        return {
            "schema": "zerker.retrieval_providers.v1",
            "embedding": {
                "default": "local:pseudo",
                "providers": {
                    "local:pseudo": {
                        "enabled": True,
                        "network": False,
                        "model_id": "zmem-pseudo-embedding-v1",
                    },
                    "openai:text-embedding-3-small": {
                        "enabled": bool(openai_enabled),
                        "network": True,
                        "model_id": "text-embedding-3-small",
                        "dimensions": 2 if openai_enabled else 1536,
                        "normalized": True,
                        "api_key": "sk-test-secret",
                        "api_key_env": "OPENAI_API_KEY",
                    },
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
                },
            },
        }

    def _write_longmemeval_jsonl(self, directory: Path) -> Path:
        dataset = directory / "dataset.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._longmemeval_records()) + "\n",
            encoding="utf-8",
        )
        return dataset

    def _write_richer_longmemeval_jsonl(self, directory: Path) -> Path:
        dataset = directory / "dataset-rich.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._richer_longmemeval_records()) + "\n",
            encoding="utf-8",
        )
        return dataset

    def _write_longmemeval_stable_miss_budget_jsonl(self, directory: Path) -> Path:
        dataset = directory / "dataset-stable-miss-budget.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._longmemeval_stable_miss_budget_records())
            + "\n",
            encoding="utf-8",
        )
        return dataset

    def _write_longmemeval_temporal_stable_miss_jsonl(self, directory: Path) -> Path:
        dataset = directory / "longmemeval-temporal-stable-miss.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._longmemeval_temporal_stable_miss_records())
            + "\n",
            encoding="utf-8",
        )
        return dataset

    def _write_locomo_jsonl(self, directory: Path) -> Path:
        dataset = directory / "locomo.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._locomo_records()) + "\n",
            encoding="utf-8",
        )
        return dataset

    def _write_locomo_stable_miss_budget_jsonl(self, directory: Path) -> Path:
        dataset = directory / "locomo-stable-miss-budget.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._locomo_stable_miss_budget_records())
            + "\n",
            encoding="utf-8",
        )
        return dataset

    def _write_richer_locomo_jsonl(self, directory: Path) -> Path:
        dataset = directory / "locomo-rich.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._richer_locomo_records()) + "\n",
            encoding="utf-8",
        )
        return dataset

    def _longmemeval_records(self):
        return [
            {
                "question_id": "lme-1",
                "split": "small",
                "category": "single_session_user_recall",
                "history": ["Ada's launch codename is Blue Finch."],
                "question": "What is Ada's launch codename?",
                "answer": "Blue Finch.",
                "supporting_facts": ["Ada's launch codename is Blue Finch."],
                "should_abstain": False,
            },
            {
                "question_id": "lme-2",
                "split": "small",
                "category": "abstention",
                "history": [],
                "question": "What is Noor's vault code?",
                "answer": "",
                "supporting_facts": [],
                "should_abstain": True,
            },
            {
                "question_id": "lme-3",
                "split": "holdout",
                "category": "temporal_reasoning",
                "history": [{"content": "On Monday, the deployment window moved to Friday."}],
                "question": "When did the deployment window move?",
                "answer": "Friday.",
                "supporting_facts": [{"content": "On Monday, the deployment window moved to Friday."}],
                "should_abstain": False,
            },
        ]

    def _richer_longmemeval_records(self):
        return [
            {
                "question_id": "lme-temporal-change-when",
                "split": "analysis",
                "category": "temporal_reasoning",
                "history": [
                    {"content": "On Monday, the deployment approver was Noor."},
                    {"content": "On Tuesday, the deployment approver changed to Imani."},
                ],
                "question": "When did the deployment approver change then?",
                "answer": "Tuesday.",
                "supporting_facts": [{"content": "On Tuesday, the deployment approver changed to Imani."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-knowledge-update-current-target",
                "split": "analysis",
                "category": "knowledge_update",
                "history": [
                    {"content": "Deploy target is Staging."},
                    {"content": "Deploy target changed to Production."},
                ],
                "question": "deploy target",
                "answer": "Production.",
                "supporting_facts": [{"content": "Deploy target changed to Production."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-knowledge-update-stale-decoy",
                "split": "analysis",
                "category": "knowledge_update",
                "history": [
                    {"content": "Deploy target is Staging."},
                    {"content": "Escalation contact is Rowan."},
                    {"content": "Deploy target changed to Production."},
                    {"content": "The previous deploy target was Staging."},
                ],
                "question": "What is the deploy target now?",
                "answer": "Production.",
                "supporting_facts": [{"content": "Deploy target changed to Production."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-knowledge-update-ambiguous-restatement",
                "split": "analysis",
                "category": "knowledge_update",
                "history": [
                    {"content": "Status page owner is Avery."},
                    {"content": "Status page owner is Blair."},
                ],
                "question": "Who's on point for the status page now?",
                "answer": "Blair.",
                "supporting_facts": [{"content": "Status page owner is Blair."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-knowledge-update-release-note-decoy",
                "split": "analysis",
                "category": "knowledge_update",
                "history": [
                    {
                        "content": (
                            "What deploy target follows the Blue Finch release note now is not stated in this "
                            "routing note."
                        )
                    },
                    {"content": "Blue Finch deploy target is Staging."},
                    {"content": "Blue Finch deploy target changed to Production."},
                ],
                "question": "What deploy target follows the Blue Finch release note now?",
                "answer": "Production.",
                "supporting_facts": [{"content": "Blue Finch deploy target changed to Production."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-knowledge-update-history-wording-gap",
                "split": "analysis",
                "category": "knowledge_update",
                "history": [
                    {"content": "Blue Finch shipped on Staging before the cutover."},
                    {"content": "Blue Finch deploy target changed to Production."},
                    {"content": "Routing note: current environment details live in the release checklist."},
                ],
                "question": "What did Blue Finch deploy to before it moved to Production?",
                "answer": "Staging.",
                "supporting_facts": [{"content": "Blue Finch shipped on Staging before the cutover."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-routing-owner-wording-gap",
                "split": "analysis",
                "category": "knowledge_update",
                "history": [
                    {"content": "Routing checklist lives in /srv/runbook."},
                    {"content": "Escalation contact changed to Rowan."},
                    {"content": "Routing summary needs a weekly cleanup."},
                ],
                "question": "Who owns routing now?",
                "answer": "Rowan.",
                "supporting_facts": [{"content": "Escalation contact changed to Rowan."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-current-conflict-abstain",
                "split": "analysis",
                "category": "current_conflict_abstention",
                "history": [
                    {"content": "Status page owner is Avery."},
                    {"content": "Status page owner is Blair."},
                ],
                "question": "Who is the status page owner?",
                "answer": "",
                "supporting_facts": [],
                "should_abstain": True,
            },
        ]

    def _longmemeval_stable_miss_budget_records(self):
        return [
            {
                "question_id": "lme-temporal-change-when",
                "split": "analysis",
                "category": "temporal_reasoning",
                "history": [
                    {"content": "On Monday, the deployment approver was Noor."},
                    {"content": "On Tuesday, the deployment approver changed to Imani."},
                ],
                "question": "When did the deployment approver change then?",
                "answer": "Tuesday.",
                "supporting_facts": [{"content": "On Tuesday, the deployment approver changed to Imani."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-routing-owner-history-gap",
                "split": "analysis",
                "category": "temporal_reasoning",
                "history": [
                    {"content": "Earlier escalation contact was Jules."},
                    {"content": "Escalation contact changed to Rowan."},
                    {"content": "Routing checklist lives in /srv/runbook."},
                ],
                "question": "Who handled routing before the change?",
                "answer": "Jules.",
                "supporting_facts": [{"content": "Earlier escalation contact was Jules."}],
                "should_abstain": False,
            },
        ]

    def _longmemeval_temporal_stable_miss_records(self):
        return [
            {
                "question_id": "lme-temporal-change-when",
                "split": "analysis",
                "category": "temporal_reasoning",
                "history": [
                    {"content": "On Monday, the deployment approver was Noor."},
                    {"content": "On Tuesday, the deployment approver changed to Imani."},
                ],
                "question": "When did the deployment approver change then?",
                "answer": "Tuesday.",
                "supporting_facts": [{"content": "On Tuesday, the deployment approver changed to Imani."}],
                "should_abstain": False,
            },
            {
                "question_id": "lme-temporal-history-shift-gap",
                "split": "analysis",
                "category": "temporal_reasoning",
                "history": [
                    {"content": "The infra channel handled the opening ping."},
                    {"content": "Avery covered the overnight rotation."},
                    {"content": "Blair took the next rotation."},
                    {"content": "Status page shift notes live in docs/status.md."},
                ],
                "question": "Who handled the status page before the shift?",
                "answer": "Avery.",
                "supporting_facts": [{"content": "Avery covered the overnight rotation."}],
                "should_abstain": False,
            },
        ]

    def _locomo_records(self):
        return [
            {
                "question_id": "locomo-1",
                "split": "dev",
                "category": "temporal_reasoning",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "Mira moved her design review to Thursday."},
                            {"speaker": "assistant", "utterance": "Noted."},
                        ]
                    }
                ],
                "question": "When is Mira's design review?",
                "answer": "Thursday.",
                "evidence": [{"speaker": "user", "utterance": "Mira moved her design review to Thursday."}],
                "should_abstain": False,
            },
            {
                "id": "locomo-2",
                "split": "dev",
                "type": "abstention",
                "conversation": [],
                "query": "What is Imani's private PIN?",
                "answer": "",
                "supporting_facts": [],
                "should_abstain": True,
            },
            {
                "qid": "locomo-3",
                "split": "holdout",
                "category": "multi_hop",
                "messages": [
                    {"content": "The Calder project uses the Aurora codename."},
                    {"content": "Aurora's kickoff owner is Jules."},
                ],
                "question": "Who owns the Calder kickoff?",
                "ground_truth": "Jules.",
                "supporting_evidence": [{"content": "Aurora's kickoff owner is Jules."}],
                "should_abstain": False,
            },
        ]

    def _richer_locomo_records(self):
        return [
            {
                "question_id": "locomo-temporal-rich",
                "split": "dev",
                "category": "temporal_reasoning",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "Mira moved her design review to Thursday."},
                            {"speaker": "assistant", "utterance": "Logged."},
                            {"speaker": "user", "utterance": "The review moved again to Friday afternoon."},
                        ]
                    }
                ],
                "question": "When is Mira's design review now?",
                "answer": "Friday afternoon.",
                "evidence": [{"speaker": "user", "utterance": "The review moved again to Friday afternoon."}],
                "should_abstain": False,
            },
            {
                "question_id": "locomo-multihop-rich",
                "split": "dev",
                "category": "multi_hop",
                "messages": [
                    {
                        "content": (
                            "What locker code follows the Kestrel Node handoff checklist is not stated in "
                            "this routing note."
                        )
                    },
                    {"content": "Kestrel Node locker code is 4182."},
                ],
                "question": "What locker code follows the Kestrel Node handoff checklist?",
                "answer": "4182.",
                "supporting_evidence": [
                    {"content": "Kestrel Node locker code is 4182."},
                ],
                "should_abstain": False,
            },
            {
                "question_id": "locomo-routing-owner-wording-gap",
                "split": "dev",
                "category": "knowledge_update",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "Routing checklist lives in /srv/runbook."},
                            {"speaker": "assistant", "utterance": "Logged."},
                            {"speaker": "user", "utterance": "Escalation contact changed to Rowan."},
                            {"speaker": "user", "utterance": "Routing summary needs a weekly cleanup."},
                        ]
                    }
                ],
                "question": "Who owns routing now?",
                "answer": "Rowan.",
                "supporting_facts": [
                    {"speaker": "user", "utterance": "Escalation contact changed to Rowan."},
                ],
                "should_abstain": False,
            },
            {
                "question_id": "locomo-routing-owner-history-gap",
                "split": "dev",
                "category": "knowledge_update",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "Routing checklist lives in /srv/runbook."},
                            {"speaker": "assistant", "utterance": "Logged."},
                            {"speaker": "user", "utterance": "Earlier escalation contact was Jules."},
                            {"speaker": "user", "utterance": "Escalation contact changed to Rowan."},
                            {"speaker": "user", "utterance": "Routing summary needs a weekly cleanup."},
                        ]
                    }
                ],
                "question": "Who owned routing before the update?",
                "answer": "Jules.",
                "supporting_facts": [
                    {"speaker": "user", "utterance": "Earlier escalation contact was Jules."},
                ],
                "should_abstain": False,
            },
            {
                "question_id": "locomo-abstention-rich",
                "split": "dev",
                "category": "abstention",
                "conversation": [],
                "query": "What is Imani's private PIN?",
                "answer": "",
                "supporting_facts": [],
                "should_abstain": True,
            },
        ]

    def _locomo_stable_miss_budget_records(self):
        return [
            {
                "question_id": "locomo-routing-now-budget-control",
                "split": "analysis",
                "category": "knowledge_update",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "Routing checklist lives in /srv/runbook."},
                            {"speaker": "assistant", "utterance": "Logged."},
                            {"speaker": "user", "utterance": "Earlier escalation contact was Jules."},
                            {"speaker": "user", "utterance": "Escalation contact changed to Rowan."},
                            {"speaker": "user", "utterance": "Routing summary needs a weekly cleanup."},
                        ]
                    }
                ],
                "question": "Who owns routing now?",
                "answer": "Rowan.",
                "supporting_facts": [
                    {"speaker": "user", "utterance": "Escalation contact changed to Rowan."},
                ],
                "should_abstain": False,
            },
            {
                "question_id": "locomo-routing-history-stable-miss",
                "split": "analysis",
                "category": "knowledge_update",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "Routing checklist lives in /srv/runbook."},
                            {"speaker": "assistant", "utterance": "Logged."},
                            {"speaker": "user", "utterance": "Earlier escalation contact was Jules."},
                            {"speaker": "user", "utterance": "Escalation contact changed to Rowan."},
                            {"speaker": "user", "utterance": "Routing summary needs a weekly cleanup."},
                        ]
                    }
                ],
                "question": "Who handled routing before the change?",
                "answer": "Jules.",
                "supporting_facts": [
                    {"speaker": "user", "utterance": "Earlier escalation contact was Jules."},
                ],
                "should_abstain": False,
            },
        ]

    def _write_locomo_temporal_stable_miss_jsonl(self, directory: Path) -> Path:
        dataset = directory / "locomo-temporal-stable-miss.jsonl"
        dataset.write_text(
            "\n".join(json.dumps(record, sort_keys=True) for record in self._locomo_temporal_stable_miss_records())
            + "\n",
            encoding="utf-8",
        )
        return dataset

    def _locomo_temporal_stable_miss_records(self):
        return [
            {
                "question_id": "locomo-temporal-change-when",
                "split": "analysis",
                "category": "temporal_reasoning",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "On Monday, the deployment approver was Noor."},
                            {"speaker": "assistant", "utterance": "Logged."},
                            {"speaker": "user", "utterance": "On Tuesday, the deployment approver changed to Imani."},
                        ]
                    }
                ],
                "question": "When did the deployment approver change then?",
                "answer": "Tuesday.",
                "supporting_facts": [
                    {"speaker": "user", "utterance": "On Tuesday, the deployment approver changed to Imani."},
                ],
                "should_abstain": False,
            },
            {
                "question_id": "locomo-temporal-now-budget-control",
                "split": "analysis",
                "category": "temporal_reasoning",
                "sessions": [
                    {
                        "messages": [
                            {"speaker": "user", "utterance": "Mira moved her design review to Thursday."},
                            {"speaker": "assistant", "utterance": "Logged."},
                            {"speaker": "user", "utterance": "The review moved again to Friday afternoon."},
                        ]
                    }
                ],
                "question": "When is Mira's design review now?",
                "answer": "Friday afternoon.",
                "evidence": [
                    {"speaker": "user", "utterance": "The review moved again to Friday afternoon."},
                ],
                "should_abstain": False,
            },
        ]


if __name__ == "__main__":
    unittest.main()
