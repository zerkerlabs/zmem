# ZMem Release Comms

## 2026-08-18 - v0.1.16 publication

Audience: internal Zerker product, engineering, developer experience, security review, Reason integration, Gateway integration, and release coordination.

`v0.1.16` is published from release PR `#42` merge commit `1f7ede37a5aa1c59e50e2700b06aeb456b0f8aa4` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.16`; feature PR `#37` supplied governed premise export at `169e7e2f1a53dea64b3e2f36d978ee2e35598772`. Release, main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. Downloaded GitHub assets match wheel `sha256:069c53dd...` and source distribution `sha256:d38de6c2...`.

The release gives downstream reasoning systems a narrow, machine-checkable boundary. `zmem reason export` emits deterministic structured facts only from active memories carrying `reason:premise:v1`, with per-fact receipt provenance under one locked SQLite snapshot. `zmem reason verify` recomputes current governed state and fails closed when an artifact is malformed, tampered, stale, replayed, revoked, duplicated, or contains non-finite JSON.

The responsibility split is explicit. ZMem establishes that the bytes came from the named governed memory and still match its current lifecycle and receipt state. It does not prove that the fact is true in the outside world, define Reason's ontology, or authorize an action. Reason remains responsible for authority policy, temporal interpretation, derivation, conflicts, and authorization.

Production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`; the changelog and `/docs/reason` canaries pass with clean console and network logs. External-agent PR `#8` is now the only open PR and remains excluded until rebased or replaced. The next cross-product gate is still Gateway's immutable `v0.1.15`-or-newer pin, cached-dense readiness, realistic load/timeout/isolation checks, and one host-native two-agent attach/revocation flow. `v0.1.16` leaves the Rooms HTTP contract unchanged.

## 2026-08-18 - v0.1.15 publication

Audience: internal Zerker product, engineering, developer experience, security review, Gateway integration, and release coordination.

`v0.1.15` is published from release PR `#40` merge commit `e9f1bf9ac374339bec9de154683f5e8607cd8fc6` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.15`; feature PR `#39` supplied the one-command agent connection flow at `91fee93a2427b8389a03654a460d8d5a6a0b4ba3`. Release, main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. Downloaded GitHub assets match wheel `sha256:9b6dcbd5...` and source distribution `sha256:ce89df3a...`.

The release turns the existing setup plus invitation machinery into one ordinary agent-native action: run `zmem connect <agent>` inside the project. ZMem verifies the exact workspace binding, configures that one host, and prints one scoped, expiring instruction for the current connector. Direct clients may still need a reload; manual clients still need an import; and no session is called live until the invited MCP process attaches.

The trust boundary remains narrow. Every agent receives a different single-use code and process identity. A client session id is asserted unless the host verifies it. A Room id supplies context but never grants Gateway membership. A real three-process acceptance proved that Codex can propose memory, a trusted operator can promote it, Claude Code can recall it through a distinct connection, and the retrieval receipt verifies.

Production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`. Gateway issue `#49` now has the exact `v0.1.15` pin and hashes. The next cross-product work is production cached-dense setup, load/timeout/isolation gates, and one host-native two-agent Room flow. Reason premise-export PR `#37` remains blocked until non-finite JSON fails closed; stale PR `#8` remains excluded.

## 2026-08-18 - v0.1.14 publication

Audience: internal Zerker product, engineering, developer experience, security review, Gateway integration, and release coordination.

`v0.1.14` is published from release PR `#36` merge commit `1a70f25fe9fc0df6680cd3fdbc5520192715d40f` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.14`. Feature PR `#35` supplied fail-closed dense Room readiness at `ebb6c96e72032c174f3188c4d262d48c2dc0f4d4`; console-native session controls and the patched docs runtime were already merged. Release, main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. Downloaded GitHub assets match wheel `sha256:ec816163...` and source distribution `sha256:652e3052...`.

This release closes an operational ambiguity in shared memory. `/healthz` answers only whether the tenant-local ZMem process is alive. `/readyz` answers whether the requested retrieval profile can actually serve traffic. FTS is immediately ready; dense-hybrid stays unavailable with HTTP `503` until FastEmbed and the configured cached local model are present. The probe never downloads or initializes a model, and startup prints the bounded reason plus setup command.

The local console now also owns the ordinary session-control loop: select a configured agent, create a short-lived single-use invitation, copy the exact attach instruction, and detach the connector without deleting memory. This authenticates the invitation and consuming MCP connection; it does not grant Room membership or claim that a client-supplied UI session id was independently verified.

Production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`. Gateway issue `#49` has the exact release pin, hashes, readiness semantics, and remaining acceptance gates. The next cross-product work is to pin `v0.1.14`, pre-cache the dense model, gate traffic on `/readyz`, then pass realistic load/timeout and one live two-agent Room flow. Reason premise-export PR `#37` is post-release work and remains independently reviewable.

## 2026-08-18 - v0.1.13 publication

