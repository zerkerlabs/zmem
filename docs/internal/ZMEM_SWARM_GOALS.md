# ZMem Swarm Goal Pack

Last updated: 2026-06-22

Use this file to launch focused Codex lane work from `docs/internal/ZMEM_AGENTIC_ROADMAP.md`. Each goal is a lane contract, not a calendar. Keep one lane narrow, run its fast checks, update its lane log, and stop before broad overlap.

## Coordinator Rule

Before spawning or resuming any lane:

1. Read `docs/internal/ZMEM_AGENTIC_ROADMAP.md`.
2. Run `git status --short --branch`.
3. Read the lane log under `docs/CONTINUOUS_BUILD/`.
4. Avoid files already dirty from another lane unless the coordinator explicitly chooses to merge the work.
5. Update the lane log with scope, files touched, behavior changed, tests, artifacts, blockers, and next safe slice.

## L7 Frontend + Public Copy

```text
/goal Outcome: Keep zmem.sh and docs.zmem.sh clear, credible, beautiful, and free of internal operator language. Improve public copy and UX around memory, receipts, benchmarks, proof, docs, and install flows without touching backend behavior unless a tiny public-surface fix requires it.

Context: Work mainly in site/src/**, docs/app/**, and docs/content/docs/**. Use docs/internal/** and top-level operator markdown only as source material. Public copy must explain local-first memory, provenance, receipt verification, handoff, and benchmark evidence in user/builder language.

Constraints: Do not expose clean-shell logs, launch assets, operator packets, return packets, strict-publish blockers, private swarm state, or unsupported benchmark rankings. Do not claim receipts prove semantic truth. Preserve unrelated dirty work.

Verify: Run a public-copy scan for internal launch terms, build docs when docs changed, check relevant live/local routes when possible, and list changed files plus exact copy/UX risk removed.

Iterate/done/stop: Pick the most confusing public surface, fix it, verify it, and update handoff notes. Done only when public pages are externally legible and no internal terms leak. Stop for deploy credentials or visual QA access if required.
```

## L6 Benchmark + Retrieval Evidence

```text
/goal Outcome: Make ZMem benchmark evidence reproducible, fast to inspect, and safe to publish without overclaiming. Advance one narrow L6 slice that improves fixture-backed LongMemEval/LoCoMo/synthetic evidence, scoring, summary verification, or benchmark reporting.

Context: Work mainly in zerker_memory/bench.py, scripts/bench/**, tests/test_bench.py, tests/test_bench_scripts.py, docs/BENCHMARK_*, .zerker/bench/** for local evidence, and docs/CONTINUOUS_BUILD/benchmark.log.md. Treat official datasets as local/untracked unless license policy says otherwise.

Constraints: Do not claim official rankings or vendor superiority without pinned dataset source, conversion command, scoring command, artifact hashes, and receipt bundles. Do not commit downloaded data/ or generated runtime outputs. Preserve unrelated dirty work.

Verify: Prefer focused benchmark tests and a fast artifact/summary check over long full-matrix replay. Record commands, hashes, changed files, artifacts, and remaining claim boundaries in the lane log.

Iterate/done/stop: Choose the highest-leverage missing evidence path, add the smallest test or tool improvement, verify, and stop before broad retrieval rewrites. Stop if datasets/API keys are unavailable and label the blocked evidence.
```

## L3 Retrieval Quality

```text
/goal Outcome: Improve ZMem retrieval quality one measurable slice at a time while keeping every retrieval decision receipt-visible. Prioritize retrieval depth, context expansion, temporal support chains, query routing, and mode comparison before broad graph extraction.

Context: Work mainly in zerker_memory/store.py, zerker_memory/retrieval_providers.py, zerker_memory/runner.py, tests/test_store.py, tests/test_runner.py, zerker_memory/bench.py only when a benchmark check is part of the slice, and docs/CONTINUOUS_BUILD/hybrid-retrieval.log.md.

Constraints: Do not broadly rewrite store.py without a failing/focused test. Do not add hosted providers as required defaults. Keep retrieved, injected, withheld, expanded, and budget-dropped decisions explainable in receipts. Preserve unrelated dirty work.

Verify: Run focused store/runner tests and zmem eval; when possible, connect the behavior to a benchmark fixture or matrix artifact. Update the lane log with behavior changed and next safe retrieval slice.

Iterate/done/stop: Pick one retrieval failure family, write/extend the smallest regression, implement the minimal fix, verify, then stop. Stop for overlapping dirty store/bench files unless coordinator approves integration.
```

## L1 Temporal + Conflict Intelligence

```text
/goal Outcome: Make current/history/timeline behavior deterministic, queryable, and receipt-visible. Advance one narrow L1 slice around query_at, explicit supersession, valid/learned time, identity disambiguation, or deterministic conflict assembly.

Context: Work mainly in zerker_memory/store.py, tests/test_store.py, tests/test_runner.py, and docs/CONTINUOUS_BUILD/temporal-kg.log.md. Existing query_at is a derived projection over events plus parent lineage.

Constraints: Do not add schema complexity before a focused contract proves projection is insufficient. Do not collapse unrelated identities. Do not use LLM judgment for deterministic current-value conflicts. Preserve unrelated dirty work.

Verify: Run focused temporal/conflict tests plus broader store tests when the store changes. Record current/historical/timeline rule, candidate set, chosen rule, and receipt visibility in the lane log.

Iterate/done/stop: Pick one temporal query family, lock behavior with a test, implement minimal logic, verify, and stop. Stop if migration design is needed and write the migration question instead of improvising.
```

