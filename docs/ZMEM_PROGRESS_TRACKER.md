# ZMem Progress Tracker

Last updated: 2026-07-10

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
| `v0.1.3` | Published | `d029b99` / `v0.1.3` | Agent capability boundary, compact proof bundles, CLI summaries, and public site/docs hardening. |

Current public release:

- GitHub: `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.3`
- Site: `https://www.zmem.sh`
- Raw installer: `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`

Current `v0.1.3` release checkpoint:

- Core checkpoint: `ebb387d Harden agent memory boundaries and compact proofs`.
- Public experience checkpoint: `766a668 Polish ZMem public experience and web CI`.
- Final verified release head: `d029b99 Align release smoke with safe agent profile`.
- Local verification passed: `1215` tests, eval `11/11`, release smoke, strict prelaunch, site lint/build, docs typecheck/build, dependency audits, and responsive browser QA.
- Remote verification passed in GitHub Actions across Python 3.10, 3.11, and 3.12, release smoke, site, and docs jobs.
- Keep broad swarms paused after the release. Resume Retrieval + Benchmark only with isolated output directories.

Shipped in `v0.1.3`:

- Default agent MCP access is now capability-limited; operator authority requires an explicit local profile.
- SQLite uses private file permissions, WAL, and bounded lock waiting for concurrent local agents.
- `inject` and `why` have compact daily-use summaries without changing their JSON defaults.
- Public site/docs facts, benchmark storage guidance, and LoCoMo evidence are aligned with the current implementation.
- Compact receipt bundle v2 replaces repeated full event histories with supporting-event Merkle witnesses by default; legacy v1 artifacts remain verifiable.
- A 31-event repeated-action fixture measured a 96.32% serialized-size reduction (963,288 bytes to 35,453 bytes), with both formats verifying successfully.
- Site and docs now have dedicated CI build gates.
- Full Python tests (`1215`), eval (`11/11`), release smoke, both web builds, and production-preview responsive QA pass locally.
- Docs audit and the site production-dependency audit report zero vulnerabilities; site development tooling still has advisories pending a separate Vite major upgrade.

## Lane Scoreboard

Percentages are practical launch-grade alpha estimates, not benchmark scores.

| Lane | Focus | Alpha completion | Shipped state | Next acceptance target |
| --- | --- | ---: | --- | --- |
| L0 Trust Ledger | Receipts, Merkle lineage, restore/export proof | 80% | Mutation/lifecycle/restore receipts and compact v2 event witnesses exist; default MCP agents cannot claim trusted write/review authority | Add compact read-only mutation-chain summary and direct snapshot-restore receipt summary |
| L1 Temporal KG | Current/history/superseded temporal memory | 55% | `query_at`, supersession, omitted-memory envelopes, runtime temporal context | Add contradiction/abstention runtime fixture and decide when true bi-temporal graph schema is needed |
| L2 Lifecycle Compaction | Sessions, checkpoints, snapshots, retention | 45% | Checkpoint/snapshot store contracts plus read-only CLI summaries | Add write-facing `zmem session checkpoint` or retention policy without widening scope |
| L3 Retrieval Baseline | FTS/BM25, semantic backfill, RRF, packing | 78% | Conservative adaptive routing is receipt-visible and beats both FTS and always-on multi-hop on LoCoMo while keeping LongMemEval gains regression-free | Improve the remaining multi-hop/open-domain misses without widening the one-loss LoCoMo boundary |
| L4 Consolidation | Hierarchical summaries and job ledger | 35% | Deterministic fixture, job lifecycle, reversible summary payloads, append-only summary ledger | Source candidates from live store or expose persisted summaries through read-only CLI |
| L5 Identity / Workspaces | Multi-agent source lineage and conflicts | 50% | Source reports, claim conflicts, resolution basis, exact-tie abstention summaries | Persist merge decisions or add repo/tool lineage descriptors |
| L6 Benchmark Harness | LoCoMo/LongMemEval/BEAM evidence | 88% | Verified four-mode and adaptive LoCoMo/LongMemEval evidence exists; compact stores are bounded and every matrix verifies | Add stable-miss slices and BEAM scale evidence |
| Launch Oversight | Release pack, proof evidence, public release | 100% for v0.1.3 | Public verify `6/6`, assets `8/8`, return packet ready, `v0.1.3` published and deployed | Keep automation paused; repeat the gate only for the next release |
| Website / Docs | Landing, proof page, docs, changelog | 100% for v0.1.3 | Agent-first copy, proof/docs routes, factual benchmark page, dedicated CI gates, and responsive QA | Keep factual surfaces aligned as retrieval evidence changes |
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
- [x] Default agent MCP profile excludes trusted write, review, import, and restore authority.
- [x] Agent proposals cannot claim human/system source authority.
- [x] Local SQLite defaults use private permissions, WAL, and bounded lock waiting.
- [x] Compact v2 receipt bundles with indexed supporting-event witnesses and backward-compatible v1 verification.

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
- [x] Optional `fts-adaptive` benchmark mode delegates activation to store routing.
- [x] Adaptive proofs record activation, evaluation, and suppression reasons.
- [x] Conservative semantic escalation gate verified on full LoCoMo and LongMemEval runs.

