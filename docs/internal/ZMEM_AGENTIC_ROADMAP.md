# ZMem Agentic Roadmap

Last audit: 2026-06-22

This is the control-plane roadmap for agentic ZMem work. It is not a calendar. Each lane should keep improving until its evidence gate is green, honestly blocked, or deliberately paused by the coordinator.

## North Star

Make ZMem the best memory product for AI agents by combining frontier retrieval quality with local-first trust, portability, provenance, receipts, verification, handoff, and reproducible benchmarks.

The public promise is:

- agents remember across sessions,
- users can inspect and govern what memory influenced an action,
- teams can verify memory lineage and benchmark evidence,
- benchmark claims are reproducible before they become marketing claims.

## Current State

Confirmed from this audit:

- Public surfaces are live: `zmem.sh` and `docs.zmem.sh`.
- Public routed docs are under `docs/content/docs/**`; `docs/internal/**` and top-level operator markdown must stay non-routed.
- The public site/docs no longer show the internal strict-publish gate language in routed public content.
- `python3 -m zerker_memory status --summary-only` reports workspace, doctor, memory proof, release packet, and manual agent pack ready.
- `python3 -m zerker_memory eval` passes `11/11`.
- Focused verification passed for benchmark scripts, consolidation fixture, store, snapshot, and workspace tests.
- Local benchmark artifacts exist for synthetic, LongMemEval-style, and LoCoMo-style runs with matrix/comparison hashes.
- The strict public publish gate remains an internal release-evidence gate, not a product readiness gate: public verify logs are `0/6`, launch assets are `0/8`, and return packet is not ready.
- Local `main` is ahead of `origin/main` by multiple continuous-build commits. Treat those commits as pending review/checkpoint work before pushing.
- Dirty files remain in continuous-build docs and core benchmark/store tests. Preserve them unless the lane explicitly owns them.

## Public Claim Boundary

Allowed publicly now:

- ZMem is local-first memory for AI agents.
- ZMem records receipts for what memory influenced an action.
- ZMem can produce proof-backed local benchmark evidence.
- ZMem has local synthetic, LongMemEval-style, and LoCoMo-style harness paths.

Not allowed publicly yet:

- official LongMemEval or LoCoMo ranking,
- superiority over Mem0, Zep, Letta, or another vendor,
- "provably true memory",
- internal clean-shell logs, launch assets, operator packets, return packets, or swarm status.

Use "proof-backed memory lineage" and "verifiable memory state." Do not imply receipts prove semantic truth.

## Coordination Rules

1. Start every lane run with `git status --short --branch`, this file, and the relevant lane log under `docs/CONTINUOUS_BUILD/`.
2. Do not edit files owned by another dirty lane unless the coordinator explicitly chooses to merge lanes.
3. Every behavior change needs a focused test or a documented reason no test applies.
4. Every benchmark claim needs a dataset/source path, conversion command, result artifact, hash, and verification path.
5. Public copy must be user/builder-facing. Internal launch operations stay in `docs/internal/**`, `.zerker/launch-proof/**`, or top-level non-routed operator docs.
6. Prefer small checkpoint commits by lane over accumulating broad cron output.
7. If three or more lanes are dirty, checkpoint or split before launching more workers.

## Lane Board

### L7 Frontend + Public Copy

Mission: Make `zmem.sh` and `docs.zmem.sh` clear, credible, beautiful, and free of internal operator language.

Primary inputs:

- `site/src/**`
- `docs/app/**`
- `docs/content/docs/**`
- `docs/internal/**` only as private source material

Current evidence:

- Public scan found no routed occurrences of strict-publish/clean-shell/launch-asset leakage after latest cleanup.
- `docs.zmem.sh` and `zmem.sh` deploy through Vercel.

Next queue:

- Audit homepage, `/proof`, `/docs`, and docs landing for clarity against real user jobs.
- Turn proof copy into "what influenced the agent" and "how to verify lineage," not launch-readiness language.
- Make benchmark pages honest but more compelling with sample local evidence.
- Add screenshots only when they show real product surfaces, not internal packets.

Fast checks:

- `rg -n "Strict public publish|clean-shell|launch assets|operator packet|return packet|public verify" site/src docs/app docs/content/docs`
- `npm run build` in `docs/`
- Vercel deployment status for `zmem-site` and `zmem-docs`

Final evidence gate:

- Public pages return 200 and contain no internal launch-ops wording.
- Docs nav is user/builder-oriented.
- Proof and benchmark pages are honest, understandable, and externally legible.

Blocked conditions:

- No access to deployment status or screenshots when visual QA is required.

### L6 Benchmark + Retrieval Evidence

Mission: Make LoCoMo/LongMemEval-style evidence reproducible, fast to inspect, and impossible to overclaim.

Primary inputs:

- `zerker_memory/bench.py`
- `scripts/bench/**`
- `tests/test_bench.py`
- `tests/test_bench_scripts.py`
- `.zerker/bench/**`
- `docs/BENCHMARK_*`
- `docs/CONTINUOUS_BUILD/benchmark.log.md`

Current evidence:

