# MycelNet / Zerker Memory Notes

## Bottom Line

`zmem` should stay positioned as open-source, local-first portable memory with proof for AI agents.

MycelNet has useful imagery and some good future-adapter ideas, but it should not become the headline product. The strongest product is Zerker Memory: a deterministic governance and proof layer for agent memory.

## What Matches

- Both concepts care about agent memory that persists across runs.
- Both want to work with existing agent frameworks rather than forcing rewrites.
- Both lean local-first: local memory, low dependency burden, no required hosted service for the core.
- Both imagine multiple agents sharing or reusing accumulated context.
- Both can support MCP-compatible workflows.
- Both can fit a larger Treeship/proof story if memory decisions become exportable receipts.

## Key Differences

### Zerker Memory

- Governs whether memory may influence an action.
- Uses symbolic policy, trust, authority, quarantine, lineage, revocation, and receipts.
- Is backend-agnostic: SQLite today, provider overlays later.
- Has a compliance/audit painkiller story: prove what was injected, withheld, and why.
- Works for hosted API-model users because it does not depend on KV-cache access.

### MycelNet

- Optimizes agent networks with latent transport, shared causal memory, and pheromone routing.
- Depends on assumptions that are hard for most hosted API users, especially KV-cache sharing.
- Has a stronger performance/cost narrative than a governance narrative.
- Risks feeling like an orchestration/performance wrapper unless paired with a sharper trust/proof wedge.

## Ideas Worth Keeping

- Use “portable substrate” language carefully: `zmem` starts local but can package memory state for another agent or machine.
- Add a simple diagram/story around:
  1. local memory store,
  2. MCP-connected agents,
  3. policy gate,
  4. proof receipts,
  5. portable handoff/restore.
- Keep the “shared memory across agents” idea, but frame it as governed handoff and MCP access, not magical latent transport.
- Keep MycelNet as a possible future adapter: a performance layer underneath `zmem`, not the product.
- Borrow the “wrap existing workflows” sentiment, but make the exact `zmem` claim: connect through MCP, export snapshots/handoffs, verify receipts.

## Ideas To Avoid For V1

- Do not lead with KV-cache latent transport.
- Do not headline 4x speed or token-reduction benchmarks unless the implementation and deployment constraints are real.
- Do not make pheromone routing central to `zmem`; it dilutes the governance/proof story.
- Do not overuse the mycelium metaphor on the `zmem` landing page. It is evocative, but it can make the product feel less concrete.
- Do not claim hosted/team memory until the team console, roles, retention, and hosted deployment actually exist.

## Recommended Positioning

One-liner:

> `zmem` is open-source, local-first portable memory with proof for AI agents.

Slightly longer:

> `zmem` stores memory locally, lets agents connect through MCP, packages handoffs across machines, and emits Merkle-backed receipts for what influenced each action.

Product promise:

> Start local. Connect agents. Govern recall. Export proof. Move memory state across machines or agents when needed.

## How MycelNet Can Fit Later

MycelNet can be a future provider/adapter under the `zmem` governance layer:

```text
Agent frameworks / MCP clients
  -> zmem policy gate
  -> local SQLite or external memory provider
  -> optional MycelNet-style causal/latent substrate
  -> receipts, snapshots, handoff, restore
```

The key rule: MycelNet may move memory or optimize coordination, but `zmem` decides what is admissible and proves the decision.

## Landing Page Implications

Lead with:

- Local-first portable memory.
- MCP agent connectivity.
- Policy-gated recall.
- Merkle-backed receipts.
- Snapshot/handoff portability.

Support with:

- Behavior-tree recovery memory.
- Provider governance scaffolding.
- Launch-proof/report packaging.

Do not lead with:

- Latent KV-cache transport.
- Pheromone routing.
- Mycelium metaphor.
- Performance benchmark claims.

