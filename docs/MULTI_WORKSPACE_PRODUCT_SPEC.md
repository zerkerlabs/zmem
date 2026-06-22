# Multi-Workspace Product Spec

ZMem currently works as a project-local memory store: one `.zerker/memory.sqlite`, one `.zerker/policy.json`, one set of agent configs. That is enough for dogfooding inside one repo, but the product needs a first-class way to manage multiple projects, agents, and sessions.

## Implementation Status

First slice shipped on 2026-06-06:

- `~/.zmem/workspaces.json` registry helpers with `ZMEM_WORKSPACE_REGISTRY` override.
- `zmem workspace register/list/current/use/status` and `zmem ws` alias.
- best-effort project registration during `zmem init`.
- profile state in `zmem status --summary-only`.
- console `Workspace Profile` panel and `/api/state.workspace_profile`.

Still pending:

- console workspace switcher.
- per-profile agent cards and profile-specific agent install.
- workspace identity in receipts and proof summaries.
- MCP tools for workspace list/current/switch.

## Product Problem

A real user may have:

- several Codex projects,
- several Claude Code projects,
- long-running browser or desktop chat sessions,
- manual MCP clients such as Cursor, OpenClaw, Hermes, or another agent,
- private personal/global memory,
- project-specific memory,
- team or handoff memory restored from another machine.

They need to know:

- which memory store an agent is connected to,
- which project each store belongs to,
- whether a session is using global, project, or imported memory,
- how to switch safely,
- how to verify what memory influenced an action,
- how to avoid leaking one project's memory into another project.

## Product Model

ZMem should treat each memory store as a named workspace profile.

```text
Profile
  id: zmem-local-id
  name: Human-readable project name
  root: /path/to/project
  db_path: /path/to/project/.zerker/memory.sqlite
  policy_path: /path/to/project/.zerker/policy.json
  prompt_path: /path/to/project/.zerker/AGENT_PROMPT.md
  agents:
    codex: connected / not connected
    claude-code: connected / not connected
    cursor: export path
    openclaw: export path
  status:
    memories, receipts, queue, proof roots
    last action, last verified, handoff ready
```

The registry should live outside any single project:

```text
~/.zmem/workspaces.json
```

Project-local state remains where it is:

```text
<project>/.zerker/memory.sqlite
<project>/.zerker/policy.json
<project>/.zerker/AGENT_PROMPT.md
<project>/.zerker/agents/*.json
```

## Core Commands

Minimum viable product commands:

```bash
zmem workspace register --name "Zerker Memory" --root .
zmem workspace list
zmem workspace status
zmem workspace use <name-or-id>
zmem workspace current
zmem workspace open <name-or-id>
zmem workspace agents <name-or-id>
zmem workspace install-agent <name-or-id> --agent codex
zmem workspace forget <name-or-id>
```

Recommended aliases:

```bash
zmem ws list
zmem ws use zmem
zmem ws current
```

The CLI should never silently switch a global agent config without showing:

- old profile,
- new profile,
- db path,
- policy path,
- affected agent config path.

## Console UX

The console should become a profile-aware control room.

First screen:

- active profile name,
- project root,
- DB path,
- policy path,
- connected agents,
- memory/receipt counts,
- proof roots,
- strict warnings if the agent config points at a different profile than the console.

Workspace switcher:

- list all registered profiles,
- search by project name/path,
- show connected agents per profile,
- open profile console,
- copy MCP config for selected profile,
- install/update Codex or Claude Code config for selected profile.

Profile cards:

- `Personal / global`
- `Project`
- `Imported handoff`
- `Archived`

The console should make cross-project leakage obvious:

```text
Codex is connected to: /project-a/.zerker/memory.sqlite
Console is viewing:    /project-b/.zerker/memory.sqlite
Status: mismatch
```

## Agent Binding Rules

Agents should bind to explicit profiles. A running agent should be able to ask:

```text
memory.workspace_current
memory.workspace_list
memory.workspace_switch
```

But switching from inside an agent must be policy-controlled. Safer default:

- agents can read current profile,
- agents can list allowed profiles,
- agents cannot switch profile unless explicitly allowed by policy or human review.

For Codex and Claude Code, the install commands should be profile-specific:

```bash
zmem workspace install-agent zmem --agent codex
zmem workspace install-agent gateway --agent claude-code
```

The installed MCP command should use absolute paths so the same agent config works regardless of shell cwd.

## Memory Scope

ZMem should support three useful layers:

1. Global/private memory
   - user preferences,
   - durable personal procedures,
   - cross-project agent operating rules.

2. Project memory
   - repo facts,
   - product decisions,
   - benchmark results,
   - launch state,
   - project-specific policies.

3. Imported/handoff memory
   - restored from another agent or machine,
   - reviewed before promotion into project memory,
   - always visibly labeled as imported.

Initial implementation can keep these as separate profiles. Later, a profile can optionally mount another profile as a read-only upstream.

## Proof Requirements

Every action receipt should include profile identity:

```json
{
  "workspace": {
    "profile_id": "...",
    "name": "Zerker Memory",
    "db_path_hash": "...",
    "policy_path_hash": "...",
    "memory_merkle_root": "..."
  }
}
```

The proof view should answer:

- which profile was active,
- which DB was used,
- which policy was applied,
- which roots were proven,
- which outcome fields were asserted.

This matches the Treeship boundary model: profile roots and committed hashes are proof material; human labels and provider outcome text are asserted metadata.

## First Build Slice

The smallest useful implementation:

1. Add registry helpers for `~/.zmem/workspaces.json`.
2. Add `zmem workspace register/list/current/use/status`.
3. Register the current project automatically during `zmem init`.
4. Add profile metadata to `zmem status --summary-only`.
5. Add console workspace banner and mismatch warning.
6. Add tests for:
   - registering two projects,
   - switching current profile,
   - rendering profile status,
   - ensuring agent install uses the selected profile's absolute DB/policy paths.

## Second Build Slice

1. Add console workspace switcher.
2. Add per-profile agent cards.
3. Add profile-specific `agent install`.
4. Add MCP tools for `workspace_current` and `workspace_list`.
5. Add profile identity into receipts.

## Third Build Slice

1. Add global/private profile.
2. Add read-only upstream mounts.
3. Add handoff/import profile type.
4. Add policy controls for profile switching.
5. Add proof UI for profile identity.

## Launch Positioning

The product should explain this simply:

```text
ZMem gives every project its own memory profile.
Agents connect to a profile, not a vague global brain.
You can switch, verify, hand off, and prove which memory profile influenced every action.
```

That is the bridge from one local SQLite file to a real multi-agent memory product.
