# ZMem Builder Experience

ZMem should feel simple to add to an agent:

```text
Install locally -> connect the agent -> attach the memory instructions -> run a smoke check.
```

The product stays local-first. Agent clients connect through MCP or a shell wrapper, and every injected memory can be inspected through `why`, `verify`, receipts, and Merkle-backed proof.

## The Builder Loop

1. Bootstrap the local workspace.

```bash
bash install.sh
zmem status --summary-only
zmem ui
```

2. Connect the agent.

Direct config targets:

```bash
zmem agent install codex
zmem agent install claude-code
zmem doctor --agent codex --agent claude-code
```

Manual MCP import targets:

```bash
zmem agent install cursor --summary-only
zmem agent pack --summary-only
zmem doctor --agent cursor --agent openclaw --agent hermes --agent generic
```

3. Attach the agent instructions.

Every connected agent needs `.zerker/AGENT_PROMPT.md` in its project instructions, rules, or system prompt. That prompt tells the agent when to call `memory.inject`, when to write or propose memory, and when to explain memory usage with `memory.why`.

4. Prove the connection.

```bash
zmem agent smoke --agent codex
zmem agent mcp-smoke --agent codex
zmem agent smoke --agent cursor
zmem agent mcp-smoke --agent cursor
```

5. Use and continue.

```bash
zmem inject "continue release prep" --agent codex --risk medium --scope project
zmem why <action-id>
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
```

## Agent Connection Model

| Agent target | Setup mode | What ZMem writes | What the builder does |
| --- | --- | --- | --- |
| Codex | Direct install | `~/.codex/config.toml` MCP server block | Add `.zerker/AGENT_PROMPT.md` to repo instructions, then run smoke |
| Claude Code | Direct install | `~/.claude/mcp.json` MCP server entry | Add `.zerker/AGENT_PROMPT.md` to `CLAUDE.md` or project instructions, then run smoke |
| Cursor | Manual MCP import | `.zerker/agents/cursor-mcp.json` and `.zerker/agents/cursor-checklist.md` | Import the JSON or paste the server snippet, then add `.zerker/AGENT_PROMPT.md` to Cursor rules |
| OpenClaw | Manual MCP import | `.zerker/agents/openclaw-mcp.json` and checklist | Import or paste the server snippet, then attach the prompt |
| Hermes | Manual MCP import | `.zerker/agents/hermes-mcp.json` and checklist | Import or paste the server snippet, then attach the prompt |
| Generic MCP | Manual MCP import | `.zerker/agents/generic-mcp.json` and checklist | Use this for any MCP client that accepts stdio servers |

## What Agents Should Do In The Background

The background behavior is intentionally boring:

- Before work that needs memory, call `memory.inject` with the task, risk, scope, and agent id.
- Use only the injected memories, not every matching memory in the database.
- When memory affects an action, keep the `action_id` and call `memory.why` on demand.
- When the agent learns something durable, call `memory.remember` for trusted user facts or `memory.propose` for agent-found facts.
- For risky or external memory, leave it in the review queue until promoted.
- Before handoff, run `zmem handoff --summary-only` so the next agent receives the same governed state.

This keeps the user experience small while preserving provenance: the agent knows where memory came from, why it was allowed, and which selected-memory Merkle root backed the injected memory.

## Cursor And Other MCP Clients

Cursor is treated as a manual MCP import target. ZMem generates the config and checklist, but the builder imports it into Cursor because Cursor settings can vary by version and workspace.

```bash
zmem agent install cursor --summary-only
zmem agent snippet cursor
zmem doctor --agent cursor
zmem agent mcp-smoke --agent cursor
```

Use `zmem agent snippet cursor` when the UI wants only the `zerker-memory` server block instead of a whole JSON file.

## BX Acceptance Checklist

- A new builder can run `bash install.sh` and open `zmem ui`.
- Codex and Claude Code have direct install commands.
- Cursor and other MCP clients have project-local import files and checklists.
- The agent prompt is visible and copyable through `zmem agent prompt`.
- `doctor`, `agent smoke`, and `agent mcp-smoke` prove the setup.
- Dashboard cards show whether each target is direct config or manual import.
- Handoff/restore gives the next agent the same local memory state.
