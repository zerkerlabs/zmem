# ZMem Progress Tracker

Last updated: 2026-07-30

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
| `v0.1.4` | Published | `0ea8316` / `v0.1.4` | Deterministic retrieval, bounded morphology gains, BEAM scale adapter, and verified ActiveGraph pack/batching. |
| `v0.1.5` | Published | `d4f6d9a` / `v0.1.5` | Bounded completion support, BEAM 500K evidence, verified ActiveGraph pre-call prompt integrity, and the simplified public hero. |
| `v0.1.6` | Published | `34b4e8a` / `v0.1.6` | Transcript-neighbor retrieval, runnable ActiveGraph host, BEAM 10M scale/index evidence, and concurrent event-chain hardening. |
| `v0.1.7` | Published | `5b1cf0f` / `v0.1.7` | Private ephemeral run context, bounded MCP/operator/provider boundaries, finite governance values, and honest pending-judge benchmark state. |
| `v0.1.8` | Candidate | `codex/l3-dense-retrieval` | Digest-bound memory context, scheduled-agent continuity, typed failure memory, and opt-in local dense/FTS retrieval. |

Current public release:

- GitHub: `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.7`
- Site: `https://www.zmem.sh`
- Raw installer: `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`

Previous `v0.1.4` release checkpoint:

- Local gates pass: `1,236` tests, eval `11/11`, strict release summary, full fresh-workspace smoke, site/docs builds, and production dependency audits.
- The `0.1.4` wheel and source distribution build; the wheel reinstalls and reports `zmem 0.1.4`.
- ActiveGraph 1.9 real-loader verification passes and is now a dedicated CI job.
- Published from `0ea8316062af6123921e902dee2a3a6783cd4ba2`; GitHub Actions run `29165187978` passed every job.
- GitHub release includes the wheel (`sha256:c0be1038...`) and source distribution (`sha256:6b6f04b5...`). Swarms remain paused.

Current `v0.1.5` release checkpoint:

- Full Python suite passes: `1,241` tests; eval passes `11/11`.
- Stable/full retrieval evidence passes the zero-regression gate at `159/227` and `1,219/1,986`; LongMemEval remains `386/500`.
- ActiveGraph 1.9 pre-call prompt integrity, site lint/build, docs typecheck/build, and strict release smoke pass.
- Wheel `sha256:fb97ea0...` and source distribution `sha256:2a3ff46a...` build; clean wheel reinstall reports `zmem 0.1.5` and passes eval.
- Published from `d4f6d9a3bd6a09a09fa579203510406edea11f6a`; GitHub Actions run `29216453125` passed every job and the release attaches both verified distributions.
- The tested Vercel deployment `dpl_3eCbYfb2MejVCAs9U6ZvWuUWG9SK` is live at `zmem.sh`; production desktop/mobile and clean-console checks pass.
- Broad swarms remain paused after publication.

Current `v0.1.6` release checkpoint:

- Packages the three post-`v0.1.5` commits already landed on `main`: bounded transcript-neighbor retrieval, the runnable two-run ActiveGraph host, and the BEAM 1M/10M scale plus SQLite event-index work.
- Serializes event-chain head advancement with SQLite's cross-process writer lock and proves the chain remains linear under forced two-connection contention.
- Expands user paths consistently and rejects non-boolean MCP quarantine flags; the default agent capability profile remains unchanged.
- Full local verification passes: `1,250` Python tests, eval `11/11`, ActiveGraph 1.10 verification plus `7/7` integration tests, site/docs builds, and zero known npm vulnerabilities.
- Strict fresh-workspace release smoke and all five benchmark artifact verifiers pass. A clean wheel reinstall reports `zmem 0.1.6` and passes eval `11/11`.
- Final merged-source artifacts: wheel `sha256:f587f65227d790374512548dc253d45ae3fa414fd7cc6e31a2841f5a7791e98c`; source distribution `sha256:7a77df87c8f699bf7d4ffe95a791ace87a6e71a202db4e5787d4584aaf751062`.
- The existing `binary-sha256-v1` format is unchanged for compatibility. A count-bound, domain-separated Merkle successor is tracked as a separate migration.
- Published from `34b4e8aa2b41a454e2e8969576511ffd56a66027`; final-commit CI run `29524503194` and tag CI run `29524866769` passed every Python, ActiveGraph, site, docs, and release-smoke job.
- The release attaches both distributions with matching GitHub digests. Production deployments `dpl_9WBakHxq6DtPXF5cXVzQ1FuQjj9e` and `dpl_Dp1maM9BzkJ8RAydjn3agp8P6dBr` are live at `zmem.sh` and `docs.zmem.sh`; desktop/mobile and clean-console checks pass.

