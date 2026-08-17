# ZMem

Agent-native local memory for AI agents. Request approved memory, propose new memory, explain what was used, and hand off governed state with proof.

Most memory systems help agents remember. ZMem helps agents remember responsibly: what an agent remembers, where it came from, whether it is allowed to influence an action, and how to prove what was used.

`zmem` stores agent memory locally, lets agents connect through MCP, packages handoffs across machines, and emits Merkle-backed receipts for what influenced each action.

Public site: `https://zmem.sh`
Repo target: `https://github.com/zerkerlabs/zmem`

Short version:

> Remember locally. Review before trust. Continue through agents. Verify what changed.

## What Ships Today

- Local SQLite memory with FTS search and safe fallback search.
- Optional true local dense candidates with explicit indexing, exact cosine search, and FTS rank fusion.
- Typed memories: episodic, semantic, procedural, and policy.
- Quarantine, review queue, promote, reject, revoke, lineage, and revocation propagation.
- Symbolic injection policy using status, trust, authority, scope, labels, type, and task risk.
- Merkle-backed event log, action receipts, `why`, compact v2 receipt bundles with legacy v1 verification, snapshots, verify, and restore.
- CLI entrypoints: `zmem`, `zerker-memory`, compatibility `zerker`, and `zerker-memory-mcp`.
- Local review console with receipt actions, proof inspector, release-pack, handoff, restore, launch-asset, and return-packet actions.
- Agent setup for Codex, Claude Code, Cursor, OpenClaw, Hermes, and generic MCP clients.
- Launch proof and release-pack artifacts for local demo proof, clean-shell public verify, screenshots/GIFs, and return-packet handoff.
- Behavior-tree recovery memory: trace ingest, fallback explanation, and BehaviorTree.CPP/Groot2 proof export.
- ActiveGraph pack, cross-run memory, pre-call recall, compact traces, and a runnable no-key two-run host example.
- Provider governance scaffold for Mem0 and Zep, with external imports quarantined by default.
- Read-only memory health, explicit expiry maintenance, and review-gated live consolidation on current `main`/post-release candidates.

See [CHANGELOG.md](CHANGELOG.md) for the shipped build history.
For a single feature-by-feature usage map, see [docs/ZMEM_FEATURE_GUIDE.md](docs/ZMEM_FEATURE_GUIDE.md).
For the current market/product signal behind this wedge, see [docs/MOLTBOOK_ZMEM_PRODUCT_SIGNAL.md](docs/MOLTBOOK_ZMEM_PRODUCT_SIGNAL.md).

## The Wedge

Agents that act need more than semantic recall. They need governed recall.

ZMem gives agents:

- Local SQLite memory.
- Typed memories: episodic, semantic, procedural, policy.
- Separate trust and authority.
- Quarantine before activation.
- Symbolic policy gate for injection decisions.
- Lineage and revocation propagation for derived memories.
- Safe retrieval for messy natural-language agent tasks.
- Append-only memory events.
- Merkle roots for tamper-evident state.
- Action receipts for injected and withheld memories.
- Full-state memory snapshots for portable audit.
- A `why` command for memory explainability.

The product principle:

> Neural recall, symbolic control.

The practical user need is inspectable memory: agents should remember across sessions, but users should still be able to see, query, govern, and prove what memory influenced an action.

## Interfaces

ZMem is a product with multiple interfaces:

- `zerker-memory`: primary long CLI.
- `zmem`: short CLI for daily use.
- MCP server: connect agents and IDE tools.
- Python package: embed the local memory store and policy gate.
- Local console: review, audit, and explain memory.

## Zerker Rooms Integration Preview

The current Rooms candidate adds a tenant-local HTTP service for governed shared memory. It keeps one isolated SQLite store per room, separates room-shared from member-private memory, persists accepted state across restarts, quarantines agent proposals, and returns explicit `ready`, `partial`, `empty`, `blocked`, `abstained`, or `budget_exhausted` context states.

```bash
export ZMEM_SERVICE_TOKEN="$(openssl rand -hex 32)"
zmem --db .zerker/control.sqlite serve --tenant-id tnt_local --storage-root .zerker/rooms
```

See [Zerker Rooms](docs/content/docs/rooms.mdx) for the local adapter and [the internal Gateway contract](docs/internal/ZERKER_ROOMS_MEMORY_CONTRACT.md) for the exact ownership, API, security, and handoff decisions. The service was introduced as an integration preview in `v0.1.10`; `v0.1.11` hardens concurrent first access to one room. The existing local CLI, MCP, and SQLite product remain the default.

The compatibility command `zerker` is still available, but launch docs use `zerker-memory` and `zmem` so the product stands on its own.

