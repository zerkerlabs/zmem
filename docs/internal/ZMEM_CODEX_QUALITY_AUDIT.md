# ZMem Codex Quality Audit

Last updated: 2026-06-22

Canonical ledger for the ZMem Codex CTO quality loop. Keep this file factual and current. Do not use it as a wish list; every row should describe behavior that exists, is expected by docs/tests/code, or is explicitly blocked/ambiguous.

## Status Legend

| Status | Meaning |
| --- | --- |
| untested | Expected behavior is documented, but no baseline has run |
| pass | Baseline verification passed |
| fail | Baseline verification failed and needs triage |
| fixed | A fix landed but retest is pending |
| retest pass | Fixed behavior passed retest and adjacent checks |
| blocked | Verification or implementation is blocked with a concrete reason |

## Audit Rules

- One row per user-facing or agent-facing capability.
- Expected behavior must be inferred from code, docs, or tests.
- If code, docs, and tests disagree, record an ambiguity instead of picking silently.
- Every failure needs a failure signal.
- Every fix needs a linked audit id.
- Every benchmark or product-quality claim needs a command and artifact path.

## Capability Ledger

| ID | Capability | User story | Lifecycle stage | Scope model | Entry points | Source files | Expected behavior | Test method | Observed behavior | Status | Severity | Owner | Issue/fix notes | Product ambiguity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ZQA-001 | Local memory add | As an agent, I can add memory locally so future runs can recall it with provenance. | capture, store | workspace, source, memory type | CLI, Python store, MCP | `zerker_memory/cli.py`, `zerker_memory/store.py`, `zerker_memory/mcp.py` | Added memories persist in SQLite, create events, carry type/status/scope metadata, and are searchable according to policy. | TBD | TBD | untested | TBD | Engineering | Initial inventory placeholder. | None recorded. |
| ZQA-002 | Quarantine and review | As a user, I can keep proposed/imported memory inactive until review. | govern | trust, authority, source | CLI, dashboard, provider imports | `zerker_memory/store.py`, `zerker_memory/policy.py`, `zerker_memory/dashboard.py`, `zerker_memory/providers.py` | Untrusted/imported memory is withheld from action influence until promoted or otherwise authorized. | TBD | TBD | untested | TBD | Security | Initial inventory placeholder. | None recorded. |
| ZQA-003 | Promote/reject/revoke | As a user, I can promote useful memory and reject or revoke bad memory with traceable effects. | update, delete, govern | memory id, lineage, trust | CLI, dashboard, store API | `zerker_memory/store.py`, `zerker_memory/cli.py`, `zerker_memory/dashboard.py` | State transitions emit durable events/receipts, preserve lineage, and affect retrieval/injection as documented. | TBD | TBD | untested | TBD | Engineering | Initial inventory placeholder. | None recorded. |
| ZQA-004 | Retrieval and search | As an agent, I can retrieve relevant scoped memories for a task without receiving unrelated memory. | retrieve, rank | workspace, labels, trust, authority, task risk | CLI, runner, store API, MCP | `zerker_memory/store.py`, `zerker_memory/runner.py`, `zerker_memory/retrieval_providers.py`, `zerker_memory/mcp.py` | Retrieval uses local search paths, ranks relevant candidates, separates retrieved from injected, and records withheld/budget-dropped decisions. | TBD | TBD | untested | TBD | Evals | Initial inventory placeholder. | None recorded. |
| ZQA-005 | Temporal/history queries | As an agent, I can distinguish current, historical, superseded, and point-in-time memory. | retrieve, rank, update | timestamp, parent lineage, identity | Store API, runner, eval | `zerker_memory/store.py`, `tests/test_store.py`, `tests/test_runner.py` | Temporal projection preserves current-vs-history behavior and does not collapse unrelated identities. | TBD | TBD | untested | TBD | Evals | Initial inventory placeholder. | None recorded. |
| ZQA-006 | Policy-gated injection | As an agent, I only receive memory that is allowed for the task risk and authority context. | govern, retrieve | status, trust, authority, labels, task risk | Runner, MCP, CLI | `zerker_memory/policy.py`, `zerker_memory/runner.py`, `zerker_memory/store.py` | Candidate memories are filtered through symbolic policy before influencing action. | TBD | TBD | untested | TBD | Security | Initial inventory placeholder. | None recorded. |
| ZQA-007 | Why/explainability | As a user, I can inspect why memory was or was not used. | explain, verify | action id, memory ids, policy decision | CLI, dashboard | `zerker_memory/cli.py`, `zerker_memory/dashboard.py`, `zerker_memory/store.py` | Explanations show injected, withheld, and relevant receipt-visible decisions without claiming semantic truth. | TBD | TBD | untested | TBD | UX | Initial inventory placeholder. | None recorded. |
| ZQA-008 | Receipts and Merkle lineage | As a user/team, I can verify what memory influenced an action and how memory state changed. | verify, store, update | event log, receipt chain, memory id | CLI, store API, Treeship/export | `zerker_memory/store.py`, `zerker_memory/treeship.py`, `zerker_memory/exporter.py` | Receipts prove provenance, mutation lineage, integrity, and influence; they do not assert truth. | TBD | TBD | untested | TBD | Security | Initial inventory placeholder. | None recorded. |
| ZQA-009 | Snapshot/restore/handoff | As a user, I can transfer or restore governed memory state across machines or agents. | sync, persist, verify | workspace, agent, snapshot root | CLI, agent pack, exporter | `zerker_memory/cli.py`, `zerker_memory/exporter.py`, `zerker_memory/workspaces.py` | Handoff artifacts preserve memory, policy, proof lineage, and enough metadata to restore/verify state. | TBD | TBD | untested | TBD | Engineering | Initial inventory placeholder. | None recorded. |
| ZQA-010 | Workspace/source identity | As a multi-agent user, I can see which agent/session/workspace produced memory. | scope, sync, verify | agent id, chat/session id, workspace id, source URI | CLI, workspace registry, dashboard | `zerker_memory/workspaces.py`, `zerker_memory/cli.py`, `zerker_memory/dashboard.py` | Source identity is visible and prevents silent cross-workspace confusion. | TBD | TBD | untested | TBD | Product | Initial inventory placeholder. | None recorded. |
| ZQA-011 | Consolidation/dedupe | As a long-running agent, I can compress or dedupe memory without losing reversibility or provenance. | summarize, update | source-child lineage, summary id | Consolidation module, tests | `zerker_memory/consolidation.py`, `tests/test_consolidation.py` | Consolidation keeps source child ids and avoids irreversible lossy replacement. | TBD | TBD | untested | TBD | Evals | Initial inventory placeholder. | None recorded. |
| ZQA-012 | Provider governance | As a builder, I can use external memory providers as candidate recall without bypassing ZMem governance. | capture, govern, retrieve | provider, source, trust status | Provider config/imports | `zerker_memory/providers.py`, `zerker_memory/retrieval_providers.py`, `templates/policy.example.json` | External candidates are quarantined or governed before action influence. | TBD | TBD | untested | TBD | Security | Initial inventory placeholder. | None recorded. |
| ZQA-013 | MCP integration | As an agent client, I can connect to ZMem through MCP and use memory safely. | capture, retrieve, explain | client, workspace, source | MCP server, examples, agent setup | `zerker_memory/mcp.py`, `zerker_memory/mcp_smoke.py`, `examples/mcp_smoke.py`, `AGENT_INTEGRATION.md` | MCP exposes memory operations consistent with CLI/store policy and proof behavior. | TBD | TBD | untested | TBD | Engineering | Initial inventory placeholder. | None recorded. |
| ZQA-014 | CLI onboarding/status/doctor | As a user, I can install, inspect readiness, and diagnose issues from the CLI. | UX, verify | local workspace, agent config | CLI, installer, doctor | `zerker_memory/cli.py`, `zerker_memory/doctor.py`, `install.sh`, `tests/test_cli_onboarding.py`, `tests/test_doctor.py` | First-run commands produce clear setup state and actionable errors. | TBD | TBD | untested | TBD | UX | Initial inventory placeholder. | None recorded. |
| ZQA-015 | Dashboard review console | As a user, I can inspect and act on memory state through the local console. | govern, explain, verify | memory id, action id, launch proof | Dashboard | `zerker_memory/dashboard.py`, `tests/test_dashboard.py` | Dashboard actions align with CLI/store behavior and do not obscure trust/proof boundaries. | TBD | TBD | untested | TBD | UX | Initial inventory placeholder. | None recorded. |
| ZQA-016 | Benchmark evidence | As a builder, I can reproduce local benchmark evidence without overclaiming. | benchmark, verify | dataset, run id, artifact hash | CLI bench, scripts, docs | `zerker_memory/bench.py`, `scripts/bench/**`, `tests/test_bench.py`, `tests/test_bench_scripts.py`, `docs/BENCHMARK_*` | Benchmark commands produce auditable artifacts, hashes, and claim boundaries. | TBD | TBD | untested | TBD | Evals | Initial inventory placeholder. | None recorded. |

