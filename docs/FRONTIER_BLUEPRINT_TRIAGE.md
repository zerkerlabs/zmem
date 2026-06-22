# Frontier Blueprint Triage

Date: 2026-06-22

This note triages the downloaded frontier architecture report against the current ZMem build lanes. It keeps the useful architecture, removes overreach, and turns research claims into buildable slices.

## Verdict

The blueprint is directionally strong. The main update is not "build a huge graph system first." The main update is:

1. Fix retrieval quality first.
2. Make conflict assembly deterministic.
3. Make temporal state explicitly bi-temporal.
4. Add query routing before expensive write-time extraction.
5. Use profiles and consolidation after retrieval/temporal basics are measurable.

The report's predicted scores and competitor comparisons are useful internal targets, not public claims.

## Keep

- Retrieval is the bottleneck. Prioritize L3 hybrid retrieval, retrieval depth tuning, context expansion, and query routing before complex write-time extraction.
- Deterministic conflict resolution is a core ZMem opportunity. Current-value conflicts should resolve by explicit serial/timestamp ordering, with receipts showing the candidates and chosen rule.
- Temporal reasoning should move from implicit heuristics to explicit bi-temporal state: valid time, recorded time, supersession, and point-in-time query behavior.
- Ground-truth-preserving storage matters. Do not replace raw episodes with only lossy summaries.
- Benchmark artifacts must remain proof-backed: isolated DBs, question records, receipt bundles, hashes, and reproducible commands.

## Add

- L1 should own deterministic conflict assembly:
  - monotonic write serial,
  - `valid_from` / `valid_to`,
  - supersession links,
  - current-value resolver,
  - point-in-time resolver,
  - timeline resolver for change questions.
- L3 should own adaptive retrieval routing:
  - direct single-hop path,
  - parallel decomposed subqueries,
  - iterative chain-of-query path,
  - temporal override when a query asks before/after/current/changed.
- L3 should own context expansion:
  - retrieve nucleus memories,
  - optionally include neighbor turns/session context,
  - record expansion in the retrieval receipt.
- L4 should include profile consolidation, but only after raw episodic retrieval and explicit temporal/conflict behavior are measurable.
- L6 should add conflict-resolution and temporal benchmark slices alongside LoCoMo/LongMemEval. FactConsolidation and EngramaBench are research candidates until primary-source methodology and local fixture support are pinned.

## Remove Or Downgrade

- Do not make graph extraction the first step. It is useful, but retrieval/router work has higher near-term leverage.
- Do not expand to 13 memory types immediately. Keep the current type model and add only types that have distinct write gates or retrieval behavior. The likely next candidates are `event`, `preference`, `profile`, `reflection`, and `constraint`.
- Do not claim projected 91-94% benchmark performance. Treat projections as internal ambition until a reproducible run exists.
- Do not require hosted LLM extraction, hosted reranking, or OpenAI-based judging in the default product path.
- Do not call receipts proof of semantic truth. Receipts prove provenance, integrity, lineage, and what evidence influenced a decision.

## Immediate Build Order

1. L3 retrieval depth and context expansion regression.
2. L1 deterministic conflict fixture with current vs historical vs timeline questions.
3. L1 minimal bi-temporal local-store fields or side table.
4. L3 query router contract: direct, parallel, chain, temporal override.
5. L6 fixture-backed benchmark for conflict resolution with receipt-visible candidate assembly.
6. L4 profile/consolidation fixture once the above has measurable evidence.

## Claim Boundary

Allowed internally:

- "Research suggests retrieval method can dominate memory performance."
- "Deterministic conflict assembly is a promising ZMem wedge."
- "Temporal and conflict benchmark lanes are now priority build lanes."

Allowed publicly only after proof:

- exact benchmark scores,
- competitor superiority,
- "official" LongMemEval/LoCoMo/FactConsolidation/EngramaBench ranking,
- token-efficiency comparisons.

## Primary Sources To Pin

- REMem: `https://arxiv.org/abs/2602.13530`
- Diagnosing Retrieval vs. Utilization Bottlenecks: `https://arxiv.org/abs/2603.02473`
- MemMachine: `https://arxiv.org/abs/2604.04853`
- TReMu: `https://arxiv.org/abs/2502.01630`
- Don't Ask the LLM to Track Freshness: `https://arxiv.org/abs/2606.01435`
- CAST: `https://arxiv.org/abs/2602.06051`
- EngramaBench: `https://arxiv.org/abs/2604.21229`
- Memory for Autonomous LLM Agents survey: `https://arxiv.org/abs/2603.07670`
