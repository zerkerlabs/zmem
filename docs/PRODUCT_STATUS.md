# Product Status

## Current Status

Zerker Memory is a functional open-source, local-first alpha with a public site, tagged releases, and a verified local proof path.

Current published release: `v0.1.17` at `https://github.com/zerkerlabs/zmem/releases/tag/v0.1.17`.

The current release makes the tenant-local Rooms contract repeatable before Gateway rollout. `zmem rooms-acceptance` verifies authenticated room-shared and member-private memory, tenant isolation, commitments, abstention, retries, conflicts, and concurrent preparation over ephemeral local stores. It does not claim that Gateway's production network, membership authority, load, timeout, or live two-agent gates have passed. The previously shipped governed Reason premise boundary, one-command agent connection, fail-closed dense Room readiness, visual shared-memory inventory, review-gated consolidation, scheduled-agent continuity, and local dense/FTS retrieval remain available.

It is ready for:

- local developer dogfooding,
- MCP-capable agent experiments,
- demos to builders/startups,
- early enterprise architecture conversations,
- GitHub open-source use as an alpha,
- receipt-backed local LoCoMo, LongMemEval, and BEAM development evidence,
- ActiveGraph 1.9+ pack experiments, a runnable two-run host, and compact causal traces.
- tenant-local Zerker Rooms integration experiments with durable shared/private room memory and explicit context state.
- governed structured-premise integration experiments with Zerker Reason and other downstream consumers.

It is not yet:

- a hosted SaaS,
- a production enterprise control plane,
- a semantic-truth oracle; receipts prove integrity, provenance, and influence rather than truth,
- a full vector/graph memory replacement,
- a fully polished hosted review workflow.
- a deployed zerker.ai Rooms backend; the ZMem service plus Gateway client and durable Rooms persistence are implemented, but the Gateway release pin, production retrieval profile, load/timeout gates, and live two-agent acceptance still need to land.

Product signal note: the current wedge is validated by builder demand for local, inspectable, structured, curated, and verifiable agent memory. See `docs/MOLTBOOK_ZMEM_PRODUCT_SIGNAL.md`.

## Not Built Yet, In Priority Order

1. Pin Gateway to immutable ZMem `v0.1.17`, provision its cached dense-hybrid profile, gate on `/readyz`, and pass realistic load/timeout plus host-native two-agent attach/revocation acceptance. The local package gate is shipped; these production claims remain open.
2. Handoff ownership/lease metadata on top of the shipped provenance-preserving dry-run import preview.
3. Reviewed live day/week/profile consolidation rollups before any periodic scheduler is considered.
4. Efficiency tuning for the opt-in local dense/FTS candidate. Full local LoCoMo and LongMemEval comparisons completed with 347 and 91 gains, zero losses, and materially higher token and latency cost.
5. Broader lifecycle maintenance for revalidation deadlines, decay, retention tombstones, and failed-claim reopen conditions. The first explicit-expiry transition is implemented in the post-release candidate.
6. True bi-temporal graph storage and richer temporal filters when a concrete consumer requires them. Current contradiction-driven withholding and abstention are already receipt-visible.
7. Governed tool and interface-contract trust records linked to Treeship canary proof without moving install/run authority into ZMem.
8. A server-controlled MCP dense-retrieval mode after the CLI/library candidate is accepted; existing MCP tool schemas intentionally retain stable FTS behavior.
9. An official model-judged BEAM submission path plus broader multi-conversation 1M and 10M coverage; the first isolated runs are complete.
10. After the live Rooms gate passes, add separately authorized remote review, hosted tenant routing, collective receipts, customer-managed keys, SSO, audit retention, and VPC/on-prem guides without weakening the tenant-local default.

## Functional Today

