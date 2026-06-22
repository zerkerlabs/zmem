# Benchmark And Retrieval Swarm Mission

This is the single mission brief for a Codex agent swarm working on ZMem's benchmark harness and top-tier retrieval baseline.

## One Mission

Make ZMem the best memory product for AI agents: frontier-grade on benchmarks and real-world recall quality, while uniquely trustworthy through local-first proof-backed memory influence.

Privacy, portability, trust, and verification are the wedge and must be designed intelligently on their own. They are not a substitute for retrieval quality. ZMem also needs to compete directly on accuracy, latency, token efficiency, temporal reasoning, update/conflict handling, abstention, multi-hop recall, and context packing.

ZMem should not claim public benchmark superiority until claims are verified against primary sources and reproducible local runs. The swarm goal is to build toward genuine top-tier performance: first the local proof-bearing benchmark foundation, then retrieval upgrades that can honestly compete on LongMemEval / LoCoMo-style tasks and real agent workflows.

## North Star

ZMem should become:

- the most trustworthy memory product, because every influential memory can be inspected, governed, verified, and ported;
- a top-ranking memory product, because retrieval quality, temporal correctness, abstention, latency, and token efficiency are genuinely strong;
- the best product experience, because agents and builders can install it, run it, benchmark it, explain it, and carry it across tools without ceremony.

The proof layer is the wedge. The memory quality must still be excellent.

## Current Launch Context

Current project phase is still `Phase 1 - Public Alpha Launch Gate`.

Known Phase 1 state:

- Local release packet is ready with warnings.
- Strict publish is blocked.
- External clean-shell proof is still missing for `https://github.com/zerkerlabs/zmem`.
- Public verify evidence is `0/6` logs.
- Launch assets are `0/8`.

Swarm rule: do not touch Phase 1 launch-proof, installer, release-pack, prelaunch, public repo proof, or generated `.zerker/launch-proof/` artifacts unless explicitly assigned by the coordinator.

## Read First

All swarm agents should start with:

1. `docs/CURRENT_STATE.md`
2. `docs/BUILD_LOG.md`
3. `docs/BENCHMARK_AND_RETRIEVAL_PLAN.md`
4. `docs/BENCHMARK_AGENT_SWARM_BRIEF.md`
5. `docs/BENCHMARK_RETRIEVAL_SWARM_MISSION.md`
6. `README.md`

Benchmark implementation agents should also read:

- `zerker_memory/cli.py`
- `zerker_memory/store.py`
- `zerker_memory/eval.py`
- `zerker_memory/exporter.py`
- `tests/test_eval.py`
- `tests/test_store.py`
- `tests/test_exporter.py`

Retrieval baseline agents should also read:

- `zerker_memory/store.py`
- `zerker_memory/policy.py`
- `zerker_memory/runner.py`
- `zerker_memory/cli.py`
- `tests/test_store.py`
- `tests/test_policy.py`
- `tests/test_runner.py`

## Product Direction To Preserve

Keep:

- ZMem competes to become frontier-grade on accuracy, latency, token efficiency, temporal reasoning, abstention, and multi-hop memory quality.
- ZMem's unique wedge is proof-backed, reproducible memory influence.
- Benchmark outputs should include receipts, Merkle roots, and optional Treeship proof URLs.
- LoCoMo and LongMemEval-style evals are important references.
- Temporal reasoning, contradiction/update handling, abstention, token cost, and latency matter.
- Benchmark theater is a risk; ZMem should win credibility through reproducible signed runs.

Soften until verified:

- Do not publicly claim any benchmark is canonical without primary-source verification.
- Do not repeat leaderboard numbers or vendor claims unless reproduced or cited from primary sources.
- Treat numeric targets such as `>85% LongMemEval` or `>90% LoCoMo` as internal ambition, not public fact.
- Treat BEAM, AMB, STATE-Bench, or any secondary benchmark names as research candidates until verified.

Strategic line:

> ZMem does not need to be only the highest-recall memory system on day one. It needs to be the most trustworthy memory system: local-first, easy to use, benchmarkable, reproducible, and able to prove what memory influenced an agent action. Then it should use that harness to become top-tier on recall quality too.

## Track A: Benchmark Harness

First implementation slice:

1. Add a deterministic synthetic benchmark adapter.
2. Add `zmem bench list`.
3. Add `zmem bench run synthetic --out .zerker/bench/<run-id>`.
4. Add `zmem bench report .zerker/bench/<run-id>`.
5. Add `zmem bench verify .zerker/bench/<run-id>/benchmark-result.json`.
6. Write benchmark metadata, per-question records, local hashes, receipt references, and `report.md`.
7. Make local verification fail on tampering.