## Who It Is For

| User | Problem | ZMem gives them |
| --- | --- | --- |
| Builders | Agents forget project memory and cannot explain memory use | Local governed memory, MCP, `zmem run`, `why` |
| Startups | Memory is needed, but infra sprawl is expensive | A governance layer above native or existing memory providers |
| Enterprise teams | Persistent memory creates security and audit risk | Quarantine, authority, lineage, revocation, receipts |

See [docs/ADOPTION_STRATEGY.md](docs/ADOPTION_STRATEGY.md).

## Future-Proof Wedge

ZMem is designed to stay useful as agents evolve from plain LLM loops into neuro-symbolic gateways and multi-agent systems.

The durable claim is not "better vector memory." It is:

> Agents need admissible memory, authority checks, lineage, revocation, and proof, no matter which model or compute substrate is doing the reasoning.

Neural systems can propose and retrieve. Symbolic systems should authorize and prove.

Zerker keeps those responsibilities explicit.

See [docs/FRONTIER_ALIGNMENT.md](docs/FRONTIER_ALIGNMENT.md) for the architecture's state-of-the-art alignment.

## Why It Is Different

| Other memory providers | ZMem |
| --- | --- |
| Store and retrieve useful memory | Govern what memory may influence |
| Semantic similarity first | Similarity plus authority checks |
| Trust is implicit | Trust is explicit |
| Authority is usually missing | Authority is first-class |
| Retrieval equals injection | Retrieval is filtered through symbolic policy |
| Hosted by default | Local-first by default |
| Logs maybe | Merkle-backed receipts |
| Delete/edit memories | Inspect, promote, revoke, verify, explain |

## Works With Existing Memory Providers

ZMem can run native local memory, but it is also designed as a governance overlay for existing memory systems.

```text
Mem0 / Zep / Graphiti / Letta / LangMem / Cognee
  -> candidate recall
Zerker
  -> trust, authority, quarantine, receipts
Treeship
  -> signed portable proof
```

See [INTEGRATIONS.md](INTEGRATIONS.md).

## Quick Start

From a fresh clone, see [QUICKSTART.md](QUICKSTART.md).

One-command local bootstrap:

```bash
bash install.sh
```

The installer now ends by printing `zmem status --summary-only`, so the first successful run finishes with the same one-screen readiness snapshot documented elsewhere.
It also runs both `zmem agent smoke` and `zmem agent mcp-smoke` against the selected bootstrap target, defaulting to OpenClaw for the safe manual-pack path.

Once the repo is public, the same script is curl-pipe ready:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
```

To also install into a local agent config during bootstrap:

```bash
ZERKER_MEMORY_AGENT=codex bash install.sh
ZERKER_MEMORY_AGENT=claude-code bash install.sh
ZERKER_MEMORY_AGENT=cursor bash install.sh
ZERKER_MEMORY_AGENT=openclaw bash install.sh
ZERKER_MEMORY_AGENT=hermes bash install.sh
ZERKER_MEMORY_AGENT=generic bash install.sh
```

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config
zmem status --summary-only
zmem eval
zmem doctor
zmem demo
```

Optional local semantic recall is explicit and remains behind the same policy and receipt boundary:

```bash
python3 -m pip install -e '.[dense]'
zmem embeddings index --download-model --summary-only
zmem inject "what maintenance cadence did we agree on?" \
  --agent cursor \
  --scope project:car \
  --retrieval-mode dense-hybrid \
  --summary-only
```

The first model fetch occurs only with `--download-model`. Later search is local-only, stale content vectors are excluded, and receipts record model/config/query-vector hashes plus lexical/dense fusion. See [docs/content/docs/dense-retrieval.mdx](docs/content/docs/dense-retrieval.mdx).

`zmem status --summary-only` is the fastest readiness check. It summarizes the local workspace, proof counts, agent handoff artifacts, launch-proof state, and the next action to take.

To inspect persisted memory health without changing any memory state:

```bash
zmem audit health --summary-only
```

The audit reports observable expiry, stale lineage, lexical conflicts, exact duplicates, weak provenance, and explicit high-risk active use. It does not claim that memory content is factually or semantically true. See [Memory Health](docs/content/docs/memory-health.mdx).

To turn an objective expiry finding into one explicit, receipted transition:

```bash
zmem maintain preview --summary-only
zmem maintain apply <plan.json> \
  --select <action-id> \
  --actor-id <operator-id> \
  --confirm-plan <plan-id> \
  --summary-only
zmem maintain verify <result.json> --summary-only
```

