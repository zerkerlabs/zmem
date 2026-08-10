# zmem Feature Guide

`zmem` is open-source, local-first portable memory with proof for AI agents.

Use this as the one-page map of what is built and how to try it.

For the clean builder setup path across Codex, Claude Code, Cursor, and other MCP
clients, see `docs/BUILDER_EXPERIENCE.md`.

## Product Shape

`zmem` starts as a local memory system and becomes portable when you package proof or handoff state.

```text
Agents / MCP clients
  -> zmem policy gate
  -> local SQLite memory
  -> receipts, why, bundles, snapshots
  -> handoff / restore across agents or machines
```

Core promise:

> Start local. Connect agents. Govern recall. Export proof. Move memory state across machines or agents when needed.

## Quick Preview

```bash
bash install.sh
zmem status --summary-only
zmem eval
zmem ui
```

Local preview commands:

- Landing: run `npm run dev --prefix site` and open the URL Vite prints.
- Console: run `zmem ui` and open the URL it prints.
- Docs: run `npm run dev --prefix docs` and open the URL Next.js prints.
- Launch proof report: run `zmem release-pack --summary-only`, then open `.zerker/launch-proof/index.html`.

## Features

### Local Memory Core

What it does:

- Stores memory locally in SQLite.
- Supports SQLite FTS search plus safe fallback search.
- Tracks typed memories: `episodic`, `semantic`, `procedural`, and `policy`.
- Supports lifecycle states: active, proposed, quarantined, rejected, revoked, forgotten.

Try it:

```bash
zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config
zmem remember "Production deploys require approval" --type policy --scope project
zmem search "deploy"
```

### Governance And Policy Gate

What it does:

- Separates trust from authority.
- Gates memory injection before an agent can use memory.
- Blocks risky memory by status, authority, labels, type, scope, source, and task risk.
- Records withheld memory instead of silently dropping it.

Try it:

```bash
zmem inject "deploy the service" --agent codex --risk high --scope project
zmem why <action-id>
```

### Review Queue

What it does:

- Lets agents propose memory without immediately making it authoritative.
- Lets humans or systems promote, reject, quarantine, or revoke memories.

Try it:

```bash
zmem propose "New production endpoint is https://example.internal" --type procedural --scope project
zmem queue --scope project
zmem promote <memory-id>
zmem reject <memory-id> --reason "unverified"
zmem revoke <memory-id> --reason "stale"
```

### Consolidation Review

What it does:

- Finds verified episodic and semantic source sets without copying raw text into the preview.
- Materializes a deterministic private summary without changing canonical memory.
- Recomputes the summary from current receipt-verified sources before review.
- Requires one exact confirmation to admit or discard the summary.
- Admits at the weakest source trust and authority ceilings, with source parents and labels committed into the write receipt.
- Records admission or discard as a terminal Merkle event and keeps source evidence intact.

Try it:

```bash
zmem consolidation preview --scope project --min-sources 3 --out preview.json --summary-only
zmem consolidation materialize preview.json --select <candidate-id> --actor-id <operator-id> --confirm-preview <confirmation-id> --summary-only
zmem consolidation inspect --summary-only
zmem consolidation inspect <summary-id> --out inspection.json --summary-only
zmem consolidation admit inspection.json --actor-id <operator-id> --confirm-inspection <confirmation-id> --summary-only
```

Use `zmem consolidation discard ... --reason <reason>` instead of `admit` when the private summary should never enter canonical memory. Operator ids are asserted metadata, Treeship anchoring is separate, and no receipt claims semantic truth.

### Proof Layer

What it does:

- Writes an append-only event log.
- Maintains Merkle roots for tamper-evident state.
- Builds a selected-memory Merkle tree for each injection receipt.
- Includes per-memory inclusion proofs so agents know which proved memory root backed the injected memory.
- Emits action receipts for injected and withheld memories.
- Explains decisions with `why`.
- Exports verifiable bundles and snapshots.

Try it:

```bash
zmem inject "ship after approval" --agent codex --risk high --scope project
zmem why <action-id>
zmem verify <action-id>
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
zmem snapshot --out-dir .zerker/exports
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
```

### Portability And Handoff

What it does:

- Packages a memory snapshot, latest receipt bundle, handoff manifest, README, and Treeship-ready statement.
- Restores handoff state into a new empty store.
- Lets another agent, operator, or machine receive the same governed state.

Try it:

```bash
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
```

### MCP And Agent Setup

What it does:

- Runs an MCP server for agent clients.
- Directly installs configs for Codex and Claude Code.
- Exports manual MCP import packs for Cursor, OpenClaw, Hermes, and generic MCP clients.
- Ships `.zerker/AGENT_PROMPT.md` so agents know when to inject, remember, propose, and explain memory usage.
- Runs agent smoke and MCP stdio smoke.

Try it:

```bash
zmem mcp-config --include-policy
zmem agent install codex
zmem agent install claude-code
zmem agent install cursor --summary-only
zmem agent pack --summary-only
zmem doctor --agent codex --agent claude-code
zmem doctor --agent cursor
zmem agent smoke --agent codex
zmem agent mcp-smoke --agent codex
zmem mcp
```

### Zerker Rooms Integration Preview

What it does:

- Runs a tenant-local HTTP service beside Zerker Gateway Rooms.
- Keeps each room in an opaque isolated SQLite store.
- Shares accepted room memory while keeping member-private memory private.
- Returns ranked admitted memory plus explicit withheld, budget, and abstention state.
- Separates trusted room-event records from quarantined agent proposals.
- Makes retries idempotent and preserves the originating Rooms event in memory provenance.

Try it:

```bash
export ZMEM_SERVICE_TOKEN="$(openssl rand -hex 32)"
zmem --db .zerker/control.sqlite serve --tenant-id tnt_local --storage-root .zerker/rooms
```

Then follow [the Rooms guide](content/docs/rooms.mdx). The ZMem candidate is implemented; the Gateway Go client, Rooms event-store persistence, and hosted multi-tenant deployment remain separate integration work.

### Local Console

What it does:

- Opens a browser UI for adding memory, topic inspection, memory review, injection preview, receipts, snapshots, and release proof actions.
- Lets users ask what ZMem knows about a person, project, task, or decision before handing memory to an agent.
- Shows release-pack, launch-proof, handoff, restore, launch-asset, and return-packet actions.

Try it:

```bash
zmem --db .zerker/memory.sqlite ui
```

Open the local URL printed by `zmem ui`.

### Launch Proof And Release Pack

What it does:

- Generates a local launch-proof report.
- Packages proof artifacts, receipt bundle, snapshot, BT export, public-verify packet, and return-packet skeleton.
- Keeps strict public publish blocked until clean-shell logs and screenshots/GIFs exist.

Try it:

```bash
zmem launch-proof --summary-only
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
zmem verify-public-verify --summary-only
zmem verify-launch-assets --summary-only
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
```

Open `.zerker/launch-proof/index.html` after generating the pack.

### Behavior-Tree Recovery Memory

What it does:

- Ingests behavior-tree trace events.
- Lists traces.
- Explains deterministic fallback/recovery behavior.
- Exports BehaviorTree.CPP/Groot2 XML plus a proof manifest.

Try it:

```bash
zmem --db .zerker/bt.sqlite bt ingest examples/bt_trace.jsonl
zmem --db .zerker/bt.sqlite bt explain trace_demo_recovery --question "why did the robot fall back?"
zmem --db .zerker/bt.sqlite bt export trace_demo_recovery --out-dir .zerker/exports
```

### Provider Governance

What it does:

- Adds governance over external recall providers.
- Supports Mem0/Zep scaffolding.
- Imports external memories into quarantine by default with provenance labels.

Try it:

```bash
zmem provider init
zmem provider doctor
zmem provider search "deploy runbook" --provider mem0 --user-id <user>
zmem provider import "deploy runbook" --provider mem0 --scope project --type procedural
zmem queue --scope project
```

## What Is Not Built Yet

- Hosted SaaS.
- Team control plane with roles, retention, and shared review queues.
- Fully signed public Treeship publish/verify workflow.
- Production vector/graph replacement.
- Memory strength, decay, reinforcement scoring, and curation policy templates.

## Product Signal

The strongest builder signal is not "give agents a bigger vector store." It is: make memory local, inspectable, structured, curated, and provable.

See [MOLTBOOK_ZMEM_PRODUCT_SIGNAL.md](MOLTBOOK_ZMEM_PRODUCT_SIGNAL.md) and [ZMEM_PROBLEM_SOLUTION_MATRIX.md](ZMEM_PROBLEM_SOLUTION_MATRIX.md) for the captured strategy notes.

## Best Mental Model

`zmem` is not just a memory database.

It is:

- a local memory store,
- a policy gate,
- an MCP-connected agent interface,
- a receipt/proof system,
- and a portable handoff format.