Left:

- [x] Relation-history RRF diff landed in the `v0.1.2` swarm hardening release.
- [x] Full benchmark reruns prove adaptive deltas against FTS and always-on multi-hop.
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
- [x] Fresh same-commit four-mode LoCoMo matrix at `871f23d`: matrix verification `ok`, comparison verification `ok`, matrix hash `9f8b77ca...`, comparison hash `18cdca15...`.
- [x] Full local LoCoMo FTS evidence: provisional accuracy `0.5967`, mean query tokens `536.0`.
- [x] Full isolated LoCoMo FTS-multihop evidence: provisional accuracy `0.6067`, mean query tokens `425.8`.
- [x] Fresh LongMemEval local matrix: `500` questions, matrix/comparison verification `ok`, matrix hash `e5dd8b06...`, comparison hash `a69090df...`.
- [x] ActiveGraph compact 5-question smoke.
- [x] Normal benchmark receipt bundles use compact v2 event witnesses by default; `--compact-artifacts` remains available to omit per-question bundles entirely.

Left:

- [x] Benchmark docs and commands use isolated output dirs plus compact artifacts.
- [x] Full LoCoMo `fts-multihop`.
- [x] Full LoCoMo `pseudo-embedding`: current-code Python 3.11 run, `1,986` questions, accuracy `0.5967`, token F1 `0.5969`, mean query tokens `536.0`, verified result hash `3d31a2ee...`.
- [x] Full LoCoMo `pseudo-embedding-rerank`: `1,986` questions, accuracy `0.5967`, token F1 `0.5969`, zero SQLite artifacts, verified result hash `427864c9...`; no quality delta from pseudo-embedding.
- [x] Confirmed `zmem-retrieval` resolves to `pseudo-embedding-rerank`; no duplicate full run is needed.
- [x] Same-commit category delta audit: multihop gains `98`, loses `78`, and nets `+20` questions while using `20.6%` fewer query tokens; temporal nets `-4`.
- [x] LongMemEval-S abstention/token efficiency run: multihop `0.780` versus `0.740`, `20` gains and zero losses, `30/30` abstention for every mode, mean query tokens `2550.5` versus `2452.1` for FTS.
- [x] Compact LongMemEval lifecycle: per-session ephemeral stores, zero retained SQLite/bundle artifacts, runnable direct and matrix CLI commands.
- [x] Summary-only delta output bounded to ten examples plus omitted counts.
- [x] Full adaptive LoCoMo evidence: `0.6108`, `29` gains and `1` loss versus FTS, with temporal preserved.
- [x] Full adaptive LongMemEval evidence: `0.766`, `13` gains and zero losses versus FTS.
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
- [x] GitHub release `v0.1.2` published and deployed.
- [x] GitHub release `v0.1.3` published and deployed.
- [x] Site live at `zmem.sh`.
- [x] CI green.

Left:

- [ ] Keep release docs/changelog synchronized after every push.
- [x] Launch oversight paused after the clean `v0.1.3` release check.
- [ ] Publish ongoing release notes for `v0.1.3+`.
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
- [x] Homepage and docs copy simplified for agent-first, human-readable positioning in `v0.1.3`.
- [x] Duplicate install nav affordance removed; public nav now has one primary install CTA.
- [x] Site lint/build and docs typecheck/build are required CI jobs.
- [x] Homepage no longer exposes internal benchmark backlog.
- [x] Public install and benchmark commands use verified, collision-safe paths.

Left:

- [x] Update public docs to reflect `v0.1.3` release state.
- [ ] Add this progress tracker to public/internal navigation where appropriate.
- [x] Add an internal release communications brief after each release/checkpoint.
- [x] Keep changelog synced for the `v0.1.3` release push.
- [x] Run final mobile/desktop visual QA on the simplified copy.
- [x] Improve the public product matrix around the ready-now product surface.

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

1. Keep benchmark runs in isolated output directories and on supported Python 3.10+ runtimes.
2. Treat the verified conservative adaptive route as the normal regression-safe path: LoCoMo `+29/-1` and LongMemEval `+13/-0` versus FTS.
3. Build the next L3 slice from stable misses in multi-hop and open-domain, requiring no wider LoCoMo regression boundary.
4. Add BEAM scale evidence; `zmem-retrieval` remains a compatibility alias for pseudo-rerank, while `fts-adaptive` explicitly measures store auto-routing.
