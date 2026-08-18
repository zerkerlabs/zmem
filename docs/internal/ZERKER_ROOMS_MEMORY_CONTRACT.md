# Zerker Rooms Memory Contract

- Status: Shipped in ZMem v0.1.10; concurrency-hardened in v0.1.11; semantic indexing candidate after v0.1.12
- Source: `main`
- Contract: `zerker.room_memory_context.v1`
- Transport: authenticated JSON over HTTP
- Initial deployment: one tenant-local ZMem service beside Rooms

## Product Outcome

A new agent joining a room should receive useful, current, policy-approved room memory without inheriting another room's state or another member's private memory. The agent should be able to contribute candidate memory without silently making it authoritative, and the next agent should be able to continue after either process restarts.

That makes the first acceptance flow:

```text
room event -> record or propose -> durable room store
agent joins -> prepare governed context -> work
next agent joins -> receives the accepted room state
```

Treeship proof is additive and asynchronous. It must not sit on the latency-critical context path.

## Ownership

| Surface | Owner |
| --- | --- |
| Room membership, goal, messages, task/event log | Zerker Gateway Rooms |
| Authentication, tenant resolution, routing, capability checks | Zerker Gateway |
| Shared/private memory, proposal state, retrieval, policy, context packing | ZMem |
| Portable attestation and public verification | Treeship |

Rooms is the collaboration product. ZMem does not duplicate the room transcript, and Treeship does not become the primary room database.

## Deployment Boundary

The first supported shape is a tenant-local sidecar:

```bash
export ZMEM_SERVICE_TOKEN="$(openssl rand -hex 32)"

zmem \
  --db /var/lib/zmem/control.sqlite \
  --policy /etc/zmem/policy.json \
  serve \
  --tenant-id tnt_123 \
  --storage-root /var/lib/zmem/rooms \
  --host 127.0.0.1 \
  --port 8766
```

The tenant is server configuration, never caller input. A non-loopback bind requires both `--allow-remote` and `ZMEM_SERVICE_TOKEN`; remote traffic also requires private networking or TLS termination outside this process.

ZMem creates one SQLite database for each `(tenant, room)` pair under an opaque SHA-256-derived directory. That provides a hard room boundary without trusting a free-form SQL scope convention. Room-shared memory and member-private memory remain separate inside that database.

For semantic room goals, install `zerker-memory[dense]`, cache the local model explicitly with `zmem --db /var/lib/zmem/control.sqlite embeddings index --download-model --summary-only`, and add `--retrieval-mode dense-hybrid` to `serve`. Dense-enabled Rooms maintain each room's derived index after writes and catch up missing or stale vectors before reads. Request handling never downloads a model, and index readiness is returned as compact metadata.

## HTTP Surface

Unauthenticated probes:

- `GET /healthz`
- `GET /readyz`
- `GET /version`

`/healthz` is liveness-only. `/readyz` returns `zerker.room_memory_service_readiness.v1` and must gate Gateway traffic: FTS returns HTTP `200` immediately, while a configured `dense-hybrid` service returns HTTP `503` until the FastEmbed runtime and cached local model are available. The response includes the retrieval state and setup command; it never loads or downloads a model. Gateway must not treat a live process with failed retrieval readiness as ready for joins.

Authenticated operations:

- `POST /v1/contexts:prepare`
- `POST /v1/inject`, compatibility alias for context preparation
- `POST /v1/memories:propose`
- `POST /v1/memories:record`

All write requests require a Rooms `source_event_id` and an `idempotency_key`. Replaying an identical write is safe. Reusing a key for different content returns HTTP `409`.

### Prepare Context

```bash
curl -fsS http://127.0.0.1:8766/v1/contexts:prepare \
  -H "Authorization: Bearer $ZMEM_SERVICE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "room_id": "rom_alpha",
    "agent_id": "agt_cursor",
    "purpose": "Finish the room release safely",
    "risk": "medium",
    "context_budget_tokens": 2000,
    "membership_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "room_state_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }'
```

`task` is accepted as an alias for `purpose` to match the current Gateway scoping draft. The response preserves ZMem's ranked order and includes:

- selected memory records and source provenance;
- retrieved, admitted, withheld, and budget-dropped counts;
- bounded omission reasons;
- context packing usage;
- an exact room-context commitment;
- request latency.

Context state is explicit:

| State | Gateway behavior |
| --- | --- |
| `ready` | Seat the member with the returned context. |
| `partial` | Seat only if the product surfaces that some memory was omitted. |
| `empty` | Seat with an explicit no-prior-active-memory state. |
| `blocked` | Fail closed; memory existed but policy admitted none. |
| `abstained` | Fail closed or request review; evidence conflicted or an established room produced no confident match. |
| `budget_exhausted` | Retry with an approved budget or fail closed. |

Transport errors and malformed commitments fail closed. Consumers can recompute the commitment with `verify_room_context_commitment(...)`.

