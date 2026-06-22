#!/usr/bin/env python3
"""LongMemEval official adapter: longmemeval_*.json -> ZMem bench records.

The official file is one record per question. Each instance carries `haystack_sessions`
(list of sessions; each a list of `{role, content, has_answer}` turns). The ZMem
benchmark harness expects one record per question with fields: question_id, split,
category, history, question, answer, supporting_facts, should_abstain.

This adapter flattens haystack turns into `history`, marks the `has_answer: true` turns
as `supporting_facts` (rendered with the same builder so the harness maps them to
history indexes by exact content match), and sets `should_abstain` for `_abs` ids.

Session dates are folded into turn content so temporal-reasoning questions retain the
timestamp signal the official haystack provides.

Usage:
  python3 scripts/bench/longmemeval_to_zmem.py \
    --in data/longmemeval/longmemeval_oracle.json \
    --out data/longmemeval/longmemeval_oracle_zmem.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _turn_content(role: str, content: str, date: str | None) -> str:
    when = f" ({date})" if date else ""
    return f"{role}{when}: {content}".strip()


def convert(instances: list[dict]) -> list[dict]:
    records: list[dict] = []
    for inst in instances:
        qid = str(inst["question_id"])
        sessions = inst.get("haystack_sessions", []) or []
        dates = inst.get("haystack_dates", []) or []
        history: list[str] = []
        supporting_facts: list[str] = []
        for s_idx, session in enumerate(sessions):
            date = dates[s_idx] if s_idx < len(dates) else None
            for turn in session:
                if not isinstance(turn, dict):
                    continue
                content = _turn_content(str(turn.get("role", "")), str(turn.get("content", "")), date)
                history.append(content)
                if turn.get("has_answer"):
                    supporting_facts.append(content)
        records.append(
            {
                "question_id": qid,
                "split": "default",
                "category": str(inst.get("question_type", "unknown")),
                "history": history,
                "question": str(inst.get("question", "")),
                "answer": str(inst.get("answer", "")),
                "supporting_facts": supporting_facts,
                "should_abstain": qid.endswith("_abs"),
                "answer_session_ids": inst.get("answer_session_ids", []),
            }
        )
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    args = ap.parse_args()

    instances = json.loads(args.inp.read_text(encoding="utf-8"))
    if not isinstance(instances, list):
        raise SystemExit("expected longmemeval json to be a JSON array of instances")
    records = convert(instances)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    abstain = sum(1 for r in records if r["should_abstain"])
    matched = sum(1 for r in records if r["supporting_facts"])
    print(
        f"wrote {len(records)} question records -> {args.out}\n"
        f"  abstention(_abs): {abstain} | with has_answer evidence: {matched}"
    )


if __name__ == "__main__":
    main()
