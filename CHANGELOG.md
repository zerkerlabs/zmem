# Changelog

All notable Zerker Memory alpha changes are summarized here.

## Unreleased

### Benchmark Operations

- Made `--compact-artifacts` effective for LongMemEval matrices and direct runs. Compact execution now uses per-session ephemeral stores, omits per-question bundles and the run database, and leaves normal proof-rich runs unchanged.
- Added direct `zmem bench run ... --compact-artifacts` support so recorded reproducibility commands are executable.
- Bounded summary-only memory-count and efficiency deltas to ten examples plus an omitted count.
- Completed a verified local `500`-question LongMemEval matrix: `fts-multihop` scored `0.780` versus `0.740` for FTS, pseudo-embedding, and pseudo-rerank; it recovered `20` questions with zero losses and all modes passed `30/30` abstention questions. These remain provisional local results, not leaderboard claims.

## 0.1.3 - 2026-07-10

### Security And Control

- Added explicit MCP capability profiles. `agent` is now the default and exposes only proposal, governed injection, explanation, and verification; trusted writes, review, external imports, snapshots, and restore require `--profile operator`.
- Prevented agent proposals from claiming human/system provenance, and updated generated Codex, Claude Code, Cursor, OpenClaw, Hermes, and generic MCP configs to request the agent profile explicitly.
- Hardened local SQLite defaults with user-private database permissions, a private default `.zerker` directory, WAL mode, a five-second busy timeout, foreign keys, and normal synchronous durability for multi-agent local use.

### Product And Builder Experience

- Added bounded `zmem inject --summary-only` and `zmem why --summary-only` views while preserving JSON as the default machine contract.
- Reworked the public hero around the plain-language promise: agents remember across runs while users retain local review, revocation, and proof controls.
- Removed internal benchmark backlog from the homepage, corrected the public Python requirement to 3.10+, and replaced the broken short installer URL with the verified raw GitHub installer.
- Updated LoCoMo docs with the current local FTS and FTS-multihop evidence, explicit non-leaderboard claim boundaries, unique run ids, and compact artifact guidance.
- Added site lint/build and docs typecheck/build jobs to GitHub Actions.
- Updated the docs dependency set and pinned fixed PostCSS/Lodash transitive releases; docs audit and site production-dependency audit now report zero vulnerabilities.

### Portable Proof

- Added `zerker.receipt_bundle.v2` as the default receipt bundle format. It commits to the complete pre-action event log while carrying only indexed Merkle witnesses for supporting write events and the final pre-action anchor.
- Kept `zerker.receipt_bundle.v1` verification intact and exposed explicit legacy generation through `MemoryStore.receipt_bundle(action_id, compact=False)`.
- Switched CLI exports, handoffs, Treeship statements, and benchmark bundle consumers to compact v2 by default without changing their command surface.
- Added witness tamper, missing-provenance-witness, legacy compatibility, and serialized-size regression coverage. A 31-event repeated-action fixture measured 35,453 bytes for v2 versus 963,288 bytes for v1, a 96.32% reduction; both artifacts verified successfully.
- Kept the claim boundary explicit: bundle verification proves inclusion and provenance relative to an anchored Merkle root, not semantic truth.

### Verification

- `python3 -m unittest discover -s tests -q` (`1215` tests)
- `python3 -m zerker_memory eval` (`11/11`)
- `python3 scripts/release_smoke.py --summary-only`
- `npm ci && npm run lint && npm run build` in `site/`
- `npm ci && npm run typecheck && npm run build` in `docs/`
- Production-preview browser QA at desktop, tablet, and mobile with a clean console

## 0.1.2 - 2026-07-06

### Shipped

- Landed the continuous swarm hardening checkpoint across trust ledger, temporal memory, lifecycle receipts, retrieval ordering, consolidation lineage, workspace source identity, dashboard reporting, and release proof tracking.
- Hardened trust-ledger mutation coverage for promoted, rejected, revoked, forgotten, checkpointed, snapshotted, and restored memory state.
- Expanded temporal/query coverage for current, historical, future, superseded, and unlearned memory views.
- Improved deterministic retrieval explainability around support-chain reservation, stale/current update-history pairs, temporal support ordering, and budget-dropped/withheld memory metadata.
- Added consolidation lineage, unwind, duplicate suppression, and append-only summary-ledger coverage.
- Improved workspace/source identity summaries, conflict previews, connected-agent traces, and dashboard source reporting.
- Kept benchmark claims narrow: LoCoMo FTS and LongMemEval matrix results remain evidence, not leaderboard claims.

### Changed

- Refined the public website positioning around ZMem as memory AI agents can rely on: local memory, review, scoped use, handoff, and receipts.
- Updated homepage copy to distinguish ZMem from generic durable context/search products: search finds context; ZMem helps decide what memory should shape agent work.
- Locked the homepage/nav/footer structure around the launch sequence: hero, agent stack band, memory workflow, native memory and context control, handoff, proof, and install.
- Reframed proof language around lineage and memory influence, not semantic truth or unsupported cryptographic claims.
- Verified the next L3 retrieval slice locally: update-history relation-pair RRF promotes explicit stale/current relation pairs over generic high-authority change anchors under tight context budgets.

