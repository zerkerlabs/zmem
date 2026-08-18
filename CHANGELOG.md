# Changelog

All notable Zerker Memory alpha changes are summarized here.

## Unreleased

### One-Command Agent Connection

- Added `zmem connect <agent>` to initialize or verify one workspace binding and issue one copy-ready, agent-bound live-session invitation.
- Kept setup truth explicit: direct clients may need a reload, manual clients still require import, the session becomes live only after the agent calls `memory.session_attach`, and optional Room context never grants membership.

## 0.1.14 - 2026-08-18

### Documentation Runtime

- Updated Next.js, React, and Fumadocs to current compatible releases and pinned patched transitive `nanoid` and `postcss` versions. The docs production dependency audit now reports zero vulnerabilities.

### Console-Native Agent Sessions

- Added local-console controls to create an agent-bound one-time invitation, copy the exact attach instruction, and detach an active connector without deleting memory.
- Reused the existing session invitation and attachment ledger; the UI does not create a second identity, membership, or storage model.

### Rooms Deployment Readiness

- Extended `/readyz` to report the configured retrieval mode and fail with HTTP `503` when `dense-hybrid` was requested without the local runtime or cached model.
- Kept `/healthz` as a liveness probe and added an exact offline setup command to readiness and startup output, so deployment systems cannot mistake lexical fallback for healthy semantic recall.

## 0.1.13 - 2026-08-18

### Live Agent Sessions

- Added hash-only, short-lived, agent-bound, single-use invitations through `zmem session invite`, `connections`, and `detach`, plus agent-safe MCP attach and status tools.
- The local console now separates configured, historically observed, active, live, idle, and detached agent states without exposing invitation codes or raw memory.
- Session labels and optional client session ids are asserted metadata, not host-verified UI chat identity. A Room id supplies context and never grants Room membership or access.

### Agent Memory Network And Safe Transfer

- The local console now distinguishes configured clients from agents that have actually written memory, joins both states into one shared-store view, and keeps unknown generic-MCP frameworks visible through recorded provenance.
- Added a read-only Rooms inventory with room-shared and member-private counts, review state, observed contributors, proof roots, and semantic-index coverage. Gateway remains authoritative for Room membership.
- Room stores now keep a content-free local identity descriptor so isolated tenant-and-room databases can be discovered without exposing memory text.
- Added `zmem restore --dry-run` and preview-id confirmation. Handoff and snapshot restores can be verified and diffed before import, then bound to the exact reviewed artifact and destination state.
- The console now requires a successful preview before restoring a handoff into a fresh local copy.

### Semantic Recall For Shared Rooms

- Dense-enabled Rooms now maintain each room's local semantic index after writes and catch up missing or stale vectors before context preparation. No context request downloads a model.
- Room write and context responses expose compact retrieval-index readiness, model identity, coverage, and zero-network status without exposing vectors or raw memory.
- An established room that produces no confident candidate now returns `abstained` with `no-relevant-memory`; `empty` is reserved for a room with no prior active memory.

### Rooms Contract Hardening

- Pinned the exact room-context commitment bytes and digest with a cross-language golden fixture, constrained temporal abstention output to a fixed allowlist, and removed caller-supplied tenant identity from the Gateway request contract.

## 0.1.12 - 2026-08-10

### Guided Agent Connections

- Added `zmem setup [agents...]` to initialize one project and bind selected Codex, Claude Code, Cursor, OpenClaw, Hermes, or generic MCP clients to the same absolute memory database and policy.
- Added exact workspace-binding checks to `doctor` and `status`, so a client configured for another project is no longer reported as ready.
- Bound generated MCP configs to an agent-host identity and added per-process connection provenance. Bound agents can omit their own id from `memory.inject`, cannot spoof another configured identity, and automatically attach connector provenance to proposals.
- Kept the identity boundary explicit: the MCP connection identifies the host process, not necessarily a visible UI chat. Manual-client exports are reported as awaiting import rather than live.
- Isolated unit and release-smoke workspace registries from the user's real `~/.zmem/workspaces.json`, and added `zmem workspace prune` as a preview-first cleanup for entries whose project roots no longer exist.

## 0.1.11 - 2026-08-10

### Concurrent Room Initialization

- Serialized only the WAL/schema initialization step for concurrent first access to one room, preventing a transient SQLite `database is locked` failure without serializing normal room writes.
- Strengthened the room concurrency test with a barrier that forces eight simultaneous first opens, then verified durable unique writes and idempotent retries.

## 0.1.10 - 2026-08-10

### Zerker Rooms Memory Service

