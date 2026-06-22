# Retrieval Baseline Implementation Plan

This is the concrete implementation plan for the first top-tier retrieval baseline in ZMem. It is documentation/design only; do not implement retrieval code from this file until the coordinator promotes the slice.

## Goal

Build a strong, local, auditable SQLite retrieval baseline before adding embeddings or hosted rerankers.

Success means a receipt can explain:

- which candidates were retrieved
- how each candidate was ranked
- which candidates policy allowed or withheld
- which allowed candidates fit the context budget
- which candidates were dropped by budget or diversity rules
- which temporal/update signals affected the decision

The first implementation should not require a receipt database migration because `receipts.retrieval_json` already exists and is restored through snapshots.

## Current Retrieval Path Summary

Current code path:

- `zerker_memory/store.py:194` creates `memories_fts` with indexed `content` and `labels`; `id` is stored as `UNINDEXED`.
- `MemoryStore.search()` at `zerker_memory/store.py:478` delegates to `MemoryStore.search_with_meta()`.
- `MemoryStore.search_with_meta()` at `zerker_memory/store.py:481` sanitizes the user query with `fts_safe_query()`, tries SQLite FTS first, then falls back to `LIKE` when FTS returns no rows or raises an operational error.
- The FTS query currently orders by `m.authority DESC, m.trust DESC, bm25(memories_fts)` and limits to 20.
- The fallback path searches `lower(m.content) LIKE ?`, orders by `m.authority DESC, m.trust DESC`, and also limits to 20.
- `MemoryStore.inject()` at `zerker_memory/store.py:675` calls `search_with_meta(..., include_quarantined=True)`, applies `decide_memory()` from `zerker_memory/policy.py`, then writes a receipt.
- Current receipt retrieval metadata at `zerker_memory/store.py:711` records only `query`, `fts_query`, and `search_mode`.
- `MemoryStore.why()` at `zerker_memory/store.py:762` already reads `retrieval_json`, so richer retrieval metadata can surface through `why()`, receipt bundles, snapshots, and benchmark artifacts without a DB schema change.
- `zerker_memory/runner.py:75` builds the runtime memory context from `receipt["memories"]`, so any context packing performed inside `inject()` will automatically affect command-run context.

Important current behavior to preserve:

- Policy authorization stays after retrieval and before injection.
- Quarantined/proposed candidates can be retrieved for policy receipts, but only active authorized memories may be injected.
- Empty retrieval is valid and should produce a receipt with `search_mode: "none"` and empty retrieved/injected lists.
- Revoked, forgotten, deprecated, and expired memories should not be returned as candidates unless a future explicit audit mode asks for them.

## First Implementation Slice

The first slice should strengthen explainable FTS/BM25 retrieval and deterministic receipt metadata. It should not add embeddings, vector indexes, hosted judges, or new temporal columns.

Files/functions to change:

- `zerker_memory/store.py`
  - Add constants for retrieval schema/version, rank config, candidate limit, and default context token budget.
  - Add small helpers near `query_terms()`:
    - `approx_memory_tokens(memory_or_text) -> int`
    - `authority_rank(authority: str) -> int`
    - `memory_rank_features(memory, *, query_terms, bm25_score, search_mode) -> dict`
    - `combine_rank_score(features: dict) -> float`
    - `pack_memory_context(allowed_memories, *, ranking, max_tokens, reserve_policy_tokens) -> dict`
  - Update `MemoryStore.search_with_meta()` to select `bm25(memories_fts) AS bm25_score` on FTS queries and return a `ranking` object with one stable entry per candidate.
  - Keep `MemoryStore.search()` returning only `["memories"]` for compatibility.
  - Update `MemoryStore.inject()` after policy authorization and before receipt construction to call `pack_memory_context()` on authorized memories.
  - Update receipt construction to store the richer `retrieval` object in `retrieval_json` and set `receipt["memories"]` from packed injected memories, not all policy-authorized memories.
- `tests/test_store.py`
  - Add focused tests listed below.
- `tests/test_runner.py`
  - Add one context test proving budget-dropped memories do not appear in `build_context()` output.

No schema migration in the first slice:

- Do not alter `memories`.
- Do not alter `memories_fts`.
- Do not alter `receipts`.
- Use the existing `retrieval_json` column for rank, packing, and dropped-candidate metadata.

## Ranking Metadata Shape

Use a versioned object in `receipt["retrieval"]` and persisted `retrieval_json`.

