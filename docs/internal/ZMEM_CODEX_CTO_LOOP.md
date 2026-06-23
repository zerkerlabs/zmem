# ZMem Codex CTO Quality Loop

Last updated: 2026-06-23

This is the executive operating loop for end-to-end ZMem quality. It is not the frontier build swarm and it is not the launch readiness track. It audits the whole product, records pass/fail/blocked status, and prioritizes dangerous gaps.

The mode is CTO-style: high agency, tight scope control, eval-first discipline, no vague "make it better" work, and no product claims without evidence.

## Three Orchestrators

ZMem has three separate operating loops. Keep them distinct:

| Loop | Canonical file | Owns | Does not own |
| --- | --- | --- | --- |
| Frontier Build Orchestrator | `docs/ZMEM_CONTINUOUS_BUILD_ORCHESTRATOR.md` | Active frontier capability work: retrieval, temporal KG, lifecycle, consolidation, identity, benchmarks, and proof ledger | Launch packaging or executive pass/fail audit |
| Launch / Public Readiness | Launch proof, release pack, clean-shell proof, public docs/site/assets, alpha tag docs | Customer-facing readiness: site, docs, release pack, clean-shell proof, launch assets, public copy, alpha tag | Frontier architecture or broad product-quality arbitration |
| CTO Quality Loop | `docs/internal/ZMEM_CODEX_CTO_LOOP.md` and `docs/internal/ZMEM_CODEX_QUALITY_AUDIT.md` | Executive audit: does the whole product work end to end, what is pass/fail/blocked, what is dangerous to ship | Competing feature work or redirecting frontier lanes |

Clean hierarchy:

- Frontier swarm builds.
- Launch readiness packages and publishes.
- CTO loop audits and prioritizes.

The CTO loop may recommend frontier or launch work, but it should not spin up competing feature work unless it finds a P0/P1 issue. Its default output is an updated audit ledger, not a redirected build plan.

## Operating Principle

ZMem quality is not measured by feature count. It is measured by whether an agent can capture, govern, retrieve, explain, transfer, and verify memory without leaking scope, fabricating certainty, losing provenance, or confusing the user.

Every Codex run in this loop must preserve three truths:

- Receipts prove provenance, lineage, integrity, and influence. They do not prove semantic truth.
- Memory correctness is product behavior, not just test coverage.
- Every fix must trace to a documented failing scenario.

## Canonical Artifacts

- Audit ledger: `docs/internal/ZMEM_CODEX_QUALITY_AUDIT.md`
- Lane roadmap: `docs/internal/ZMEM_AGENTIC_ROADMAP.md`
- Lane goal pack: `docs/internal/ZMEM_SWARM_GOALS.md`
- Continuous-build orchestrator: `docs/ZMEM_CONTINUOUS_BUILD_ORCHESTRATOR.md`
- Lane logs: `docs/CONTINUOUS_BUILD/*.log.md`

`docs/internal/ZMEM_CODEX_QUALITY_AUDIT.md` is the source of truth for feature/user-story status during this loop. Lane logs can contain implementation detail, but the audit ledger owns pass/fail/blocker status.

## CTO Loop Prompt

Use this prompt to start or resume the loop:

```text
/goal Run the ZMem Codex CTO quality loop.

Act like the internal Codex product + evals + engineering lead for zmem. Your job is to prove the memory system works end to end, document gaps honestly, and fix only test-backed or audit-backed failures.

Read first:
- docs/internal/ZMEM_CODEX_CTO_LOOP.md
- docs/internal/ZMEM_CODEX_QUALITY_AUDIT.md
- docs/internal/ZMEM_AGENTIC_ROADMAP.md
- docs/ZMEM_CONTINUOUS_BUILD_ORCHESTRATOR.md
- git status --short --branch

Maintain docs/internal/ZMEM_CODEX_QUALITY_AUDIT.md as the canonical status ledger.

Work in phases:
1. Inventory every discoverable ZMem capability and map it to a user story, expected behavior, lifecycle stage, scope model, entry point, source files, and current status.
2. Convert each story into an eval or manual verification scenario with setup, inputs, expected output, observed output, and failure signal.
3. Run baseline verification before fixing. Document pass, fail, or blocked with exact evidence.
4. Triage failures by severity:
   - P0: data loss, cross-user/project leakage, destructive behavior, security/privacy risk
   - P1: wrong retrieval, broken persistence, corrupted summaries, unusable core workflow
   - P2: confusing UX/API, bad ranking edge case, incomplete behavior
   - P3: polish, docs, minor ergonomics
5. Fix P0/P1 first. Fix P2 only when scoped and directly supported by the audit. Do not spend time on P3 until higher-priority work is clean.
6. Retest every fixed story and adjacent memory lifecycle behavior. Update the audit ledger.
7. End with an internal readout: audited surface, pass/fail counts, fixes landed, blockers, product ambiguities, and next evals.

Constraints:
- Treat this as an executive audit loop, not a frontier build swarm.
- Update the audit ledger before redirecting any lane work.
- Do not spin up feature work unless the audit finds a P0/P1 or the user explicitly asks for implementation.
- Recommend frontier work back to the Frontier Build Orchestrator instead of owning it here.
- Recommend public-readiness work back to the launch track instead of owning it here.
- Do not refactor unrelated code.
- Do not invent requirements when code/docs/tests disagree; record a product ambiguity.
- Do not edit files already dirty from another lane unless this loop explicitly owns the integration.
- Do not make public benchmark or product claims unless backed by reproducible commands and artifacts.
- Do not claim receipts prove truth.
- Prefer focused tests over broad rewrites.
- Every code change must link back to a failing audit row.

Success criteria:
- Every discoverable capability has a user story and expected behavior entry.
- Every testable story has observed results.
- Every fix traces to a documented failing eval.
- Available tests/build/lint pass, or failures are documented with exact causes.
- Remaining ambiguity is captured as product questions, not silently resolved.
```

