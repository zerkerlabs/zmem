#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="${ZERKER_LAUNCH_PROOF_DIR:-$REPO_ROOT/.zerker/launch-proof}"

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

PYTHON_BIN="$(pick_python)" || {
  echo "Zerker Memory launch proof requires Python 3.10+." >&2
  exit 1
}

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON_BIN" -m zerker_memory launch-proof --out-dir "$OUT_DIR"