Maintenance applies one action from a fresh plan. In this first contract, only a reached `expires_at` boundary is executable; conflicts, duplicates, weak provenance, lineage questions, and high-risk use remain review-only. Plan and result artifacts contain hashes and metadata, not raw memory content. See [Memory Maintenance](docs/content/docs/memory-maintenance.mdx).

To inspect which live memories could support a reversible session summary:

```bash
zmem consolidation preview \
  --scope project \
  --min-sources 3 \
  --out preview.json \
  --summary-only

zmem consolidation materialize preview.json \
  --select <candidate-id> \
  --actor-id <operator-id> \
  --confirm-preview <confirmation-id> \
  --summary-only

zmem consolidation audit --summary-only

zmem consolidation inspect --summary-only
zmem consolidation inspect <summary-id> --out inspection.json --summary-only

zmem consolidation admit inspection.json \
  --actor-id <operator-id> \
  --confirm-inspection <confirmation-id> \
  --summary-only

# Or keep it out of canonical memory without deleting the evidence.
zmem consolidation discard inspection.json \
  --actor-id <operator-id> \
  --confirm-inspection <confirmation-id> \
  --reason "Not useful for future recall" \
  --summary-only
```

Preview verifies the global event chain and each source write-receipt chain, groups active episodic/semantic memories by origin actor, environment, and session provenance, and lists every omission without raw memory text. Materialize requires the exact candidate and confirmation ids, revalidates under a locked query-only snapshot, and writes one deterministic summary to private reversible ledgers. Inspect independently recomputes that summary from current verified sources. Only an exact `admit` confirmation creates canonical memory, at the weakest source trust and authority ceilings; `discard` records a terminal Merkle event without deleting evidence. Operator identity remains asserted metadata, Treeship anchoring is separate, and no step claims semantic truth. See [Consolidation Review](docs/content/docs/consolidation-preview.mdx).

For day-1 agent setup:

```bash
zmem setup codex claude-code hermes --summary-only
zmem status --summary-only
```

This binds supported clients to the same absolute workspace database. Codex and Claude Code are ready after reload; Hermes and other manual clients receive a project-local import file. A connector identifies the agent host and MCP process, not necessarily a visible UI chat. In a new or reloaded chat, say: `Use the zerker-memory tools for this project. Request relevant memory before work.` For low-level or custom config paths:

```bash
zmem agent install codex
zmem agent install claude-code
zmem agent install cursor --summary-only
zmem agent pack --summary-only
zmem doctor --agent codex --agent claude-code --agent cursor
```

To bind one current connector as a named live session, create a one-time invitation and paste the printed instruction into that agent:

```bash
zmem session invite --agent codex --label release-chat --summary-only
zmem session connections --summary-only
```

The agent consumes the code through `memory.session_attach`. Codes are hash-only, agent-bound, short-lived, and single-use. ZMem reports recent connector presence separately from configuration and historical memory provenance. A client-provided chat id remains explicitly asserted, and an optional Room id does not grant Gateway membership.

For shared-memory transfer:

```bash
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
```

For release prep:

```bash
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
zmem verify-launch-assets --summary-only
```

The strict publish gate is intentionally not green until the clean-shell public-verify logs and final launch assets exist. If another chat or operator is taking the remaining Phase-1 work, start with [docs/CLEAN_SHELL_VERIFICATION_CHECKLIST.md](docs/CLEAN_SHELL_VERIFICATION_CHECKLIST.md) for the shortest durable path, then use [docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) for the full send-run-receive brief. For the full operator runbook, see [docs/CLEAN_SHELL_PUBLIC_VERIFY.md](docs/CLEAN_SHELL_PUBLIC_VERIFY.md). For a copy-ready clean-shell brief, see [docs/CLEAN_SHELL_OPERATOR_PROMPT.md](docs/CLEAN_SHELL_OPERATOR_PROMPT.md). For the durable screenshot/GIF fallback brief, see [docs/LAUNCH_ASSET_OPERATOR_PROMPT.md](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md). For the durable capture-ready board, see [docs/LAUNCH_ASSET_BOARD.html](docs/LAUNCH_ASSET_BOARD.html).

If you want the repo's fully verified day-1 flow instead of entering commands by hand:

```bash
bash examples/first_run.sh
```

`bash examples/first_run.sh` now refreshes the manual-agent pack before printing the same `zmem status --summary-only` readiness summary, so the run ends with `Manual pack ready: yes`.

To wire a real agent on day 1, see [docs/DAY1_AGENT_SETUP.md](docs/DAY1_AGENT_SETUP.md).
For multi-agent and shared-memory workflows, see [docs/SHARED_MEMORY.md](docs/SHARED_MEMORY.md).

