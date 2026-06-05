# Frontier Alignment

This document maps Zerker Memory against the 2026 frontier for agent memory and neuro-symbolic agent infrastructure.

## Current Read

The research direction supports Zerker's wedge:

- Agent memory is best understood as a **write-manage-read** loop coupled to perception and action, not as a vector DB feature.
- Persistent memory is a long-term attack surface. Sleeper/persistent memory poisoning can survive across sessions and influence future actions.
- Neuro-symbolic agent architectures are maturing around layered systems: neural components propose, retrieve, summarize, and classify; symbolic components enforce constraints, policy, proof, and auditability.
- Production memory providers increasingly specialize in recall substrates: vector memory, temporal graph memory, managed state, or framework-native stores.
- The unsolved product gap is governed memory: admission, authority, quarantine, revocation, lineage, and proof.
- Embodied and behavior-tree agents need a related primitive: recovery memory. They need causal traces that explain why a fallback, replanning step, or recovery policy fired.

## Zerker's Architecture Claim

Zerker Memory is not another recall backend.

It is a memory governance layer:

```text
Recall providers:
  SQLite FTS, Mem0, Zep/Graphiti, Letta, LangMem, Cognee, future vector/graph stores

Zerker:
  admission, trust, authority, quarantine, symbolic policy, lineage, revocation, receipts

Treeship:
  portable signed proof and handoff artifacts
```

The stable principle:

> Neural recall, symbolic control, cryptographic proof.

## State-Of-The-Art Requirements

| Frontier Requirement | Zerker Status |
| --- | --- |
| Write-manage-read lifecycle | Implemented through remember/propose, queue/promote/reject/revoke, inject/why |
| Memory poisoning resistance | Quarantine, symbolic policy gate, review queue, eval scenario |
| Trustworthy reflection | Agent-generated memories default to quarantine/low trust |
| Neuro-symbolic control | `zerker.symbolic_policy.v1` gates injection after recall |
| Source and authority separation | `source_kind`, `trust`, `authority`, `status` are separate |
| Local-first operation | SQLite local store, no network required |
| Provider interoperability | Mem0 adapter scaffold, external import into quarantine |
| Provenance and auditability | Merkle event log, action receipts, `why`, Treeship statement export |
| Revocation/taint propagation | Parent lineage and descendant revocation implemented |
| Agent integration | CLI, MCP server, `zmem run` wrapper |
| Behavior-tree recovery memory | `zmem bt` ingests typed trace events and explains fallback causality |
| Evaluation | `zmem eval` proof harness, including BT recovery explanation |

## What Is Still Not Frontier-Complete

These are intentionally not claimed yet:

- Vector embeddings.
- Temporal knowledge graph backend.
- CRDT multi-device sync.
- Signed Treeship publication.
- Live Mem0/Zep/Letta integration tests.
- Rich policy language.
- Formal verification of policy rules.
- Hosted UI for review queue.
- Benchmark suite against external memory systems and BT recovery baselines.

## Next Frontier Moves

1. Add real Treeship signing/push integration.
2. Add live Mem0 integration test behind env vars.
3. Add a provider adapter interface for Zep/Graphiti and Letta.
4. Add vector search as a recall backend, keeping symbolic policy as the injection gate.
5. Add a small declarative policy language for authority thresholds and source rules.
6. Add py_trees/BTPG adapter helpers for behavior-tree traces.
7. Add benchmark fixtures for poisoning, stale recall, contradiction, revocation, and BT fallback recovery.
8. Add signed memory snapshots.

## Architecture Guardrails

Do not collapse recall and authorization.

Do not let external provider recall become authority.

Do not let agent-generated memory become active policy without promotion.

Do not remove lineage from derived memories.

Do not make Treeship a hard runtime dependency for local memory.

Do not market this as quantum memory. The correct future-proof claim is substrate independence: any future neural, neuro-symbolic, or quantum-assisted agent still needs admissible memory, revocation, and proof.
