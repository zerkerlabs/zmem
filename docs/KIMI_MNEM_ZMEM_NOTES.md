# Kimi / mnem Memory Design Notes

Source reviewed: `/Users/zzo/Downloads/Kimi_Agent_Frontier Agentic Memory Design/`.

## What It Proposes

The proposal is a polished marketing/prototype app for a product called `mnem`.

Its product shape:

- hosted or service-like agentic memory platform,
- Python, Node, Docker, and HTTP API entrypoints,
- three main memory types: episodic, semantic, procedural,
- working memory in the architecture diagram,
- automatic embeddings and indexing,
- decay curves,
- semantic graph memory,
- learned workflow/procedural memory from traces,
- unified query layer across memory types,
- pricing tiers and memory limits.

The central pitch is:

> Give autonomous agents persistent memory.

It is strongest as a broad "agent memory infrastructure" product.

## What Is Good

- Very clear memory primitives: episodic, semantic, procedural, working.
- Strong visual architecture language around a unified memory substrate.
- Clean developer UX: install, serve, store, query.
- API shape is easy to understand: `/v1/memory`, `/v1/memory/query`, `/v1/agents`.
- Good emphasis on context metadata: agent, session, intent.
- Decay curves and procedure extraction are useful ideas for future ZMem memory quality.
- The "one interface, all memory" idea is worth borrowing for docs.

## Where It Differs From ZMem

`mnem` optimizes for recall infrastructure.

`zmem` optimizes for governed, inspectable, portable, verifiable memory.

| Area | mnem proposal | ZMem direction |
| --- | --- | --- |
| Primary wedge | persistent agent memory | local-first verifiable memory |
| Storage posture | service/platform | local SQLite by default |
| Retrieval | embeddings, graphs, query | structured search, policy-gated injection |
| Memory types | episodic, semantic, procedural | episodic, semantic, procedural, policy |
| Governance | mostly absent | trust, authority, quarantine, review, revoke |
| Proof | mostly absent | Merkle receipts, bundles, snapshots, handoff |
| Portability | not central | core feature |
| Human review | not central | core feature |
| Pricing | hosted SaaS-like | open-source wedge first |

## What ZMem Should Borrow

- A simpler first-run API story:
  - `zmem remember`
  - `zmem query`
  - `zmem continue`
  - `zmem verify`
- The phrase "one interface, all memory" if framed around governed memory.
- A clearer split of memory quality features:
  - episodic events,
  - semantic facts,
  - procedural workflows,
  - policy memories.
- Decay/reinforcement as a future quality layer.
- A visual architecture page that shows recall, policy, receipts, and handoff as one pipeline.

## What ZMem Should Not Borrow

- Do not lead with hosted pricing tiers yet.
- Do not promise automatic graph/procedure extraction before it exists.
- Do not claim sub-5ms retrieval or 10M memories per agent without benchmarks.
- Do not make "automatic embeddings" the core story.
- Do not drop the proof/governance wedge to become another memory platform.

## Best Synthesis

ZMem should feel as simple as `mnem`, but stay differentiated by proof.

Recommended framing:

> ZMem is local-first memory for AI agents. One interface to remember, query, review, continue, and verify what changed.

Architecture shape:

```text
Agent / MCP client
  -> query local memory
  -> policy gate decides admissibility
  -> agent receives allowed context
  -> receipt records injected and withheld memory
  -> snapshot/handoff moves state across agents
  -> Treeship can anchor proof later
```

The Kimi/mnem design validates the market for agent memory infrastructure. It does not replace ZMem's category. It makes the case that ZMem needs a sleeker developer UX on top of its stronger proof substrate.