```json
{
  "schema": "zerker.retrieval.v1",
  "query": "deploy service to production",
  "query_terms": ["deploy", "service", "production"],
  "fts_query": "\"deploy\" \"service\" \"production\"",
  "search_mode": "fts",
  "candidate_limit": 20,
  "rank_config": {
    "schema": "zerker.retrieval_rank_config.v1",
    "mode": "fts_bm25_v1",
    "weights": {
      "bm25": 1.0,
      "authority": 0.35,
      "trust": 0.25,
      "label_exact": 0.15,
      "content_exact": 0.10,
      "freshness": 0.05
    }
  },
  "candidates": [
    {
      "memory_id": "mem_...",
      "rank": 1,
      "search_mode": "fts",
      "bm25": -1.234,
      "score": 1.837,
      "features": {
        "authority": "policy",
        "authority_rank": 4,
        "trust": 0.95,
        "content_term_matches": 2,
        "label_term_matches": 1,
        "created_at": "2026-06-05T00:00:00Z",
        "updated_at": "2026-06-05T00:00:00Z",
        "expires_at": null,
        "is_expired": false,
        "has_parents": false
      }
    }
  ],
  "policy": {
    "engine": "zerker.symbolic_policy.v1",
    "authorized_ids": ["mem_..."],
    "withheld_ids": ["mem_..."]
  },
  "packing": {
    "schema": "zerker.context_packing.v1",
    "strategy": "ranked_budget_v1",
    "max_tokens": 1200,
    "approximation": "chars_div_4_ceil",
    "reserved_policy_tokens": 0,
    "used_tokens": 184,
    "injected_ids": ["mem_..."],
    "budget_dropped": [
      {
        "memory_id": "mem_...",
        "reason": "token_budget",
        "approx_tokens": 420,
        "rank": 4
      }
    ],
    "diversity_dropped": []
  }
}
```

Ranking rules:

- Use deterministic scoring only. No randomness and no wall-clock dependent score components in the first slice.
- Preserve current broad priority order: authority and trust matter, then textual relevance.
- Keep SQLite `bm25()` as a raw feature. Because SQLite FTS5 returns lower BM25 values for better matches, convert it into a positive component in Python for the combined score.
- For fallback `LIKE`, set `bm25` to `null`, `search_mode` to `fallback`, and compute text match counts from sanitized query terms.
- Do not include raw memory content in ranking metadata; receipts already carry memory IDs, content hashes, memory tree leaves, and injected memory payloads where appropriate.

## Context Packing Design

Placement:

- Retrieval: `search_with_meta()` returns ranked candidates plus ranking metadata.
- Policy: `inject()` applies `decide_memory()` to each candidate.
- Packing: immediately after policy authorization and before receipt construction in `MemoryStore.inject()`.
- Receipt: `retrieved_memory_ids` remains all retrieved candidates, `withheld` remains policy-withheld candidates, and `injected_memory_ids` becomes the packed subset.
- Context: `runner.build_context()` continues to consume `receipt["memories"]`, which should contain only packed injected memories.

Token approximation:

- Use a deterministic local approximation: `ceil(len(text) / 4)`.
- Approximate each memory from the text that will actually enter context, initially `stable_json(memory.to_dict())`.
- Record the approximation name as `chars_div_4_ceil`.
- This is intentionally rough but stable enough for benchmark comparisons until tokenizer-specific accounting lands.

Packing algorithm:

1. Split policy-authorized candidates into mandatory policy memories and ordinary memories.
2. Sort each group by the final retrieval rank.
3. Pack mandatory policy memories first while recording any policy memory that cannot fit as `budget_dropped`.
4. Pack ordinary memories by rank until `max_tokens` is exhausted.
5. Apply a simple deterministic diversity cap only if required by tests or benchmark noise, such as max 3 memories per `source_kind`; keep this disabled in the first slice unless it is explicitly configured.
6. Record every excluded authorized memory as either `budget_dropped` or `diversity_dropped`.

Open config question for implementation:

- Start with a constant default such as `DEFAULT_CONTEXT_MEMORY_TOKENS = 1200`.
- Add a public CLI/config knob only after the benchmark harness needs mode comparison. Do not add broad configurability in the first slice.

## Temporal, Update, And Conflict Sequencing

First use existing lifecycle fields:

- `status` already excludes revoked/deprecated/forgotten memories from normal retrieval.
- `expires_at` exists and should become an explicit retrieval feature before any new column work.
- `parents` already supports lineage and revocation of descendants.
- `created_at` and `updated_at` already support simple freshness metadata.

Slice 1 behavior:

- Surface `created_at`, `updated_at`, `expires_at`, `is_expired`, and `has_parents` in candidate rank features.
- Exclude expired memories from normal retrieval if `expires_at` is before `now_iso()`. If implementation chooses not to change filtering yet, at minimum set `is_expired` in metadata and add a follow-up blocker.
- Preserve revocation behavior already covered by `test_lineage_and_revoke_descendants`.

