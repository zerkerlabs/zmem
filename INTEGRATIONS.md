# Integrations

Zerker Memory should work above existing memory providers.

The goal is not to replace every memory backend. The goal is to add governance:

```text
Existing memory provider = storage, extraction, graph/vector recall
Zerker Memory = authority, quarantine, lineage, receipts, explainability
Treeship = portable signed proof
```

## Adapter Strategy

Zerker supports three modes:

| Mode | Description | Use Case |
| --- | --- | --- |
| Native | Zerker stores and retrieves memories locally | Simple local-first agents |
| Overlay | Zerker searches external providers, then gates retrieved memories before injection | Teams already using Mem0, Zep, Letta, LangMem, Cognee |
| Mirror | Zerker imports external memories into local quarantine, then users promote what may influence agents | High-trust and regulated workflows |

The default safe mode is **mirror**.

External memories should not become authoritative just because a provider retrieved them. Zerker treats them as candidates until trust and authority are assigned.

## Priority Providers

### 1. Mem0

Why first:

- Largest adoption signal in the agent-memory space.
- OSS and hosted options.
- REST API, CLI, SDKs, and MCP/plugin surface.
- Strong ecosystem integrations.

Zerker integration:

```text
Mem0 search result
  -> Zerker external candidate
  -> source_kind=import
  -> status=quarantined by default
  -> promote or inject only if policy allows
```

Commands:

```bash
zmem provider init
zmem provider doctor
zmem provider search "deploy runbook" --provider mem0 --user-id <user>
zmem provider import "deploy runbook" --provider mem0 --scope project --type procedural
zmem queue --scope project
```

Run `zmem provider doctor --live` only when the configured provider endpoint is reachable and credentials are available.

The older `external-search` and `external-import` commands remain as compatibility aliases. Product-facing docs should prefer `zmem provider ...`.

### 2. Zep / Graphiti

Why:

- Temporal knowledge graph model.
- Strong fit for lineage, time-aware facts, and business data.
- Graphiti is useful as a graph substrate under Zerker's symbolic layer.

Zerker integration:

```text
Graphiti episode/node
  -> Zerker episodic/semantic memory candidate
  -> preserve graph node id as source uri
  -> use Zerker for authority and receipts
```

### 3. Letta

Why:

- Stateful agent platform with memory-first design.
- Strong fit when the agent runtime itself is Letta.

Zerker integration:

```text
Letta memory block/context repo
  -> Zerker policy/semantic/procedural candidate
  -> action receipts wrap Letta context decisions
```

### 4. LangMem / LangGraph Store

Why:

- Common among LangGraph builders.
- Provides memory primitives and background management.

Zerker integration:

```text
LangMem store/search
  -> Zerker authorization before injection
  -> Zerker receipt after injection
```

### 5. Cognee

Why:

- Memory control plane with graph and cognitive-science positioning.
- Useful for document and workflow memory.

Zerker integration:

```text
Cognee recall
  -> Zerker governance overlay
```

## Integration Contract

Every external provider adapter should normalize results into:

```ts
type ExternalMemoryCandidate = {
  provider: string
  external_id: string
  content: string
  score?: number
  source_uri?: string
  metadata: Record<string, unknown>
}
```

Zerker then decides:

- whether to import,
- which type to assign,
- default trust,
- default authority,
- whether to quarantine,
- whether to inject,
- what receipt to produce.

Imported provider memories are labeled with `provider:<name>` and `external:<id>`. If a provider does not include a source URI, Zerker records a deterministic URI such as `mem0://<external-id>` so provenance survives snapshot export and receipt bundles.

## Non-Negotiable Rule

External recall is not authorization.

Zerker may use another provider to find candidate memories, but Zerker must still decide whether those memories are allowed to influence an action.