- CLI.
- `v0.1.17` Rooms acceptance: authenticated local HTTP checks for room/member/tenant isolation, exact context commitments, abstention, retry safety, conflict rejection, concurrent preparation, and an optional operator-supplied p95 budget.
- `v0.1.16` governed premise export: deterministic strict-JSON facts from active labeled policy memory, per-fact receipt provenance, and fail-closed current-state verification for downstream Reason consumers.
- `v0.1.15` one-command agent connection: initialize or verify one workspace, configure one agent host, and issue one unique scoped invitation without claiming Room membership or host-verified chat identity.
- `v0.1.14` deployment-safe Room readiness: `/healthz` is liveness-only; `/readyz` returns a versioned readiness contract and fails closed until a requested dense runtime plus cached local model are available, without loading or downloading a model during the probe.
- `v0.1.14` console-native agent session controls: create a short-lived, agent-bound invitation, copy the exact attach instruction, and detach a connector without deleting memory or granting Room membership.
- `v0.1.13` live agent sessions with hash-only, expiring, agent-bound invitations; exact MCP connection attachment; client-asserted optional session ids; live/idle presence; explicit detach; and a console that keeps configured, observed, active, and live state distinct.
- `v0.1.13` visual agent memory network and preview-bound transfer flow with Room-shared/member-private inventory, contributors, proof roots, semantic-index coverage, and exact handoff/snapshot restore confirmation.
- `v0.1.13` semantic recall and context-contract hardening for Rooms, including post-write index maintenance, compact readiness metadata, `empty` versus `abstained` state, and cross-language context commitment fixtures.
- The Gateway repository now has the durable Room/event store, real authenticated ZMem HTTP client, `PrepareContext`/`Propose`/`Record` seam, commitment verification, fail-closed joins, accepted-event recording, and quarantined proposal handling. Production rollout and current-release acceptance remain separate gates.
- `v0.1.12` guided setup with `zmem setup [agents...]`, exact database/policy/agent/profile verification, bound MCP host identity, per-process connection provenance, explicit reload/import states, and `zmem workspace prune` for stale registry entries.
- `v0.1.11` concurrent first-open hardening over the `v0.1.10` room-scoped shared/private memory service, authenticated context/record/propose endpoints, explicit withheld/abstention state, retry-safe writes, and hard tenant-room isolation.
- Read-only `zmem audit health` JSON and terminal summaries for observable memory-state findings, with no semantic-truth claim.
- Review-gated consolidation through `preview`, `materialize`, `audit`, `inspect`, `admit`, and `discard`, with verified source coverage, private deterministic materialization, live recomputation, interruption recovery, and explicit ceiling-bound terminal decisions. CLI actor ids are asserted rather than authenticated, and Treeship anchoring remains separate.
- `zmem maintain preview`, `apply`, and `verify` for one state-bound, non-cascading, receipt-backed explicit-expiry transition.
- Deterministic adaptive retrieval with receipt-visible routing, packing, semantic rescue, conservative regular-inflection evidence, bounded completion support, and exact-event-head transcript-neighbor support.
- Opt-in FastEmbed local dense candidates, SQLite vector cache, exact cosine search, FTS RRF fusion, stale-vector rejection, and receipt-visible model/config/vector identity.
- Verified local LoCoMo and LongMemEval matrices with explicit provisional claim boundaries.
- BEAM official-layout adapter with verified isolated evidence at 100K, 500K, 1M, and 10M. The 10M conversation covers 19,895 messages, 6,209,948 observed whitespace tokens, and `201/201` source references in a compact proof artifact.
- Real ActiveGraph 1.9+ pack discovery/loading, event persistence, a runnable no-key two-run host, a pre-call wrapper with recorded/sent prompt equality, and a batched compact trace runner.
- `install.sh` one-command bootstrap for clone and curl-style setup.
- `install.sh` now runs both day-1 smoke commands against the selected bootstrap target, defaulting to OpenClaw for the safe manual-pack path.
- MCP server.
- `zmem ui` local console can now run release-pack, generate launch-proof, package handoff, restore that handoff into a fresh import DB, and verify a returned public-verify packet archive from the same review surface, while the release panel also surfaces the operator packet, public-verify runbook/summary, the exact missing clean-shell logs and launch assets still blocking Phase 1, and the full eight-asset launch storyboard with per-asset output paths plus captured-vs-missing state.
- `zmem launch-proof` now writes a generated `.zerker/launch-proof/launch-proof.json` manifest plus `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, `.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md`, `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md`, `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md`, `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, `.zerker/launch-proof/public-verify-result.json`, `.zerker/launch-proof/public-verify-summary.md`, and `.zerker/launch-proof/public-verify-return-packet.tar.gz` files plus `.zerker/launch-proof/public-verify-logs/` and `.zerker/launch-proof/assets/` targets, `launch-proof.json` now also carries the packaged-install requirement plus the expected clean-shell command/log/result contract for the public verify pass, a launch-asset storyboard, per-asset output paths, the outbound operator-packet path, the receive-side handoff path, the finalize-script path, and the optional one-file return-packet archive path, and the generated launch-proof README/report plus `PUBLIC_VERIFY_HANDOFF.md`, `RECEIVE_VERIFY_HANDOFF.md`, and `LAUNCH_ASSET_HANDOFF.md` now foreground the external operator contract directly. The launch-proof HTML report now also surfaces the operator prompt, runbook, outbound packet path, and forward-together triplet in that clean-shell section so another chat can resume the Phase-1 handoff from one proof screen, while `LAUNCH_ASSET_BOARD.html` keeps the screenshot/GIF save paths and reference files on one capture-ready surface. The generated `public-verify-result.json` receipt now records whether the clean-shell proof is pending, failed, or passed and captures the release-smoke `install_mode` when available, while `public-verify-summary.md` now also carries the expected public repo/raw installer targets, the packaged-install completion rule, the exact outbound triplet, launch-asset progress, the capture checklist, the verify-before-assets and receive-side acceptance commands, the finalize step, the return archive path, and the expected asset list so another chat can see the full send-and-receive contract without opening multiple files. The generated `PUBLIC_VERIFY_CHECKLIST.md`, `CAPTURE_CHECKLIST.md`, and durable `docs/CLEAN_SHELL_PUBLIC_VERIFY.md` now also carry a one-screen command-to-log map with the success cue each returned clean-shell log must satisfy, so the external operator can hand back the six proof logs, including `operator-packet-verify.log`, without reconstructing the contract from prose. `zmem verify-operator-packet --summary-only` and `zmem verify-public-verify --summary-only` now also print that exact six-log command map directly in the terminal alongside the runbook, prompt, unpack command, and handoff triplet, so another orchestrator chat can resume the clean-shell handoff from one verifier screen. `zmem verify-return-packet --summary-only` now also restates the receive-side handoff path, expected logs root, `packaged` install requirement, pinned public targets, and the rerun-then-finalize contract for incomplete return packets, so the receiving chat can accept or reject a handback from one screen. The summary-only launch/release surfaces now also validate both packet directions and the screenshot/GIF storyboard: they report whether the outbound operator archive is intact before handoff, whether the clean-shell logs plus receipt already satisfy `zmem verify-public-verify --summary-only`, whether the return archive is still pending evidence or actually ready to hand back, `FINALIZE_RETURN_PACKET.sh` now runs `zmem verify-public-verify --summary-only` plus `zmem verify-launch-assets --summary-only` before rebuilding the handback archive after asset capture, `zmem verify-operator-packet` verifies the outbound archive before another chat receives it, `zmem verify-launch-assets` verifies the local launch asset storyboard before packet finalization and now prints the per-shot command plus capture cue inline, and `zmem verify-return-packet` verifies the returned archive from the receiving side before the handoff is accepted.
- `docs/CLEAN_SHELL_PUBLIC_VERIFY.md` gives the same Phase-1 send/receive proof loop a durable repo-level runbook, so another chat can brief the external operator and accept the returned packet even before the generated `.zerker/launch-proof/` pack is refreshed again.
- `docs/CLEAN_SHELL_VERIFICATION_CHECKLIST.md` now gives that same launch gate one concise durable repo-level checklist, so another chat can run the send, public-proof, asset-capture, finalize, and receive-side acceptance sequence without scanning the longer brief first.
- `docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md` now gives orchestrator chats one durable repo-level Phase-1 handoff doc that spans outbound clean-shell proof, launch-asset capture, and receive-side acceptance in one place.
- `docs/CLEAN_SHELL_OPERATOR_PROMPT.md` is the durable repo-level source for the copy-ready prompt, and `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` is the generated packet copy for forwarding that outbound packet to a separate clean-shell chat, so the remaining Phase-1 public proof can be delegated without rewriting the contract by hand.
- `docs/LAUNCH_ASSET_OPERATOR_PROMPT.md` is the durable repo-level source for the screenshot/GIF pass, so another chat can run the eight-shot asset storyboard even when the generated packet has not been refreshed yet.
- `docs/LAUNCH_ASSET_BOARD.html` is the durable repo-level visual board for that same screenshot/GIF pass, so another chat can keep the eight-shot cue map, save paths, and durable fallback references on one screen even before `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` is regenerated.
- Fresh launch-proof packs now copy that repo-level runbook into `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` and include it in the outbound operator packet, so the clean-shell handoff stays self-contained when another chat only receives the tarball, and the shipped handoff contract now explicitly tells the operator to unpack that tarball back into `.zerker/launch-proof/` before running `PUBLIC_VERIFY_COMMANDS.sh`.
- Agent config presets for Codex, Claude Code, Cursor, OpenClaw, Hermes, and generic MCP agents.
- Direct agent install for Codex `~/.codex/config.toml` and Claude Code `~/.claude/mcp.json`.
- Manual-target agent install for Cursor, OpenClaw, Hermes, and generic MCP clients now writes both the project-local export and matching `.zerker/agents/<preset>-checklist.md`, plus an inline `install_preview` payload with the first import step and fallback.
- Manual-target checklist artifacts now embed the exact `zerker-memory` server JSON so operators can finish setup from one markdown handoff even when whole-file import fails.
- Agent installs now return an immediate post-install `doctor` result proving the prompt plus written config passed verification in the same command.
- Manual-target installs can now print a compact terminal-first operator summary with `zmem agent install <preset> --summary`, or skip JSON entirely with `--summary-only`.
- One-command manual-agent pack generation with `zmem agent pack --summary-only`, including Cursor, OpenClaw, Hermes, generic, a compact text handoff, and a shared `.zerker/agents/manual-agent-pack.md` index.
- Optional doctor verification for installed Codex and Claude Code configs with `zmem doctor --agent ...`.
- Optional doctor verification for manual-target exports with `zmem doctor --agent openclaw` / `--agent hermes` / `--agent generic`, plus custom-path verification with `zmem doctor --agent-config <preset>=<path>`.
- Copy-ready manual import guidance in CLI output plus docs for Cursor, OpenClaw, Hermes, and generic MCP agents.
- Single-server MCP snippet helper with `zmem agent snippet <preset>` for UIs that reject whole-file JSON import.
- Human-readable preset setup guides with `zmem agent guide <preset>`.
- One-command manual-agent checklist artifacts with `zmem agent checklist <preset>`.
- Day-1 agent smoke with `zmem agent smoke`.
- Real MCP stdio protocol smoke with `zmem agent mcp-smoke`.
- Packaged MCP stdio smoke covering initialize, tools/list, and `memory.inject`.
- Verified first-run script with `bash examples/first_run.sh`, including manual-agent pack generation before the final summary.
- Bootstrap scripts now finish by printing `zmem status --summary-only`, so day-1 users land on the compact readiness view automatically, with `Manual pack ready: yes` on the verified first-run path.
- `zmem run` wrapper.
- Local review console with `zmem ui`, first-run setup guidance, receipt actions, proof inspector, one-click release-pack, and separate launch-proof, handoff, launch-asset verification, and return-packet verification actions.
- Console proof flow now includes launch-ready demo guidance for eval, deploy preview, and portable proof export.
- Behavior-tree recovery-memory tools with `zmem bt`.
- Local SQLite memory store.
- SQLite FTS and safe fallback search.
- Memory types: episodic, semantic, procedural, policy.
- Trust vs authority.
- Quarantine, queue, promote, reject.
- Neuro-symbolic policy gate.
- JSON policy configuration for trust, authority, and deny labels.
- Lineage and revocation propagation.
- Merkle event log.
- Cross-process event appends acquire SQLite's writer lock before reading and advancing the chain head.
- Action receipts and `why`.
- Compact v2 receipt bundles with supporting-event Merkle witnesses and backward-compatible v1 verification.
- Bundle verification now enforces proof metadata consistency before Treeship export.
- Stable JSON export.
- Treeship statement export backed by receipt-bundle proof.
- Treeship CLI doctor plus verified statement publish handoff via configurable command template.
- Full-state memory snapshot export.
- Snapshot verification.
- Snapshot restore into an empty store.
- One-command shared-memory handoff with `zmem handoff --summary-only`, including a verified snapshot, latest bundle when present, a Treeship-ready statement for that action, `.zerker/handoff/README.md`, and a machine-readable `handoff.json` manifest for one-command receive-side restore.
- BT event JSONL ingest, trace listing, and deterministic fallback explanation.
- Dependency-free `py_trees` and BTPG transition adapter helpers for governed BT trace ingest.
- BehaviorTree.CPP/Groot2 export for BT traces with XML plus a proof manifest sidecar.
- Mem0 provider search/import scaffold through `zmem provider`.
- Provider config with `.zerker/providers.json` and `zmem provider doctor`.
- Provider import governance for allowed scope/type, default quarantine status, import trust, and labels.
- Live Mem0 and Zep governance smoke via `zmem provider doctor --live`.
- Live provider smoke can target explicit adapters so release demos only probe the intended Mem0/Zep endpoints.
- External provider imports default to quarantine with provider provenance labels.
- Terminal-first readiness summary with `zmem status --summary-only` for workspace files, proof counts, manual-agent handoff artifacts, and repo release readiness when the full launch surface is present, plus agent-aware next-step suggestions that follow the configured target instead of assuming Codex. When launch-proof artifacts are still missing, that same status view now tells the operator to run `zmem release-pack --summary-only` first instead of advertising packet-local proof paths prematurely.
- `zmem status --summary-only` now also surfaces `zmem release-pack --summary-only` when launch-proof or handoff artifacts are missing, and once those exist it reports both public-verify log readiness against `.zerker/launch-proof/public-verify-logs/` and launch-asset readiness against `.zerker/launch-proof/assets/`, so release operators can see the remaining external-proof and screenshot/GIF gaps from one screen.
- That same status view now also prints the exact capture checklist, launch-asset handoff, public-verify checklist/script, receive-side handoff, outbound operator packet, result receipt, and return-packet archive paths, and it tells the clean-shell operator to hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` or the equivalent return packet after the Phase-1 proof pass.
- `zmem status --summary-only` and `zmem prelaunch --summary-only` now also tell the operator to rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` and confirm `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` before handback, so the main release surfaces match the dedicated receive-side verifier.
- Once launch-proof and handoff exist, that same status view keeps its next steps focused on outbound operator-packet verification, the clean-shell proof script, launch-asset verification, and return-packet handback ahead of generic UI or agent smoke prompts.
- Direct `python3 -m zerker_memory doctor` and `status --summary-only` now auto-reexec with a discovered Python 3.10+ interpreter when the shell default is older, while still surfacing the `bash install.sh` and manual venv recovery path if no supported interpreter is available.
- `zmem eval`.
- `zmem doctor`.
- Fresh-venv release smoke with `scripts/release_smoke.py`, now including outbound `verify-operator-packet` plus receive-side `verify-return-packet` coverage in the shipped Phase-1 loop.
- Release smoke now auto-reexecs with a discovered Python 3.10+ interpreter when the shell `python3` is too old, proves the direct `python3 -m zerker_memory doctor/status` path in a fresh workspace, and the summary-only Phase-1 preflight reruns `zmem status --summary-only` after `release-pack` so the terminal ends on the refreshed operator packet state instead of the stale pre-pack snapshot.
- Release smoke now falls back from isolated editable install to `--no-build-isolation`, then a venv-local `.pth` import bootstrap, and only then local venv wrappers, so proof still completes in network-restricted environments.
- Release smoke now also proves `zmem prelaunch --summary-only` without placeholder mode, so the strict publish gate covers live public URLs, release-surface artifacts, required clean-shell public-verify logs, and final launch screenshots/GIFs before tagging.
- Release smoke now also supports `--require-install-mode packaged` for the final public clean-shell pass, so launch verification fails if proof only succeeded through local wrapper fallback.
- First-class `zmem launch-proof` proof capture that refreshes `.zerker/launch-proof/` with transcript, bundle, snapshot, BT export, README, and a local HTML proof report, and now supports `--summary-only` for the same terminal-first operator flow as the other release commands, with `scripts/launch_proof.sh` kept as a thin wrapper.
- First-class `zmem release-pack --summary-only` launch operator command that refreshes `.zerker/handoff/`, `.zerker/launch-proof/`, and the prelaunch gate in one pass, and now also prints the expected public repo URL, raw installer URL, packet-local runbook, six-log clean-shell proof contract, and eight-shot launch-asset cue map before the clean-shell proof pass starts.
- `zmem prelaunch` release-manager audit for required files, CLI entrypoints, generated-state ignores, launch-proof artifacts, launch-asset capture readiness, public-verify evidence, handoff artifacts, bootstrap readiness summary, and unresolved public URL placeholders.
- The prelaunch handoff gate now requires the shared README plus snapshot, bundle, and Treeship statement exports, so the local alpha cannot report ready with only partial handoff proof.
- GitHub Actions CI now mirrors launch verification with unit-test plus eval matrix coverage and a dedicated Python 3.10 first-run/release-smoke job.
- Static landing page.
- Landing page now includes a dedicated launch proof path section for screenshot/GIF-ready demos.

