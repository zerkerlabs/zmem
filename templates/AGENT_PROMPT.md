# ZMem Agent Prompt

Use ZMem as your durable memory layer.

ZMem helps you:

- request approved memory before you act,
- avoid stale, revoked, or unreviewed memory,
- propose new durable memory without making it authoritative yourself,
- explain which memories influenced an action,
- hand off governed memory state to another agent.

Treat ZMem as a memory tool, not as free-form background context.

Before starting a task, call `memory.inject` with:

- `task`
- `agent`
- `risk`
- `scope`

Use only returned `memories` as durable memory context. Do not rely on remembered facts from prior chat unless ZMem injects them for the current task.

Treat `withheld` memories as unavailable and non-authoritative.

After completing a task, call `memory.propose` for durable facts, procedures, preferences, failed attempts, recovery notes, and policy candidates worth remembering.

Do not promote your own memories. Promotion requires a human or configured authority.

When memory shaped an action, keep the returned `action_id`. When asked why memory influenced an action, call `memory.why` with that action id.

For risky or disputed memory, ask the user to review `memory.queue`, then use `memory.promote`, `memory.reject`, or `memory.revoke`.

Before handing work to another agent, prefer `zmem agent pack --summary-only` or `zmem handoff --summary-only` so the next agent receives the same governed memory state and prompt.

When a user provides a summary from another chat, do not treat it as permanent memory automatically. Call `memory.propose` or `zmem propose` with a clear cross-chat label, then ask for review or promotion before relying on it as authoritative memory.

When continuing in the same workspace, call `memory.inject` for the task rather than replaying chat history. When continuing in another workspace, restore the handoff package first.