- Added `zmem serve`, a tenant-local authenticated HTTP adapter for Zerker Gateway Rooms with loopback-only defaults and explicit remote-bind protection.
- Added isolated SQLite storage per tenant-and-room pair, room-shared and member-private visibility, restart persistence, and source-event provenance without changing the existing local CLI, MCP, or single-store defaults.
- Added policy-ranked context preparation through `/v1/contexts:prepare` plus the Gateway-compatible `/v1/inject` alias. Responses preserve selected order and distinguish `ready`, `partial`, `empty`, `blocked`, `abstained`, and `budget_exhausted` instead of treating every HTTP success as usable memory.
- Added trusted accepted-state recording and quarantined agent proposals as separate operations. Every write requires a room event and idempotency key; concurrent retries replay safely, while changed content or source events fail with a conflict.
- Added compact room-context commitments over tenant, room, agent, purpose, risk, budget, optional membership/room-state digests, ZMem context and policy digests, memory roots, exact selected IDs, and state.
- Added adversarial coverage for cross-room, cross-member, and cross-tenant isolation, symlink refusal, authentication, caller-supplied tenant rejection, restart durability, concurrent writes, and remote-bind safety.
- Added a public preview guide and an internal Gateway contract. The candidate does not claim that the Gateway Go client, Rooms persistence, hosted multi-tenant routing, or asynchronous Treeship publication is complete.

## 0.1.9 - 2026-08-05

### Review-Gated Live Consolidation

- Added `zmem consolidation preview` with a stable `zerker.live_consolidation_preview.v1` report over one exact live-memory scope.
- Opens the database in SQLite read-only/query-only mode, verifies the full event/Merkle chain plus each source write-receipt chain, and rejects out-of-band row drift or a latest memory event that lacks a receipt.
- Groups active episodic and semantic sources by verified origin actor, environment, and session provenance. Policy, procedural, non-active, missing-receipt, invalid-receipt, row-divergent, and malformed sources remain explicit omissions with content-free reason codes.
- Carries exact source ids, content and receipt digests, source-set hashes, and weakest-source trust/authority ceilings without copying raw memory text.
- Added a second, artifact-bound confirmation identity that includes the reviewed database path and evaluation time while preserving stable source-set preview identity.
- Added `zmem consolidation materialize` for one explicitly selected candidate. It revalidates the exact source state while holding the SQLite writer lock through a query-only snapshot, then records a deterministic summary in private append-only job and summary ledgers.
- Keeps every materialized summary quarantined at trust `0` and authority `none`, reversible, non-blocking, and below the weakest source ceilings. No canonical memory is written, retrieval is unchanged, and the compact result excludes source and summary text.
- Serializes both job and summary ledgers, makes exact replay idempotent, and repairs verified append interruptions. Abrupt trailing fragments use newline commit markers and leave a durable, hash-bound local recovery receipt before materialization continues. Custom ledgers and result paths cannot alias the database or use a symlinked final destination.
- Added `zmem consolidation audit` with content-commitment, preview, admission, review, job-history, duplicate-summary, orphan-summary, and incomplete-transition checks. A changed summary cannot pass by merely recomputing its own digest.
- Added `zmem consolidation inspect` to list the content-free review queue or produce one private `zerker.consolidation_inspection.v1` artifact. Inspection audits the ledgers, verifies current source receipt heads, and independently recomputes the deterministic summary from live source text.
- Added explicit `zmem consolidation admit` and `discard` decisions. Admission is the only canonical write in the flow, uses exactly the weakest source trust and authority ceilings, and records the source ids as parents. Discard writes no canonical memory and deletes no evidence.
- Records admission and discard as terminal, mutually exclusive events in the SQLite Merkle chain. Exact replay is idempotent; stale source, summary, audit, target, database, or confirmation bindings fail before mutation.
- New write receipts bind exact parents, labels, and their digests into both the source event and Treeship statement. Receipt-chain verification rejects out-of-band lineage edits while older receipts retain their prior compatibility contract.
- Keeps the proof boundary explicit: CLI actor ids are asserted metadata, Treeship anchoring is separate from the local review transaction, and neither local nor external proof establishes semantic truth.

### Reviewable Memory Maintenance

- Added `zmem maintain preview`, `apply`, and `verify` with versioned plan, result, and verification artifacts.
- Kept `zmem audit health` permanently read-only. The first executable maintenance action is limited to an active memory whose explicit `expires_at` boundary has passed and whose write receipt verifies.
- Added a dedicated non-cascading `expired` lifecycle state. Apply changes one memory per fresh plan, leaves the row in place, appends a mutation receipt, and is idempotent for the same action.
- Bound plans to the event Merkle root, a content-free global memory-state hash, target metadata, and the latest receipt record. Changed or tampered state is rejected before mutation.
- Kept conflicts, duplicates, lineage questions, weak provenance, and high-risk use review-only. The command does not claim semantic truth or authenticate the operator identity supplied through `--actor-id`.
- Verification distinguishes historical transition proof from current state, reporting later event advancement and out-of-band state divergence without invalidating a sound historical receipt.

### Read-Only Memory Health