Out of scope for the first slice:

- hosted judges
- automatic dataset downloads
- embeddings
- rerankers
- public benchmark publication
- Treeship publish integration beyond schema placeholders

## Track B: Top-Tier Retrieval Baseline

Goal: design and ship the retrieval stack ZMem needs to rank high while staying auditable.

Retrieval capabilities to plan and sequence:

- stronger SQLite FTS / BM25 baseline
- hybrid FTS + embeddings
- reranking
- temporal query expansion
- multi-hop query decomposition
- update/conflict handling
- context packing budget
- citations in injected context
- retrieval receipts that explain retrieved, injected, withheld, and budget-dropped memories

The retrieval track should move from design to implementation as soon as the first no-migration slice is clear. Each slice should improve measurable quality and preserve receipt explainability.

## Swarm Roles

### Agent 1: Benchmark Harness Explorer

Read-only. Map the current CLI/store/eval/exporter hooks and recommend the minimal `zmem bench synthetic` integration path.

Output:

- files/functions to use
- proposed command dispatch shape
- proposed run JSON fields
- tests to add
- risks and unknowns

### Agent 2: Retrieval Baseline Explorer

Read-only. Map current retrieval behavior and propose the first top-tier baseline slice.

Output:

- current search/inject path
- existing FTS/fallback behavior
- where BM25/field boosts/context packing would fit
- schema changes needed, if any
- recommended first implementation slice
- tests to add

### Agent 3: Benchmark Proof Worker

Implementation worker. Own only benchmark-harness files if activated by the coordinator.

Allowed write set:

- `zerker_memory/bench.py`
- `zerker_memory/cli.py`
- `tests/test_bench.py`
- benchmark docs if needed

Do not touch Phase 1 launch files.

### Agent 4: Retrieval Plan Worker

Documentation/design worker. Own retrieval baseline planning only unless the coordinator promotes it to implementation.

Allowed write set:

- `docs/BENCHMARK_AND_RETRIEVAL_PLAN.md`
- a new retrieval design doc if needed
- tests only if making implementation changes later

Do not touch Phase 1 launch files.

## Verification Expectations

For docs-only work:

```bash
git diff -- docs/BENCHMARK_AND_RETRIEVAL_PLAN.md docs/BENCHMARK_AGENT_SWARM_BRIEF.md docs/BENCHMARK_RETRIEVAL_SWARM_MISSION.md
```

For benchmark or retrieval behavior changes:

```bash
python3 -m unittest tests.test_eval -q
python3 -m unittest tests.test_store -q
python3 -m unittest tests.test_exporter -q
python3 -m zerker_memory eval
```

If CLI, proof, launch, handoff, Treeship, prelaunch, or release-pack behavior changes:

```bash
python3 scripts/release_smoke.py --summary-only
python3 -m zerker_memory status --summary-only
```

## Coordinator Rules

- Keep one mission, two tracks.
- Do not let agents duplicate each other's work.
- Keep the critical path local in the coordinator thread.
- Integrate explorer output before activating broad implementation.
- Prefer synthetic local benchmark proof before external benchmark adapters.
- Prefer FTS/BM25/context-packing clarity before embeddings/reranking.
- Keep public claims conservative until primary sources are verified.

## Copy-Ready Coordinator Prompt

```text
You are joining the ZMem Benchmark And Retrieval Swarm.

Mission: make ZMem the best memory product for AI agents: frontier-grade on benchmark and real-world recall quality, with proof-backed memory influence as the wedge.

Read first:
- docs/CURRENT_STATE.md
- docs/BUILD_LOG.md
- docs/BENCHMARK_AND_RETRIEVAL_PLAN.md
- docs/BENCHMARK_AGENT_SWARM_BRIEF.md
- docs/BENCHMARK_RETRIEVAL_SWARM_MISSION.md
- README.md

Current Phase 1 launch state: local packet ready with warnings, strict publish blocked, public verify logs 0/6, launch assets 0/8. Do not touch launch-proof, installer, release-pack, prelaunch, public repo proof, or generated `.zerker/launch-proof/` artifacts.

Work on one assigned role only. Report files read, files changed, exact verification run, risks, and next handoff. If making public benchmark claims, verify primary sources first; otherwise frame claims as internal targets or research candidates.
```
