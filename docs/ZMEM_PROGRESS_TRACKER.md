# ZMem Progress Tracker

Last updated: 2026-07-06

This is the shared progress board for ZMem release and frontier work. It turns the
continuous-build lanes into a checkpointable product plan: what is built, what is
shipped, what remains, and when an automation can be paused.

Every push or meaningful automation drop should update this file alongside:

- `docs/CURRENT_STATE.md`
- `docs/BUILD_LOG.md`
- `docs/SWARM_OPERATION_TRACKER.md`
- the matching `docs/CONTINUOUS_BUILD/*.log.md`
- public docs or `CHANGELOG.md` when user-facing behavior changes
- `docs/internal/ZMEM_RELEASE_COMMS.md` when a change needs internal launch context

## Release State

| Release | Status | Commit | Notes |
| --- | --- | --- | --- |
| `v0.1.0` | Historical tag | `f460191` | Earlier launch checkpoint. Do not move this tag. |
| `v0.1.1` | Published | `e9c80c5` | Previous public alpha release. CI passed on Python 3.10/3.11/3.12 plus release-smoke. |
| `v0.1.2` | Published | `v0.1.2` tag | Continuous swarm hardening release. CI passed on Python 3.10/3.11/3.12 plus release-smoke. |

Current public release:

- GitHub: `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.2`
- Site: `https://www.zmem.sh`
- Raw installer: `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`

Current `v0.1.2` release checkpoint:

- Base checkpoint: `91c792f Land continuous swarm hardening`
- Landed the paused swarm harvest as one coherent checkpoint because the lane output crossed `store.py`, `cli.py`, tests, dashboards, and shared control-room docs.
- Local verification passed: `python3 -m unittest discover -s tests -q`, `python3 -m zerker_memory eval`, `python3 scripts/release_smoke.py --summary-only`, and `git diff --check`.
- Remote verification passed in GitHub Actions on Python 3.10, 3.11, and 3.12 plus `release-smoke`.
- Keep swarms paused until the release tag/deploy is complete, then restart only bounded lanes with isolated benchmark output directories.

## Lane Scoreboard

Percentages are practical launch-grade alpha estimates, not benchmark scores.

| Lane | Focus | Alpha completion | Shipped state | Next acceptance target |
| --- | --- | ---: | --- | --- |
| L0 Trust Ledger | Receipts, Merkle lineage, restore/export proof | 70% | Mutation/lifecycle/restore receipts exist; handoff restore verifies and summarizes restore receipts | Add compact read-only mutation-chain summary and direct snapshot-restore receipt summary |
| L1 Temporal KG | Current/history/superseded temporal memory | 55% | `query_at`, supersession, omitted-memory envelopes, runtime temporal context | Add contradiction/abstention runtime fixture and decide when true bi-temporal graph schema is needed |
| L2 Lifecycle Compaction | Sessions, checkpoints, snapshots, retention | 45% | Checkpoint/snapshot store contracts plus read-only CLI summaries | Add write-facing `zmem session checkpoint` or retention policy without widening scope |
| L3 Retrieval Baseline | FTS/BM25, semantic backfill, RRF, packing | 68% | Hybrid semantic, multi-hop RRF, temporal support-chain RRF, chronology mutation RRF, update-history relation-pair RRF shipped in `v0.1.2` | Rerun LoCoMo mode deltas in isolated output dirs |
| L4 Consolidation | Hierarchical summaries and job ledger | 35% | Deterministic fixture, job lifecycle, reversible summary payloads, append-only summary ledger | Source candidates from live store or expose persisted summaries through read-only CLI |
| L5 Identity / Workspaces | Multi-agent source lineage and conflicts | 50% | Source reports, claim conflicts, resolution basis, exact-tie abstention summaries | Persist merge decisions or add repo/tool lineage descriptors |
| L6 Benchmark Harness | LoCoMo/LongMemEval/BEAM evidence | 45% | Synthetic/LoCoMo/LongMemEval-style harnesses, full LoCoMo FTS baseline, ActiveGraph compact smoke | Resume with isolated dirs: LoCoMo `fts-multihop`, `pseudo-embedding`, `pseudo-embedding-rerank`, `zmem-retrieval`; then LongMemEval-S |
| Launch Oversight | Release pack, proof evidence, public release | 92% | Public verify `6/6`, assets `8/8`, return packet ready, `v0.1.2` pushed and CI-green | Tag/deploy `v0.1.2`, then keep launch automation paused/archived after one clean post-release check |
| Website / Docs | Landing, proof page, docs, changelog | 70% | Site live, proof page, changelog, ActiveGraph/blog/docs, benchmark docs | Add release writeup discipline: public changelog, public docs, internal comms after each push |
| ActiveGraph Integration | Event substrate and compact traces | 45% | Source pack, `zmem.persist`, `zmem.recall`, `zmem-bench-locomo`, 5-question compact smoke | Clean `activegraph pack add zmem` smoke and batching/perf for full traces |

