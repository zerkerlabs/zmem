# Benchmark Agent Swarm Brief

Use this brief to run a separate agentic swarm on the ZMem benchmark track without confusing it with the current Phase 1 public-launch proof work.

For the one-mission coordinator brief that combines benchmark harness work with the top-tier retrieval baseline track, start from `docs/BENCHMARK_RETRIEVAL_SWARM_MISSION.md`.

## Current Project Context

ZMem / Zerker Memory is a local-first, verifiable memory runtime for AI agents. The product difference is not just better recall; it is governed recall with provenance, policy gates, receipts, Merkle proof, handoff, and local verification.

Latest orchestration state:

- Current phase: Phase 1 - Public Alpha Launch Gate.
- Phase 1 local packet readiness: ready with warnings.
- Strict publish readiness: blocked.
- Remaining Phase 1 blockers: external clean-shell proof for `https://github.com/zerkerlabs/zmem`, six public-verify logs, and eight launch screenshots/GIFs.
- Do not let benchmark work block, rewrite, or restate the Phase 1 launch-proof flow unless a benchmark change directly touches release-pack, prelaunch, proof, or installability.

The benchmark track is a Phase 2/Phase 3 product wedge. It should be prepared now, but scoped so it can run in parallel with the launch gate.

## Source Docs To Read First

Read these in order:

1. `docs/CURRENT_STATE.md`
2. `docs/BUILD_LOG.md`
3. `docs/BENCHMARK_AND_RETRIEVAL_PLAN.md`
4. `README.md`
5. `docs/MOLTBOOK_ZMEM_PRODUCT_SIGNAL.md`
6. `docs/ZMEM_PROBLEM_MAP_DEEP_DIVE.md`
7. Existing code entry points: `zerker_memory/cli.py`, `zerker_memory/store.py`, `zerker_memory/eval.py`, `zerker_memory/exporter.py`, `zerker_memory/treeship.py`
8. Existing tests: `tests/test_eval.py`, `tests/test_store.py`, `tests/test_exporter.py`, `tests/test_treeship.py`, `tests/test_cli_onboarding.py`

## Swarm Mission

Design and incrementally implement `zmem bench` as a local-first benchmark harness that proves memory quality with receipts.

The harness should answer:

- What did ZMem retrieve?
- What did it inject?
- What did it withhold?
- Why was each memory allowed or withheld?
- What did the model or local judge answer?
- What score resulted?
- Can the run be verified from disk?

Benchmark reports should be useful even when no public account, Hub, or hosted service is available.

## Non-Negotiable Product Principle

Accuracy earns attention. Proof earns trust.

Do not build a benchmark harness that only prints scores. Every benchmark run must preserve enough local evidence to verify what memory influenced the answer.

## Proposed Swarm Roles

### Agent 1: Harness Architect

Owns command shape, run layout, schemas, and CLI integration.

Primary outputs:

- `zmem bench list`
- `zmem bench run <adapter>`
- `zmem bench report <run-dir>`
- `zmem bench verify <result-json>`
- On-disk run layout under `.zerker/bench/<run-id>/`
- JSON schema-ish docs for `benchmark-run.json`, `benchmark-result.json`, per-question files, and receipt references

Guardrail: keep the first implementation small and local. A synthetic built-in benchmark adapter is acceptable before LongMemEval/LoCoMo if it proves the contract.

### Agent 2: Dataset Adapter Agent

Owns benchmark adapters and fixtures.

Primary outputs:

- Adapter interface for benchmark datasets
- A tiny built-in fixture adapter for deterministic tests
- LongMemEval adapter plan or scaffold
- LoCoMo adapter plan or scaffold
- Dataset version/hash capture in run manifests

Guardrail: do not download datasets silently. If network access is required, make the adapter accept a local dataset path and document the expected format.

### Agent 3: Retrieval And Metrics Agent

Owns scoring and retrieval observability.

Primary outputs:

- recall@k where supporting facts are available
- precision@k where supporting facts are available
- abstention correctness
- temporal / knowledge-update correctness fields, even if initially `not_applicable`
- p50/p95/p99 retrieval latency
- end-to-end latency
- retrieved, injected, and withheld memory counts
- token-count placeholders or deterministic local token approximations until model integrations exist

Guardrail: keep metrics deterministic. If an external judge is optional, local verification must still work without it.

### Agent 4: Proof And Report Agent

Owns receipts, aggregate verification, report generation, and optional Treeship handoff.

Primary outputs:

- Per-question receipt or receipt bundle reference
- Benchmark receipt with run ID, dataset hash, adapter version, prompt/config hashes, aggregate result hash, and aggregate Merkle root
- `report.md`
- Optional `report.html`
- `zmem bench verify` that succeeds from local disk without external services
- Future optional `zmem bench publish` path using Treeship

Guardrail: do not publish raw private memory by default. Public proof should expose hashes, receipts, and summaries, not memory content unless explicitly requested.