## Proof Commands

```bash
python3 -m unittest discover
bash examples/first_run.sh
zmem status --summary-only
zmem eval
zmem agent config codex --include-policy
zmem agent install codex
zmem agent install claude-code
zmem agent pack --summary-only
zmem doctor --agent codex --agent claude-code
zmem agent checklist openclaw
zmem agent checklist hermes
zmem agent checklist generic
zmem agent smoke --agent codex
zmem agent mcp-smoke --agent codex
zmem --db /tmp/zerker-bt.sqlite bt ingest examples/bt_trace.jsonl
zmem --db /tmp/zerker-bt.sqlite bt explain trace_demo_recovery --question "why did the robot fall back?"
zmem --db /tmp/zerker-bt.sqlite bt export trace_demo_recovery --out-dir .zerker/exports
zmem ui
zmem release-pack --summary-only
zmem verify-public-verify --summary-only
zmem treeship doctor
zmem treeship publish <action-id> --dry-run --command-template "treeship prove {statement} --action {action_id}"
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
zmem snapshot --out-dir .zerker/exports
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
zmem --db .zerker/restored.sqlite restore .zerker/exports/<snapshot>.snapshot.json
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
zmem export <action-id> --format treeship --out-dir .zerker/exports
zmem provider import "deploy runbook" --provider mem0 --scope project --type procedural
zmem provider doctor
zmem provider doctor --live --mem0-base-url http://localhost:8888 --mem0-query "zerker mem0 smoke" --zep-base-url http://localhost:8000 --zep-query "zerker zep smoke"
python scripts/verify_activegraph_pack.py --summary-only
zmem bench run beam --dataset /path/to/BEAM/chats/100K --split 100K --out .zerker/bench/runs --run-id beam-100k-local --compact-artifacts
zmem doctor
zmem prelaunch
python3 scripts/release_smoke.py --summary-only
python3 scripts/release_smoke.py
python3 scripts/release_smoke.py --require-install-mode packaged
```

## Product Promise Proven

The current MVP proves:

```text
Agent memory can be local-first, governed before injection, explainable after action, exportable as proof, and extended into behavior-tree recovery traces.
```

## Next Production Gaps

1. Additional multi-hop/open-domain retrieval improvements under the zero-regression gate.
2. Dense vector and temporal graph fusion.
3. Official BEAM model-judged scoring plus broader multi-conversation scale coverage.
4. Broader ActiveGraph application integration beyond the runnable two-run host.
5. Expand live provider smoke into hosted CI coverage and add a Graphiti adapter.
6. Policy config expansion: per-agent, per-scope, and per-action rules.
7. Snapshot merge/import conflict rules.
8. Hosted or VPC review workflow and public package publishing.