Audience: internal Zerker product, engineering, developer experience, security review, Gateway integration, and release coordination.

`v0.1.13` is published from release PR `#30` merge commit `6fe15c6b310fea6e1dd3b26206ca6172b680eea1` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.13`. Feature PRs `#26` through `#29` supplied the Rooms contract, semantic recall, agent memory network/transfer, and live-session implementations. Release, main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. GitHub assets match wheel `sha256:c2450c6a...` and source distribution `sha256:44bdf177...`.

The release makes the daily multi-agent story tangible. Guided setup still gives supported agents one exact project store. Operators can now issue a short-lived one-time invitation for a named connector, see configured and historically observed agents next to live or idle attachments, detach a connection without deleting memory, inspect Room-shared/member-private inventory and proof roots, and preview handoff or snapshot state before importing it.

The identity and authority boundary remains deliberately narrow. ZMem authenticates the invitation and consuming MCP connection; optional client session labels and ids are asserted until a host-native adapter verifies them. A Room id never grants membership. Gateway remains authoritative for tenant identity, Room membership, and access, while ZMem owns governed memory selection and its exact context commitment.

Dense-enabled Rooms now maintain local semantic indexes after writes and disclose compact readiness without leaking vectors. Context preparation distinguishes a Room with no memory from an established Room with no confident match. The cross-language commitment fixture pins exactly what Gateway and ZMem must hash.

Production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`. The next ZMem slice is console-native invitation/detach actions; the next cross-product slice is host-confirmed session identity plus the Gateway/Buzz attach and revocation handshake. External-agent PR `#8` remains excluded until rebased and revalidated against current `main`.

## 2026-08-10 - v0.1.12 publication

Audience: internal Zerker product, engineering, developer experience, security review, Gateway integration, and release coordination.

`v0.1.12` is published from release PR `#24` merge commit `25b1c7a1f125f4e42f43053e0de99fef2538a0f7` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.12`; feature PR `#23` supplied the implementation. Feature PR, release PR, post-merge main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. GitHub assets match wheel `sha256:ae75cb6e...` and source distribution `sha256:cca4fed7...`.

The release replaces the ambiguous idea of `zmem connect codex claude-code hermes` with a real builder workflow. Run `zmem setup codex claude-code hermes` inside a project. ZMem initializes the local workspace, points every selected client at the same absolute database and policy, configures Codex and Claude Code directly, exports exact entries for manual clients, and tells the operator whether each client is reload-ready or still awaiting import.

The identity boundary is deliberately narrow. The generated MCP command binds the agent host, and each server process contributes a connection id for provenance. ZMem does not claim that process id is the editor's private UI chat id. The default agent profile remains proposal/read/explain/verify only; setup does not grant agents operator review authority.

Real-machine dogfooding installed the exact published wheel, configured all six supported presets, verified every exact binding with doctor, and passed live Codex plus Claude Code MCP read/write/proof smokes. Existing direct-client sessions need reload. Hermes, Cursor, OpenClaw, and generic MCP clients require one explicit import of the generated project-local export.

Production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`. The next product integration remains the Gateway Rooms client and durable persistence boundary; guided setup should be reused as the local developer entry point rather than replaced with a second connection model.

## 2026-08-10 - v0.1.11 publication

Audience: internal Zerker product, engineering, security review, Gateway integration, and release coordination.

`v0.1.11` is published from PR `#20` merge commit `ca427692cab8cb71c5f95c7d48c9a33499f01f7b` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.11`. PR, post-merge main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. GitHub assets match wheel `sha256:cd19b739...` and source distribution `sha256:11bc45f4...`.

The patch closes a real race found only by the later `v0.1.10` main run. Multiple workers could first-open the same room database and collide while enabling SQLite WAL. ZMem now serializes database construction and schema initialization per opaque tenant-room key, then releases the lock before normal reads and writes. The regression forces eight simultaneous first opens and verifies durable unique writes plus retry idempotency.

The product boundary is unchanged. ZMem now provides a stronger tenant-local shared-memory service, but the Gateway Go client, durable Rooms event persistence, hosted tenant routing, remote review authorization, production load evidence, and asynchronous Treeship publication remain separate integration work.

Production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`; the public changelog, `/docs/rooms`, and ActiveGraph `0.1.11` example match the shipped package. The next integration slice is the Gateway adapter and persistence boundary.

## 2026-08-10 - v0.1.10 publication

Audience: internal Zerker product, engineering, security review, Gateway integration, and release coordination.

`v0.1.10` is published from PR `#18` merge commit `a48219337abf5b70373a59d2b1ed420378d7d8c3` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.10`. PR, main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. GitHub assets match wheel `sha256:dbaa5f34...` and source distribution `sha256:17f2eaef...`.

The release turns the proposed Zerker Rooms memory boundary into a runnable tenant-local service. Room-shared and member-private state are physically isolated per tenant and room, accepted events and agent proposals have distinct write paths, retries are idempotent, and context preparation preserves policy order plus admitted, withheld, budget-dropped, and abstained state. A compact commitment binds the exact memory selection without copying raw memory into the proof layer.

