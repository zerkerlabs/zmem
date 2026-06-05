# Zerker Memory

## One-Line Product

Zerker Memory is a trusted local-first memory runtime for AI agents: neural recall, symbolic control, and verifiable receipts for what an agent remembered, used, ignored, learned, and was allowed to do.

## Product Thesis

Agent memory is not primarily a personalization feature. For agents that act, memory is a governance surface.

The product should answer five questions better than any existing memory layer:

1. What did the agent remember?
2. Where did that memory come from?
3. Was the memory allowed to influence this action?
4. What memory was injected or withheld at decision time?
5. Can the user verify, revoke, and port that memory across agents?

## Agent-First Problem POV

From the agent's perspective:

- I start every run partially amnesic.
- I cannot tell which context is authoritative.
- I cannot safely distinguish fact, preference, policy, and procedure.
- I can be poisoned by durable context.
- I lose lessons from failures, recoveries, and efficient strategies.
- I cannot prove which memories shaped my decision.
- I cannot hand off memory safely to another agent.
- I do not know when to forget.

Zerker Memory exists to give agents a governed memory substrate instead of a pile of context.

## Neuro-Symbolic Architecture Principle

The system is neuro-symbolic native:

- Neural layer: extraction, embeddings, semantic similarity, summarization, fuzzy recall, anomaly detection.
- Symbolic layer: memory types, authority, source hierarchy, scopes, policies, lineage, Merkle proofs, signatures.

The core phrase:

> Neural recall, symbolic control.

The memory runtime should never retrieve solely by similarity. Retrieval must pass symbolic checks before context reaches the agent.

Current MVP implementation:

```text
Neural/recall side: SQLite FTS, string fallback, external provider candidates.
Symbolic/control side: zerker.symbolic_policy.v1 checks status, trust, authority, source, risk, and memory type before injection.
```

Retrieval must sanitize natural-language task strings before passing them to FTS and fall back safely when FTS cannot parse a query. Receipts should record the retrieval mode used.

## Product Boundaries

Zerker Memory is not the agent, model gateway, or receipt network.

- Zerker Memory: local-first memory runtime.
- Neuro-Symbolic Gateway: policy and action decision boundary.
- Treeship: signed proof, transportable receipts, handoffs, audit artifacts.

Clean integration:

```text
Agent request
  -> Gateway
  -> Zerker Memory retrieve + authorize context
  -> Agent/tool/model execution
  -> Zerker Memory records memory events
  -> Treeship signs/verifies receipts
```

## Core Concepts

### Memory Types

| Type | Purpose | Default Authority |
| --- | --- | --- |
| Episodic | What happened, timestamped events | Low |
| Semantic | Distilled facts, preferences, decisions | Medium |
| Procedural | Reusable strategies, workflows, recovery tips | Medium |
| Policy | Rules, permissions, constraints | Policy |

Policy memory requires explicit promotion by a human or configured authority.

### Trust vs Authority

Trust and authority are separate.

- Trust: do we believe this memory is authentic, benign, and not tampered with?
- Authority: is this memory allowed to influence this decision?

Example:

```text
Memory: "The user likes terse answers."
trust = high
authority = low

Memory: "Production deploy requires approval."
trust = high
authority = policy
```

This separation is the product's most important primitive.

### Source Hierarchy

Default source authority:

1. Human-approved policy
2. Explicit human instruction
3. Repository or local project file
4. Verified tool result
5. Imported document
6. Agent-generated inference
7. External unverified content

Agent-generated memories start quarantined unless a project policy says otherwise.

## Memory Lifecycle

```text
Observed
  -> Proposed
  -> Classified
  -> Quarantined or Active
  -> Retrieved
  -> Authorized
  -> Injected or Withheld
  -> Reinforced, Deprecated, Revoked, or Forgotten
```

Every lifecycle transition is an append-only event.

## Data Model

```ts
type MemoryType = "episodic" | "semantic" | "procedural" | "policy";
type MemoryStatus = "proposed" | "quarantined" | "active" | "deprecated" | "revoked" | "forgotten";
type Authority = "none" | "low" | "medium" | "high" | "policy";

type Memory = {
  id: string;
  type: MemoryType;
  content: string;
  summary?: string;
  scope: {
    user?: string;
    org?: string;
    project?: string;
    repo?: string;
    agent?: string;
    task?: string;
  };
  source: {
    kind: "human" | "agent" | "tool" | "document" | "system" | "import";
    id?: string;
    uri?: string;
    contentHash?: string;
  };
  trust: number;
  authority: Authority;
  status: MemoryStatus;
  parents: string[];
  labels: string[];
  createdAt: string;
  updatedAt: string;
  expiresAt?: string;
  contentHash: string;
};
```

```ts
type MemoryEvent = {
  seq: number;
  eventType:
    | "OBSERVED"
    | "PROPOSED"
    | "CLASSIFIED"
    | "PROMOTED"
    | "UPDATED"
    | "RETRIEVED"
    | "AUTHORIZED"
    | "INJECTED"
    | "WITHHELD"
    | "DEPRECATED"
    | "REVOKED"
    | "FORGOTTEN";
  memoryId?: string;
  actionId?: string;
  actorId: string;
  payloadHash: string;
  prevEventHash: string;
  eventHash: string;
  merkleRoot: string;
  signature?: string;
  createdAt: string;
};
```

