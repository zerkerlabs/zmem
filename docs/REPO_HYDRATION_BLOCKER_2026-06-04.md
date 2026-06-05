## Repo Hydration Blocker - 2026-06-04

### 2026-06-04 21:54 EDT addendum

- `python3 -m zerker_memory eval` still passes locally (`11/11`), so the packaged runtime itself is not fully broken in this workspace.
- A fresh `python3 -m zerker_memory status --summary-only` attempt during orientation did not return promptly, which is consistent with the repo remaining only partially hydrated.
- `docs/CURRENT_STATE.md` is readable again in this workspace, but the broader required orientation set is still incomplete because `README.md`, `QUICKSTART.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `docs/DAY1_AGENT_SETUP.md`, `tests/test_release_smoke.py`, and `zerker_memory/cli.py` are still `compressed,dataless`.
- Treat this as a strict boundary: use the readable state docs for handoff only, but do not make new product-code claims or broad doc-sync edits until the dataless files are hydrated.

Phase: Phase 1 - Public Alpha Launch Gate

Top blocker:
The repository's tracked docs and source files are present as macOS `dataless` placeholders in this environment, so local reads fail with `Operation timed out` before code or status-doc updates can be done safely.

Evidence:
- Required first check passed: `GSTACK_OK`.
- `ls -lO` shows `compressed,dataless` on key files including `README.md`, `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `tests/test_release_smoke.py`, and `zerker_memory/cli.py`.
- Direct reads fail on those files with `Operation timed out` or generic read errors.
- This workspace is not its own git repo checkout; `git rev-parse --show-toplevel` resolves to `/Users/zzo`, so `git show HEAD:<path>` cannot recover the current project files.
- Sandbox restrictions prevent invoking `brctl` or `fileproviderctl` to hydrate the placeholders from iCloud/File Provider state.

Why this was the right next slice:
- The run instructions require reading current state docs before choosing work and require appending to `docs/BUILD_LOG.md` and updating `docs/CURRENT_STATE.md` after any slice.
- With the tracked files unreadable, guessing at code or doc changes would risk clobbering user state and violating the repo's surgical-change rules.
- Recording the exact blocker gives the next run a fast diagnosis path and preserves the Phase-1 focus.

What to do next once files are hydrated:
1. Re-run the required orientation pass against `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `README.md`, `QUICKSTART.md`, `docs/DAY1_AGENT_SETUP.md`, and automation memory.
2. Confirm whether the Phase-1 blocker is still the external publish/install proof plus eight launch assets.
3. If yes, take one local-adjacent slice only: launch-proof polish, strict verifier tightening, or clean-shell checklist refinement.

Commands/results from this run:
- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`
- `ls -lO README.md docs/CURRENT_STATE.md tests/test_release_smoke.py zerker_memory/cli.py`
  - all showed `compressed,dataless`
- `wc`, `head`, and `rg` against the core docs failed with `Operation timed out`
- `brctl download ...` and `fileproviderctl ...` were rejected from the sandbox
