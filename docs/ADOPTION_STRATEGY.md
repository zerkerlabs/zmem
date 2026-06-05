# Adoption Strategy

Zerker Memory should not be sold as "AI memory."

It should be adopted as:

> Governed memory for agents that act.

The product must speak differently to builders, startups, and enterprises while preserving the same technical core.

## Primary User Problems

### Builders

Problem:

- Agents forget repo conventions.
- Agents repeat failed attempts.
- Agents ingest random context as authority.
- Agents cannot explain which memories shaped an action.

Promise:

> Give your coding agent local memory it can prove and you can control.

Proof:

```bash
zmem eval
zmem doctor
zmem run --agent codex --task "fix deploy" --risk medium -- your-agent-command
```

Adoption path:

1. Install locally.
2. Run eval.
3. Add MCP config.
4. Add one policy memory.
5. Run a real task.
6. Inspect `why`.

### Startups

Problem:

- Memory is becoming table stakes.
- Building memory from scratch distracts from product.
- Existing memory providers optimize recall, not governance.
- Customers increasingly ask about privacy, retention, audit, and agent safety.

Promise:

> Add a memory governance layer without becoming an AI infra company.

Proof:

- Works locally.
- Runs above existing providers like Mem0.
- Produces receipts.
- Keeps future Treeship proof path open.

Adoption path:

1. Use native SQLite mode in development.
2. Add MCP to internal agent workflows.
3. Overlay on current provider.
4. Export receipts for customer/security reviews.
5. Build UI around queue/promote/revoke.

### Enterprise

Problem:

- Persistent memory is a liability without governance.
- Agent actions need auditability.
- Data sovereignty matters.
- Memory poisoning is hard to explain and harder to prove against.

Promise:

> Govern what agents remember before memory becomes action.

Proof:

- Quarantine by default.
- Trust and authority are separate.
- Symbolic policy gate before injection.
- Lineage and revocation propagation.
- Merkle event log.
- Treeship-ready exports.

Adoption path:

1. Run offline evaluation.
2. Review policy model.
3. Pilot with low-risk internal agents.
4. Connect to existing memory provider in mirror mode.
5. Export receipts into audit systems.
6. Add enterprise policy configuration.

## Packaging By Persona

| Persona | First CTA | Proof Artifact | Success Moment |
| --- | --- | --- | --- |
| Builder | `zmem eval` | Terminal output | Agent used a policy and withheld bad memory |
| Startup | MCP + provider overlay | Demo receipt | Adds governance without replacing stack |
| Enterprise | `zmem doctor` + eval | Exported receipt | Security team sees lineage and revocation |

## Product Messaging Hierarchy

1. Governed memory for agents that act.
2. Neural recall, symbolic control, cryptographic proof.
3. Local-first by default, provider-compatible by design.
4. Inspect, promote, revoke, and prove memory use.

## What Not To Say

Avoid:

- "We are the best vector memory."
- "Agents remember everything."
- "Quantum memory."
- "Blockchain for memory."
- "Fully solved agent security."

Say:

- "External recall is not authorization."
- "Memory should not automatically become authority."
- "Receipts make memory use inspectable."
- "Local-first governance works with existing providers."

## Adoption Metrics

Developer:

- Time from clone to `zmem eval`.
- Time from MCP config to first `memory.inject`.
- Number of memories proposed by agent.
- Number of memories promoted/rejected.

Startup:

- Number of internal agent tasks wrapped by `zmem run`.
- Number of external provider imports quarantined.
- Number of receipts exported.

Enterprise:

- High-risk actions with receipts.
- Rejected/quarantined memories.
- Revoked memory descendants.
- Audit exports generated.

