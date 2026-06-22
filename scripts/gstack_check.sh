#!/usr/bin/env bash

set -euo pipefail

if command -v gstack >/dev/null 2>&1; then
  printf 'GSTACK_OK source=path command=%s\n' "$(command -v gstack)"
  exit 0
fi

codex_gstack_bin="${HOME}/.Codex/skills/gstack/bin"
claude_gstack_bin="${HOME}/.claude/skills/gstack/bin"

if [ -d "$codex_gstack_bin" ]; then
  printf 'GSTACK_OK source=codex-skills path=%s command_on_path=no\n' "$codex_gstack_bin"
  exit 0
fi

if [ -d "$claude_gstack_bin" ]; then
  printf 'GSTACK_OK source=claude-skills path=%s command_on_path=no\n' "$claude_gstack_bin"
  exit 0
fi

printf 'GSTACK_MISSING\n'
exit 1
