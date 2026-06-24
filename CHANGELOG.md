# Changelog

All notable Zerker Memory alpha changes are summarized here.

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
