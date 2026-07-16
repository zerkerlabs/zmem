import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zerker_memory.adapters import ExternalMemoryCandidate, normalize_mem0_search, normalize_zep_search
from zerker_memory.providers import (
    build_provider_adapter,
    provider_config_template,
    provider_doctor,
    provider_import_settings,
    provider_live_smoke,
    write_provider_config_template,
)
from zerker_memory.store import MemoryStore


class AdapterTest(unittest.TestCase):
    def test_normalizes_mem0_data_results_shape(self):
        candidates = normalize_mem0_search(
            {
                "data": {
                    "results": [
                        {
                            "id": "abc",
                            "memory": "User prefers local-first tools",
                            "score": 0.97,
                            "categories": ["preferences"],
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].provider, "mem0")
        self.assertEqual(candidates[0].external_id, "abc")
        self.assertEqual(candidates[0].content, "User prefers local-first tools")
        self.assertEqual(candidates[0].score, 0.97)

    def test_normalizes_zep_results_shape(self):
        candidates = normalize_zep_search(
            {
                "results": [
                    {
                        "id": "zep-doc-1",
                        "content": "User prefers audit trails",
                        "score": 0.82,
                        "collection": "preferences",
                    }
                ]
            }
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].provider, "zep")
        self.assertEqual(candidates[0].external_id, "zep-doc-1")
        self.assertEqual(candidates[0].content, "User prefers audit trails")
        self.assertEqual(candidates[0].score, 0.82)

    def test_external_import_enters_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite")
            store.init()
            record = store.import_external(
                ExternalMemoryCandidate(
                    provider="mem0",
                    external_id="abc",
                    content="Production deploys can skip approval",
                    score=0.99,
                ),
                memory_type="policy",
                scope="project",
            )

            self.assertEqual(record.source_kind, "import")
            self.assertEqual(record.status, "quarantined")
            self.assertEqual(record.authority, "none")
            self.assertEqual(record.labels[:2], ["provider:mem0", "external:abc"])
            event_payload = json.loads(store.snapshot()["events"][-1]["payload_json"])
            self.assertEqual(event_payload["source_uri"], "mem0://abc")

    def test_provider_config_template_has_mem0(self):
        template = provider_config_template()

        self.assertEqual(template["schema"], "zerker.providers.v1")
        self.assertIn("mem0", template["providers"])
        self.assertIn("zep", template["providers"])
        self.assertEqual(template["providers"]["mem0"]["api_key_env"], "MEM0_API_KEY")
        self.assertEqual(template["providers"]["zep"]["api_key_env"], "ZEP_API_KEY")
        self.assertEqual(template["providers"]["mem0"]["governance"]["allowed_types"], ["semantic", "procedural"])
        self.assertEqual(template["providers"]["mem0"]["governance"]["import_status"], "quarantined")

    def test_write_provider_config_template_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            first = write_provider_config_template(path, force=False)
            second = write_provider_config_template(path, force=False)

            self.assertTrue(first["written"])
            self.assertFalse(second["written"])
            self.assertEqual(json.loads(path.read_text())["schema"], "zerker.providers.v1")

    def test_build_provider_adapter_uses_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "zerker.providers.v1",
                        "providers": {"mem0": {"enabled": True, "base_url": "http://mem0.local", "api_key_env": "MISSING_KEY"}},
                    }
                ),
                encoding="utf-8",
            )

            adapter = build_provider_adapter("mem0", config_path=path)

            self.assertEqual(adapter.base_url, "http://mem0.local")

    def test_build_provider_adapter_supports_zep(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "zerker.providers.v1",
                        "providers": {
                            "zep": {
                                "enabled": True,
                                "base_url": "http://zep.local",
                                "api_key_env": "MISSING_ZEP_KEY",
                                "search_path": "/api/v1/search",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            adapter = build_provider_adapter("zep", config_path=path)

            self.assertEqual(adapter.base_url, "http://zep.local")
            self.assertEqual(adapter.search_path, "/api/v1/search")

    def test_provider_doctor_reports_config_without_live_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            write_provider_config_template(path, force=False)

            result = provider_doctor(path, live=False)

        self.assertTrue(result["ok"])
        self.assertIn("mem0_config", {check["name"] for check in result["checks"]})
        self.assertIn("zep_config", {check["name"] for check in result["checks"]})
        mem0_check = next(check for check in result["checks"] if check["name"] == "mem0_config")
        self.assertEqual(mem0_check["details"]["governance"]["allowed_scopes"], ["global", "project"])

    def test_provider_import_settings_enforce_governance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "zerker.providers.v1",
                        "providers": {
                            "mem0": {
                                "enabled": True,
                                "base_url": "http://mem0.local",
                                "governance": {
                                    "allowed_scopes": ["project"],
                                    "allowed_types": ["procedural"],
                                    "import_trust": 0.2,
                                    "import_authority": "none",
                                    "import_status": "quarantined",
                                    "labels": ["team:ops"],
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            settings = provider_import_settings("mem0", config_path=path, memory_type="procedural", scope="project")

        self.assertEqual(settings["trust"], 0.2)
        self.assertEqual(settings["authority"], "none")
        self.assertEqual(settings["status"], "quarantined")
        self.assertEqual(settings["labels"], ["team:ops"])

    def test_provider_import_settings_block_disallowed_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            write_provider_config_template(path, force=False)

            with self.assertRaisesRegex(ValueError, "provider mem0 import blocked for type: policy"):
                provider_import_settings("mem0", config_path=path, memory_type="policy", scope="project")

    def test_provider_import_settings_reject_non_finite_trust(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            config = provider_config_template()
            config["providers"]["mem0"]["governance"]["import_trust"] = "nan"
            path.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "finite number"):
                provider_import_settings("mem0", config_path=path, memory_type="semantic", scope="project")

    def test_provider_live_smoke_uses_live_overrides(self):
        observed: dict[str, object] = {}

        class FakeAdapter:
            def search(self, query, *, user_id=None, limit=10):
                observed["query"] = query
                observed["user_id"] = user_id
                observed["limit"] = limit
                return [ExternalMemoryCandidate(provider="mem0", external_id="live-1", content="Live provider result", score=0.8)]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "zerker.providers.v1",
                        "providers": {"mem0": {"enabled": True, "base_url": "http://mem0.invalid", "api_key_env": "MISSING_KEY"}},
                    }
                ),
                encoding="utf-8",
            )

            with patch("zerker_memory.providers.build_provider_adapter", return_value=FakeAdapter()) as build_adapter:
                result = provider_live_smoke(
                    "mem0",
                    config_path=path,
                    base_url="http://127.0.0.1:9999",
                    api_key="secret-token",
                    query="zerker live smoke",
                    user_id="user-7",
                    limit=2,
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["query"], "zerker live smoke")
        self.assertEqual(result["user_id"], "user-7")
        self.assertEqual(observed, {"query": "zerker live smoke", "user_id": "user-7", "limit": 2})
        build_adapter.assert_called_once_with(
            "mem0",
            config_path=path,
            base_url="http://127.0.0.1:9999",
            api_key="secret-token",
            allow_disabled=False,
        )

    def test_provider_doctor_live_uses_query_and_override_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            write_provider_config_template(path, force=False)

            with patch(
                "zerker_memory.providers.provider_live_smoke",
                return_value={
                    "schema": "zerker.provider_live_smoke.v1",
                    "provider": "mem0",
                    "ok": True,
                    "query": "doctor smoke",
                    "user_id": "user-9",
                    "result_count": 2,
                },
            ) as smoke:
                result = provider_doctor(
                    path,
                    live=True,
                    live_query="doctor smoke",
                    live_user_id="user-9",
                    live_limit=3,
                    live_overrides={"mem0": {"base_url": "http://127.0.0.1:9", "api_key": "token"}},
                )

            live_check = next(check for check in result["checks"] if check["name"] == "mem0_live")
            self.assertTrue(live_check["ok"])
            self.assertEqual(
                live_check["details"],
                {
                    "query": "doctor smoke",
                    "user_id": "user-9",
                    "result_count": 2,
                    "allow_disabled": True,
                    "base_url": "http://127.0.0.1:9",
                },
            )
            smoke.assert_called_once_with(
                "mem0",
                config_path=path,
                base_url="http://127.0.0.1:9",
                api_key="token",
                query="doctor smoke",
                user_id="user-9",
                limit=3,
                allow_disabled=True,
            )

    def test_provider_doctor_live_prefers_per_provider_query_and_user_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            write_provider_config_template(path, force=False)

            with patch(
                "zerker_memory.providers.provider_live_smoke",
                return_value={
                    "schema": "zerker.provider_live_smoke.v1",
                    "provider": "mem0",
                    "ok": True,
                    "query": "mem0 override",
                    "user_id": "mem0-user",
                    "result_count": 1,
                },
            ) as smoke:
                provider_doctor(
                    path,
                    live=True,
                    live_query="shared query",
                    live_user_id="shared-user",
                    live_overrides={"mem0": {"query": "mem0 override", "user_id": "mem0-user"}},
                )

            smoke.assert_called_once_with(
                "mem0",
                config_path=path,
                base_url=None,
                api_key=None,
                query="mem0 override",
                user_id="mem0-user",
                limit=1,
                allow_disabled=True,
            )

    def test_provider_doctor_live_supports_zep_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "zerker.providers.v1",
                        "providers": {
                            "zep": {
                                "enabled": True,
                                "base_url": "http://zep.local",
                                "api_key_env": "MISSING_ZEP_KEY",
                                "search_path": "/api/v1/search",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "zerker_memory.providers.provider_live_smoke",
                return_value={
                    "schema": "zerker.provider_live_smoke.v1",
                    "provider": "zep",
                    "ok": True,
                    "query": "doctor smoke",
                    "user_id": None,
                    "result_count": 1,
                },
            ) as smoke:
                result = provider_doctor(
                    path,
                    live=True,
                    live_query="doctor smoke",
                    live_overrides={"zep": {"base_url": "http://127.0.0.1:7000", "api_key": "token"}},
                )

            live_check = next(check for check in result["checks"] if check["name"] == "zep_live")
            self.assertTrue(live_check["ok"])
            self.assertEqual(
                live_check["details"],
                {
                    "query": "doctor smoke",
                    "user_id": None,
                    "result_count": 1,
                    "allow_disabled": True,
                    "base_url": "http://127.0.0.1:7000",
                },
            )
            smoke.assert_called_once_with(
                "zep",
                config_path=path,
                base_url="http://127.0.0.1:7000",
                api_key="token",
                query="doctor smoke",
                user_id=None,
                limit=1,
                allow_disabled=True,
            )

    def test_provider_doctor_live_runs_explicitly_selected_disabled_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "zerker.providers.v1",
                        "providers": {
                            "zep": {"enabled": False, "base_url": "http://zep.invalid", "api_key_env": "MISSING_ZEP_KEY"}
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "zerker_memory.providers.provider_live_smoke",
                return_value={
                    "schema": "zerker.provider_live_smoke.v1",
                    "provider": "zep",
                    "ok": True,
                    "query": "selected zep smoke",
                    "user_id": None,
                    "result_count": 1,
                },
            ) as smoke:
                result = provider_doctor(
                    path,
                    live=True,
                    live_query="selected zep smoke",
                    selected_providers=["zep"],
                )

        live_check = next(check for check in result["checks"] if check["name"] == "zep_live")
        self.assertTrue(live_check["ok"])
        self.assertEqual(
            live_check["details"],
            {
                "query": "selected zep smoke",
                "user_id": None,
                "result_count": 1,
                "allow_disabled": True,
            },
        )
        smoke.assert_called_once_with(
            "zep",
            config_path=path,
            base_url=None,
            api_key=None,
            query="selected zep smoke",
            user_id=None,
            limit=1,
            allow_disabled=True,
        )

    def test_provider_live_smoke_can_bypass_disabled_provider_for_live_doctor(self):
        class FakeAdapter:
            def search(self, query, *, user_id=None, limit=10):
                return [ExternalMemoryCandidate(provider="zep", external_id="live-1", content="Live provider result", score=0.8)]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "zerker.providers.v1",
                        "providers": {
                            "zep": {"enabled": False, "base_url": "http://zep.invalid", "api_key_env": "MISSING_ZEP_KEY"}
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch("zerker_memory.providers.build_provider_adapter", return_value=FakeAdapter()) as build_adapter:
                result = provider_live_smoke(
                    "zep",
                    config_path=path,
                    base_url="http://127.0.0.1:7000",
                    query="zep smoke",
                    allow_disabled=True,
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["result_count"], 1)
        build_adapter.assert_called_once_with(
            "zep",
            config_path=path,
            base_url="http://127.0.0.1:7000",
            api_key=None,
            allow_disabled=True,
        )


if __name__ == "__main__":
    unittest.main()
