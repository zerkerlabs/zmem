# ZMem Release Comms

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
- The website now leads with “Agents remember. You stay in control,” removes internal roadmap material from the homepage, and keeps proof claims tied to memory influence rather than semantic truth.
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