## L0 Proof + Provenance

```text
/goal Outcome: Make memory provenance and mutation lineage independently inspectable without claiming semantic truth. Advance one narrow L0 slice around ordered write receipts, mutation receipts, bundle/export verification, or human-readable receipt-chain summaries.

Context: Work mainly in zerker_memory/store.py, zerker_memory/treeship.py, zerker_memory/exporter.py, tests/test_store.py, tests/test_snapshot.py, tests/test_treeship.py, and docs/CONTINUOUS_BUILD/trust-ledger.log.md.

Constraints: Receipts prove provenance, integrity, lineage, and influence, not truth. Treeship stays optional. Do not change public copy except internal lane docs. Preserve existing source-provenance semantics while adding mutation chain visibility.

Verify: Run focused mutation/bundle/snapshot tests and zmem eval when proof behavior changes. Record fields proven, artifacts emitted, legacy unknowns, and next missing mutation path.

Iterate/done/stop: Pick one missing receipt-chain surface or mutation path, add a focused test, implement minimally, verify, and stop. Stop if older receipts lack metadata; label unknowns instead of inventing fields.
```

## L5 Identity + Workspaces + Agent Handoff

```text
/goal Outcome: Make multi-agent, multi-session, multi-project memory understandable and switchable. Advance one narrow L5 slice that clarifies workspace identity, source lineage, connected agents, trust status, or handoff visibility without changing write paths unless required.

Context: Work mainly in zerker_memory/workspaces.py, zerker_memory/cli.py, zerker_memory/dashboard.py, tests/test_workspaces.py, tests/test_cli_onboarding.py, .zerker/agents/**, and docs/CONTINUOUS_BUILD/identity-workspaces.log.md.

Constraints: Do not silently paper over workspace identity mismatches. Avoid schema migrations unless a test proves they are required. Keep source URI, agent id, chat/session id, workspace id, trust status, and proof lineage explicit. Preserve unrelated dirty work.

Verify: Run focused workspace/CLI tests and zmem status. Update the lane log with source fields shown, user-visible command/surface, and any remaining ambiguity.

Iterate/done/stop: Pick one visibility gap, add a human-readable or dashboard-ready surface, verify, and stop. Stop if switching semantics require product decision.
```

## L4 Consolidation + Dedupe

```text
/goal Outcome: Prevent memory stores from becoming noisy piles while preserving reversibility and provenance. Advance one narrow L4 slice around consolidation levels, dedupe/clustering fixtures, non-blocking local jobs, source-child lineage, or profile/project aggregation.

Context: Work mainly in zerker_memory/consolidation.py, tests/test_consolidation.py, docs/CONSOLIDATION_FIXTURE.md, and docs/CONTINUOUS_BUILD/consolidation.log.md.

Constraints: Do not require hosted LLM summarization. Do not replace raw episodes with only lossy summaries. Every summary/dedupe output must keep source child ids and be reversible/auditable. Preserve unrelated dirty work.

Verify: Run tests/test_consolidation.py and any focused recall/planner tests. Record job states, lineage, artifacts, blockers, and next safe slice in the lane log.

Iterate/done/stop: Pick one fixture or job-model gap, implement minimally, verify, and stop. Stop if runtime summarization policy is needed.
```

## L2 Lifecycle + Context Boundaries

```text
/goal Outcome: Make long-running agent sessions survive context windows and restarts. Advance one narrow L2 slice around session lifecycle, checkpoints, snapshots, handoff, restore, or context-boundary receipts.

Context: Work mainly in zerker_memory/cli.py, zerker_memory/store.py, zerker_memory/runner.py, MCP surfaces, snapshot/handoff tests, and docs/CONTINUOUS_BUILD/lifecycle-compaction.log.md.

Constraints: Do not introduce session schema changes without focused tests and migration plan. Keep checkpoint roots and injected/withheld/budget-dropped memory receipt-visible. Preserve unrelated dirty work.

Verify: Run focused snapshot/handoff/session tests and zmem status. Update the lane log with commands/APIs touched, artifacts emitted, and next safe slice.

Iterate/done/stop: Pick one lifecycle boundary, add or clarify its contract, verify, and stop. Stop if session product semantics are ambiguous.
```

## L8 Research Watch

```text
/goal Outcome: Turn frontier memory research into buildable or rejected ZMem lane tickets without coupling production to unverified architecture. Advance one narrow research note or fixture proposal with primary-source support and claim boundaries.

Context: Work mainly in docs/FRONTIER_BLUEPRINT_TRIAGE.md and docs/internal/research/**. Use primary sources and local fixture potential as the evidence standard.

Constraints: Separate confirmed findings, approximate support, blocked claims, and speculation. Do not publish projected scores or competitor superiority. Do not require hosted LLM extraction as default product architecture.

Verify: Produce a claim inventory, evidence map, recommended lane ticket or no-go decision, and public-claim boundary.

Iterate/done/stop: Pick one research idea, pin sources, decide build/no-go, and stop. Stop if the source cannot be verified.
```