For one-command local MCP install into common agent config files:

```bash
zmem agent install codex
zmem agent install claude-code
zmem agent install cursor --summary-only
zmem agent install openclaw --summary-only
zmem agent pack --summary-only
zmem status --summary-only
zmem doctor --agent codex --agent claude-code --agent cursor
zmem agent checklist openclaw
zmem agent checklist generic
```

Before tagging or publishing, run the release smoke test:

```bash
python3 scripts/release_smoke.py --summary-only
python3 scripts/release_smoke.py
python3 scripts/release_smoke.py --require-install-mode packaged
ZERKER_PROVIDER_LIVE=1 ZERKER_PROVIDER_MEM0_BASE_URL=http://localhost:8888 python3 scripts/release_smoke.py
ZERKER_PROVIDER_LIVE=1 ZERKER_PROVIDER_LIVE_PROVIDERS=zep ZERKER_PROVIDER_ZEP_BASE_URL=http://localhost:8000 python3 scripts/release_smoke.py
```

`scripts/release_smoke.py` now auto-reexecs itself with a discovered Python 3.10+ interpreter when the shell `python3` is too old, and it also proves the direct `python3 -m zerker_memory doctor/status` module-entrypoint path in a fresh workspace.
Use `python3 scripts/release_smoke.py --summary-only` when you want the current Phase-1 preflight without creating a fresh temp install: it refreshes the repo-local release-pack surface, reruns `zmem status --summary-only` after that refresh so the terminal ends on the current operator packet state, verifies the outbound operator packet, checks launch-asset and return-packet readiness, and reruns the strict `prelaunch` gate in one terminal pass.
In network-restricted or dependency-thin environments, it also retries editable install with `--no-build-isolation`, then writes a venv-local `.pth` import bootstrap, and only then falls back to local venv wrapper entrypoints so the end-to-end proof path can still complete.
The same release smoke now also proves the strict publish gate by running `zmem prelaunch --summary-only` without placeholder mode, so regressions in live public URLs, release-surface artifacts, or missing clean-shell public-verify logs fail before tagging.
The same release smoke now also proves `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, so the outbound clean-shell bundle is verified before the existing launch-asset and return-packet checks run.
For the final external clean-shell launch proof, run `python3 scripts/release_smoke.py --require-install-mode packaged`; it fails if the smoke had to fall all the way back to local wrapper entrypoints instead of staying at `editable`, `editable-no-build-isolation`, or `venv-pth`.
The generated `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` script now mirrors that exact clean-shell flow, including the repo path created by the curl installer before the repo-local proof commands run, and it saves per-step logs under `.zerker/launch-proof/public-verify-logs/` plus a machine-readable `.zerker/launch-proof/public-verify-result.json` receipt and a compact `.zerker/launch-proof/public-verify-summary.md` handoff summary so the external alpha pass leaves durable terminal evidence and one glanceable pass/fail artifact behind. That receipt now records whether the proof run is still pending, failed, or passed and captures the release-smoke `install_mode` when it can, while the summary now also shows the expected public repo/raw installer targets, the packaged-install completion rule, the exact outbound triplet to forward together, launch-asset progress, the capture checklist, the verify-before-assets and verify-on-receive commands, the finalize step, the return archive path, and the expected asset list so another chat can inspect the full send-and-receive contract without digging through raw logs. After the screenshots/GIFs are saved, run `zmem verify-launch-assets --summary-only`, then run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` to rebuild the return archive and run `zmem verify-return-packet` locally before handback. The same proof pack now also writes `.zerker/launch-proof/launch-proof.json` as the machine-readable manifest for cross-chat handoff and external proof review, `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md` as the copy-ready operator brief for a separate clean-shell chat, and `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md` as the matching copy-ready receive-side brief for the orchestrator chat that accepts the returned packet. The generated `.zerker/launch-proof/README.md` and `.zerker/launch-proof/index.html` now put that clean-shell contract front-and-center, including the operator prompt, runbook, and outbound packet triplet, so the remaining external launch gate is explicit inside the proof pack itself, the summary-only CLI now tells you whether that tarball is still pending evidence or actually ready to hand back, and `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` gives the receiving side one command to validate the returned archive before accepting it. The generated `PUBLIC_VERIFY_CHECKLIST.md`, `CAPTURE_CHECKLIST.md`, and durable [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) now also include the exact clean-shell command-to-log map plus the success cue each saved log must show, so the operator can hand back the six proof logs, including `operator-packet-verify.log`, without reconstructing the contract from multiple files.

