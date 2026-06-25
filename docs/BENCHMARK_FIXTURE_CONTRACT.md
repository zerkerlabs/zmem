# Benchmark Fixture Contract

This contract describes the local fixture shape accepted by the current `zmem bench run longmemeval` and `zmem bench run locomo` scaffolds. It is for adapting external datasets into reproducible local runs without changing core code and without turning scaffold results into public benchmark claims.

## Local-Only Policy

- Dataset inputs must be local files. URL inputs such as `https://...` are rejected.
- ZMem does not download datasets, call hosted judges, or publish verification URLs for these scaffold runs.
- LongMemEval-style and LoCoMo-style results are provisional local scaffold results. They can guide development, regression testing, and fixture validation, but they are not canonical LongMemEval or LoCoMo benchmark scores.
- Do not claim public ranking, superiority, parity, or benchmark wins from local scaffold output.

## Accepted Input Shapes

The adapters read UTF-8 JSON or JSONL.

- `.jsonl`: one JSON object per non-empty line.
- `.json`: a JSON array of record objects.
- `.json`: a JSON object wrapper whose first list value appears under one of `records`, `data`, `examples`, `questions`, or `items`.
- `.json`: a split-keyed object where every top-level value is a list. The loader flattens the lists and adds `split` from the top-level key when a record does not already include `split`.

Every final record must be a JSON object after wrapper extraction. Other input shapes are out of scope for the current code.

## Split Filtering

Runs filter records before normalization:

```text
str(record.get("split", "default")) == --split
```

If no records match, the run fails. Use explicit split values when adapting fixtures. For split-keyed JSON objects, missing record-level `split` fields are filled from the top-level key before filtering.

## LongMemEval-Style Records

The current LongMemEval scaffold requires these fields:

- `question_id`: unique within the filtered split.
- `split`: split name, unless supplied by split-keyed wrapper expansion.
- `category`: local category label.
- `history`: list of memory/history items.
- `question`: retrieval query.
- `answer`: expected answer when `should_abstain` is false.
- `supporting_facts`: list of supporting fact indexes or content-like items.
- `should_abstain`: boolean.

History items may be strings or objects. Object text is read from the first available `content`, `text`, `message`, or `value` field. If an object has `speaker`, `role`, or `actor` plus `utterance`, it is rendered as `speaker: utterance`.

`supporting_facts` may contain zero-based integer indexes into `history`, or content-like items matched against normalized history text. If `should_abstain` is true, the expected answer becomes the local abstention string:

```text
I don't know
```

## LoCoMo-Style Records

The current LoCoMo scaffold accepts these common fields:

- `question_id`, `id`, or `qid`: optional ID. If missing, the adapter assigns `locomo-<index>`.
- `split`: optional split name. Defaults to `default`.
- `category` or `type`: optional category label. Defaults to `locomo`.
- `question` or `query`: required retrieval query.
- `answer`, `ground_truth`, or `target_answer`: expected answer. Defaults to an empty string.
- `history`, `conversation`, `messages`, `dialogue`, or `sessions`: optional list of history items.
- `supporting_facts`, `evidence`, `supporting_evidence`, or `evidence_list`: optional supporting evidence.
- `should_abstain`: optional boolean. Defaults to false.

Nested history lists under `messages`, `history`, `conversation`, `dialogue`, or `utterances` are flattened. History item text uses the same extraction rules as LongMemEval-style records.

If supporting evidence is not a list, it is wrapped in a single-item list. If a non-abstention LoCoMo-style record has history but no matched supporting facts, the current scaffold treats all history items as expected support.

## Hashes And Artifacts

Each run writes a local run directory containing:

```text
benchmark-run.json
benchmark-result.json
questions/
receipts/
snapshots/
report.md
```

`dataset_hash` is the SHA-256 hash of the stable JSON representation of all loaded records after wrapper extraction and split-key expansion. It is not a byte-for-byte hash of the source file.

`filtered_dataset_hash` is the SHA-256 hash of the stable JSON representation of only the records selected by `--split`. Comparisons should treat different filtered hashes as different evaluated fixtures even when the source dataset hash is the same.

Each question produces a question JSON, an action receipt bundle, and proof fields for the receipt Merkle root, memory tree root, and bundle hash. Each run also stores before/after memory snapshots and an aggregate Merkle root over the run artifacts.

## Scoring Status

Scoring is `provisional-local`.

The scaffold inserts fixture history into an isolated local memory scope, runs local retrieval/injection, and uses a deterministic local answerer plus exact-match local judge. A non-abstention question is correct only when all expected supporting memories are injected; otherwise the answer abstains and the question fails. Abstention questions are correct when they produce the local abstention string.

LoCoMo-style question records also include local `token_f1`, but the run score remains provisional local scoring. These values are useful for regression work, not public benchmark claims.

## Verify, Report, And Compare

`bench report` regenerates `report.md` from the run manifest, summary, and question records.

`bench verify` recomputes the result hash, artifact hashes, aggregate result hash, aggregate Merkle root, snapshot verification, question hashes, and receipt bundle verification from local disk.

`bench compare` requires at least two `benchmark-result.json` paths. It verifies each input, reports compatibility warnings when benchmark names, dataset hashes, filtered dataset hashes, or question counts differ, and computes metric deltas against the first result as baseline.

## Example Commands

```bash
zmem bench run longmemeval \
  --dataset /path/to/local-longmemeval-fixture.jsonl \
  --split dev \
  --out /private/tmp/zmem-bench \
  --seed 0 \
  --run-id longmemeval-dev

zmem bench run locomo \
  --dataset /path/to/local-locomo-fixture.json \
  --split dev \
  --out /private/tmp/zmem-bench \
  --seed 0 \
  --run-id locomo-dev

zmem bench verify /private/tmp/zmem-bench/longmemeval-dev/benchmark-result.json

zmem bench compare \
  /private/tmp/zmem-bench/longmemeval-dev/benchmark-result.json \
  /private/tmp/zmem-bench/longmemeval-dev-alt/benchmark-result.json
```

## Out Of Scope

- Dataset downloading, dataset registry resolution, or remote fixture URLs.
- Hosted LLM answerers or hosted LLM judges.
- Canonical benchmark scoring for LongMemEval, LoCoMo, or related datasets.
- Public leaderboard claims, vendor comparisons, or score marketing.
- Adapter-specific schema inference beyond the fields listed above.
- Core-code changes to accommodate a fixture that can be adapted into this contract.

## Public-Claims Guardrails

Allowed language:

- "ZMem can run local LongMemEval-style and LoCoMo-style fixtures with receipt-backed artifacts."
- "This run is locally reproducible and locally verifiable from the bundled artifacts."
- "This provisional scaffold helps test retrieval, abstention, latency, token use, and proof integrity."

Disallowed language from scaffold results:

- "ZMem achieves X on LongMemEval."
- "ZMem beats or matches another memory system on LoCoMo."
- "This local scaffold is an official benchmark result."
- "The public benchmark score is verified by this local report."