- Official conversion/scoring scripts exist under `scripts/bench/`.
- `tests.test_bench_scripts` passes.
- Matrix artifacts exist with hashes for synthetic, LongMemEval-style, and LoCoMo-style runs.
- Full matrix verification can be heavy; it is not yet a good cheap audit check.

Next queue:

- Add a tiny fixture-backed smoke for the documented `--mode zmem-retrieval` path.
- Add fast summary verification for matrix/comparison artifacts so agents can inspect benchmark health without long artifact replays.
- Pin dataset hashes and conversion commands for any run considered publishable.
- Add conflict/temporal benchmark slices before public comparison claims.
- Build a benchmark panel that separates local evidence, provisional scored runs, and official submissions.

Fast checks:

- `python3 -m unittest tests.test_bench_scripts -q`
- `python3 -m unittest tests.test_bench.BenchmarkHarnessTest.<focused_test> -q`
- artifact hash scan for `.zerker/bench/*/benchmark-matrix.json`

Final evidence gate:

- Reproducible command regenerates local matrix, dashboard, public benchmark page, hashes, and receipt bundles.
- Public benchmark copy uses only allowed claims.

Blocked conditions:

- Missing licensed official datasets.
- Missing API key for optional LLM judging.
- No pinned dataset/version/hash for a public claim.

### L3 Retrieval Quality

Mission: Make retrieval frontier-grade before adding broad write-time graph complexity.

Primary inputs:

- `zerker_memory/store.py`
- `zerker_memory/retrieval_providers.py`
- `zerker_memory/runner.py`
- `tests/test_store.py`
- `tests/test_runner.py`
- `docs/CONTINUOUS_BUILD/hybrid-retrieval.log.md`

Current evidence:

- FTS baseline, context packing, support-chain reservation, chronology support backfill, and receipt-visible retrieval decisions are active.
- Recent focused store/runner tests have passed in lane logs.

Next queue:

- Extend explicit support-chain reservation to target-history prompts.
- Add retrieval depth/context expansion regression around nucleus hits.
- Add router contracts: direct, parallel decomposition, chain-of-query, temporal override.
- Add RRF/fusion contract after local keyword/temporal path is stable.
- Keep every retrieved/injected/withheld/budget-dropped decision receipt-visible.

Fast checks:

- focused `tests.test_store` retrieval test
- focused `tests.test_runner` injection/context test
- `python3 -m zerker_memory eval`

Final evidence gate:

- Benchmark matrix compares retrieval modes with receipt hashes and shows accuracy, latency, token, and memory-count tradeoffs.

Blocked conditions:

- Dirty overlap in `store.py` or `bench.py` from another lane.

### L1 Temporal + Conflict Intelligence

Mission: Make current/history/timeline behavior deterministic, queryable, and receipt-visible.

Primary inputs:

- `zerker_memory/store.py`
- `tests/test_store.py`
- `tests/test_runner.py`
- `docs/CONTINUOUS_BUILD/temporal-kg.log.md`

Current evidence:

- `query_at(timestamp)` exists as a derived projection over events plus parent lineage.
- Tests cover learned-vs-valid time and `Alice` vs `Alice Chen` identity separation.

Next queue:

- Port explicit same-subject update/restatement supersession rules into `query_at`.
- Decide whether `inject`/`why` should surface derived temporal envelopes.
- Add current-value, historical, and timeline conflict assembly fixtures.
- Add monotonic serial/valid-time side table only after tests show projection is insufficient.

Fast checks:

- focused `query_at` tests
- `python3 -m unittest tests.test_store -q`

Final evidence gate:

- Current, historical, changed, and timeline questions resolve deterministically with receipt-visible candidates and chosen rule.

Blocked conditions:

- Schema migration needs broader review.

### L0 Proof + Provenance

Mission: Make every durable memory mutation explainable without claiming semantic truth.

Primary inputs:

- `zerker_memory/store.py`
- `zerker_memory/treeship.py`
- `zerker_memory/exporter.py`
- `tests/test_store.py`
- `tests/test_snapshot.py`
- `tests/test_treeship.py`
- `docs/CONTINUOUS_BUILD/trust-ledger.log.md`

Current evidence:

- Add/source write receipts exist.
- `promote()` now emits a mutation receipt chain.
- Snapshot export preserves ordered write receipts.

Next queue:

- Add mutation receipts for `reject`, `revoke`, and `forget`.
- Add one CLI/report surface that summarizes ordered memory receipt chains.
- Build the memory-poisoning incident reconstruction demo: poisoned write -> later action -> receipt-chain traceback.
- Keep Treeship optional and explain it as public proof export, not product dependency.

Fast checks:

- focused mutation receipt tests
- `python3 -m unittest tests.test_snapshot -q`
- `python3 -m zerker_memory eval`

Final evidence gate:

- A memory can be traced from current action back through mutation/source receipts to source session/tool metadata, with bundle verification.

Blocked conditions:

- Missing actor/session/source metadata in older receipts must be labeled as legacy or unknown, not invented.

### L4 Consolidation + Dedupe

Mission: Prevent memory from becoming a noisy pile while preserving reversibility and provenance.