The security and ownership boundary remains explicit. Rooms owns membership, goals, messages, and the room event log; ZMem owns memory state, review, retrieval, context packing, and memory receipts. This release does not yet include the Gateway Go client, durable Rooms event persistence, hosted tenant routing, remote review authorization, production load evidence, or asynchronous Treeship room publication.

Production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`; the public changelog and `/docs/rooms` guide match the shipped package. The next integration slice is the Gateway adapter and persistence boundary, not another memory-store rewrite.

## 2026-08-05 - v0.1.9 publication

Audience: internal Zerker product, engineering, security review, and release coordination.

`v0.1.9` is published from PR `#16` merge commit `a2a469f3502bfdfafc13158db6e9ceea3c5769bf` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.9`. PR, main, and tag CI passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. GitHub assets match wheel `sha256:3c47550a...` and source distribution `sha256:f801c7fd...`.

The release completes the bounded consolidation review lifecycle. Live source evidence is verified before private materialization, inspection independently recomputes the deterministic summary, and an operator must explicitly admit or discard it. Admission is the only canonical-memory write and cannot exceed the weakest source trust or authority. Discard retains evidence and creates no canonical memory.

The proof boundary remains unchanged: receipts establish integrity, provenance, lineage, and the recorded decision path, not semantic truth. CLI actor ids are asserted rather than authenticated, and optional Treeship anchoring remains a separate proof step.

The production site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`. The next product slice is reviewed live day/week/profile rollups, still without a scheduler or automatic semantic promotion.

## 2026-08-05 - Explicit consolidation decision candidate

Audience: internal Zerker product, engineering, security review, and release coordination.

The post-`v0.1.8` consolidation path is now end to end. Materialization still creates only a private review copy. A separate inspection re-audits its ledgers, verifies current source receipt heads, and recomputes the deterministic summary from live sources before exposing an exact confirmation.

Admission is the only operation that crosses into canonical memory. It writes one deterministic semantic memory at exactly the weakest source trust and authority ceilings, with source ids as parents and parent/label lineage committed in the write receipt. Discard writes no canonical memory and deletes no evidence. Both are terminal, mutually exclusive events in the local Merkle chain.

The canonical write, receipt, and admission event commit atomically. Exact replay and concurrent operators are idempotent; stale source or inspection state fails closed. Operator ids remain asserted metadata, Treeship anchoring is separate, and neither the summary nor its proof is a semantic-truth claim.

Focused acceptance is green across the new `16`-test adversarial suite, `117` consolidation tests, the `411`-test consolidation/store gate, and adjacent Treeship/trust, runner, and policy suites. Independent re-review reproduced and cleared the event/receipt-head, trust-ceiling, canonical-content, and unreceipted-source integrity findings. Full local acceptance also passes `1,370` tests with two expected optional skips, eval `11/11`, site lint/build, docs typecheck/build, compilation, strict release smoke, and a clean staged-source `0.1.9` package install. The publication record above supersedes this pre-release checkpoint.

## 2026-08-01 - Review-gated live consolidation candidate

Audience: internal Zerker product, engineering, security review, and release coordination.

PR `#14` merged the read-only source preview with every CI check green. The next isolated candidate completes one deliberately narrow transition: an operator reviews the content-free source report, confirms its artifact-specific id, selects one candidate, and materializes one deterministic local summary into private append-only ledgers.

The summary is not trusted memory. It starts quarantined at trust zero and authority none, remains non-blocking and reversible, and cannot influence retrieval because no canonical memory row is created. The compact result carries hashes and bindings rather than source or summary text; the private `0600` summary ledger retains the local summary content.

The correctness boundary was independently reviewed and hardened before landing. The commit holds a SQLite writer lock while exposing a query-only source snapshot, serializes ledger writers, resumes verified partial appends, binds the completed job to the original summary content digest, rejects database/sidecar or symlink destination aliases, and makes audit fail on incomplete, orphan, duplicate, reordered, content-changed, or binding-broken histories. Operator identity remains asserted metadata, not authenticated identity, and no semantic-truth claim is made.

Focused consolidation acceptance passes `109/109`; the full repository passes `1,354` tests with two expected optional skips. Eval `11/11`, docs typecheck/build (`17` static pages), site lint/build, fresh-workspace release smoke with the packaged-path requirement, strict publish readiness, public proof `6/6`, launch assets `8/8`, and return-packet verification all pass. No release tag or production deployment has been made for this candidate.

## 2026-08-01 - Live consolidation source preview candidate

Audience: internal Zerker product, engineering, security review, and release coordination.

PR `#13` merged reviewable lifecycle maintenance with all CI checks green. The next isolated candidate now connects the existing consolidation ledgers to live MemoryStore evidence through a read-only preview. It verifies global events, each source receipt chain, latest-event coverage, and current row coherence before grouping active episodic/semantic sources by origin actor, environment, and session.

