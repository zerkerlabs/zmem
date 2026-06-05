# Zerker Memory Launch Asset Operator Prompt

Use this as the durable repo-level brief for the Phase-1 screenshot and GIF pass when generated `.zerker/launch-proof/` artifacts are stale, missing, or have not been refreshed yet.

Current phase: Phase 1 - Public Alpha Launch Gate.
Top remaining blocker: the final eight launch screenshots and GIFs still need to be captured and returned under the shipped proof-pack contract.
Why this slice is the right next move now: the clean-shell public-verify path already has a durable repo-level runbook and prompt, but the asset-capture pass still benefits from one copy-ready fallback brief that names the exact storyboard, save paths, and handback bar.

Send this prompt to the person or chat capturing the final launch assets and have them follow the generated checklist exactly when it exists.

## Operator Steps

1. Refresh the local proof pack with `zmem release-pack --summary-only` if `.zerker/launch-proof/` is missing or stale.
2. Open `.zerker/launch-proof/CAPTURE_CHECKLIST.md` and capture the storyboard in order.
3. Keep `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` open while recording so the save paths and proof references stay visible.
4. Use `.zerker/launch-proof/index.html`, `.zerker/launch-proof/README.md`, and `.zerker/launch-proof/terminal-transcript.txt` as the proof references while recording.
5. Save every screenshot or GIF under `.zerker/launch-proof/assets/` with the exact filenames below.
6. Run `zmem verify-launch-assets --summary-only` to confirm the storyboard is complete.
7. If the clean-shell proof logs are also complete, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`.
8. Hand back `.zerker/launch-proof/assets/` or the rebuilt `.zerker/launch-proof/public-verify-return-packet.tar.gz` only after the self-checks pass.

## Storyboard

1. `install-status` -> `assets/install-status.png`
   Command: `bash install.sh`
   Capture: End on `Zerker Memory status`.
2. `first-run-status` -> `assets/first-run-status.png`
   Command: `bash examples/first_run.sh`
   Capture: End on `Manual pack ready: yes`.
3. `release-pack-summary` -> `assets/release-pack-summary.png`
   Command: `zmem release-pack --summary-only`
   Capture: Show launch proof, handoff, public verify script, logs dir, and the current strict publish gate result.
4. `proof-report-overview` -> `assets/proof-report-overview.png`
   Command: `open .zerker/launch-proof/index.html`
   Capture: Show the proof overview and artifact inventory.
5. `transcript-proof` -> `assets/transcript-proof.png`
   Command: `less .zerker/launch-proof/terminal-transcript.txt`
   Capture: Capture `inject`, `why`, `verify`, `bundle verify`, `snapshot verify`, and `bt explain`.
6. `ui-release-pack` -> `assets/ui-release-pack.gif`
   Command: `zmem --db ".zerker/launch-proof/memory.sqlite" ui`
   Capture: Show the `zmem ui` release-pack action and the proof-review surface.
7. `handoff-restore-terminal` -> `assets/handoff-restore-terminal.png`
   Command: `zmem --db .zerker/imports/launch-proof-restore.sqlite restore --handoff-dir .zerker/handoff`
   Capture: Show snapshot verification plus restored memory and receipt counts.
8. `ui-handoff-restore` -> `assets/ui-handoff-restore.gif`
   Command: `zmem --db ".zerker/imports/launch-proof-restore.sqlite" ui`
   Capture: Show the receive-side proof path after restoring the packaged handoff.

## Acceptance Rules

- `zmem verify-public-verify --summary-only` reports `Ready: yes` before the asset pass is considered complete.
- `zmem verify-launch-assets --summary-only` reports `8/8 captured`.
- `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` is rerun after the asset pass whenever the clean-shell proof packet is being handed back.
- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes` before Phase 1 is marked complete.

## Return Contract

- Source of truth when present: `.zerker/launch-proof/CAPTURE_CHECKLIST.md`.
- Capture board: `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`.
- Asset root: `.zerker/launch-proof/assets/`.
- Verify command: `zmem verify-launch-assets --summary-only`.
- Finalize command: `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`.
- Receive-side verify command: `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`.