### Agent 5: QA And Integration Agent

Owns tests and release-safety checks.

Primary outputs:

- Focused unit tests for the bench command family
- Fixture-based end-to-end test for one complete run
- Verification test proving tampered benchmark results fail
- Docs check that the benchmark command examples stay aligned

Required checks after behavior changes:

```bash
python3 -m unittest tests.test_eval -q
python3 -m unittest tests.test_store -q
python3 -m unittest tests.test_exporter -q
python3 -m unittest tests.test_treeship -q
python3 -m zerker_memory eval
```

If `zerker_memory/cli.py`, release-pack, prelaunch, installer, handoff, Treeship, or proof paths change, also run:

```bash
python3 scripts/release_smoke.py --summary-only
python3 -m zerker_memory status --summary-only
```

## First Slice Recommendation

Do not start with hosted datasets or external judges. Start with the smallest local proof-bearing benchmark:

1. Add `zerker_memory/bench.py` with a synthetic fixture adapter.
2. Add `zmem bench list`.
3. Add `zmem bench run synthetic --out .zerker/bench/<run-id>`.
4. Write `benchmark-run.json`, `benchmark-result.json`, `questions/<id>.json`, and `report.md`.
5. Make each synthetic question use the existing store/inject path so retrieved, injected, and withheld memories are real ZMem decisions.
6. Add `zmem bench verify <result-json>` that recomputes hashes and fails on tampering.
7. Add tests proving the run and verify contract.

Success means the swarm can show a fully local, deterministic benchmark report before touching LongMemEval, LoCoMo, embeddings, rerankers, or model judges.

## Expected Run Layout

```text
.zerker/bench/<run-id>/
  benchmark-run.json
  benchmark-result.json
  questions/
    <question-id>.json
  receipts/
    <action-id>.bundle.json
  snapshots/
    before.snapshot.json
    after.snapshot.json
  report.md
  report.html
```

`report.html` is optional in the first slice. `report.md` is required.

## Implementation Boundaries

Allowed first-slice files:

- `zerker_memory/bench.py`
- `zerker_memory/cli.py`
- `tests/test_bench.py`
- `docs/BENCHMARK_AND_RETRIEVAL_PLAN.md`
- `docs/BENCHMARK_AGENT_SWARM_BRIEF.md`

Avoid touching unless strictly necessary:

- Phase 1 launch-proof docs and generated `.zerker/launch-proof/` artifacts
- `install.sh`
- `scripts/release_smoke.py`
- Treeship integration files
- existing dirty files not required for the bench slice

## Reporting Format For The Swarm

Each swarm agent should report:

- What changed
- Files touched
- Verification run and exact result
- Remaining blockers
- Next handoff step
- Any Phase 1 surface touched, or explicit statement that none was touched

The coordinator should consolidate into:

- One benchmark-track summary
- One risk list
- One next slice recommendation
- A note on whether Phase 1 launch proof remains unaffected

## Stop Conditions

Stop and ask the coordinator before:

- Downloading datasets or calling hosted benchmark APIs
- Adding hosted model or judge dependencies
- Publishing benchmark results
- Changing public launch proof, installer, release-pack, or prelaunch behavior
- Rewriting unrelated memory, policy, handoff, or Treeship surfaces

## Copy-Ready Prompt For A New Swarm

```text
You are the Benchmark Swarm for ZMem / Zerker Memory.

Start by reading:
- docs/CURRENT_STATE.md
- docs/BUILD_LOG.md
- docs/BENCHMARK_AND_RETRIEVAL_PLAN.md
- docs/BENCHMARK_AGENT_SWARM_BRIEF.md
- README.md
- zerker_memory/cli.py
- zerker_memory/store.py
- zerker_memory/eval.py
- tests/test_eval.py
- tests/test_store.py

Mission: build the first local proof-bearing `zmem bench` slice without blocking Phase 1 public-launch proof work.

Current Phase 1 state: local release packet is ready, but strict publish is blocked on external clean-shell proof, six public-verify logs, and eight launch assets. Do not touch launch-proof, installer, release-pack, prelaunch, or public repo proof surfaces unless your benchmark work directly requires it.

First target: implement a deterministic synthetic benchmark adapter and command family:
- `zmem bench list`
- `zmem bench run synthetic --out .zerker/bench/<run-id>`
- `zmem bench report .zerker/bench/<run-id>`
- `zmem bench verify .zerker/bench/<run-id>/benchmark-result.json`

The run must write benchmark metadata, per-question records, a report, and enough hashes/receipt references for local verification. Use existing ZMem store/inject/receipt behavior where practical. Keep external datasets, hosted judges, embeddings, rerankers, and publish paths out of the first slice.

After changes, run focused tests and `python3 -m zerker_memory eval`. Report files touched, exact verification results, blockers, next step, and whether any Phase 1 surface was touched.
```