The report keeps source ids and hashes, explicit omission reasons, and weakest-source trust/authority ceilings while excluding raw memory text. A future output would start quarantined at trust zero and authority none. It does not generate a summary, queue a consolidation job, write either ledger, or create canonical memory. The next reviewed action is explicit materialization into the existing reversible ledgers, still without canonical admission.

Focused acceptance passes `16/16`, the consolidation/store/CLI integration cluster passes `663/663`, and the full repository passes `1,330` tests with two expected optional skips. Specialist review findings for malformed-row isolation and stable preview identity are closed. Eval, docs, package build/import, compilation, diff checks, and release smoke pass; strict publish evidence remains ready. This candidate is not yet merged, tagged, or deployed.

## 2026-08-01 - Reviewable lifecycle maintenance candidate

Audience: internal Zerker product, engineering, security review, and release coordination.

The post-`v0.1.8` candidate now joins read-only health inspection to a deliberately narrow maintenance workflow. An operator previews a hash-bound plan, selects one action, confirms the exact plan id, applies it, and verifies the resulting receipt. The only executable v1 condition is an active memory whose explicit expiry timestamp has passed and whose write receipt verifies.

This does not turn ZMem into a semantic-truth engine. Conflicts, duplicates, weak provenance, active lineage, and high-risk use remain review-only. The new `expired` transition is non-cascading and preserves the row. Plans contain metadata and hashes rather than memory text, stale state is rejected, replay is idempotent, and result verification distinguishes historical proof from the current store state. The supplied operator id is an asserted audit field, not authenticated identity.

Broad swarms remain paused. After review and release gates, the next isolated product lane should connect consolidation to live store candidates with explicit source coverage and reversible summaries.

Local acceptance is complete: focused maintenance `20/20`, combined integration `824/824`, full repository `1,314` with two expected optional skips, eval `11/11`, fresh-workspace and strict release smoke, packaged-wheel import, and docs typecheck/build all pass. This branch has not yet been committed, opened as a PR, tagged, or deployed.

## 2026-07-30 - v0.1.8 publication

Audience: internal Zerker product, engineering, benchmark review, security review, and release coordination.

`v0.1.8` is published from `969a943a987ac9528e4781702b8cb14ed59a9387` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.8`. Main CI run `30571175219` and tag CI run `30571663116` passed every Python 3.10/3.11/3.12, ActiveGraph, site, docs, and release-smoke job. GitHub assets match wheel `sha256:6e5bedd1...` and source distribution `sha256:84b773c7...`.

The site and docs are live at `https://www.zmem.sh` and `https://docs.zmem.sh`. Production canary caught one stale pre-dense benchmark callout below the new release entry; the follow-up replaces it with the verified v0.1.8 dense-hybrid comparison and retains the explicit local-evidence, non-leaderboard boundary.

The next isolated product lane is a read-only memory-health audit. It may identify stale, contradictory, duplicate, weak-provenance, or high-risk active memory, but it must not mutate lifecycle state or present heuristic findings as semantic truth.

## 2026-07-30 - v0.1.8 governed continuity and dense-retrieval candidate

Audience: internal Zerker product, engineering, benchmark review, security review, and release coordination.

`v0.1.8` packages three clean post-`v0.1.7` commits: digest-bound governed memory context, scheduled-agent cold-start continuity plus typed failure memory, and opt-in local dense/FTS retrieval. The release keeps dense candidate discovery behind the existing scope, lifecycle, policy, packing, and receipt boundary; it does not make semantic similarity a truth or authorization signal.

The full local evidence is material and zero-loss against the selected lexical baseline: the frozen cohort improves from `160/227` to `203/227`, LoCoMo from `1,220/1,986` to `1,567/1,986`, and LongMemEval from `386/500` to `477/500`. Dense remains opt-in because query context and latency both increase. The benchmark values are deterministic local evidence-support scores, not official leaderboard claims.

The July 30 product-signal reconciliation sets the next post-release sequence: read-only memory health audit, contradiction-driven abstention, reviewable lifecycle maintenance, live source-backed consolidation, handoff ownership/import preview, and governed tool-contract trust records. Effect verification, capability leases, missing-witness reporting, and skill cold-start execution proof remain Treeship/Guard responsibilities.

## 2026-07-21 - Local dense retrieval candidate

Audience: internal Zerker product, engineering, benchmark review, and release coordination.

ZMem now has an opt-in true local dense candidate source rather than another lexical exception. FastEmbed generates candidates independently of FTS, and reciprocal-rank fusion preserves the adaptive lexical candidate set before the normal scope, lifecycle, policy, packing, and receipt path runs. Search cannot download a model. Vectors are derived local state bound to memory content, provider config, and a digest of the cached model files.

