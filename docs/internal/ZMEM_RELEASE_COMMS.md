# ZMem Release Comms

## 2026-07-06 - v0.1.2 release checkpoint

Audience: internal Zerker launch/build coordination.

### What changed

- The paused continuous-swarm harvest is landed on `main` as `91c792f Land continuous swarm hardening`.
- CI is green on Python 3.10, 3.11, and 3.12 plus release-smoke.
- The release includes trust-ledger, temporal, lifecycle, retrieval, consolidation, identity/workspace, dashboard, and release-proof hardening.
- Website positioning now leads with governed memory for agents that act.
- The homepage explains ZMem as native local memory plus an authority gate: propose, review, inject, withhold, revoke, verify.
- The copy avoids competing on generic durable context. The sharper line is: search finds context; ZMem decides what becomes trusted memory.
- L3 retrieval has a verified local candidate slice for update-history relation-pair RRF, promoting explicit stale/current relation pairs over generic high-authority change anchors.
- The shared progress tracker now records lane status, acceptance targets, and what remains before automations can pause.

### Claim boundaries

- Do not claim benchmark wins from this slice until isolated LoCoMo and LongMemEval runs are complete.
- Do not claim semantic truth. ZMem records memory state, lineage, injection, withholding, and influence.
- Do not claim every memory entry is independently Ed25519-signed unless the Treeship path was used for that receipt.
- Do not present ActiveGraph full-trace runs as complete; the compact smoke works, full batching/performance still needs hardening.

### Next external-facing message

ZMem is an open-source, local-first memory system for agents with review before trust. Agents can request approved memory, propose new facts, hand off governed state, and produce receipts showing what memory influenced an action.

### Next build move

Tag and deploy `v0.1.2`, then resume benchmarks in isolated output directories:

```bash
zmem bench matrix locomo \
  --dataset data/locomo/locomo_official_zmem.json \
  --out .zerker/bench \
  --run-id locomo-official-v1-fts-multihop-20260624 \
  --mode fts-multihop \
  --seed 42
```