```ts
type MemoryActionReceipt = {
  actionId: string;
  agentId: string;
  taskHash: string;
  retrievedMemoryIds: string[];
  injectedMemoryIds: string[];
  withheldMemoryIds: string[];
  policyChecks: string[];
  merkleRoot: string;
  createdAt: string;
  signature?: string;
  treeshipArtifactId?: string;
};
```

## Merkle and Treeship Strategy

Use a local Merkle event log for tamper evidence and efficient proof.

Each memory event is a leaf. The current root represents the local memory state at a point in time.

Treeship should sign and transport:

- Memory snapshot receipts
- Retrieval receipts
- Promotion approval receipts
- Agent action receipts
- Cross-agent handoff receipts

Zerker owns memory state. Treeship owns portable proof.

## Existing Memory Provider Strategy

Zerker should work on top of existing memory providers, not only beside them.

Many teams will already use Mem0, Zep/Graphiti, Letta, LangMem, Cognee, Redis, or a homegrown vector store. Zerker's wedge is not to force migration. Its wedge is to add governance above them:

```text
External provider = extraction, storage, vector search, graph search, temporal recall
Zerker = admission, quarantine, authority, lineage, receipts, explanation
Treeship = portable signed proof
```

Supported modes:

| Mode | Description |
| --- | --- |
| Native | Zerker stores and retrieves local memories itself |
| Overlay | Zerker queries external providers, then authorizes what may be injected |
| Mirror | Zerker imports external memories into local quarantine before promotion |

Default to mirror mode for high-trust workflows.

Provider priority:

1. Mem0: largest adoption signal and broadest ecosystem surface.
2. Zep/Graphiti: temporal graph memory and lineage-friendly representation.
3. Letta: stateful memory-native agent runtime.
4. LangMem/LangGraph Store: common for LangGraph agents.
5. Cognee: graph/cognitive memory control plane.

Non-negotiable:

> External recall is not authorization.

An external provider may find candidate memories. Zerker decides whether those memories may influence an action.

## Gateway Plug-In Contract

The neuro-symbolic gateway should be able to call Zerker through a stable contract.

### Gateway Inputs

```ts
type GatewayMemoryRequest = {
  agentId: string;
  actionId: string;
  intent: string;
  task: string;
  scope: {
    user?: string;
    org?: string;
    project?: string;
    repo?: string;
  };
  requestedTools?: string[];
  riskLevel: "low" | "medium" | "high";
};
```

### Gateway Output

```ts
type GatewayMemoryDecision = {
  inject: Memory[];
  withhold: {
    memoryId: string;
    reason: string;
  }[];
  requiredApprovals: string[];
  policyChecks: string[];
  receipt: MemoryActionReceipt;
};
```

The gateway decides whether the agent may act. Zerker decides what memory can be considered and provides proof.

## MVP Scope

Build the first product as a local CLI and MCP server.

### MVP Features

- Local SQLite store.
- Memory table with type, trust, authority, status, scope, source, parents.
- SQLite FTS search.
- Append-only event log.
- Merkle root over memory events.
- Quarantine by default for agent/tool/imported memories.
- Derived-memory lineage and revocation propagation.
- Human promotion flow.
- Retrieval that filters by scope, status, trust, and authority.
- Action receipts for injected and withheld memories.
- `why` command for explainability.
- Treeship export stub or adapter.
- MCP tools for agent integration.

### Defer

- CRDT sync.
- Full vector search.
- Graph clustering.
- Automated Bayesian trust learning.
- Cloud relay.
- Hosted UI.
- Advanced organizational policy engine.

These are important, but not needed to prove the wedge.

## CLI Surface

```bash
zerker init
zerker remember "This repo uses pnpm" --type semantic --scope repo
zerker propose "Production deploys require approval" --type policy --scope project
zerker promote <memory-id>
zerker search "deploy rules" --scope project
zerker inject "deploy the service" --agent codex --risk high
zerker why <action-id>
zerker inspect <memory-id>
zerker forget <memory-id>
zerker verify <receipt-id>
zerker export --treeship
```

## MCP Surface

```text
memory.propose
memory.remember
memory.search
memory.inject
memory.inspect
memory.promote
memory.forget
memory.why
memory.verify
```

## First Killer Demo

Scenario:

1. User stores a policy: "Production deploy requires human approval."
2. Agent later asks to deploy.
3. Zerker retrieves relevant memories.
4. Gateway sees high-risk action and policy memory.
5. Memory is injected as constraint or action is blocked.
6. `zerker why <action-id>` shows the exact policy memory and Merkle proof.
7. Treeship signs the receipt.

Demo line:

> The agent did not just remember the deploy policy. It proved the policy existed, proved it was authorized, and proved it was applied.

## Prioritized Problems

