# ZMem Problem-Solution Matrix

Date: 2026-06-05

This matrix captures the product signal from recent memory notes and Moltbook-derived analysis. Treat external market/frontier claims here as strategy inputs unless independently verified. The product truth boundary remains the shipped code and release checks.

## Core Position

ZMem should be:

> A local-first trusted memory layer for AI agents: structured enough to inspect, governed enough to trust, portable enough to hand off, and proof-backed enough to verify.

Do not position ZMem as just a vector database, a hosted memory SaaS, or a vague "memory mesh." The better architecture phrase is:

> Trusted memory graph, local-first proof ledger, selective sharing.

The public product language should stay simpler:

> Give agents memory they can use, inspect, continue from, and verify.

## What We Already Cover

| Problem | Current ZMem solution | Status |
| --- | --- | --- |
| Agents restart from scratch | Local SQLite store, persisted memories, MCP server | Built |
| Vector stores are opaque | Typed records, SQLite/FTS search, dashboard inspection | Built |
| Agents store unsafe or low-quality memory | Quarantine, review queue, promote/reject/revoke | Built |
| Memory should not be blindly injected | Policy-gated injection with withheld-memory receipts | Built |
| Agents need to know why memory was used | `why`, action receipts, retrieval metadata, policy decisions | Built |
| Memory use needs proof | Event Merkle root, memory Merkle tree, receipt bundles, snapshots | Built |
| Agent-to-agent continuity is hard | MCP configs, manual packs, handoff, restore | Built |
| External memory providers need governance | Mem0/Zep scaffold with quarantine-by-default import | Built |
| Users need a local review surface | Browser dashboard with add-memory, review, inject preview, proof actions | Built |

## Good Missing Features

These are the highest-signal gaps from the attached analysis.

| Missing feature | Problem it solves | Recommended priority |
| --- | --- | --- |
| Signed memory transition receipts | Merkle proofs show integrity, but signatures establish accountable origin across machines | P0 after launch polish |
| Curation policy templates | Agents either store nothing or hoard junk without clear behavioral rules | P0/P1 |
| Memory strength and decay | Prevents memory from becoming a stale junk drawer; rewards repeatedly useful memories | P1 |
| Usage/retrieval log | Lets agents and humans see when memory was used, reinforced, or ignored | P1 |
| Topic/entity "what do you know?" view | Makes memory inspection delightful and legible without SQL or raw JSON | P1 |
| Typed graph edges | Supports `DERIVED_FROM`, `CONTRADICTS`, `SUPPORTS`, `ABOUT`, `SUPERSEDES`, and causal recall | P1/P2 |
| Bi-temporal validity | Lets an agent ask what it knew or believed at a specific time | P2 |
| Scoped sub-agent memory packets | Parent agents can give sub-agents only the relevant memory slice, not the whole store | P1 |
| Shared local memory instance | Multiple local agents can coordinate through one governed store with attribution | P1 |
| Signed export/import deltas | Enables safe memory transmission across agents/machines without silent shared mutable state | P1/P2 |
| Optional semantic overlay | Better fuzzy recall while keeping SQLite/proof as the source of truth | P2 |
| Postgres backend | Team/heavier multi-agent workflows need stronger concurrency and admin controls | P2 |

## Product Decisions

### Keep The MVP Simple

The launch experience should remain:

1. Install locally.
2. Connect an agent.
3. Add/search/review memory.
4. Preview what the agent receives.
5. Verify why memory was used.
6. Handoff to another agent or machine.

### Add Proof Without Making Users Think About Proof

Agents and developers should see:

- source,
- status,
- timestamp,
- reason selected,
- memory root,
- receipt verification.

Normal users should see:

> This memory was allowed, this memory was withheld, and the proof checks out.

### Use "Mesh" Internally, Not As The Main Wedge

"Memory mesh" is useful as a design direction for shared scopes and transmitted bundles, but it is too vague as the primary product category. Prefer:

- trusted memory,
- proof-backed context,
- governed memory graph,
- portable agent memory.

## Best Next Build Sequence

1. **Signed transition receipts**
   Add local Ed25519 keys and sign each important memory transition/root.

2. **Curation presets**
   Ship policy packs for coding agent, research agent, personal assistant, and team workspace.

3. **Memory quality layer**
   Add `strength`, `last_used_at`, `use_count`, decay scoring, and reinforcement on successful retrieval.

4. **Topic inspector**
   Add CLI/dashboard flow: "what do you know about X?" with memories, sources, receipts, and conflicts.

5. **Scoped sub-agent packet**
   Add a selective export: task, allowed memory subset, proof root, prompt instructions, and restore/import command.

6. **Graph edges**
   Add typed memory links for derived, supports, contradicts, supersedes, about, and shared-with relationships.

7. **Signed sharing**
   Add export/import deltas with signatures, revocation metadata, and conflict visibility.

## Claim Boundary

Safe to claim now:

- Local-first memory for AI agents.
- Inspectable structured memory.
- Policy-gated injection.
- Action receipts and `why`.
- Event Merkle roots and selected-memory Merkle trees.
- Portable handoff and restore.
- MCP setup for multiple agent targets.

Do not claim yet:

- Ed25519-signed memory events.
- Full graph memory backend.
- Semantic/vector benchmark superiority.
- Automatic memory decay or strength ranking.
- Networked shared memory sync.
- Team ACLs or hosted control plane.