The measured quality change is material. The frozen gate moves from `160/227` to `203/227`; full LoCoMo moves from `1,220/1,986` to `1,567/1,986`; full LongMemEval moves from `386/500` to `477/500`. The comparisons contain 43, 347, and 91 gains with zero losses. All result and cross-mode comparison artifacts verify locally, one pinned model digest was used, and no query-time network call or fallback occurred.

The cost is also material. Mean query context rises about 69% on LoCoMo and 44% on LongMemEval. Observed full-run p95 latency rises from `690.389 ms` to `3,158.984 ms` on LoCoMo and from `193.610 ms` to `368.415 ms` on LongMemEval. Product decision: package dense-hybrid as opt-in, then tune candidate depth and packing under the same zero-loss gates. Do not make it the default or add ANN complexity until profiling justifies that move.

Claim boundary: these are deterministic local evidence-support scores, not official LoCoMo or LongMemEval leaderboard submissions. Dense similarity finds candidates; it does not make a memory true, trusted, current, or authorized. Existing MCP schemas remain on stable FTS behavior in this candidate.

## 2026-07-20 - Digest-bound memory context candidate

Audience: internal Zerker product, engineering, security review, and release coordination.

ZMem can now commit the exact memory context it supplied to an agent. The `zerker.memory_context.v1` digest covers admitted records, considered/withheld/budget-dropped sets, policy decisions and policy digest, temporal metadata, and memory/event roots. The compact commitment persists with the action receipt and follows the decision through `why`, wrapped runs, Treeship export, and ActiveGraph read proof.

This sharpens the product claim without overreaching. We can prove which ZMem context artifact crossed the decision boundary and detect later tampering. We are not claiming semantic truth, hidden-reasoning capture, or full provider-prompt capture. Treeship remains optional and receives compact digests; ZMem remains useful and verifiable locally.

The July 20 product signal changes the next sequence. First, turn existing session/handoff primitives into a scheduled-agent cold-start demo with wall-clock gap audit and explicit stale/unknown state. Second, add typed failure memory for expected invariant, observed effect, correction, and invalidation. Third, begin isolated true local dense candidate generation; stop buying retrieval gains one lexical exception at a time.

Local acceptance is green: `1,266` tests, eval `11/11`, both public builds, strict release smoke, and an end-to-end CLI/Treeship digest smoke pass. This is an unreleased candidate until it is committed, reviewed, and packaged.

## 2026-07-16 - v0.1.7 runtime and claim-integrity publication

Audience: internal Zerker product, engineering, security review, and release coordination.

`v0.1.7` packages the independently reproduced post-`v0.1.6` findings that could be fixed without changing ZMem's compatibility contract. Implicit run context is private and ephemeral; MCP inputs, outputs, errors, file paths, and provider connections are bounded at the operator boundary; provider governance values must be finite; and unjudged benchmark answers remain pending instead of being counted as failures.

The release intentionally preserves `binary-sha256-v1`. The real compatibility weakness is duplicate-last leaf-count ambiguity, not a demonstrated variable-boundary collision between fixed-width receipt hashes. Merkle `v2` requires per-receipt algorithm dispatch, legacy fixtures, mixed-algorithm verification, and no historical rewrite. Installer integrity and provider credential-host binding are also deferred as separate security slices.

PR `#6` merged at `9f3996f` with every remote check green, and the versioned release commit merged at `5831d85`. `v0.1.7` is published from `5b1cf0f05689143a3905fb2337807f4c60a191ea`; final-commit CI run `29534932237` and tag CI run `29535282896` passed every job. GitHub assets match wheel `sha256:d8a3fdba...` and source distribution `sha256:8a710295...`. Production deployments `dpl_9Xb2upPsawLoDhaco6r5CSJppvxW` and `dpl_ckk7y9HhAg4fg2n1z67uBLJJQ8e8` are live at `zmem.sh` and `docs.zmem.sh`, and public package, raw-installer, responsive browser, console, network, agent-smoke, and MCP-smoke canaries pass.

## 2026-07-16 - v0.1.6 publication and independent review boundary

Audience: internal Zerker product, engineering, security review, and release coordination.

`v0.1.6` combines the three post-`v0.1.5` feature commits with four bounded release hardening fixes: serialized event-chain appends, consistent `~` expansion, strict MCP boolean parsing, and corrected public dependency/copy surfaces. It is published from `34b4e8aa2b41a454e2e8969576511ffd56a66027`; final-commit CI run `29524503194` and tag CI run `29524866769` are green. The GitHub release carries the verified wheel `sha256:f587f652...` and source distribution `sha256:7a77df87...`. Production deployments `dpl_9WBakHxq6DtPXF5cXVzQ1FuQjj9e` and `dpl_Dp1maM9BzkJ8RAydjn3agp8P6dBr` are live at `zmem.sh` and `docs.zmem.sh` with clean desktop/mobile, console, and network canaries.

