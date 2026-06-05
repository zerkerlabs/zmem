# Zerker Memory Epic Swarm

Zerker Memory is a standalone product by Zerker. The CLI is one interface, not the product.

Product identity:

```text
Product: Zerker Memory
Package: zerker-memory
Primary CLI: zerker-memory
Short CLI: zmem
Compatibility CLI: zerker
```

## North Star

Trusted, verifiable memory for AI agents that act.

Zerker Memory should answer seven questions:

1. What did the agent remember?
2. Who or what created that memory?
3. Was it allowed to influence this action?
4. What was withheld?
5. Why?
6. Can it be revoked?
7. Can it be proven later?

## Epic 1: Instant Product Onboarding

Status: implemented in alpha.

Goal: a developer can install, prove, configure, and connect Zerker Memory in two minutes.

Build:

- `zmem` CLI alias.
- `zerker-memory` as primary long command in docs.
- `zmem init` first-run flow.
- `zmem mcp-config` generator.
- `zmem policy init` from template.
- `zmem demo` one-command proof.

Acceptance:

- Clean Python 3.10 venv can install and run `zmem eval`.
- Quickstart never depends on global state.
- Landing page has one copyable install path and one copyable connect path.

Verified:

- `zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config`
- `zmem policy init`
- `zmem mcp-config --include-policy`
- `zmem demo`
- `zmem eval`

## Epic 2: Verifiable Memory Core

Goal: every memory injection and snapshot can be independently verified.

Build:

- Receipt bundle format. `Implemented in alpha.`
- Snapshot verification command. `Implemented in alpha.`
- Stable proof schema docs. `Implemented in docs/PROOF_SCHEMA.md.`
- Optional Treeship signing bridge.
- Local receipt inspector in `zmem ui`.

Acceptance:

- `zmem verify <action-id>` verifies action receipt.
- `zmem bundle <action-id>` exports receipt, supporting memories, and pre-action event proof.
- `zmem bundle verify <file>` independently verifies exported bundles.
- `zmem snapshot verify <file>` detects tampering. `Verified.`
- Treeship-compatible export remains optional.

## Epic 3: Provider-Neutral Governance

Goal: Zerker Memory governs recall from local memory and external memory providers.

Build:

- Live Mem0 adapter. `Search/import CLI, provider doctor live overrides, and env-gated release smoke implemented.`
- Zep/Graphiti adapter.
- Provider config file. `Implemented with .zerker/providers.json.`
- Provider import quarantine. `Implemented.`
- Source scoring and contradiction flags. `Score labels implemented; contradiction flags pending.`

Acceptance:

- External memories never become active authority on import.
- `zmem provider import` lands candidates in review queue. `Implemented.`
- `zmem eval` includes provider-poisoning scenario. `Implemented.`

## Epic 4: Policy And Review Workflow

Goal: teams can safely approve, reject, revoke, and audit memory.

Build:

- Per-agent and per-scope policy rules.
- Policy lint/test/explain commands.
- Review console receipt viewer.
- Lineage graph.
- Revocation impact preview.

Acceptance:

- A reviewer can see why a memory is queued.
- A reviewer can promote/reject with reason.
- Revoking a source shows affected descendants before commit.

## Epic 5: Recovery Memory Vertical

Goal: behavior-tree and embodied agents get causal recovery memory.

Build:

- py_trees adapter.
- BTPG adapter.
- BehaviorTree.CPP/Groot2 export.
- BT trace replay.
- Recovery metrics.
- BT trace viewer in console.

Acceptance:

- A BT executor can emit Zerker trace JSONL without changing tick semantics.
- `zmem bt explain` cites concrete event IDs.
- Demo shows fallback caused by sensor or guard failure.

## Epic 6: Product Console

Goal: local `zmem ui` feels like the product, not a debug page.

Build:

- First-run setup state.
- Memory review queue.
- Receipt inspector.
- Policy editor.
- Snapshot export/restore.
- BT trace view.

Acceptance:

- Builder can install, open console, approve memory, run injection preview, and export proof.
- Console screenshots are launch-ready.

## Epic 7: Launch Readiness

Goal: GitHub alpha launch feels coherent and credible.

Build:

- Clean repo init.
- README final pass.
- Screenshots/GIFs.
- Release notes.
- GitHub Actions install/test matrix.
- `v0.1.0-alpha` tag.

Acceptance:

- Fresh clone path works.
- CI proves install + tests + eval.
- Landing links to GitHub and docs.

## Immediate Swarm Order

1. Product identity pass: `zmem`, `zerker-memory`, docs, landing.
2. Onboarding commands: `init`, `policy init`, `mcp-config`, `demo`.
3. Packaging cleanup: modern editable install, no setuptools warnings.
4. Console polish: receipt viewer and policy template setup.
5. BT adapters: py_trees first, BTPG second.
