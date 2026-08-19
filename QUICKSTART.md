# Quickstart

From a fresh clone:

One-command local bootstrap:

```bash
bash install.sh
```

The installer ends by printing `zmem status --summary-only`, so the first successful run leaves you at the compact readiness snapshot immediately.
It also runs both day-1 smoke commands against the selected bootstrap target, defaulting to OpenClaw for the safe manual-pack flow.

Once the repo is public, the same script can be used as a curl-style starter:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
```

By default, the installer creates the local venv, installs Zerker Memory, initializes `.zerker/`, runs eval and doctor, generates the manual-agent pack, and runs both day-1 smoke commands without writing into Codex or Claude config files. To opt into a real agent install:

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

`zmem status --summary-only` is the shortest readiness view. It shows the local workspace, proof counts, agent handoff state, and the next useful command.

For everyday use:

```bash
zmem status --summary-only
zmem agent pack --summary-only
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
```

For a scheduled agent, use one command to audit continuity, run with governed memory, checkpoint, and prove the result:

```bash
zmem scheduled-run --session-id cron://daily --agent hermes --task "daily review" --scope project --summary-only -- your-agent-command
```

Optional semantic recall uses an explicit local index and the same governance path:

```bash
python3 -m pip install -e '.[dense]'
zmem embeddings index --download-model --summary-only
zmem inject "continue the release work" --agent cursor --scope project --retrieval-mode dense-hybrid --summary-only
```

Ordinary search never downloads the model. If the local runtime or index is unavailable, the action receipt records the fallback and FTS continues.

Add `--handoff-dir .zerker/handoff` when the target database is empty and the run must restore portable state first.

For launch or clean-shell proof work, use the dedicated operator docs instead of this quickstart:

- [docs/CLEAN_SHELL_VERIFICATION_CHECKLIST.md](docs/CLEAN_SHELL_VERIFICATION_CHECKLIST.md)
- [docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md)
- [docs/CLEAN_SHELL_PUBLIC_VERIFY.md](docs/CLEAN_SHELL_PUBLIC_VERIFY.md)
- [docs/CLEAN_SHELL_OPERATOR_PROMPT.md](docs/CLEAN_SHELL_OPERATOR_PROMPT.md)
- [docs/LAUNCH_ASSET_OPERATOR_PROMPT.md](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md)
- [docs/LAUNCH_ASSET_BOARD.html](docs/LAUNCH_ASSET_BOARD.html)

Run the release smoke test before tagging or publishing:

```bash
python3 scripts/release_smoke.py --summary-only
python3 scripts/release_smoke.py
python3 scripts/release_smoke.py --require-install-mode packaged
ZERKER_PROVIDER_LIVE=1 ZERKER_PROVIDER_MEM0_BASE_URL=http://localhost:8888 python3 scripts/release_smoke.py
```

If the shell `python3` is older than 3.10, `scripts/release_smoke.py` now auto-reexecs itself with a discovered Python 3.10+ interpreter when one is available on `PATH` or through `pyenv`, and it proves the direct `python3 -m zerker_memory doctor/status` module path in the same fresh workspace.
Use `python3 scripts/release_smoke.py --summary-only` when you only need the repo-local Phase-1 preflight: it refreshes `release-pack`, reruns `zmem status --summary-only` after that refresh so the terminal ends on the current operator packet state, verifies the operator packet, checks launch-asset and return-packet readiness, and reruns the strict `prelaunch` gate without building a fresh temp install.
If isolated editable install cannot fetch packaging dependencies, the smoke retries with `--no-build-isolation`, then writes a venv-local `.pth` import bootstrap, and only then falls back to local venv wrapper entrypoints so the launch proof still runs in restricted environments.
The same release smoke now also proves `zmem handoff`, so shared-memory restore artifacts stay aligned with the launch-ready proof path, including the handoff Treeship statement.
The same release smoke now also proves `zmem launch-proof --summary-only`, so the proof-only operator path stays aligned with the shipped artifact contract.
The same release smoke now also proves `zmem release-pack --summary-only`, so the shortest local launch-refresh command stays aligned with the release contract.
The same release smoke now also proves `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, so the outbound proof bundle is validated before the launch-assets and return-packet checks run.
The same release smoke now also proves `zmem prelaunch --summary-only` without placeholder mode, so the strict publish gate, live public URLs, required clean-shell public-verify logs, and final launch screenshots/GIFs stay covered before tagging.
For the final clean-shell public launch check, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`; it rejects the local-wrapper fallback and only passes when the install path stays at `editable`, `editable-no-build-isolation`, or `venv-pth`. The `zmem release-pack --summary-only` step now also restates the exact public repo URL, raw installer URL, packet-local runbook, six-log proof contract, and eight-shot asset cue map that the clean-shell operator must use first.
The launch-proof step now also expects `.zerker/launch-proof/index.html`, `.zerker/launch-proof/launch-proof.json`, `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, `.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md`, `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md`, `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md`, `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, `.zerker/launch-proof/public-verify-summary.md`, `.zerker/launch-proof/public-verify-return-packet.tar.gz`, and `.zerker/launch-proof/assets/`, so the local proof report, machine-readable manifest, outbound operator bundle, screenshot/GIF checklist, the capture-ready launch-asset board, asset-capture handoff, receive-side acceptance brief, external clean-shell verification commands, saved terminal evidence, the public-verify pass/fail receipt, the compact run summary, the local finalize/self-check step, the optional one-file return bundle, and final launch screenshots/GIFs stay aligned before demos. That manifest now also carries the packaged-install requirement plus the expected clean-shell command/log/result contract for separate-chat and external audit handoff, including the exact outbound operator packet to forward before the run and the exact return packet to hand back after the clean-shell pass. The generated `public-verify-result.json` receipt now records whether the proof run is still pending, failed, or passed and captures the release-smoke `install_mode` when available, while `public-verify-summary.md` now also shows the expected public repo/raw installer targets, the packaged-install completion rule, the exact outbound triplet, launch-asset progress, the capture checklist, the verify-before-assets and receive-side acceptance commands, the finalize step, the return archive path, and the expected asset list so another chat can inspect the full handback contract without opening raw logs. The generated launch-proof README/report plus `PUBLIC_VERIFY_HANDOFF.md` and `RECEIVE_VERIFY_HANDOFF.md` now surface that send-and-receive contract directly for the final operator loop, and the launch-proof HTML report now also surfaces the operator prompt, runbook, and outbound packet triplet in the same clean-shell section while the `LAUNCH_ASSET_BOARD.html` surface keeps the save paths and reference files on one screen for the screenshot pass. `zmem launch-proof --summary-only` and `zmem release-pack --summary-only` now also tell you whether that archive is still pending public-verify evidence or actually ready to hand back, and `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` verifies that returned archive on the receiving side. The generated `PUBLIC_VERIFY_CHECKLIST.md`, `CAPTURE_CHECKLIST.md`, and repo-level [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) now also include the exact clean-shell command-to-log map with the success cue each saved log must show. When handoff artifacts are present, the generated checklist, board, and manifest also spell out the `ui-release-pack`, `handoff-restore-terminal`, and `ui-handoff-restore` launch assets together with their `assets/...` output paths.
The operator bundle now also includes `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, a packet-local start-here copy of the clean-shell runbook for the receiving chat or operator.