The external review was useful but mixed real defects with incorrect trust-boundary assumptions. Search, provider calls, snapshot/restore, and lifecycle mutation tools are operator-profile capabilities, not default agent-profile tools. Direct `MemoryStore` methods are in-process library primitives; the current interface boundary is the MCP profile, not multi-user authentication.

One cryptographic issue is real and intentionally deferred: the current duplicate-last Merkle tree cannot distinguish `[a,b,c]` from `[a,b,c,c]`. A safe fix is not an unversioned hash tweak. The follow-up must define a versioned root with leaf/node domain separation and explicit leaf-count or shape binding, continue verifying legacy `binary-sha256-v1` receipts, and document migration before implementation.

After `v0.1.6`, give the reviewer a clean tag and a read-only adversarial brief. Ask it to reproduce the fixed concurrency/path/boolean cases, reassess every remaining finding against agent/operator/in-process boundaries, and pressure-test the Merkle `v2` design. Do not let that review edit the same worktree while the dense retrieval lane is active.

## 2026-07-16 - BEAM 1M/10M scale checkpoint

Audience: internal Zerker product, engineering, and release coordination.

ZMem now completes locally verified official-layout BEAM conversation runs at both 1M and 10M buckets. The sampled 10M conversation contains 19,895 messages and 6,209,948 observed whitespace tokens; all 201 source references resolve, and the compact proof artifact stays under 1 MB.

The first 10M run found a real SQLite bottleneck rather than a benchmark-harness illusion. Semantic rescue ordered candidates through a correlated event-sequence lookup without an index. Adding `events(memory_id, seq)` improved the same `fts-adaptive` event-ordering query from `112,976 ms` to `8,344 ms`, a `13.54x` speedup, with the same result and the same retrieved/injected memories.

The migration is behavior-neutral across the deterministic 227-question gate, all 1,986 LoCoMo questions, and all 500 LongMemEval questions. LoCoMo stays `0.6143`; LongMemEval stays `0.772`.

The honest product conclusion is two-part: sampled-scale execution and compact proof now work, but retrieval quality at scale does not. Local BEAM evidence recall is `0.15` at 1M and `0.10` at 10M. Public copy must keep `public_benchmark_claim: false` and must not present this as an official model-judged BEAM result.

## 2026-07-16 - runnable ActiveGraph host candidate

Audience: internal Zerker product, engineering, and release coordination.

ActiveGraph integration now has a runnable product path rather than only a verifier and code snippet. `examples/activegraph_host.py` uses no API key: the first run loads the installed pack and persists an event-backed memory, while a distinct resume run recalls the shared ZMem scope before a deterministic provider call.

The command fails unless the original ActiveGraph event id survives into the memory receipt, the provider receives the memory plus a ZMem recall receipt, ActiveGraph records exactly that same prompt, and the answer comes from the recalled fact. ActiveGraph `1.10.0`, the installed-pack verifier, the command, and all seven integration tests pass locally.

This completes the runnable-host acceptance item. Larger selected-mode traces and aggregate Treeship artifacts remain optional follow-ups; they are not blockers for the standalone integration.

## 2026-07-16 - transcript-neighbor retrieval candidate

Audience: internal Zerker product, engineering, and release coordination.

The next L3 candidate recovers one structured conversational onset answer without widening unrelated retrieval. For `When did John get an ankle injury in 2023?`, an already-retrieved same-speaker nucleus can pull in one earlier turn only when both memories share the exact event head, transcript session, and timestamp and are at most two turns apart.

The narrowing process matters. Bidirectional adjacency changed nine stable contexts. Earlier same-timestamp adjacency changed six. Requiring the event head removed the five qualifier-only decoys, leaving exactly one changed retrieval context.

The stable cohort moves from `159/227` to `160/227`; full adaptive LoCoMo moves from `1,219/1,986` to `1,220/1,986` (`0.6143`). Both comparisons have one multi-hop gain and zero losses. LongMemEval stays exactly unchanged at `386/500`, including answers, retrieval ids, and tokens. All three artifacts verify locally.

Claim boundary: this is provisional local retrieval evidence and bounded structured-transcript support. It is not official leaderboard scoring, unrestricted conversation adjacency, or general graph traversal.

## 2026-07-12 - v0.1.5 release checkpoint

Audience: internal Zerker product, engineering, and release coordination.

The candidate adds one deliberately narrow retrieval gain, the first BEAM 500K scale evidence, and a real ActiveGraph pre-call host boundary.

Completion support activates only when retrieval already found the same named subject and object, then adds at most one explicit completion paraphrase. It improved the stable 227-question cohort from `158` to `159` and full LoCoMo from `1,218` to `1,219`, with zero losses in both comparisons. LongMemEval stayed at `386/500`. This is a small gain, but it is exactly the desired shape: measurable, receipt-visible, and regression-free.

The isolated official-layout BEAM 500K conversation covered 796 messages, 247,175 observed whitespace tokens, 20 questions, and all 83 source references. Its `0.30` deterministic local evidence recall is diagnostic, not an official BEAM answer score.