Current `v0.1.7` release checkpoint:

- PR `#6` merged at `9f3996f` after every Python, ActiveGraph, site, docs, and release-smoke check passed.
- Implicit run context is private and ephemeral; explicit context paths remain user-owned and retained.
- MCP now bounds framing, nesting, result limits, file I/O roots, provider connection inputs, and unexpected error detail without widening the default agent profile.
- LLM benchmark answers remain pending until judged, and hosted LongMemEval judge output cannot support a public claim without explicit review.
- Merkle `v1` is unchanged. Merkle `v2`, installer integrity, provider credential-host binding, and true dense retrieval remain separate reviewed work.
- Local release gates pass `1,260` tests with two expected optional skips, eval `11/11`, and strict release smoke with all public proof and launch-asset requirements ready.
- Published from `5b1cf0f05689143a3905fb2337807f4c60a191ea`; final-commit CI run `29534932237` and tag CI run `29535282896` passed every Python, ActiveGraph, site, docs, and release-smoke job.
- The clean public wheel reinstall reports `zmem 0.1.7` and passes eval `11/11`. GitHub assets match wheel `sha256:d8a3fdba9c5e60c5d00cc8918c8c9e5d87b40cee764ea9756f8e5f9b8053d89b` and source distribution `sha256:8a7102958be108098f9576d61d80730566d6c1bd1515ec1f21278ffea0fa13c4`.
- Production deployments `dpl_9Xb2upPsawLoDhaco6r5CSJppvxW` and `dpl_ckk7y9HhAg4fg2n1z67uBLJJQ8e8` are live at `zmem.sh` and `docs.zmem.sh`; responsive browser, console, network, raw-installer, agent-smoke, and MCP-smoke canaries pass.

Current `v0.1.8` candidate checkpoint:

- `zerker.memory_context.v1` now carries a canonical `sha256:` commitment over the exact ZMem context supplied to an agent, including admitted, withheld, and budget-dropped memory, policy decisions, temporal state, and memory roots.
- Inject receipts persist a compact commitment in existing retrieval JSON; no SQLite migration, retrieval change, Merkle v1 change, or duplicate raw-context copy is introduced.
- Wrapped runs expose `ZERKER_MEMORY_CONTEXT_DIGEST`; compact `inject` and `why` summaries show the same proof reference.
- Treeship memory-proof statements and ActiveGraph `memory.read.v1` payloads carry the context digest while keeping raw memory out of the compact commitment.
- Scheduled-agent continuity now composes verified restore, current/stale/unknown gap audit, governed execution, checkpoint, and linked proof. Typed failure memory records expected, observed, correction, confidence, and invalidation while keeping agent corrections quarantined.
- Opt-in local dense/FTS fusion passes the frozen gate at `203/227` versus `160/227`, then improves full LoCoMo from `1,220/1,986` to `1,567/1,986` and LongMemEval from `386/500` to `477/500`, with zero losses in all three comparisons. Full result and comparison artifacts verify locally.
- The dense gain costs more context and latency, so it remains opt-in. Existing MCP schemas retain stable FTS behavior; server-controlled MCP dense retrieval and any ANN backend remain follow-ups.
- Combined acceptance passes `1,289` tests with two expected skips, eval `11/11`, docs build/typecheck, fresh-workspace release smoke, and wheel/sdist packaging with the optional dense runtime correctly declared.
- Site lint/build passes. Clean Python 3.10 wheel reinstall reports `zmem 0.1.8` and passes eval `11/11`.
- Candidate artifacts: wheel `sha256:6e5bedd198927a4c3aaa1cdf87b97268f9e47fe272e8ec6a435b61b66be32fc2`; source distribution `sha256:84b773c70a5b99bf6cd85c1fd7713cb3cad4f7ec1f2f8205f2bc3e017fab424e`.

