# ZMem Release Comms

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
