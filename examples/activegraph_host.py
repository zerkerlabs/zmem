#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from zerker_memory.integrations.activegraph import enable_precall_recall
from zerker_memory.store import MemoryStore, sha256_text


DEFAULT_FACT = "The release target is Production."
DEFAULT_QUERY = "What is the release target?"


class DemoProvider:
    default_model = "zmem-activegraph-demo"

    def __init__(self, expected_fact: str) -> None:
        self.expected_fact = expected_fact
        self.calls: list[dict[str, Any]] = []
        self.answer = "I don't know."

    def recognizes_model(self, _name: str) -> bool:
        return True

    def supports_native_structured_output(self, _model: str) -> bool:
        return False

    def count_tokens(self, *, system: str, messages: list[Any], model: str) -> int:
        return len(system) + sum(len(str(getattr(message, "content", ""))) for message in messages)

    def estimate_cost(self, *, input_tokens: int, output_tokens: int, model: str) -> Decimal:
        return Decimal("0")

    def complete(self, **kwargs: Any) -> Any:
        from activegraph.llm import LLMResponse

        self.calls.append(kwargs)
        prompt = _user_message_content(list(kwargs.get("messages", [])))
        self.answer = self.expected_fact if self.expected_fact in prompt else "I don't know."
        return LLMResponse(
            raw_text=self.answer,
            parsed=None,
            input_tokens=1,
            output_tokens=1,
            cost_usd=Decimal("0"),
            latency_seconds=0.0,
            model=str(kwargs["model"]),
            finish_reason="end_turn",
        )