- Added `zmem audit health` with stable `zerker.memory_health_report.v1` JSON and a compact `--summary-only` view.
- Reports observable stale or expired state, lexical conflicts, exact duplicates, weak provenance, and explicit high-risk active use without changing memory lifecycle state.
- Reads committed SQLite WAL state when present while retaining a read-only database connection.
- Keeps the claim boundary explicit: health findings describe persisted metadata and deterministic lexical signals, not whether memory content is factually or semantically true.

## 0.1.8 - 2026-07-30

### Governed Context Proof

- Added a canonical `sha256:` commitment to `zerker.memory_context.v1`, covering the exact memories admitted to an agent, the considered/withheld/budget-dropped sets, policy decisions and policy digest, temporal metadata, and memory Merkle references.
- Persisted the compact commitment with inject receipts so `zmem why` can recover the original decision reference without storing a second raw-context copy.
- Exposed the digest to wrapped agents as `ZERKER_MEMORY_CONTEXT_DIGEST` and in compact `inject` / `why` summaries.
- Added `zmem context verify <file> --summary-only` for direct local or receive-side verification of retained context artifacts.
- Added the context and policy digests to Treeship memory-proof statements and ActiveGraph `memory.read.v1` payloads while preserving older receipts and exports.
- Kept the claim boundary explicit: this proves the exact ZMem context artifact, not semantic truth, hidden reasoning, or provider prompt material outside that artifact.

### Scheduled-Agent Continuity

- Added `zmem scheduled-run` to compose optional verified restore, wall-clock gap audit, session start, governed execution, checkpoint, and one linked proof receipt.
- Classified continuity as `current`, `stale`, or `unknown`; an uncheckpointed prior run and a deleted latest snapshot payload remain explicitly unknown.
- Bound the compact continuity audit into `zerker.memory_context.v1`, so the agent sees the same gap state committed by the run context digest.
- Kept operational success separate from proof validity: nonzero commands are still checkpointed and their execution proof can verify.

### Failure Memory

- Added `zmem failure record` and `zmem failure show` for a typed, receipted `zerker.failure_memory.v1` payload containing expected result, observed result, confidence, correction, and invalidation.
- Agent-authored corrections remain quarantined evidence until reviewed. Recording an invalidated memory reference does not silently revoke or rewrite that memory.

### Local Dense Retrieval Candidate

- Added optional FastEmbed-backed local embeddings with an explicit `zmem embeddings index --download-model` first-run boundary; ordinary search cannot download a model.
- Added a derived SQLite float32 vector cache bound to memory content hash, provider, model id, local model-file digest, and redacted provider-config hash. Stale vectors are excluded.
- Added `dense-hybrid` retrieval for `inject`, `run`, and `scheduled-run`. Dense candidates are generated independently of FTS, fused with the adaptive lexical baseline through RRF without deleting lexical candidates, and then governed by the existing policy, temporal, packing, and receipt pipeline.
- Added receipt-visible provider/model/config/query-vector identity, index coverage, candidate source ranks, fusion results, and explicit lexical fallback reasons without copying raw vectors into receipts.
- Kept semantic expansion from manufacturing a state conflict: dense-only candidates cannot trigger the legacy lexical current-fact resolver, while conflicts supported by lexical candidates and explicit update/supersession links still resolve normally.
- Passed a clean repeat of the frozen 227-question gate at `203/227` versus `160/227`: 43 gains, zero losses, zero fallbacks, zero query-time network calls, and one pinned model digest. Observed p95 retrieval latency increased from `209.629 ms` to `419.818 ms`.
- Completed proof-verified full local comparisons with zero answer regressions. LoCoMo improved from `1,220/1,986` (`61.43%`) to `1,567/1,986` (`78.90%`), with 347 gains. LongMemEval improved from `386/500` (`77.2%`) to `477/500` (`95.4%`), with 91 gains. Every answerable category improved; LoCoMo adversarial abstention remained `446/446`.
- Kept the cost visible: mean query context increased from `533.32` to `903.05` tokens on LoCoMo and from `2,510.65` to `3,615.88` on LongMemEval. The mode remains opt-in while candidate depth, packing cost, and exact-cosine latency are tuned.

### Verification

- Full Python suite: `1,289` tests passed with two expected optional skips; eval passed `11/11`.
- Docs production build and typecheck passed after a clean generated cache; fresh-workspace release smoke reports strict publish ready.
- Wheel and source distribution build successfully. The wheel contains `zerker_memory/dense.py` and advertises `fastembed>=0.8,<1` only through the optional `dense` extra.
- Clean Python 3.10 wheel reinstall reports `zmem 0.1.8` and passes eval `11/11`.
- Wheel `sha256:6e5bedd198927a4c3aaa1cdf87b97268f9e47fe272e8ec6a435b61b66be32fc2`; source distribution `sha256:84b773c70a5b99bf6cd85c1fd7713cb3cad4f7ec1f2f8205f2bc3e017fab424e`.

