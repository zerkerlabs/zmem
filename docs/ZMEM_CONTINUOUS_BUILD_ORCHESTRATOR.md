# ZMem Continuous Build Orchestrator

This is the canonical operating file for Codex agents building ZMem past launch readiness. It replaces phase/week planning with parallel lanes, narrow mergeable slices, and durable logs.

## Mission

Make ZMem the best local-first memory system for AI agents by closing the frontier gaps without losing the core wedge: memory state that is local, portable, inspectable, and receipt-ready.

Use this language precisely:

- Say "verifiable memory state" or "proof-backed memory lineage".
- Do not say a memory is "provably true" just because it has a receipt.
- Treeship proves provenance, mutation history, and integrity of evidence. It does not prove semantic correctness by itself.

## Current Product Truth

As of 2026-08-10, the product has a published `v0.1.10` release and a lane-by-lane progress board:

- Progress tracker: [`ZMEM_PROGRESS_TRACKER.md`](ZMEM_PROGRESS_TRACKER.md)
- Current public release: `v0.1.10` at `a48219337abf5b70373a59d2b1ed420378d7d8c3`; `main` may contain only the docs-only publication record after that tagged feature commit.
- The release adds a tenant-local Zerker Rooms service with isolated shared/private room memory, governed context preparation, explicit omission and abstention state, retry-safe writes, and exact context commitments. Previously shipped consolidation, lifecycle, retrieval, proof, and benchmark behavior remains intact.
- There is no active broad release candidate. Broad swarms and launch oversight remain paused while the Gateway client and durable Rooms persistence are handled as a bounded cross-repo integration.

The product already has meaningful working surface:

- Local-first SQLite memory store and CLI.
- Typed memory categories already in the product surface.
- Deterministic adaptive FTS/retrieval, temporal/update-history handling, conservative morphology, and multi-hop retrieval work in progress.
- Memory event/Merkle lineage and Treeship memory proof integration paths.
- Release pack, launch proof, public verify handoffs, clean-shell operator packet, return packet, and launch asset verification.
- Benchmark harnesses for LongMemEval, LoCoMo, and the official BEAM scale layout, with metrics, isolated stores, reports, receipts, and provider metadata.
- A real ActiveGraph 1.9 pack plus compact WAL-backed batched trace runner.
- A published tenant-local Zerker Rooms memory service and explicit Gateway integration contract.
- Agent setup and handoff docs for Codex, Claude Code, Cursor, OpenClaw, Hermes, and generic MCP.
- Public landing/site work under `site/`.

The open frontier gaps are not "start from scratch". They are targeted upgrades to make the existing product top-tier.

## Frontier Blueprint Triage

Latest triage: [`FRONTIER_BLUEPRINT_TRIAGE.md`](FRONTIER_BLUEPRINT_TRIAGE.md).

The frontier report does not change the product thesis. It changes the order of attack:

1. Retrieval first: improve hybrid retrieval, retrieval depth, context expansion, and query routing before complex write-time extraction.
2. Deterministic conflict assembly: current-value conflict resolution should use explicit serial/timestamp ordering, not LLM judgment.
3. Explicit temporal state: point-in-time, current, and timeline queries need bi-temporal fields or a side table.
4. Router before graph sprawl: direct, parallel decomposition, chain-of-query, and temporal override should exist before a large graph extractor.
5. Profiles after evidence: profile/character consolidation is promising, but it should follow measurable raw episodic retrieval and conflict/temporal behavior.

Current frontier benchmark TODO, from the verified adaptive checkpoints:

1. Treat adaptive LoCoMo `0.6143` and LongMemEval `0.772` as the current local provisional checkpoints, with their explicit non-leaderboard claim boundary.
2. Keep unique run ids and isolated output directories for every run; never reuse a target while another process can touch it.
3. Keep the deterministic 227-question cohort as a safety gate, but do not require every answer to remain identical when evaluating a new retrieval architecture. Protect governance, temporal consistency, abstention, provenance, and exact-identifier behavior while requiring a meaningful full-dataset gain.
4. Freeze new one-question lexical rules unless they fix a broad correctness class. Build true dense candidates independently of FTS, then fuse lexical and dense ranks before governance and packing.
5. Keep the verified BEAM 100K, 500K, 1M, and 10M runs reproducible; broaden conversation coverage and add official model-judged scoring before making scale-quality claims.
6. Keep the runnable ActiveGraph two-run host green across the supported `activegraph>=1.9,<2` range; larger traces and aggregate Treeship proof remain optional follow-ups.
7. Record embedding model id/digest, content hash, index configuration, candidate ranks, and fusion output in the same proof artifacts used by the current retrieval modes.

