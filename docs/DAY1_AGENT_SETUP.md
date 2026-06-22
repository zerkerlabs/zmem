# Day-1 Agent Setup

Use Zerker Memory when you want an agent to keep long-term memory, but only let approved memory influence action.

The day-1 path is:

```bash
bash install.sh
```

The installer ends by printing `zmem status --summary-only`, so the first successful run leaves you at the readiness summary without another command.
It also runs `zmem agent smoke` and `zmem agent mcp-smoke` against the selected bootstrap target, defaulting to OpenClaw for the safe manual-pack path.

The installer creates `.venv`, installs Zerker Memory, initializes `.zerker/`, runs eval and doctor, generates the manual-agent pack, and runs both day-1 smoke commands. It does not write into Codex or Claude config files unless you opt in:

```bash
ZERKER_MEMORY_AGENT=codex bash install.sh
ZERKER_MEMORY_AGENT=claude-code bash install.sh
ZERKER_MEMORY_AGENT=cursor bash install.sh
ZERKER_MEMORY_AGENT=openclaw bash install.sh
ZERKER_MEMORY_AGENT=hermes bash install.sh
ZERKER_MEMORY_AGENT=generic bash install.sh
```

Manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config
zmem status --summary-only
zmem eval
zmem doctor
```

If you want the same flow as a single verified script, run:

```bash
bash examples/first_run.sh
```

`bash examples/first_run.sh` also refreshes the manual-agent pack before printing `zmem status --summary-only`, so the final readiness view already includes the shareable handoff artifacts. In the full repo, that same status view now also shows whether release artifacts are the missing step, whether the clean-shell public-verify logs exist yet, the exact capture checklist, launch-asset handoff, public-verify handoff/script/result/archive paths, the receive-side `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md`, the generated `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` self-check step, the outbound `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, and tells the operator to hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` after the clean-shell pass, `zmem verify-public-verify --summary-only`, asset capture, `zmem verify-launch-assets --summary-only`, and finalize step. Before you forward that outbound bundle to another chat or clean shell, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` if you want a local check that the packet still contains the shipped manifest, handoffs, script, finalize step, placeholder result, and return archive; that summary now also prints the exact six-log command map, pair that bundle with `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, and note that the release summaries now also repeat the exact triplet to send together: `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz`. On the clean shell, unpack that archive back into `.zerker/launch-proof/` and open `CLEAN_SHELL_PUBLIC_VERIFY.md` before running `PUBLIC_VERIFY_COMMANDS.sh`. After the clean-shell script finishes, run `zmem verify-public-verify --summary-only` to validate the saved logs and receipt before the screenshot pass; that verifier now also restates the packet-local operator prompt, the start-here runbook, the unpack command, the same outbound triplet, and the exact six-log command map so the next orchestrator chat can continue from one summary. Once that archive comes back, run `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` before you mark the external proof handoff complete, or hand the receiving chat `RECEIVE_VERIFY_HANDOFF.md` so it follows the same acceptance checklist; that receive-side summary now also restates the logs root, `packaged` install requirement, pinned public targets, and the rerun-then-finalize contract before another handback attempt. It still points at `zmem release-pack --summary-only` when launch-proof or handoff needs to be refreshed together, and once those artifacts exist it keeps the next-step list focused on the remaining Phase-1 operator packet, clean-shell proof, launch asset, and return-packet work instead of generic smoke prompts. If the shell `python3` is too old, direct `python3 -m zerker_memory doctor` and `python3 -m zerker_memory status --summary-only` now auto-reexec with a discovered Python 3.10+ interpreter when one is available on `PATH` or through `pyenv`; if none is available, the output tells users to start with `bash install.sh` and prints a discovered Python 3.10+ `-m venv .venv` fallback when possible.
The `zmem status --summary-only` next-step list now also explicitly tells the operator to rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` and confirm `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` before handback, so the day-1 readiness screen already carries the receive-side acceptance rule.
If a separate chat or operator is taking the remaining public-launch work, start with [docs/CLEAN_SHELL_VERIFICATION_CHECKLIST.md](CLEAN_SHELL_VERIFICATION_CHECKLIST.md) for the shortest durable checklist, then use [docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md](PHASE1_EXTERNAL_OPERATOR_BRIEF.md) for the one-file send, run, capture, and accept loop.
For the durable repo-level operator brief outside generated `.zerker/launch-proof/` state, see [docs/CLEAN_SHELL_PUBLIC_VERIFY.md](CLEAN_SHELL_PUBLIC_VERIFY.md).
For the durable repo-level copy-ready chat prompt, see [docs/CLEAN_SHELL_OPERATOR_PROMPT.md](CLEAN_SHELL_OPERATOR_PROMPT.md).
For the durable repo-level capture board, see [docs/LAUNCH_ASSET_BOARD.html](LAUNCH_ASSET_BOARD.html).
Fresh launch-proof packs also copy that runbook into `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` and the prompt into `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` so the outbound operator packet stays self-contained, and the generated `.zerker/launch-proof/index.html` report now surfaces that same operator prompt, runbook, and outbound packet triplet in one clean-shell section.

