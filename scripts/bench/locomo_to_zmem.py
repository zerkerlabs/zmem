#!/usr/bin/env python3
"""LoCoMo official adapter: snap-research/locomo `locomo10.json` -> ZMem bench records.

The official file is one record per *conversation* with a nested `qa` list. The ZMem
benchmark harness (`zmem bench matrix locomo`) expects one record per *question* with
fields: question_id, split, category, history, question, answer, supporting_facts,
should_abstain.

This adapter explodes each conversation x each qa into a flat per-question record.
Crucially, both `history` turns and `supporting_facts` are rendered with the *same*
builder (dia_id embedded), so the harness can map evidence dia_ids -> history indexes
by exact content match and compute honest recall@k.

Category mapping (snap-research LoCoMo):
  1 -> multi_hop, 2 -> temporal_reasoning, 3 -> open_domain,
  4 -> single_hop, 5 -> adversarial (abstention; uses `adversarial_answer`).

Usage:
  python3 scripts/bench/locomo_to_zmem.py \
    --in data/locomo-repo/data/locomo10.json \
    --out data/locomo/locomo_official_zmem.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CATEGORY_LABELS = {
    1: "multi_hop",
    2: "temporal_reasoning",
    3: "open_domain",
    4: "single_hop",
    5: "adversarial",
}


def _turn_content(dia_id: str, speaker: str, text: str, date: str | None) -> str:
    """Single source of truth for turn rendering (history AND evidence use this)."""
    when = f" ({date})" if date else ""
    return f"[{dia_id}]{when} {speaker}: {text}".strip()


def _build_conversation(conv: dict) -> tuple[list[str], dict[str, str]]:
    """Return (chronological history strings, dia_id -> content map)."""
    history: list[str] = []
    dia_map: dict[str, str] = {}
    session_keys = sorted(
        (k for k in conv if k.startswith("session_") and k.split("_")[1].isdigit()),
        key=lambda k: int(k.split("_")[1]),
    )
    for skey in session_keys:
        date = conv.get(f"{skey}_date_time")
        for turn in conv[skey]:
            if not isinstance(turn, dict):
                continue
            dia_id = str(turn.get("dia_id", ""))
            speaker = str(turn.get("speaker", ""))
            # multimodal turns carry blip_caption; fold it into text for retrieval.
            text = str(turn.get("text", "") or turn.get("blip_caption", ""))
            content = _turn_content(dia_id, speaker, text, date)
            history.append(content)
            if dia_id:
                dia_map[dia_id] = content
    return history, dia_map


def convert(samples: list[dict]) -> list[dict]:
    records: list[dict] = []
    for sample in samples:
        sample_id = str(sample.get("sample_id", "conv"))
        history, dia_map = _build_conversation(sample.get("conversation", {}))
        for i, qa in enumerate(sample.get("qa", [])):
            category = int(qa.get("category", 0))
            should_abstain = category == 5
            answer = qa.get("answer", qa.get("adversarial_answer", ""))
            evidence = qa.get("evidence", []) or []
            if not isinstance(evidence, list):
                evidence = [evidence]
            supporting_facts = [dia_map[e] for e in (str(x) for x in evidence) if e in dia_map]
            records.append(
                {
                    "question_id": f"{sample_id}#{i}",
                    "split": "default",
                    "category": CATEGORY_LABELS.get(category, f"category_{category}"),
                    "locomo_category_int": category,
                    "locomo_evidence_dia_ids": [str(x) for x in evidence],
                    "history": history,
                    "question": str(qa.get("question", "")),
                    "answer": str(answer),
                    "supporting_facts": supporting_facts,
                    "should_abstain": should_abstain,
                }
            )
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    args = ap.parse_args()

    samples = json.loads(args.inp.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise SystemExit("expected locomo10.json to be a JSON array of conversations")
    records = convert(samples)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    abstain = sum(1 for r in records if r["should_abstain"])
    matched = sum(1 for r in records if r["supporting_facts"])
    print(
        f"wrote {len(records)} question records -> {args.out}\n"
        f"  conversations: {len(samples)} | abstention(cat5): {abstain} | "
        f"with mapped evidence: {matched}"
    )


if __name__ == "__main__":
    main()
