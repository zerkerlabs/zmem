# GitHub Release Checklist

## Before Public Alpha Proof

- Confirm product name: `zmem`.
- Confirm license: MIT.
- Confirm public positioning: "Governed memory for agents that act."
- Confirm the target public repo is `zerkerlabs/zmem`.
- Confirm the target raw installer URL is `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`.
- Create or publish the repo at `zerkerlabs/zmem` before attempting live clean-shell proof.
- After the repo is live, verify the raw installer URL from a clean shell:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
```

- Remove or ignore local `.zerker/` databases.
- Run verification in Python 3.10+.
- Complete [PUBLIC_LAUNCH_AUDIT.md](PUBLIC_LAUNCH_AUDIT.md).
- Use [PHASE1_EXTERNAL_OPERATOR_BRIEF.md](PHASE1_EXTERNAL_OPERATOR_BRIEF.md) as the one-file outbound clean-shell plus asset-capture brief.
- Use [CLEAN_SHELL_PUBLIC_VERIFY.md](CLEAN_SHELL_PUBLIC_VERIFY.md) as the stable send/receive runbook for the final public installer proof.
- Use [LAUNCH_ASSET_BOARD.html](LAUNCH_ASSET_BOARD.html) as the durable capture-ready board if the generated packet-local board has not been refreshed yet.
- Treat Phase 1 as complete only when `zmem verify-public-verify --summary-only` reports ready, `zmem verify-launch-assets --summary-only` reports `8/8 captured`, and `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

## Required Files

- `README.md`
- `QUICKSTART.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `pyproject.toml`
- `setup.py`
- `.gitignore`
- `.github/workflows/test.yml`
- `scripts/release_smoke.py`
- `zmem launch-proof`
- `scripts/launch_proof.sh`
- `docs/`
- `docs/PUBLIC_LAUNCH_AUDIT.md`
- `examples/`
- `tests/`
- `landing/`
- `templates/policy.example.json`

## Verification

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
python3 -m unittest discover -s tests
zmem eval
zmem --db /tmp/zerker-bt.sqlite bt ingest examples/bt_trace.jsonl
zmem --db /tmp/zerker-bt.sqlite bt explain trace_demo_recovery --question "why did the robot fall back?"
zmem snapshot --out-dir .zerker/exports
zmem snapshot verify .zerker/exports/<snapshot>.snapshot.json
zmem bundle <action-id> --out-dir .zerker/exports
zmem bundle verify .zerker/exports/<bundle>.bundle.json
zmem --db .zerker/restored.sqlite restore .zerker/exports/<snapshot>.snapshot.json
zmem doctor
bash examples/first_run.sh
bash install.sh
zmem launch-proof --summary-only
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
zmem verify-public-verify --summary-only
zmem verify-launch-assets --summary-only
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
zmem handoff --summary-only
zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff
bash scripts/launch_proof.sh
zmem prelaunch --allow-placeholders --summary-only
zmem prelaunch --summary-only
python3 scripts/release_smoke.py --summary-only
python3 scripts/release_smoke.py
python3 scripts/release_smoke.py --require-install-mode packaged
ZERKER_PROVIDER_LIVE=1 ZERKER_PROVIDER_MEM0_BASE_URL=http://localhost:8888 python3 scripts/release_smoke.py
ZERKER_PROVIDER_LIVE=1 ZERKER_PROVIDER_ZEP_BASE_URL=http://localhost:8000 python3 scripts/release_smoke.py
```

