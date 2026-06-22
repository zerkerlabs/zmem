#!/usr/bin/env bash
set -e
if [ -z "$OPENAI_API_KEY" ]; then echo "Set OPENAI_API_KEY first"; exit 1; fi

zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench \
  --run-id locomo-scored-v1 \
  --mode zmem-retrieval \
  --answerer llm \
  --trace \
  --seed 42

python3 scripts/bench/score_locomo.py --run-id locomo-scored-v1
