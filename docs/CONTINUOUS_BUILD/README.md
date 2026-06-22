# ZMem Continuous Build Logs

This directory stores lane logs for the continuous Codex build.

Read `docs/ZMEM_CONTINUOUS_BUILD_ORCHESTRATOR.md` first. Every agent or automation should append to exactly one lane log per slice and keep entries short enough to review.

Lane logs:

- `trust-ledger.log.md`
- `temporal-kg.log.md`
- `lifecycle-compaction.log.md`
- `hybrid-retrieval.log.md`
- `consolidation.log.md`
- `identity-workspaces.log.md`
- `benchmark.log.md`
- `launch.log.md`

Entry template:

```md
## 2026-06-22T00:00:00Z - <lane> - <agent or automation id>

- Scope:
- Files touched:
- Behavior changed:
- Tests:
- Artifacts/receipts:
- Blockers:
- Next safe slice:
```
