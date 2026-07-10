# Zerker Memory Proof Schema

Zerker Memory proof artifacts are local-first JSON documents designed to be checked without a hosted service.

## Treeship Statement

Command:

```bash
zmem export <action-id> --format treeship --out-dir .zerker/exports
zmem treeship doctor
zmem treeship publish <action-id> --dry-run --command-template "treeship prove {statement} --action {action_id}"
```

Schema: `com.zerker.memory.treeship.statement`

The Treeship export is a portable statement derived from a verified receipt bundle, not just a raw receipt reshape.
For lifecycle mutation receipts that already embed a Treeship statement,
export helpers can also emit that embedded statement unchanged after
recomputing the lifecycle `receipt_hash` and checking the embedded
`source.receipt` linkage locally. That preserves actor/content/root
lineage for session and restore mutations without requiring a live
store or a local Treeship install, but restore statements still need
the original snapshot artifact if an external verifier wants to
re-check the `source_snapshot_verified` claim.
For per-memory write receipts that already embed a Treeship statement,
export helpers can also emit the embedded provenance or mutation
statement after locally re-verifying the receipt hash, source event
linkage, optional Treeship attestation metadata, and any signed prior
receipt id/hash/root anchors already carried on the receipt. Export now
normalizes `object.semantic_truth_guaranteed=false` when older mutation
statements omitted it, but a standalone exported mutation receipt still
proves only the current receipt's provenance/integrity plus its signed
linkage hints. Full ordered-chain continuity still requires the prior
receipt or a lineage/snapshot proof surface.

Core fields:

- `evidence.bundle_hash`: stable hash of the underlying receipt bundle.
- `evidence.bundle_event_count`: number of append-only events committed by the bundle proof.
- `evidence.bundle_event_witness_count`: number of compact event inclusion witnesses carried by a v2 bundle.
- `evidence.bundle_verified`: true only when the bundle proof recomputes to the receipt Merkle root.
- `evidence.supporting_write_receipt_count` / `evidence.verified_supporting_write_receipt_count`: how many embedded supporting write receipts were carried and locally re-verified from the bundle payload.
- `evidence.trusted_provenance_verified`: true only when every embedded supporting write receipt verifies locally.
- `object.semantic_truth_guaranteed`: always false; the statement proves provenance/integrity, not semantic truth.
- `source.bundle`: the embedded receipt bundle used to build the statement.
- `source.supporting_provenance_receipts`: compact supporting provenance anchors with memory id, actor id, content digest, Merkle-root transition, and optional Treeship artifact id.

Export fails when the bundle hash, Merkle proof, receipt identity, or embedded supporting provenance receipts do not validate locally.

`zmem treeship publish` reuses that same verified statement export, then invokes a local Treeship CLI command template. `{statement}` expands to the exported JSON path and `{action_id}` expands to the governed action ID. If `{statement}` is omitted, Zerker appends the statement path as the final argument.

## Receipt Bundle

Command:

```bash
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
```

Current schema: `zerker.receipt_bundle.v2`

Legacy schema: `zerker.receipt_bundle.v1` remains verifiable, and can still be generated through the Python API with `store.receipt_bundle(action_id, compact=False)`.

The bundle proves which governed memories were available before an agent action and whether the receipt Merkle root matches the supporting event chain.

Core fields:

- `bundle_hash`: SHA-256 over the stable JSON bundle without `bundle_hash`.
- `receipt`: the agent action receipt returned by `zmem inject`.
- `supporting_memories`: retrieved memories cited by the receipt.
- `supporting_memory_write_receipts`: original provenance receipts for the cited memories.
- `event_log`: event count, sequence anchors, final pre-action event hash, and Merkle root for the full pre-action log.
- `event_witnesses`: payload-hash-only event records plus indexed Merkle inclusion proofs for every supporting write event and the final pre-action event.
- `proof.event_log_merkle_root`: Merkle root committed by the compact event-log proof.
- `proof.receipt_merkle_root`: Merkle root stored in the action receipt.
- `proof.event_witnesses_verified`: true when every carried event witness recomputes and verifies against the receipt root.
- `proof.verified`: true when the committed event-log root matches the receipt root and the generated witnesses are valid.

V2 does not copy every historical event payload into every action artifact. It keeps the full log committed by the same receipt Merkle root and carries only the events needed to verify supporting write provenance plus a final-log anchor. In a 31-event repeated-action regression fixture, this reduced serialized output from 963,288 bytes to 35,453 bytes (96.32%) while both v1 and v2 verified successfully.

Verification fails when the bundle hash, action ID, event hash material, indexed Merkle witness, supporting write-event linkage, Merkle root, or embedded proof fields do not match. The proof establishes tamper-evident inclusion and provenance relative to the anchored root; it does not establish that remembered content is semantically true. A Treeship attestation can independently sign the portable statement derived from the verified bundle.

V1 bundles carry the complete pre-action event list under `supporting_events` and recompute `proof.computed_merkle_root`. Their verification contract is unchanged.

## Snapshot

Command:

```bash
zmem snapshot --out-dir .zerker/exports
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
```

Schema: `zerker.memory_snapshot.v1`

The snapshot proves a portable memory-store state at export time.

Core fields:

- `snapshot_hash`: SHA-256 over the stable JSON snapshot without `snapshot_hash`.
- `memories`: full memory records.
- `events`: append-only memory event log.
- `receipts`: action receipts and explanations.
- `merkle_root`: Merkle root recomputed from event hashes.
- `memory_count`, `event_count`, `receipt_count`: integrity counts for fast mismatch detection.

Verification fails when the snapshot hash, Merkle root, schema, algorithm IDs, or counts do not match.