When you need launch-ready proof after setup, run `zmem release-pack --summary-only` for the shortest repo-local refresh; that summary now also pins the exact public repo URL, raw installer URL, packet-local runbook, six-log proof contract, and eight-shot launch-asset cue map the clean-shell operator must use first. Then open `.zerker/launch-proof/index.html`, `.zerker/launch-proof/launch-proof.json`, `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, `.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md`, `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md`, `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md`, `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, `.zerker/launch-proof/public-verify-summary.md`, `.zerker/launch-proof/public-verify-return-packet.tar.gz`, and `.zerker/launch-proof/assets/` before recording screenshots or the console demo. Keep `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` beside that pack and, after the assets are saved, run `zmem verify-launch-assets --summary-only` and then the finalize script so the return archive is rebuilt and self-checked before handback. `launch-proof.json` now also carries the machine-readable public verify contract plus the launch-asset storyboard, so separate chats can hand off the exact `ui-release-pack`, `handoff-restore-terminal`, and `ui-handoff-restore` deliverables plus their `assets/...` output paths instead of improvising the final captures, and the generated handoffs/checklists now explicitly tell the clean-shell operator which log files, launch assets, result receipt, compact run summary, and return-packet roots have to come back or be bundled as one tarball while `RECEIVE_VERIFY_HANDOFF.md` tells the orchestrator exactly how to accept that packet. The generated `PUBLIC_VERIFY_CHECKLIST.md`, `CAPTURE_CHECKLIST.md`, and repo-level `docs/CLEAN_SHELL_PUBLIC_VERIFY.md` now also include the exact clean-shell command-to-log map plus the success cue each saved log must show, so the handback proof is auditable from one screen. Forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` when you want that clean-shell operator to receive the generated brief, checklist, script, README/report, placeholder return artifacts, and receive-side brief as one file before they start, and run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` if you want to prove that outbound archive locally before it leaves your machine. If you only want the proof bundle without refreshing handoff or prelaunch, run `zmem launch-proof --summary-only`. Both summary-only commands now also report whether that archive is still pending evidence or actually ready to hand back, and `public-verify-result.json` now records whether the proof run is still pending, failed, or passed plus the observed release-smoke `install_mode` when the script can detect it while `public-verify-summary.md` now also shows the outbound triplet, launch-asset progress, the capture checklist, the verify-before-assets and receive-side acceptance commands, the finalize step, the return archive path, and the expected asset list so another chat can inspect the full handback contract without opening raw logs. `zmem verify-launch-assets --summary-only` now also prints the full eight-shot storyboard inline, including each deliverable filename, capture ID, source command, capture cue, and `assets/...` output path, and now points directly at `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` as the capture-ready surface for the screenshot pass. `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` verifies the returned archive on the receiving side. If you are already in `zmem ui`, the console now has a matching release-pack action plus launch-proof, handoff, handoff-restore, launch-asset verification, and return-packet verification actions so you can generate and receive those release artifacts without leaving the review surface, and the release panel now shows the live operator-packet state, public-verify summary/runbook, and exact missing clean-shell logs and launch assets together with the checklist, result, and return-packet state that still need to be completed. Before tagging, run `python3 scripts/release_smoke.py`; it now also proves `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` before the launch-assets and return-packet checks, alongside the strict `zmem prelaunch --summary-only` publish gate. If you only need the current repo-local Phase-1 preflight, run `python3 scripts/release_smoke.py --summary-only`; it refreshes `release-pack`, reruns `zmem status --summary-only` after that refresh so the terminal ends on the current operator packet state, verifies the operator packet, checks launch assets and the return packet, and reruns the strict prelaunch gate without creating a fresh temp install. For the final public clean-shell proof, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`; the generated public verify script will save operator-packet preflight, install, first-run, release-pack, release-smoke, and prelaunch logs into `.zerker/launch-proof/public-verify-logs/`, overwrite `.zerker/launch-proof/public-verify-result.json` with the machine-readable pass/fail receipt, refresh `.zerker/launch-proof/public-verify-summary.md` with the compact run summary plus the launch-asset/finalize contract, refresh `.zerker/launch-proof/public-verify-return-packet.tar.gz` for one-file handoff, and still fail if the run falls all the way back to local wrappers instead of `editable`, `editable-no-build-isolation`, or `venv-pth`.

The `zmem release-pack --summary-only` output now also states the explicit Phase-1 completion contract and inlines the same command-log and launch-asset cue maps used by the verifier surfaces, so the shortest local release refresh is also a durable handoff brief.
For the durable repo-level screenshot/GIF fallback brief, see [docs/LAUNCH_ASSET_OPERATOR_PROMPT.md](LAUNCH_ASSET_OPERATOR_PROMPT.md).
For the durable repo-level visual capture board, see [docs/LAUNCH_ASSET_BOARD.html](LAUNCH_ASSET_BOARD.html).

This creates:

```text
.zerker/memory.sqlite
.zerker/policy.json
.zerker/AGENT_PROMPT.md
.zerker/mcp.json
.zerker/providers.json
```

## The Product Contract

Zerker Memory works with any agent or workflow that can do at least one of these:

- connect to a stdio MCP server,
- run shell commands,
- call Python code,
- read a JSON memory context file,
- share or import a verified snapshot.

If an environment cannot call tools, run commands, or receive injected context, Zerker can still store memory for you, but that environment will not automatically use it.

## MCP-Capable Agents

For Codex, Claude Code, Cursor, OpenClaw, Hermes, and other MCP-capable agents, use a preset:

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
zmem agent pack --summary-only
zmem agent checklist cursor
zmem agent checklist openclaw
zmem agent checklist hermes
zmem agent checklist generic
```

