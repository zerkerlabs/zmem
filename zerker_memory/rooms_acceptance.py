from __future__ import annotations

import json
import math
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import __version__
from .rooms import RoomMemoryService, RoomStoreResolver, verify_room_context_commitment
from .service import RoomMemoryHTTPServer


ROOM_ACCEPTANCE_SCHEMA = "zerker.room_memory_acceptance.v1"
DEFAULT_REQUESTS = 50
DEFAULT_CONCURRENCY = 4
DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_MAX_P95_MS: float | None = None
MAX_REQUESTS = 10_000
MAX_CONCURRENCY = 128


class _LocalRoomServer:
    def __init__(self, root: Path, *, tenant_id: str, token: str):
        resolver = RoomStoreResolver(root, tenant_id=tenant_id)
        self.server = RoomMemoryHTTPServer(
            ("127.0.0.1", 0),
            RoomMemoryService(resolver),
            bearer_token=token,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.token = token

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def run_local_rooms_acceptance(
    *,
    requests: int = DEFAULT_REQUESTS,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_p95_ms: float | None = DEFAULT_MAX_P95_MS,
) -> dict[str, Any]:
    """Exercise the public Rooms HTTP contract without mutating an external service."""

    if requests < 1 or requests > MAX_REQUESTS:
        raise ValueError(f"requests must be between 1 and {MAX_REQUESTS}")
    if concurrency < 1 or concurrency > MAX_CONCURRENCY:
        raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than 0")
    if max_p95_ms is not None and (not math.isfinite(max_p95_ms) or max_p95_ms <= 0):
        raise ValueError("max_p95_ms must be greater than 0")

    started_at = datetime.now(timezone.utc).isoformat()
    checks: dict[str, bool] = {}
    failures: list[dict[str, Any]] = []
    measured_ms: list[float] = []

    with tempfile.TemporaryDirectory(prefix="zmem-rooms-acceptance-") as tmp:
        root = Path(tmp)
        servers: list[_LocalRoomServer] = []
        try:
            primary = _LocalRoomServer(root / "tenant-a", tenant_id="tenant-a", token="token-a")
            servers.append(primary)
            secondary = _LocalRoomServer(root / "tenant-b", tenant_id="tenant-b", token="token-b")
            servers.append(secondary)
            try:
                _run_contract_checks(primary, secondary, checks=checks, timeout_seconds=timeout_seconds)
            except Exception as exc:
                failures.append({"phase": "contract", "error": str(exc)})
            else:
                scenarios = (
                    (primary, "rom_alpha", "agt_alpha", "What launch target was accepted?"),
                    (primary, "rom_alpha", "agt_alpha", "What private operator token was accepted?"),
                    (primary, "rom_alpha", "agt_beta", "What launch target was accepted?"),
                    (primary, "rom_beta", "agt_beta", "What is the room beta status?"),
                    (secondary, "rom_alpha", "agt_beta", "What is the tenant beta status?"),
                )

                def prepare(index: int) -> None:
                    server, room_id, agent_id, purpose = scenarios[index % len(scenarios)]
                    before = time.perf_counter()
                    status, payload = _request_json(
                        server,
                        "/v1/contexts:prepare",
                        payload={
                            "room_id": room_id,
                            "agent_id": agent_id,
                            "purpose": purpose,
                            "risk": "medium",
                            "request_id": f"acceptance-{index}",
                        },
                        timeout_seconds=timeout_seconds,
                    )
                    elapsed_ms = (time.perf_counter() - before) * 1000
                    if status != 200 or payload.get("state") not in {"ready", "partial"}:
                        raise RuntimeError(f"prepare returned HTTP {status} with state={payload.get('state')}")
                    if not verify_room_context_commitment(payload):
                        raise RuntimeError("prepare returned an invalid room-context commitment")
                    measured_ms.append(elapsed_ms)

                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = [executor.submit(prepare, index) for index in range(requests)]
                    for index, future in enumerate(futures):
                        try:
                            future.result(timeout=timeout_seconds + 1)
                        except Exception as exc:
                            failures.append({"phase": "load", "request_index": index, "error": str(exc)})
        finally:
            for server in reversed(servers):
                server.close()

    latency = _latency_summary(measured_ms)
    checks["concurrent_prepares_completed"] = not failures and len(measured_ms) == requests
    if max_p95_ms is not None:
        checks["p95_within_limit"] = latency["p95_ms"] is not None and latency["p95_ms"] <= max_p95_ms
    ok = all(checks.values()) and not failures
    return {
        "schema": ROOM_ACCEPTANCE_SCHEMA,
        "ok": ok,
        "zmem_version": __version__,
        "started_at": started_at,
        "profile": {
            "transport": "loopback-http",
            "storage": "ephemeral-sqlite",
            "retrieval_mode": "fts",
            "requests": requests,
            "concurrency": concurrency,
            "timeout_seconds": timeout_seconds,
            "max_p95_ms": max_p95_ms,
        },
        "checks": checks,
        "latency": latency,
        "failures": failures[:20],
        "limits": [
            "This is a local engineering acceptance run, not a production SLO.",
            "Gateway still owns its network timeout, retry, deployment, and join-path acceptance.",
        ],
    }


def render_rooms_acceptance_summary(result: Mapping[str, Any]) -> str:
    profile = result.get("profile") if isinstance(result.get("profile"), Mapping) else {}
    latency = result.get("latency") if isinstance(result.get("latency"), Mapping) else {}
    checks = result.get("checks") if isinstance(result.get("checks"), Mapping) else {}
    failed_checks = sorted(key for key, value in checks.items() if value is not True)
    p50 = latency.get("p50_ms") if latency.get("p50_ms") is not None else "n/a"
    p95 = latency.get("p95_ms") if latency.get("p95_ms") is not None else "n/a"
    maximum = latency.get("max_ms") if latency.get("max_ms") is not None else "n/a"
    lines = [
        f"Rooms acceptance: {'PASS' if result.get('ok') else 'FAIL'}",
        (
            f"Load: {latency.get('completed_requests', 0)}/{profile.get('requests', 0)} requests, "
            f"concurrency {profile.get('concurrency', 0)}"
        ),
        (
            f"Latency: p50 {p50} ms, p95 {p95} ms, max {maximum} ms"
        ),
        f"Isolation and fail-closed checks: {sum(value is True for value in checks.values())}/{len(checks)}",
    ]
    if failed_checks:
        lines.append("Failed checks: " + ", ".join(failed_checks))
    failures = result.get("failures") if isinstance(result.get("failures"), list) else []
    if failures:
        lines.append(f"Request failures: {len(failures)}")
    lines.append("Scope: local HTTP + ephemeral SQLite; Gateway production acceptance remains separate.")
    return "\n".join(lines) + "\n"


def _run_contract_checks(
    primary: _LocalRoomServer,
    secondary: _LocalRoomServer,
    *,
    checks: dict[str, bool],
    timeout_seconds: float,
) -> None:
    health_status, health = _request_json(primary, "/healthz", timeout_seconds=timeout_seconds)
    ready_status, readiness = _request_json(primary, "/readyz", timeout_seconds=timeout_seconds)
    checks["liveness"] = health_status == 200 and health.get("ok") is True
    checks["readiness"] = ready_status == 200 and readiness.get("ok") is True

    unauthorized_status, unauthorized = _request_json(
        primary,
        "/v1/contexts:prepare",
        payload={"room_id": "rom_alpha", "agent_id": "agt_alpha", "purpose": "continue"},
        token=None,
        timeout_seconds=timeout_seconds,
    )
    checks["authentication_fails_closed"] = (
        unauthorized_status == 401 and _error_code(unauthorized) == "unauthorized"
    )

    tenant_status, tenant_error = _request_json(
        primary,
        "/v1/contexts:prepare",
        payload={
            "tenant_id": "tenant-b",
            "room_id": "rom_alpha",
            "agent_id": "agt_alpha",
            "purpose": "continue",
        },
        timeout_seconds=timeout_seconds,
    )
    checks["tenant_identity_not_caller_controlled"] = (
        tenant_status == 400 and _error_code(tenant_error) == "invalid_request"
    )

    shared = _record(
        primary,
        room_id="rom_alpha",
        agent_id="agt_alpha",
        content="The isolation marker launch target is the ZMem Rooms acceptance gate.",
        source_event_id="evt-shared",
        idempotency_key="evt-shared:decision",
        visibility="room",
        timeout_seconds=timeout_seconds,
    )
    private = _record(
        primary,
        room_id="rom_alpha",
        agent_id="agt_alpha",
        content="The private operator token is cobalt.",
        source_event_id="evt-private",
        idempotency_key="evt-private:preference",
        visibility="member",
        timeout_seconds=timeout_seconds,
    )
    room_beta = _record(
        primary,
        room_id="rom_beta",
        agent_id="agt_beta",
        content="The isolation marker room beta status is isolated.",
        source_event_id="evt-room-beta",
        idempotency_key="evt-room-beta:status",
        visibility="room",
        timeout_seconds=timeout_seconds,
    )
    tenant_beta = _record(
        secondary,
        room_id="rom_alpha",
        agent_id="agt_beta",
        content="The isolation marker tenant beta status is isolated.",
        source_event_id="evt-tenant-beta",
        idempotency_key="evt-tenant-beta:status",
        visibility="room",
        timeout_seconds=timeout_seconds,
    )

    alpha_shared = _prepare(primary, "rom_alpha", "agt_alpha", "launch target", timeout_seconds)
    alpha_private = _prepare(primary, "rom_alpha", "agt_alpha", "private operator token", timeout_seconds)
    other_member_shared = _prepare(primary, "rom_alpha", "agt_beta", "launch target", timeout_seconds)
    other_member_private = _prepare(primary, "rom_alpha", "agt_beta", "private operator token", timeout_seconds)
    alpha_partition = _prepare(primary, "rom_alpha", "agt_beta", "isolation marker", timeout_seconds)
    beta_room = _prepare(primary, "rom_beta", "agt_beta", "isolation marker", timeout_seconds)
    other_tenant = _prepare(secondary, "rom_alpha", "agt_beta", "isolation marker", timeout_seconds)
    checks["room_memory_shared"] = (
        _memory_ids(alpha_shared) == {shared["memory"]["id"]}
        and _memory_ids(other_member_shared) == {shared["memory"]["id"]}
    )
    checks["member_memory_private"] = (
        _memory_ids(alpha_private) == {private["memory"]["id"]}
        and private["memory"]["id"] not in _memory_ids(other_member_private)
        and other_member_private.get("state") == "abstained"
    )
    checks["room_isolation"] = (
        _memory_ids(alpha_partition) == {shared["memory"]["id"]}
        and _memory_ids(beta_room) == {room_beta["memory"]["id"]}
    )
    checks["tenant_isolation"] = (
        _memory_ids(alpha_partition) == {shared["memory"]["id"]}
        and _memory_ids(other_tenant) == {tenant_beta["memory"]["id"]}
    )
    checks["context_commitments"] = all(
        verify_room_context_commitment(item)
        for item in (
            alpha_shared,
            alpha_private,
            other_member_shared,
            other_member_private,
            alpha_partition,
            beta_room,
            other_tenant,
        )
    )

    abstained = _prepare(primary, "rom_alpha", "agt_beta", "quasar zebrafish", timeout_seconds)
    checks["established_room_miss_abstains"] = (
        abstained.get("state") == "abstained" and not abstained.get("memories")
    )

    replay_status, replay = _request_json(
        primary,
        "/v1/memories:record",
        payload={
            "room_id": "rom_alpha",
            "agent_id": "agt_alpha",
            "content": "The isolation marker launch target is the ZMem Rooms acceptance gate.",
            "source_event_id": "evt-shared",
            "idempotency_key": "evt-shared:decision",
            "visibility": "room",
        },
        timeout_seconds=timeout_seconds,
    )
    conflict_status, conflict = _request_json(
        primary,
        "/v1/memories:record",
        payload={
            "room_id": "rom_alpha",
            "agent_id": "agt_alpha",
            "content": "Changed content must not reuse the same key.",
            "source_event_id": "evt-shared",
            "idempotency_key": "evt-shared:decision",
            "visibility": "room",
        },
        timeout_seconds=timeout_seconds,
    )
    checks["idempotent_replay"] = (
        replay_status == 200
        and replay.get("replayed") is True
        and replay.get("memory", {}).get("id") == shared["memory"]["id"]
    )
    checks["idempotency_conflict_fails_closed"] = (
        conflict_status == 409 and _error_code(conflict) == "idempotency_conflict"
    )


def _record(
    server: _LocalRoomServer,
    *,
    room_id: str,
    agent_id: str,
    content: str,
    source_event_id: str,
    idempotency_key: str,
    visibility: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    status, payload = _request_json(
        server,
        "/v1/memories:record",
        payload={
            "room_id": room_id,
            "agent_id": agent_id,
            "content": content,
            "source_event_id": source_event_id,
            "idempotency_key": idempotency_key,
            "visibility": visibility,
        },
        timeout_seconds=timeout_seconds,
    )
    if status != 201:
        raise RuntimeError(f"record returned HTTP {status}: {payload}")
    return payload


def _prepare(
    server: _LocalRoomServer,
    room_id: str,
    agent_id: str,
    purpose: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    status, payload = _request_json(
        server,
        "/v1/contexts:prepare",
        payload={
            "room_id": room_id,
            "agent_id": agent_id,
            "purpose": purpose,
            "risk": "medium",
        },
        timeout_seconds=timeout_seconds,
    )
    if status != 200:
        raise RuntimeError(f"prepare returned HTTP {status}: {payload}")
    return payload


def _request_json(
    server: _LocalRoomServer,
    path: str,
    *,
    payload: Mapping[str, Any] | None = None,
    token: str | None | object = ...,
    timeout_seconds: float,
) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json"}
    effective_token = server.token if token is ... else token
    if isinstance(effective_token, str):
        headers["authorization"] = f"Bearer {effective_token}"
    request = Request(
        server.base_url + path,
        data=body,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _memory_ids(payload: Mapping[str, Any]) -> set[str]:
    memories = payload.get("memories") if isinstance(payload.get("memories"), list) else []
    return {
        str(memory["id"])
        for memory in memories
        if isinstance(memory, Mapping) and isinstance(memory.get("id"), str)
    }


def _error_code(payload: Mapping[str, Any]) -> str | None:
    error = payload.get("error")
    return str(error.get("code")) if isinstance(error, Mapping) and error.get("code") else None


def _latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "completed_requests": 0,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    ordered = sorted(values)
    return {
        "completed_requests": len(ordered),
        "p50_ms": round(_percentile(ordered, 0.50), 3),
        "p95_ms": round(_percentile(ordered, 0.95), 3),
        "max_ms": round(ordered[-1], 3),
    }


def _percentile(ordered: list[float], quantile: float) -> float:
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]