Primary inputs:

- `zerker_memory/consolidation.py`
- `tests/test_consolidation.py`
- `docs/CONSOLIDATION_FIXTURE.md`
- `docs/CONTINUOUS_BUILD/consolidation.log.md`

Current evidence:

- First fixture helpers and tests exist.
- No durable job table, scheduler, or runtime summary writer yet.

Next queue:

- Add non-blocking local consolidation job model.
- Persist source-child ids and output summary ids.
- Add profile/project aggregation fixture.
- Add dedupe/clustering status for console before hosted summarization.

Fast checks:

- `python3 -m unittest tests.test_consolidation -q`

Final evidence gate:

- Consolidation creates reversible, auditable summaries without requiring hosted LLMs.

Blocked conditions:

- Any hosted summarization dependency proposed as default path.

### L5 Identity + Workspaces + Agent Handoff

Mission: Make multi-agent, multi-session, multi-project memory understandable and switchable.

Primary inputs:

- `zerker_memory/workspaces.py`
- `zerker_memory/cli.py`
- `zerker_memory/dashboard.py`
- `tests/test_workspaces.py`
- `tests/test_cli_onboarding.py`
- `.zerker/agents/**`
- `docs/CONTINUOUS_BUILD/identity-workspaces.log.md`

Current evidence:

- Agent handoff reports ok for Codex, Claude Code, Cursor, OpenClaw, Hermes, and generic MCP.
- `workspace sources` exists as a read-only JSON lineage report.
- Status currently shows a profile match mismatch that should be clarified: current profile is `treeship.dev`, matched workspace is `Zerker Memory`.

Next queue:

- Add human-readable `workspace sources` summary.
- Add dashboard card for connected agents, workspace ids, source URI, trust status, and proof lineage.
- Design memory store switching for multiple projects/sessions.
- Add source-level conflict/merge fixture.

Fast checks:

- `python3 -m unittest tests.test_workspaces -q`
- focused CLI onboarding parser tests
- `python3 -m zerker_memory status --summary-only`

Final evidence gate:

- A user can see which project/session/agent wrote memory, switch stores intentionally, and hand off verified state.

Blocked conditions:

- Ambiguous workspace identity cannot be silently papered over.

### L2 Lifecycle + Context Boundaries

Mission: Make long-running agent sessions survive context windows and restarts.

Primary inputs:

- `zerker_memory/cli.py`
- `zerker_memory/store.py`
- `zerker_memory/runner.py`
- MCP surfaces
- snapshots/handoff tests
- `docs/CONTINUOUS_BUILD/lifecycle-compaction.log.md`

Current evidence:

- Handoff, snapshots, restore, and action receipts exist.
- Lane is seeded but not deeply implemented.

Next queue:

- Inventory session, checkpoint, snapshot, handoff, inject, and propose flows.
- Define `start_session`, `checkpoint_session`, `snapshot_session`, and `end_session` contract or document deferral.
- Make checkpoint roots receipt-visible.
- Ensure context packing records injected, withheld, and budget-dropped memory.

Fast checks:

- focused snapshot/handoff tests
- `python3 -m zerker_memory status --summary-only`

Final evidence gate:

- Agent can resume from checkpoint/handoff with approved memory and proof context, not pasted transcripts.

Blocked conditions:

- Session schema change without migration/test plan.

### L8 Research Watch

Mission: Evaluate promising frontier memory papers without coupling production to unverified architecture.

Primary inputs:

- `docs/FRONTIER_BLUEPRINT_TRIAGE.md`
- future research notes under `docs/internal/research/**`

Current evidence:

- Research triage says retrieval-first, deterministic conflict, temporal dispatch, and consolidation after evidence.

Next queue:

- Pin primary-source claims.
- Convert each useful idea into a local fixture or reject it.
- Keep projected scores internal.

Fast checks:

- claim inventory separates confirmed, approximate, blocked, and speculative.

Final evidence gate:

- Research produces buildable lane tickets or explicit no-go decisions.

Blocked conditions:

- Source cannot be verified or cannot become a reproducible fixture.

## Immediate Coordinator Queue

1. Review local commits ahead of `origin/main`: `20469a7`, `5a56571`, `a8b26ae`, `612ce4b`. Decide whether to push, split, or hold.
2. Keep `.treeship/`, `data/`, and generated/runtime outputs uncommitted unless explicitly reviewed.
3. Stabilize dirty lane files before spawning more overlapping work.
4. Give L7 this thread as the public/frontend/copy specialist lane.
5. Give L6 and L3 separate implementation threads so benchmark/retrieval work does not collide with public copy.
6. Add the fast benchmark artifact verification path so future agents can inspect benchmark health cheaply.
7. Start the memory-poisoning incident reconstruction demo only after L0 receipt-chain summary is visible to a human.

## Done Definition For This Roadmap

This roadmap is useful when a fresh agent can:

- identify the correct lane,
- read the right files,
- avoid public/private boundary mistakes,
- know the next safe slice,
- know the fast checks,
- know the final evidence gate,
- stop honestly when blocked.

