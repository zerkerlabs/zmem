# Changelog

All notable Zerker Memory alpha changes are summarized here.

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