## Lane Checklists

### L0 Trust Ledger

Built:

- [x] Memory/action receipts.
- [x] Merkle event log.
- [x] Mutation receipts for promote, reject, revoke, forget.
- [x] Lifecycle receipts for checkpoint, snapshot, restore.
- [x] Restore receipt verification.
- [x] Receipt-aware handoff restore summary.
- [x] Treeship-ready export/publish path.

Left:

- [ ] Direct CLI summary for ordered per-memory mutation chains.
- [ ] Direct snapshot restore should show the same compact receipt summary as handoff restore.
- [ ] Typed predicate/schema validation once the Treeship registry work lands.
- [ ] Local key/signature story beyond Merkle proof.

### L1 Temporal KG

Built:

- [x] `query_at(...)`.
- [x] Supersession/history/current/future/unlearned temporal projections.
- [x] Temporal envelopes in receipts.
- [x] Withheld and budget-dropped temporal graphs.
- [x] Runtime context preserves temporal metadata for agents.
- [x] Same-subject update supersession without requiring parent edges.

Left:

- [ ] True bi-temporal graph schema/edges.
- [ ] Contradiction-driven abstention envelope.
- [ ] Richer temporal query filters.
- [ ] Entity/relation graph traversal.
- [ ] Temporal benchmark proof beyond fixtures.

### L2 Lifecycle Compaction

Built:

- [x] Checkpoint/session snapshot store contracts.
- [x] Read-only CLI summaries for `zmem session checkpoints`.
- [x] Read-only CLI summaries for `zmem session snapshots`.
- [x] Snapshot payload visibility and retention tombstone reporting.
- [x] Lifecycle memory-class separation in context.

Left:

- [ ] CLI write surface for checkpoint/snapshot.
- [ ] `start_session` / `end_session` user flow.
- [ ] Automatic retention/compaction policy.
- [ ] Session lifecycle UX for real agent continuation.

### L3 Retrieval Baseline

Built:

- [x] SQLite FTS baseline.
- [x] Semantic backfill metadata.
- [x] Local reranking improvements.
- [x] Baseline-only semantic ordering when reranker is disabled.
- [x] Target-history support/current pair preservation.
- [x] Target-history selection exclusions in receipts.
- [x] Multi-hop RRF ordering.
- [x] Temporal support-chain RRF.
- [x] Chronology mutation RRF.
- [x] Update-history stale/current pair RRF.
- [x] Update-history relation-pair RRF verified locally.
- [x] Receipts explain selected, excluded, injected, withheld, and budget-dropped candidates.

Left:

- [ ] Commit and push the current relation-history RRF diff.
- [ ] Full benchmark reruns to prove deltas.
- [ ] Real dense embeddings / sqlite-vec path.
- [ ] Graph traversal fusion.
- [ ] Abstention confidence threshold.
- [ ] Context expansion around nucleus memories.
- [ ] Query decomposition beyond the current local heuristic.

### L4 Consolidation

Built:

- [x] Deterministic local consolidation fixture.
- [x] Job ledger with pending/running/completed lifecycle.
- [x] Reversible summary payloads.
- [x] Append-only summary ledger.
- [x] Duplicate suppression.
- [x] Source child ids and content digests.

Left:

- [ ] Real store-backed candidate sourcing.
- [ ] Runtime summary writer.
- [ ] Periodic daemon/scheduler.
- [ ] Hierarchical consolidation levels in normal memory use.
- [ ] UX for inspecting consolidated summaries.

### L5 Identity / Workspaces

Built:

- [x] Workspace source reports.
- [x] Connected agent/source visibility.
- [x] Claim conflicts across agents/sessions.
- [x] Deterministic merge preview by authority, trust, freshness, or exact-tie abstention.
- [x] `zmem workspace sources --summary-only` with lineage details.
- [x] Dashboard/source conflict visibility.

Left:

- [ ] Persisted merge decisions.
- [ ] Identity keys / cryptographic agent identity anchors.
- [ ] Rich source-lineage details for repo/tool/context.
- [ ] Team/workspace permission model.
- [ ] Merge/resolve UX.

