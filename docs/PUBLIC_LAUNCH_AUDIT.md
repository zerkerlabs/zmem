# Public Launch Audit

Use this as the final operator checklist before announcing Zerker Memory.
For the stable send/receive runbook for the Phase-1 clean-shell proof loop, see [CLEAN_SHELL_PUBLIC_VERIFY.md](CLEAN_SHELL_PUBLIC_VERIFY.md).
For the stable screenshot/GIF fallback brief, see [LAUNCH_ASSET_OPERATOR_PROMPT.md](LAUNCH_ASSET_OPERATOR_PROMPT.md).

## Blocking Before Public Announcement

- Final GitHub owner/repo is chosen.
- `install.sh` default `ZERKER_MEMORY_REPO_URL` points to the final public repo.
- README, QUICKSTART, landing, and `pyproject.toml` use the same final repo URL.
- Raw installer URL works from a clean shell:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh | bash
cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
python3 scripts/release_smoke.py --require-install-mode packaged
```

- `LICENSE` is present and the release checklist confirms MIT.
- Generated local state is absent from the publish branch: `.zerker/`, `.venv/`, `*.sqlite`, `*.egg-info/`, `build/`, and `dist/`.
- CI is green on the public repo for unit/eval and release-smoke jobs.
- The repo-local release packet verifies before handoff:

```bash
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
```

- The clean-shell handback verifies on receive:

```bash
zmem verify-public-verify --summary-only
zmem verify-launch-assets --summary-only
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
```

## Launch Proof Assets

Capture the exact eight-asset Phase-1 storyboard before posting. The durable repo-level fallback is this section; the generated capture-ready surfaces are `.zerker/launch-proof/CAPTURE_CHECKLIST.md` and `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`.

- `assets/install-status.png`: run `bash install.sh` and capture the terminal ending on `Zerker Memory status`.
- `assets/first-run-status.png`: run `bash examples/first_run.sh` and capture the terminal ending on `Manual pack ready: yes`.
- `assets/release-pack-summary.png`: run `zmem release-pack --summary-only` and capture launch proof, handoff, public verify script, logs dir, and the current strict publish gate result.
- `assets/proof-report-overview.png`: open `.zerker/launch-proof/index.html` and capture the proof overview plus artifact inventory.
- `assets/transcript-proof.png`: inspect `.zerker/launch-proof/terminal-transcript.txt` and capture `inject`, `why`, `verify`, `bundle verify`, `snapshot verify`, and `bt explain`.
- `assets/ui-release-pack.gif`: run `zmem --db ".zerker/launch-proof/memory.sqlite" ui` and capture the `zmem ui` release-pack action plus the proof-review surface.
- `assets/handoff-restore-terminal.png`: run `zmem --db .zerker/imports/launch-proof-restore.sqlite restore --handoff-dir .zerker/handoff` and capture snapshot verification plus restored memory and receipt counts.
- `assets/ui-handoff-restore.gif`: run `zmem --db ".zerker/imports/launch-proof-restore.sqlite" ui` and capture the receive-side proof path after restoring the packaged handoff.

Required acceptance before handback:

- `zmem verify-public-verify --summary-only` reports `Ready: yes`.
- `zmem verify-launch-assets --summary-only` reports `8/8 captured`.
- `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` is rerun after the asset pass.
- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.

## Copy Guardrails

- Say "functional local-first alpha" for the current product.
- Say "Treeship-ready export" unless the fully signed public Treeship publish path is demonstrated.
- Say "provider governance overlay" rather than "replacement for Mem0/Zep/Graphiti/Letta/LangMem/Cognee."
- Keep hosted/team/enterprise control-plane language in roadmap sections, not current-feature sections.
- Avoid claims of perfect security, autonomous safety, quantum readiness, or production enterprise compliance.

## Final Smoke Commands

Run from a Python 3.10+ environment before tagging:

```bash
bash install.sh
bash examples/first_run.sh
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
python3 -m unittest discover -s tests
python3 -m zerker_memory eval
python3 scripts/release_smoke.py --require-install-mode packaged
zmem verify-public-verify --summary-only
zmem verify-launch-assets --summary-only
.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
zmem prelaunch
```

Expected alpha proof:

- `bash install.sh` prints `Zerker Memory status`.
- `bash examples/first_run.sh` prints `Manual pack ready: yes`.
- `zmem release-pack --summary-only` refreshes `.zerker/launch-proof/`, `.zerker/handoff/`, and the prelaunch gate in one command.
- `zmem verify-operator-packet ... --summary-only` reports `Ready: yes` before the clean-shell handoff leaves the repo.
- unit tests pass.
- eval passes 11/11.
- the clean-shell proof run passes `python3 scripts/release_smoke.py --require-install-mode packaged`, proving the public installer did not rely on local wrappers.
- `zmem verify-public-verify --summary-only` reports `Ready: yes` before the asset pass.
- `zmem verify-launch-assets --summary-only` reports `8/8 captured`.
- `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` succeeds and `zmem verify-return-packet ... --summary-only` reports `Ready: yes`.
- plain `zmem prelaunch` passes with no blockers before tagging.

Use `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` as the exact outbound triplet for the clean-shell operator. Accept the returned proof only after the receive-side verifier passes.