ActiveGraph hosts can now wrap an LLM behavior with `enable_precall_recall(...)`. ZMem enriches the prompt before ActiveGraph hashes and records it. A real ActiveGraph 1.9 runtime test proves the provider-bound and event-recorded prompt content match exactly. The installed `zmem.recall` behavior remains an audit hook for immutable request events.

Published `v0.1.5` from `d4f6d9a3bd6a09a09fa579203510406edea11f6a` after GitHub Actions run `29216453125` passed the full Python matrix, ActiveGraph, site, docs, and release smoke. Final artifacts are wheel `sha256:fb97ea0b91e210f1342d368490b000987ae3d31493c10c81d50ca2d555bbc930` and source distribution `sha256:2a3ff46a4e0d1e977aeb753c23b17f5933b93e69d71a4eda8f2232ecb59b8a04`.

The tested Vercel deployment `dpl_3eCbYfb2MejVCAs9U6ZvWuUWG9SK` is live at `zmem.sh`. Desktop and mobile production checks pass with no horizontal overflow, and a fresh production tab reports no console warnings or errors.

## 2026-07-11 - v0.1.4 release checkpoint

Audience: internal Zerker product, engineering, and release coordination.

Published from `0ea8316062af6123921e902dee2a3a6783cd4ba2` after GitHub Actions run `29165187978` passed every job. The release attaches the verified `0.1.4` wheel and source distribution.

This release packages the nine post-v0.1.3 benchmark-operation commits with one bounded retrieval improvement, the first BEAM scale adapter, and a production-shaped ActiveGraph pack.

The retrieval change is deliberately narrow. Conservative regular-inflection matching activates only when a candidate already shares at least two exact query anchors and gains at least two additional inflection matches. It improved the stable 227-question cohort from `156` to `158` with zero losses. Only after that gate passed, full adaptive LoCoMo improved from `1,213/1,986` to `1,218/1,986` (`0.6133`) with five gains and zero losses, and LongMemEval improved from `383/500` to `386/500` (`0.772`) with three gains and zero losses.

BEAM is now an implemented scale harness, not a roadmap row. The first untouched official 100K adapter smoke covered 188 messages, 63,411 observed whitespace tokens, 20 questions across all ten categories, and resolved all 53 source references. Its compact result verifies locally. This is evidence-recall and scale instrumentation, not the official model-judged BEAM quality score.

ActiveGraph 1.9 now discovers a real `zerker_memory.pack:pack`, loads it idempotently, resolves both canonical behaviors, and persists a real object event into ZMem. A 227-question batched trace wrote 908 events in eight commits, produced an approximately 1 MB event database and 196 KB trace, and wrote zero per-question receipt bundles. The direct source hook can return context before a host model call; the installed request behavior records an immutable runtime event and must not be described as a prompt interceptor.

Release smoke also uncovered and fixed two local packaging hazards: copied uv-managed Python executables lost their base-prefix on macOS, and the release-surface copy included local web caches plus `.treeship` runtime data. POSIX smokes now use symlinked venv executables and omit generated dependency/runtime directories. The optimized full smoke passes, and the `0.1.4` wheel and source distribution both build.

### Release claim boundaries

- LoCoMo and LongMemEval values are verified local provisional retrieval evidence, not official leaderboard rankings.
- The BEAM smoke proves adapter/source coverage and compact evidence behavior, not an official BEAM answer score.
- ActiveGraph loader, event persistence, and batching are verified; production-host pre-call injection still requires the explicit direct recall hook.
- Tag only after the full Python suite, eval, release smoke, site/docs builds, package build, real ActiveGraph verifier, and remote CI are green.

## 2026-07-10 - adaptive retrieval checkpoint

Audience: internal Zerker product and engineering.

ZMem now has a measured conservative adaptive route. It lets the store decide when a compound query needs multi-hop expansion and records that activation or suppression in the retrieval proof.

On the local provisional LoCoMo path, adaptive scored `0.6108` versus `0.5967` for FTS and `0.6067` for always-on multi-hop. Against FTS it gained `29` questions and lost `1`, while preserving temporal accuracy and improving open-domain recall. On LongMemEval it scored `0.766` versus `0.740` for FTS, gaining `13` questions with zero losses; always-on multi-hop remains the specialist high-recall result at `0.780`.

Product decision: normal store behavior stays selective. Always-on multi-hop remains explicit rather than becoming a blanket default. Public claims must continue to describe these as verified local provisional results, not official leaderboard rankings or competitor comparisons.

Next build move: inspect adaptive stable misses, choose one bounded multi-hop/open-domain support failure, and reject any change that widens LoCoMo beyond the current one-loss regression boundary. BEAM remains the next scale benchmark after that quality slice.

## 2026-07-10 - v0.1.3 release checkpoint

Audience: internal Zerker product, engineering, and launch coordination.

Final acceptance: published at `d029b99` as `v0.1.3`; GitHub Actions run `29119164360`, Vercel site/docs deployments, and production browser checks passed.