## 0.1.7 - 2026-07-16

### Runtime And MCP Hardening

- Made implicit `zmem run` memory-context files mode `0600` and removed them after the child command exits. An explicit `--context-path` remains a retained user-owned artifact.
- Bounded MCP request lines, JSON nesting, and external-provider result limits. Unexpected server failures now return a generic error instead of echoing internal exception details.
- Confined operator-profile snapshot and restore paths to an explicit MCP I/O root. The default root is the memory database directory; operators can set `--io-root` when they need another local handoff directory.
- Removed caller-supplied provider URLs and API keys from MCP tool calls. Operator MCP now resolves provider connections from the trusted provider config, while local and private provider endpoints remain supported.
- Rejected non-finite provider governance values such as `NaN` and infinity.

### Benchmark Claim Integrity

- Changed LLM answerer runs from automatic failures to `pending-external-judge`. Pending questions are excluded from accuracy and failure counts until scored.
- Kept LongMemEval hosted-judge output non-public by default. A scored receipt now requires explicit review before it can support a public claim.

### Compatibility Boundary

- Kept `binary-sha256-v1` unchanged. Its concrete compatibility weakness is duplicate-last leaf-count ambiguity; the fixed-width receipt hashes do not demonstrate the variable-boundary concatenation collision claimed in the external review.
- Deferred Merkle v2 until legacy fixtures, per-receipt algorithm dispatch, mixed v1/v2 bundle verification, and no-rewrite migration rules are specified and tested together.

### Verification

- `python3 -m unittest discover -s tests -q` (`1,260` tests; two expected optional skips)
- `python3 -m zerker_memory eval` (`11/11`)
- Strict release smoke with public proof `6/6`, launch assets `8/8`, and the return packet ready
- Python 3.10, 3.11, and 3.12 plus ActiveGraph, site, docs, and release-smoke CI
- Clean wheel reinstall reports `zmem 0.1.7` and passes eval `11/11`
- Wheel `sha256:d8a3fdba9c5e60c5d00cc8918c8c9e5d87b40cee764ea9756f8e5f9b8053d89b`; source distribution `sha256:8a7102958be108098f9576d61d80730566d6c1bd1515ec1f21278ffea0fa13c4`

## 0.1.6 - 2026-07-16

### Retrieval Quality

- Added a bounded transcript-neighbor support path for onset questions such as "When did John get an ankle injury?" It can recover one earlier same-speaker turn only when the retrieved nucleus and support share the exact event head, transcript session, and timestamp, and are at most two turns apart.
- Kept the decision receipt-visible through `zerker.support_expansion.v1`, including the event head, nucleus, selected support, direction, timestamp constraint, and any replaced candidate id.
- Improved the deterministic `227`-question gate from `159/227` to `160/227`. Exactly one answer and one retrieval context changed; there were no losses and only `17` additional query tokens.
- Improved full local adaptive LoCoMo from `1,219/1,986` to `1,220/1,986` (`0.6143`) with the same single multi-hop gain, zero losses, and one changed retrieval context. Full LongMemEval remained exactly unchanged at `386/500` (`0.772`).

### ActiveGraph

- Added `examples/activegraph_host.py`, a no-key two-run host that loads the installed pack, persists an event-backed memory, recalls it in a distinct resume run, and answers through a deterministic demo provider.
- Made the example fail unless the source event pointer is preserved, a recall receipt reaches the provider, and ActiveGraph's recorded `llm.requested` prompt exactly matches the provider-bound prompt.
- Added the host example to the ActiveGraph CI job and its optional-dependency test suite.

### BEAM Scale And Retrieval Performance

- Completed isolated official-layout BEAM `1M` and `10M` conversation runs with compact, locally verified proof artifacts. The runs covered 1,802 and 19,895 messages, 490,991 and 6,209,948 observed whitespace tokens, and resolved `107/107` and `201/201` source references.
- Added an index on `events(memory_id, seq)` for the observation-order lookup used by semantic rescue. On the same official 10M event-ordering question in `fts-adaptive` mode, retrieval fell from `112,976 ms` to `8,344 ms` (`13.54x`) while preserving the same outcome and the same 20 retrieved / 6 injected memories.
- Re-ran the deterministic 227-question gate, full LoCoMo, and full LongMemEval after the index migration. All 2,713 question records preserved their answers, retrieval/injection sets, abstention outcomes, and support states; LoCoMo remains `1,220/1,986` and LongMemEval remains `386/500`.
- Kept the scale claim narrow: the BEAM artifacts report local evidence recall of `0.15` at 1M and `0.10` at 10M with `public_benchmark_claim: false`. They prove bounded execution, source coverage, and proof integrity, not an official model-judged BEAM score or solved long-context retrieval quality.

### Integrity And Operator UX

