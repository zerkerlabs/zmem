import json
import tempfile
import unittest
from pathlib import Path

from zerker_memory.retrieval_providers import (
    REDACTED_CONFIG_SCHEMA,
    RETRIEVAL_PROVIDERS_SCHEMA,
    load_retrieval_provider_config,
    lookup_retrieval_provider,
    redacted_retrieval_provider_config,
    resolve_embedding_provider,
    resolve_reranker_provider,
    retrieval_provider_config_hash,
    retrieval_provider_config_template,
    retrieval_provider_readiness,
    retrieval_provider_registry,
)


class RetrievalProviderConfigTest(unittest.TestCase):
    def test_default_config_is_local_only_for_enabled_providers(self):
        config = retrieval_provider_config_template()

        self.assertEqual(config["schema"], RETRIEVAL_PROVIDERS_SCHEMA)
        self.assertEqual(config["embedding"]["default"], "local:pseudo")
        self.assertEqual(config["reranker"]["default"], "local:deterministic")
        self.assertTrue(config["embedding"]["providers"]["local:pseudo"]["enabled"])
        self.assertFalse(config["embedding"]["providers"]["local:pseudo"]["network"])
        self.assertTrue(config["reranker"]["providers"]["local:deterministic"]["enabled"])
        self.assertFalse(config["reranker"]["providers"]["local:deterministic"]["network"])

        enabled = [
            settings
            for section in (config["embedding"], config["reranker"])
            for settings in section["providers"].values()
            if settings["enabled"]
        ]
        self.assertTrue(enabled)
        self.assertTrue(all(settings["network"] is False for settings in enabled))

    def test_hosted_example_providers_are_disabled_by_default(self):
        config = retrieval_provider_config_template()

        openai = config["embedding"]["providers"]["openai:text-embedding-3-small"]
        cohere = config["reranker"]["providers"]["cohere:rerank-v3.5"]

        self.assertFalse(openai["enabled"])
        self.assertTrue(openai["network"])
        self.assertEqual(openai["api_key_env"], "OPENAI_API_KEY")
        self.assertFalse(cohere["enabled"])
        self.assertTrue(cohere["network"])
        self.assertEqual(cohere["api_key_env"], "COHERE_API_KEY")

    def test_load_missing_config_returns_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_retrieval_provider_config(Path(tmp) / "missing.json")

        self.assertEqual(config, retrieval_provider_config_template())

    def test_registry_lookup_exposes_future_adapter_metadata(self):
        registry = retrieval_provider_registry()
        entry = lookup_retrieval_provider("embedding", "local:pseudo")

        self.assertIn("embedding:local:pseudo", registry)
        self.assertEqual(entry.kind, "embedding")
        self.assertEqual(entry.provider_id, "local:pseudo")
        self.assertEqual(entry.model_id, "zmem-pseudo-embedding-v1")
        self.assertTrue(entry.enabled)
        self.assertFalse(entry.network)

    def test_redaction_removes_fake_secret_sentinels_but_keeps_env_names(self):
        config = retrieval_provider_config_template()
        openai = config["embedding"]["providers"]["openai:text-embedding-3-small"]
        openai["enabled"] = True
        openai["api_key"] = "sk-fake-secret-sentinel"
        openai["authorization"] = "Bearer fake-secret-token"
        openai["headers"] = {"password": "fake-secret-password", "safe": "not sensitive"}

        redacted = redacted_retrieval_provider_config(config)
        provider = redacted["config"]["embedding"]["providers"]["openai:text-embedding-3-small"]

        self.assertEqual(redacted["schema"], REDACTED_CONFIG_SCHEMA)
        self.assertEqual(provider["api_key_env"], "OPENAI_API_KEY")
        self.assertEqual(provider["api_key"], "<redacted>")
        self.assertEqual(provider["authorization"], "<redacted>")
        self.assertEqual(provider["headers"]["password"], "<redacted>")
        self.assertEqual(provider["headers"]["safe"], "not sensitive")
        self.assertNotIn("sk-fake-secret-sentinel", json.dumps(redacted))
        self.assertNotIn("Bearer fake-secret-token", json.dumps(redacted))

    def test_hash_is_stable_and_ignores_secret_value_changes(self):
        first = retrieval_provider_config_template()
        second = retrieval_provider_config_template()
        first["embedding"]["providers"]["openai:text-embedding-3-small"]["api_key"] = "sk-fake-secret-one"
        second["embedding"]["providers"]["openai:text-embedding-3-small"]["api_key"] = "sk-fake-secret-two"

        self.assertEqual(retrieval_provider_config_hash(first), retrieval_provider_config_hash(second))

        second["embedding"]["providers"]["openai:text-embedding-3-small"]["model_id"] = "different-model"
        self.assertNotEqual(retrieval_provider_config_hash(first), retrieval_provider_config_hash(second))

    def test_env_readiness_reports_booleans_without_leaking_values(self):
        config = retrieval_provider_config_template()
        config["embedding"]["providers"]["openai:text-embedding-3-small"]["enabled"] = True
        readiness = retrieval_provider_readiness(config, env={"OPENAI_API_KEY": "sk-fake-secret-sentinel"})
        payload = json.dumps(readiness, sort_keys=True)
        openai = next(
            check
            for check in readiness["checks"]
            if check["kind"] == "embedding" and check["provider_id"] == "openai:text-embedding-3-small"
        )

        self.assertTrue(openai["enabled"])
        self.assertTrue(openai["network"])
        self.assertTrue(openai["hosted"])
        self.assertEqual(openai["api_key_env"], "OPENAI_API_KEY")
        self.assertTrue(openai["api_key_ready"])
        self.assertNotIn("sk-fake-secret-sentinel", payload)
        self.assertNotIn("fake-secret", payload)

    def test_env_value_changes_do_not_affect_hashes(self):
        config = retrieval_provider_config_template()
        first = retrieval_provider_readiness(config, env={"OPENAI_API_KEY": "sk-fake-secret-one"})
        second = retrieval_provider_readiness(config, env={"OPENAI_API_KEY": "sk-fake-secret-two"})

        self.assertEqual(first["config_hash"], second["config_hash"])

    def test_network_embedding_provider_requires_explicit_runtime_allow(self):
        config = retrieval_provider_config_template()
        config["embedding"]["providers"]["openai:text-embedding-3-small"]["enabled"] = True

        with self.assertRaisesRegex(ValueError, "network provider not allowed"):
            resolve_embedding_provider(
                config,
                "openai:text-embedding-3-small",
                allow_network_providers=False,
                env={"OPENAI_API_KEY": "sk-fake-secret-sentinel"},
            )

        entry = resolve_embedding_provider(
            config,
            "openai:text-embedding-3-small",
            allow_network_providers=True,
            env={"OPENAI_API_KEY": "sk-fake-secret-sentinel"},
        )

        self.assertEqual(entry.provider_id, "openai:text-embedding-3-small")
        self.assertTrue(entry.network)

    def test_network_reranker_provider_requires_explicit_runtime_allow(self):
        config = retrieval_provider_config_template()
        config["reranker"]["providers"]["cohere:rerank-v3.5"]["enabled"] = True

        with self.assertRaisesRegex(ValueError, "network provider not allowed"):
            resolve_reranker_provider(
                config,
                "cohere:rerank-v3.5",
                allow_network_providers=False,
                env={"COHERE_API_KEY": "cohere-test-secret"},
            )

        entry = resolve_reranker_provider(
            config,
            "cohere:rerank-v3.5",
            allow_network_providers=True,
            env={"COHERE_API_KEY": "cohere-test-secret"},
        )

        self.assertEqual(entry.provider_id, "cohere:rerank-v3.5")
        self.assertTrue(entry.network)

    def test_malformed_config_errors_are_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "retrieval-providers.json"
            path.write_text("{bad json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "malformed retrieval provider config"):
                load_retrieval_provider_config(path)

            path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported retrieval provider config schema"):
                load_retrieval_provider_config(path)


if __name__ == "__main__":
    unittest.main()