The repo CI mirrors this release path: unit tests plus eval run across Python 3.10-3.12, and a dedicated release-smoke job runs `bash examples/first_run.sh` and `python scripts/release_smoke.py` on Python 3.10.

Run the repo's verified first-run path:

```bash
bash examples/first_run.sh
```

`bash examples/first_run.sh` also refreshes the manual-agent pack before printing `zmem status --summary-only`, so the final summary reports `Manual pack ready: yes`.

Connect agent clients to this project:

```bash
zmem connect codex --label current-chat

# Or connect several current agents to one shared workspace.
zmem connect codex claude-code hermes --label release-work
zmem status --summary-only
zmem doctor --agent codex --agent claude-code
```

`zmem connect` initializes the workspace once and prints one one-time `memory.session_attach` instruction per requested configured agent identity. Codex and Claude Code use directly written MCP entries. Hermes and other manual clients get a project-local export to import. Every generated entry points to the same absolute workspace database and carries its agent-host identity. List every host before command options. If one host setup fails, no invitation is issued. The per-process connection id is provenance, not a guaranteed UI chat id.

For individual or manual config work:

```bash
zmem agent install openclaw --summary-only
zmem agent pack --summary-only
zmem agent checklist openclaw
zmem agent checklist generic
zmem agent smoke --agent codex
zmem agent mcp-smoke --agent codex
```

For Cursor, OpenClaw, Hermes, or another generic MCP client, `zmem agent install <preset>` writes `.zerker/agents/<preset>-checklist.md` with the exact export path, doctor command, prompt path, snippet fallback, embedded fallback server JSON, and proof smoke. If you prefer a terminal-first walkthrough, run `zmem agent install <preset> --summary-only`. If the UI rejects whole-file JSON import, either use the embedded server block in the checklist or run `zmem agent snippet <preset>` and paste that server object as `zerker-memory`, then add `.zerker/AGENT_PROMPT.md` to the agent instructions. `zmem agent checklist <preset>` refreshes the same artifact on demand, and `zmem agent pack --summary-only` refreshes all manual-target exports plus the shared pack index while printing the exact next steps.

Mirror an external provider into review instead of trusting recall directly:

```bash
zmem provider init
zmem provider doctor
zmem provider doctor --live --mem0-base-url http://localhost:8888 --query "zerker smoke"
zmem provider search "deploy runbook" --provider mem0 --user-id <user>
zmem provider import "deploy runbook" --provider mem0 --scope project --type procedural
zmem queue --scope project
```

Export a verifiable action bundle after `zmem inject` returns an action ID:

```bash
zmem why <action-id>
zmem verify <action-id>
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
```

Export a portable memory-state snapshot:

```bash
zmem snapshot --out-dir .zerker/exports
```

Package both into a shareable handoff:

```bash
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
```

Verify a snapshot before sharing or restoring:

```bash
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
```

Restore a snapshot into a new empty store:

```bash
zmem --db .zerker/restored.sqlite restore .zerker/exports/<snapshot>.snapshot.json
```

Use a project policy config:

```bash
zmem --policy templates/policy.example.json inject "deploy the service" --agent codex --risk high
```

Start the local review console:

```bash
zmem --db .zerker/memory.sqlite ui
```

Try the behavior-tree recovery-memory demo:

```bash
zmem --db .zerker/bt.sqlite bt ingest examples/bt_trace.jsonl
zmem --db .zerker/bt.sqlite bt explain trace_demo_recovery --question "why did the robot fall back?"
```

Start the MCP server:

```bash
zmem --db .zerker/memory.sqlite mcp
```

Use [examples/mcp_config.example.json](examples/mcp_config.example.json) as the config shape for MCP-capable clients.