Slice 2 behavior:

- Add explicit update/conflict heuristics without schema changes:
  - Prefer active children over active parents when both match the same query.
  - Mark lower-ranked parent candidates as `superseded_by_candidate` in retrieval metadata when a child is retrieved.
  - Record `temporal_strategy: "lifecycle_fields_v1"`.

Slice 3 behavior:

- Add a schema migration only after benchmark data proves the need:
  - `valid_from`
  - `valid_to`
  - `observed_at`
  - `superseded_at`
  - `revoked_at`
  - relationship labels such as `supersedes`, `contradicts`, `supports`, and `derived_from`
- Add a chronological retrieval mode for LongMemEval/LoCoMo temporal questions.

## Test Plan

Add these tests in `tests/test_store.py`:

- `test_search_with_meta_surfaces_ranked_bm25_candidates`
  - Creates multiple active memories with overlapping terms.
  - Asserts `retrieval["schema"]`, candidate rank entries, `bm25`, `score`, and deterministic ordering are present.
- `test_search_with_meta_records_fallback_rank_metadata`
  - Forces or uses a fallback query path.
  - Asserts fallback candidates have `bm25 is None`, `search_mode == "fallback"`, and text match features.
- `test_injection_receipt_records_ranking_and_packing_metadata`
  - Calls `inject()`.
  - Asserts `why(action_id)["retrieval"]` includes candidates, policy authorized/withheld IDs, and packing metadata.
- `test_context_packing_drops_over_budget_authorized_memories`
  - Creates enough authorized memories to exceed the default budget or calls the helper with a small budget.
  - Asserts over-budget IDs are not in `injected_memory_ids` and appear in `packing["budget_dropped"]`.
- `test_empty_retrieval_receipt_records_absence`
  - Calls `inject()` with no matching memories.
  - Asserts `search_mode == "none"`, candidate list is empty, packing used tokens is zero, and the receipt verifies.
- `test_expired_memory_is_not_injected_and_is_receipted`
  - Uses an expired memory if implementation adds filtering.
  - If filtering is deferred, replace with a narrower metadata-only test and keep the blocker visible.

Add this test in `tests/test_runner.py`:

- `test_run_context_uses_packed_injected_memories_only`
  - Produces a receipt with a budget-dropped authorized memory.
  - Asserts the written context contains only `receipt["memories"]` and omits dropped IDs.

Existing tests that should continue to pass:

- `test_policy_memory_can_be_promoted_and_injected`
- `test_injection_receipt_includes_memory_merkle_tree`
- `test_quarantined_memory_is_withheld`
- `test_lineage_and_revoke_descendants`
- `test_search_handles_punctuation_and_hyphenated_queries`
- `test_policy_config_denies_labeled_memory_at_injection`
- `test_run_writes_context_and_preserves_exit_code`

## Rollout Gates

Gate 1: Docs/design acceptance

```bash
git diff -- docs/RETRIEVAL_BASELINE_IMPLEMENTATION_PLAN.md docs/BENCHMARK_AND_RETRIEVAL_PLAN.md
```

Gate 2: First implementation slice

```bash
python3 -m unittest tests.test_store -q
python3 -m unittest tests.test_policy -q
python3 -m unittest tests.test_runner -q
python3 -m zerker_memory eval
```

Gate 3: Benchmark comparison readiness

```bash
python3 -m unittest tests.test_eval -q
python3 -m zerker_memory eval
```

Gate 4: Only if CLI, launch, proof, handoff, Treeship, prelaunch, or release-pack behavior changes

```bash
python3 scripts/release_smoke.py --summary-only
python3 -m zerker_memory status --summary-only
```

The first retrieval slice should not need Gate 4 if it only changes `store.py`, `tests/test_store.py`, and `tests/test_runner.py`.

## Public-Claims Guardrail

Do not publicly claim that ZMem beats Mem0, Zep, Letta, LangMem, LongMemEval, LoCoMo, or any other system/benchmark from this baseline alone.

Allowed public language after implementation:

> ZMem is adding auditable retrieval receipts that record ranked candidates, policy decisions, context packing, token budget drops, and proof roots for local verification.

Keep benchmark and competitive claims internal until:

- primary benchmark sources are verified
- dataset versions and prompt/judge configs are pinned
- local runs reproduce the result
- receipts and benchmark result hashes verify from disk
- private memory content is not published by default

Strategic boundary:

- Retrieval quality is important, but ZMem's public wedge remains proof-backed, local-first, governed memory influence.
