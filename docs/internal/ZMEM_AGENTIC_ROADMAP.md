# ZMem Agentic Roadmap

Last audit: 2026-07-20

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

- `v0.1.7` is the current public release; GitHub release, wheel reinstall, site, docs, CI, eval `11/11`, public proof `6/6`, launch assets `8/8`, and return packet are green.
- Broad recurring swarms and launch oversight remain paused. Work should proceed as explicit bounded slices from a clean checkpoint.
- The stable retrieval gate is `160/227`; full local LoCoMo is `1,220/1,986` (`0.6143`) and LongMemEval is `386/500` (`0.772`). These remain provisional local evidence, not leaderboard claims.
- ActiveGraph pack discovery, batching, pre-call recall, compact traces, and the two-run host are implemented and verified.
- The July 20 Moltbook signal prioritizes cold-start handoff, memory-as-state, silent-success/failure memory, and proof of the exact context admitted to an action.
- Current unreleased work adds a canonical `zerker.memory_context.v1` digest, policy digest, persisted compact commitment, wrapped-run environment binding, Treeship export, and ActiveGraph read-proof binding without changing retrieval or SQLite schema.
- True local dense candidate generation remains the highest-leverage retrieval project. Stop adding one-question lexical rules unless a safety regression requires one.
- Skill installation authority, delegated capabilities, and side-effect enforcement belong primarily to Treeship plus a future Guard/runtime layer. ZMem may retain their trust state as governed memory but should not become a package manager.

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

- Official conversion/scoring scripts and compact artifact verifiers exist under `scripts/bench/`.
- Verified local evidence exists for full LoCoMo, LongMemEval, and official-layout BEAM 100K/500K/1M/10M runs.
- ActiveGraph compact traces avoid per-question receipt-bundle explosion.
- LLM-judged results remain pending until an external judge completes; unjudged answers do not count as failures or public claims.

Next queue:

- Keep dataset hashes, conversion commands, result hashes, and claim boundaries pinned for every publishable run.
- Add an official model-judged BEAM path and broader multi-conversation scale coverage.
- Compare true dense and fused retrieval against the frozen lexical baseline only after the stable cohort passes.
- Keep the benchmark panel separated into local evidence, provisional scored runs, and official submissions.

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

- Adaptive FTS/BM25, context packing, temporal routing, semantic backfill, RRF, and bounded morphology/completion/transcript support are active and receipt-visible.
- The stable gate is `160/227`; full LoCoMo is `1,220/1,986` and LongMemEval is `386/500`.
- The lexical rule effort-to-gain curve has flattened. Provider reranking of lexical candidates is not independent dense recall.

Next queue:

- Add true local dense candidate generation independent of FTS.
- Fuse lexical and dense candidate ranks behind the unchanged policy, packing, and receipt boundary.
- Require zero stable-cohort regressions and a meaningful full-dataset gain before making dense the recommended mode.
- Keep model id, model artifact digest, query digest, candidate-source ranks, and fusion decision receipt-visible without storing raw vectors in portable proofs.

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

- `query_at(timestamp)` plus current/history/future/superseded/learned/unlearned projections are implemented.
- Inject receipts and runtime context preserve temporal subsets, selection ordering, conflicts, omissions, and abstention envelopes.
- Same-subject updates can supersede prior state without requiring explicit parent edges.

Next queue:

- Add benchmark-backed contradiction and stale-state abstention coverage.
- Add richer temporal filters and relation traversal only where fixtures prove the projection is insufficient.
- Keep bi-temporal schema migration deferred until query/runtime evidence requires it.

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

- Add/source, promote, reject, revoke, forget, checkpoint, snapshot, and restore receipts exist.
- Compact receipt bundle v2 uses Merkle witnesses while legacy v1 remains verifiable.
- Optional Treeship write attestation signs compact write-receipt digests.
- Current unreleased work commits the exact `zerker.memory_context.v1` artifact and carries its digest into Treeship proof.

Next queue:

- Finish the memory-context commitment verification and portable handoff path.
- Add one CLI/report surface that summarizes ordered per-memory mutation chains.
- Build the poisoned-memory and silent-success incident reconstruction demos.
- Design Merkle v2 only with domain separation, leaf-count binding, mixed v1/v2 verification, and migration fixtures.

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

- Deterministic fixtures, append-only job lifecycle, source-child ids, duplicate suppression, and reversible summary payloads exist.

Next queue:

- Source consolidation candidates from the live store.
- Add the runtime summary writer and a read-only status/report surface.
- Keep summaries reversible and linked to source children; consolidation must not mask weak retrieval.

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
- `workspace sources --summary-only` and dashboard source reports expose claims, conflicts, and unresolved exact ties.
- Handoff/restore carries verified state across agents and machines.

Next queue:

- Persist explicit merge decisions and source-lineage detail.
- Add durable identity keys/anchors and intentional multi-store switching.
- Make connected agent, workspace, source URI, trust status, and proof lineage easy to scan in the console.

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

- Session start/end, checkpoint, snapshot, retention summaries, handoff, restore, action receipts, and committed runtime context exist.
- Context packing records admitted, withheld, and budget-dropped memory.

Next queue:

- Build the scheduled-agent cold-start workflow over the existing primitives.
- Add wall-clock gap audit, stale/unknown-state summary, and next-run checkpoint guidance.
- Add write-facing lifecycle UX only where it reduces setup friction without widening agent authority.

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

1. [x] Finish and verify the canonical memory-context commitment across inject, `why`, wrapped runs, Treeship export, ActiveGraph recall, CLI summaries, and public docs.
2. [x] Package that bounded L0/L2 slice from a clean diff before starting dense retrieval work.
3. [x] Build one scheduled-agent cold-start path from existing handoff/session primitives: restore, gap audit, admissibility report, run, checkpoint, and portable proof.
4. [x] Add typed failure memory around expected invariant, observed outcome, confidence, correction, and invalidation without confusing HTTP success with verified state-transition success.
5. [ ] Start true local dense candidate generation in an isolated L3 branch. Fuse dense and lexical candidates behind the existing policy/receipt boundary and require stable-gate safety plus meaningful full-dataset gain.
6. [ ] Keep benchmark output directories isolated and rerun full LoCoMo/LongMemEval only after the stable cohort passes.
7. [ ] Keep `.treeship/`, `.zerker/bench/`, datasets, build output, and other generated/runtime state uncommitted unless explicitly reviewed.

## Done Definition For This Roadmap

This roadmap is useful when a fresh agent can:

- identify the correct lane,
- read the right files,
- avoid public/private boundary mistakes,
- know the next safe slice,
- know the fast checks,
- know the final evidence gate,
- stop honestly when blocked.
