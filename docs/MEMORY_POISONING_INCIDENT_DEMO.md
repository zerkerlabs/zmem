# ZMem Memory-Poisoning Incident Demo

This demo shows the Phase 1 provenance wedge: every memory write has a local Treeship-ready write receipt, and later action receipts can trace injected memories back to the write actor, source session, source URI, parent action receipt, content digest, environment hash, event hash, and Merkle root.

## Run

Use a fresh demo database so the retrieval story is clean:

```bash
python3 -m zerker_memory --db /tmp/zmem-poison-demo.sqlite poison-demo --out-dir /tmp/zmem-poison-demo
```

The command writes:

- `/tmp/zmem-poison-demo/incident-report.md`
- `/tmp/zmem-poison-demo/incident-bundle.json`

## Narration

1. A prompt-injected tool result writes the false fact `Payment service owner is Mallory`.
2. The write emits `zerker.memory_write.v1` provenance with a Treeship-ready statement.
3. Later sessions add normal operational memory.
4. A later agent action asks who owns the payment service and receives the poisoned memory.
5. `zmem why <action-id>` shows the action receipt and `injected_memory_write_receipts`.
6. The bundle shows `supporting_memory_write_receipts.<memory-id>`, proving the backward chain to the exact actor, session, source URI, parent action, content digest, event hash, and Merkle root.

## Video Shape

- Minute 0-1: show the poisoned write source and generated receipt fields.
- Minute 1-2: show later action using the memory.
- Minute 2-4: walk backward through `why` and the incident bundle.
- Minute 4-5: explain why this is the security wedge: memory poisoning becomes reconstructable instead of folklore.