The release smoke script creates a fresh temporary virtualenv, runs modern editable install, checks installed entrypoints, initializes a new `.zerker/` workspace, verifies agent config generation, `zmem agent smoke`, real MCP stdio smoke, `zmem handoff`, `zmem --db ... restore --handoff-dir ...`, and `zmem launch-proof`, verifies one bundle and one snapshot, confirms the handoff manifest and Treeship statement exist, and runs `bash examples/first_run.sh` so the published day-1 script stays launch-ready. `bash install.sh` is the public bootstrap path behind the curl-style install command; it sets up the local venv, initializes `.zerker/`, runs eval/doctor, generates the manual-agent pack, and runs both day-1 smoke commands against the selected bootstrap target without mutating Codex or Claude configs unless `ZERKER_MEMORY_AGENT` opts in. If `ZERKER_PROVIDER_LIVE=1` is set, release smoke also runs opt-in live provider smoke using per-provider env vars such as `ZERKER_PROVIDER_MEM0_BASE_URL` or `ZERKER_PROVIDER_ZEP_BASE_URL`, plus matching `*_API_KEY`, `*_USER_ID`, and `*_QUERY` overrides. When provider-specific overrides are present, release smoke now scopes the live doctor run to those providers instead of implicitly defaulting back to Mem0.
If the shell `python3` is older than 3.10, `scripts/release_smoke.py` now reexecs itself with a discovered Python 3.10+ interpreter from `PATH` or `pyenv` before building the fresh virtualenv.
If isolated editable install cannot fetch packaging dependencies, the smoke retries with `--no-build-isolation`, then a venv-local `.pth` bootstrap, and only then falls back to local venv wrapper entrypoints so the rest of the release proof can still run in restricted environments.
Use `python3 scripts/release_smoke.py --require-install-mode packaged` for the final public clean-shell verification pass; it accepts editable install modes but fails if the smoke had to fall back to local wrappers.
Use `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` as the generated copy-ready script for that same clean-shell pass; it includes the repo path created by the curl installer before it runs repo-local proof commands.
The same smoke now verifies `zmem agent install codex`, `zmem agent install claude-code`, plus manual-target `openclaw`, `hermes`, and `generic` installs against temporary config targets. It also runs the manual-target doctor checks and generates `zmem agent checklist <preset>` artifacts so the documented day-1 import path stays aligned with packaged behavior.
GitHub Actions now mirrors that launch contract: a Python 3.10-3.12 matrix runs unit tests plus eval, and a dedicated Python 3.10 release-smoke job runs `bash examples/first_run.sh` plus `python scripts/release_smoke.py`.
Use [PUBLIC_LAUNCH_AUDIT.md](PUBLIC_LAUNCH_AUDIT.md) for the final URL, screenshot/GIF, and claim-boundary pass before announcing.
Use `zmem prelaunch --allow-placeholders --summary-only` before the final repo URL is chosen, then plain `zmem prelaunch --summary-only` while the strict publish gate is still expected to be blocked on missing clean-shell evidence or launch assets. Run plain `zmem prelaunch` only after the live repo/raw installer proof and launch assets exist, just before tagging. The prelaunch gate now expects both launch-proof and handoff artifacts to exist.

## Suggested GitHub About

Description:

```text
Governed local-first memory for AI agents that act.
```

Topics:

```text
ai-agents
mcp
memory
local-first
agent-memory
provenance
neuro-symbolic
behavior-trees
robotics
sqlite
treeship
```

## First Release

Tag:

```text
v0.1.0-alpha
```

Release title:

```text
ZMem v0.1.0-alpha: verifiable memory for agents that act
```

Release notes:

```text
Initial alpha release.

- Local SQLite memory store
- CLI and MCP server
- `zmem run` wrapper
- Local review console with `zmem ui`
- Behavior-tree recovery-memory tools with `zmem bt`
- Trust vs authority
- Quarantine/review/promote/reject
- Symbolic policy gate
- JSON policy config
- Lineage and revocation propagation
- Merkle event log
- Action receipts and `why`
- Verifiable receipt bundles
- Treeship-ready export
- Full-state memory snapshots
- Snapshot verification
- Snapshot restore into an empty store
- Mem0 and Zep adapter scaffolds
- `zmem eval` and `zmem doctor`
```
