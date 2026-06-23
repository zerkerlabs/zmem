# ZMem Codex Quality Audit

Last updated: 2026-06-23

Canonical ledger for the ZMem Codex CTO quality loop. Keep this file factual and current. Do not use it as a wish list; every row should describe behavior that exists, is expected by docs/tests/code, or is explicitly blocked/ambiguous.

## Current CTO Readout

Scope audited: repo-local ZMem product behavior across capture, governance, retrieval, policy, receipts, handoff, workspaces, consolidation, providers, MCP, CLI, dashboard, behavior-tree memory, and benchmark evidence.

Pass: 16 capability rows.

Fail: 0 capability rows.

Fixed: 0 in this pass.

Retest pass: not applicable; no fixes were required.

Blocked: strict public publish remains blocked by external clean-shell public verify logs and launch assets, not by core memory behavior.

Top P0/P1 risks: none found in this baseline.

Product ambiguities: scope guarantee granularity, deletion versus revocation semantics, and public benchmark claim boundary remain open questions.

Evidence commands:

- `python3 -m unittest discover -s tests -q` passed, `Ran 641 tests in 277.273s`.
- `python3 -m zerker_memory eval` passed `11/11`.
- `python3 -m zerker_memory status --summary-only` reported workspace ready, doctor ok, memory proof ready, release packet ready, manual pack ready, and strict publish blocked only on `launch_assets` plus `public_verify_evidence`.
- `python3 -m unittest tests.test_policy tests.test_mcp tests.test_snapshot tests.test_workspaces tests.test_consolidation tests.test_retrieval_providers tests.test_adapters tests.test_doctor tests.test_exporter -q` passed, `Ran 72 tests`.
- `python3 -m zerker_memory --help` confirmed the expected CLI surfaces are registered.
- `python3 -m zerker_memory bench --help` confirmed benchmark artifact commands are registered.
- `python3 -m zerker_memory cto-smoke` passed `6/6` fast CTO checks covering all seeded audit rows.
- `python3 -m unittest tests.test_store.MemoryStoreTest.test_scope_search_inject_isolates_project_thread_and_session_values tests.test_store.MemoryStoreTest.test_forget_hides_memory_without_deleting_audit_event -q` passed.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` reported `Ready: yes`.
- `python3 -m zerker_memory verify-public-verify --summary-only` reported `Ready: no`, `0/6` logs captured.
- `python3 -m zerker_memory verify-launch-assets --summary-only` reported `Ready: no`, `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reported `Ready: no` because public verify logs and launch assets are missing.
- `python3 -m zerker_memory prelaunch --summary-only` reported blockers only on `launch_assets` and `public_verify_evidence`.
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py --summary-only` passed after rerun; it confirms the operator packet is ready and the only publish blockers are still external evidence.

Artifacts updated:

- `docs/internal/ZMEM_CODEX_QUALITY_AUDIT.md`
- `docs/internal/ZMEM_LIFECYCLE_SEMANTICS.md`

Next evals:

- Keep `python3 -m zerker_memory cto-smoke` green as the fast one-command health gate for all seeded audit rows.
- Extend the new scope-leak fixture beyond exact scope strings if/when user/project/workspace/thread/session become separate first-class fields.
- Close the lifecycle proof gap by adding mutation receipts for `revoke()` and `forget()`.
- Add a public-claim fixture that verifies benchmark pages cannot claim official rankings without pinned artifacts.

Next engineering slices:

- No P0/P1 fix is required from this baseline.
- Route frontier capability work back to `docs/ZMEM_CONTINUOUS_BUILD_ORCHESTRATOR.md`; the CTO loop should only audit and prioritize unless a P0/P1 appears.
- Route clean-shell proof, launch assets, public copy, and alpha-tag work back to the launch/public-readiness track.
- External launch evidence still requires a networked clean shell and screenshot/GIF capture pass; local verification cannot honestly complete it.

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
| ZQA-001 | Local memory add | As an agent, I can add memory locally so future runs can recall it with provenance. | capture, store | workspace, source, memory type | CLI, Python store, MCP | `zerker_memory/cli.py`, `zerker_memory/store.py`, `zerker_memory/mcp.py` | Added memories persist in SQLite, create events, carry type/status/scope metadata, and are searchable according to policy. | Full suite plus eval: `tests.test_store`, `tests.test_mcp`, `python3 -m zerker_memory eval`. | Full suite passed; eval scenario created and used governed memories. | pass | none | Engineering | No fix required. | None recorded. |
| ZQA-002 | Quarantine and review | As a user, I can keep proposed/imported memory inactive until review. | govern | trust, authority, source | CLI, dashboard, provider imports | `zerker_memory/store.py`, `zerker_memory/policy.py`, `zerker_memory/dashboard.py`, `zerker_memory/providers.py` | Untrusted/imported memory is withheld from action influence until promoted or otherwise authorized. | `tests.test_policy`, `tests.test_adapters`, `tests.test_mcp`, eval review queue and provider quarantine scenarios. | Focused suite passed; eval reported poisoned memory withheld, review queue, and provider candidate quarantined. | pass | none | Security | No fix required. | None recorded. |
| ZQA-003 | Promote/reject/revoke/forget | As a user, I can promote useful memory and reject, revoke, or forget bad memory with traceable effects. | update, delete, govern | memory id, lineage, trust | CLI, dashboard, store API | `zerker_memory/store.py`, `zerker_memory/cli.py`, `zerker_memory/dashboard.py`, `docs/internal/ZMEM_LIFECYCLE_SEMANTICS.md` | State transitions emit durable events and, where currently implemented, ordered mutation receipts; affected memory is excluded from normal influence. | Full suite plus `tests.test_snapshot`, `tests.test_mcp`, eval revocation scenario, `tests.test_store.MemoryStoreTest.test_forget_hides_memory_without_deleting_audit_event`, `python3 -m zerker_memory cto-smoke`. | Full suite passed; eval reported revoked source and descendant; snapshot tests cover promote mutation receipts; CTO smoke and focused store test cover forget hiding plus audit event. | pass | none | Engineering | No code fix required. `revoke()` and `forget()` mutation receipts remain a documented trust-ledger gap. | `forget` is logical forgetting, not physical deletion or cryptographic erasure. |
| ZQA-004 | Retrieval and search | As an agent, I can retrieve relevant scoped memories for a task without receiving unrelated memory. | retrieve, rank | workspace, labels, trust, authority, task risk | CLI, runner, store API, MCP | `zerker_memory/store.py`, `zerker_memory/runner.py`, `zerker_memory/retrieval_providers.py`, `zerker_memory/mcp.py` | Retrieval uses local search paths, ranks relevant candidates, separates retrieved from injected, and records withheld/budget-dropped decisions. | Full suite plus `tests.test_store`, `tests.test_runner`, `python3 -m zerker_memory eval`, `tests.test_store.MemoryStoreTest.test_scope_search_inject_isolates_project_thread_and_session_values`. | Full suite passed; runner/store suites cover current, history, chronology, conflict, alias, decoy, and budget behavior; focused scope fixture proves exact project/thread/session-style scope isolation plus intentional `global` visibility. | pass | none | Evals | No fix required. | Scope boundaries are still encoded as strings rather than first-class user/project/thread/session fields. |
| ZQA-005 | Temporal/history queries | As an agent, I can distinguish current, historical, superseded, and point-in-time memory. | retrieve, rank, update | timestamp, parent lineage, identity | Store API, runner, eval | `zerker_memory/store.py`, `tests/test_store.py`, `tests/test_runner.py` | Temporal projection preserves current-vs-history behavior and does not collapse unrelated identities. | Full suite plus temporal store/runner tests in `tests.test_store` and `tests.test_runner`. | Full suite passed; query-at and Alice/Alice Chen identity-disambiguation tests are covered. | pass | none | Evals | No fix required. | Whether `inject` and `why` should surface derived temporal envelopes remains a roadmap question. |
| ZQA-006 | Policy-gated injection | As an agent, I only receive memory that is allowed for the task risk and authority context. | govern, retrieve | status, trust, authority, labels, task risk | Runner, MCP, CLI | `zerker_memory/policy.py`, `zerker_memory/runner.py`, `zerker_memory/store.py` | Candidate memories are filtered through symbolic policy before influencing action. | `tests.test_policy`, `tests.test_runner`, `tests.test_store`, eval policy scenarios. | Focused suite passed; eval reported authorized policy injection and quarantined policy withholding. | pass | none | Security | No fix required. | None recorded. |
| ZQA-007 | Why/explainability | As a user, I can inspect why memory was or was not used. | explain, verify | action id, memory ids, policy decision | CLI, dashboard | `zerker_memory/cli.py`, `zerker_memory/dashboard.py`, `zerker_memory/store.py` | Explanations show injected, withheld, and relevant receipt-visible decisions without claiming semantic truth. | Full suite plus eval, CLI help, dashboard tests. | Full suite passed; eval action receipts include injected/withheld memory and `why` next-step coverage. | pass | none | UX | No fix required. | None recorded. |
| ZQA-008 | Receipts and Merkle lineage | As a user/team, I can verify what memory influenced an action and how memory state changed. | verify, store, update | event log, receipt chain, memory id | CLI, store API, Treeship/export | `zerker_memory/store.py`, `zerker_memory/treeship.py`, `zerker_memory/exporter.py` | Receipts prove provenance, mutation lineage, integrity, and influence; they do not assert truth. | `tests.test_snapshot`, `tests.test_exporter`, `tests.test_treeship`, eval Treeship export. | Focused suite passed; eval exported Treeship proof statement; status reported memory proof ready. | pass | none | Security | No fix required. | None recorded. |
| ZQA-009 | Snapshot/restore/handoff | As a user, I can transfer or restore governed memory state across machines or agents. | sync, persist, verify | workspace, agent, snapshot root | CLI, agent pack, exporter | `zerker_memory/cli.py`, `zerker_memory/exporter.py`, `zerker_memory/workspaces.py` | Handoff artifacts preserve memory, policy, proof lineage, and enough metadata to restore/verify state. | `tests.test_snapshot`, `tests.test_cli_onboarding`, status summary. | Full suite passed; eval restored snapshot; status reported handoff ok and manual pack ready. | pass | none | Engineering | No fix required. | Strict publish handback remains externally blocked by missing public verify logs/assets. |
| ZQA-010 | Workspace/source identity | As a multi-agent user, I can see which agent/session/workspace produced memory. | scope, sync, verify | agent id, chat/session id, workspace id, source URI | CLI, workspace registry, dashboard | `zerker_memory/workspaces.py`, `zerker_memory/cli.py`, `zerker_memory/dashboard.py` | Source identity is visible and prevents silent cross-workspace confusion. | `tests.test_workspaces`, `tests.test_dashboard`, status summary. | Focused suite passed; status reported current workspace, matched workspace, agent handoff targets, and source registry state. | pass | none | Product | No fix required. | Exact guaranteed scope boundaries beyond workspace/source remain open. |
| ZQA-011 | Consolidation/dedupe | As a long-running agent, I can compress or dedupe memory without losing reversibility or provenance. | summarize, update | source-child lineage, summary id | Consolidation module, tests | `zerker_memory/consolidation.py`, `tests/test_consolidation.py` | Consolidation keeps source child ids and avoids irreversible lossy replacement. | `tests.test_consolidation` and full suite. | Focused suite passed; fixture has ordered levels, reversible lineage, and no hosted summarizer dependency. | pass | none | Evals | No fix required. | Runtime consolidation job behavior remains roadmap work, not a failing shipped path. |
| ZQA-012 | Provider governance | As a builder, I can use external memory providers as candidate recall without bypassing ZMem governance. | capture, govern, retrieve | provider, source, trust status | Provider config/imports | `zerker_memory/providers.py`, `zerker_memory/retrieval_providers.py`, `templates/policy.example.json` | External candidates are quarantined or governed before action influence. | `tests.test_adapters`, `tests.test_retrieval_providers`, `tests.test_mcp`, eval provider quarantine. | Focused suite passed; hosted providers are disabled by default; eval quarantined provider candidate. | pass | none | Security | No fix required. | None recorded. |
| ZQA-013 | MCP integration | As an agent client, I can connect to ZMem through MCP and use memory safely. | capture, retrieve, explain | client, workspace, source | MCP server, examples, agent setup | `zerker_memory/mcp.py`, `zerker_memory/mcp_smoke.py`, `examples/mcp_smoke.py`, `AGENT_INTEGRATION.md` | MCP exposes memory operations consistent with CLI/store policy and proof behavior. | `tests.test_mcp`, `tests.test_cli_onboarding`, CLI help. | Focused suite passed; CLI exposes `mcp`; status reports agent MCP handoff targets ok. | pass | none | Engineering | No fix required. | None recorded. |
| ZQA-014 | CLI onboarding/status/doctor | As a user, I can install, inspect readiness, and diagnose issues from the CLI. | UX, verify | local workspace, agent config | CLI, installer, doctor | `zerker_memory/cli.py`, `zerker_memory/doctor.py`, `install.sh`, `tests/test_cli_onboarding.py`, `tests/test_doctor.py` | First-run commands produce clear setup state and actionable errors. | Full suite, `python3 -m zerker_memory --help`, `python3 -m zerker_memory status --summary-only`. | Full suite passed; status reported workspace ready and doctor ok. Some temp install tests printed sandbox registry warnings but still passed. | pass | none | UX | No fix required. | Strict publish readiness is external-evidence blocked, not CLI failure. |
| ZQA-015 | Dashboard review console | As a user, I can inspect and act on memory state through the local console. | govern, explain, verify | memory id, action id, launch proof | Dashboard | `zerker_memory/dashboard.py`, `tests/test_dashboard.py` | Dashboard actions align with CLI/store behavior and do not obscure trust/proof boundaries. | `tests.test_dashboard` and full suite. | Full suite passed; dashboard tests cover proof inspector, workspace sources, benchmark state, onboarding, release readiness, handoff/restore, return packet, and launch assets. | pass | none | UX | No fix required. | Visual browser QA was not run in this baseline. |
| ZQA-016 | Benchmark evidence | As a builder, I can reproduce local benchmark evidence without overclaiming. | benchmark, verify | dataset, run id, artifact hash | CLI bench, scripts, docs | `zerker_memory/bench.py`, `scripts/bench/**`, `tests/test_bench.py`, `tests/test_bench_scripts.py`, `docs/BENCHMARK_*` | Benchmark commands produce auditable artifacts, hashes, and claim boundaries. | Full suite, `tests.test_bench`, `tests.test_bench_scripts`, `python3 -m zerker_memory bench --help`. | Full suite passed; benchmark CLI exposes list/run/matrix/report/dashboard/public-page/verify/compare/compare-matrices. | pass | none | Evals | No fix required. | Official/public benchmark claims still need pinned datasets, commands, hashes, and receipt bundles. |

## Memory Correctness Matrix

| Invariant | Related audit IDs | Current evidence | Gap |
| --- | --- | --- | --- |
| Relevant scoped retrieval beats unrelated global similarity | ZQA-004, ZQA-010 | Full store/runner suite passed; many decoy, alias, history, and current-state retrieval regressions are covered. | Add explicit user/project/thread/session leak fixtures. |
| Cross-user/project/workspace/thread/session leakage is prevented | ZQA-004, ZQA-006, ZQA-010 | Workspace/source identity tests passed; policy gate tests passed; exact project/thread/session-style scope string fixture passed. | First-class scope fields remain product-questioned. |
| Retrieved vs injected decisions are separate and receipt-visible | ZQA-004, ZQA-006, ZQA-007, ZQA-008 | Eval and full suite passed; status reports proof ready with receipts and Merkle roots. | Add a smaller CTO smoke that prints one receipt-visible injected/withheld case. |
| Summaries preserve facts without fabrication | ZQA-011 | Consolidation fixture tests passed and require reversible source-child lineage without hosted summarizer dependency. | Runtime summary fidelity eval remains future work. |
| Dedupe avoids merging distinct facts | ZQA-011 | Consolidation fixture tests passed. | Add distinct-but-similar dedupe fixture once runtime dedupe exists. |
| Updates preserve provenance and prior state | ZQA-003, ZQA-008 | Snapshot tests cover promote mutation write receipts; eval revocation scenario passed. | None for current shipped path. |
| Forgetting/revocation is observable | ZQA-003, ZQA-008 | Revocation and lineage behavior passed in eval/full suite; forget is now covered by CTO smoke and focused store test; lifecycle matrix added. | Add mutation receipts for `revoke()` and `forget()`. |
| Persistence survives restart and handoff/restore | ZQA-001, ZQA-009 | Snapshot restore eval passed; snapshot/handoff tests passed; status reports handoff ok. | Strict publish return packet waits on external evidence. |
| Benchmark claims are reproducible before public use | ZQA-016 | Benchmark tests passed and CLI verification surfaces exist. | Official/public claims need pinned dataset artifacts and proof bundles. |

## Baseline Run Log

Add newest entries at the top.

| Date/time | Operator | Scope | Commands/artifacts | Result | Notes |
| --- | --- | --- | --- | --- | --- |
| 2026-06-23 | Codex | First CTO baseline across all seeded audit rows | `python3 -m unittest discover -s tests -q`; `python3 -m zerker_memory eval`; `python3 -m zerker_memory status --summary-only`; focused 72-test governance/proof/provider/MCP batch; CLI and bench help | pass | No P0/P1 found. Strict publish remains externally blocked by clean-shell logs and launch assets. |
| 2026-06-23 | Codex | Fast CTO smoke, scope fixture, lifecycle semantics, and local launch-gate refresh | `python3 -m zerker_memory cto-smoke`; focused store scope/forget tests; `verify-operator-packet`; `verify-public-verify`; `verify-launch-assets`; `verify-return-packet`; `prelaunch`; release smoke | pass with external blockers | Fast CTO smoke passed. Scope/forget tests passed. Release smoke passed. Operator packet is ready. Strict publish remains externally blocked on `0/6` clean-shell logs and `0/8` launch assets. |
| 2026-06-22 | Codex | Set up CTO quality loop artifacts | Created `docs/internal/ZMEM_CODEX_CTO_LOOP.md` and this audit ledger | setup | First baseline completed on 2026-06-23. |

## Open Product Questions

| ID | Question | Related audit IDs | Owner | Status |
| --- | --- | --- | --- | --- |
| ZPQ-001 | Which scope boundaries are guaranteed today versus planned: user, project, workspace, thread, session, agent source? | ZQA-004, ZQA-006, ZQA-010 | Product | open |
| ZPQ-002 | Which deletion/forgetting semantics are product guarantees versus revocation/withholding semantics? | ZQA-003, ZQA-008 | Product, Security | partially answered in `docs/internal/ZMEM_LIFECYCLE_SEMANTICS.md`; mutation receipt gap remains open |
| ZPQ-003 | Which benchmark artifacts are allowed to support public copy before official dataset runs are pinned? | ZQA-016 | Product, Evals | open |
| ZPQ-004 | Should `inject` and `why` expose derived temporal envelopes from `query_at`, or only receipt/current-state context? | ZQA-005, ZQA-007 | Product, Evals | open |
