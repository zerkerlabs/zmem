from __future__ import annotations

import hmac
import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

from . import __version__
from .rooms import RoomMemoryConflict, RoomMemoryService


SERVICE_ERROR_SCHEMA = "zerker.room_memory_service_error.v1"
MAX_REQUEST_BYTES = 1_048_576
LOGGER = logging.getLogger(__name__)


class RoomMemoryHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        service: RoomMemoryService,
        *,
        bearer_token: str | None = None,
    ):
        self.service = service
        self.bearer_token = bearer_token
        super().__init__(server_address, RoomMemoryHandler)


class RoomMemoryHandler(BaseHTTPRequestHandler):
    server: RoomMemoryHTTPServer

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            self._send_json({"ok": True, "service": "zmem-room-memory"})
            return
        if path == "/readyz":
            readiness = self.server.service.readiness()
            self._send_json(
                readiness,
                status=HTTPStatus.OK if readiness.get("ok") else HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        if path == "/version":
            self._send_json({"service": "zmem-room-memory", "version": __version__})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not_found", "route not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self._authorized():
            self._send_error(HTTPStatus.UNAUTHORIZED, "unauthorized", "valid bearer token required")
            return
        try:
            payload = self._read_json()
            if "tenant_id" in payload:
                raise ValueError("tenant_id is resolved by the service and must not be supplied by the caller")
            if path in {"/v1/contexts:prepare", "/v1/inject"}:
                self._send_json(self.server.service.prepare_context(payload))
                return
            if path == "/v1/memories:propose":
                result = self.server.service.propose_memory(payload)
                self._send_json(result, status=HTTPStatus.OK if result["replayed"] else HTTPStatus.CREATED)
                return
            if path == "/v1/memories:record":
                result = self.server.service.record_memory(payload)
                self._send_json(result, status=HTTPStatus.OK if result["replayed"] else HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "route not found")
        except RoomMemoryConflict as exc:
            self._send_error(HTTPStatus.CONFLICT, "idempotency_conflict", str(exc))
        except RequestTooLarge as exc:
            self._send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request_too_large", str(exc))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))
        except Exception:
            LOGGER.exception("room memory request failed")
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "room memory request failed")

    def _authorized(self) -> bool:
        expected = self.server.bearer_token
        if expected is None:
            return True
        supplied = self.headers.get("authorization") or ""
        prefix = "Bearer "
        if not supplied.startswith(prefix):
            return False
        return hmac.compare_digest(supplied[len(prefix) :], expected)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("content-length")
        if raw_length is None:
            raise ValueError("content-length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("content-length must be an integer") from exc
        if length < 0:
            raise ValueError("content-length cannot be negative")
        if length > MAX_REQUEST_BYTES:
            raise RequestTooLarge(f"request body exceeds {MAX_REQUEST_BYTES} bytes")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def _send_json(self, value: Mapping[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.send_header("x-content-type-options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json(
            {
                "schema": SERVICE_ERROR_SCHEMA,
                "ok": False,
                "error": {"code": code, "message": message},
            },
            status=status,
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


class RequestTooLarge(ValueError):
    pass


def host_is_loopback(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "::1", "localhost"}


def serve_room_memory(
    service: RoomMemoryService,
    *,
    host: str,
    port: int,
    bearer_token: str | None,
    allow_remote: bool = False,
) -> None:
    if not host_is_loopback(host):
        if not allow_remote:
            raise ValueError("non-loopback binding requires --allow-remote")
        if not bearer_token:
            raise ValueError("non-loopback binding requires ZMEM_SERVICE_TOKEN")
    server = RoomMemoryHTTPServer((host, port), service, bearer_token=bearer_token)
    print(f"ZMem Room Memory API running at http://{host}:{server.server_port}")
    print(f"Tenant: {service.resolver.tenant_id}")
    print(f"Authentication: {'bearer token' if bearer_token else 'loopback only'}")
    retrieval = service.readiness()["retrieval"]
    print(f"Retrieval: {retrieval['mode']} ({retrieval['state']})")
    if retrieval.get("next_command"):
        print(f"Next: {retrieval['next_command']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nZMem Room Memory API stopped.")
    finally:
        server.server_close()