The release smoke also runs `bash examples/first_run.sh` and now fails if that script stops printing the terminal-first readiness summary, so the documented first-run path stays aligned with the shipped install surface.

The repo CI now mirrors that launch path: the matrix job runs unit tests plus eval, and a dedicated release-smoke job runs `bash examples/first_run.sh` and `python scripts/release_smoke.py` on Python 3.10.

`ZERKER_PROVIDER_LIVE_PROVIDERS` accepts a comma- or space-separated list such as `mem0`, `zep`, or `mem0,zep` so launch smoke runs only the adapters you intend to probe.

Or run directly from the checkout:

```bash
python3 -m zerker_memory init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config
zmem status --summary-only
zmem eval
zmem doctor
zmem demo
zmem mcp-config --include-policy
zmem agent config codex --include-policy
zmem agent install codex
zmem doctor --agent codex
zmem agent smoke --agent codex
zmem agent mcp-smoke --agent codex
zmem ui
zmem bt ingest examples/bt_trace.jsonl
zmem bt explain trace_demo_recovery --question "why did the robot fall back?"
zmem bt export trace_demo_recovery --out-dir .zerker/exports
zmem release-pack --summary-only
zmem launch-proof --summary-only
zmem prelaunch
bash scripts/launch_proof.sh
```

