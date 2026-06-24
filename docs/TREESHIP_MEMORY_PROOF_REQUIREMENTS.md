# Treeship Memory Proof Requirements

ZMem is the first customer for Treeship memory proofs, but the contract should stay provider-neutral so Mem0, Zep, Letta, SQLite-backed stores, and future Zerker Gateway memory systems can use the same proof rail.

## ZMem Proof Surfaces To Preserve

ZMem already emits several local-first proof artifacts:

- Action receipts: every governed memory injection records retrieved, injected, and withheld memory IDs, policy checks, task hash, agent ID, Merkle root, and memory-tree root.
- Receipt bundles: `zmem bundle <action-id>` packages the receipt with supporting memories, supporting append-only events, a bundle hash, and a recomputed Merkle proof.
- Memory snapshots: `zmem snapshot` exports full local memory state, receipts, event log, counts, snapshot hash, and Merkle root for portable restore.
- Memory trees: action receipts include a memory tree that proves the injected active memory set without requiring trust in a hosted service.
- External provider governance: Mem0 and Zep candidates can be searched, normalized, imported into quarantine, labeled by provider/external ID, and governed locally before use.
- Handoffs: `zmem handoff` packages a verified snapshot, latest receipt bundle, handoff manifest, and Treeship-ready statement for cross-agent or cross-machine restore.
- Launch proof packs: `zmem release-pack` and `zmem launch-proof` package clean-shell verification commands, public-verify logs, result receipts, launch assets, operator packets, and return-packet verification.
- Treeship bridge: `zmem export --format treeship` produces a verified statement from a receipt bundle, and `zmem treeship publish` signs it through Treeship as `system://zmem` / `kind=memory.proof`.
- Optional write attestation: when `ZMEM_TREESHIP_AUTO_SIGN=1` is enabled, each memory write asks Treeship to attest the compact `sha256:<receipt_hash>` digest as `system://zmem` / `kind=memory.write`, then stores only the returned artifact id, signed timestamp, digest, and status with the write receipt. This avoids duplicating raw memory content while making the receipt externally attributable.

## Treeship Contract ZMem Needs

Treeship should support proofing memory systems without owning memory semantics.

- Receipt CLI: `treeship attest receipt --system <system-uri> --kind <kind> --payload-file <path>` is the current target. Treeship `v0.12.0` published this surface; ZMem keeps an inline `--payload` fallback for older customer CLIs.
- Digest-only receipt CLI: `treeship attest receipt --system <system-uri> --kind <kind> --payload-digest sha256:<hex>` is the write-time path for compact memory-write attestations.
- Boundary proof payloads: ZMem should move toward the `treeship.boundary.v1` profile in [`BOUNDARY_PROOF_SCHEMA.md`](BOUNDARY_PROOF_SCHEMA.md), which separates proven fields from asserted/policy-derived fields.
- Provider-neutral identity: examples should use `system://<provider>` and `memory://<provider>/<namespace>/<key>` instead of ZMem-only naming.
- Safe defaults: Treeship should sign proof payloads, payload digests, summaries, and provider URIs by default; it should not require raw prompts, raw memories, embeddings, or private recall traces.
- Memory proof kinds: `memory.proof` should be a first-class documented receipt kind, but providers should be free to define narrower kinds.
- Suggested action labels: `memory.read`, `memory.write`, `memory.delete`, `memory.query`, `memory.retrieve`, `memory.inject`, `memory.compact`, `memory.handoff`.
- Verify readability: public verify pages should summarize system, kind, artifact ID, subject/action ID, signed time, provider, payload digest, and proof status, with raw JSON secondary.
- Hub activation: attach flows must preserve terminal states so browser polling never turns a successful attach into `device_code not found`.

## Current Treeship Release Status

Treeship `v0.12.0` is the first release aligned with this ZMem proof contract:

- published CLI includes `attest receipt --payload-file`;
- published CLI includes `--payload-digest`;
- published CLI includes `attest action --output-digest`;
- provider-neutral memory proof docs are published;
- Hub activation state-machine fixes are merged and released in source, but require the Hub/API service to be redeployed before `api.treeship.dev` reflects the new activation states.

Until the Hub/API redeploy is verified, ZMem can still produce local proof artifacts and Treeship-signed receipts. Public Hub attach UX may still show the old activation behavior.

## Adapter Shape

ZMem-side adapters should normalize external memory into local governed candidates. Treeship-side adapters should not fetch or interpret memory. The clean split is:

1. Provider adapter searches or imports memory candidates.
2. ZMem governance decides whether candidates are quarantined, promoted, injected, withheld, revoked, forgotten, or handed off.
3. ZMem emits local receipts, bundles, snapshots, and Treeship statements.
4. Treeship signs and publishes portable proof artifacts.
5. Zerker Gateway can later compose ZMem, Treeship, and Guard as one operator surface without changing the proof primitive.

## Gateway Integration Target

The Gateway should treat ZMem as the memory authority, Treeship as the proof authority, and Guard as the execution/policy authority.

- ZMem answers: what memory was available, why it was used or withheld, and how it can be restored.
- Treeship answers: who signed the proof, when, what payload digest was attested, and whether the artifact verifies offline.
- Gateway answers: which agent/session/action should receive which memory/proof/policy context.

## Treeship Agent Checklist

When coordinating a Treeship PR, verify it covers:

- `--payload-file` for `attest receipt`.
- Provider-neutral memory proof docs.
- Hub activation terminal state fix.
- CLI attach next-step copy.
- Public verify page readability for memory proofs.
- Tests for challenge state transitions and receipt CLI file payloads.
- No ZMem hardcoding beyond examples.
