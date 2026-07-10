# ZMem Release Comms

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
