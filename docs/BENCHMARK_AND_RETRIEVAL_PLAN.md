# Benchmark And Retrieval Plan

ZMem should compete on memory quality while staying differentiated on trust. The goal is not only to score well on memory benchmarks, but to make every score reproducible: what was retrieved, why it was injected, what was withheld, how long it took, how many tokens it cost, and which proof root verifies the run.

## Product Principle

Accuracy earns attention. Proof earns trust.

Benchmark work must strengthen the core product rather than become benchmark theater. Every benchmark feature should also improve real agent use: continuation, handoff, temporal correctness, conflict handling, absence awareness, and explainable memory injection.

The north star is not merely "verifiable memory." It is the best AI-agent memory product: top-tier recall quality, latency, token efficiency, temporal correctness, abstention, and multi-hop reasoning, with privacy, portability, trust, and verification as the wedge that makes the quality credible.

## Claims Discipline

Use benchmark work as an internal forcing function before using it as a public claim.

Keep as product direction:

- ZMem should compete on benchmark accuracy, latency, and token efficiency.
- ZMem's unique wedge is proof-backed, reproducible memory influence, not just another "we retrieve better" claim.
- LongMemEval and LoCoMo-style evaluations are important references for long-term agent memory.
- Temporal reasoning, contradiction/update handling, abstention, and token cost are core benchmark dimensions.
- Receipts, Merkle roots, and optional Treeship proof URLs should make benchmark runs reproducible and auditable.

Soften until primary-source verified:

- Do not claim that a small fixed set of benchmarks defines the whole market ranking.
- Do not repeat leaderboard numbers, vendor claims, or secondary-source scores until they are reproduced or cited from primary benchmark pages.
- Treat numeric goals such as `>85%` LongMemEval or `>90%` LoCoMo as internal ambition, not public fact.
- Treat BEAM, AMB, STATE-Bench, or any other less-established benchmark names as research candidates until verified from primary sources.

Strategic line:

> ZMem does not need to be only the highest-recall memory system on day one. It needs to be the most trustworthy memory system: local-first, easy to use, benchmarkable, reproducible, and able to prove what memory influenced an agent action.

Sources to anchor before public benchmark copy:

- LongMemEval
- LongMemEval-V2
- LoCoMo
- Zep research / benchmark material
- Letta benchmark critique

See `docs/BENCHMARK_RETRIEVAL_SWARM_MISSION.md` for the active Codex swarm mission brief.

## Phase 2: Benchmark Harness

Build `zmem bench` as a first-class command family.

For the current local LongMemEval-style and LoCoMo-style fixture contract, see `docs/BENCHMARK_FIXTURE_CONTRACT.md`.
For the operator path from first local run to public evidence page, see `docs/BENCHMARK_GETTING_STARTED.md`.

### Commands

```bash
zmem bench list
zmem bench run longmemeval --dataset /path/to/local-longmemeval.jsonl --split dev --out .zerker/bench/longmemeval
zmem bench run locomo --dataset /path/to/local-locomo.jsonl --split dev --out .zerker/bench/locomo
zmem bench report .zerker/bench/<run-id>
zmem bench verify .zerker/bench/<run-id>/benchmark-result.json
zmem bench compare .zerker/bench/<run-a>/benchmark-result.json .zerker/bench/<run-b>/benchmark-result.json
zmem bench dashboard .zerker/bench/<matrix-run-id>
zmem bench public-page .zerker/bench/<matrix-run-id> --out landing/benchmarks.html
zmem bench publish .zerker/bench/<run-id>
```

Keep `bench publish` optional. Local benchmark proof must work without Hub or account setup; public proof can use Treeship when the operator wants a shareable verification URL.

### Adapters

#### LongMemEval

Support the canonical question categories:

- single-session user recall
- single-session assistant recall
- single-session preference
- temporal reasoning
- knowledge update
- multi-session reasoning
- abstention when no grounded memory exists

Each question should run in an isolated store namespace so no question leaks memory into another question.

#### LoCoMo

Support the canonical question types:

- single-hop
- multi-hop
- temporal
- open-domain / commonsense plus conversation context

Report F1 by category and overall. Keep exact prompt/judge configuration in the run manifest.

### Metrics

Every run should report:

- accuracy / judge score
- F1 where benchmark requires it
- recall@k for retrieved memory candidates
- precision@k when ground-truth supporting facts are available
- abstention correctness
- temporal correctness
- knowledge-update correctness
- p50, p95, and p99 retrieval latency
- end-to-end answer latency
- retrieved context token count
- generated answer token count
- total tokens per question
- number of memories retrieved, injected, and withheld
- proof verification status

### Run Isolation

Each benchmark run should write:

```text
.zerker/bench/<run-id>/
  benchmark-run.json
  benchmark-result.json
  questions/
    <question-id>.json
  receipts/
    <action-id>.bundle.json
  snapshots/
    before.snapshot.json
    after.snapshot.json
  report.md
  report.html
```

Each question should record:

- dataset and question ID
- question category
- input history hash
- ground truth answer hash
- retrieval query / query variants
- candidate memory IDs
- injected memory IDs
- withheld memory IDs
- final answer
- judge output
- latency and token metrics
- action receipt ID
- receipt bundle path

