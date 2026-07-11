#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.metadata
import json
import tempfile
from pathlib import Path

from activegraph import Graph, Runtime
from activegraph.packs import Pack, discover, load_by_name

from zerker_memory.pack import ZMemSettings
from zerker_memory.store import MemoryStore


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
