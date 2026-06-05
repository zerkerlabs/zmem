# Zerker Memory One-Pager

## What It Is

Zerker Memory is a local-first memory governance layer for AI agents.

It lets agents use memory without letting memory automatically become authority.

## Why Now

AI agents are moving from chat into action: code changes, deployments, support replies, research workflows, and internal operations.

Persistent memory makes those agents more useful, but also creates a new risk: stale, poisoned, or unverified memories can influence future actions.

## The Wedge

Most memory products optimize recall.

Zerker governs recall.

```text
Recall provider finds candidate memory.
Zerker checks trust, authority, status, lineage, and risk.
Agent receives only authorized memory.
Zerker records a receipt.
```

## Core Capabilities

- Local SQLite memory.
- MCP server.
- `zmem run` wrapper.
- Memory types: episodic, semantic, procedural, policy.
- Trust and authority as separate fields.
- Quarantine and review queue.
- Symbolic policy gate.
- Lineage and revocation propagation.
- Merkle event log.
- `why` explanations.
- Treeship-ready receipt exports.
- Mem0/external provider overlay path.

## Developer Proof

```bash
zmem eval
zmem doctor
```

The evaluation proves:

- authorized policy injection,
- poisoned memory withholding,
- review queue and rejection,
- revocation propagation,
- Treeship-ready export.

## Buyer Proof

Zerker answers:

- What did the agent remember?
- Where did that memory come from?
- Was it allowed to influence this action?
- What was injected or withheld?
- Can we revoke bad memory and derived memories?
- Can we export a receipt?

## Positioning

Short:

> Governed memory for agents that act.

Technical:

> Neural recall, symbolic control, cryptographic proof.

Enterprise:

> A local-first memory control plane for agent governance, auditability, and data sovereignty.