Score projections, competitor comparisons, and "official benchmark" language stay internal until reproduced with pinned datasets, commands, hashes, and receipt bundles.

## Non-Negotiables

- Keep slices small enough to review and merge independently.
- Every worker must read this file before editing.
- Every worker must append a dated entry to its lane log under `docs/CONTINUOUS_BUILD/`.
- Every worker must update `docs/BUILD_LOG.md` and `docs/CURRENT_STATE.md` only with factual, bounded notes.
- Avoid editing generated `.zerker/launch-proof/` artifacts unless the task is explicitly release-pack or proof-pack work.
- Preserve user and automation changes. Do not reset, checkout, or delete unrelated work.
- No broad rewrites of `zerker_memory/store.py` or `zerker_memory/cli.py` without a focused failing test first.
- Do not add another bespoke lexical rule for a single benchmark question when an independent dense candidate source addresses the same failure class.
- New memory behavior needs tests. Docs-only slices must say they are docs-only.
- Every claim about benchmark quality must be backed by a reproducible command and an artifact hash or receipt path.
- If the working tree contains uncommitted changes outside the lane, do not edit those files. Record the overlap and choose a smaller slice or stop with a status-only update.
- Automation lanes should stop themselves from widening scope. The coordinator pauses or deletes automations only after the acceptance gates below are met.
- Do not let research-blueprint language create public benchmark claims. Primary-source links are not enough; public claims need local reproducible artifacts.

## Current Diff Review

- `v0.1.10` points to the shipped Rooms feature commit; the publication bookkeeping pass after it is docs-only and must not alter package behavior or move the release tag.
- Two pre-existing untracked duplicate files remain outside the release and must not be added or deleted by this pass.
- The next ZMem implementation branch should contain only Rooms hardening required by the Gateway contract. The Gateway Go client and durable Rooms event store belong in their owning repository; unrelated consolidation, retrieval, and scheduler work stays separate.

## Live Session Protocol

Use this when the user is present and actively working with Codex. Do not wait hours for the next cron if a lane is ready to continue.

1. Start with `git status --short`, the relevant lane log, and this orchestrator.
2. If a cron swarm just dropped changes, inspect that lane first and decide: keep, split, or exclude.
3. If the working tree is dirty, do not launch overlapping workers on the same files. Either checkpoint the reviewed slice or choose a disjoint lane.
4. Manual swarm work is allowed while the user is here, but each worker needs a narrow lane and write set.
5. Before the next scheduled automation window, leave a handoff entry in the relevant lane log with:
   - current files touched
   - tests already run
   - what is safe to continue
   - what must not be touched
   - whether the current diff should be committed first
6. If a lane cron starts while the user is actively coordinating, let it finish only if it respects the lane protocol. Otherwise pause that automation after the current run and resume after checkpointing.
7. Prefer one clean checkpoint over more parallel work once three or more lanes are dirty.

Current live-session stance:

- Keep broad recurring swarms and launch oversight paused after `v0.1.10` publication.
- Coordinate one bounded Rooms/Gateway integration at a time, with explicit ownership for the ZMem service, Gateway client, and Rooms event store.
- Keep periodic scheduling, Merkle `v2`, consolidation, and unrelated retrieval work on separate branches with separate acceptance evidence.

## Final Acceptance Gates

These gates define when the recurring build automations can be paused or deleted. Until then, the automations should keep producing small, mergeable slices.

### Global Gates