Included `v0.1.6` L3 checkpoint:

- Bounded transcript-neighbor onset support passes the stable gate at `160/227` versus `159/227`, with one gain, zero losses, one changed retrieval context, and `+17` query tokens.
- Full adaptive LoCoMo reaches `1,220/1,986` (`0.6143`) versus `1,219/1,986`; LongMemEval remains exactly unchanged at `386/500` (`0.772`).
- Verified result hashes: stable `ec83cfdf...`, full LoCoMo `308a492a...`, LongMemEval `e81b886c...`.

Included `v0.1.6` scale and integration checkpoint:

- The runnable ActiveGraph host is landed on `main` through PR `#2` at `fbca687`; it verifies a distinct write run and resume run with causal lineage, recall receipt attachment, and recorded/provider prompt equality.
- Isolated official-layout BEAM 1M and 10M runs now complete and verify. The 10M conversation contains 19,895 messages, 6,209,948 observed whitespace tokens, and `201/201` resolved references.
- An additive `events(memory_id, seq)` index removed the 10M observation-order scan. The same `fts-adaptive` question improved from `112,976 ms` to `8,344 ms` (`13.54x`) without changing its result or retrieved/injected memories.
- Stable, full LoCoMo, and full LongMemEval post-index runs preserve all answers and retrieval behavior. BEAM local evidence recall remains `0.15` at 1M and `0.10` at 10M, so scale execution is complete while scale-quality work remains open.

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
- Full Python tests (`1,274`), eval (`11/11`), release smoke, and the docs production build pass locally for the current candidate.
- Docs audit and the site production-dependency audit report zero vulnerabilities; site development tooling still has advisories pending a separate Vite major upgrade.

## Lane Scoreboard

Percentages are practical launch-grade alpha estimates, not benchmark scores.