- Serialized event-chain head reads and appends with SQLite's cross-process writer lock. A deterministic two-connection regression test now proves concurrent appends both survive and retain one linear `prev_event_hash` chain.
- Expanded `~` consistently for store, CLI, MCP, policy, provider, snapshot, benchmark, workspace, and export paths instead of creating a literal `~` directory.
- Made MCP reject non-boolean `include_quarantined` values instead of treating strings such as `"false"` as true. The capability remains operator-only; the default agent profile still cannot call `memory.search`.
- Corrected the public proof-page provenance example to use `--source-uri`, replaced stale fixed local-preview ports with the commands that print current URLs, and removed speculative runtime language from the README.
- Updated the site dependency lock without a framework migration. Both the production and full npm audits now report zero known vulnerabilities.

### Claim Boundaries

- LoCoMo and LongMemEval values remain verified local provisional retrieval evidence, not official leaderboard rankings.
- The transcript-neighbor rule is deliberately limited to structured transcript memories and qualified onset questions; it is not a general graph traversal or unrestricted adjacency expansion.
- BEAM 1M/10M results are one-conversation scale diagnostics with local evidence-recall scoring, not official submissions or broad scale-quality claims.
- This release preserves `binary-sha256-v1` so existing receipts remain verifiable. A versioned Merkle successor with domain separation and explicit leaf-count binding is a separate compatibility-sensitive migration, not a silent root change.

### Verification

- `python3.11 -m unittest discover -s tests -q` (`1,250` tests; two optional ActiveGraph checks skipped in the base environment and passed separately with ActiveGraph installed)
- `python3.11 -m zerker_memory eval` (`11/11`)
- ActiveGraph 1.10 pack verification and `tests.test_activegraph_pack` (`7/7`)
- Site lint/build and docs typecheck/build, with zero known npm vulnerabilities
- Strict release smoke and all five benchmark artifact verifiers
- Clean wheel reinstall reports `zmem 0.1.6` and passes eval `11/11`
- Wheel `sha256:f587f65227d790374512548dc253d45ae3fa414fd7cc6e31a2841f5a7791e98c`; source distribution `sha256:7a77df87c8f699bf7d4ffe95a791ace87a6e71a202db4e5787d4584aaf751062`

## 0.1.5 - 2026-07-12

### Retrieval Quality

- Added a bounded completion-support expansion for questions such as "When did Jolene finish her robotics project?" It can bridge an already-retrieved subject/object nucleus to one paraphrased completion fact, while requiring the same subject and object anchors and adding at most one candidate.
- Passed the stable `227`-question gate at `159/227`, one gain and zero losses against the `v0.1.4` morphology checkpoint.
- Improved full local adaptive LoCoMo from `1,218/1,986` to `1,219/1,986` (`0.6138`), again with one gain and zero losses. Full LongMemEval remained `386/500` (`0.772`) with zero changes.
- Kept the expansion receipt-visible through `zerker.support_expansion.v1`, including the nucleus, selected support candidate, and any replaced candidate ids.

### BEAM Scale Evidence

- Completed the first isolated official-layout BEAM `500K` conversation run: 796 messages, 247,175 observed whitespace tokens, 20 questions, and 83/83 source references resolved.
- The compact proof artifact verifies locally and reports `0.30` deterministic evidence recall. `public_benchmark_claim` remains `false`: this is a scale and evidence-retrieval diagnostic, not BEAM's official model-judged answer score.

### ActiveGraph

- Added `enable_precall_recall(...)` for ActiveGraph LLM behaviors. It injects scoped ZMem context before ActiveGraph hashes the prompt and emits `llm.requested`, so the recorded prompt and provider-bound prompt remain identical.
- Extended the installed-pack verifier to exercise the real ActiveGraph 1.9 runtime, a capture provider, pre-call recall, and recorded-prompt equality in addition to discovery, idempotent loading, and event persistence.
- Kept the installed `zmem.recall` behavior as an immutable-event audit hook. Hosts opt into current-call context with the explicit pre-call wrapper; ZMem does not claim that an after-emission hook rewrites a request.

### Website

- Reframed the homepage around the plain-language promise `Agent memory you can trust.` The supporting copy now explains persistent local memory through concrete review, revocation, and verification controls rather than asking visitors to decode authority-gate terminology.
- Fixed the local Vite development path to use the same automatic JSX transform as the production build, preventing a black preview caused by a missing classic `React` binding.

### Claim Boundaries

- LoCoMo and LongMemEval values remain verified local provisional retrieval evidence, not official rankings.
- BEAM `500K` records source coverage, latency, scale, and local evidence recall; it is not an official model-judged BEAM submission.

### Verification

- `python3.11 -m unittest discover -s tests -q` (`1,241` tests; one optional ActiveGraph test skipped in the base environment and passed separately with ActiveGraph installed)
- `python3.11 -m zerker_memory eval` (`11/11`)
- ActiveGraph 1.9 pack tests and `scripts/verify_activegraph_pack.py --summary-only`
- Site lint/build and docs typecheck/build
- `python3.11 scripts/release_smoke.py --summary-only` with strict publish ready
- `0.1.5` wheel and source distribution build; clean wheel reinstall reports `zmem 0.1.5` and passes eval `11/11`