- `python3 -m unittest discover -s tests` passes locally.
- `python3 -m zerker_memory eval` passes `11/11` or the current documented successor suite.
- `python3 -m zerker_memory status --summary-only` reports workspace, doctor, memory proof, release packet, and agent handoff ready.
- The launch gate is either complete or explicitly deferred with a current handoff: public verify logs, launch assets, return packet, zmem.sh deployment, and alpha tag status are not ambiguous.
- README, QUICKSTART, product feature guide, public site, and orchestrator agree on what is built vs planned.
- No active public docs claim benchmark superiority without reproducible artifacts and proof hashes.
- All lane logs have a latest entry with: scope, files touched, behavior changed, tests, blockers, and next safe slice.

### Lane Acceptance

| Lane | Acceptance criteria | Pause/delete condition |
| --- | --- | --- |
| L0 trust-ledger | Durable mutations have receipt-visible lineage for add, promote, reject, revoke, quarantine, supersede, checkpoint/snapshot/export; trusted means verified provenance, not semantic truth | Pause after mutation receipt tests and export/verify docs pass |
| L1 temporal-kg | Current/history/superseded behavior is explicit; deterministic conflict assembly exists for current, historical, and timeline queries; `query_at(timestamp)` exists or is consciously deferred; identity disambiguation fixture passes | Pause after conflict resolver, point-in-time query, and identity tests pass |
| L2 lifecycle-compaction | Session lifecycle commands/APIs exist or are documented as deferred; checkpoint/snapshot roots are receipt-visible; context packing records injected/withheld/budget-dropped | Pause after lifecycle tests and agent handoff docs agree |
| L3 hybrid-retrieval | FTS/BM25, local provider config, retrieval depth tuning, context expansion, direct/parallel/chain query routing, graph/temporal candidates, RRF/fusion, and context-budget receipts have reproducible tests/benchmarks | Pause after benchmark matrix compares local modes with receipt hashes |
| L4 consolidation | Consolidation levels, lineage fixtures, durable jobs, verified live-source preview, private materialization, independent inspection, and explicit ceiling-bound admit/discard exist without hosted LLM dependency | Keep broad automation paused; target store-backed multi-level rollups next and treat scheduling as a later separate reviewed slice |
| L5 identity-workspaces | CLI/dashboard can show connected agents, chat/session ids, workspace ids, source URI, trust status, and proof lineage; conflict fixture exists | Pause after source report plus first conflict-resolution test pass |
| L6 benchmarks | LongMemEval/LoCoMo adapters, conflict/temporal fixture candidates, isolated DBs, metrics, receipt bundles, and public-readable reports are reproducible | Pause after local matrix report can be regenerated from documented commands |
| L7 DX-dashboard-site | Setup, MCP, dashboard, landing, feature matrix, and proof page are public-ready and mobile/desktop checked | Pause after launch QA checklist is complete |
| L8 hdc-research | Research note exists with go/no-go and no production coupling | Keep paused unless explicitly restarted |

### Automation Sunset Protocol

1. When a lane meets its acceptance criteria, append a final lane-log entry titled `Acceptance met`.
2. The coordinator verifies the lane with the listed tests and updates this file.
3. The coordinator pauses the matching automation first, not deletes it.
4. After one clean release or one week without needing the lane, delete or archive the automation.
5. Any newly discovered gap goes into the lane log as `Post-acceptance backlog` and can reactivate the automation.

## Lane Registry

