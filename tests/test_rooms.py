import hashlib
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zerker_memory.cli import build_parser
from zerker_memory.rooms import (
    MAX_ABSTENTION_IDS,
    ROOM_STORAGE_DESCRIPTOR_SCHEMA,
    RoomMemoryConflict,
    RoomMemoryService,
    RoomStoreResolver,
    member_scope,
    room_storage_key,
    verify_room_context_commitment,
)
from zerker_memory.rooms_acceptance import (
    ROOM_ACCEPTANCE_SCHEMA,
    render_rooms_acceptance_summary,
    run_local_rooms_acceptance,
)
from zerker_memory.dense import dense_hybrid_retrieval_config
from zerker_memory.retrieval_providers import EmbeddingProviderResult, local_dense_provider_config
from zerker_memory.service import RoomMemoryHTTPServer, host_is_loopback, serve_room_memory
from zerker_memory.store import MemoryStore, sha256_text, stable_json


def _fake_room_embed_texts(provider_entry, texts, *, input_type="document", allow_model_download=False, **_kwargs):
    vectors = [[1.0, 0.0] for _text in texts]
    return EmbeddingProviderResult(
        provider_id=provider_entry.provider_id,
        model_id=provider_entry.model_id or "BAAI/bge-small-en-v1.5",
        dims=2,
        normalized=True,
        vectors=vectors,
        latency_ms=0.1,
        network_call=allow_model_download,
        vector_hashes=[
            "sha256:" + hashlib.sha256(repr(vector).encode("utf-8")).hexdigest()
            for vector in vectors
        ],
        model_digest="sha256:test-room-model",
    )


class RoomMemoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "rooms"
        self.resolver = RoomStoreResolver(self.root, tenant_id="tenant-a")
        self.service = RoomMemoryService(self.resolver)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fts_service_readiness_is_immediate(self):
        readiness = self.service.readiness()

        self.assertTrue(readiness["ok"])
        self.assertTrue(readiness["storage_ready"])
        self.assertEqual(readiness["retrieval"]["mode"], "fts")
        self.assertEqual(readiness["retrieval"]["state"], "ready")
        self.assertFalse(readiness["retrieval"]["network_calls_enabled"])

    @patch("zerker_memory.retrieval_providers.retrieval_provider_readiness")
    def test_dense_service_readiness_requires_runtime_and_cached_model(self, provider_readiness):
        service = RoomMemoryService(
            self.resolver,
            retrieval_config=dense_hybrid_retrieval_config(),
            retrieval_provider_config=local_dense_provider_config(cache_dir=self.root / "models"),
        )

        for runtime_ready, model_cached, expected_state, expected_reason in (
            (False, False, "unavailable", "dense-runtime-unavailable"),
            (True, False, "unavailable", "dense-model-unavailable"),
            (True, True, "ready", None),
        ):
            with self.subTest(runtime_ready=runtime_ready, model_cached=model_cached):
                provider_readiness.return_value = {
                    "schema": "zerker.retrieval_provider_readiness.v1",
                    "ok": True,
                    "config_hash": "sha256:test-config",
                    "checks": [
                        {
                            "kind": "embedding",
                            "provider_id": "local:fastembed",
                            "enabled": True,
                            "network": False,
                            "runtime_ready": runtime_ready,
                            "model_cached": model_cached,
                        }
                    ],
                }

                readiness = service.readiness()

                self.assertEqual(readiness["ok"], expected_state == "ready")
                self.assertEqual(readiness["retrieval"]["state"], expected_state)
                self.assertEqual(readiness["retrieval"].get("reason"), expected_reason)
                self.assertEqual(readiness["retrieval"]["provider_id"], "local:fastembed")
                self.assertFalse(readiness["retrieval"]["network_calls_enabled"])
                if expected_reason is None:
                    self.assertNotIn("next_command", readiness["retrieval"])
                else:
                    self.assertIn("embeddings index --download-model", readiness["retrieval"]["next_command"])

    def context(self, room_id="rom_alpha", agent_id="agt_a", purpose="continue the release", **updates):
        request = {
            "room_id": room_id,
            "agent_id": agent_id,
            "purpose": purpose,
            "risk": "medium",
            "context_budget_tokens": 2_000,
            "membership_digest": "sha256:" + "1" * 64,
            "room_state_digest": "sha256:" + "2" * 64,
            "request_id": "req_1",
        }
        request.update(updates)
        return self.service.prepare_context(request)

    def write(self, *, trusted=True, room_id="rom_alpha", agent_id="agt_a", content="Release uses tag v1", visibility="room", key="evt_1:release", **updates):
        request = {
            "room_id": room_id,
            "agent_id": agent_id,
            "content": content,
            "memory_type": "semantic",
            "visibility": visibility,
            "source_event_id": "evt_1",
            "idempotency_key": key,
        }
        request.update(updates)
        operation = self.service.record_memory if trusted else self.service.propose_memory
        return operation(request)

    def test_empty_room_is_explicit_and_committed(self):
        result = self.context()

        self.assertEqual(result["state"], "empty")
        self.assertEqual(result["counts"], {"retrieved": 0, "admitted": 0, "withheld": 0, "budget_dropped": 0})
        self.assertEqual(result["memories"], [])
        self.assertEqual(result["retrieval_index"]["state"], "not-required")
        self.assertTrue(verify_room_context_commitment(result))
        self.assertEqual(result["commitment"]["membership_digest"], "sha256:" + "1" * 64)
        self.assertNotIn("continue the release", json.dumps(result))

    def test_room_store_records_a_discoverable_local_identity(self):
        self.write(content="Keep the release room durable")

        descriptor_path = self.resolver.db_path("rom_alpha").parent / "room.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        rooms = self.resolver.list_rooms()

        self.assertEqual(descriptor["schema"], ROOM_STORAGE_DESCRIPTOR_SCHEMA)
        self.assertEqual(descriptor["tenant_id"], "tenant-a")
        self.assertEqual(descriptor["room_id"], "rom_alpha")
        self.assertEqual(descriptor["database"], "memory.sqlite")
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["room_id"], "rom_alpha")
        self.assertEqual(rooms[0]["descriptor_state"], "recorded")
        self.assertEqual(rooms[0]["db_path"], str(self.resolver.db_path("rom_alpha").resolve()))

    def test_room_discovery_infers_identity_for_a_pre_descriptor_store(self):
        self.write(content="This room predates local discovery descriptors")
        descriptor_path = self.resolver.db_path("rom_alpha").parent / "room.json"
        descriptor_path.unlink()

        rooms = self.resolver.list_rooms()

        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["room_id"], "rom_alpha")
        self.assertEqual(rooms[0]["descriptor_state"], "inferred")
        self.assertFalse(descriptor_path.exists())

    def test_room_open_refuses_to_overwrite_a_malformed_descriptor(self):
        room_dir = self.resolver.db_path("rom_alpha").parent
        room_dir.mkdir(parents=True)
        descriptor_path = room_dir / "room.json"
        descriptor_path.write_text('{"schema":"unknown"}\n', encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "descriptor is malformed"):
            self.write(content="Do not overwrite local storage identity")

        self.assertEqual(json.loads(descriptor_path.read_text(encoding="utf-8"))["schema"], "unknown")

    def test_room_schema_initialization_runs_once_per_resolver(self):
        original_init = MemoryStore.init
        calls = 0

        def counted_init(store):
            nonlocal calls
            calls += 1
            original_init(store)

        with patch("zerker_memory.rooms.MemoryStore.init", new=counted_init):
            with self.resolver.open("rom_alpha") as store:
                self.assertEqual(store.conn.execute("SELECT 1").fetchone()[0], 1)
            with self.resolver.open("rom_alpha") as store:
                self.assertEqual(store.list_memories(), [])

        self.assertEqual(calls, 1)

    def test_room_schema_cache_recovers_after_database_replacement(self):
        with self.resolver.open("rom_alpha") as store:
            store.remember(
                "Original room memory",
                memory_type="semantic",
                scope="global",
                source_kind="system",
            )

        db_path = self.resolver.db_path("rom_alpha")
        db_path.unlink()
        Path(f"{db_path}-wal").unlink(missing_ok=True)
        Path(f"{db_path}-shm").unlink(missing_ok=True)

        with self.resolver.open("rom_alpha") as store:
            self.assertEqual(store.list_memories(), [])
            tables = {
                row[0]
                for row in store.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            }

        self.assertIn("memories", tables)

    def test_room_schema_cache_repairs_a_changed_schema(self):
        with self.resolver.open("rom_alpha") as store:
            store.conn.execute("DROP INDEX events_memory_id_seq_idx")
            store.conn.commit()

        with self.resolver.open("rom_alpha") as store:
            indexes = {
                row[1]
                for row in store.conn.execute("PRAGMA index_list(events)").fetchall()
            }

        self.assertIn("events_memory_id_seq_idx", indexes)

    def test_nonempty_room_with_no_relevant_fts_match_abstains(self):
        self.write(
            content="we agreed to ship on Friday after the security review passed",
            key="evt_semantic:decision",
        )

        result = self.context(purpose="ship the product safely")

        self.assertEqual(result["state"], "abstained")
        self.assertEqual(result["counts"]["retrieved"], 0)
        self.assertEqual(result["omissions"]["abstention"]["reason"], "no-relevant-memory")
        self.assertTrue(verify_room_context_commitment(result))

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=_fake_room_embed_texts)
    def test_dense_rooms_index_writes_and_recalls_semantic_goal(self, _embed):
        provider_config = local_dense_provider_config(cache_dir=self.root / "models")
        service = RoomMemoryService(
            self.resolver,
            retrieval_config=dense_hybrid_retrieval_config(min_score=0.5),
            retrieval_provider_config=provider_config,
        )
        write = service.record_memory(
            {
                "room_id": "rom_alpha",
                "agent_id": "agt_a",
                "content": "we agreed to ship on Friday after the security review passed",
                "memory_type": "semantic",
                "visibility": "room",
                "source_event_id": "evt_dense",
                "idempotency_key": "evt_dense:decision",
            }
        )

        result = service.prepare_context(
            {
                "room_id": "rom_alpha",
                "agent_id": "agt_b",
                "purpose": "ship the product safely",
                "risk": "medium",
            }
        )

        self.assertEqual(write["retrieval_index"]["state"], "ready")
        self.assertEqual(write["retrieval_index"]["indexed_now"], 1)
        self.assertEqual(result["state"], "ready")
        self.assertEqual(
            [memory["content"] for memory in result["memories"]],
            ["we agreed to ship on Friday after the security review passed"],
        )
        self.assertEqual(result["retrieval_index"]["coverage"], 1.0)
        self.assertFalse(result["retrieval_index"]["network_calls_enabled"])

    @patch("zerker_memory.retrieval_providers.embed_texts", side_effect=ValueError("model unavailable"))
    def test_dense_rooms_report_unavailable_index_without_losing_write(self, _embed):
        service = RoomMemoryService(
            self.resolver,
            retrieval_config=dense_hybrid_retrieval_config(),
            retrieval_provider_config=local_dense_provider_config(cache_dir=self.root / "models"),
        )

        write = service.record_memory(
            {
                "room_id": "rom_alpha",
                "agent_id": "agt_a",
                "content": "we agreed to ship on Friday after the security review passed",
                "source_event_id": "evt_unavailable",
                "idempotency_key": "evt_unavailable:decision",
            }
        )
        result = service.prepare_context(
            {
                "room_id": "rom_alpha",
                "agent_id": "agt_b",
                "purpose": "ship the product safely",
                "risk": "medium",
            }
        )

        self.assertEqual(write["retrieval_index"]["state"], "unavailable")
        self.assertEqual(write["retrieval_index"]["reason"], "dense-model-unavailable")
        self.assertEqual(result["state"], "abstained")
        self.assertEqual(result["retrieval_index"]["state"], "unavailable")
        with self.resolver.open("rom_alpha") as store:
            self.assertEqual(len(store.list_memories(scope="global", status="active")), 1)

    @patch("zerker_memory.rooms.MemoryStore.inject")
    def test_abstention_omission_is_bounded_to_known_fields(self, inject):
        abstained_ids = [f"mem_{index}" for index in range(MAX_ABSTENTION_IDS + 3)]
        inject.return_value = {
            "action_id": "act_abstain",
            "created_at": "2026-08-10T20:45:26Z",
            "memories": [],
            "retrieved_memory_ids": abstained_ids,
            "withheld": [],
            "merkle_root": "sha256:" + "7" * 64,
            "memory_context": {
                "context_digest": "sha256:" + "4" * 64,
                "policy_digest": "sha256:" + "5" * 64,
                "memory_tree_root": "sha256:" + "6" * 64,
            },
            "retrieval": {
                "packing": {"budget_dropped": []},
                "temporal": {
                    "abstention": {
                        "applied": True,
                        "reason": "unresolved-current-conflict",
                        "abstained_ids": abstained_ids,
                        "conflict_reasons": ["lexical-current-conflict"],
                        "raw_context": "must not cross the service boundary",
                    }
                },
            },
        }

        result = self.context()
        abstention = result["omissions"]["abstention"]

        self.assertEqual(result["state"], "abstained")
        self.assertEqual(
            set(abstention),
            {"applied", "reason", "abstained_ids", "abstained_count", "conflict_reasons"},
        )
        self.assertEqual(len(abstention["abstained_ids"]), MAX_ABSTENTION_IDS)
        self.assertEqual(abstention["abstained_count"], MAX_ABSTENTION_IDS + 3)
        self.assertNotIn("raw_context", json.dumps(result))

    def test_room_context_commitment_matches_cross_language_golden_vector(self):
        fixture_path = Path(__file__).parent / "fixtures" / "room_context_commitment_v1.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        commitment = dict(fixture["material"])
        commitment["room_context_digest"] = fixture["room_context_digest"]

        self.assertEqual(stable_json(fixture["material"]), fixture["canonical_json"])
        self.assertEqual(
            "sha256:" + sha256_text(fixture["canonical_json"]),
            fixture["room_context_digest"],
        )
        self.assertTrue(verify_room_context_commitment({"commitment": commitment}))

    def test_room_memory_is_shared_but_member_memory_is_private(self):
        shared = self.write(content="The room deploy target is production", key="evt_1:target")
        private = self.write(
            content="Agent A prefers a compact terminal summary",
            visibility="member",
            key="evt_2:preference",
        )

        agent_a = self.context(agent_id="agt_a", purpose="What should Agent A know about the deploy and summary?")
        agent_b = self.context(agent_id="agt_b", purpose="What is the room deploy target and Agent A preference?")

        self.assertEqual(shared["memory"]["visibility"], "room")
        self.assertEqual(private["memory"]["visibility"], "member")
        self.assertCountEqual(
            [memory["content"] for memory in agent_a["memories"]],
            ["The room deploy target is production", "Agent A prefers a compact terminal summary"],
        )
        self.assertEqual([memory["content"] for memory in agent_b["memories"]], ["The room deploy target is production"])
        self.assertEqual(agent_b["memories"][0]["provenance"]["source_uri"], "room://rom_alpha/events/evt_1")

    def test_agent_proposal_is_blocked_until_review(self):
        proposal = self.write(
            trusted=False,
            content="Deploy without approval",
            key="evt_3:unsafe-procedure",
            memory_type="procedural",
        )
        result = self.context(purpose="Should we deploy without approval?")

        self.assertEqual(proposal["memory"]["status"], "quarantined")
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["counts"]["admitted"], 0)
        self.assertEqual(result["counts"]["withheld"], 1)
        self.assertEqual(result["omissions"]["withheld"][0]["rule"], "active-status-required")

    def test_active_and_withheld_memory_return_partial_state(self):
        self.write(content="Release approval is required", key="evt_4:approval")
        self.write(
            trusted=False,
            content="Release approval can be skipped",
            key="evt_5:skip-approval",
        )

        result = self.context(purpose="Can release approval be skipped or is it required?")

        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["counts"]["admitted"], 1)
        self.assertEqual(result["counts"]["withheld"], 1)

    def test_idempotent_write_replays_and_rejects_changed_content(self):
        first = self.write(content="The room owner is Revaz", key="evt_6:owner")
        replay = self.write(content="The room owner is Revaz", key="evt_6:owner")

        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(first["memory"]["id"], replay["memory"]["id"])
        with self.assertRaises(RoomMemoryConflict):
            self.write(content="The room owner is Jacob", key="evt_6:owner")
        with self.assertRaises(RoomMemoryConflict):
            self.write(content="The room owner is Revaz", key="evt_6:owner", source_event_id="evt_changed")

    def test_room_store_survives_service_restart_and_isolates_rooms(self):
        self.write(content="Alpha room memory", room_id="rom_alpha", key="evt_7:alpha")
        restarted = RoomMemoryService(RoomStoreResolver(self.root, tenant_id="tenant-a"))

        alpha = restarted.prepare_context(
            {"room_id": "rom_alpha", "agent_id": "agt_b", "purpose": "Alpha room memory", "risk": "low"}
        )
        beta = restarted.prepare_context(
            {"room_id": "rom_beta", "agent_id": "agt_b", "purpose": "Alpha room memory", "risk": "low"}
        )

        self.assertEqual([memory["content"] for memory in alpha["memories"]], ["Alpha room memory"])
        self.assertEqual(beta["state"], "empty")
        self.assertNotEqual(self.resolver.db_path("rom_alpha"), self.resolver.db_path("rom_beta"))

    def test_storage_paths_are_opaque_and_tenant_bound(self):
        first = room_storage_key("tenant-a", "rom_alpha")
        second = room_storage_key("tenant-b", "rom_alpha")

        self.assertNotEqual(first, second)
        self.assertNotIn("tenant", first)
        self.assertNotIn("rom_alpha", str(self.resolver.db_path("rom_alpha")))
        self.assertTrue(member_scope("agt_a").startswith("member:"))

    def test_same_room_id_is_isolated_across_configured_tenants(self):
        self.write(content="Tenant A release target", key="evt_tenant_a:target")
        tenant_b = RoomMemoryService(RoomStoreResolver(self.root, tenant_id="tenant-b"))

        result = tenant_b.prepare_context(
            {"room_id": "rom_alpha", "agent_id": "agt_a", "purpose": "release target", "risk": "low"}
        )

        self.assertEqual(result["state"], "empty")
        self.assertEqual(result["memories"], [])

    def test_room_storage_refuses_symlink_escape(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        room_dir = self.resolver.db_path("rom_symlink").parent
        room_dir.symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "cannot be a symlink"):
            self.service.prepare_context(
                {"room_id": "rom_symlink", "agent_id": "agt_a", "purpose": "continue", "risk": "low"}
            )

    def test_concurrent_room_writes_are_durable_and_idempotent(self):
        first_open = threading.Barrier(8)

        def write_unique(index):
            if index < first_open.parties:
                first_open.wait()
            return self.write(
                content=f"Concurrent fact {index}",
                key=f"evt_{index}:fact",
                source_event_id=f"evt_{index}",
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            unique = list(executor.map(write_unique, range(12)))
            replayed = list(
                executor.map(
                    lambda _: self.write(content="One retry-safe fact", key="evt_retry:fact", source_event_id="evt_retry"),
                    range(8),
                )
            )

        self.assertEqual(len({item["memory"]["id"] for item in unique}), 12)
        self.assertEqual(len({item["memory"]["id"] for item in replayed}), 1)
        self.assertEqual(sum(item["replayed"] for item in replayed), 7)
        with self.resolver.open("rom_alpha") as store:
            self.assertEqual(len(store.list_memories(scope="global")), 13)


class RoomMemoryHTTPTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        resolver = RoomStoreResolver(Path(self.tmp.name) / "rooms", tenant_id="tenant-a")
        self.server = RoomMemoryHTTPServer(
            ("127.0.0.1", 0),
            RoomMemoryService(resolver),
            bearer_token="room-secret",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, path, *, payload=None, token="room-secret"):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"content-type": "application/json"}
        if token is not None:
            headers["authorization"] = f"Bearer {token}"
        request = Request(self.base_url + path, data=data, headers=headers, method="POST" if payload is not None else "GET")
        try:
            response = urlopen(request, timeout=3)
            return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_health_version_and_authenticated_room_flow(self):
        health_status, health = self.request("/healthz")
        readiness_status, readiness = self.request("/readyz")
        version_status, version = self.request("/version")
        write_status, write = self.request(
            "/v1/memories:record",
            payload={
                "room_id": "rom_alpha",
                "agent_id": "agt_a",
                "content": "The accepted implementation uses a room store",
                "source_event_id": "evt_1",
                "idempotency_key": "evt_1:implementation",
            },
        )
        context_status, context = self.request(
            "/v1/contexts:prepare",
            payload={
                "room_id": "rom_alpha",
                "agent_id": "agt_b",
                "purpose": "Which implementation was accepted?",
                "risk": "medium",
            },
        )

        self.assertEqual(health_status, 200)
        self.assertTrue(health["ok"])
        self.assertEqual(readiness_status, 200)
        self.assertTrue(readiness["ok"])
        self.assertEqual(readiness["retrieval"]["mode"], "fts")
        self.assertEqual(version_status, 200)
        self.assertIn("version", version)
        self.assertEqual(write_status, 201)
        self.assertEqual(context_status, 200)
        self.assertEqual(context["state"], "ready")
        self.assertEqual(context["memories"][0]["id"], write["memory"]["id"])

    @patch("zerker_memory.retrieval_providers.retrieval_provider_readiness")
    def test_dense_readyz_fails_closed_until_model_is_cached(self, provider_readiness):
        provider_readiness.return_value = {
            "schema": "zerker.retrieval_provider_readiness.v1",
            "ok": True,
            "config_hash": "sha256:test-config",
            "checks": [
                {
                    "kind": "embedding",
                    "provider_id": "local:fastembed",
                    "enabled": True,
                    "network": False,
                    "runtime_ready": True,
                    "model_cached": False,
                }
            ],
        }
        self.server.service = RoomMemoryService(
            self.server.service.resolver,
            retrieval_config=dense_hybrid_retrieval_config(),
            retrieval_provider_config=local_dense_provider_config(cache_dir=Path(self.tmp.name) / "models"),
        )

        status, readiness = self.request("/readyz")

        self.assertEqual(status, 503)
        self.assertFalse(readiness["ok"])
        self.assertEqual(readiness["retrieval"]["reason"], "dense-model-unavailable")

    def test_inject_alias_accepts_gateway_task_vocabulary(self):
        self.request(
            "/v1/memories:record",
            payload={
                "room_id": "rom_alpha",
                "agent_id": "agt_a",
                "content": "The room goal is ship safely",
                "source_event_id": "evt_2",
                "idempotency_key": "evt_2:goal",
            },
        )

        status, context = self.request(
            "/v1/inject",
            payload={
                "room_id": "rom_alpha",
                "agent_id": "agt_b",
                "task": "What is the room goal?",
                "risk": "medium",
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(context["state"], "ready")
        self.assertEqual(context["memories"][0]["content"], "The room goal is ship safely")

    def test_auth_and_tenant_resolution_fail_closed(self):
        unauthorized_status, unauthorized = self.request(
            "/v1/contexts:prepare",
            token=None,
            payload={"room_id": "rom_alpha", "agent_id": "agt_a", "purpose": "continue"},
        )
        tenant_status, tenant = self.request(
            "/v1/contexts:prepare",
            payload={
                "tenant_id": "tenant-b",
                "room_id": "rom_alpha",
                "agent_id": "agt_a",
                "purpose": "continue",
            },
        )

        self.assertEqual(unauthorized_status, 401)
        self.assertEqual(unauthorized["error"]["code"], "unauthorized")
        self.assertEqual(tenant_status, 400)
        self.assertIn("must not be supplied", tenant["error"]["message"])

    def test_loopback_detection(self):
        self.assertTrue(host_is_loopback("127.0.0.1"))
        self.assertTrue(host_is_loopback("localhost"))
        self.assertFalse(host_is_loopback("0.0.0.0"))

    def test_remote_bind_requires_explicit_opt_in_and_token(self):
        with self.assertRaisesRegex(ValueError, "--allow-remote"):
            serve_room_memory(
                self.server.service,
                host="0.0.0.0",
                port=8766,
                bearer_token="room-secret",
            )
        with self.assertRaisesRegex(ValueError, "ZMEM_SERVICE_TOKEN"):
            serve_room_memory(
                self.server.service,
                host="0.0.0.0",
                port=8766,
                bearer_token=None,
                allow_remote=True,
            )

    @patch("zerker_memory.service.RoomMemoryHTTPServer")
    def test_cli_server_stops_cleanly_on_keyboard_interrupt(self, server_class):
        server = server_class.return_value
        server.server_port = 8766
        server.serve_forever.side_effect = KeyboardInterrupt

        with patch("builtins.print"):
            serve_room_memory(
                self.server.service,
                host="127.0.0.1",
                port=8766,
                bearer_token="room-secret",
            )

        server.server_close.assert_called_once_with()


class RoomMemoryAcceptanceTest(unittest.TestCase):
    def test_local_acceptance_covers_isolation_fail_closed_and_concurrent_reads(self):
        result = run_local_rooms_acceptance(
            requests=12,
            concurrency=4,
            timeout_seconds=3,
            max_p95_ms=5_000,
        )

        self.assertEqual(result["schema"], ROOM_ACCEPTANCE_SCHEMA)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["latency"]["completed_requests"], 12)
        self.assertTrue(all(result["checks"].values()), result["checks"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["profile"]["storage"], "ephemeral-sqlite")

    def test_local_acceptance_rejects_invalid_load_parameters(self):
        for kwargs, message in (
            ({"requests": 0}, "requests"),
            ({"requests": 10_001}, "requests"),
            ({"concurrency": 0}, "concurrency"),
            ({"concurrency": 129}, "concurrency"),
            ({"timeout_seconds": 0}, "timeout_seconds"),
            ({"timeout_seconds": float("nan")}, "timeout_seconds"),
            ({"max_p95_ms": 0}, "max_p95_ms"),
            ({"max_p95_ms": float("inf")}, "max_p95_ms"),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, message):
                    run_local_rooms_acceptance(**kwargs)

    @patch("zerker_memory.rooms_acceptance._run_contract_checks", side_effect=RuntimeError("backend failed"))
    def test_local_acceptance_reports_contract_failure_without_traceback(self, _contract_checks):
        result = run_local_rooms_acceptance(requests=2, concurrency=1)

        self.assertFalse(result["ok"])
        self.assertEqual(result["latency"]["completed_requests"], 0)
        self.assertEqual(result["failures"], [{"phase": "contract", "error": "backend failed"}])
        summary = render_rooms_acceptance_summary(result)
        self.assertIn("p50 n/a ms", summary)
        self.assertNotIn("None ms", summary)

    def test_rooms_acceptance_cli_arguments_are_explicit(self):
        args = build_parser("zmem").parse_args(
            [
                "rooms-acceptance",
                "--requests",
                "20",
                "--concurrency",
                "5",
                "--timeout-seconds",
                "2.5",
                "--max-p95-ms",
                "400",
                "--summary-only",
            ]
        )

        self.assertEqual(args.command, "rooms-acceptance")
        self.assertEqual(args.requests, 20)
        self.assertEqual(args.concurrency, 5)
        self.assertEqual(args.timeout_seconds, 2.5)
        self.assertEqual(args.max_p95_ms, 400)
        self.assertTrue(args.summary_only)


if __name__ == "__main__":
    unittest.main()