### Verification

- `npm run build` in `site/`
- `python3 -m unittest tests.test_store.MemoryStoreTest.test_update_history_relation_rrf_promotes_explicit_current_relation_over_high_authority_generic_anchor tests.test_runner.RunnerTest.test_update_history_relation_context_rrf_promotes_explicit_current_relation_over_high_authority_generic_anchor -q`
- `python3 -m unittest tests.test_store tests.test_policy tests.test_runner -q`
- `python3 -m zerker_memory eval`
- `git diff --check`
- `python3 -m unittest discover -s tests -q`
- `python3 scripts/release_smoke.py --summary-only`
- GitHub Actions `test` on Python 3.10, 3.11, and 3.12
- GitHub Actions `release-smoke`

## 0.1.0-alpha frontier build - ActiveGraph, LoCoMo, and compact traces

### Shipped

- Added the ActiveGraph source integration pack with `zmem.persist`, `zmem.recall`, and compact benchmark behaviors.
- Added `pack/pack.yaml` and the `activegraph.packs` entry point so the ZMem pack has a stable manifest.
- Added ActiveGraph memory writes with causal event pointers through `caused_by_event`.
- Added a compact event-sourced LoCoMo runner that writes `trace.jsonl` and `scored_receipt.json` instead of per-question receipt bundles.
- Recorded the official LoCoMo FTS baseline under `.zerker/bench/locomo-official-v1/fts/`: 1,986 questions, F1 `0.3752394031509457`, EM `0.37210473313192344`, trace SHA `67a005bf87b4bafcd2d7ce1cf8bfff97d7f430788afd0472511f738594971d0c`.
- Added next-run guidance for `fts-multihop` and `pseudo-embedding-rerank` so retrieval depth and reranking can be compared against the same LoCoMo dataset.
- Added the frontier benchmark queue: LongMemEval-S for abstention and token efficiency, plus BEAM for scale and causal-memory stress.

### Current Boundary

- The ActiveGraph integration is built at source level and covered by local tests.
- A real `activegraph pack add zmem` loader/install smoke still needs a networked environment.
- Public benchmark claims remain scoped to the recorded rule-based token F1/EM receipts until official benchmark submission rules are satisfied.

## 0.1.0-alpha - Local-first proof memory MVP

### Positioning

- Packaged Zerker Memory as open-source, local-first portable memory with proof for AI agents.
- Clarified the `zmem` promise: store memory locally, govern what gets injected, and prove what influenced each action.

### Shipped

- Local SQLite memory store with FTS search and fallback search.
- Typed memories: episodic, semantic, procedural, and policy.
- Trust and authority as separate controls.
- Quarantine, review queue, promote, reject, revoke, lineage, and revocation propagation.
- Symbolic policy gate before memory injection.
- Append-only event log, Merkle roots, action receipts, `why`, receipt bundles, stable export, snapshots, verify, and restore.
- Memory Merkle trees on injection receipts, so agents can see the selected-memory root and per-memory inclusion proof behind the context they used.
- CLI entrypoints: `zmem`, `zerker-memory`, compatibility `zerker`, and `zerker-memory-mcp`.
- MCP server and Python package APIs.
- Local review console with memory review, topic inspection, receipt actions, proof inspector, release-pack, handoff, restore, launch-asset verification, and return-packet verification.
- Agent setup for Codex, Claude Code, OpenClaw, Hermes, and generic MCP clients.
- Day-1 bootstrap with `install.sh`, `examples/first_run.sh`, eval, doctor, agent smoke, and MCP smoke.
- Launch proof and release pack flows for local proof reports, handoff archives, public verify packets, return packets, and screenshot/GIF checklists.
- Behavior-tree recovery memory: trace ingest, deterministic fallback explanation, py_trees/BTPG helpers, and BehaviorTree.CPP/Groot2 export.
- Provider governance scaffold for Mem0 and Zep, with external imports quarantined by default.
- GitHub Actions test/eval/release-smoke coverage.
- Static landing page and launch-proof report surfaces.
- Landing and dashboard usability pass with clearer agent-facing positioning, a direct add-memory flow, topic inspection, daily-use workflow cards, Cursor continuity state, and a friendlier saved-memory proof summary.
- Builder-experience pass with `docs/BUILDER_EXPERIENCE.md`, clearer Codex/Claude direct install guidance, Cursor/manual MCP import guidance, agent prompt usage, and smoke-check acceptance steps.

### Current Launch Gate

- Local alpha is functional and ready for dogfooding.
- Strict public alpha launch still requires public GitHub/raw-installer proof, clean-shell packaged-install logs, and the final screenshot/GIF asset set.
