from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .paths import expand_user_path
from .providers import SUPPORTED_PROVIDERS, build_provider_adapter, provider_import_settings
from .store import MemoryStore, default_db_path, default_policy_path


JSON = dict[str, Any]


MCP_PROFILES = ("agent", "operator")
AGENT_TOOL_NAMES = frozenset(
    {
        "memory.propose",
        "memory.inject",
        "memory.why",
        "memory.verify",
    }
)
PROPOSAL_SOURCE_KINDS = frozenset({"agent", "tool", "document", "import"})


TOOL_SCHEMAS: list[JSON] = [
    {
        "name": "memory.remember",
        "description": "Store an active memory, usually from a trusted human or system source.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "type": {"type": "string", "enum": ["episodic", "semantic", "procedural", "policy"], "default": "semantic"},
                "scope": {"type": "string", "default": "global"},
                "source": {"type": "string", "enum": ["human", "system", "tool", "document", "agent", "import"], "default": "human"},
                "labels": {"type": "array", "items": {"type": "string"}, "default": []},
                "source_uri": {"type": "string"},
                "actor_uri": {"type": "string"},
                "session_id": {"type": "string"},
                "parent_action_id": {"type": "string"},
                "environment_hash": {"type": "string"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory.propose",
        "description": "Propose a memory. Agent/tool/document memories are quarantined by default.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "type": {"type": "string", "enum": ["episodic", "semantic", "procedural", "policy"], "default": "semantic"},
                "scope": {"type": "string", "default": "global"},
                "source": {"type": "string", "enum": sorted(PROPOSAL_SOURCE_KINDS), "default": "agent"},
                "labels": {"type": "array", "items": {"type": "string"}, "default": []},
                "source_uri": {"type": "string"},
                "actor_uri": {"type": "string"},
                "session_id": {"type": "string"},
                "parent_action_id": {"type": "string"},
                "environment_hash": {"type": "string"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory.search",
        "description": "Search local memories. Active memories are returned by default.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "scope": {"type": "string"},
                "include_quarantined": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory.inject",
        "description": "Retrieve authorized memories for an agent action and create an action receipt with memory Merkle proofs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "agent": {"type": "string"},
                "risk": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
                "scope": {"type": "string"},
            },
            "required": ["task", "agent"],
        },
    },
    {
        "name": "memory.inspect",
        "description": "Inspect a memory by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory.queue",
        "description": "List proposed or quarantined memories waiting for review.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string"},
                "status": {"type": "string", "enum": ["proposed", "quarantined"]},
            },
        },
    },
    {
        "name": "memory.promote",
        "description": "Promote a quarantined/proposed memory to active.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory.reject",
        "description": "Reject a proposed or quarantined memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory.lineage",
        "description": "Show parents and descendants for a memory.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory.revoke",
        "description": "Revoke a memory and all derived descendants.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory.forget",
        "description": "Mark a memory forgotten.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "memory.why",
        "description": "Explain which memories were retrieved, injected, or withheld for an action, including memory Merkle proof roots.",
        "inputSchema": {
            "type": "object",
            "properties": {"action_id": {"type": "string"}},
            "required": ["action_id"],
        },
    },
    {
        "name": "memory.verify",
        "description": "Verify a memory action receipt against local event and memory Merkle state.",
        "inputSchema": {
            "type": "object",
            "properties": {"action_id": {"type": "string"}},
            "required": ["action_id"],
        },
    },
    {
        "name": "memory.external_search",
        "description": "Search an external memory provider and return normalized candidates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "enum": list(SUPPORTED_PROVIDERS), "default": "mem0"},
                "query": {"type": "string"},
                "user_id": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
                "mem0_base_url": {"type": "string"},
                "mem0_api_key": {"type": "string"},
                "zep_base_url": {"type": "string"},
                "zep_api_key": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory.external_import",
        "description": "Search an external memory provider and import candidates into Zerker quarantine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "enum": list(SUPPORTED_PROVIDERS), "default": "mem0"},
                "query": {"type": "string"},
                "scope": {"type": "string", "default": "global"},
                "type": {"type": "string", "enum": ["episodic", "semantic", "procedural", "policy"], "default": "semantic"},
                "user_id": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
                "mem0_base_url": {"type": "string"},
                "mem0_api_key": {"type": "string"},
                "zep_base_url": {"type": "string"},
                "zep_api_key": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory.snapshot",
        "description": "Export the full local memory state, receipts, and Merkle event chain as a hashed artifact.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "out": {"type": "string"},
                "out_dir": {"type": "string"},
            },
        },
    },
    {
        "name": "memory.restore",
        "description": "Restore a snapshot file into an empty local memory store.",
        "inputSchema": {
            "type": "object",
            "properties": {"snapshot_path": {"type": "string"}},
            "required": ["snapshot_path"],
        },
    },
]