def run_demo(
    *,
    db_path: Path,
    session_id: str,
    fact: str = DEFAULT_FACT,
    query: str = DEFAULT_QUERY,
    retrieval_mode: str = "fts",
) -> dict[str, Any]:
    try:
        from activegraph import Graph, Runtime, clear_registry, llm_behavior, register
        from activegraph.packs import load_by_name
        from zerker_memory.pack import ZMemSettings
    except ModuleNotFoundError as exc:
        raise RuntimeError("ActiveGraph is not installed. Run: python -m pip install -e '.[activegraph]'") from exc

    db_path = db_path.expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    scope = f"ag:{session_id}"
    write_run_id = session_id
    read_run_id = f"{session_id}-resume"
    existing_store = MemoryStore(db_path)
    try:
        existing_memory_ids = {
            memory.id
            for memory in existing_store.list_memories(scope=scope, limit=10_000)
        }
    finally:
        existing_store.conn.close()
    previous_registry = clear_registry()
    try:
        zmem_pack = load_by_name("zmem")
        write_graph = Graph(run_id=write_run_id)
        write_runtime = Runtime(write_graph)
        pack_loaded = write_runtime.load_pack(
            zmem_pack,
            settings=ZMemSettings(db_path=str(db_path), retrieval_mode=retrieval_mode),
        )
        write_graph.add_object("project_fact", {"content": fact})
        write_runtime.run_until_idle()

        clear_registry()

        @llm_behavior(
            name="zmem_activegraph_host_answer",
            on=["object.created"],
            model=DemoProvider.default_model,
        )
        def answer_question(event: Any, graph: Any, ctx: Any, llm_output: Any) -> None:
            return None

        enable_precall_recall(
            answer_question,
            db_path=db_path,
            retrieval_mode=retrieval_mode,
            scope=scope,
        )
        provider = DemoProvider(fact)
        read_graph = Graph(run_id=read_run_id)
        read_runtime = Runtime(
            read_graph,
            behaviors=[answer_question],
            llm_provider=provider,
        )
        read_graph.add_object("question", {"query": query})
        read_runtime.run_until_idle()
    finally:
        clear_registry()
        for registered_behavior in previous_registry:
            register(registered_behavior)

    write_event_ids = {str(event.id) for event in write_graph.events}
    store = MemoryStore(db_path)
    try:
        persisted = None
        write_receipt = None
        for memory in store.list_memories(scope=scope, limit=10_000):
            if memory.id in existing_memory_ids or memory.content != fact:
                continue
            candidate_receipt = store.memory_write_receipt(memory.id)
            source_event_id = str(
                candidate_receipt["treeship_statement"]["object"].get("caused_by_event") or ""
            )
            if source_event_id in write_event_ids:
                persisted = memory
                write_receipt = candidate_receipt
                break
    finally:
        store.conn.close()

    sent_prompt = _user_message_content(list(provider.calls[0].get("messages", []))) if provider.calls else ""
    requested = next((event for event in read_graph.events if event.type == "llm.requested"), None)
    recorded_messages = (
        list(requested.payload.get("prompt", {}).get("messages", []))
        if requested is not None
        else []
    )
    recorded_prompt = _user_message_content(recorded_messages)
    receipt_match = re.search(r"ZMem recall receipt: (act_[A-Za-z0-9]+)", sent_prompt)
    source_event_id = (
        str(write_receipt["treeship_statement"]["object"].get("caused_by_event") or "")
        if write_receipt is not None
        else ""
    )
    checks = {
        "pack_loaded": bool(pack_loaded),
        "memory_persisted": persisted is not None,
        "causal_pointer_preserved": bool(source_event_id) and source_event_id in write_event_ids,
        "provider_called_once": len(provider.calls) == 1,
        "memory_recalled_before_call": fact in sent_prompt,
        "recall_receipt_attached": receipt_match is not None,
        "recorded_prompt_matches_provider": bool(sent_prompt) and recorded_prompt == sent_prompt,
        "answer_used_recalled_memory": provider.answer == fact,
    }
    return {
        "schema": "zerker.activegraph_host_example.v1",
        "ok": all(checks.values()),
        "db": str(db_path),
        "scope": scope,
        "write_run_id": write_run_id,
        "read_run_id": read_run_id,
        "pack_version": zmem_pack.version,
        "persisted_memory_id": persisted.id if persisted is not None else None,
        "source_event_id": source_event_id or None,
        "recall_receipt_id": receipt_match.group(1) if receipt_match is not None else None,
        "answer": provider.answer,
        "sent_prompt_sha256": sha256_text(sent_prompt) if sent_prompt else None,
        "recorded_prompt_sha256": sha256_text(recorded_prompt) if recorded_prompt else None,
        "checks": checks,
    }


def _user_message_content(messages: list[Any]) -> str:
    for message in messages:
        if isinstance(message, Mapping):
            role = str(message.get("role", ""))
            content = message.get("content", "")
        else:
            role = str(getattr(message, "role", ""))
            content = getattr(message, "content", "")
        if role == "user":
            return str(content)
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a two-run ZMem + ActiveGraph memory host example")
    parser.add_argument("--db", type=Path, default=Path(".zerker/activegraph-host/memory.sqlite"))
    parser.add_argument("--session", default="zmem-activegraph-host")
    parser.add_argument("--retrieval-mode", choices=("fts", "semantic", "hybrid"), default="fts")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    try:
        result = run_demo(
            db_path=args.db,
            session_id=args.session,
            retrieval_mode=args.retrieval_mode,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.summary_only:
        print(f"ActiveGraph host example: {'PASS' if result['ok'] else 'FAIL'}")
        print(f"Runs: {result['write_run_id']} -> {result['read_run_id']}")
        print(f"Memory: {result['persisted_memory_id'] or 'missing'}")
        print(f"Recall receipt: {result['recall_receipt_id'] or 'missing'}")
        print(f"Recorded prompt matches provider: {'yes' if result['checks']['recorded_prompt_matches_provider'] else 'no'}")
        print(f"Answer: {result['answer']}")
        failed = [name for name, ok in result["checks"].items() if not ok]
        print(f"Failed checks: {', '.join(failed) if failed else 'none'}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
