# Chat-To-Chat Memory Bridge

ZMem can connect separate agent chats in three simple ways. The important rule is that shared memory should be visible, scoped, and reviewable, not silently mixed into a new chat.

## Same Workspace

When two chats use the same repository and the same `.zerker/` store, they are already connected through local memory.

Use this at the start of the next chat:

```bash
zmem status --summary-only
zmem search "current launch state" --scope project
zmem inject "continue the ZMem launch work" --agent codex --scope project --risk medium
```

The next agent should use only the injected memories as durable context. If something is missing, it should ask for it or propose a new memory.

## Paste A Chat Summary

When a user pastes a summary from another chat, store it as proposed or quarantined memory first:

```bash
zmem propose "Cross-chat checkpoint: ..." --type episodic --scope project --source agent --label cross-chat-checkpoint
zmem queue --scope project --status quarantined
```

After review, promote the accepted memory:

```bash
zmem promote <memory-id>
```

This gives the next chat searchable context immediately, while preventing unreviewed agent summaries from becoming authoritative memory by default.

## Separate Workspace Or Machine

When the next chat is in another checkout or machine, export a handoff:

```bash
zmem agent pack --summary-only
zmem handoff --summary-only
```

Then restore it in the receiving workspace:

```bash
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
zmem status --summary-only
```

The handoff includes the prompt, verified snapshot, receipt bundle when available, and restore instructions. That is the portable version of "continue from the same memory."

## Operator Rule

Agents should not invent continuity from chat history. They should either:

- call `memory.inject` from the shared local store,
- propose a pasted checkpoint for review,
- or restore a verified handoff package.

That keeps multi-chat work fast without turning memory into an opaque transcript blob.