class McpServer:
    def __init__(self, store: MemoryStore, *, profile: str = "agent"):
        if profile not in MCP_PROFILES:
            raise ValueError(f"unknown MCP profile: {profile}")
        self.store = store
        self.profile = profile
        self.allowed_tools = (
            AGENT_TOOL_NAMES if profile == "agent" else frozenset(tool["name"] for tool in TOOL_SCHEMAS)
        )
        self.store.init()

    def handle(self, request: JSON) -> JSON | None:
        method = request.get("method")
        request_id = request.get("id")
        try:
            if method == "initialize":
                return self._result(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "zerker-memory", "version": __version__},
                    },
                )
            if method == "notifications/initialized":
                return None
            if method == "tools/list":
                return self._result(
                    request_id,
                    {"tools": [tool for tool in TOOL_SCHEMAS if tool["name"] in self.allowed_tools]},
                )
            if method == "tools/call":
                params = request.get("params") or {}
                name = params.get("name")
                args = params.get("arguments") or {}
                return self._result(request_id, self._tool_result(self.call_tool(name, args)))
            return self._error(request_id, -32601, f"method not found: {method}")
        except Exception as exc:  # MCP should keep running after tool errors.
            return self._error(request_id, -32000, str(exc))

    def call_tool(self, name: str, args: JSON) -> Any:
        handlers: dict[str, Callable[[JSON], Any]] = {
            "memory.remember": self._remember,
            "memory.propose": self._propose,
            "memory.search": self._search,
            "memory.inject": self._inject,
            "memory.inspect": self._inspect,
            "memory.queue": self._queue,
            "memory.promote": self._promote,
            "memory.reject": self._reject,
            "memory.lineage": self._lineage,
            "memory.revoke": self._revoke,
            "memory.forget": self._forget,
            "memory.why": self._why,
            "memory.verify": self._verify,
            "memory.external_search": self._external_search,
            "memory.external_import": self._external_import,
            "memory.snapshot": self._snapshot,
            "memory.restore": self._restore,
        }
        if name not in handlers:
            raise ValueError(f"unknown tool: {name}")
        if name not in self.allowed_tools:
            raise PermissionError(
                f"MCP tool {name} is unavailable in profile={self.profile}; "
                "agents should use memory.propose or memory.inject, while trusted local review "
                "requires --profile operator"
            )
        return handlers[name](args)

    def _remember(self, args: JSON) -> JSON:
        record = self.store.remember(
            required_str(args, "content"),
            memory_type=args.get("type", "semantic"),
            scope=args.get("scope", "global"),
            source_kind=args.get("source", "human"),
            labels=args.get("labels", []),
            status="active" if args.get("source", "human") in {"human", "system"} else None,
            source_uri=args.get("source_uri"),
            actor_uri=args.get("actor_uri"),
            session_id=args.get("session_id"),
            parent_action_id=args.get("parent_action_id"),
            environment_hash=args.get("environment_hash"),
        )
        return record.to_dict()

    def _propose(self, args: JSON) -> JSON:
        source_kind = "agent" if self.profile == "agent" else args.get("source", "agent")
        if source_kind not in PROPOSAL_SOURCE_KINDS:
            allowed = ", ".join(sorted(PROPOSAL_SOURCE_KINDS))
            raise ValueError(f"memory.propose source must be one of: {allowed}")
        record = self.store.remember(
            required_str(args, "content"),
            memory_type=args.get("type", "semantic"),
            scope=args.get("scope", "global"),
            source_kind=source_kind,
            labels=args.get("labels", []),
            source_uri=args.get("source_uri"),
            actor_uri=args.get("actor_uri"),
            session_id=args.get("session_id"),
            parent_action_id=args.get("parent_action_id"),
            environment_hash=args.get("environment_hash"),
        )
        return record.to_dict()

    def _search(self, args: JSON) -> list[JSON]:
        return [
            memory.to_dict()
            for memory in self.store.search(
                required_str(args, "query"),
                scope=args.get("scope"),
                include_quarantined=optional_bool(args, "include_quarantined"),
            )
        ]

    def _inject(self, args: JSON) -> JSON:
        return self.store.inject(
            required_str(args, "task"),
            agent_id=required_str(args, "agent"),
            risk=args.get("risk", "medium"),
            scope=args.get("scope"),
        )

    def _inspect(self, args: JSON) -> JSON:
        return self.store.get(required_str(args, "memory_id")).to_dict()

    def _queue(self, args: JSON) -> list[JSON]:
        return [memory.to_dict() for memory in self.store.queue(scope=args.get("scope"), status=args.get("status"))]

    def _promote(self, args: JSON) -> JSON:
        return self.store.promote(required_str(args, "memory_id")).to_dict()

    def _reject(self, args: JSON) -> JSON:
        return self.store.reject(required_str(args, "memory_id"), reason=args.get("reason")).to_dict()

    def _lineage(self, args: JSON) -> JSON:
        return self.store.lineage(required_str(args, "memory_id"))

    def _revoke(self, args: JSON) -> JSON:
        return self.store.revoke(required_str(args, "memory_id"), reason=args.get("reason"))

    def _forget(self, args: JSON) -> JSON:
        memory_id = required_str(args, "memory_id")
        self.store.forget(memory_id)
        return {"ok": True, "memory_id": memory_id}

    def _why(self, args: JSON) -> JSON:
        return self.store.why(required_str(args, "action_id"))

    def _verify(self, args: JSON) -> JSON:
        action_id = required_str(args, "action_id")
        return {"ok": self.store.verify(action_id), "action_id": action_id}

    def _external_search(self, args: JSON) -> list[JSON]:
        adapter = build_adapter(args)
        return [
            candidate.to_dict()
            for candidate in adapter.search(
                required_str(args, "query"),
                user_id=args.get("user_id"),
                limit=int(args.get("limit", 10)),
            )
        ]

    def _external_import(self, args: JSON) -> list[JSON]:
        adapter = build_adapter(args)
        provider = args.get("provider", "mem0")
        governance = provider_import_settings(
            provider,
            memory_type=args.get("type", "semantic"),
            scope=args.get("scope", "global"),
        )
        return [
            self.store.import_external(
                candidate,
                memory_type=args.get("type", "semantic"),
                scope=args.get("scope", "global"),
                trust=governance["trust"],
                authority=governance["authority"],
                status=governance["status"],
                labels=governance["labels"],
            ).to_dict()
            for candidate in adapter.search(
                required_str(args, "query"),
                user_id=args.get("user_id"),
                limit=int(args.get("limit", 10)),
            )
        ]

    def _snapshot(self, args: JSON) -> JSON:
        from .exporter import export_snapshot

        out = expand_user_path(args["out"]) if args.get("out") else None
        out_dir = expand_user_path(args["out_dir"]) if args.get("out_dir") else None
        return export_snapshot(self.store.snapshot(), out=out, out_dir=out_dir)

    def _restore(self, args: JSON) -> JSON:
        snapshot_path = expand_user_path(required_str(args, "snapshot_path"))
        return self.store.restore_snapshot(json.loads(snapshot_path.read_text(encoding="utf-8")))

    @staticmethod
    def _tool_result(value: Any) -> JSON:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(value, indent=2, sort_keys=True),
                }
            ]
        }

    @staticmethod
    def _result(request_id: Any, result: Any) -> JSON:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> JSON:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def required_str(args: JSON, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string argument: {key}")
    return value


def optional_bool(args: JSON, key: str, *, default: bool = False) -> bool:
    value = args.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def build_adapter(args: JSON):
    provider = args.get("provider", "mem0")
    base_url = args.get(f"{provider}_base_url")
    api_key = args.get(f"{provider}_api_key")
    return build_provider_adapter(provider, base_url=base_url, api_key=api_key)


def run_stdio(server: McpServer) -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = server.handle(json.loads(line))
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Zerker Memory MCP server over stdio")
    parser.add_argument("--db", type=expand_user_path, default=default_db_path(), help="SQLite database path")
    parser.add_argument("--policy", type=expand_user_path, default=default_policy_path(), help="Policy config JSON path")
    parser.add_argument(
        "--profile",
        choices=MCP_PROFILES,
        default=os.environ.get("ZMEM_MCP_PROFILE", "agent"),
        help="Capability profile (default: agent)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_stdio(McpServer(MemoryStore(args.db, policy_path=args.policy), profile=args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