## Memory Correctness Matrix

| Invariant | Related audit IDs | Current evidence | Gap |
| --- | --- | --- | --- |
| Relevant scoped retrieval beats unrelated global similarity | ZQA-004, ZQA-010 | TBD | TBD |
| Cross-user/project/workspace/thread/session leakage is prevented | ZQA-004, ZQA-006, ZQA-010 | TBD | TBD |
| Retrieved vs injected decisions are separate and receipt-visible | ZQA-004, ZQA-006, ZQA-007, ZQA-008 | TBD | TBD |
| Summaries preserve facts without fabrication | ZQA-011 | TBD | TBD |
| Dedupe avoids merging distinct facts | ZQA-011 | TBD | TBD |
| Updates preserve provenance and prior state | ZQA-003, ZQA-008 | TBD | TBD |
| Forgetting/revocation is observable | ZQA-003, ZQA-008 | TBD | TBD |
| Persistence survives restart and handoff/restore | ZQA-001, ZQA-009 | TBD | TBD |
| Benchmark claims are reproducible before public use | ZQA-016 | TBD | TBD |

## Baseline Run Log

Add newest entries at the top.

| Date/time | Operator | Scope | Commands/artifacts | Result | Notes |
| --- | --- | --- | --- | --- | --- |
| 2026-06-22 | Codex | Set up CTO quality loop artifacts | Created `docs/internal/ZMEM_CODEX_CTO_LOOP.md` and this audit ledger | setup | No behavioral verification run yet; first full loop should fill TBD fields. |

## Open Product Questions

| ID | Question | Related audit IDs | Owner | Status |
| --- | --- | --- | --- | --- |
| ZPQ-001 | Which scope boundaries are guaranteed today versus planned: user, project, workspace, thread, session, agent source? | ZQA-004, ZQA-006, ZQA-010 | Product | open |
| ZPQ-002 | Which deletion/forgetting semantics are product guarantees versus revocation/withholding semantics? | ZQA-003, ZQA-008 | Product, Security | open |
| ZPQ-003 | Which benchmark artifacts are allowed to support public copy before official dataset runs are pinned? | ZQA-016 | Product, Evals | open |

## CTO Readout Scratchpad

Use this after the first full pass:

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

