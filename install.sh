#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${ZERKER_MEMORY_REPO_URL:-https://github.com/zerkerlabs/zmem.git}"
INSTALL_DIR="${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}"
AGENT="${ZERKER_MEMORY_AGENT:-manual-pack}"
SMOKE_AGENT="openclaw"

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

if [ -f "./pyproject.toml" ] && grep -q 'name = "zerker-memory"' "./pyproject.toml"; then
  REPO_DIR="$(pwd)"
else
  REPO_DIR="$INSTALL_DIR/repo"
  if [ ! -d "$REPO_DIR/.git" ]; then
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone --depth 1 "$REPO_URL" "$REPO_DIR"
  else
    git -C "$REPO_DIR" pull --ff-only
  fi
fi

PYTHON_BIN="$(pick_python)" || {
  echo "Zerker Memory requires Python 3.10+." >&2
  echo "Install Python 3.10+ or configure pyenv, then rerun this installer." >&2
  exit 1
}

cd "$REPO_DIR"
"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
SITE_PACKAGES="$(python - <<'PY'
import sysconfig
print(sysconfig.get_path("purelib"))
PY
)"
write_repo_path_bootstrap() {
  mkdir -p "$SITE_PACKAGES"
  printf '%s\n' "$REPO_DIR" > "$SITE_PACKAGES/zerker_memory_repo.pth"
}
if python -m pip install -e .; then
  write_repo_path_bootstrap
else
  echo "Editable install with build isolation failed; retrying with local build backend." >&2
  if python -m pip install -e . --no-build-isolation; then
    write_repo_path_bootstrap
  else
    echo "Editable install could not fetch or build packaging dependencies; creating venv-local import bootstrap." >&2
    write_repo_path_bootstrap
    cat > .venv/bin/zmem <<EOF
#!/usr/bin/env bash
exec "$REPO_DIR/.venv/bin/python" -m zerker_memory "\$@"
EOF
    cat > .venv/bin/zerker-memory <<EOF
#!/usr/bin/env bash
exec "$REPO_DIR/.venv/bin/python" -m zerker_memory "\$@"
EOF
    cat > .venv/bin/zerker <<EOF
#!/usr/bin/env bash
exec "$REPO_DIR/.venv/bin/python" -m zerker_memory "\$@"
EOF
    cat > .venv/bin/zerker-memory-mcp <<EOF
#!/usr/bin/env bash
exec "$REPO_DIR/.venv/bin/python" -m zerker_memory.mcp "\$@"
EOF
    chmod +x .venv/bin/zmem .venv/bin/zerker-memory .venv/bin/zerker .venv/bin/zerker-memory-mcp
  fi
fi

zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config
zmem eval
zmem doctor
zmem agent pack --summary-only

case "$AGENT" in
  "")
    SMOKE_AGENT="openclaw"
    ;;
  manual-pack)
    SMOKE_AGENT="openclaw"
    ;;
  codex|claude-code)
    zmem agent install "$AGENT"
    zmem doctor --agent "$AGENT"
    SMOKE_AGENT="$AGENT"
    ;;
  cursor|openclaw|hermes|generic)
    zmem agent install "$AGENT" --summary-only
    zmem doctor --agent "$AGENT"
    SMOKE_AGENT="$AGENT"
    ;;
  all)
    zmem agent install codex
    zmem agent install claude-code
    zmem doctor --agent codex --agent claude-code
    SMOKE_AGENT="codex"
    ;;
  *)
    echo "Unsupported ZERKER_MEMORY_AGENT=$AGENT" >&2
    echo "Use manual-pack, codex, claude-code, openclaw, hermes, generic, or all." >&2
    exit 1
    ;;
esac

zmem agent smoke --agent "$SMOKE_AGENT"
zmem agent mcp-smoke --agent "$SMOKE_AGENT"
zmem status --summary-only

cat <<EOF

Zerker Memory is ready.

Repo: $REPO_DIR
Activate: cd "$REPO_DIR" && source .venv/bin/activate
Console: zmem ui
MCP: zmem mcp
Smoke target: $SMOKE_AGENT
Manual agent pack: $REPO_DIR/.zerker/agents/manual-agent-pack.md

EOF