| Lane | Focus | Alpha completion | Shipped state | Next acceptance target |
| --- | --- | ---: | --- | --- |
| L0 Trust Ledger | Receipts, Merkle lineage, context and restore/export proof | 90% | Mutation/lifecycle/restore receipts, compact v2 event witnesses, serialized event appends, digest-bound memory context, and linked cold-start proof exist; default MCP agents cannot claim trusted write/review authority | Add direct mutation-chain UX, then design a backward-compatible Merkle successor |
| L1 Temporal KG | Current/history/superseded temporal memory | 55% | `query_at`, supersession, omitted-memory envelopes, runtime temporal context | Add contradiction/abstention runtime fixture and decide when true bi-temporal graph schema is needed |
| L2 Lifecycle Compaction | Sessions, checkpoints, snapshots, retention | 70% | Session start/end/checkpoint/snapshot CLI, handoff/restore, cold-start gap audit, governed scheduled run, and linked proof are implemented | Add reviewable maintenance for revalidation, expiry, decay, tombstones, and failed-claim reopen conditions |
| L3 Retrieval Baseline | FTS/BM25, local dense candidates, RRF, packing | 97% | Offline FastEmbed plus adaptive FTS passes the frozen gate and full LoCoMo/LongMemEval comparisons with 43/347/91 gains, zero losses, lexical recall preservation, and receipt-visible model/fusion evidence | Tune candidate/context cost, then profile whether ANN or `sqlite-vec` is warranted before exposing server-controlled MCP dense retrieval |
| L4 Consolidation | Hierarchical summaries and job ledger | 35% | Deterministic fixture, job lifecycle, reversible summary payloads, append-only summary ledger | Source candidates from live store or expose persisted summaries through read-only CLI |
| L5 Identity / Workspaces | Multi-agent source lineage and conflicts | 50% | Source reports, claim conflicts, resolution basis, exact-tie abstention summaries | Add handoff ownership/lease metadata and a dry-run import preview, then persist merge decisions |
| L6 Benchmark Harness | LoCoMo/LongMemEval/BEAM evidence | 100% for local harness and sampled scale | Verified LoCoMo/LongMemEval evidence plus official-layout BEAM 100K, 500K, 1M, and 10M runs exist; compact artifacts verify | Add broader evidence and an official model-judged path; do not report unjudged LLM answers as incorrect |
| Launch Oversight | Release pack, proof evidence, public release | 100% for v0.1.7 | Public verify `6/6`, assets `8/8`, return packet ready, release assets published, and production canaries pass | Keep automation paused until the next bounded release candidate exists |
| Website / Docs | Landing, proof page, docs, changelog | 100% for v0.1.7 | Release copy and ActiveGraph pack version are synchronized and live on the production domains | Keep release facts synchronized with the next shipped product change |
| ActiveGraph Integration | Event substrate and compact traces | 100% | The real pack loads, persists events, batches traces, and ships a runnable two-run host with recorded/sent prompt equality | Keep larger selected-mode traces and aggregate Treeship artifacts as optional follow-ups |

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
- [x] Canonical governed-context digest carried through cold-start evidence and scheduled-run proof.

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
- [ ] Read-only memory-health audit across stale, expired, contradictory, duplicate, weak-provenance, and high-risk active records.
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
- [x] CLI write surfaces for start, end, checkpoint, and snapshot.
- [x] Scheduled-agent cold start with optional restore and explicit current/stale/unknown gap state.
- [x] Governed scheduled execution, checkpoint, and compact linked proof.
- [x] Typed failure memory with quarantined agent corrections.

Left:

- [ ] Reviewable lifecycle maintenance with dry-run/apply modes.
- [ ] Revalidation deadlines, expiry/decay transitions, tombstones, and failed-claim reopen conditions.
- [ ] Richer session lifecycle and failure-review UI for real agent continuation.

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
- [x] Deterministic benchmark ids, timestamps, and support ordering remove repeat-run drift.
- [x] Conservative regular-inflection rescue requires two exact anchors and two added morphology matches.
- [x] Stable 227-question gate improved from `156` to `158` with zero regressions.
- [x] Full adaptive LoCoMo improved from `0.6108` to `0.6133` with five gains and zero losses.
- [x] Full adaptive LongMemEval improved from `0.766` to `0.772` with three gains and zero losses.
- [x] Bounded completion-support expansion requires a retrieved subject/object nucleus and adds at most one same-subject completion fact.
- [x] Stable gate improved from `158/227` to `159/227`; full LoCoMo improved from `1,218` to `1,219`; both comparisons have zero losses.
- [x] Full LongMemEval remained `386/500` with zero changed decisions after completion support.
- [x] Bounded transcript-neighbor onset support requires an exact event head, same speaker/session/timestamp, and an earlier turn within distance two.
- [x] Transcript-neighbor evidence improves the stable gate to `160/227` and full LoCoMo to `1,220/1,986`, with one context change and zero losses; LongMemEval remains exactly unchanged.

Left:

- [x] Relation-history RRF diff landed in the `v0.1.2` swarm hardening release.
- [x] Full benchmark reruns prove adaptive deltas against FTS and always-on multi-hop.
- [x] Real local dense embedding baseline with explicit model cache, SQLite vectors, exact cosine candidates, and FTS RRF fusion.
- [x] Dense-only recall cannot trigger regex-based lexical conflict suppression; lexical and explicit update/supersession conflicts retain their existing governance behavior.
- [x] Full dense-hybrid LoCoMo comparison: `1,567/1,986` versus `1,220/1,986`, 347 gains, zero losses, proof verified.
- [x] Full dense-hybrid LongMemEval comparison: `477/500` versus `386/500`, 91 gains, zero losses, proof verified.
- [ ] Profile and add `sqlite-vec` or another ANN path only if exact cosine is the measured scale bottleneck.
- [ ] Graph traversal fusion.
- [ ] Abstention confidence threshold.
- [x] Bounded context expansion around completion and structured transcript nuclei.
- [ ] General context expansion beyond the current completion/onset contracts.
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
- [ ] Handoff owner/lease/next-action metadata and provenance-preserving dry-run import.
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
- [x] BEAM official-layout scale adapter across 100K, 500K, 1M, and 10M buckets.
- [x] Official BEAM 100K adapter smoke with all ten categories and `53/53` resolved source references.
- [x] Isolated official-layout BEAM 500K conversation: `247,175` observed whitespace tokens and `83/83` resolved source references.
- [x] ActiveGraph batching/performance for the full stable 227-question trace.
- [x] Public benchmark page/report polish after real deltas.
- [x] Isolated BEAM 1M and 10M scale runs: `490,991` and `6,209,948` observed whitespace tokens, complete source-reference coverage, compact verified artifacts, and explicit non-official claim boundaries.

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
- [x] GitHub release `v0.1.4` published with wheel and source distribution.
- [x] Site live at `zmem.sh`.
- [x] CI green.

Left:

- [ ] Keep release docs/changelog synchronized after every push.
- [x] Launch oversight paused after the clean `v0.1.4` release check.
- [x] Publish `v0.1.4` release notes with benchmark and integration claim boundaries.
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
- [x] Update public docs to reflect `v0.1.4` retrieval, BEAM, and ActiveGraph state.
- [ ] Add this progress tracker to public/internal navigation where appropriate.
- [x] Add an internal release communications brief after each release/checkpoint.
- [x] Keep changelog synced for the `v0.1.3` release push.
- [x] Keep changelog synced for the `v0.1.4` release push.
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
- [x] Concrete ActiveGraph 1.9 `Pack` with typed settings and canonical runtime behaviors.
- [x] Real entry-point discovery and idempotent runtime loader verification.
- [x] Real `object.created` event-to-ZMem persistence smoke.
- [x] Batched WAL-backed event log with shared conversation ingestion.
- [x] Full 227-question acceptance trace: `908` events, eight commits, zero receipt bundles.
- [x] Public docs and use-case post describe the verified integration and prompt boundary.
- [x] `enable_precall_recall(...)` enriches a host LLM behavior before ActiveGraph hashes and records the prompt.
- [x] Real ActiveGraph runtime test verifies the recorded `llm.requested` prompt equals the provider-bound prompt.
- [x] Runnable no-key two-run host persists memory through the pack, recalls it in a distinct resume run, and verifies causal lineage, receipt attachment, prompt equality, and the memory-derived answer.

Optional follow-ups:

- [ ] Run a larger official selected-mode trace when the retrieval matrix justifies preserving it.
- [ ] Decide whether an aggregate Treeship artifact belongs on completed trace runs.

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

1. Publish the already-verified `v0.1.8` candidate without adding another runtime feature.
2. Build a bounded read-only `zmem audit health` report with a stable JSON contract and terminal summary.
3. Add contradiction-driven withholding/abstention, then reviewable lifecycle maintenance with dry-run/apply receipts.
4. Connect consolidation to the live store with source coverage and reversible summaries; do not promote summaries into canonical truth.
5. Add handoff ownership/import preview and governed tool-contract state while keeping effect/capability enforcement in Treeship/Guard.
6. Sweep dense candidate depth and context packing before recommending dense as a default or exposing server-controlled MCP dense retrieval.
7. Keep Merkle `v2`, BEAM quality, and official model-judged scoring as separate compatibility/evidence projects.
