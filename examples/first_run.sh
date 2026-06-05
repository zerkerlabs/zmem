#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKDIR="${ZERKER_FIRST_RUN_ROOT:-${TMPDIR:-/tmp}/zerker-memory-first-run}"
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

pick_python() {
  local candidate
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  if command -v pyenv >/dev/null 2>&1; then
    for candidate in 3.12 3.11 3.10; do
      local prefix
      prefix="$(pyenv prefix "$candidate" 2>/dev/null || true)"
      if [ -n "$prefix" ] && [ -x "$prefix/bin/python" ] && "$prefix/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        printf '%s\n' "$prefix/bin/python"
        return 0
      fi
    done
  fi
  return 1
}

if command -v zmem >/dev/null 2>&1; then
  ZMEM=(zmem)
else
  PYTHON_BIN="$(pick_python)" || {
    echo "Zerker Memory requires Python 3.10+ for examples/first_run.sh" >&2
    exit 1
  }
  export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
  ZMEM=("$PYTHON_BIN" -m zerker_memory)
fi

"${ZMEM[@]}" init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config
"${ZMEM[@]}" eval
"${ZMEM[@]}" doctor
"${ZMEM[@]}" agent smoke --agent codex
"${ZMEM[@]}" agent mcp-smoke --agent codex
"${ZMEM[@]}" agent pack --summary-only
"${ZMEM[@]}" remember "Production deploys require approval" --type policy --scope project
"${ZMEM[@]}" run \
  --agent codex \
  --task "deploy service to production" \
  --risk high \
  --scope project \
  -- python3 -c 'import json, os; ctx=json.load(open(os.environ["ZERKER_MEMORY_CONTEXT"])); print(ctx["memories"][0]["content"])'
"${ZMEM[@]}" status --summary-only