## 0.1.4 - 2026-07-11

### Benchmark Operations

- Made benchmark ingestion reproducible with deterministic memory ids and timestamps while preserving random ids and current timestamps for normal product writes.
- Made relation and update-history expansion order by append-only observation sequence instead of coarse wall-clock timestamps, removing ranking drift caused by ingestion speed.
- Verified two independent `227`-question LoCoMo repeats with the same `156/227` result and `147,710` query tokens, plus exact parity for decisions, answers, retrieved/injected ids, content hashes, and candidate-rank hashes.
- Evaluated and rejected a broad FTS token-prefix fallback after it introduced decoy regressions. No unsafe morphology shortcut was shipped.
- Added the optional `fts-adaptive` benchmark mode. It measures ZMem's query-by-query store routing without forcing multi-hop on every question, and records activation or suppression reasons in each retrieval proof.
- Tightened semantic multi-hop escalation to explicit composition signals while preserving fallback and no-lexical-match escalation. Broad semantic matches now remain on the base route unless the query asks for a composed answer.
- Completed verified adaptive follow-up runs with compact artifacts and no retained SQLite databases or per-question bundles. On local LoCoMo, adaptive scored `0.6108` versus `0.5967` for FTS and `0.6067` for always-on multi-hop, gaining `29` questions and losing `1` against FTS. On local LongMemEval, adaptive scored `0.766` versus `0.740` for FTS, gaining `13` questions with zero losses; always-on multi-hop remains highest there at `0.780`.
- Kept the benchmark claim boundary explicit: these are provisional local retrieval-recall measurements, not official leaderboard submissions or vendor comparisons.
- Made `--compact-artifacts` effective for LongMemEval matrices and direct runs. Compact execution now uses per-session ephemeral stores, omits per-question bundles and the run database, and leaves normal proof-rich runs unchanged.
- Added direct `zmem bench run ... --compact-artifacts` support so recorded reproducibility commands are executable.
- Bounded summary-only memory-count and efficiency deltas to ten examples plus an omitted count.
- Completed a verified local `500`-question LongMemEval matrix: `fts-multihop` scored `0.780` versus `0.740` for FTS, pseudo-embedding, and pseudo-rerank; it recovered `20` questions with zero losses and all modes passed `30/30` abstention questions. These remain provisional local results, not leaderboard claims.

### Retrieval Quality

- Added a conservative regular-inflection rescue for semantic fallback. It activates only with at least two exact query anchors and two additional inflection matches, so broad prefix matching cannot pull in weak decoys.
- Passed the required zero-regression gate: `158/227` versus `156/227` on the stable morphology cohort, with two gains and zero losses.
- Improved full local LoCoMo adaptive evidence from `1,213/1,986` (`0.6108`) to `1,218/1,986` (`0.6133`), with five gains and zero losses.
- Improved full local LongMemEval adaptive evidence from `383/500` (`0.766`) to `386/500` (`0.772`), with three gains and zero losses. The added retrieval costs `11,968` tokens across the 500-question run.

### BEAM Scale Harness

- Added `zmem bench run beam` for the official BEAM `chats/<scale>/<conversation>` layout across `100K`, `500K`, `1M`, and `10M` buckets.
- BEAM runs hash every source chat and probing file, preserve official source chat ids, record observed scale, and emit compact verifiable evidence artifacts.
- The first official 100K smoke covered 188 messages, 63,411 observed whitespace tokens, 20 questions, all ten BEAM categories, and 53/53 resolved source references. Its result verifies locally.
- BEAM scores are explicitly local evidence-recall diagnostics with `public_benchmark_claim: false`; they are not the official model-judged BEAM answer score.

### ActiveGraph

- Replaced the placeholder entry point with a real ActiveGraph 1.9 `Pack` object at `zerker_memory.pack:pack`, typed settings, and canonical `zmem.persist` / `zmem.recall` behaviors.
- Added the optional install extra `zerker-memory[activegraph]` and a repeatable `scripts/verify_activegraph_pack.py` discovery, idempotent-load, behavior, event, and persistence smoke.
- Batched the compact event log with WAL and bounded commits, shared each conversation across its questions, and stopped copying full retrieval receipts into every event.
- Closed SQLite connections created by runtime pack behaviors after each operation while leaving caller-owned stores open.
- A full 227-question acceptance run wrote 908 replayable events in eight commits, a 1 MB causal event database, a 196 KB trace, and zero receipt bundles.

### Release Engineering