### L6 Benchmark Harness

Built:

- [x] Synthetic benchmark matrix.
- [x] LoCoMo harness.
- [x] LongMemEval-style harness.
- [x] Metrics for F1, EM, latency, tokens, retrieval stats.
- [x] Matrix receipts with hashes/proof roots.
- [x] Official local LoCoMo FTS baseline: F1 `0.3752`, EM `0.3721`.
- [x] LongMemEval local matrix exists.
- [x] ActiveGraph compact 5-question smoke.

Left:

- [ ] Resume benchmark runs with isolated output dirs.
- [ ] Full LoCoMo `fts-multihop`.
- [ ] Full LoCoMo `pseudo-embedding`.
- [ ] Full LoCoMo `pseudo-embedding-rerank`.
- [ ] Full LoCoMo `zmem-retrieval`.
- [ ] LongMemEval-S abstention/token efficiency run.
- [ ] BEAM scale benchmark.
- [ ] ActiveGraph batching/performance for full traces.
- [ ] Public benchmark page/report polish after real deltas.

### Launch Oversight

Built:

- [x] Release pack.
- [x] Clean-shell operator packet.
- [x] Public verify logs: `6/6`.
- [x] Launch assets: `8/8`.
- [x] Return packet ready.
- [x] Strict prelaunch gate green.
- [x] GitHub release `v0.1.1` published.
- [x] Site live at `zmem.sh`.
- [x] CI green.

Left:

- [ ] Keep release docs/changelog synchronized after every push.
- [ ] Decide whether to pause, archive, or delete old launch automation after one clean post-release check.
- [ ] Publish ongoing release notes for `v0.1.2+`.
- [ ] Optional package registry publishing.

### Website / Docs

Built:

- [x] Public landing site.
- [x] Proof/status page.
- [x] Changelog page.
- [x] ActiveGraph page/blog.
- [x] Benchmark docs.
- [x] Feature guide.
- [x] Builder experience docs.
- [x] Clean-shell proof docs.
- [x] Site styling, favicon, static build, and deployment fixed.
- [x] Homepage positioning refined around governed memory, memory authority, review before trust, provider overlay, and handoff.

Left:

- [ ] Update public docs to reflect `v0.1.1` fully.
- [ ] Add this progress tracker to public/internal navigation where appropriate.
- [ ] Add an internal release communications brief after each release.
- [ ] Keep changelog synced after each push.
- [ ] Improve the public product matrix for "what shipped / what is next".
- [ ] Optional docs-site deployment at `docs.zmem.sh`.

### ActiveGraph Integration

Built:

- [x] `pack/pack.yaml`.
- [x] `activegraph.packs` entry point.
- [x] `zmem.persist`.
- [x] `zmem.recall`.
- [x] Cross-run/session memory scope: `ag:{session_id}`.
- [x] `caused_by_event` linkage.
- [x] Optional Treeship write/read artifact path.
- [x] Compact LoCoMo runner: `zmem-bench-locomo`.
- [x] Five-question compact trace smoke with no per-question receipt bundles.

Left:

- [ ] Real `activegraph pack add zmem` install smoke in a clean networked environment.
- [ ] Performance/batching fix for full official benchmark traces.
- [ ] Better docs around ActiveGraph use cases.
- [ ] Full benchmark run through the ActiveGraph compact trace path.
- [ ] Blog post after the full trace path is proven.

## Per-Push Release Hygiene

Every push that changes user-facing behavior should update:

- [ ] `CHANGELOG.md`
- [ ] public docs under `README.md`, `QUICKSTART.md`, or `docs/content/docs/`
- [ ] `docs/PRODUCT_STATUS.md` if capability status changed
- [ ] this progress tracker
- [ ] `docs/internal/ZMEM_RELEASE_COMMS.md` or a dated internal brief

Every release tag should include:

- [ ] exact commit SHA
- [ ] CI status
- [ ] local verification commands
- [ ] public site status
- [ ] raw installer status
- [ ] release notes with public claim boundaries

## Current Highest-Leverage Next Move

1. Push this `v0.1.2` candidate checkpoint and wait for CI.
2. Resume benchmarks only after output dirs are isolated.
3. Run LoCoMo `fts-multihop`, `pseudo-embedding`, `pseudo-embedding-rerank`, and `zmem-retrieval` as separate run ids.
4. Use the deltas to decide whether the next L3 slice is abstention, context expansion, or graph fusion.
