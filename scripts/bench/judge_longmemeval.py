from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


LABEL_RE = re.compile(r"autoeval_label['\"]?\s*[:=]\s*['\"]?([A-Za-z_ -]+)")


def ensure_repo(path: Path) -> None:
    if path.exists():
        return
    subprocess.run(["git", "clone", "https://github.com/xiaowu0162/LongMemEval", str(path)], check=True)


def parse_labels(log_path: Path) -> list[str]:
    labels: list[str] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LABEL_RE.search(line)
        if match:
            labels.append(match.group(1).strip().lower())
    return labels


def label_is_correct(label: str) -> bool:
    return label in {"correct", "true", "1", "yes"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bench-dir", type=Path, default=Path(".zerker/bench"))
    parser.add_argument("--repo-dir", type=Path, default=Path("data/longmemeval-repo"))
    args = parser.parse_args()

    ensure_repo(args.repo_dir)
    run_dir = args.bench_dir / args.run_id
    hypothesis_path = run_dir / "hypothesis.jsonl"
    receipt_path = run_dir / "receipt.json"
    if not hypothesis_path.exists():
        raise SystemExit(f"missing hypothesis file: {hypothesis_path}")
    if not receipt_path.exists():
        raise SystemExit(f"missing receipt: {receipt_path}")

    command = [
        "python3",
        str(args.repo_dir / "src/evaluation/evaluate_qa.py"),
        "gpt-4o",
        str(hypothesis_path),
        "data/longmemeval/longmemeval_oracle.json",
    ]
    subprocess.run(command, check=True)
    logs = sorted(run_dir.glob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not logs:
        logs = sorted(Path(".").glob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not logs:
        raise SystemExit("LongMemEval evaluator completed but no .log file was found")

    labels = parse_labels(logs[0])
    if not labels:
        raise SystemExit(f"no autoeval_label fields parsed from {logs[0]}")

    questions = [json.loads(line) for line in hypothesis_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_type: dict[str, list[float]] = defaultdict(list)
    abstain_tp = abstain_fp = abstain_fn = 0
    for row, label in zip(questions, labels):
        correct = 1.0 if label_is_correct(label) else 0.0
        by_type[str(row.get("question_type", row.get("category", "unknown")))].append(correct)
        hyp = str(row.get("hypothesis", "")).strip().lower()
        abstained = hyp in {"", "i don't know", "i do not know"}
        if abstained and correct:
            abstain_tp += 1
        elif abstained and not correct:
            abstain_fp += 1
        elif not abstained and not correct:
            abstain_fn += 1

    accuracy_values = [1.0 if label_is_correct(label) else 0.0 for label in labels]
    precision = abstain_tp / (abstain_tp + abstain_fp) if abstain_tp + abstain_fp else 0.0
    recall = abstain_tp / (abstain_tp + abstain_fn) if abstain_tp + abstain_fn else 0.0
    abstention_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    scores = {
        "overall_accuracy": sum(accuracy_values) / len(accuracy_values),
        "question_count": len(labels),
        "per_question_type_accuracy": {
            key: sum(values) / len(values) for key, values in sorted(by_type.items())
        },
        "abstention_f1": abstention_f1,
        "judge_log": str(logs[0]),
    }
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    scored = {
        **receipt,
        "scores": scores,
        "judge": "gpt-4o",
        "scoring_type": "longmemeval-gpt-4o-judge",
        "public_benchmark_claim": True,
    }
    out_path = run_dir / "scored_receipt.json"
    out_path.write_text(json.dumps(scored, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(scores, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