Equivalent config shape:

```json
{
  "mcpServers": {
    "zerker-memory": {
      "command": "zmem",
      "args": [
        "--db",
        ".zerker/memory.sqlite",
        "--policy",
        ".zerker/policy.json",
        "mcp"
      ]
    }
  }
}
```

`zmem agent install codex` writes the Zerker MCP server into `~/.codex/config.toml`.
`zmem agent install claude-code` writes the Zerker MCP server into `~/.claude/mcp.json`.
Run `zmem doctor --agent codex` or `zmem doctor --agent claude-code` after install to verify the real local config contains the Zerker MCP server and that `.zerker/AGENT_PROMPT.md` exists.
Run `zmem status --summary-only` any time you want a one-screen terminal summary of the local workspace, proof counts, and manual-agent handoff artifacts before you dive into the deeper checks. In the repo itself, that summary also shows launch-proof, handoff, and prelaunch gate state so operators can see the next release blocker without running another command. Once the workspace is ready, that summary now chooses its suggested smoke commands from the configured agent artifacts it finds and points at `zmem release-pack --summary-only` when either release artifact set is stale or missing, so manual-target installs no longer get Codex-only next steps. For the local review path, `zmem ui` now surfaces the same release readiness and can run the combined release-pack flow or the lower-level launch-proof and handoff artifact actions directly.
For Cursor, OpenClaw, Hermes, generic MCP clients, and other manual-target presets, `zmem agent install <preset>` writes a project-local export under `.zerker/agents/` and a matching `.zerker/agents/<preset>-checklist.md`. The install JSON also includes an `install_preview` block with the exact import path, doctor command, snippet fallback, and prompt path so the first import step is visible immediately in CLI output, plus a post-install `doctor` block that proves the prompt and written config passed verification in the same command. Use `zmem agent install <preset> --summary-only` for a compact text walkthrough of one target. Run `zmem doctor --agent cursor`, `zmem doctor --agent openclaw`, `zmem doctor --agent hermes`, or `zmem doctor --agent generic` to verify that exported config file again later before you paste or import it into the agent. If you exported to a custom path, use `zmem doctor --agent-config <preset>=/path/to/config.json`.
If you want to refresh the shareable proof checklist directly, run `zmem agent checklist <preset>`. That rewrites `.zerker/agents/<preset>-checklist.md` with the config path, prompt path, doctor command, snippet fallback, embedded server block, and proof smoke. If you want all manual-target artifacts in one handoff, run `zmem agent pack --summary-only`; it refreshes Cursor, OpenClaw, Hermes, generic, the shared `.zerker/agents/manual-agent-pack.md` index, and prints the exact import/verify steps.
If you want Zerker to print the install/import path as plain text instead of returning JSON, run `zmem agent guide <preset>` first.
If you want the install command itself to print that compact operator view, run `zmem agent install <preset> --summary`, or use `--summary-only` for text without JSON. For the combined manual-target path, use `zmem agent pack --summary-only`.