- Made fresh-workspace release smoke use symlinked virtualenv executables on POSIX, so uv-managed standalone Python builds retain their base-prefix and can bootstrap pip.
- Excluded local `.treeship`, web `node_modules`, and Next.js/Turborepo caches from the release-surface copy. The same full smoke now stays storage-bounded instead of copying more than a gigabyte of generated state.
- Built and reinstalled both the `0.1.4` wheel and source distribution before release.

### Claim Boundaries

- LoCoMo and LongMemEval values remain verified local provisional retrieval evidence, not official leaderboard rankings.
- The ActiveGraph source hook can return context before a host model call. The installed ActiveGraph behavior observes immutable runtime events and records memory provenance/read receipts; it is not a pre-provider prompt interceptor.

## 0.1.3 - 2026-07-10

### Security And Control

- Added explicit MCP capability profiles. `agent` is now the default and exposes only proposal, governed injection, explanation, and verification; trusted writes, review, external imports, snapshots, and restore require `--profile operator`.
- Prevented agent proposals from claiming human/system provenance, and updated generated Codex, Claude Code, Cursor, OpenClaw, Hermes, and generic MCP configs to request the agent profile explicitly.
- Hardened local SQLite defaults with user-private database permissions, a private default `.zerker` directory, WAL mode, a five-second busy timeout, foreign keys, and normal synchronous durability for multi-agent local use.

### Product And Builder Experience

- Added bounded `zmem inject --summary-only` and `zmem why --summary-only` views while preserving JSON as the default machine contract.
- Reworked the public hero around the plain-language promise: agents remember across runs while users retain local review, revocation, and proof controls.
- Removed internal benchmark backlog from the homepage, corrected the public Python requirement to 3.10+, and replaced the broken short installer URL with the verified raw GitHub installer.
- Updated LoCoMo docs with the current local FTS and FTS-multihop evidence, explicit non-leaderboard claim boundaries, unique run ids, and compact artifact guidance.
- Added site lint/build and docs typecheck/build jobs to GitHub Actions.
- Updated the docs dependency set and pinned fixed PostCSS/Lodash transitive releases; docs audit and site production-dependency audit now report zero vulnerabilities.

### Portable Proof

- Added `zerker.receipt_bundle.v2` as the default receipt bundle format. It commits to the complete pre-action event log while carrying only indexed Merkle witnesses for supporting write events and the final pre-action anchor.
- Kept `zerker.receipt_bundle.v1` verification intact and exposed explicit legacy generation through `MemoryStore.receipt_bundle(action_id, compact=False)`.
- Switched CLI exports, handoffs, Treeship statements, and benchmark bundle consumers to compact v2 by default without changing their command surface.
- Added witness tamper, missing-provenance-witness, legacy compatibility, and serialized-size regression coverage. A 31-event repeated-action fixture measured 35,453 bytes for v2 versus 963,288 bytes for v1, a 96.32% reduction; both artifacts verified successfully.
- Kept the claim boundary explicit: bundle verification proves inclusion and provenance relative to an anchored Merkle root, not semantic truth.

### Verification

- `python3 -m unittest discover -s tests -q` (`1215` tests)
- `python3 -m zerker_memory eval` (`11/11`)
- `python3 scripts/release_smoke.py --summary-only`
- `npm ci && npm run lint && npm run build` in `site/`
- `npm ci && npm run typecheck && npm run build` in `docs/`
- Production-preview browser QA at desktop, tablet, and mobile with a clean console

## 0.1.2 - 2026-07-06

### Shipped

- Landed the continuous swarm hardening checkpoint across trust ledger, temporal memory, lifecycle receipts, retrieval ordering, consolidation lineage, workspace source identity, dashboard reporting, and release proof tracking.
- Hardened trust-ledger mutation coverage for promoted, rejected, revoked, forgotten, checkpointed, snapshotted, and restored memory state.
- Expanded temporal/query coverage for current, historical, future, superseded, and unlearned memory views.
- Improved deterministic retrieval explainability around support-chain reservation, stale/current update-history pairs, temporal support ordering, and budget-dropped/withheld memory metadata.
- Added consolidation lineage, unwind, duplicate suppression, and append-only summary-ledger coverage.
- Improved workspace/source identity summaries, conflict previews, connected-agent traces, and dashboard source reporting.
- Kept benchmark claims narrow: LoCoMo FTS and LongMemEval matrix results remain evidence, not leaderboard claims.

### Changed

- Refined the public website positioning around ZMem as memory AI agents can rely on: local memory, review, scoped use, handoff, and receipts.
- Updated homepage copy to distinguish ZMem from generic durable context/search products: search finds context; ZMem helps decide what memory should shape agent work.
- Locked the homepage/nav/footer structure around the launch sequence: hero, agent stack band, memory workflow, native memory and context control, handoff, proof, and install.
- Reframed proof language around lineage and memory influence, not semantic truth or unsupported cryptographic claims.
- Verified the next L3 retrieval slice locally: update-history relation-pair RRF promotes explicit stale/current relation pairs over generic high-authority change anchors under tight context budgets.

