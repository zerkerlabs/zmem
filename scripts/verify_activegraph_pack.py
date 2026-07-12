#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.metadata
import json
import tempfile
from decimal import Decimal
from pathlib import Path

from activegraph import Graph, Runtime, clear_registry, llm_behavior, register
from activegraph.llm import LLMResponse
from activegraph.packs import Pack, discover, load_by_name

from zerker_memory.integrations.activegraph import enable_precall_recall
from zerker_memory.pack import ZMemSettings
from zerker_memory.store import MemoryStore


class _CaptureProvider:
    default_model = "zmem-capture-model"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def recognizes_model(self, _name: str) -> bool:
        return True

    def supports_native_structured_output(self, _model: str) -> bool:
        return False

    def count_tokens(self, *, system: str, messages: list[object], model: str) -> int:
        return len(system) + sum(len(str(getattr(message, "content", ""))) for message in messages)

    def estimate_cost(self, *, input_tokens: int, output_tokens: int, model: str) -> Decimal:
        return Decimal("0")

    def complete(self, **kwargs: object) -> LLMResponse:
        self.calls.append(kwargs)
        return LLMResponse(
            raw_text="ok",
            parsed=None,
            input_tokens=1,
            output_tokens=1,
            cost_usd=Decimal("0"),
            latency_seconds=0.0,
            model=str(kwargs["model"]),
            finish_reason="end_turn",
        )


def _verify_precall_recall(db_path: Path) -> tuple[bool, bool]:
    store = MemoryStore(db_path)
    store.remember(
        "The release target is Production.",
        memory_type="semantic",
        scope="ag:zmem_precall_verify",
        source_kind="human",
    )
    store.conn.close()

    previous_registry = clear_registry()
    try:
        @llm_behavior(
            name="zmem_precall_verify",
            on=["object.created"],
            model="zmem-capture-model",
        )
        def answer_question(event: object, graph: object, ctx: object, llm_output: object) -> None:
            return None

        enable_precall_recall(answer_question, db_path=db_path)
        provider = _CaptureProvider()
        graph = Graph(run_id="zmem_precall_verify")
        runtime = Runtime(graph, behaviors=[answer_question], llm_provider=provider)
        graph.add_object("question", {"query": "What is the release target?"})
        runtime.run_until_idle()
    finally:
        clear_registry()
        for registered_behavior in previous_registry:
            register(registered_behavior)

    sent_content = str(provider.calls[0]["messages"][0].content) if len(provider.calls) == 1 else ""
    requested = next((event for event in graph.events if event.type == "llm.requested"), None)
    recorded_content = (
        str(requested.payload["prompt"]["messages"][0]["content"])
        if requested is not None
        else ""
    )
    has_memory = (
        "ZMem recall receipt: act_" in sent_content
        and "The release target is Production." in sent_content
    )
    return has_memory, bool(sent_content) and recorded_content == sent_content


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the installed ZMem ActiveGraph pack")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    discovered = {item.name: item for item in discover()}
    zmem = load_by_name("zmem")
    with tempfile.TemporaryDirectory(prefix="zmem-activegraph-pack-") as tmp:
        db_path = Path(tmp) / "memory.sqlite"
        graph = Graph(run_id="zmem_pack_verify")
        runtime = Runtime(graph)
        first_load = runtime.load_pack(zmem, settings=ZMemSettings(db_path=str(db_path)))
        second_load = runtime.load_pack(zmem, settings=ZMemSettings(db_path=str(db_path)))
        graph.add_object("fact", {"content": "ZMem ActiveGraph pack verification fact."})
        runtime.run_until_idle()
        store = MemoryStore(db_path)
        memories = store.list_memories(scope="ag:zmem_pack_verify")
        store.conn.close()
        precall_context, precall_prompt_recorded = _verify_precall_recall(db_path)

    checks = {
        "discovered": "zmem" in discovered,
        "pack_type": isinstance(zmem, Pack),
        "first_load": first_load is True,
        "idempotent_second_load": second_load is False,
        "persist_behavior": runtime.get_behavior("zmem.persist").name == "zmem.persist",
        "recall_behavior": runtime.get_behavior("zmem.recall").name == "zmem.recall",
        "pack_loaded_event": any(event.type == "pack.loaded" for event in graph.events),
        "persist_runtime_smoke": any(
            memory.content == "ZMem ActiveGraph pack verification fact." for memory in memories
        ),
        "precall_context": precall_context,
        "precall_prompt_recorded": precall_prompt_recorded,
    }
    result = {
        "ok": all(checks.values()),
        "activegraph_version": importlib.metadata.version("activegraph"),
        "zmem_pack_version": zmem.version,
        "entry_point": discovered.get("zmem").entry_point if "zmem" in discovered else None,
        "checks": checks,
    }
    if args.summary_only:
        print(f"ActiveGraph pack verify: {'PASS' if result['ok'] else 'FAIL'}")
        print(f"ActiveGraph: {result['activegraph_version']}")
        print(f"ZMem pack: {result['zmem_pack_version']}")
        failed = [name for name, ok in checks.items() if not ok]
        print(f"Failed checks: {', '.join(failed) if failed else 'none'}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