### Proof Contract

Every benchmark run gets a benchmark receipt:

- run ID
- dataset name and version
- adapter version
- model and judge model
- prompt hashes
- per-question receipt bundle hashes
- aggregate result hash
- aggregate Merkle root
- local verification result
- optional Treeship artifact ID / public verify URL

This creates the launch differentiator:

> ZMem benchmark reports do not just claim a score. They prove the memory evidence behind the score.

### Reproducibility

Every report should include a copy-ready command:

```bash
zmem bench run longmemeval --dataset <path-or-version> --config <config> --seed <seed>
```

The command must pin:

- dataset version or hash
- ZMem version
- retrieval config
- model config
- judge config
- random seed
- token budget

## Phase 3: Retrieval Upgrades

Retrieval upgrades should land behind explicit configs so the benchmark harness can compare modes honestly.

The retrieval goal is a top-tier baseline that improves quality without weakening auditability:

- hybrid FTS plus embeddings
- reranking
- temporal query expansion
- multi-hop query decomposition
- update/conflict handling
- context packing budget
- citations in injected context
- receipt fields for retrieved, injected, withheld, and budget-dropped memories

See `docs/RETRIEVAL_BASELINE_IMPLEMENTATION_PLAN.md` for the concrete first-slice implementation plan.

### Mode 1: Strong FTS Baseline

Improve the current SQLite FTS path before adding complexity.

- BM25-style scoring from SQLite FTS.
- Better query term extraction.
- phrase search and exact-match boosts.
- field boosts for type, labels, source, actor, and scope.
- absence-aware results: returning no memory is valid and should be receipted.
- deterministic context packing so repeated runs are comparable.

Target: a simple local baseline that is fast, explainable, and hard to misuse.

### Mode 2: Embedding Overlay

Add optional embeddings without making them required for day-1 use.

- local embedding provider first where possible.
- configurable hosted embedding provider.
- embedding table keyed by memory ID and content hash.
- lazy backfill command: `zmem index embeddings`.
- metadata filters before vector ranking.
- receipt records the embedding model and embedding index hash.

Principle: SQL/metadata prunes; embeddings rank fuzzy matches inside the governed scope.

### Mode 3: Reranking

Add a second-pass reranker for benchmark and high-accuracy modes.

- cross-encoder or LLM reranker adapter.
- deterministic prompt/config hashing.
- separate latency/token accounting.
- rerank explanation attached to receipt metadata.
- fallback to FTS/embedding order when reranker is unavailable.

### Mode 4: Temporal Memory

Add explicit temporal fields and query behavior.

- valid_from / valid_to where applicable.
- observed_at, superseded_at, revoked_at.
- relationship: supersedes / contradicts / supports / derived_from.
- chronological retrieval mode for temporal questions.
- knowledge-update resolver that prefers current facts while preserving history.
- receipt field for temporal strategy used.

This directly targets the Moltbook problems around stale assumptions and benchmark categories around temporal reasoning and knowledge updates.

### Mode 5: Context Packing Budget

Add a packing layer before injection.

- max memory tokens per action.
- diversity cap by type/source/session.
- mandatory policy memories can reserve budget.
- recent/high-authority memories can receive priority.
- duplicate compression.
- proof records which candidates were dropped because of token budget.

This prevents token bloat and makes retrieval decisions auditable.

### Mode 6: Multi-Hop Query Decomposition

Add query planning for complex questions.

- decompose question into subqueries.
- retrieve per subquery.
- merge candidates with evidence paths.
- cite memory chains used for final answer.
- record decomposition plan in receipt metadata.

Use this for LoCoMo multi-hop and LongMemEval multi-session questions, but keep the plan visible so it remains inspectable.

## Launch Scorecard

Phase 2 launch is ready when:

- `zmem bench run longmemeval` produces a verified local report.
- `zmem bench run locomo` produces a verified local report.
- each question has an action receipt and bundle.
- aggregate benchmark result verifies from disk.
- optional `bench publish` produces a Treeship proof URL.
- report includes accuracy, F1, recall@k, latency, token metrics, and abstention.

Phase 3 launch is ready when:

- FTS baseline, embedding overlay, reranking, temporal retrieval, context packing, and multi-hop modes can be enabled independently.
- benchmark reports compare at least `fts`, `fts+embedding`, and `fts+embedding+rerank`.
- temporal and knowledge-update questions include explicit stale/current decision metadata.
- no raw private memory is published by default.

## Roadmap Order

1. Add `zmem bench` skeleton, run manifest, result schema, and local verification.
2. Add LongMemEval adapter with isolated DB per question.
3. Add LoCoMo adapter and F1 scoring.
4. Add benchmark report markdown/HTML.
5. Add benchmark receipt bundle and optional Treeship publish.
6. Strengthen FTS/BM25 baseline and context packing.
7. Add optional embeddings and embedding index receipts.
8. Add temporal fields, conflict/update handling, and chronological retrieval.
9. Add reranking.
10. Add multi-hop query decomposition.

## Product Copy

Use this when describing the benchmark system:

> ZMem benchmark reports are reproducible memory audits. Every score includes the retrieved memories, withheld memories, receipts, token cost, latency, and proof root behind the result.
