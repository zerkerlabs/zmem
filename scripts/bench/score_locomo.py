from __future__ import annotations

import argparse
import json
import re
import string
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import nltk
except ModuleNotFoundError:  # pragma: no cover - environment fallback
    nltk = None


CATEGORY_LABELS = {
    "1": "1_single_hop",
    "single-hop": "1_single_hop",
    "single_hop": "1_single_hop",
    "single hop": "1_single_hop",
    "2": "2_multi_hop",
    "multi-hop": "2_multi_hop",
    "multi_hop": "2_multi_hop",
    "multi hop": "2_multi_hop",
    "3": "3_temporal",
    "temporal": "3_temporal",
    "temporal_reasoning": "3_temporal",
    "4": "4_open_domain_knowledge",
    "open-domain knowledge": "4_open_domain_knowledge",
    "open_domain": "4_open_domain_knowledge",
    "open_domain_knowledge": "4_open_domain_knowledge",
    "5": "5_adversarial_abstention",
    "adversarial": "5_adversarial_abstention",
    "adversarial/abstention": "5_adversarial_abstention",
    "adversarial_abstention": "5_adversarial_abstention",
}
ORDERED_CATEGORIES = [
    "1_single_hop",
    "2_multi_hop",
    "3_temporal",
    "4_open_domain_knowledge",
    "5_adversarial_abstention",
]


def normalize_tokens(text: str) -> list[str]:
    table = str.maketrans("", "", string.punctuation)
    raw_tokens = nltk.word_tokenize(text.lower()) if nltk else re.findall(r"\w+", text.lower())
    return [token.translate(table) for token in raw_tokens if token.translate(table)]


def token_f1(hypothesis: str, reference: str) -> float:
    hyp_tokens = normalize_tokens(hypothesis)
    ref_tokens = normalize_tokens(reference)
    if not hyp_tokens and not ref_tokens:
        return 1.0
    if not hyp_tokens or not ref_tokens:
        return 0.0
    overlap = sum((Counter(hyp_tokens) & Counter(ref_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(hyp_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def exact_match(hypothesis: str, reference: str) -> float:
    return 1.0 if " ".join(normalize_tokens(hypothesis)) == " ".join(normalize_tokens(reference)) else 0.0


def is_abstention(text: str) -> bool:
    normalized = " ".join(str(text).strip().lower().split())
    if not normalized:
        return True
    return any(
        phrase in normalized
        for phrase in (
            "don't know",
            "do not know",
            "no information",
            "cannot",
        )
    )


def category_key(row: dict[str, Any]) -> str:
    raw = row.get("category", "unknown")
    key = str(raw).strip().lower().replace("-", "_")
    if key in CATEGORY_LABELS:
        return CATEGORY_LABELS[key]
    return CATEGORY_LABELS.get(str(raw).strip().lower(), str(raw or "unknown"))


def score_row(row: dict[str, Any]) -> tuple[float, float]:
    category = category_key(row)
    hypothesis = str(row.get("hypothesis", ""))
    if category == "5_adversarial_abstention" or row.get("should_abstain") is True:
        score = 1.0 if is_abstention(hypothesis) else 0.0
        return score, score
    reference = str(row.get("reference", ""))
    return token_f1(hypothesis, reference), exact_match(hypothesis, reference)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bench-dir", type=Path, default=Path(".zerker/bench"))
    args = parser.parse_args()

    run_dir = args.bench_dir / args.run_id
    trace_path = run_dir / "trace.jsonl"
    receipt_path = run_dir / "receipt.json"
    if not trace_path.exists():
        raise SystemExit(f"missing trace: {trace_path}")
    if not receipt_path.exists():
        raise SystemExit(f"missing receipt: {receipt_path}")

    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    f1_values: list[float] = []
    em_values: list[float] = []
    by_category: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"f1": [], "em": []})
    for row in rows:
        f1, em = score_row(row)
        f1_values.append(f1)
        em_values.append(em)
        category = category_key(row)
        by_category[category]["f1"].append(f1)
        by_category[category]["em"].append(em)

    ordered_keys = ORDERED_CATEGORIES + sorted(category for category in by_category if category not in ORDERED_CATEGORIES)
    scores = {
        "overall_f1": mean(f1_values),
        "overall_em": mean(em_values),
        "question_count": len(rows),
        "per_category": {
            category: {
                "f1": mean(values["f1"]),
                "em": mean(values["em"]),
                "question_count": len(values["f1"]),
            }
            for category in ordered_keys
            for values in [by_category[category]]
        },
    }
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    scored = {
        **receipt,
        "scores": scores,
        "scoring_type": "locomo-token-f1-exact-match",
        "public_benchmark_claim": False,
    }
    out_path = run_dir / "scored_receipt.json"
    out_path.write_text(json.dumps(scored, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(scores, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