The byte-level commitment contract is pinned by
`tests/fixtures/room_context_commitment_v1.json`. Implementations in other
languages must reproduce its `canonical_json` and `room_context_digest`
exactly. Abstention omissions expose only `applied`, `reason`, bounded
`abstained_ids`, `abstained_count`, and bounded `conflict_reasons`; arbitrary
retrieval metadata never crosses the HTTP boundary.

An active room whose retrieval path returns no candidate uses the bounded abstention reason `no-relevant-memory`; a room with no active memory remains `empty`. This keeps a semantic miss distinguishable from a cold room without adding another context-state enum or changing the commitment schema.

### Record Accepted Room State

Only the trusted Rooms service should call `record`:

```bash
curl -fsS http://127.0.0.1:8766/v1/memories:record \
  -H "Authorization: Bearer $ZMEM_SERVICE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "room_id": "rom_alpha",
    "agent_id": "agt_cursor",
    "content": "Production deploys require release approval.",
    "memory_type": "procedural",
    "visibility": "room",
    "source_event_id": "evt_release_policy_1",
    "idempotency_key": "evt_release_policy_1:procedure"
  }'
```

The memory is active because Rooms is asserting an accepted room transition. The contributing agent remains visible in labels and the source event remains in the write receipt.

### Propose Agent Memory

Agent-authored claims use `propose` and start quarantined:

```bash
curl -fsS http://127.0.0.1:8766/v1/memories:propose \
  -H "Authorization: Bearer $ZMEM_SERVICE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "room_id": "rom_alpha",
    "agent_id": "agt_cursor",
    "content": "The deployment target may have changed to eu-west.",
    "memory_type": "semantic",
    "visibility": "room",
    "source_event_id": "evt_agent_claim_9",
    "idempotency_key": "evt_agent_claim_9:target"
  }'
```

It will be reported as withheld until reviewed. The first service contract intentionally does not expose a remote promote/reject endpoint; authority remains on the existing local review surface until Gateway has a separate operator capability.

`visibility: "member"` creates memory visible only to the named agent inside that room. It does not leak into another member's context or another room.

## Required Gateway Interface Change

The current Rooms interface cannot carry the product contract:

```go
Read(ctx context.Context, scope Scope) ([]Entry, error)
Append(ctx context.Context, scope Scope, content string) (Entry, error)
```

It loses `room_id`, purpose, risk, budget, ranked order, omitted memory, state, provenance, and the commitment. It should become a context-preparation interface rather than a CRUD interface:

```go
type PrepareRequest struct {
    RoomID             string
    AgentID            string
    Purpose            string
    Risk               string
    ContextBudgetTokens int
    MembershipDigest   string
    RoomStateDigest    string
}

type ContextResult struct {
    State      string
    Memories   []Memory
    Counts     Counts
    Omissions  Omissions
    Commitment Commitment
}

type Store interface {
    PrepareContext(ctx context.Context, req PrepareRequest) (ContextResult, error)
    Propose(ctx context.Context, req ProposeRequest) (WriteResult, error)
    Record(ctx context.Context, req RecordRequest) (WriteResult, error)
}
```

The concrete Go client should:

1. Resolve the room before the call and use `room.Goal` as `Purpose`.
2. Never send `tenant_id`; it is fixed by service configuration. Assert that the response tenant matches the client's configured expectation and fail closed on mismatch.
3. Apply a short explicit HTTP timeout and fail the join closed on transport or commitment failure.
4. Preserve ZMem's returned order. Do not re-sort chronologically.
5. Branch on `State`; do not treat every HTTP `200` as usable context.
6. Keep caller-provided onboarding documents separate from governed memory. Do not silently append them to the admitted memory list. Trusted room events may call `record`; agent claims call `propose`.
7. Keep the service token in Gateway configuration and never expose it to room members.

## Performance And Reliability Gate

The implementation uses one SQLite connection per request with WAL and the existing five-second busy timeout. Local development measurements on 2026-08-09 showed an empty-context cold call around `34 ms`, warm mean around `7 ms`, and warm p95 around `9 ms`. These are engineering observations, not a production SLO.

Before zerker.ai production traffic:

- run a Gateway-to-ZMem load test with realistic room sizes;
- set and test the Gateway timeout and retry policy;
- verify concurrent identical writes replay rather than duplicate;
- verify cross-room, cross-member, and cross-tenant isolation;
- persist the Rooms room/event store itself;
- keep Treeship publication asynchronous and separately observable.

## Decisions Against The Draft Questions

- Withheld state is first-class, not a log line.
- Room goal is the retrieval purpose; risk and budget are explicit room/tenant policy.
- Preserve policy-ranked order and metadata.
- Replace unused `Append` with distinct `Propose` and trusted `Record` operations.
- Gateway Rooms owns collaboration. Treeship proves selected transitions.
- Ship tenant-local co-location first. Hosted multi-tenant routing comes after a dedicated auth and isolation review.
