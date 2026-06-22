#!/usr/bin/env bash
set -e
if [ -z "$OPENAI_API_KEY" ]; then echo "Set OPENAI_API_KEY first"; exit 1; fi

zmem bench matrix longmemeval \
  --dataset data/longmemeval/longmemeval_oracle.json \
  --out .zerker/bench \
  --run-id longmemeval-scored-v1 \
  --mode zmem-retrieval \
  --answerer llm \
  --trace \
  --seed 42

python3 scripts/bench/judge_longmemeval.py \
  --run-id longmemeval-scored-v1