Post-release evidence: a fresh same-commit four-mode LoCoMo matrix completed over `1,986` questions at checkpoint `871f23d`. Both matrix and comparison verification pass. The matrix hash is `9f8b77ca...`; the comparison hash is `18cdca15...`.

`fts-multihop` is the measured winner at accuracy `0.6067` and `425.8` mean query tokens, versus `0.5967` and `536.0` for plain FTS. It gained `98` questions and lost `78`, with a net four-question temporal regression and materially higher latency. The product decision is adaptive routing, not a global multihop default.

Pseudo-embedding and pseudo-rerank match FTS on every scored category. This is useful negative evidence: the next retrieval investment should target query routing and support coverage, not another deterministic reranking layer.

LongMemEval now provides the complementary signal. The verified `500`-question matrix scores multihop at `0.780` versus `0.740` for the other modes, with `20` recovered questions, zero losses, and `30/30` abstention across every mode. Multihop costs `4.0%` more query tokens and higher latency. Combined with LoCoMo's temporal regressions, this selects adaptive routing as the next product slice.

The run also fixed a real operator problem: LongMemEval now honors `--compact-artifacts` with per-session ephemeral stores. The four-mode run completed in `174.84s`, wrote zero databases/bundles, and verified under matrix hash `e5dd8b06...` and comparison hash `a69090df...`. Summary-only output is bounded instead of printing thousands of per-question delta lines.

### What changed

- Agent MCP connections are narrow by default: propose, inject, explain, and verify. Trusted writes and review now require an explicit operator profile.
- Agent proposals cannot spoof human/system provenance.
- Local SQLite stores are private by default and configured for bounded concurrent-agent access through WAL and a busy timeout.
- Daily `inject` and `why` output now has compact human-readable modes.
- The website now leads with “Agent memory you can trust,” explains that promise through persistent local memory, review, revocation, and verification, and keeps proof claims tied to memory influence rather than semantic truth.
- Benchmark docs now show the current local FTS and FTS-multihop results, their tradeoffs, and safe isolated compact-run commands.
- Site and docs builds are now first-class CI checks.
- Docs dependencies and the site's production Lodash chain are patched; runtime dependency audits are clean.
- Receipt bundles now default to v2 compact event witnesses instead of copying the full pre-action event history into every artifact. Legacy v1 bundles still verify.
- A 31-event repeated-action fixture measured 35,453 bytes for v2 versus 963,288 bytes for v1 (96.32% smaller), with both formats verified.

### Claim boundaries

- The MCP profile is a capability boundary, not multi-user authentication. Operators must not attach `--profile operator` to an untrusted agent.
- Local file permissions and OS disk encryption protect storage; ZMem does not yet provide database encryption at rest.
- LoCoMo values are provisional local retrieval-recall evidence with `public_benchmark_claim: false`, not official leaderboard scores.
- Compact bundle witnesses prove that cited write events are included under the receipt Merkle root; they do not prove semantic truth or completeness beyond the committed local log.

### Next build move

Expose and measure the existing selective-multihop path as an explicit adaptive benchmark mode. Acceptance is to retain LongMemEval's `20` recovered questions while reducing LoCoMo's `78` regressions, especially its net four temporal losses. Keep broad swarms and launch oversight paused.

## 2026-07-06 - v0.1.2 release checkpoint

Audience: internal Zerker launch/build coordination.

### What changed

- The paused continuous-swarm harvest is landed on `main` as `91c792f Land continuous swarm hardening`.
- CI is green on Python 3.10, 3.11, and 3.12 plus release-smoke.
- The release includes trust-ledger, temporal, lifecycle, retrieval, consolidation, identity/workspace, dashboard, and release-proof hardening.
- Website positioning now leads with memory AI agents can rely on.
- The homepage explains ZMem as local memory agents can use across runs: ask, propose, review, use, withhold, revoke, verify.
- The copy avoids competing on generic durable context. The sharper line is: agents may find old notes, proposed facts, and conflicting claims; ZMem helps decide what should shape the task.
- L3 retrieval has a verified local candidate slice for update-history relation-pair RRF, promoting explicit stale/current relation pairs over generic high-authority change anchors.
- The shared progress tracker now records lane status, acceptance targets, and what remains before automations can pause.

### Claim boundaries

- Do not claim benchmark wins from this slice until isolated LoCoMo and LongMemEval runs are complete.
- Do not claim semantic truth. ZMem records memory state, lineage, injection, withholding, and influence.
- Do not claim every memory entry is independently Ed25519-signed unless the Treeship path was used for that receipt.
- Do not present ActiveGraph full-trace runs as complete; the compact smoke works, full batching/performance still needs hardening.

### Next external-facing message

ZMem is an open-source, local-first memory system for agents that need to continue across runs. Agents can request scoped memory, propose new facts, hand off state, and produce receipts showing what memory influenced an action.

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