| Lane | Focus | Current intent | Primary files |
| --- | --- | --- | --- |
| L0 trust-ledger | Treeship-ready memory receipts, Merkle roots, rollback evidence | Make every durable memory mutation receipt-ready and independently verifiable | `zerker_memory/treeship.py`, `zerker_memory/store.py`, `tests/test_treeship.py`, `tests/test_store.py`, `docs/TREESHIP_MEMORY_PROOF_REQUIREMENTS.md` |
| L1 temporal-kg | Bi-temporal graph layer, relation history, point-in-time queries | Upgrade existing temporal/update-history logic into explicit graph primitives | `zerker_memory/store.py`, new `zerker_memory/temporal_graph.py` if needed, `tests/test_store.py`, `tests/test_runner.py` |
| L2 lifecycle-compaction | Working/Episodic/Semantic/Procedural gates, sessions, checkpoints, snapshots | Make agent continuity explicit across context boundaries | `zerker_memory/cli.py`, `zerker_memory/store.py`, `zerker_memory/runner.py`, MCP surfaces, tests |
| L3 hybrid-retrieval | BM25/FTS + dense + graph + RRF + packing budget | Make retrieval quality top-tier while keeping local-first defaults | `zerker_memory/store.py`, `zerker_memory/retrieval_providers.py`, `zerker_memory/bench.py`, retrieval tests |
| L4 consolidation | Hierarchical memory tree and scheduled summarization | Keep long-running memory useful instead of endlessly accumulating episodes | new consolidation module, `zerker_memory/bench.py`, tests, docs |
| L5 identity-workspaces | Agent identity, workspace identity, cross-session entity resolution | Make multi-agent memory traceable by source agent, workspace, and proof lineage | workspace registry files, `zerker_memory/store.py`, dashboard/docs/tests |
| L6 benchmarks | LongMemEval/LoCoMo adapters, metrics, receipts, reproducible results | Make quality claims benchmarkable and proof-backed | `zerker_memory/bench.py`, `tests/test_bench.py`, benchmark docs |
| L7 DX-dashboard-site | MCP setup, agent instructions, dashboard, landing, product docs | Make the product self-serve for agents and humans | `site/`, docs, MCP setup, dashboard surfaces |
| L8 hdc-research | Hyperdimensional retrieval research spike | Explore only after core lanes are stable; no product coupling yet | docs/research only until approved |

## First Wave Tasks

### L0 Trust Ledger

Goal: make memory mutations auditable without turning Treeship into a dependency users have to understand.

Tasks:

1. Inventory all durable mutation paths: add/promote/reject/revoke/quarantine/supersede/checkpoint/snapshot/export.
2. Define the minimal `MemoryReceipt` envelope actually present in ZMem: memory id, action id, content hash, actor/agent id, model/prompt hashes when available, prior root, new root, timestamp, optional Treeship artifact id.
3. Add or strengthen tests that prove receipts are emitted for state transitions, not just final memories.
4. Keep `trusted_only` semantics honest: valid lineage means trusted provenance, not guaranteed truth.
5. Ensure export bundles contain enough data to verify a memory chain outside the repo.

### L1 Temporal KG

Goal: turn the current temporal retrieval behavior into explicit, queryable bi-temporal memory.

Tasks:

1. Map existing temporal metadata and tests before adding schema.
2. Add explicit fields or tables for `valid_from`, `valid_to`, `learned_at`/`recorded_from`, `superseded_at`, `superseded_by`, `unlearned_at`, and monotonic write `serial` where they do not already exist.
3. Add deterministic conflict assembly tests before general graph work: current-value -> max valid/serial, historical -> point-in-time, change-detection -> timeline.
4. Add `query_at(timestamp)` behavior for the current local store before introducing any external graph engine.
5. Preserve superseded facts and prove the current-vs-history distinction in receipt metadata.
6. Add a tiny identity-disambiguation fixture such as `Alice` vs `Alice Chen` across sessions.

### L2 Lifecycle Compaction

Goal: make long agent sessions survive context boundaries.

Tasks:

1. Inventory existing session, handoff, restore, and inject/propose behavior.
2. Add or harden `start_session`, `checkpoint_session`, `snapshot_session`, and `end_session` commands/APIs.
3. Make checkpoints emit memory events and roots.
4. Add token-budget-aware context packing receipts that show injected, withheld, and budget-dropped memory.
5. Keep the four memory classes separate enough that procedural rules do not pollute episodic recall.

### L3 Hybrid Retrieval

Goal: reach frontier retrieval quality while keeping the default local/offline path useful.

Tasks:

1. Strengthen the existing FTS/BM25 path before adding network providers.
2. Tune retrieval depth and add context expansion around nucleus hits before adding more write-time extraction.
3. Keep local pseudo-embedding/provider config paths testable with no network.
4. Add RRF fusion across keyword, dense, and temporal/graph candidates.
5. Add an adaptive router contract: direct single-hop, parallel decomposition, iterative chain-of-query, and temporal override.
6. Ensure every retrieval result can explain why a memory was retrieved, injected, withheld, expanded, or dropped.
7. Benchmark each mode with isolated DBs and reproducible artifacts.

### L4 Consolidation

Goal: prevent memory stores from becoming noisy piles.

Tasks:

1. Start with a docs-plus-test fixture defining levels: turn, session, day, week, profile/project.
2. Add a consolidation job model that is non-blocking and local-first.
3. Record source child ids and output summary ids so consolidation is reversible and auditable.
4. Add profile/character aggregation fixtures for scattered facts about the same person or project.
5. Add recall-planner tests before adding LLM summarization.
6. Do not add hosted summarization as a hard dependency.
7. Require exact preview and candidate confirmation before live materialization.
8. Keep materialized summaries quarantined and outside canonical memory until a separate reviewed admission action exists.

### L5 Identity Workspaces

Goal: make the console and APIs clear about which agents, chats, workspaces, and memory sources are connected.

Tasks:

1. Add a source model for agent id, chat/session id, workspace id, tool, repo, and optional Treeship key/artifact.
2. Make multi-agent memory sharing show source and trust status.
3. Add merge/conflict rules for two agents writing different claims about the same entity.
4. Tie identity anchors to Treeship where available, but keep ZMem usable without remote Hub access.
5. Surface this in the dashboard/console as connected agents and memory lineage.

### L6 Benchmarks

Goal: make the "top-tier memory" claim reproducible.

Tasks:

1. Keep LongMemEval and LoCoMo adapters deterministic and isolated.
2. Track accuracy, F1, recall@k, latency, token use, abstention, memory counts, and context budget behavior.
3. Store benchmark receipts and hashes.
4. Add matrix comparisons for retrieval modes.
5. Add local conflict-resolution and temporal fixture candidates before making external leaderboard claims.
6. Make public benchmark reports understandable without raw logs.
7. Treat FactConsolidation and EngramaBench as research candidates until primary-source methodology and local fixture support are pinned.

### L7 DX Dashboard Site

Goal: make ZMem delightful for both agents and humans.

Tasks:

1. Keep setup instructions concrete for Codex, Claude Code, Cursor, and MCP clients.
2. Make dashboard show connected agents, active memory stores, memory source lineage, and proof status.
3. Keep landing copy agent-native, short, and factual.
4. Keep the feature/proof matrix current with built vs planned.
5. Mobile and desktop QA must run before public deploy.

## Automation Registry

Existing automations to keep, but point them at this file:

- `zerker-memory-overnight-build-loop`: launch/readiness oversight.
- `zmem-retrieval-baseline-swarm`: L3 retrieval quality and context packing.
- `zmem-benchmark-harness-swarm`: L6 benchmark harness.

New continuous lanes to add:

- `zmem-trust-ledger-swarm`: L0, every 4 hours.
- `zmem-temporal-kg-swarm`: L1, every 4 hours.
- `zmem-lifecycle-compaction-swarm`: L2, every 6 hours.
- `zmem-consolidation-swarm`: L4, every 8 hours.
- `zmem-identity-workspaces-swarm`: L5, every 8 hours.

Each automation must write to its lane log and include the exact tests it ran. If it cannot run tests, it must say why.

## Worker Write Protocol

Every worker entry must use this shape:

```md
## 2026-06-22T00:00:00Z - <lane> - <agent or automation id>

- Scope:
- Files touched:
- Behavior changed:
- Tests:
- Artifacts/receipts:
- Blockers:
- Next safe slice:
```

Do not paste long transcripts. Store raw output only when the command itself produced an artifact intended for review.

## Merge Protocol

1. Prefer one lane per branch or one narrow slice per commit.
2. Before merging, run the smallest relevant test first, then a broader suite if shared surfaces changed.
3. If two lanes touch `store.py` or `cli.py`, merge the narrower tested slice first and rebase the other lane.
4. The coordinator reconciles lane logs into this orchestrator. Workers should append, not reorder.
5. The product status page must only mark a feature "built" after code, tests, and user-facing docs agree.

## Latest Coordinator Entries

## 2026-06-22 - coordinator - continuous build launch

- Scope: converted the frontier gap report into lane-based continuous build operations.
- Files touched: this orchestrator plus `docs/CONTINUOUS_BUILD/` lane logs.
- Behavior changed: none yet.
- Tests: not applicable for docs scaffolding.
- Blockers: existing dirty docs from active automation need preservation during future merges.
- Next safe slice: update automation prompts and launch first-wave Codex workers for L0/L1/L2/L4/L5.