## Phase Gates

| Phase | Gate | Evidence required |
| --- | --- | --- |
| 0. Orientation | Current repo state understood | `git status --short --branch`, current roadmap/orchestrator read, dirty overlap noted |
| 1. Inventory | Product surface mapped | Audit rows for CLI, MCP, store, policy, retrieval, receipts, snapshots, workspaces, dashboard, handoff, benchmarks, provider governance |
| 2. Eval design | Behavior is testable | Test/manual scenario for each non-blocked row |
| 3. Baseline | Failures are real before fixes | Observed output, command, artifact path, or blocker reason |
| 4. Triage | Work is prioritized | P0-P3 severity, owner role, and next action |
| 5. Fix | Changes are surgical | Failing row id in fix notes, focused tests added/updated |
| 6. Retest | Regressions checked | Retest status and adjacent-flow verification |
| 7. Readout | Leadership can act | Summary of what is shippable, blocked, ambiguous, and next |

## Memory Correctness Invariants

These are non-negotiable eval themes. If a capability touches one of these and lacks a test or manual verification path, mark it as an audit gap.

1. Retrieval prefers relevant scoped memories over globally similar unrelated memories.
2. Memories from another user, project, workspace, thread, session, or agent source do not appear unless explicitly allowed.
3. Retrieved memory and injected memory are different decisions, and the receipt explains both.
4. Summaries preserve decisions, constraints, preferences, and open tasks without fabricating facts.
5. Deduplication does not merge distinct facts that only look similar.
6. Updates preserve provenance and prior state where the system supports it.
7. Deletion, revocation, rejection, quarantine, and forgetting are observable and testable.
8. Persistence survives process restart and handoff/restore flows.
9. Benchmark evidence separates local reproducible proof from public claims.
10. Product ambiguity is documented before implementation changes.

## Capability Map

The first full loop should cover these surfaces at minimum:

| Area | Capabilities to audit |
| --- | --- |
| Capture | `add`, agent proposals, provider imports, behavior-tree trace ingest |
| Govern | quarantine, promote, reject, revoke, authority, trust, policy gates |
| Retrieve | search, query, FTS/BM25 fallback, temporal/history retrieval, context packing |
| Explain | `why`, action receipts, injected/withheld/budget-dropped decisions |
| Persist | SQLite store, events, Merkle roots, snapshots, restore |
| Transfer | handoff, agent pack, MCP config, workspace registry |
| Scope | user/project/workspace/thread/session/source identity |
| Consolidate | dedupe, summaries, source-child lineage, consolidation fixtures |
| Verify | receipt bundles, Treeship integration, proof export, release smoke |
| Benchmark | synthetic, LongMemEval-style, LoCoMo-style, matrix comparison, artifact hashes |
| UX | CLI errors, dashboard actions, onboarding, quickstart, docs consistency |

## Severity Rubric

| Severity | Definition | Default action |
| --- | --- | --- |
| P0 | Memory leak across trust/scope boundaries, data loss, destructive action, security/privacy risk | Stop lane widening, write focused repro, fix immediately |
| P1 | Core memory behavior wrong or unusable: bad retrieval, broken persistence, corrupted summary, invalid proof chain | Fix before P2/P3 work |
| P2 | Important UX/API or edge-case quality issue with bounded blast radius | Fix if small and audit-backed |
| P3 | Polish, docs, low-risk ergonomics | Backlog unless higher priorities are clean |

## Owner Roles

Use these owner roles in the audit ledger:

- Product: expected behavior, ambiguity, public claim boundary.
- Evals: test scenario, fixture design, benchmark evidence.
- Engineering: implementation, regression tests, runtime correctness.
- UX: CLI/dashboard/onboarding clarity.
- Security: trust, scope, privacy, destructive behavior.

## CTO Readout Template

End every full loop or substantial resume with:

```text
ZMem Codex CTO Readout

Scope audited:
Pass:
Fail:
Fixed:
Retest pass:
Blocked:
Top P0/P1 risks:
Product ambiguities:
Evidence commands:
Artifacts updated:
Next evals:
Next engineering slices:
```

## Stop Conditions

Stop and record a blocker instead of improvising when:

- Required behavior contradicts code, docs, and tests.
- A fix requires schema migration without a focused migration plan.
- A public claim needs unavailable external evidence.
- The relevant files are dirty from another lane and ownership is unclear.
- Verification requires credentials or network access that are unavailable.

## First CTO Pass

The first pass should be documentation and eval-heavy:

1. Fill the audit ledger with a complete capability inventory.
2. Mark each row as `untested`, `pass`, `fail`, or `blocked`.
3. Add focused tests only for high-risk missing contracts.
4. Fix only P0/P1 failures found during baseline.
5. Leave P2/P3 items as audit-backed backlog unless they are tiny and isolated.