Copy-ready manual import path:

- OpenClaw: open MCP or tool-server settings, import the generated JSON file if the UI supports whole-file import, otherwise run `zmem agent snippet openclaw` and paste the output into a server named `zerker-memory`, then add `.zerker/AGENT_PROMPT.md` to the policy/system prompt.
- Hermes: open stdio tool or MCP server settings, import the generated JSON file if supported, otherwise run `zmem agent snippet hermes` and paste the output into a server named `zerker-memory`, then add `.zerker/AGENT_PROMPT.md` to the runtime instructions.
- Generic MCP agents: follow the same pattern and copy only the `zerker-memory` server entry if the UI does not accept the whole exported file.

Example guide commands:

```bash
zmem agent guide codex
zmem agent guide claude-code
zmem agent guide openclaw
zmem agent guide hermes
zmem agent guide generic
zmem agent checklist openclaw
zmem agent checklist hermes
zmem agent checklist generic
```

For the default project-local export path, those guides now follow the short path directly: `zmem agent install cursor|openclaw|hermes|generic` plus `zmem doctor --agent <preset>`. Keep `--config-path` for cases where you need the export somewhere else.

For other agents, add the generated server to the agent MCP configuration manually, then add `.zerker/AGENT_PROMPT.md` to the agent instructions.

Print the instruction prompt any time:

```bash
zmem agent prompt
```

Verify the MCP server over the actual stdio protocol:

```bash
zmem agent mcp-smoke --agent codex
```

The agent loop is:

```text
Before task: memory.inject
During task: use only injected memories
After task: memory.propose
Review: memory.queue, memory.promote, memory.reject, memory.revoke
Audit: memory.why, memory.verify
```

## Shell-Based Agents

For agents or scripts that can run a command but do not support MCP, wrap the command:

```bash
zmem run \
  --agent codex \
  --task "ship the release" \
  --risk medium \
  --scope project \
  -- your-agent-command
```

The wrapped command receives:

```text
ZERKER_ACTION_ID
ZERKER_MEMORY_CONTEXT
ZERKER_MEMORY_DB
ZERKER_MEMORY_MERKLE_ROOT
```

`ZERKER_MEMORY_CONTEXT` is a JSON file with authorized memories, withheld memories, policy checks, and the Merkle root at decision time.

## Permanent Chat Windows

For long-running chats such as a persistent Kimi, Claude, or browser chat instance, Zerker Memory can provide long-term memory if there is a bridge that can inject context into the chat.

Good bridges:

- MCP tool calls,
- a local wrapper that copies `memory.inject` output into the prompt,
- browser automation that prepends approved memory,
- an agent runtime that reads `ZERKER_MEMORY_CONTEXT`.

Without a bridge, Zerker still keeps the memory locally, but the chat window will not know to retrieve it.

## Existing Memory Providers

Use provider recall as candidates, not authority:

```bash
zmem provider init
zmem provider doctor
zmem provider search "deployment rules" --provider mem0 --user-id <user>
zmem provider import "deployment rules" --provider mem0 --scope project --type procedural
zmem queue --scope project
```

Imported provider memories start in quarantine by default.

## Proof And Portability

After an action:

```bash
zmem why <action-id>
zmem verify <action-id>
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
```

Export the whole local memory state:

```bash
zmem snapshot --out-dir .zerker/exports
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
```

Restore into a fresh store:

```bash
zmem --db .zerker/restored.sqlite restore .zerker/exports/<snapshot>.snapshot.json
```

If you want one shared-memory transfer artifact instead of running those steps separately:

```bash
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
```

This writes `.zerker/handoff/README.md`, `handoff.json`, the verified snapshot, the latest action bundle if one exists, and a Treeship-ready statement for that action, so the receiving machine can verify, restore, and dry-run publish with the exact commands already written down.

## Day-1 Smoke

Run this after wiring an agent:

```bash
zmem agent smoke --agent codex
zmem agent mcp-smoke --agent codex
zmem why <action-id>
zmem verify <action-id>
```

If `zmem inject` returns an `action_id`, the agent has a verifiable memory decision.
