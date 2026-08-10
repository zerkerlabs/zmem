# Shared And Swarm Memory

Zerker Memory is local-first, but it can support shared-memory workflows when agents share a database, exchange verified snapshots, or collaborate through the Zerker Rooms integration preview.

The shortest handoff path now is:

```bash
zmem handoff --summary-only
```

That writes `.zerker/handoff/README.md`, `handoff.json`, a verified snapshot, the latest action bundle if one exists, and a Treeship-ready statement for that action so another machine can verify, restore, and dry-run publish from one directory.

## What Works Today

### Shared Local Database

Multiple local agents can point at the same project database:

```bash
zmem --db .zerker/memory.sqlite mcp
zmem --db .zerker/memory.sqlite run --agent codex --task "edit code" --risk medium --scope project -- your-agent-command
zmem --db .zerker/memory.sqlite run --agent hermes --task "review code" --risk medium --scope project -- your-other-agent-command
```

Each action gets its own receipt and Merkle root.

### Shared Review Queue

Agents can propose memories into the same queue:

```bash
zmem propose "The staging deploy failed because the secret name changed" --type episodic --scope project --source agent
zmem queue --scope project
zmem promote <memory-id>
```

Agent-written memory is not authoritative until promoted.

### Snapshot Handoff

One machine or agent can export:

```bash
zmem snapshot --out-dir .zerker/exports
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
```

Another can restore into an empty store:

```bash
zmem --db .zerker/imported.sqlite restore .zerker/exports/<snapshot>.snapshot.json
```

Or package the snapshot plus operator instructions in one step:

```bash
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
```

### Receipt Bundle Handoff

After an action:

```bash
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
```

This lets another user or agent inspect what memory was injected, what was withheld, and which Merkle root anchored the decision.

## Current Limits

The alpha does not yet provide full distributed swarm coordination.

Still needed:

- per-agent identity keys,
- multi-writer merge rules,
- conflict resolution for divergent snapshots,
- quorum approval for high-risk shared memories,
- team/VPC sync,
- signed Treeship publish by default,
- hosted review workflow.

## Zerker Rooms Integration Preview

The Rooms candidate adds a narrow HTTP adapter around the existing ZMem store and policy gate:

- one opaque SQLite store per tenant-and-room pair;
- room-shared and member-private visibility;
- policy-ranked context preparation with explicit withheld and abstention state;
- retry-safe accepted-state records and quarantined agent proposals;
- room-event provenance and a commitment over the exact context returned.

Start it locally with:

```bash
export ZMEM_SERVICE_TOKEN="$(openssl rand -hex 32)"
zmem --db .zerker/control.sqlite serve --tenant-id tnt_local --storage-root .zerker/rooms
```

See [docs/content/docs/rooms.mdx](content/docs/rooms.mdx) for usage and [docs/internal/ZERKER_ROOMS_MEMORY_CONTRACT.md](internal/ZERKER_ROOMS_MEMORY_CONTRACT.md) for the Gateway contract. The first deployment is a tenant-local sidecar; it is not yet a general hosted multi-tenant ZMem service.

## Recommended Swarm Pattern

Use one shared project DB for local swarms:

```text
agent A proposes memory
agent B proposes memory
human/system reviews queue
Zerker injects only active authorized memory
each action emits a receipt
snapshots and bundles move between machines
```

This keeps the important invariant:

> Shared recall is not shared authority.