`zmem launch-proof` is now the first-class proof capture path: it refreshes `.zerker/launch-proof/` with a clean proof database, transcript, bundle, snapshot, BT export, README, a generated `launch-proof.json` manifest, a generated `CAPTURE_CHECKLIST.md`, a generated `PUBLIC_VERIFY_CHECKLIST.md`, a generated `PUBLIC_VERIFY_HANDOFF.md`, a generated `RECEIVE_VERIFY_HANDOFF.md`, a generated `PUBLIC_VERIFY_COMMANDS.sh`, a generated `.zerker/launch-proof/public-verify-logs/` target for clean-shell evidence, a generated `.zerker/launch-proof/public-verify-result.json` placeholder/receipt, a generated `.zerker/launch-proof/public-verify-return-packet.tar.gz` bundle path for one-file handoff, a generated `.zerker/launch-proof/assets/` directory for the final screenshots/GIFs, and a local HTML proof report in one command. Use `zmem launch-proof --summary-only` when you want the same terminal-first operator view as the other release commands, then open `.zerker/launch-proof/index.html`, `.zerker/launch-proof/launch-proof.json`, `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, or `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md` for the fastest review surface before screenshots, release smoke, or the final clean-shell public install pass. `launch-proof.json` now also carries the machine-readable public verify contract plus a launch-asset storyboard, including the packaged-install requirement, expected clean-shell commands, expected `public-verify-logs/*.log` files, the expected `public-verify-result.json` receipt, the `ui-release-pack` capture, the per-asset `assets/...` output paths, the exact return packet for the separate clean-shell operator, the matching receive-side handoff path, and the optional archive path for bundling that packet into one tarball. The same launch-proof summary now also reports whether that archive is merely structurally present or actually ready with the captured logs and assets. The same artifact can now also be generated from `zmem ui` when you want console review and release proof in one place, and that console can now also run the combined release-pack flow, restore the generated handoff into a fresh `.zerker/imports/` DB for receive-side proof, or verify the returned public-verify packet archive before you accept it. `bash scripts/launch_proof.sh` remains as the Python-picking wrapper for the same flow.

`zmem release-pack --summary-only` is the fastest release-operator path inside the repo: it refreshes `.zerker/handoff/`, refreshes `.zerker/launch-proof/`, rewrites `.zerker/launch-proof/CAPTURE_CHECKLIST.md` with the handoff/restore path included, rewrites `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md` with the clean-shell packaged-install commands, refreshes the `.zerker/launch-proof/public-verify-result.json` placeholder/receipt path plus `.zerker/launch-proof/public-verify-return-packet.tar.gz`, reports public-verify log readiness, launch-asset capture readiness, and return-packet readiness, then runs the prelaunch gate so one command tells you whether strict publish is still blocked on missing clean-shell logs, screenshots/GIFs, or something else. That summary now also prints the expected public repo URL, raw installer URL, the packet-local runbook to open first, the exact six-log clean-shell proof contract, and the full eight-shot launch-asset cue map before another chat starts the clean-shell proof pass. In `zmem ui`, the matching release surface now shows the same eight-asset launch storyboard with each deliverable's output path and captured-vs-missing state, so the final screenshot/GIF pass no longer depends on reconstructing the checklist from prose alone.

`zmem prelaunch` is the release-manager gate. It now expects both `.zerker/launch-proof/` and `.zerker/handoff/` to be present, the handoff export must include the verified snapshot, receipt bundle, and Treeship statement, and strict publish now also requires both the clean-shell public-verify logs under `.zerker/launch-proof/public-verify-logs/` plus the matching `.zerker/launch-proof/public-verify-result.json` receipt and the final screenshot/GIF set under `.zerker/launch-proof/assets/`, so launch review, cross-machine restore, external installer proof, and launch collateral are tracked together. This repo now uses plain `zmem prelaunch` as the default publish check, and `scripts/release_smoke.py` verifies that strict path directly. If you are working from an unreleased fork with placeholder URLs, use `zmem prelaunch --allow-placeholders` to downgrade the public-URL, public-verify, and launch-asset blockers into warnings while you finish local alpha setup.

`zmem handoff` is the shared-memory transfer path. It writes `.zerker/handoff/README.md`, a machine-readable `handoff.json` manifest, a verified snapshot, the latest or selected action bundle when available, and a Treeship-ready statement for that action so another agent or machine can verify, restore, and dry-run publish the same governed state. On the receiving side, run `zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff` to verify the packaged snapshot and bundle, then restore the handoff into one empty store.

For `py_trees` executors, normalize status transitions without adding a runtime dependency:

```python
from zerker_memory.bt import BtMemory
from zerker_memory.store import MemoryStore

bt = BtMemory(MemoryStore(".zerker/memory.sqlite"))
bt.ingest_py_trees_transitions(
    "trace_robot_demo",
    [
        {
            "behaviour_id": "guard_visible",
            "name": "GuardVisible",
            "class_name": "CheckBlackboardVariableValue",
            "previous_status": "RUNNING",
            "current_status": "FAILURE",
            "blackboard_keys": ["human_visible"],
        }
    ],
    executor_id="robot_1",
    tree_id="mission_tree",
)
```

Govern an external memory provider without letting recall become authority:

```bash
zmem provider init
zmem provider doctor
zmem provider doctor --live --mem0-base-url http://localhost:8888 --mem0-query "zerker mem0 smoke" --zep-base-url http://localhost:8000 --zep-query "zerker zep smoke"
zmem provider search "deploy policy" --provider mem0 --user-id <user>
zmem provider import "deploy runbook" --provider mem0 --scope project --type procedural
zmem queue --scope project
```

Provider imports are governed by `.zerker/providers.json`. The default policy allows only `semantic` and `procedural` imports into `global` or `project` scope, keeps them quarantined, and adds `governance:external` alongside provider provenance labels.

By default, Zerker stores data at:

```text
.zerker/memory.sqlite
```

## Agent Integration: MCP

Run the MCP server over stdio:

```bash
zmem mcp --profile agent
```

Or with an explicit database path:

```bash
zmem --db /path/to/memory.sqlite mcp --profile agent
```

Example MCP client config:

```json
{
  "mcpServers": {
    "zerker-memory": {
      "command": "zmem",
      "args": ["--db", ".zerker/memory.sqlite", "mcp", "--profile", "agent"]
    }
  }
}
```

See [examples/mcp_config.example.json](examples/mcp_config.example.json).

For named agent presets:

```bash
zmem agent config codex --include-policy
zmem agent config claude-code --include-policy
zmem agent config cursor --include-policy
zmem agent config openclaw --include-policy
zmem agent config hermes --include-policy
zmem agent config generic --include-policy
zmem agent snippet cursor
zmem agent snippet openclaw
zmem agent snippet hermes
zmem agent snippet generic
zmem agent install codex
zmem agent install claude-code
zmem agent install cursor
zmem agent install openclaw
zmem agent install hermes
zmem agent install generic
zmem agent checklist cursor
zmem agent checklist openclaw
zmem agent checklist hermes
zmem agent checklist generic
zmem doctor --agent cursor --agent openclaw --agent hermes --agent generic
zmem agent smoke --agent codex
zmem agent mcp-smoke --agent codex
```

For manual-target presets, the CLI returns a `manual_import` block with copy-ready steps, an `install_preview` block with the exact first import action and fallback, and a `doctor` block proving the prompt plus exported config passed verification immediately after install. If you want that flow in human-readable terminal output, run `zmem agent install <preset> --summary`, or use `--summary-only` when you want text without JSON. If you are preparing multiple manual-target options for a teammate or customer, run `zmem agent pack --summary-only` to refresh every manual export plus `.zerker/agents/manual-agent-pack.md` and print the operator handoff in one screen. The short version:

- Cursor: import `.zerker/agents/cursor-mcp.json` into Cursor MCP settings, or run `zmem agent snippet cursor` and paste the output as `zerker-memory`, then add `.zerker/AGENT_PROMPT.md` to project instructions or rules.
- OpenClaw: import `.zerker/agents/openclaw-mcp.json` into MCP/tool settings, or run `zmem agent snippet openclaw` and paste the output as `zerker-memory`, then add `.zerker/AGENT_PROMPT.md` to the policy/system prompt.
- Hermes: import `.zerker/agents/hermes-mcp.json` into stdio tool/MCP settings, or run `zmem agent snippet hermes` and paste the output as `zerker-memory`, then add `.zerker/AGENT_PROMPT.md` to the runtime instructions.
- Generic MCP clients: import `.zerker/agents/generic-mcp.json` if the UI supports full config import, or run `zmem agent snippet generic` and paste the output as `zerker-memory`, then add `.zerker/AGENT_PROMPT.md` to the agent instructions.

If you want a shareable artifact with the export path, prompt path, doctor command, snippet fallback, embedded server block, and proof smoke already assembled, run:

```bash
zmem agent checklist openclaw
zmem agent checklist hermes
zmem agent checklist generic
zmem agent pack --summary-only
```

That writes `.zerker/agents/<preset>-checklist.md`, embeds the exact fallback `zerker-memory` server JSON, and refreshes the matching exported config if needed.

If you do not want to inspect JSON output, use the built-in guide:

```bash
zmem agent guide codex
zmem agent guide claude-code
zmem agent guide cursor
zmem agent guide openclaw
zmem agent guide hermes
zmem agent guide generic
```

For Cursor, OpenClaw, Hermes, and generic MCP clients, the guide now mirrors the shortest default path: `zmem agent install <preset>` writes the project-local export under `.zerker/agents/`, and `zmem doctor --agent <preset>` verifies that default export before import. Use `--config-path` only when you intentionally want a non-default file location.

The default `agent` profile is deliberately narrow. It lets an agent request governed memory, propose new memory, explain an action, and verify its receipt:

```text
memory.session_attach
memory.session_status
memory.propose
memory.inject
memory.why
memory.verify
```

Trusted review and maintenance stay outside the agent connection. Use the CLI/UI, or start an explicit local operator server that you do not attach to an untrusted agent:

```bash
zmem mcp --profile operator
```

The operator profile adds:

```text
memory.remember
memory.search
memory.inspect
memory.queue
memory.promote
memory.reject
memory.lineage
memory.revoke
memory.forget
memory.external_search
memory.external_import
memory.snapshot
memory.restore
```

`memory.external_search` and `memory.external_import` accept `provider="mem0"` or `provider="zep"`. Connections and credentials come from the trusted `--providers` config; MCP call arguments cannot replace them. Operator snapshot and restore paths stay under the memory database directory by default. Set `--io-root <directory>` on the operator server when a separate local handoff directory is required.

See [AGENT_INTEGRATION.md](AGENT_INTEGRATION.md) for the recommended agent loop and system prompt snippet.
See [docs/DAY1_AGENT_SETUP.md](docs/DAY1_AGENT_SETUP.md) for Codex, Claude Code, OpenClaw, Hermes, shell-agent, and persistent-chat setup patterns.
See [docs/DOGFOOD.md](docs/DOGFOOD.md) for a first real dogfood flow.
See [docs/PROOF_SCHEMA.md](docs/PROOF_SCHEMA.md) for receipt bundle and snapshot verification details.

Recommended agent loop:

```text
Before task: call memory.inject
During task: use only injected memories
After task: call memory.propose for durable lessons
Human/system: promote high-authority memories
Human/system: reject unsafe or stale memories
Audit: call memory.why
```

For subprocess-based agents, `run` wraps a command with governed memory:

```bash
zmem run --agent codex --task "deploy service" --risk high --scope project -- your-agent-command
```

Scheduled and ephemeral agents can restore optional handoff state, audit the wall-clock gap, run with the audit inside the exact context digest, and leave a verified checkpoint:

```bash
zmem scheduled-run \
  --session-id cron://daily-signal \
  --agent hermes \
  --task "collect the daily product signal" \
  --scope project:zmem \
  --stale-after-seconds 86400 \
  --summary-only \
  -- your-agent-command
```

Record a silent-success or failed outcome without promoting the agent's correction into trusted procedure:

```bash
zmem failure record \
  --expected "transfer exactly 10 credits" \
  --observed "API returned 200 but transferred 100 credits" \
  --correction "compare the requested and settled ledger amounts" \
  --invalidation "settled amount differs from the request" \
  --confidence 0.98 \
  --scope project:payments \
  --agent payments-agent \
  --summary-only
```

Agent-authored failure memories enter quarantine and require review before promotion.

Export and verify a portable memory-state snapshot:

```bash
zmem export <action-id> --format treeship --out-dir .zerker/exports
zmem treeship doctor
zmem treeship publish <action-id> --dry-run
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
zmem snapshot --out-dir .zerker/exports
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
zmem handoff --summary-only
```

`zmem export --format treeship` emits a Treeship statement backed by the local receipt bundle proof, including the bundle hash and verification status.

`zmem treeship doctor` checks whether a local Treeship CLI is reachable. `zmem treeship publish` exports a verified statement first, then signs it as a Treeship receipt with `system://zmem` and `kind=memory.proof`. Pass `--command-template` only when you need to override that default.

For write-time signing, set `ZMEM_TREESHIP_AUTO_SIGN=1` after `treeship init`. ZMem will ask Treeship to attest the compact write-receipt digest as `system://zmem` / `kind=memory.write` and store the returned artifact metadata with the write receipt. Set `ZMEM_TREESHIP_STRICT=1` when unsigned writes should fail instead of falling back to local-only receipts.

The command receives `ZERKER_MEMORY_CONTEXT`, `ZERKER_MEMORY_CONTEXT_DIGEST`, `ZERKER_ACTION_ID`, `ZERKER_MEMORY_DB`, and `ZERKER_MEMORY_MERKLE_ROOT`. The context file contains the exact admitted, withheld, and budget-dropped memory decision plus its policy and Merkle references. `ZERKER_MEMORY_CONTEXT_DIGEST` is the `sha256:` commitment to that file, excluding only the digest field itself.

The context commitment proves which ZMem memory artifact was supplied to the wrapped command. It does not claim the memory was semantically true, capture hidden model reasoning, or commit provider prompt material outside the ZMem context file.

Verify a retained or received context artifact directly:

```bash
zmem context verify .zerker/context.json --summary-only
```

## Local Review Console

Run a dependency-free local dashboard:

```bash
zmem --db .zerker/memory.sqlite ui
```

The console opens a local HTTP service for reviewing queued memories, promoting or rejecting candidates, previewing injection decisions, inspecting recent receipts, exporting receipt bundles, exporting snapshots, and reading proof summaries without leaving the browser.

## Behavior-Tree Recovery Memory

Zerker includes an early behavior-tree recovery-memory pack:

```bash
zmem --db .zerker/memory.sqlite bt ingest examples/bt_trace.jsonl
zmem --db .zerker/memory.sqlite bt traces
zmem --db .zerker/memory.sqlite bt explain trace_demo_recovery --question "why did the robot fall back?"
zmem --db .zerker/memory.sqlite bt export trace_demo_recovery --out-dir .zerker/exports
```

The BT event schema captures trace IDs, node IDs, node status, event type, executor ID, confidence, TTL, affected symbols, causal parents, and delivery semantics. Explanations cite concrete event IDs instead of producing free-floating summaries. `zmem bt export` writes a BehaviorTree.CPP/Groot2-ready XML tree plus a JSON proof manifest sidecar so recovery traces can move into launch demos and external BT tooling without losing Zerker provenance.

## Evaluation

Run the built-in product proof harness:

```bash
zmem eval
```

It verifies:

- authorized policy injection,
- poisoned/quarantined memory withholding,
- review queue and rejection,
- revocation propagation through descendants,
- Treeship-ready export.
- snapshot restore into an empty store.
- full-state snapshot export.
- behavior-tree fallback explanation.

Exports write stable JSON artifacts and return an artifact id, path, and SHA-256 hash.

Retrieval receipts include the search mode used (`fts`, `fallback`, or `none`) so agent behavior can be audited.

## Policy Configuration

Zerker ships with safe defaults and can load a project policy file:

```bash
zmem --policy templates/policy.example.json inject "deploy the service" --agent codex --risk high
```

Policy files use JSON schema `zerker.policy.v1` and can tune risk thresholds or deny labels such as `secret`, `credential`, or `private-key`.

## Core Idea

Trust answers:

> Is this memory authentic, benign, and not tampered with?

Authority answers:

> Is this memory allowed to influence this action?

A memory can be trusted but still low-authority.

## Roadmap

- Real Treeship signing/push.
- Live Mem0/Zep integration smoke.
- Zep adapter scaffold.
- py_trees and BTPG adapter helpers.
- Vector search.
- Declarative policy configuration.
- Review queue UI.
- CRDT sync.

See [docs/PRODUCT_STATUS.md](docs/PRODUCT_STATUS.md) for what is functional today and what remains before production.

## Contributing and License

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

ZMem is released under the [MIT License](LICENSE).
