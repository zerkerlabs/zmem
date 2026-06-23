from __future__ import annotations

import argparse
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from zerker_memory.bench import (
    LOCAL_ABSTAIN_ANSWER,
    _load_local_dataset_records,
    _normalize_locomo_record,
    _now_iso,
    _token_f1,
    resolve_benchmark_retrieval_config,
)
from zerker_memory.store import MemoryStore, merkle_root, sha256_text, stable_json


TRACE_SCHEMA = "zerker.activegraph_bench_trace.v1"
SCORED_RECEIPT_SCHEMA = "zerker.activegraph_bench_scored_receipt.v1"


class ActiveGraphEventLog:
    def __init__(self, path: Path, *, run_id: str):
        self.path = path
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              id TEXT UNIQUE NOT NULL,
              run_id TEXT NOT NULL,
              behavior TEXT NOT NULL,
              object_type TEXT NOT NULL,
              object_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              parent_event_id TEXT,
              event_hash TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def append(
        self,
        behavior: str,
        object_type: str,
        object_id: str,
        payload: dict[str, Any],
        *,
        parent_event_id: str | None = None,
    ) -> dict[str, Any]:
        event_id = "ag_evt_" + uuid.uuid4().hex[:16]
        created_at = _now_iso()
        event_without_hash = {
            "id": event_id,
            "run_id": self.run_id,
            "behavior": behavior,
            "object_type": object_type,
            "object_id": object_id,
            "payload": payload,
            "parent_event_id": parent_event_id,
            "created_at": created_at,
        }
        event_hash = sha256_text(stable_json(event_without_hash))
        self.conn.execute(
            """
            INSERT INTO events (
              id, run_id, behavior, object_type, object_id, payload_json,
              parent_event_id, event_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                self.run_id,
                behavior,
                object_type,
                object_id,
                stable_json(payload),
                parent_event_id,
                event_hash,
                created_at,
            ),
        )
        self.conn.commit()
        return {**event_without_hash, "event_hash": event_hash}

    def close(self) -> None:
        self.conn.close()


def run_locomo_activegraph_benchmark(
    dataset: Path,
    *,
    run_id: str,
    out: Path,
    retrieval_mode: str = "fts",
    split: str | None = None,
    treeship: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    run_dir = out / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(run_dir / "memory.sqlite")
    event_log = ActiveGraphEventLog(run_dir / "activegraph.sqlite", run_id=run_id)
    trace_path = run_dir / "trace.jsonl"
    records = _load_local_dataset_records(dataset, "locomo")
    normalized = [_normalize_locomo_record(record, index) for index, record in enumerate(records)]
    if split:
        normalized = [record for record in normalized if record["split"] == split]
    if limit is not None:
        normalized = normalized[: max(0, int(limit))]

    line_hashes: list[str] = []
    lines: list[dict[str, Any]] = []
    try:
        with trace_path.open("w", encoding="utf-8") as trace_file:
            for question in normalized:
                question_event = question_started(event_log, store, question)
                retrieval_event = memory_retrieved(
                    event_log,
                    store,
                    question_event,
                    question,
                    retrieval_mode=retrieval_mode,
                    treeship=treeship,
                )
                answer_event = answer_generated(event_log, retrieval_event, question)
                line = question_completed(event_log, answer_event, question, retrieval_mode=retrieval_mode)
                trace_file.write(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n")
                line_hashes.append(line["line_hash"])
                lines.append(line)
    finally:
        event_log.close()

    scored_receipt = score_trace(trace_path)
    return {
        "ok": True,
        "schema": "zerker.activegraph_bench_run.v1",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "memory_db": str(run_dir / "memory.sqlite"),
        "activegraph_db": str(run_dir / "activegraph.sqlite"),
        "trace_path": str(trace_path),
        "scored_receipt_path": str(run_dir / "scored_receipt.json"),
        "question_count": len(lines),
        "line_hashes": line_hashes,
        "scored_receipt": scored_receipt,
    }


def question_started(event_log: ActiveGraphEventLog, store: MemoryStore, question: dict[str, Any]) -> dict[str, Any]:
    event = event_log.append(
        "zmem.bench.question_started",
        "zmem_bench_question",
        question["question_id"],
        {
            "question_id": question["question_id"],
            "category": question["category"],
            "query": question["query"],
        },
    )
    scope = f"bench:{question['question_id']}"
    for index, memory in enumerate(question["history_memories"]):
        store.remember(
            memory["content"],
            memory_type="episodic",
            scope=scope,
            source_kind="human",
            actor_id="activegraph-bench",
            labels=["benchmark", "locomo", question["category"]],
            source_uri=f"activegraph://event/{event['id']}#history-{index}",
            session_id=f"activegraph://run/{event_log.run_id}",
            caused_by_event=event["id"],
        )
    return event


def memory_retrieved(
    event_log: ActiveGraphEventLog,
    store: MemoryStore,
    parent_event: dict[str, Any],
    question: dict[str, Any],
    *,
    retrieval_mode: str,
    treeship: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    receipt = store.inject(
        question["query"],
        agent_id="activegraph-bench",
        risk="low",
        scope=f"bench:{question['question_id']}",
        retrieval_config=resolve_benchmark_retrieval_config(_mode_for_store(retrieval_mode)),
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    payload = {
        "question_id": question["question_id"],
        "retrieval_mode": retrieval_mode,
        "retrieval_latency_ms": latency_ms,
        "receipt": receipt,
        "treeship_requested": treeship,
    }
    return event_log.append(
        "zmem.bench.memory_retrieved",
        "zmem_retrieval",
        receipt["action_id"],
        payload,
        parent_event_id=parent_event["id"],
    )


def answer_generated(event_log: ActiveGraphEventLog, retrieval_event: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    receipt = retrieval_event["payload"]["receipt"]
    memories = receipt.get("memories", [])
    if question["should_abstain"] or not memories:
        answer = LOCAL_ABSTAIN_ANSWER
    else:
        answer = str(memories[0].get("content", ""))
    f1 = _token_f1(answer, question["expected_answer"])
    exact_match = float(answer.strip().lower() == question["expected_answer"].strip().lower())
    correct = bool(exact_match == 1.0)
    return event_log.append(
        "zmem.bench.answer_generated",
        "zmem_bench_answer_ready",
        question["question_id"],
        {
            "question_id": question["question_id"],
            "final_answer": answer,
            "reference": question["expected_answer"],
            "f1": f1,
            "exact_match": exact_match,
            "correct": correct,
            "retrieval_event_id": retrieval_event["id"],
            "receipt_id": receipt["action_id"],
            "retrieved_count": len(receipt.get("retrieved_memory_ids", [])),
            "retrieval_latency_ms": retrieval_event["payload"]["retrieval_latency_ms"],
        },
        parent_event_id=retrieval_event["id"],
    )


def question_completed(
    event_log: ActiveGraphEventLog,
    answer_event: dict[str, Any],
    question: dict[str, Any],
    *,
    retrieval_mode: str,
) -> dict[str, Any]:
    payload = answer_event["payload"]
    trace_base = {
        "schema": TRACE_SCHEMA,
        "question_id": question["question_id"],
        "category": question["category"],
        "correct": payload["correct"],
        "f1": payload["f1"],
        "exact_match": payload["exact_match"],
        "final_answer": payload["final_answer"],
        "reference": payload["reference"],
        "retrieved_count": payload["retrieved_count"],
        "retrieval_latency_ms": payload["retrieval_latency_ms"],
        "retrieval_mode": retrieval_mode,
        "receipt_id": payload["receipt_id"],
        "trace_sha256": sha256_text(stable_json(payload)),
        "ag_event_id": answer_event["id"],
        "ag_run_id": event_log.run_id,
    }
    line_hash = sha256_text(stable_json(trace_base))
    line = {**trace_base, "line_hash": line_hash}
    event_log.append(
        "zmem.bench.question_completed",
        "zmem_bench_scored",
        question["question_id"],
        line,
        parent_event_id=answer_event["id"],
    )
    return line


def score_trace(trace_path: Path) -> dict[str, Any]:
    lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    line_hashes = [str(line["line_hash"]) for line in lines]
    per_category: dict[str, dict[str, Any]] = {}
    for line in lines:
        category = str(line["category"])
        bucket = per_category.setdefault(category, {"count": 0, "correct": 0, "f1_sum": 0.0})
        bucket["count"] += 1
        bucket["correct"] += int(bool(line["correct"]))
        bucket["f1_sum"] += float(line["f1"])
    category_scores = {
        category: {
            "count": bucket["count"],
            "accuracy": bucket["correct"] / bucket["count"] if bucket["count"] else 0.0,
            "mean_f1": bucket["f1_sum"] / bucket["count"] if bucket["count"] else 0.0,
        }
        for category, bucket in sorted(per_category.items())
    }
    count = len(lines)
    correct = sum(int(bool(line["correct"])) for line in lines)
    f1_sum = sum(float(line["f1"]) for line in lines)
    receipt = {
        "schema": SCORED_RECEIPT_SCHEMA,
        "question_count": count,
        "overall_accuracy": correct / count if count else 0.0,
        "mean_f1": f1_sum / count if count else 0.0,
        "per_category": category_scores,
        "aggregate_merkle_root": merkle_root(line_hashes),
        "trace_sha256": sha256_text(trace_path.read_text(encoding="utf-8")),
        "line_hashes": line_hashes,
        "reproducibility_claim": "Re-run zmem-bench-locomo with the same dataset, run id, split, and retrieval mode; verify trace line_hashes and aggregate_merkle_root.",
        "public_benchmark_claim": False,
        "created_at": _now_iso(),
    }
    (trace_path.parent / "scored_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def _mode_for_store(mode: str) -> str:
    return {
        "semantic": "pseudo-embedding",
        "hybrid": "pseudo-embedding-rerank",
    }.get(mode, mode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run compact ActiveGraph-backed LoCoMo benchmark traces")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--retrieval-mode", default="fts")
    parser.add_argument("--split")
    parser.add_argument("--treeship", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    result = run_locomo_activegraph_benchmark(
        args.dataset,
        run_id=args.run_id,
        out=args.out,
        retrieval_mode=args.retrieval_mode,
        split=args.split,
        treeship=args.treeship,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
