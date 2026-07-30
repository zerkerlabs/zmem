import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zerker_memory.cli import build_parser, render_inject_summary, render_why_summary
from zerker_memory.dense import dense_hybrid_retrieval_config
from zerker_memory.retrieval_providers import EmbeddingProviderResult, local_dense_provider_config
from zerker_memory.store import MemoryStore, sha256_text


def _fake_embed_texts(provider_entry, texts, *, input_type="document", allow_model_download=False, **_kwargs):
    vectors = []
    for text in texts:
        if input_type == "query" or "oil change" in text.lower() or "quarantined semantic" in text.lower():
            vectors.append([1.0, 0.0])
        else:
            vectors.append([0.0, 1.0])
    vector_hashes = [
        "sha256:" + hashlib.sha256(repr(vector).encode("utf-8")).hexdigest()
        for vector in vectors
    ]
    return EmbeddingProviderResult(
        provider_id=provider_entry.provider_id,
        model_id=provider_entry.model_id or "BAAI/bge-small-en-v1.5",
        dims=2,
        normalized=True,
        vectors=vectors,
        latency_ms=0.1,
        network_call=allow_model_download,
        vector_hashes=vector_hashes,
        model_digest="sha256:test-model",
    )


class DenseRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = MemoryStore(self.root / "memory.sqlite")
        self.store.init()
        self.provider_config = local_dense_provider_config(cache_dir=self.root / "models")
        self.retrieval_config = dense_hybrid_retrieval_config(min_score=0.5)

    def tearDown(self):
        self.store.conn.close()
        self.temp_dir.cleanup()

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=_fake_embed_texts)
    def test_dense_source_recovers_candidate_absent_from_fts_and_records_rrf(self, _embed):
        relevant = self.store.remember(
            "The sedan requires an oil change every five thousand miles.",
            memory_type="semantic",
            scope="project:car",
            source_kind="human",
            memory_id="mem_dense_relevant",
        )
        lexical = self.store.remember(
            "Automobile service invoices are retained for seven years.",
            memory_type="semantic",
            scope="project:car",
            source_kind="human",
            memory_id="mem_lexical_decoy",
        )
        indexed = self.store.index_embeddings(provider_config=self.provider_config, scope="project:car")

        base = self.store.search_with_meta("automobile service", scope="project:car")
        result = self.store.search_with_meta(
            "automobile service",
            scope="project:car",
            retrieval_config=self.retrieval_config,
            retrieval_provider_config=self.provider_config,
        )
        metadata = result["retrieval"]["dense_hybrid"]
        candidates = {item["memory_id"]: item for item in result["retrieval"]["candidates"]}

        self.assertEqual(indexed["indexed_count"], 2)
        self.assertNotIn(relevant.id, [memory.id for memory in base["memories"]])
        self.assertIn(relevant.id, [memory.id for memory in result["memories"]])
        self.assertIn(lexical.id, [memory.id for memory in result["memories"]])
        self.assertIn(relevant.id, metadata["introduced_candidate_ids"])
        self.assertEqual(metadata["fusion"]["strategy"], "reciprocal_rank_fusion_v1")
        self.assertEqual(metadata["model_digest"], "sha256:test-model")
        self.assertTrue(metadata["lexical_recall_preserved"])
        self.assertEqual(candidates[relevant.id]["dense_candidate_source"], "dense")
        self.assertEqual(candidates[relevant.id]["dense_score"], 1.0)
        self.assertTrue(metadata["query_vector_hash"].startswith("sha256:"))
        self.assertFalse(metadata["network_calls_enabled"])

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=_fake_embed_texts)
    def test_dense_candidates_respect_scope_and_policy_withholds_quarantine(self, _embed):
        quarantined = self.store.remember(
            "Quarantined semantic evidence about an oil change.",
            memory_type="semantic",
            scope="project:car",
            source_kind="agent",
            memory_id="mem_quarantined_dense",
        )
        out_of_scope = self.store.remember(
            "The sedan requires an oil change every thousand miles.",
            memory_type="semantic",
            scope="project:other",
            source_kind="human",
            memory_id="mem_other_scope",
        )
        self.store.index_embeddings(provider_config=self.provider_config)

        public_search = self.store.search_with_meta(
            "maintenance cadence",
            scope="project:car",
            retrieval_config=self.retrieval_config,
            retrieval_provider_config=self.provider_config,
        )
        receipt = self.store.inject(
            "maintenance cadence",
            agent_id="agent:test",
            risk="medium",
            scope="project:car",
            retrieval_config=self.retrieval_config,
            retrieval_provider_config=self.provider_config,
        )

        self.assertNotIn(quarantined.id, [memory.id for memory in public_search["memories"]])
        self.assertNotIn(out_of_scope.id, [memory.id for memory in public_search["memories"]])
        self.assertIn(quarantined.id, receipt["retrieved_memory_ids"])
        self.assertNotIn(quarantined.id, receipt["injected_memory_ids"])
        self.assertIn(quarantined.id, [item["memory_id"] for item in receipt["withheld"]])
        self.assertNotIn(out_of_scope.id, receipt["retrieved_memory_ids"])

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=_fake_embed_texts)
    def test_stale_vectors_are_excluded_until_reindexed(self, _embed):
        memory = self.store.remember(
            "The sedan requires an oil change every five thousand miles.",
            memory_type="semantic",
            scope="project:car",
            source_kind="human",
            memory_id="mem_stale_dense",
        )
        self.store.index_embeddings(provider_config=self.provider_config)
        replacement = "This record has changed and needs a new vector."
        self.store.conn.execute(
            "UPDATE memories SET content = ?, content_hash = ? WHERE id = ?",
            (replacement, sha256_text(replacement), memory.id),
        )
        self.store.conn.commit()

        status = self.store.embedding_index_status(provider_config=self.provider_config)
        result = self.store.search_with_meta(
            "maintenance cadence",
            retrieval_config=self.retrieval_config,
            retrieval_provider_config=self.provider_config,
        )

        self.assertEqual(status["missing_or_stale_count"], 1)
        self.assertNotIn(memory.id, result["retrieval"]["dense_hybrid"]["dense_ranked_candidate_ids"])
        self.assertTrue(result["retrieval"]["dense_hybrid"]["fallback"])
        self.assertEqual(result["retrieval"]["dense_hybrid"]["disabled_reason"], "index-empty-or-stale")

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=ValueError("model unavailable"))
    def test_dense_failure_falls_back_to_lexical_with_visible_reason(self, _embed):
        memory = self.store.remember(
            "Automobile service records are current.",
            memory_type="semantic",
            scope="project:car",
            source_kind="human",
        )

        result = self.store.search_with_meta(
            "automobile service",
            scope="project:car",
            retrieval_config=self.retrieval_config,
            retrieval_provider_config=self.provider_config,
        )
        metadata = result["retrieval"]["dense_hybrid"]

        self.assertIn(memory.id, [item.id for item in result["memories"]])
        self.assertTrue(metadata["fallback"])
        self.assertEqual(metadata["disabled_reason"], "provider-error")
        self.assertEqual(metadata["error"], "model unavailable")

    @patch("zerker_memory.retrieval_providers.fastembed_model_cached", return_value=False)
    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=_fake_embed_texts)
    def test_download_model_prefetches_on_empty_store(self, embed, _cached):
        result = self.store.index_embeddings(
            provider_config=self.provider_config,
            allow_model_download=True,
        )

        self.assertEqual(result["indexed_count"], 0)
        self.assertTrue(result["model_download_observed"])
        self.assertEqual(result["model_digest"], "sha256:test-model")
        embed.assert_called_once()

    def test_query_model_digest_mismatch_excludes_indexed_vectors(self):
        memory = self.store.remember(
            "The sedan requires an oil change every five thousand miles.",
            memory_type="semantic",
            scope="project:car",
            source_kind="human",
        )

        def embed_with_digest(provider_entry, texts, *, input_type="document", **_kwargs):
            result = _fake_embed_texts(provider_entry, texts, input_type=input_type)
            return EmbeddingProviderResult(
                **{
                    **result.__dict__,
                    "model_digest": "sha256:query-model" if input_type == "query" else "sha256:index-model",
                }
            )

        with patch("zerker_memory.retrieval_providers.embed_texts", side_effect=embed_with_digest):
            self.store.index_embeddings(provider_config=self.provider_config, scope="project:car")
            result = self.store.search_with_meta(
                "maintenance cadence",
                scope="project:car",
                retrieval_config=self.retrieval_config,
                retrieval_provider_config=self.provider_config,
            )

        metadata = result["retrieval"]["dense_hybrid"]
        self.assertNotIn(memory.id, metadata["dense_ranked_candidate_ids"])
        self.assertEqual(metadata["indexed_candidate_count"], 0)
        self.assertEqual(metadata["model_digest"], "sha256:query-model")
        self.assertTrue(metadata["fallback"])
        self.assertEqual(metadata["disabled_reason"], "index-empty-or-stale")

    def test_dense_index_rejects_network_provider(self):
        provider_config = local_dense_provider_config(cache_dir=self.root / "models")
        provider_config["embedding"]["providers"]["local:fastembed"]["network"] = True

        with self.assertRaisesRegex(ValueError, "network provider not allowed"):
            self.store.index_embeddings(provider_config=provider_config)

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=_fake_embed_texts)
    def test_fusion_adds_dense_candidates_without_deleting_lexical_candidates(self, _embed):
        lexical_ids = {
            self.store.remember(
                f"Maintenance record {index} is retained for audit.",
                memory_type="semantic",
                scope="project:car",
                source_kind="human",
            ).id
            for index in range(20)
        }
        dense_ids = {
            self.store.remember(
                f"Oil change evidence {index} describes the service cadence.",
                memory_type="semantic",
                scope="project:car",
                source_kind="human",
            ).id
            for index in range(20)
        }
        self.store.index_embeddings(provider_config=self.provider_config, scope="project:car")

        baseline = self.store.search_with_meta("maintenance", scope="project:car")
        fused = self.store.search_with_meta(
            "maintenance",
            scope="project:car",
            retrieval_config=self.retrieval_config,
            retrieval_provider_config=self.provider_config,
        )

        baseline_ids = {memory.id for memory in baseline["memories"]}
        fused_ids = {memory.id for memory in fused["memories"]}
        metadata = fused["retrieval"]["dense_hybrid"]
        self.assertEqual(baseline_ids, lexical_ids)
        self.assertTrue(baseline_ids.issubset(fused_ids))
        self.assertTrue(dense_ids.issubset(fused_ids))
        self.assertEqual(metadata["fused_candidate_count"], 40)
        self.assertTrue(metadata["lexical_recall_preserved"])

    def test_dense_only_candidate_cannot_trigger_lexical_conflict_suppression(self):
        target = self.store.remember(
            "user (2023-05-29 Mon 03:32) My signed debut album is limited to 500 copies worldwide.",
            memory_type="semantic",
            scope="project:music",
            source_kind="human",
            memory_id="mem_lexical_target",
        )
        dense_only = self.store.remember(
            "user (2023-05-29 Mon 03:32) My vintage camera is displayed in the hallway.",
            memory_type="semantic",
            scope="project:music",
            source_kind="human",
            memory_id="mem_dense_only_conflict",
        )

        def embed_conflict_pair(provider_entry, texts, *, input_type="document", **_kwargs):
            vectors = [[1.0, 0.0] for _text in texts]
            return EmbeddingProviderResult(
                provider_id=provider_entry.provider_id,
                model_id=provider_entry.model_id or "BAAI/bge-small-en-v1.5",
                dims=2,
                normalized=True,
                vectors=vectors,
                latency_ms=0.1,
                network_call=False,
                vector_hashes=[
                    "sha256:" + hashlib.sha256(repr(vector).encode("utf-8")).hexdigest()
                    for vector in vectors
                ],
                model_digest="sha256:test-model",
            )

        with patch("zerker_memory.retrieval_providers.embed_texts", side_effect=embed_conflict_pair):
            self.store.index_embeddings(provider_config=self.provider_config, scope="project:music")
            receipt = self.store.inject(
                "debut album copies worldwide",
                agent_id="agent:test",
                risk="low",
                scope="project:music",
                retrieval_config=self.retrieval_config,
                retrieval_provider_config=self.provider_config,
            )

        candidates = {
            item["memory_id"]: item for item in receipt["retrieval"]["candidates"]
        }
        self.assertEqual(candidates[target.id]["dense_candidate_source"], "lexical+dense")
        self.assertEqual(candidates[dense_only.id]["dense_candidate_source"], "dense")
        self.assertIn(target.id, receipt["injected_memory_ids"])
        self.assertFalse(
            any(
                target.id in item.get("dropped_current_ids", [])
                for item in receipt["retrieval"]["temporal"]["conflict_sets"]
            )
        )
        self.assertEqual(
            receipt["retrieval"]["dense_hybrid"]["conflict_resolution_boundary"],
            "dense-only-candidates-cannot-trigger-lexical-conflicts-v1",
        )

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=_fake_embed_texts)
    def test_dense_mode_keeps_conflict_resolution_for_lexical_candidates(self, _embed):
        lower_authority = self.store.remember(
            "Deploy target is Render",
            memory_type="semantic",
            scope="project:deploy",
            source_kind="document",
            authority="low",
        )
        higher_authority = self.store.remember(
            "Deploy target is Railway",
            memory_type="semantic",
            scope="project:deploy",
            source_kind="human",
            authority="high",
        )
        self.store.index_embeddings(provider_config=self.provider_config, scope="project:deploy")

        receipt = self.store.inject(
            "deploy target",
            agent_id="agent:test",
            risk="low",
            scope="project:deploy",
            retrieval_config=self.retrieval_config,
            retrieval_provider_config=self.provider_config,
        )

        conflict = next(
            item
            for item in receipt["retrieval"]["temporal"]["conflict_sets"]
            if item["reason"] == "lexical-current-conflict"
        )
        self.assertEqual(conflict["chosen_current_id"], higher_authority.id)
        self.assertEqual(conflict["dropped_current_ids"], [lower_authority.id])
        self.assertEqual(receipt["injected_memory_ids"], [higher_authority.id])

    def test_cli_exposes_explicit_index_and_dense_hybrid_modes(self):
        parser = build_parser("zmem")

        index_args = parser.parse_args(["embeddings", "index", "--download-model", "--summary-only"])
        inject_args = parser.parse_args(
            ["inject", "remember the maintenance cadence", "--agent", "cursor", "--retrieval-mode", "dense-hybrid"]
        )

        self.assertEqual(index_args.command, "embeddings")
        self.assertTrue(index_args.download_model)
        self.assertEqual(inject_args.retrieval_mode, "dense-hybrid")

    def test_compact_summaries_surface_dense_mode_and_fallback(self):
        receipt = {
            "action_id": "act_dense",
            "agent_id": "cursor",
            "risk": "medium",
            "task": "continue the release",
            "retrieved_memory_ids": [],
            "injected_memory_ids": [],
            "withheld": [],
            "merkle_root": "root",
            "retrieval": {
                "dense_hybrid": {
                    "enabled": True,
                    "fallback": False,
                    "model_id": "BAAI/bge-small-en-v1.5",
                }
            },
        }
        self.assertIn("Recall: dense + FTS (BAAI/bge-small-en-v1.5)", render_inject_summary(receipt))

        receipt["retrieval"]["dense_hybrid"].update(
            {"fallback": True, "disabled_reason": "index-empty-or-stale"}
        )
        self.assertIn("Recall: FTS fallback (index-empty-or-stale)", render_why_summary(receipt))


if __name__ == "__main__":
    unittest.main()