### Verification

- `npm run build` in `site/`
- `python3 -m unittest tests.test_store.MemoryStoreTest.test_update_history_relation_rrf_promotes_explicit_current_relation_over_high_authority_generic_anchor tests.test_runner.RunnerTest.test_update_history_relation_context_rrf_promotes_explicit_current_relation_over_high_authority_generic_anchor -q`
- `python3 -m unittest tests.test_store tests.test_policy tests.test_runner -q`
- `python3 -m zerker_memory eval`
- `git diff --check`
- `python3 -m unittest discover -s tests -q`
- `python3 scripts/release_smoke.py --summary-only`
- GitHub Actions `test` on Python 3.10, 3.11, and 3.12
- GitHub Actions `release-smoke`

## 0.1.0-alpha frontier build - ActiveGraph, LoCoMo, and compact traces

### Shipped

- Added the ActiveGraph source integration pack with `zmem.persist`, `zmem.recall`, and compact benchmark behaviors.
- Added `pack/pack.yaml` and the `activegraph.packs` entry point so the ZMem pack has a stable manifest.
- Added ActiveGraph memory writes with causal event pointers through `caused_by_event`.
- Added a compact event-sourced LoCoMo runner that writes `trace.jsonl` and `scored_receipt.json` instead of per-question receipt bundles.
- Recorded the official LoCoMo FTS baseline under `.zerker/bench/locomo-official-v1/fts/`: 1,986 questions, F1 `0.3752394031509457`, EM `0.37210473313192344`, trace SHA `67a005bf87b4bafcd2d7ce1cf8bfff97d7f430788afd0472511f738594971d0c`.
- Added next-run guidance for `fts-multihop` and `pseudo-embedding-rerank` so retrieval depth and reranking can be compared against the same LoCoMo dataset.
- Added the frontier benchmark queue: LongMemEval-S for abstention and token efficiency, plus BEAM for scale and causal-memory stress.

### Boundary At That Checkpoint

- The ActiveGraph integration was source-level at this checkpoint; `0.1.4` replaces it with a real ActiveGraph 1.9 pack and loader verification.
- The old proposed `activegraph pack add` smoke is superseded by `activegraph pack list` plus `python scripts/verify_activegraph_pack.py --summary-only`.
- Public benchmark claims remain scoped to the recorded rule-based token F1/EM receipts until official benchmark submission rules are satisfied.

## 0.1.0-alpha - Local-first proof memory MVP

### Positioning

- Packaged Zerker Memory as open-source, local-first portable memory with proof for AI agents.
- Clarified the `zmem` promise: store memory locally, govern what gets injected, and prove what influenced each action.

### Shipped

- Local SQLite memory store with FTS search and fallback search.
- Typed memories: episodic, semantic, procedural, and policy.
- Trust and authority as separate controls.
- Quarantine, review queue, promote, reject, revoke, lineage, and revocation propagation.
- Symbolic policy gate before memory injection.
- Append-only event log, Merkle roots, action receipts, `why`, receipt bundles, stable export, snapshots, verify, and restore.
- Memory Merkle trees on injection receipts, so agents can see the selected-memory root and per-memory inclusion proof behind the context they used.
- CLI entrypoints: `zmem`, `zerker-memory`, compatibility `zerker`, and `zerker-memory-mcp`.
- MCP server and Python package APIs.
- Local review console with memory review, topic inspection, receipt actions, proof inspector, release-pack, handoff, restore, launch-asset verification, and return-packet verification.
- Agent setup for Codex, Claude Code, OpenClaw, Hermes, and generic MCP clients.
- Day-1 bootstrap with `install.sh`, `examples/first_run.sh`, eval, doctor, agent smoke, and MCP smoke.
- Launch proof and release pack flows for local proof reports, handoff archives, public verify packets, return packets, and screenshot/GIF checklists.
- Behavior-tree recovery memory: trace ingest, deterministic fallback explanation, py_trees/BTPG helpers, and BehaviorTree.CPP/Groot2 export.
- Provider governance scaffold for Mem0 and Zep, with external imports quarantined by default.
- GitHub Actions test/eval/release-smoke coverage.
- Static landing page and launch-proof report surfaces.
- Landing and dashboard usability pass with clearer agent-facing positioning, a direct add-memory flow, topic inspection, daily-use workflow cards, Cursor continuity state, and a friendlier saved-memory proof summary.
- Builder-experience pass with `docs/BUILDER_EXPERIENCE.md`, clearer Codex/Claude direct install guidance, Cursor/manual MCP import guidance, agent prompt usage, and smoke-check acceptance steps.

### Current Launch Gate

- Local alpha is functional and ready for dogfooding.
- Strict public alpha launch still requires public GitHub/raw-installer proof, clean-shell packaged-install logs, and the final screenshot/GIF asset set.