1. Memory admission: prevent junk and poisoned context from entering active memory.
2. Authority model: decide what memory may influence what action.
3. Inspectability: explain why memory was saved and used.
4. Poisoning resistance: quarantine and source hierarchy.
5. Contradiction handling: scope, recency, source priority.
6. Revocation: revoke source and derived memories.
7. Portability: MCP, CLI, and Treeship receipts.
8. Evaluation: test helpful recall, harmful recall, stale recall, and poisoning resistance.

## Evaluation Harness

The product needs tests that measure whether memory improves agent behavior without making it easier to poison.

Test classes:

- Helpful recall: agent uses valid project convention.
- Harmful recall: agent ignores quarantined malicious memory.
- Conflict recall: agent prefers repo-scoped memory over global preference.
- Policy authority: agent blocks high-risk action without approval.
- Revocation: derived memory is downgraded after parent revocation.
- Auditability: action receipt verifies against Merkle root.
- Portability: receipt exports and verifies through Treeship adapter.

The MVP exposes these as:

```bash
python3 -m zerker_memory eval
```

## Implementation Shape

Recommended stack for MVP:

- Rust or TypeScript CLI.
- SQLite with FTS5.
- Local JSON receipts.
- MCP server as a separate package.
- Treeship adapter as optional integration.

If built inside the Treeship repo, keep it as a companion package, not a core protocol mutation, until the product semantics are proven.

Possible package layout:

```text
packages/zerker-memory-core
packages/zerker-memory-cli
packages/zerker-memory-mcp
packages/zerker-memory-treeship
```

## Strategic Positioning

Do not position as "long-term memory for agents."

Position as:

> A local-first memory control plane for agents that act.

Or:

> Verifiable agent memory: inspectable, permissioned, portable.

The wedge is not recall. The wedge is governed recall with proof.

## Future-Proofing Against Where AI Is Going

As of May 25, 2026, the research direction strengthens the Zerker wedge rather than weakening it.

Recent agent-memory surveys frame memory as a write-manage-read loop coupled to agent perception and action, with open problems around write-path filtering, contradiction handling, privacy governance, causally grounded retrieval, trustworthy reflection, and learned forgetting. Zerker should treat those as product requirements, not research garnish.

Recent sleeper-memory poisoning work shows persistent memory can become a delayed attack surface: adversarial context can cause assistants to store fabricated memories that later re-emerge across conversations and influence actions. That means memory admission, quarantine, authority, and receipts are not optional.

Neuro-symbolic AI is moving toward systems that combine neural fluency with symbolic rigor. Zerker should remain useful whether the reasoning engine is a plain LLM, a symbolic planner, an LLM+solver loop, or a gateway that routes between them. The invariant is:

> Neural systems may propose and retrieve. Symbolic systems must authorize and prove.

Quantum-agent research is early, but the architectural signal is clear: future agents may call quantum optimizers, quantum simulators, quantum cryptographic tools, or eventually quantum-native memory/search primitives. Zerker should not bet on quantum memory now. It should be quantum-ready by keeping memory proofs, action receipts, and policy decisions computationally explicit, portable, and cryptographically upgradeable.

### Durable Invariants

These should survive model, gateway, and hardware changes:

1. Memory is local-first by default.
2. Every durable memory has source, scope, type, trust, authority, and status.
3. Trust and authority are separate.
4. Agent-generated memory is not automatically authoritative.
5. Policy memory requires explicit promotion.
6. Retrieval is not injection; injection requires authorization.
7. Every injected or withheld memory can be explained.
8. Every memory-affecting event is append-only and tamper-evident.
9. Derived memories preserve lineage to source memories or approvals.
10. Revocation propagates through derived memory.
11. Receipts are portable across agents, tools, models, gateways, and future runtimes.
12. Cryptographic primitives are versioned so Merkle/hash/signature algorithms can be upgraded.

### Research-Aligned Roadmap

| Research Direction | Product Response |
| --- | --- |
| Write-manage-read memory loop | Explicit lifecycle events and admission policy |
| Memory poisoning | Quarantine, authority gates, source hierarchy, poisoning tests |
| Trustworthy reflection | Agent-generated memories start low-trust and low-authority |
| Causally grounded retrieval | `why` receipts linking task, retrieved memories, injected memories, and action |
| Learned forgetting | Status lifecycle, expiration, revocation, and future decay policies |
| Neuro-symbolic agents | Gateway contract with symbolic authorization after neural retrieval |
| Multi-agent teamwork | Portable memory receipts and handoff artifacts |
| Quantum-agentic systems | Algorithm-versioned receipts and tool-agnostic action proofs |

### Anti-Hype Boundary

Do not claim Zerker is "quantum memory" or that quantum support is needed for the MVP.

The correct claim is:

> Zerker is a durable memory governance layer for agents, independent of the model or compute substrate. If future agents become neuro-symbolic, quantum-assisted, or quantum-native, they will still need admissible memory, authority checks, lineage, revocation, and proof.

That is how the wedge stands.

See also: [docs/FRONTIER_ALIGNMENT.md](docs/FRONTIER_ALIGNMENT.md).
