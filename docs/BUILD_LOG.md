# Build Log

This file tracks product-build slices so parallel Codex runs and hourly automations do not become invisible.

## 2026-06-05 - Capture Checklist Now Carries The Full Handback Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the generated `CAPTURE_CHECKLIST.md` was still the weakest forwarded Phase-1 asset surface because it named the storyboard but did not fully carry the pre-asset verify gate, durable fallback docs, or the finalize-and-receive-side acceptance contract on one screen.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so generated `.zerker/launch-proof/CAPTURE_CHECKLIST.md` now includes an explicit `Asset Pass Gate` section, the durable Phase-1 fallback doc set, the `verify-public-verify` prerequisite, the rerun-`FINALIZE_RETURN_PACKET.sh` handback step, and the `verify-return-packet` receive-side acceptance rule.
- Tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the generated capture checklist now fails fast if those standalone handoff cues disappear from future Phase-1 packets.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts -q` -> 1 test OK.
- `python3 -m unittest tests.test_release_smoke -q` -> 43 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; `.zerker/launch-proof/CAPTURE_CHECKLIST.md` refreshed and strict publish still blocked only on `0/6` clean-shell logs plus `0/8` launch assets.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight remains healthy with the same external blockers.
- `sed -n '1,260p' .zerker/launch-proof/CAPTURE_CHECKLIST.md` -> verified the generated checklist now carries the asset-pass gate, durable fallback docs, finalize step, and receive-side acceptance command inline.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the six clean-shell logs, including `operator-packet-verify.log`, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice strengthened the generated asset handoff contract locally, but it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, start from [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), rerun `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the shipped triplet, run the clean-shell packaged proof, use the stronger `.zerker/launch-proof/CAPTURE_CHECKLIST.md` for the screenshot/GIF pass, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.
- If external access is still unavailable, the best local-adjacent slice is another narrow Phase-1 generated-artifact polish pass only if a similarly weak forwarded surface is found; otherwise do not spend another run restating the now-aligned asset handback contract.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture once networked execution is available.

## 2026-06-05 - Public Verify Summary Restored Operator-Packet Preflight Step

## 2026-06-05 - Status Summary Now Separates Release Packet Readiness From Publish Readiness

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was the right next move now: `zmem status --summary-only` is still the first Phase-1 handoff surface, and it was incorrectly leading with `Release proof ready: yes` even while the same screen showed `Public verify: pending`, `Launch assets: pending`, and `Strict publish gate: blocked`.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the top status summary now says `Release packet ready` for the generated local handoff bundle state and separately says `Strict publish ready` for the actual Phase-1 external-proof gate, instead of conflating the two under the older `Release proof ready` label.
- Tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and synced [`docs/LAUNCH_READINESS_NOW.md`](docs/LAUNCH_READINESS_NOW.md) so the new status wording is locked to the shipped launch-gate semantics.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_render_status_summary_includes_release_readiness_when_repo_surface_exists` -> 1 test OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 -m zerker_memory status --summary-only` -> passed; top lines now read `Release packet ready: yes` and `Strict publish ready: no` while Phase 1 remains blocked on `0/6` public-verify logs plus `0/8` launch assets.
- `python3 scripts/release_smoke.py --summary-only` -> passed; the repo-local preflight now shows the same top-line distinction before the unchanged blocked release surfaces.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the six clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice only corrected the local release-state wording; it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, use the now-clearer `zmem status --summary-only` screen to drive the existing Phase-1 handoff from [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md): verify the outbound packet, forward the shipped triplet, run the clean-shell packaged proof, capture the eight launch assets, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.
- If external access is still unavailable, the best local-adjacent slice is another narrow Phase-1 handoff polish change that reduces operator ambiguity without reworking the already-stable proof contract.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture once networked execution is available.

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the local audit initially looked clean, but `python3 scripts/release_smoke.py --summary-only` exposed a real Phase-1 regression where generated `.zerker/launch-proof/public-verify-summary.md` still omitted the operator-packet preflight command from its command-log map even though the shipped verifier and runbook now require that sixth proof log.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `render_public_verify_result_summary()` now renders its command-log map from the shared `PUBLIC_VERIFY_LOG_SPECS` contract instead of a stale hard-coded five-step list, which restores the missing `verify-operator-packet -> operator-packet-verify.log` step in generated `public-verify-summary.md`.
- Updated [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md), [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md), and the automation memory so the next run starts from the fixed Phase-1 contract rather than the earlier wording-audit detour.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `rg -n "0/5|5/5|five-log|five log|five-command|five command" --glob '!docs/BUILD_LOG.md' --glob '!docs/CURRENT_STATE.md' .` -> no matches.
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_launch_proof_summary_requires_public_verify_logs_dir -q` -> 2 tests OK.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_verify_public_verify_reports_ready_logs_and_receipt tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts -q` -> 2 tests OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now succeeds again with the generated public-verify summary carrying the operator-packet preflight log contract.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; operator packet ready (`16/16 files packed`), public verify pending `0/6`, launch assets pending `0/8`.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> `Ready: yes`.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected blocked state; reports `0/6` logs captured and the generated summary now includes the operator-packet preflight step.
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected blocked state; `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected blocked state; archive structure is OK but external proof evidence and launch assets are still missing.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the six clean-shell logs, including `operator-packet-verify.log`, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice restored the local Phase-1 summary contract, but it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, start from [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), rerun `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, then run the clean-shell packaged proof and capture pass against `https://github.com/zerkerlabs/zerker-memory`.
- If external access is still unavailable, pick a new Phase-1 artifact polish slice that directly helps the blocked handoff, such as a clean-shell verification checklist refinement or launch-asset board polish; do not spend another run re-auditing the now-clean `five-log` / `five-command` wording.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture once networked execution is available.

## 2026-06-05 - Phase-1 Live Contract Audit Closed With No Remaining Non-Historical Drift

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was the right next move now: after the `6/6` log contract shipped, the highest-leverage local-adjacent move was to verify whether any live launch-facing repo surfaces still referenced the old `5/5` or five-command wording before another automation run spent time re-auditing the same question.
- Audited the live repo surfaces with `rg` across `README.md`, `QUICKSTART.md`, `docs/`, `landing/`, `zerker_memory/`, `tests/`, `scripts/`, and `install.sh`, excluding historical run logs; no remaining non-historical `five-log`, `five-command`, `0/5`, or `5/5` references were found outside historical notes in this file and prior shipped-entry prose in [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md).
- Updated [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) and this build log so future offline runs can skip the wording audit and move directly to the next Phase-1 artifact that helps the blocked external handoff.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `rg -n "0/5|5/5|five-log|five log|five-command|five command" --glob '!docs/BUILD_LOG.md' --glob '!docs/CURRENT_STATE.md' .` -> no matches.
- `python3 -m zerker_memory status --summary-only` -> OK before refresh; launch proof missing locally, handoff present, next repo-local step remains `zmem release-pack --summary-only`.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; operator packet ready (`16/16 files packed`), public verify pending `0/6`, launch assets pending `0/8`.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected blocked state; reports `0/6` logs captured and the full six-step command/log map.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still points at `zerkerlabs/zerker-memory` and remains blocked only on the missing external proof logs and launch assets.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the six clean-shell logs, including `operator-packet-verify.log`, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice confirmed the live launch contract is already clean locally, but it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, start from [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), rerun `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, then run the clean-shell packaged proof and capture pass against `https://github.com/zerkerlabs/zerker-memory`.
- If external access is still unavailable, pick a new Phase-1 artifact polish slice that directly helps the blocked handoff, such as a clean-shell verification checklist refinement or launch-asset board polish; do not spend another run re-auditing the now-clean `five-log` / `five-command` wording.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture once networked execution is available.

## 2026-06-05 - Public Verify Contract Requires Operator-Packet Preflight Log

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the generated clean-shell script already wrote `operator-packet-verify.log`, but the shipped receive-side contract, terminal summaries, and launch docs still described only five required logs, which weakened the handback audit for the one external proof loop that still blocks Phase 1.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the shipped public-verify contract now requires `operator-packet-verify.log` everywhere that matters: the manifest-backed expected log list, command-log map, `verify-public-verify` completion rule, return-packet handback copy, and generated fallback docs/prompts.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md), and [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md) so the Phase-1 handoff bar is now consistently `6/6` logs instead of a stale `5/5`.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> passed.
- `python3 -m zerker_memory status --summary-only` -> passed; local alpha gate still reports `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; now prints the operator-packet preflight log inside the required clean-shell proof contract.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected blocked state; now reports `0/6` logs captured instead of `0/5`.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; `public_verify_evidence` now requires six logs, including `operator-packet-verify.log`.
- `python3 -m zerker_memory eval` -> 11/11 passed.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the six clean-shell logs, including `operator-packet-verify.log`, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice tightened the receive-side proof contract locally, but it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, use [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), forward the shipped triplet, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, and accept handback only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes` with all six logs and all eight assets present.
- If external access is still unavailable, the best local-adjacent slice is a final audit for any remaining live `five-log` or `five-command` wording outside historical build notes.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture, now with the receive-side proof contract explicitly requiring `operator-packet-verify.log`.

## 2026-06-05 - Public Repo Target Normalized To zerker-memory

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the automation brief and recent handoff notes had already converged on `zerkerlabs/zerker-memory`, but the shipped installer default, release CLI summaries, tests, and several launch docs still pointed at `zerkerlabs/zmem`, which made the Phase-1 clean-shell proof target ambiguous.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py), [`install.sh`](install.sh), [`scripts/release_smoke.py`](scripts/release_smoke.py), [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`landing/index.html`](landing/index.html), and the active launch docs so the public GitHub repo target and raw installer URL now consistently point to `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` while keeping the product and CLI name `zmem`.
- Tightened [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the Phase-1 proof surfaces, generated manifests, and installer contract now fail fast if they drift back to the old repo target.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_release_pack_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_operator_packet_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_summary_requires_strict_human_output -q` -> 3 tests OK.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts tests.test_cli_onboarding.CliOnboardingTest.test_verify_operator_packet_archive_reports_ready_packet tests.test_cli_onboarding.CliOnboardingTest.test_verify_public_verify_reports_ready_logs_and_receipt -q` -> 3 tests OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; the repo-local Phase-1 preflight, operator packet verifier, public-verify verifier, and return-packet verifier now all point at `zerkerlabs/zerker-memory`.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; expected public repo is now `https://github.com/zerkerlabs/zerker-memory`.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> `Ready: yes`; expected public repo and raw install URL now match `zerkerlabs/zerker-memory`.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected not ready; `0/5` logs captured.
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected not ready; `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected not ready; archive structure is OK but evidence/assets are still missing.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed the repo-target ambiguity locally, but it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, use [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) as the pinned sidecar brief, rerun `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the shipped triplet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.
- If external access is still unavailable, the best local-adjacent slice is a final docs audit for any remaining non-historical `zerkerlabs/zmem` references outside the active launch surfaces.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture, now with an unambiguous `zerkerlabs/zerker-memory` target across the shipped proof path.

## 2026-06-05 - Generated Launch-Proof Artifacts Carry Durable Phase-1 Fallbacks

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the terminal-first release surfaces were already aligned, but another chat could still lose the durable repo-level fallback path when it only received generated `.zerker/launch-proof/` artifacts.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem launch-proof --summary-only`, the generated launch-proof HTML report, and the generated `LAUNCH_ASSET_HANDOFF.md`, `PUBLIC_VERIFY_HANDOFF.md`, and `RECEIVE_VERIFY_HANDOFF.md` now all repeat the durable fallback set: [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md), [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md), [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md), and [`docs/LAUNCH_ASSET_BOARD.html`](docs/LAUNCH_ASSET_BOARD.html).
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the launch-proof summary contract and generated-artifact coverage now fail if those durable fallback references disappear from the forwarded proof surfaces.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_launch_proof_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_launch_proof_summary_requires_public_verify_logs_dir -q` -> 2 tests OK.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_render_launch_proof_summary_lists_artifacts_and_next_steps tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_surfaces_public_verify_contract_in_readme_and_report tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts -q` -> 3 tests OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 -m zerker_memory launch-proof --summary-only` -> passed; the launch-proof summary now includes the durable brief/runbook/prompt/asset-board fallback set while the return packet remains expected-pending on external proof and launch assets.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight remains healthy and the generated launch-proof artifact path now stays aligned with the terminal/operator fallback contract.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed the remaining artifact-only handoff gap locally, but it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, use [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) as the pinned sidecar brief, verify the outbound archive locally, forward the shipped triplet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.
- If external access is still unavailable, the best local-adjacent slice is a launch-asset/operator-proof polish pass that does not need network access, such as threading the durable fallback set into any remaining generated packet-local checklist/readme surfaces not yet covered by the report, summaries, and handoff markdowns.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the generated launch-proof summary/report/handoff surfaces carry the same durable fallback contract as the main terminal/operator summaries.

## 2026-06-05 - Durable Phase-1 Fallbacks Surfaced In Terminal Summaries

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the repo already had durable Phase-1 fallback docs, but the highest-frequency terminal/operator surfaces still mostly assumed another chat would open packet-local `.zerker/launch-proof/` files first.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem status --summary-only`, `zmem release-pack --summary-only`, `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, and prelaunch/status next-step guidance now all surface the durable repo-level fallback set: [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md), [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md), [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md), and [`docs/LAUNCH_ASSET_BOARD.html`](docs/LAUNCH_ASSET_BOARD.html).
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so Phase-1 smoke and summary-contract coverage now fail if those durable fallback references disappear, and synced [`docs/GITHUB_RELEASE_CHECKLIST.md`](docs/GITHUB_RELEASE_CHECKLIST.md) with the same fallback-first launch instruction set.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_render_status_summary_includes_release_readiness_when_repo_surface_exists tests.test_cli_onboarding.CliOnboardingTest.test_run_release_pack_refreshes_artifacts_and_prelaunch tests.test_cli_onboarding.CliOnboardingTest.test_verify_public_verify_reports_ready_logs_and_receipt -q` -> 3 tests OK.
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_release_pack_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_operator_packet_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_summary_requires_strict_human_output -q` -> 3 tests OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now prints the durable fallback doc set on the main terminal summaries while strict publish remains blocked only on `launch_assets` plus `public_verify_evidence`.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)` and now surfaces the durable fallback brief/runbook/prompt/board paths inline.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; operator packet remains ready and now also carries the durable fallback doc set beside the packet-local runbook and asset board.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain, and next-step guidance now includes the durable fallback set.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed another operator-handoff ambiguity, but it did not generate the missing networked evidence or captured launch assets.

Next:

- If external access is available, use [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) as the pinned sidecar brief, verify the outbound archive locally, forward the shipped triplet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.
- If external access is still unavailable, the best local-adjacent slice is to thread the same durable fallback references into the generated packet-local markdown/HTML artifacts such as `.zerker/launch-proof/public-verify-summary.md` and the launch-proof report so forwarded artifact-only handoffs stay aligned with the new terminal summaries.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the durable fallback doc set visible on the primary terminal/operator surfaces another chat is most likely to use before that sidecar starts.

## 2026-06-05 - Durable Launch Asset Board

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the durable Phase-1 docs already covered the screenshot/GIF contract in prose, but the most capture-friendly surface, `LAUNCH_ASSET_BOARD.html`, still effectively lived only inside generated `.zerker/launch-proof/` state when another chat needed a stable visual board before refreshing the packet.
- Added durable [`docs/LAUNCH_ASSET_BOARD.html`](docs/LAUNCH_ASSET_BOARD.html) so the repo now has a stable visual board for the eight required launch screenshots/GIFs, with the same capture IDs, commands, cues, save paths, and fallback references carried by the generated board.
- Synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the main launch-facing surfaces now point at the durable board alongside the existing brief and prompt.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `sed -n '1,260p' docs/LAUNCH_ASSET_BOARD.html` -> verified the new durable board mirrors the eight-shot asset contract with the expected commands, cues, save paths, and durable fallback links.
- `rg -n "LAUNCH_ASSET_BOARD.html" README.md QUICKSTART.md docs/DAY1_AGENT_SETUP.md docs/PRODUCT_STATUS.md landing/index.html docs/LAUNCH_ASSET_BOARD.html` -> confirmed the new durable board is referenced from the main Phase-1 launch-facing docs and landing copy.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)` and the outbound operator packet remains ready.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight remains healthy, still points operators at the generated launch-asset board, and strict publish remains blocked only on the missing clean-shell logs and launch assets.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed a remaining repo-level handoff gap for the asset-capture sidecar, but it did not generate the missing networked evidence or launch assets.

Next:

- Use [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) plus the new durable [`docs/LAUNCH_ASSET_BOARD.html`](docs/LAUNCH_ASSET_BOARD.html) as the pinned sidecar set: rerun `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the shipped triplet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run added the durable visual capture board another chat should now use alongside the existing brief and prompt.

## 2026-06-05 - Durable Phase-1 External Operator Brief

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the local packet, verifier, runbook, prompt, compact summary, and asset-board surfaces were already aligned, but there was still no single pinned repo doc another chat could use end-to-end for send, run, capture, and receive-side acceptance.
- Added durable [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) so the repo now has one orchestrator-facing Phase-1 handoff doc that combines repo-local preflight, the forward-together triplet, clean-shell proof steps, the five-log contract, the eight-asset pass, finalize/return-packet acceptance, and stop conditions.
- Synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the main launch-facing surfaces now point at that single durable brief before falling back to the narrower runbook, prompt, and asset brief.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)` and the outbound operator packet remains ready.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight remains healthy, and strict publish is still blocked only on the missing clean-shell logs and launch assets.
- `sed -n '1,260p' docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md` -> verified the new durable brief carries the one-file send, run, capture, finalize, and accept contract.
- `rg -n "PHASE1_EXTERNAL_OPERATOR_BRIEF" README.md QUICKSTART.md docs/DAY1_AGENT_SETUP.md docs/PRODUCT_STATUS.md` -> confirmed the main launch-facing docs point at the new durable brief.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed another orchestration gap, but it did not generate the missing networked evidence or captured launch assets.

Next:

- Use [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) as the pinned sidecar brief: rerun `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the shipped triplet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run added the single durable orchestrator brief another chat should now use for that work.

## 2026-06-05 - Durable Launch Asset Operator Prompt

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was the right next move now: the clean-shell public-verify loop already had durable repo-level fallback docs, but the screenshot/GIF pass still depended too heavily on generated `.zerker/launch-proof/` artifacts when another chat needed a stable asset-capture brief.
- Added durable [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md) so the repo now has one copy-ready Phase-1 screenshot/GIF brief that mirrors the shipped eight-asset storyboard, save paths, verification bar, finalize step, and receive-side acceptance command.
- Synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`docs/PUBLIC_LAUNCH_AUDIT.md`](docs/PUBLIC_LAUNCH_AUDIT.md) so the main launch-facing surfaces now point at that durable asset-capture fallback alongside the existing clean-shell runbook and operator prompt.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `sed -n '1,240p' docs/LAUNCH_ASSET_OPERATOR_PROMPT.md` -> verified the durable prompt carries the exact eight-asset storyboard, save paths, finalize step, and receive-side acceptance command.
- `rg -n "LAUNCH_ASSET_OPERATOR_PROMPT" README.md QUICKSTART.md docs/DAY1_AGENT_SETUP.md docs/PRODUCT_STATUS.md docs/PUBLIC_LAUNCH_AUDIT.md docs/LAUNCH_ASSET_OPERATOR_PROMPT.md` -> confirmed the new durable prompt is referenced from the main release-facing docs.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; operator packet remains ready, launch assets remain `0/8`, and the Phase-1 handoff contract is unchanged.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice improved the durable screenshot/GIF handoff surface, but it did not generate the missing clean-shell proof or captured launch assets.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the clean-shell triplet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, then use either `.zerker/launch-proof/CAPTURE_CHECKLIST.md` or [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md) to capture the eight launch assets before rerunning `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` and accepting handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only added the durable repo-level fallback brief for the asset-capture side of that handoff.

## 2026-06-05 - Status Summary Separates Memory Proof From Release Proof

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was the right next move now: `zmem status --summary-only` is still the first day-1 and release-orchestration surface, and it was incorrectly leading with `Proof ready: yes` even when the release proof path was still missing and the alpha gate was blocked.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the status summary now says `Memory proof ready` for the local receipt/eval surface and separately says `Release proof ready` for the launch-proof packet state, without changing the existing release readiness logic or next-step contract.
- Tightened [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the status-summary renderer now fails fast if those labels drift and start conflating the two proof surfaces again.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_render_status_summary_includes_workspace_and_agent_pack tests.test_cli_onboarding.CliOnboardingTest.test_render_status_summary_includes_release_readiness_when_repo_surface_exists -q` -> 2 tests OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; the preflight now shows `Memory proof ready: yes` / `Release proof ready: no` before `release-pack`, then `Release proof ready: yes` after `release-pack`, while strict publish remains blocked only on `launch_assets` plus `public_verify_evidence`.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; operator packet remains ready and the command still carries the full Phase-1 clean-shell and asset-capture contract.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed a misleading local status signal, but it did not generate the missing networked evidence or launch assets.

Next:

- Use the clarified status summary as the first external-sidecar brief: run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the prompt/runbook/archive triplet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight storyboarded assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the main status surface distinguish local memory proof from release-proof readiness before that handoff.

## 2026-06-05 - Release Pack Summary Carries Full Phase-1 Brief

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: `zmem release-pack --summary-only` is the shortest repo-local Phase-1 refresh and the documented starting point, but it still stopped short of the full clean-shell command-log contract and launch-asset cue map that the verifier surfaces already carried.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only` now also prints the packet-local runbook line, required `packaged` install mode, the exact five-command clean-shell log contract, `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, and the full eight-shot command/capture cue map inline.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so Phase-1 smoke now fails if the release-pack summary loses that one-screen operator brief, and synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) with the stronger release-pack claim.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_release_pack_summary_requires_strict_human_output -q` -> 1 test OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now shows the full `release-pack` command-log contract plus the eight-shot asset cue map while strict publish remains blocked only on the missing clean-shell logs and launch assets.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; now prints the runbook, required `packaged` install mode, the exact five-command log contract, `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, and the full eight-shot asset cue map inline.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> `Ready: yes`.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected not ready; `0/5` logs captured.
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected not ready; `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected not ready; archive structure is OK but evidence/assets are still missing.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed the last summary-level local gap on the main `release-pack` operator surface, but it did not generate the missing external evidence or captured assets.

Next:

- Use the upgraded `zmem release-pack --summary-only` output as the top-level operator brief in the external sidecar: verify the outbound packet locally, forward the prompt/runbook/archive triplet, run `PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight storyboarded assets directly from the same summary or board, rerun `FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the shortest repo-local release command carry the full Phase-1 handoff contract on one screen.

## 2026-06-05 - Operator Surfaces Carry Asset Cue Map

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the launch-asset verifier already printed the full eight-shot cue map, but the two main forwarded/operator surfaces, `zmem verify-operator-packet --summary-only` and `zmem verify-public-verify --summary-only`, still forced another chat to open the checklist or board separately before it could run the screenshot/GIF pass cleanly.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, and generated `.zerker/launch-proof/public-verify-summary.md` now all surface the launch-asset board path plus the full eight-shot command/capture cue map inline beside the existing clean-shell command-log contract.
- Tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so operator-packet, public-verify, and generated-summary surfaces now fail fast if the launch-asset board path or per-asset cue map disappears, and synced [`README.md`](README.md) with the stronger operator-surface contract.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `sed -n '1,220p' docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `README.md`, `QUICKSTART.md`, and `docs/DAY1_AGENT_SETUP.md` -> orientation completed against the current shipped Phase-1 contract.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_verify_operator_packet_archive_reports_ready_packet tests.test_cli_onboarding.CliOnboardingTest.test_verify_public_verify_reports_ready_logs_and_receipt tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts -q` -> 3 tests OK.
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_run_release_smoke_summary_prints_phase_one_preflight tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_result_summary_artifact_requires_handoff_contract -q` -> 2 tests OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now shows the stronger operator/public-verify asset cue map while strict publish remains blocked only on the missing clean-shell logs and launch assets.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> `Ready: yes`; now also prints `Launch asset board: LAUNCH_ASSET_BOARD.html` plus the full eight-shot command/capture cue map inline.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected not ready; `0/5` logs captured, and it now also prints `Launch asset board: .zerker/launch-proof/LAUNCH_ASSET_BOARD.html` plus the full eight-shot command/capture cue map inline.
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected not ready; `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected not ready; archive structure is OK but evidence/assets are still missing.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed another local handoff ambiguity, but it did not generate the missing external evidence or captured assets.

Next:

- Use the stronger one-screen operator surfaces to drive the external sidecar: verify the outbound packet locally, forward the prompt/runbook/archive triplet, run `PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the eight storyboarded assets directly from the inline cue map or board, rerun `FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only moved the last high-frequency asset-capture instructions onto the main forwarded/operator surfaces.

## 2026-06-04 - Hydration Boundary Captured For Orientation

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets, but this run was blocked earlier by local file hydration because most required orientation inputs are still macOS `compressed,dataless` placeholders.
- Confirmed the boundary precisely instead of guessing through it: `README.md`, `QUICKSTART.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `docs/DAY1_AGENT_SETUP.md`, `tests/test_release_smoke.py`, and `zerker_memory/cli.py` still report `compressed,dataless`, while `docs/CURRENT_STATE.md` remained readable enough to recover the last shipped state and verification baseline.
- Updated [`docs/REPO_HYDRATION_BLOCKER_2026-06-04.md`](docs/REPO_HYDRATION_BLOCKER_2026-06-04.md) with the new boundary note that `python3 -m zerker_memory eval` still passes locally, but a fresh `python3 -m zerker_memory status --summary-only` no longer returned promptly during orientation under the same partially hydrated workspace.
- Updated [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) so the next run sees the exact local blocker before attempting new Phase-1 work: rehydrate the repo files, rerun orientation, then resume the external-proof critical path.

Verification:

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `ls -lO README.md QUICKSTART.md docs/CURRENT_STATE.md docs/BUILD_LOG.md docs/PRODUCT_STATUS.md docs/DAY1_AGENT_SETUP.md tests/test_release_smoke.py zerker_memory/cli.py` -> `README.md`, `QUICKSTART.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `docs/DAY1_AGENT_SETUP.md`, `tests/test_release_smoke.py`, and `zerker_memory/cli.py` still show `compressed,dataless`; `docs/CURRENT_STATE.md` is locally readable.
- `sed -n '1,240p' docs/CURRENT_STATE.md` -> succeeded and recovered the latest shipped Phase-1 state plus the last known verification baseline.
- `head -n 20 docs/BUILD_LOG.md` -> succeeded; top shipped slice remained `2026-06-04 - Durable Launch Asset Audit Exactness`.
- `git rev-parse --show-toplevel` -> `/Users/zzo`, confirming this workspace cannot recover the project files with a simple repo-local `git show HEAD:<path>` fallback.
- `python3 -m zerker_memory eval` -> passed (`11/11`).
- `python3 -m zerker_memory status --summary-only` -> attempted during orientation but did not return promptly in this partially hydrated workspace, so no fresh local status snapshot was recorded safely this run.

Blockers:

- Required orientation remains incomplete because several mandated docs and source files are still local file-provider placeholders and cannot be read safely.
- Phase 1 still remains externally blocked on the clean-shell public repo/raw installer proof and the eight launch assets once the local hydration issue is cleared.

Next:

- Rehydrate the dataless repo files first.
- Rerun the full required orientation pass against `docs/CURRENT_STATE.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `README.md`, `QUICKSTART.md`, `docs/DAY1_AGENT_SETUP.md`, automation memory, and current tests/status.
- Then take exactly one Phase-1 slice on the external-proof path, most likely the clean-shell publish audit or adjacent launch-proof polish if external access is still unavailable.

Delegation/Handoff:

- No active delegated sidecar work. Intended sidecar remains the external clean-shell publish audit plus eight launch assets after hydration is restored.

## 2026-06-04 - Durable Launch Asset Audit Exactness

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the generated packet already had the exact eight-asset storyboard, but the durable repo-level launch audit still collapsed that blocker into generic proof categories and could send another chat to capture the wrong launch surface when `.zerker/launch-proof/` was stale or unavailable.
- Updated [`docs/PUBLIC_LAUNCH_AUDIT.md`](docs/PUBLIC_LAUNCH_AUDIT.md) so the durable launch checklist now mirrors the exact Phase-1 asset contract: all eight required deliverables, the command and capture cue for each asset, and the receive-side acceptance bar of `verify-public-verify`, `verify-launch-assets`, finalize, and `verify-return-packet`.
- Updated [`landing/index.html`](landing/index.html) so the public proof-path section now states the real Phase-1 completion contract and includes `zmem verify-launch-assets --summary-only` in the GIF-ready command path instead of stopping before the asset-verification gate.

Verification:

- `python3 -m unittest discover` -> passed locally earlier in this run.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; strict publish remains blocked only on `launch_assets` plus `public_verify_evidence`.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> `Ready: yes`.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected not ready; `0/5` logs captured.
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected not ready; `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected not ready; archive structure is OK but evidence/assets are still missing.
- `rg -n "eight-asset|install-status.png|ui-handoff-restore|verify-launch-assets --summary-only|packaged install" docs/PUBLIC_LAUNCH_AUDIT.md landing/index.html` -> confirmed the durable audit and landing proof path now surface the exact asset contract.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice tightened the durable asset checklist, but it did not generate the missing external evidence or captured assets.

Next:

- Use the updated durable audit as the fallback brief for the external sidecar: verify the outbound packet locally, forward the prompt/runbook/archive triplet, capture the five packaged-install proof logs plus the exact eight launch assets, rerun `FINALIZE_RETURN_PACKET.sh`, and accept handback only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the durable repo-level asset checklist match the shipped packet contract.

## 2026-06-04 - Clean-Shell Bootstrap Contract Clarified

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the local packet/verifier surfaces were aligned, but the highest-risk remaining local ambiguity was operator confusion between the bootstrap install needed to create the clean repo path and the second installer pass that `PUBLIC_VERIFY_COMMANDS.sh` reruns and records as `curl-install.log`.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the generated operator packet surfaces now state that contract directly on the terminal-first verifier screens, in `public-verify-summary.md`, in the fallback clean-shell runbook/prompt, in `PUBLIC_VERIFY_COMMANDS.sh`, and in the public-verify handoff text.
- Synced the durable repo-level runbook and prompt in [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) and [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md) so another chat sees the same bootstrap-vs-recorded-install rule even before refreshing `.zerker/launch-proof/`.
- Tightened [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so launch-proof generation now fails if the bootstrap note disappears from the clean-shell runbook, prompt, script, or compact public-verify summary.

Verification:

- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts -q` -> 1 test OK.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; local Phase-1 surfaces remain aligned, the new bootstrap note shows on the operator-packet and public-verify verifier summaries, and strict publish is still blocked only on `launch_assets` plus `public_verify_evidence`.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed a clean-shell operator ambiguity, but it did not generate the missing external evidence or launch assets.

Next:

- Use the clarified operator packet/runbook/prompt bundle to drive the real clean-shell pass: verify the outbound packet locally, forward the prompt/runbook/archive triplet, capture the five packaged-install proof logs plus eight launch assets, rerun `FINALIZE_RETURN_PACKET.sh`, and accept handback only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the bootstrap-vs-proof-install contract explicit on the primary operator surfaces.

## 2026-06-04 - Compact Summary Outbound Verify Cue

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the compact `public-verify-summary.md` artifact was now a common forwarded handoff surface, but it still skipped the repo-local `verify-operator-packet` gate and could let another chat forward the bundle without rechecking the outbound archive first.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so generated `.zerker/launch-proof/public-verify-summary.md` now explicitly tells the orchestrator to run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` before forwarding the clean-shell bundle.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the compact summary contract now fails fast if that outbound verification cue disappears again.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 scripts/release_smoke.py --summary-only` -> passed; local release surfaces remain aligned, `status`/`release-pack`/verifier flow stays consistent, and strict publish is still blocked only on `launch_assets` plus `public_verify_evidence`.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> `Ready: yes`.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected not ready; `0/5` logs captured.
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected not ready; `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected not ready; archive structure is OK but evidence/assets are still missing.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice tightened the compact handoff summary, but it did not generate the missing external evidence or launch assets.

Next:

- Use the updated `.zerker/launch-proof/public-verify-summary.md` as a pinned forwarded artifact only after the local `verify-operator-packet` gate passes, then send the normal outbound triplet to a clean networked shell for the real public proof and asset pass.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only closed the last local summary-level ambiguity before that handoff.

## 2026-06-04 - Public Launch Audit Strictness Sync

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the shipped CLI, packet, and verifier surfaces already enforce the strict packaged-install send/receive contract, but the durable repo-level `docs/PUBLIC_LAUNCH_AUDIT.md` still described the older placeholder-tolerant publish flow and could send another chat through the wrong launch checklist.
- Updated [`docs/PUBLIC_LAUNCH_AUDIT.md`](docs/PUBLIC_LAUNCH_AUDIT.md) so the final launch audit now matches the shipped Phase-1 contract: repo-local `verify-operator-packet` before handoff, clean-shell `--require-install-mode packaged`, receive-side `verify-public-verify` / `verify-launch-assets` / `verify-return-packet`, plain `zmem prelaunch` before tagging, and the exact outbound triplet to hand to the clean-shell operator.

Verification:

- `python3 scripts/release_smoke.py --summary-only` -> passed; local release surfaces remain aligned and strict publish is still blocked only on `launch_assets` plus `public_verify_evidence`.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)`.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected blocked state; only `launch_assets` and `public_verify_evidence` remain.
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> `Ready: yes`.
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected not ready; `0/5` logs captured.
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected not ready; `0/8` assets captured.
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected not ready; archive structure is OK but evidence/assets are still missing.
- `rg -n "allow-placeholders|local wrapper fallback|placeholder warning" docs/PUBLIC_LAUNCH_AUDIT.md` -> no matches.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice tightened the durable launch checklist, but it did not generate the missing external evidence or launch assets.

Next:

- Use `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` as the final local handoff gate, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell for the real public proof and asset pass.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the durable launch-audit doc match the already-shipped strict send/receive verifier flow.

## 2026-06-04 - Packaged Verify Mode Alignment

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the shipped clean-shell contract already allowed the `venv-pth` packaged-install fallback in `scripts/release_smoke.py`, but the receive-side CLI verification path still rejected that same mode and could falsely fail a legitimate returned proof packet.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the Phase-1 verifier contract now treats `venv-pth` as satisfying the `packaged` install requirement, matching the existing release-smoke fallback contract instead of rejecting valid clean-shell proof.
- Added focused regression coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) proving both `zmem verify-public-verify --summary-only` and `zmem verify-return-packet --summary-only` accept a passing `venv-pth` receipt under the packaged requirement.

Verification:

- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_install_mode_satisfies_packaged_requirement_for_venv_pth tests.test_cli_onboarding.CliOnboardingTest.test_verify_public_verify_accepts_venv_pth_for_packaged_requirement tests.test_cli_onboarding.CliOnboardingTest.test_verify_return_packet_archive_accepts_venv_pth_for_packaged_requirement -q` -> 3 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 149 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only` -> OK; local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)` and the operator packet is still ready at `.zerker/launch-proof/public-verify-operator-packet.tar.gz`
- `python3 -m zerker_memory prelaunch --summary-only` -> expected non-zero / blocked only on `launch_assets` and `public_verify_evidence`

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed a false-negative verifier path, but it did not produce the missing external evidence or captured assets.

Next:

- Use `python3 -m zerker_memory status --summary-only` as the local handoff snapshot, verify the outbound archive with `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then forward the prompt/runbook/operator-packet triplet to a clean networked shell for the real public proof and asset pass.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only removed a local verifier mismatch that could have rejected a valid returned packet.
 
## 2026-06-04 - Atomic Packet Archive Writes

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: a real local handoff race still remained, because overlapping `zmem release-pack --summary-only` and `zmem verify-operator-packet --summary-only` reads could catch the operator packet or return packet tarball mid-write and report a false `archive invalid`.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the operator-packet and return-packet tarballs are now written to temp files and atomically replaced into place only after the full archive finishes, which keeps parallel verifier/status/read paths from seeing half-written packet archives.
- Added focused regression coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) proving failed packet rewrites preserve the last good archive instead of corrupting the clean-shell handoff surface.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_write_operator_packet_archive_preserves_existing_archive_on_failure tests.test_cli_onboarding.CliOnboardingTest.test_write_return_packet_archive_preserves_existing_archive_on_failure -q` -> 2 tests OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts tests.test_cli_onboarding.CliOnboardingTest.test_verify_operator_packet_archive_reports_ready_packet tests.test_release_smoke.ReleaseSmokeTest.test_ensure_operator_packet_summary_requires_strict_human_output -q` -> 3 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 146 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; the repo-local Phase-1 preflight still blocks only on missing clean-shell evidence plus launch assets, and it now finishes with `Operator packet: ok (archive ready at .zerker/launch-proof/public-verify-operator-packet.tar.gz (16/16 files packed))`.
- Live overlap check: parallel `python3 -m zerker_memory release-pack --summary-only` plus `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` both completed without the earlier transient `archive invalid` failure.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed a local packet-corruption race, but it did not produce the missing external evidence or captured assets.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the local preflight, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell for the real public proof and asset pass.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the Phase-1 packet archives safe to read while another chat refreshes them.

## 2026-06-04 - Launch Asset Verifier Cue Map

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the operator-packet and public-verify verifiers were already terminal-first, but `zmem verify-launch-assets --summary-only` still made another chat open the checklist or board to recover the exact per-shot command and capture cue.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-launch-assets --summary-only` now prints the full per-shot cue map inline for all required launch assets: deliverable filename, capture ID, source command, capture cue, and output path, while keeping the finalize-before-handback contract on the same screen.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs and preflight checks now describe the stronger launch-asset verifier surface consistently.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_verify_launch_assets_reports_missing_storyboard_items tests.test_cli_onboarding.CliOnboardingTest.test_verify_launch_assets_reports_ready_storyboard tests.test_release_smoke.ReleaseSmokeTest.test_ensure_launch_assets_summary_requires_strict_human_output -q` -> 3 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 144 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; the live Phase-1 preflight still blocks only on missing clean-shell evidence plus launch assets, and `zmem verify-launch-assets --summary-only` now shows the full command-plus-capture cue map for all eight required assets inline

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed the last terminal-first cue lookup on the launch-asset pass, but it did not produce the missing external evidence or captured assets.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the local preflight, forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell, then use the upgraded `zmem verify-launch-assets --summary-only` output or `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` to execute the eight-shot asset pass without opening extra docs.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the launch-asset verifier as self-sufficient as the other Phase-1 verifier surfaces.

## 2026-06-03 - Verifier Command Log Map Surfacing

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the generated packet, checklist, and compact summary already carried the five-command proof contract, but the two terminal-first verifier surfaces another chat is most likely to run before and after handoff still required bouncing back into markdown to recover the exact command-to-log map.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-operator-packet --summary-only` and `zmem verify-public-verify --summary-only` now print the full five-command clean-shell command-log map inline, including the expected saved log path and success cue for each command.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and refreshed [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so the Phase-1 smoke now fails if either verifier summary drops that terminal-first command-log contract again.
- Synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs now describe the stronger verifier summaries accurately.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_operator_packet_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_summary_requires_strict_human_output -q` -> 2 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 43 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; the live Phase-1 preflight now shows `Command log map:` inline on both `verify-operator-packet` and `verify-public-verify`, while strict publish remains blocked only on missing clean-shell evidence plus launch assets

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed the last terminal-first command/log lookup gap, but it did not produce the missing external evidence or launch assets.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the local preflight, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell; the operator and orchestrator can now recover the full five-command command-log contract directly from `verify-operator-packet` and `verify-public-verify` before the real public proof run starts.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the two terminal-first verifier surfaces self-sufficient enough that another chat can execute or audit the outbound packet from one command.

## 2026-06-03 - Public Verify Summary Log Map

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the clean-shell runbook and checklist already carried the exact five-command log contract, but the compact `public-verify-summary.md` artifact that another chat is most likely to forward on its own still did not restate that map.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the generated `.zerker/launch-proof/public-verify-summary.md` now includes the exact five-command clean-shell command-to-log map plus the existing success confirmations for `curl-install.log`, `first-run.log`, `release-pack.log`, `packaged-release-smoke.log`, and `prelaunch.log`.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and refreshed [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so the Phase-1 preflight now fails if that compact summary loses the command-log contract again.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_result_summary_artifact_requires_handoff_contract -q` -> 1 test OK
- `python3 -m unittest tests.test_release_smoke -q` -> 43 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; Phase-1 preflight still blocks only on missing clean-shell evidence plus launch assets, and the regenerated `.zerker/launch-proof/public-verify-summary.md` now includes `## Command Log Map` with all five expected proof-log commands
- `python3 -m zerker_memory status --summary-only` -> OK; current local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)` and strict publish remains blocked only on the missing external logs/assets

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed one more handoff reconstruction step, but it did not produce the missing external evidence or launch assets.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the local preflight, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell; the regenerated `.zerker/launch-proof/public-verify-summary.md` can now travel with that packet as the compact five-command proof-log contract.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the compact summary artifact self-sufficient enough that another chat can validate the five saved proof logs from one screen.

## 2026-06-03 - Launch Asset Capture Board

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the Phase-1 checklists and verifier summaries were already explicit, but the screenshot/GIF pass still made another chat jump between markdown, the proof report, transcript, and handoff files instead of capturing from one stable reference surface.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem launch-proof` and `zmem release-pack --summary-only` now generate `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, include it in the outbound operator packet, carry it through the launch-proof manifest/report, and surface it from `zmem verify-launch-assets --summary-only`.
- Tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) so the launch-facing docs now point operators at the new capture board.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts tests.test_cli_onboarding.CliOnboardingTest.test_render_launch_proof_summary_lists_artifacts_and_next_steps tests.test_release_smoke.ReleaseSmokeTest.test_ensure_launch_assets_summary_requires_strict_human_output tests.test_release_smoke.ReleaseSmokeTest.test_ensure_operator_packet_summary_requires_strict_human_output -q` -> 4 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 144 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; the refreshed proof pack now verifies the outbound operator packet at `16/16 files packed`, and `zmem verify-launch-assets --summary-only` now points at `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` while strict publish remains blocked only on missing clean-shell evidence plus launch assets

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice reduced operator friction for the asset pass, but it did not produce the missing networked evidence or captured assets.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the local preflight, forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to a clean networked shell, then use `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` plus `.zerker/launch-proof/CAPTURE_CHECKLIST.md` to capture the eight required launch assets before handback.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only added a capture-ready board so another chat can execute the launch-asset storyboard from one stable proof surface.

## 2026-06-03 - Release Smoke Refreshed Status Pass

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the Phase-1 packet and verifier surfaces were already aligned, but the repo-local preflight command, `python3 scripts/release_smoke.py --summary-only`, still opened with a stale pre-refresh `status` snapshot instead of finishing on the refreshed operator packet state that another chat should actually forward.
- Updated [`scripts/release_smoke.py`](scripts/release_smoke.py) so the summary-only preflight now reruns `python3 -m zerker_memory status --summary-only` immediately after `release-pack --summary-only`, which leaves the terminal on the current launch-proof/operator-packet state before the verifier sequence continues.
- Added focused regression coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and synced the launch-facing wording in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the documented Phase-1 preflight now matches the shipped refreshed-status behavior.

Verification:

- `python3 -m py_compile scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_run_release_smoke_summary_prints_phase_one_preflight -q` -> 1 test OK
- `python3 -m unittest tests.test_release_smoke -q` -> 43 tests OK
- `python3 scripts/release_smoke.py --summary-only` -> passed; the summary now prints `status --summary-only`, `release-pack --summary-only`, then a second refreshed `status --summary-only` before operator-packet/public-verify/launch-asset/return-packet/prelaunch verification
- `python3 -m zerker_memory status --summary-only` -> OK; current local alpha gate remains `ok with warnings (launch_assets, public_verify_evidence)` and strict publish remains blocked only on the missing external logs/assets
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice improved the local orchestration proof surface, but it did not produce the missing networked evidence or launch assets.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the local handoff preflight, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell to capture the five proof logs and eight launch assets.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the repo-local preflight end on the refreshed operator packet state so another chat sees the right Phase-1 snapshot before handoff.

## 2026-06-03 - Clean-Shell Command Log Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo-local Phase-1 flow was stable, but the clean-shell operator packet still required another chat to reconstruct which exact command should create which saved proof log and what success cue each log had to show.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so generated `PUBLIC_VERIFY_CHECKLIST.md`, `CAPTURE_CHECKLIST.md`, and the fallback packet-local `CLEAN_SHELL_PUBLIC_VERIFY.md` now all carry the exact clean-shell command-to-log map with required success cues for `curl-install.log`, `first-run.log`, `release-pack.log`, `packaged-release-smoke.log`, and `prelaunch.log`.
- Synced the durable repo runbook in [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus the launch-facing docs in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) plus focused onboarding coverage so future `release-pack` refreshes fail if that one-screen log contract disappears.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py scripts/release_smoke.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_result_summary_artifact_requires_handoff_contract tests.test_release_smoke.ReleaseSmokeTest.test_run_release_smoke_summary_prints_phase_one_preflight -q` -> 3 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 144 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still blocks only on missing clean-shell evidence plus launch assets, and the refreshed packet/checklists now include the explicit command-log-success mapping for the external operator.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed the remaining local command/log ambiguity, but it did not produce the missing external evidence or launch assets.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell so that operator can produce the five mapped logs plus the eight required launch assets without re-deriving the Phase-1 contract.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the outbound packet, generated checklists, and durable runbook self-auditing enough that another chat can validate each returned log against its source command from one screen.

## 2026-06-03 - Release Pack Overlap Lock

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the latest Phase-1 surfaces were already aligned, but the main local operator command, `zmem release-pack --summary-only`, could still crash when overlapping chats refreshed `.zerker/launch-proof/` at the same time.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so launch-proof and release-pack refreshes now serialize through a repo-local `.zerker/launch-proof.lock`, while the launch-proof cleanup path also tolerates disappearing-file races during directory teardown instead of crashing mid-refresh.
- Added focused regression coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) for the missing-path cleanup race and preserved the existing Phase-1 contract surfaces without changing the operator packet, runbook, or release summaries.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_ignores_missing_target_dir_race tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_propagates_non_missing_target_dir_errors -q` -> 2 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 144 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; Phase-1 remains blocked only on missing clean-shell logs plus launch assets, and the repo-local release path no longer crashed during refresh.
- Isolated concurrent repro: two overlapping `python -m zerker_memory release-pack --summary-only` runs both completed with the expected prelaunch-blocked output and no traceback.

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This slice removed the local overlapping-refresh crash, but it did not produce the missing external evidence or launch assets.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell for the real public-repo/raw-installer proof and the eight launch assets.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only hardened the repo-local Phase-1 refresh path so overlapping chats no longer corrupt or tear down each other’s launch-proof work.

## 2026-06-03 - Launch Proof Report Handoff Surface

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the CLI summaries, packet verifier, and handoff docs were already aligned, but the generated `.zerker/launch-proof/index.html` proof report still stopped short of showing the operator prompt, runbook, and outbound packet triplet together on the same Phase-1 screen.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the launch-proof HTML report now surfaces the clean-shell runbook, copy-ready operator prompt, outbound operator packet, and explicit forward-together triplet inside the existing `Clean-Shell Public Verify` section, while the artifact list now also carries the prompt and packet path directly.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs now match the stronger proof-report handoff surface.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_surfaces_public_verify_contract_in_readme_and_report tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_result_summary_artifact_requires_handoff_contract -q` -> 2 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 142 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still blocks only on missing clean-shell evidence plus launch assets, and the generated `.zerker/launch-proof/index.html` proof report now includes the operator prompt, runbook, outbound packet path, and forward-together contract in the clean-shell section

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- The repo-local handoff surfaces are now aligned across CLI summaries, docs, packet verifier, and proof report, but another shell still has to produce the real networked evidence set and return packet.

Next:

- Forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell, have that operator run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard under `.zerker/launch-proof/assets/`, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only closed the last local proof-report handoff gap so another chat can resume Phase 1 from the generated HTML report without opening multiple artifacts first.

## 2026-06-03 - Status And Prelaunch Return-Packet Cue

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the dedicated verifier surfaces already enforced the correct handback contract, but the main operator entry points, `zmem status --summary-only` and `zmem prelaunch --summary-only`, still stopped short of explicitly telling another chat to rerun finalize and confirm receive-side acceptance before handback.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the shared next-step builders for status and prelaunch now append the same explicit Phase-1 handback step: rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, then confirm `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` is ready before handback.
- Refreshed focused onboarding coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the launch-facing docs and landing proof copy now match the stronger handback wording.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_prelaunch_next_steps_ready_path_points_at_generated_public_verify_artifacts tests.test_cli_onboarding.CliOnboardingTest.test_prelaunch_next_steps_prioritize_public_verify_before_launch_assets tests.test_cli_onboarding.CliOnboardingTest.test_build_status_next_steps_skips_duplicate_strict_publish_guidance tests.test_cli_onboarding.CliOnboardingTest.test_build_status_next_steps_prioritizes_public_verify_validation_before_launch_assets -q` -> 4 tests OK
- `python3 - <<'PY' ... build_status_next_steps(...) / prelaunch_next_steps(...) ... PY` -> both live helper probes now end with `After the clean-shell pass and asset capture, rerun .zerker/launch-proof/FINALIZE_RETURN_PACKET.sh, then confirm zmem verify-return-packet ... is ready before handback.`
- `python3 -m zerker_memory prelaunch --summary-only | rg -n "FINALIZE_RETURN_PACKET|verify-return-packet|Next:"` -> matched the new finalize plus receive-side acceptance step under `Next:`
- `python3 -m zerker_memory eval | python3 -c 'import sys,json; data=json.load(sys.stdin); print("EVAL:%s/%s" % (data["passed"], data["passed"] + data["failed"]))'` -> `EVAL:11/11`
- `rg -n "FINALIZE_RETURN_PACKET.sh|verify-return-packet .*before handback|After the clean-shell pass and asset capture" zerker_memory/cli.py tests/test_cli_onboarding.py README.md QUICKSTART.md docs/DAY1_AGENT_SETUP.md docs/PRODUCT_STATUS.md landing/index.html` -> updated contract surfaced across code, tests, docs, and landing copy

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- Full post-edit `zmem status --summary-only` and `python3 scripts/release_smoke.py --summary-only` runs were slow/buffered in this sandbox, so this slice verified the changed next-step contract through the shared builders, focused tests, `prelaunch` grep, eval, and doc/code surface checks instead of waiting indefinitely on full CLI output.

Next:

- Run `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py --summary-only`, verify the outbound archive locally with `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, capture the full eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the main status/prelaunch operator surfaces carry the same finalize-and-acceptance rule as the dedicated receive-side verifier.

## 2026-06-03 - Return Packet Receive-Side Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the send-side packet and clean-shell verifier were already explicit, but the receive-side `zmem verify-return-packet --summary-only` surface was still too thin for another chat to accept or reject a handback from one screen.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so return-packet verification now carries the receive-side handoff path, public-verify logs root, packaged-install requirement, pinned public repo/raw installer targets, and finalize-script path through the archive result, and the human summary now restates the rerun-then-finalize contract when a return packet is incomplete.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs now match the stronger receive-side acceptance surface.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_release_smoke.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_return_packet_summary_requires_strict_human_output tests.test_cli_onboarding.CliOnboardingTest.test_verify_return_packet_archive_reports_missing_logs tests.test_cli_onboarding.CliOnboardingTest.test_verify_return_packet_archive_reports_ready_packet -q` -> 3 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 142 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight stayed blocked only on missing clean-shell evidence plus launch assets, and `zmem verify-return-packet --summary-only` now restates the receive-side brief, packaged requirement, pinned public targets, and finalize rerun contract from one screen

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell; have that operator execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, capture the eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand the return packet back only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the receive-side acceptance surface as explicit as the send-side handoff surfaces.

## 2026-06-02 - Compact Public Verify Summary Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo already had a durable runbook, prompt, packet, and receive-side brief, but the compact `.zerker/launch-proof/public-verify-summary.md` artifact was still the weakest forwarded surface because it did not restate the full outbound and handback contract in one file.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the generated `public-verify-summary.md` now includes the exact open-first runbook path, operator prompt path, outbound operator-packet path, unpack command, forward-together triplet, verify-before-assets command, verify-after-assets command, and the receive-side `verify-return-packet` acceptance command alongside the existing target pinning and asset/log status.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) so the repo-local Phase-1 smoke now fails if that compact summary drops the new handoff contract, refreshed focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the launch-facing docs match the shipped summary behavior.

Verification:

- `python3 -m unittest tests.test_release_smoke.ReleaseSmokeTest.test_ensure_public_verify_result_summary_artifact_requires_handoff_contract tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_surfaces_public_verify_contract_in_readme_and_report -q` -> 2 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 142 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight stayed blocked only on missing clean-shell evidence plus launch assets, and the regenerated `.zerker/launch-proof/public-verify-summary.md` now includes the outbound triplet plus receive-side acceptance command in one compact artifact
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected non-zero; still pending `0/5` clean-shell logs, but the compact summary now restates the exact forward/unpack/verify/receive contract for the next operator

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.

Next:

- Forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell, have that operator run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate with `zmem verify-public-verify --summary-only`, capture all eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the smallest forwarded artifact strong enough to carry the full send-and-receive contract by itself.

## 2026-06-02 - Launch Asset Storyboard Surfacing

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the operator packet already carried the full eight-shot storyboard, but the launch-asset verifier still only listed missing filenames, which left the screenshot/GIF pass as the weakest terminal-first handoff surface in the loop.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-launch-assets --summary-only` now prints the full eight-shot storyboard inline from the manifest, including each deliverable filename, capture ID, output path, and the finalize step to rerun before handback.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) so release smoke now fails if that asset-storyboard mapping disappears, refreshed focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), and [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md) so the launch-facing docs match the shipped verifier output.

Verification:

- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_verify_launch_assets_reports_missing_storyboard_items tests.test_cli_onboarding.CliOnboardingTest.test_verify_launch_assets_reports_ready_storyboard tests.test_release_smoke.ReleaseSmokeTest.test_ensure_launch_assets_summary_requires_strict_human_output -q` -> 3 tests OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected non-zero; still pending `0/8` assets, and now prints the exact eight deliverables with capture IDs plus `assets/...` output paths
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight stayed blocked only on missing clean-shell evidence plus launch assets while the launch-asset verifier now exposes the exact storyboard inline

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell; have that operator execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate with `zmem verify-public-verify --summary-only`, capture the eight launch assets using the now-inline `verify-launch-assets` storyboard, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand the return packet back for `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only moved the last thin launch-asset surface onto the same explicit terminal-first contract as the operator packet and release summaries.

## 2026-06-02 - Outbound Handoff Triplet Surfacing

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo had already generated the right operator artifacts, but the main orchestrator surfaces still made another chat reconstruct which files needed to be forwarded together before the clean-shell pass.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the Phase-1 summaries now explicitly restate the outbound handoff triplet: `CLEAN_SHELL_OPERATOR_PROMPT.md`, `CLEAN_SHELL_PUBLIC_VERIFY.md`, and `public-verify-operator-packet.tar.gz`. That triplet now appears in `zmem release-pack --summary-only`, `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, and in the generated status/prelaunch next-step guidance.
- Refreshed the summary-contract coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) so release smoke now fails if the outbound handoff triplet disappears from those human-readable summaries, and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), and [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md) so the user-facing launch docs match the shipped wording.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now prints the exact outbound triplet on status/release-pack/prelaunch guidance and on the operator-packet/public-verify summaries while remaining blocked only on missing clean-shell evidence plus launch assets

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together to a clean networked shell; have that operator execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate with `zmem verify-public-verify --summary-only`, capture the eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand the return packet back for `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the outbound packet, runbook, and prompt an explicit forward-together contract on the main orchestrator surfaces.

## 2026-06-02 - Public Verify Summary Target Pinning

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the outbound packet, verifier summaries, and runbook already pinned the exact public proof targets, but the most-forwarded artifact, `.zerker/launch-proof/public-verify-summary.md`, still dropped that target pinning and the explicit packaged-install completion rule.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `render_public_verify_result_summary()` now writes the expected public repo URL, raw installer URL, and the `5/5 logs + receipt ok + packaged install mode` completion rule directly into the generated `public-verify-summary.md` artifact, using the launch-proof manifest when present.
- Kept the focused Phase-1 contract aligned in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and refreshed launch-facing copy in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the compact summary surface now matches the shipped verifier/runbook contract.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 99 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 42 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python -m zerker_memory launch-proof --summary-only` -> passed; regenerated `.zerker/launch-proof/public-verify-summary.md` with the pinned public repo/raw installer targets and packaged-install completion rule
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still blocks only on missing clean-shell evidence plus missing launch assets while the live release surfaces show the same pinned proof targets and completion contract

Blockers:

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the five clean-shell logs, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- `python3 scripts/release_smoke.py --require-install-mode packaged` was not rerun in this sandbox after this docs/summary slice because the real final proof is still network-dependent here.

Next:

- Hand `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to a clean networked shell, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus the eight-asset screenshot/GIF pass; this run only tightened the forwarded summary artifact so that sidecar receives the same pinned proof targets and completion rule as the verifier and runbook.

## 2026-06-02 - Phase 1 Completion Contract Surfacing

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo-local verifier surfaces already agreed on the missing evidence, but another operator still had to infer the exact Phase-1 done condition across multiple summaries before handing the packet back.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only`, `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, `zmem verify-launch-assets --summary-only`, and `zmem verify-return-packet --summary-only` now all print the explicit completion or acceptance contract for the clean-shell loop instead of only listing missing artifacts.
- Refreshed [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), and [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md) so the user-facing launch instructions now restate that same completion contract, and tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py).

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack, kept strict publish blocked only on missing public-verify evidence plus launch assets, and now prints the explicit Phase-1 completion contract
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected non-zero; still pending `0/5` logs and now prints the exact packaged-install completion condition
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected non-zero; still pending `0/8` assets and now prints the finalize-before-handback condition
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected non-zero; still pending logs/assets and now prints the explicit receive-side acceptance rule
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight stayed stable and now shows the same completion contract across release-pack, operator-packet, public-verify, launch-assets, and return-packet surfaces

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to a clean-network operator; have them prove `https://github.com/zerkerlabs/zerker-memory`, run the raw installer from `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture all eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand the packet back only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only tightened the explicit done/acceptance contract so the next chat can execute that external pass without reconstructing success criteria from multiple files.

## 2026-06-02 - Public Verify Start-Here Summary

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the shipped clean-shell packet and operator verifier already exposed the start-here contract, but `zmem verify-public-verify --summary-only` was still the main post-run gate another chat would consult and it omitted the operator prompt, the `Open first` runbook cue, and the unpack command needed to continue the handoff from one screen.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `verify_public_verify()` now carries the packet-local runbook path, operator prompt path, and operator-packet archive path through the verifier result, and `render_public_verify_summary()` now prints the operator prompt, `Open first: CLEAN_SHELL_PUBLIC_VERIFY.md`, and the exact tar unpack command alongside the existing log/result/install-mode checks.
- Tightened the Phase-1 smoke contract in [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so release smoke now fails if the public-verify summary drops that start-here handoff context, then refreshed [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) to match the shipped verifier output.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 141 tests OK
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now shows the operator prompt, `Open first` runbook cue, and unpack command in `verify-public-verify --summary-only`, while strict publish remains blocked only on `public_verify_evidence` and `launch_assets`
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected non-zero; blocked at `0/5` logs, but now prints `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `mkdir -p .zerker/launch-proof && tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof`
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, verify the outbound archive with `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then hand `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to a clean-network operator so they can open `CLEAN_SHELL_PUBLIC_VERIFY.md` first, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, capture the eight launch assets, finalize the return packet, and hand it back for `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the post-run verifier itself restate the shipped start-here contract so another chat can resume the handoff without opening multiple files.

## 2026-06-02 - Durable Operator Prompt Handoff

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage local slice was making the send-side operator brief durable and impossible to miss; the generated packet already carried a prompt, but the stable repo docs still did not treat it as a first-class handoff artifact.
- Added durable [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md) as the stable repo-level source for the exact prompt another chat or human operator should receive before the clean-shell public-proof run.
- Updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the send-side Phase-1 handoff now consistently points at both the durable runbook and the durable operator prompt.
- Regenerated the live launch packet with `zmem release-pack --summary-only`, which refreshed `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, kept the operator packet at `15/15 files packed`, and updated the release/prelaunch next-step guidance to explicitly hand that prompt to the clean-shell operator with the outbound bundle.

Verification:

- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero strict publish result; regenerated the launch pack and now surfaces `Operator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` plus a prompt-forwarding next step.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now shows the operator prompt across `release-pack`, `verify-operator-packet`, `verify-public-verify`, and `prelaunch` summaries while strict publish remains blocked only on missing external logs and launch assets.

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand both [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) and [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md) or their packet-local `.zerker/launch-proof/` copies plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; have them restore the tarball, run `PUBLIC_VERIFY_COMMANDS.sh`, validate with `zmem verify-public-verify --summary-only`, capture the eight launch assets, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the send-side operator brief durable and explicit for the next chat.

## 2026-06-02 - Operator Prompt Surface Completion

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage local slice was finishing the operator-facing handoff surface; `CLEAN_SHELL_OPERATOR_PROMPT.md` already existed in the packet, but the main CLI summaries and smoke contract still made another chat reconstruct that artifact by hand.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the release-pack, launch-proof, operator-packet, public-verify, launch-assets, and return-packet summaries all surface the operator prompt path and the current Phase-1 completion bar beside the existing runbook/script/archive paths.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) plus focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so the shipped Phase-1 contract now requires the operator prompt path and the current `15/15 files packed` packet state.
- Refreshed [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) so another chat is explicitly told when to use `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` versus the longer runbook.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; printed the operator prompt path, kept the operator packet at `15/15 files packed`, and stayed blocked only on missing public-verify evidence and launch assets
- `python3 -m zerker_memory prelaunch --summary-only` -> expected non-zero; `Next:` now includes handing `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` to the clean-shell operator before the shipped script step
- `python3 scripts/release_smoke.py --summary-only` -> passed; release smoke now proves the operator prompt path across release-pack, operator-packet verify, public-verify verify, launch-assets verify, return-packet verify, and prelaunch

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`, so the packaged-install claim still needs a normal networked shell.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the repo-local preflight, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` to the clean-shell operator or separate chat. Have them restore the packet, open `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, capture the eight launch assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` for receive-side acceptance with `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only completed the local operator-facing surfaces so another chat can execute the existing Phase-1 proof loop from one copy-ready prompt.

## 2026-06-02 - Operator Prompt Next-Step Surfacing

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage local slice was pushing the existing operator prompt into the default orchestration path; the prompt was already in the proof pack, but the repo’s main next-step surfaces still made another chat reconstruct that brief instead of pointing at the shipped artifact directly.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so both `zmem status --summary-only` and `zmem prelaunch --summary-only` now explicitly tell the orchestrator to hand `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` to the clean-shell operator alongside the outbound packet before the public-verify script step.
- Updated focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the Phase-1 next-step ordering now stays locked to operator-packet verify -> operator prompt handoff -> clean-shell script -> public-verify check -> launch-asset capture.
- Refreshed the release-facing docs in [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the public handoff contract now consistently tells another chat to pair the outbound tarball with the copy-ready operator prompt instead of improvising the brief.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now shows the operator-prompt handoff step in both `status` and `prelaunch` while strict publish remains blocked only on missing public-verify evidence and launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64`, the venv-local import bootstrap can exhaust disk here, and the final fallback still cannot prove a packaged install from this sandbox.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` together with `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`; have the clean-shell operator confirm `https://github.com/zerkerlabs/zerker-memory` plus `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, open `CLEAN_SHELL_PUBLIC_VERIFY.md` first from the restored packet, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate with `zmem verify-public-verify --summary-only`, capture the eight launch assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the copy-ready operator prompt a first-class part of the shipped Phase-1 handoff so another chat can pick up that external pass without rewriting instructions.

## 2026-06-02 - Phase 1 Completion Contract Surfacing

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo-local verifier surfaces already agreed on the missing evidence, but another operator still had to infer the exact Phase-1 done condition across multiple summaries before handing the packet back.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only`, `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, `zmem verify-launch-assets --summary-only`, and `zmem verify-return-packet --summary-only` now all print the explicit completion or acceptance contract for the clean-shell loop instead of only listing missing artifacts.
- Refreshed [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), and [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md) so the user-facing launch instructions now restate that same completion contract, and tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py).

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; still blocked only on `public_verify_evidence` and `launch_assets`, and now prints the explicit Phase-1 completion contract
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected non-zero; still pending `0/5` logs and now prints the exact packaged-install completion condition
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> expected non-zero; still pending `0/8` assets and now prints the finalize-before-handback condition
- `python3 -m zerker_memory verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` -> expected non-zero; still pending logs/assets and now prints the explicit receive-side acceptance rule
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight stayed stable and now shows the same completion contract across release-pack, operator-packet, public-verify, launch-assets, and return-packet surfaces

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to a clean-network operator; have them prove `https://github.com/zerkerlabs/zerker-memory`, run the raw installer from `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture all eight launch assets, rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand the packet back only when `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only tightened the explicit done/acceptance contract so the next chat can execute that external pass without reconstructing success criteria from multiple files.

## 2026-06-02 - Offline Packaged Smoke Unblock

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, but the highest-leverage remaining local gap was the repo-local packaged smoke path still collapsing to `local-wrappers` in a fresh network-restricted venv, which left the Phase-1 installability claim partially unproven inside this sandbox.
- Updated [`scripts/release_smoke.py`](scripts/release_smoke.py) so the install fallback chain now inserts a venv-local `.pth` import bootstrap before the old wrapper-only fallback, and `--require-install-mode packaged` now accepts the new `venv-pth` mode alongside the existing editable modes while still rejecting `local-wrappers`.
- Mirrored that same offline bootstrap in [`install.sh`](install.sh), refreshed the fallback wording in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and tightened focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) plus [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) to lock the new fallback contract and the path-format expectations around the public-verify summary.

Verification:

- `python3 -m py_compile scripts/release_smoke.py tests/test_release_smoke.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --require-install-mode packaged` -> passed; the fresh temp env failed the networked editable install and `--no-build-isolation` retry as expected, then completed the full smoke path with `install_mode: venv-pth` instead of dropping to `local-wrappers`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the repo-local preflight, then hand `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to a clean-network operator; have them prove `https://github.com/zerkerlabs/zerker-memory`, run the raw installer from `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the eight launch assets, finalize the return packet, and hand it back for `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only removed the remaining local packaged-smoke fallback blocker so the next chat can focus on the real external evidence pass.

## 2026-06-02 - Release-Pack Target Pinning

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: `zmem release-pack --summary-only` is the main Phase-1 entrypoint another chat sees first, but it still required opening deeper verifier surfaces to restate the exact public targets and packet-local runbook before the clean-shell handoff began.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only` now prints the expected public repo URL, expected raw installer URL, and `Open first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` directly in the top-level release summary.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so the shipped release-smoke contract now fails if those pinned targets disappear from the release-pack summary again.
- Refreshed the user-facing release-path docs in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the documented Phase-1 entrypoint matches the shipped CLI output.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_release_smoke -q` -> 42 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; the live release-pack summary now prints `Expected public repo: https://github.com/zerkerlabs/zerker-memory`, `Expected raw install URL: https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, and `Open first: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack and kept strict publish blocked only on missing public-verify evidence and launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch packaging dependencies, so packaged-install proof still needs a normal networked shell.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` to a clean-network operator; have them restore the packet, open `CLEAN_SHELL_PUBLIC_VERIFY.md` first, run `PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, capture all eight launch assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and return `.zerker/launch-proof/public-verify-return-packet.tar.gz` for receive-side acceptance with `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only made the top-level `release-pack` surface self-contained enough that another chat no longer has to reconstruct the proof targets before handing off the packet.

## 2026-06-02 - Release Panel Storyboard Visibility

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage local slice was making the final screenshot/GIF pass harder to mis-execute; the CLI/checklists already carried the exact eight-asset storyboard, but `zmem ui` still only showed counts and missing paths instead of the full capture plan on the release surface itself.
- Updated [`zerker_memory/dashboard.py`](zerker_memory/dashboard.py) so the release panel, release-pack proof summary, and `Verify Launch Assets` proof summary now render the shipped launch-asset storyboard directly from the launch-proof manifest, including each deliverable, capture id, output path, and captured-vs-missing state.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so both release-readiness state and `zmem verify-launch-assets` return the normalized `expected_launch_assets` list that the console can render without reconstructing it from prose.
- Added focused coverage in [`tests/test_dashboard.py`](tests/test_dashboard.py) so the console HTML, release-readiness state, and launch-assets verifier all stay pinned to the storyboard contract.

Verification:

- `python3 -m unittest tests.test_dashboard tests.test_cli_onboarding` -> 112 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only` -> passed; release state still shows operator packet ready, public verify pending `0/5`, launch assets pending `0/8`, and strict publish blocked only on `public_verify_evidence` plus `launch_assets`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still refreshes `release-pack`, verifies the operator packet, and stays intentionally blocked only on the external public-verify evidence plus launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot be closed from this network-restricted environment, so the packaged-install proof still needs a normal networked shell.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Use `zmem release-pack --summary-only` plus `zmem ui` as the operator surface for the next external run: forward the verified operator packet to a clean-shell operator, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, then use the now-storyboarded release panel or `Verify Launch Assets` panel to capture and confirm all eight launch assets before `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` and receive-side `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus the eight-asset screenshot/GIF capture, now using the dashboard storyboard cards instead of only the markdown checklist.

## 2026-06-02 - Copy-Ready Clean-Shell Operator Prompt

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage local slice was removing the last handoff reconstruction step; the packet had the runbook, checklist, and verifier, but another chat still had to restate the operator task manually before starting the clean-shell pass.
- Added durable [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md) and updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only` now generates and ships `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` inside the operator packet, carries that path in the launch-proof manifest, and surfaces it through status, release-pack, public-verify, and operator-packet summaries.
- Updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) so the durable repo docs now tell the orchestrator to pair the outbound packet with the copy-ready prompt and brief another clean-shell chat from the shipped artifact instead of paraphrasing the flow.
- Kept focused proof coverage aligned in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), including the `15/15 files packed` operator-packet contract and the live operator prompt path.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack and now surfaces `Operator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` while strict publish remains blocked only on missing public-verify evidence and launch assets
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now shows the operator prompt in release-pack and public-verify summaries and keeps the clean-shell handoff order pinned to packet verify -> prompt -> script -> asset capture -> finalize

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`, so the packaged-install proof still needs a normal networked shell.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` to the clean-shell operator; have them restore the packet, run `zmem verify-operator-packet ... --summary-only`, follow `CLEAN_SHELL_PUBLIC_VERIFY.md`, validate the five logs with `zmem verify-public-verify --summary-only`, capture the eight launch assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` for receive-side acceptance with `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only added the copy-ready operator prompt artifact so another chat can execute that evidence pass without reconstructing instructions manually.

## 2026-06-02 - Operator Packet Script Preflight

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage local slice was hardening the outbound operator loop itself; the shipped packet could already be verified before handoff, but the generated clean-shell script still trusted the restored archive blindly once another operator started the final proof pass.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so generated `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` now fails fast by verifying `.zerker/launch-proof/public-verify-operator-packet.tar.gz` before it starts the live public-proof commands, and it writes that preflight output to `.zerker/launch-proof/public-verify-logs/operator-packet-verify.log` for operator-side debugging.
- Updated the durable repo runbook [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) so the repo-local preflight and clean-shell execution steps both describe the repeated operator-packet verification and the saved preflight log, keeping the external handoff contract aligned with the generated script.
- Refreshed focused onboarding coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the clean-shell script contract and current Phase-1 next-step ordering stay locked to the shipped operator-prompt-plus-script flow.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 99 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still shows launch proof/handoff/operator packet ready while strict publish remains blocked only on missing public-verify evidence and launch assets
- `python3 -m zerker_memory status --summary-only` (via release smoke) -> passed; operator packet now reports `15/15 files packed`, surfaces the bundled operator prompt path, and keeps the clean-shell script/verify/public-asset order intact

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`, so the packaged-install claim still needs a normal networked shell.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the repo-local preflight, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus either [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) or the bundled `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` to the clean-shell operator. Have them restore the packet, let `PUBLIC_VERIFY_COMMANDS.sh` re-verify the packet archive first, then run the live proof, validate the five logs with `zmem verify-public-verify --summary-only`, capture the eight launch assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` for receive-side acceptance with `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only hardened the fail-fast preflight inside the shipped clean-shell script so the next external operator does not spend time on a stale or incomplete packet.

## 2026-06-02 - Operator Prompt Contract Alignment

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the shipped clean-shell packet now includes a dedicated operator prompt artifact, but the focused smoke/test contract had drifted from the live Phase-1 surface and could no longer prove the release-pack/operator-packet path without manual inspection.
- Updated [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so release-smoke summary validation, launch-proof manifest fixtures, and the Phase-1 fake command outputs now require the copy-ready operator prompt path and the current `15/15 files packed` operator-packet contract.
- Kept focused onboarding coverage aligned with the shipped packet surface in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), so the operator-packet verifier remains locked to the 15-file archive and `CLEAN_SHELL_OPERATOR_PROMPT.md`.
- Re-verified the live Phase-1 path: `zmem release-pack --summary-only`, `zmem verify-operator-packet ... --summary-only`, and `python3 scripts/release_smoke.py --summary-only` now agree on the same operator prompt artifact, packet count, public targets, and remaining blockers.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 141 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack, surfaced `Operator prompt: .zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, and kept strict publish blocked only on missing public-verify evidence and launch assets
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> passed; outbound packet verifies as `15/15 files packed` and surfaces the operator prompt, runbook, expected public targets, expected logs, and eight-asset storyboard
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now matches the live release-pack/operator-packet contract including the operator prompt path and `15/15 files packed`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64`, the venv-local import bootstrap can exhaust disk here, and the final fallback still cannot prove a packaged install from this sandbox.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus either [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) or the bundled `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` to a clean-network operator. Have them restore the packet, confirm the repo and raw installer targets, run `PUBLIC_VERIFY_COMMANDS.sh`, validate the five logs with `zmem verify-public-verify --summary-only`, capture the eight launch assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and return `.zerker/launch-proof/public-verify-return-packet.tar.gz` for acceptance with `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only realigned the local proof contract so the next chat can focus on evidence capture instead of test/smoke drift.

## 2026-06-02 - Launch Plan Contract Lock

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage adjacent work was removing durable runbook drift; the generated packet and verifier already enforced the current clean-shell contract, but [`docs/LAUNCH_PLAN.md`](docs/LAUNCH_PLAN.md) still described an older ad hoc demo path instead of the shipped operator-packet loop.
- Updated [`docs/LAUNCH_PLAN.md`](docs/LAUNCH_PLAN.md) so the durable launch plan now matches the actual Phase-1 contract: repo-local preflight with `python3 scripts/release_smoke.py --summary-only`, `zmem release-pack --summary-only`, and `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`; proof of `https://github.com/zerkerlabs/zerker-memory` plus `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`; `zmem verify-public-verify --summary-only` before capture; the exact eight required launch assets; and receive-side acceptance only through `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`.
- Added `ensure_launch_plan_contract()` in [`scripts/release_smoke.py`](scripts/release_smoke.py) so release smoke now fails if the durable launch plan drops any of those Phase-1 operator contract details.
- Added focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) to keep that doc-contract guard pinned.

Verification:

- `python3 -m py_compile scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_release_smoke -q` -> 40 tests OK
- `python3 scripts/release_smoke.py --summary-only` -> passed; release summary completed and stayed blocked only on missing clean-shell evidence plus missing launch assets
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; printed the human summary, refreshed the packet surfaces, and kept strict publish blocked on public verify plus launch assets
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` and the fallback env lacks `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to a clean-shell operator; have them confirm the repo is `https://github.com/zerkerlabs/zerker-memory`, run the raw installer from `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only locked the durable repo launch plan to the shipped operator packet contract so another chat does not follow stale Phase-1 instructions.

## 2026-06-02 - Clean-Shell Stop-Rule Hardening

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external proof is still blocked here, so the highest-leverage adjacent work was making the shipped operator packet harder to mis-execute; the clean-shell materials already described the happy path, but they still lacked explicit stop/reject rules for URL mismatches, wrapper fallback, failed verify steps, and bad handback packets.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) plus the durable repo runbook [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) so the generated `PUBLIC_VERIFY_CHECKLIST.md`, `PUBLIC_VERIFY_HANDOFF.md`, `RECEIVE_VERIFY_HANDOFF.md`, and packet-local `CLEAN_SHELL_PUBLIC_VERIFY.md` now all include explicit stop conditions or rejection rules for the clean-shell pass and receive-side acceptance.
- Fixed the release-pack regression surfaced during verification by threading `public_verify_operator_prompt_path` back through the `run_release_pack()` manifest refresh path, so `python3 -m zerker_memory release-pack --summary-only` works again after the operator-prompt artifact addition.
- The outbound operator packet now carries the copy-ready operator prompt as a first-class artifact and verifies as `15/15 files packed` instead of silently omitting that path from the refreshed release-pack manifest.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 99 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still shows launch proof/handoff/operator packet ready while strict publish remains blocked only on missing public-verify evidence and launch assets
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack, now surfaces the operator prompt path, and keeps strict publish blocked only on missing public-verify evidence and launch assets
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> passed; outbound packet now verifies as `15/15 files packed` and surfaces the operator prompt, bundled runbook, expected public targets, expected logs, and launch-asset storyboard

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`, so the packaged-install claim still needs a normal networked shell.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the repo-local preflight, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus either [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) or the bundled `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` to the clean-shell operator. Have them restore the packet, open the runbook first, run `PUBLIC_VERIFY_COMMANDS.sh`, stop immediately on any stop-condition failure, verify the five logs with `zmem verify-public-verify --summary-only`, capture the eight launch assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and only then hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` for receive-side acceptance with `zmem verify-return-packet ... --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run tightened the shipped operator packet contract so the next external operator can fail fast instead of improvising around a bad proof run.

## 2026-06-02 - Pre-Release Surface Truthfulness

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local slice was tightening the very first receive-side surface; before `zmem release-pack --summary-only` runs, `zmem status --summary-only` and the console release panel still advertised packet-local scripts/checklists as if they already existed, which could send another chat into the clean-shell loop before the proof pack had even been generated.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the repo status summary now collapses the pre-release-pack release section to one explicit instruction: run `zmem release-pack --summary-only` first, then follow the generated operator packet/runbook/checklists after they exist.
- Updated [`zerker_memory/dashboard.py`](zerker_memory/dashboard.py) so `zmem ui` mirrors that same contract and tells the operator to generate the release pack first whenever launch-proof artifacts are still missing, instead of rendering downstream packet/script paths prematurely.
- Added focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the pre-release-pack status summary keeps that narrower contract locked in.

Verification:

- `python3 -m py_compile zerker_memory/cli.py zerker_memory/dashboard.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_dashboard -q` -> 112 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only` -> passed; before `release-pack`, the live release section now says to run `zmem release-pack --summary-only` first instead of printing packet-local proof paths prematurely
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack and still blocked strict publish only on missing public-verify evidence and launch assets
- `python3 scripts/release_smoke.py --summary-only` -> passed; the release-smoke status step now stays truthful before `release-pack`, while the subsequent `release-pack`/`verify-operator-packet` path still surfaces the exact public repo URL and raw installer URL

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` and the fallback env lacks `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; have them confirm the repo is `https://github.com/zerkerlabs/zerker-memory`, run the raw installer from `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only removed the last misleading pre-release-pack proof copy so another chat now gets the right first step before the external loop starts.

## 2026-06-01 - Landing Packet Restore Callout

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo docs, CLI summaries, and generated packet already agreed that the clean-shell operator must restore the outbound tarball and open the packet-local runbook first, but the public landing proof copy still skipped that restore step and could leave a separate operator with a one-file bundle but no clear first action.
- Updated [`landing/index.html`](landing/index.html) so the public launch-proof story now explicitly tells the clean-shell operator to restore `.zerker/launch-proof/public-verify-operator-packet.tar.gz` back into `.zerker/launch-proof/`, open `CLEAN_SHELL_PUBLIC_VERIFY.md` from the restored packet first, and only then run `PUBLIC_VERIFY_COMMANDS.sh`.
- Refreshed [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) and the automation memory so the next chat sees that this run was a Phase-1 launch-copy alignment pass, not a new product feature.

Verification:

- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> passed; live operator-packet summary still prints the restore command, packet-local runbook, expected public repo/raw installer URLs, and launch-asset storyboard.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still shows launch proof/handoff/operator packet ready while strict publish remains blocked only on missing public-verify evidence and launch assets.
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the repo-local preflight, then hand `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus either `docs/CLEAN_SHELL_PUBLIC_VERIFY.md` or the packet-local `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` to the clean-shell operator; have them restore the tarball into `.zerker/launch-proof/`, run `PUBLIC_VERIFY_COMMANDS.sh`, validate with `zmem verify-public-verify --summary-only`, capture the eight launch assets, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only removed the last public-facing restore-step omission from the launch proof story.

## 2026-06-01 - Public Proof Target Pinning

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local slice was tightening the last operator ambiguity; the clean-shell packet already required the right script, but the first receiving surfaces did not all restate the exact GitHub repo URL and raw `install.sh` URL that another shell must prove.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the launch-proof manifest now carries the expected public repo URL plus raw installer URL, and the shipped `verify-operator-packet` / `verify-public-verify` summaries now print both values directly.
- Refreshed the generated Phase-1 handoff surfaces so `PUBLIC_VERIFY_HANDOFF.md`, the bundled `CLEAN_SHELL_PUBLIC_VERIFY.md`, and the operator packet all tell the clean-shell operator to prove `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` before trusting the run. Updated [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) to keep the durable repo-level runbook aligned with the generated packet copy.
- Added focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the manifest, operator-packet summary, public-verify summary, and generated handoff/runbook all stay pinned to those exact public targets.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 138 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack and kept strict publish blocked only on missing public-verify evidence and launch assets
- `python3 scripts/release_smoke.py --summary-only` -> passed; `verify-operator-packet` and `verify-public-verify` now both print the expected public repo URL and raw installer URL in the live Phase-1 preflight
- `python3 scripts/release_smoke.py --require-install-mode packaged` -> expected failure in this environment; still falls back to `install_mode=local-wrappers` after `setuptools>=64` fetch failure and missing `bdist_wheel`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` and the fallback env lacks `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; have them confirm the repo is `https://github.com/zerkerlabs/zerker-memory`, run the raw installer from `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run narrowed the operator contract so another chat now sees the exact public repo/raw installer targets on every receive-side proof surface.

## 2026-06-01 - Status Gate Ordering Alignment

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local slice was tightening the first-screen operator contract; `zmem status --summary-only` still listed launch-asset capture before `zmem verify-public-verify --summary-only`, which made the clean-shell handoff order drift from the shipped runbook and verifier flow.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the release-blocker next steps in `build_status_next_steps()` now keep `verify-public-verify` immediately after the clean-shell script step whenever public proof is still pending, before any screenshot/GIF capture guidance or return-packet handback.
- Added focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) to lock the Phase-1 ordering contract: operator-packet preflight -> clean-shell script -> `verify-public-verify` -> launch-asset capture.

Verification:

- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 99 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only` -> passed; the live next-step order now prints `verify-public-verify` before `.zerker/launch-proof/CAPTURE_CHECKLIST.md`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still ends with `verify-public-verify` before launch-asset capture while the known external blockers remain `0/5` public-verify logs and `0/8` launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; have them open `CLEAN_SHELL_PUBLIC_VERIFY.md` first from the unpacked bundle, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run only tightened the status-screen ordering so another chat gets the same Phase-1 sequence from the first command output as from the generated runbook.

## 2026-06-01 - Console Release Surface Hardening

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local slice was to make the `zmem ui` release surface as explicit as the CLI handoff contract while fixing the live launch-proof/release-pack regressions uncovered during verification.
- Expanded [`zerker_memory/dashboard.py`](zerker_memory/dashboard.py) and release-readiness state in [`zerker_memory/cli.py`](zerker_memory/cli.py) so the console now surfaces the operator packet, public-verify summary/runbook, return-packet archive, and the exact missing clean-shell logs and launch assets directly in the release views instead of forcing the operator to cross-reference multiple files.
- Fixed the live Phase-1 proof path in [`zerker_memory/cli.py`](zerker_memory/cli.py): `run_launch_proof()` now always threads the bundled runbook into the manifest contract, preserves the 14-file operator packet, and keeps the intended `ok with warnings (launch_assets, public_verify_evidence)` versus `blocked (launch_assets, public_verify_evidence)` gate snapshot even outside a full repo surface, so `release-pack --summary-only` and `scripts/release_smoke.py --summary-only` return to a truthful blocked state instead of crashing.
- Refreshed [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the user-facing console claims now match the shipped release panel behavior.

Verification:

- `python3 -m py_compile zerker_memory/cli.py zerker_memory/dashboard.py tests/test_cli_onboarding.py tests/test_release_smoke.py tests/test_dashboard.py` -> OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding tests.test_dashboard -q` -> 150 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now stays stable, reports `Operator packet: ok (14/14 files packed)`, surfaces `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and still shows the expected external blockers `0/5` public-verify logs and `0/8` launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; have them open `CLEAN_SHELL_PUBLIC_VERIFY.md` first from the unpacked bundle, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the shipped operator bundle tell the next chat exactly which file to open first.

## 2026-06-01 - Launch Proof Transcript Snapshot Refresh

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local work was tightening the proof packet itself; the generated launch-proof transcript could still carry a stale `Launch proof: missing` snapshot inside a freshly generated pack, which made the outbound Phase-1 evidence set internally contradictory.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `run_launch_proof()` still writes the transcript early enough for launch-proof readiness checks, then rewrites that transcript at the end with the post-pack status snapshot instead of leaving the stale pre-pack release view in the final artifact.
- Tightened focused onboarding coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the standalone launch-proof contract now asserts `Launch proof: ok` in the generated transcript and status summary and rejects the stale `Launch proof: missing` wording in those final proof-pack artifacts.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 137 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack and kept strict publish blocked only on `launch_assets` and `public_verify_evidence`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still reports `0/5` public-verify logs and `0/8` launch assets while refreshing the launch pack
- `rg -n "Launch proof: missing|Launch proof: ok" .zerker/launch-proof/terminal-transcript.txt` -> only `Launch proof: ok`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run removed the last stale launch-proof snapshot inside the generated transcript so the outbound proof pack no longer contradicts its own final status.

## 2026-06-01 - Standalone Public Verify Gate

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the outbound operator packet and receive-side return-packet verifier already existed, but another chat still had no single shipped command that said whether the clean-shell logs plus result receipt were valid before starting the screenshot pass.
- Added `zmem verify-public-verify --summary-only` in [`zerker_memory/cli.py`](zerker_memory/cli.py). It verifies the clean-shell log contract, validates the machine-readable receipt, checks the packaged-install requirement, and prints the exact checklist/handoff/result paths from one command.
- Threaded that verifier through the generated Phase-1 operator contract: `PUBLIC_VERIFY_HANDOFF.md`, `PUBLIC_VERIFY_CHECKLIST.md`, `PUBLIC_VERIFY_COMMANDS.sh`, `FINALIZE_RETURN_PACKET.sh`, status/prelaunch/release next-step guidance, and the durable repo runbook now all tell the operator to validate the clean-shell proof before moving to launch-asset capture.
- Updated focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and refreshed launch-facing docs in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md).

Verification:

- `python3 -m unittest tests.test_release_smoke -q` -> 39 tests OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 98 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; `Launch proof: ok`, `Handoff: ok`, `Operator packet: ok (14/14 files packed)`, strict publish still blocked only on `public_verify_evidence` and `launch_assets`
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected non-zero; new summary reports `0/5` logs captured, points at the receipt/checklist/handoff paths, and keeps the packaged-install requirement explicit
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 summary now exercises `verify-public-verify` between operator-packet and launch-asset checks

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the clean-shell proof validation itself a first-class shipped step so that sidecar can fail fast before recording collateral.

## 2026-06-01 - Console Release Surface Hardening

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local slice was to make the `zmem ui` release surface as explicit as the CLI handoff contract while fixing the live launch-proof/release-pack regressions uncovered during verification.
- Expanded [`zerker_memory/dashboard.py`](zerker_memory/dashboard.py) and release-readiness state in [`zerker_memory/cli.py`](zerker_memory/cli.py) so the console now surfaces the operator packet, public-verify summary/runbook, return-packet archive, and the exact missing clean-shell logs and launch assets directly in the release views instead of forcing the operator to cross-reference multiple files.
- Fixed the live Phase-1 proof path in [`zerker_memory/cli.py`](zerker_memory/cli.py): `run_launch_proof()` now always threads the bundled runbook into the manifest contract, preserves the 14-file operator packet, and keeps the intended `ok with warnings (launch_assets, public_verify_evidence)` versus `blocked (launch_assets, public_verify_evidence)` gate snapshot even outside a full repo surface, so `release-pack --summary-only` and `scripts/release_smoke.py --summary-only` return to a truthful blocked state instead of crashing.
- Refreshed [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the user-facing console claims now match the shipped release panel behavior.

Verification:

- `python3 -m py_compile zerker_memory/cli.py zerker_memory/dashboard.py tests/test_cli_onboarding.py tests/test_release_smoke.py tests/test_dashboard.py` -> OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding tests.test_dashboard -q` -> 150 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now stays stable, reports `Operator packet: ok (14/14 files packed)`, surfaces `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and still shows the expected external blockers `0/5` public-verify logs and `0/8` launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus the bundled `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` to the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the console and proof-path state consistent enough that another chat can operate from one release surface without reconstructing the remaining blocker set.

## 2026-06-01 - Operator Packet Open-First Runbook

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, but the outbound operator tarball still depended on repo docs/chat context for the durable clean-shell brief, so another chat could receive the packet without the stable runbook that already existed in `docs/`.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so fresh launch-proof packs now copy `docs/CLEAN_SHELL_PUBLIC_VERIFY.md` into `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, carry that path in the manifest/public-verify contract, include it in `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, surface it through `status`, `launch-proof`, `release-pack`, and `verify-operator-packet` summaries, and explicitly print `Open first: CLEAN_SHELL_PUBLIC_VERIFY.md` from the operator-packet verifier.
- Tightened the release-smoke contract in [`scripts/release_smoke.py`](scripts/release_smoke.py), aligned focused onboarding/release-smoke coverage, and refreshed launch-facing docs so the shipped Phase-1 packet contract now explicitly includes the bundled runbook copy before the clean-shell pass starts.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 137 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch packet and now reports `Public verify runbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` plus `Operator packet: ok (14/14 files packed)`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now surfaces `Open first: CLEAN_SHELL_PUBLIC_VERIFY.md` in the operator packet summary while the real blockers remain the expected `0/5` public-verify logs and `0/8` launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) or the bundled `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator: have them open `CLEAN_SHELL_PUBLIC_VERIFY.md` first from the unpacked bundle, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the outbound tarball self-contained with the same durable runbook another chat would otherwise have to open separately.

## 2026-06-01 - Launch Proof Transcript Snapshot Refresh

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local work was tightening the proof packet itself; the generated launch-proof transcript could still carry a stale `Launch proof: missing` snapshot inside a freshly generated pack, which made the outbound Phase-1 evidence set internally contradictory.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `run_launch_proof()` still writes the transcript early enough for launch-proof readiness checks, then rewrites that transcript at the end with the post-pack status snapshot instead of leaving the stale pre-pack release view in the final artifact.
- Tightened focused onboarding coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the standalone launch-proof contract now asserts `Launch proof: ok` in the generated transcript and status summary and rejects the stale `Launch proof: missing` wording in those final proof-pack artifacts.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 137 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack and kept strict publish blocked only on `launch_assets` and `public_verify_evidence`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still reports `0/5` public-verify logs and `0/8` launch assets while refreshing the launch pack
- `rg -n "Launch proof: missing|Launch proof: ok" .zerker/launch-proof/terminal-transcript.txt` -> only `Launch proof: ok`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run removed the last stale launch-proof snapshot inside the generated transcript so the outbound proof pack no longer contradicts its own final status.

## 2026-06-01 - Standalone Public Verify Gate

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the outbound operator packet and receive-side return-packet verifier already existed, but another chat still had no single shipped command that said whether the clean-shell logs plus result receipt were valid before starting the screenshot pass.
- Added `zmem verify-public-verify --summary-only` in [`zerker_memory/cli.py`](zerker_memory/cli.py). It verifies the clean-shell log contract, validates the machine-readable receipt, checks the packaged-install requirement, and prints the exact checklist/handoff/result paths from one command.
- Threaded that verifier through the generated Phase-1 operator contract: `PUBLIC_VERIFY_HANDOFF.md`, `PUBLIC_VERIFY_CHECKLIST.md`, `PUBLIC_VERIFY_COMMANDS.sh`, `FINALIZE_RETURN_PACKET.sh`, status/prelaunch/release next-step guidance, and the durable repo runbook now all tell the operator to validate the clean-shell proof before moving to launch-asset capture.
- Updated focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and refreshed launch-facing docs in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md).

Verification:

- `python3 -m unittest tests.test_release_smoke -q` -> 39 tests OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 98 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; `Launch proof: ok`, `Handoff: ok`, `Operator packet: ok (14/14 files packed)`, strict publish still blocked only on `public_verify_evidence` and `launch_assets`
- `python3 -m zerker_memory verify-public-verify --summary-only` -> expected non-zero; new summary reports `0/5` logs captured, points at the receipt/checklist/handoff paths, and keeps the packaged-install requirement explicit
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 summary now exercises `verify-public-verify` between operator-packet and launch-asset checks

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the clean-shell proof validation itself a first-class shipped step so that sidecar can fail fast before recording collateral.

## 2026-06-01 - Console Release Surface Hardening

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local slice was to make the `zmem ui` release surface as explicit as the CLI handoff contract while fixing the live launch-proof/release-pack regressions uncovered during verification.
- Expanded [`zerker_memory/dashboard.py`](zerker_memory/dashboard.py) and release-readiness state in [`zerker_memory/cli.py`](zerker_memory/cli.py) so the console now surfaces the operator packet, public-verify summary/runbook, return-packet archive, and the exact missing clean-shell logs and launch assets directly in the release views instead of forcing the operator to cross-reference multiple files.
- Fixed the live Phase-1 proof path in [`zerker_memory/cli.py`](zerker_memory/cli.py): `run_launch_proof()` now always threads the bundled runbook into the manifest contract, preserves the 14-file operator packet, and keeps the intended `ok with warnings (launch_assets, public_verify_evidence)` versus `blocked (launch_assets, public_verify_evidence)` gate snapshot even outside a full repo surface, so `release-pack --summary-only` and `scripts/release_smoke.py --summary-only` return to a truthful blocked state instead of crashing.
- Refreshed [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the user-facing console claims now match the shipped release panel behavior.

Verification:

- `python3 -m py_compile zerker_memory/cli.py zerker_memory/dashboard.py tests/test_cli_onboarding.py tests/test_release_smoke.py tests/test_dashboard.py` -> OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding tests.test_dashboard -q` -> 150 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now stays stable, reports `Operator packet: ok (14/14 files packed)`, surfaces `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and still shows the expected external blockers `0/5` public-verify logs and `0/8` launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand `.zerker/launch-proof/public-verify-operator-packet.tar.gz` plus the bundled `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` to the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the console and proof-path state consistent enough that another chat can operate from one release surface without reconstructing the remaining blocker set.

## 2026-06-01 - Operator Packet Open-First Runbook

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local improvement was making the outbound proof packet unmistakably self-starting for the next clean-shell operator instead of leaving the runbook as a bundled file with no explicit first-step surface.
- Surfaced the packet-local clean-shell runbook directly in the shipped release summaries: [`zerker_memory/cli.py`](zerker_memory/cli.py) now prints `Public verify runbook` in `zmem launch-proof --summary-only` and `zmem release-pack --summary-only`, and `zmem verify-operator-packet --summary-only` now prints `Open first: CLEAN_SHELL_PUBLIC_VERIFY.md` before the rest of the contract details.
- Tightened the release-smoke contract in [`scripts/release_smoke.py`](scripts/release_smoke.py) so the operator-packet preflight now requires that open-first runbook path, aligned focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and refreshed launch-facing docs in [`README.md`](README.md) and [`QUICKSTART.md`](QUICKSTART.md) to mention the packet-local runbook copy.

Verification:

- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_release_smoke.py tests/test_cli_onboarding.py` -> OK
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 137 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch packet and now reports `Public verify runbook: .zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` plus `Operator packet: ok (14/14 files packed)`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now surfaces `Open first: CLEAN_SHELL_PUBLIC_VERIFY.md` in the operator packet summary while the real blockers remain the expected `0/5` public-verify logs and `0/8` launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; have them open `CLEAN_SHELL_PUBLIC_VERIFY.md` first from the unpacked bundle, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the shipped operator bundle tell the next chat exactly which file to open first.

## 2026-06-01 - Release Pack Packet Consistency Repair

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the highest-leverage local blocker had shifted from docs drift to a shipped regression, because `zmem release-pack --summary-only` was crashing and the outbound operator packet could no longer be trusted to mirror the refreshed launch state.
- Fixed [`zerker_memory/cli.py`](zerker_memory/cli.py) so `run_launch_proof()` now writes the clean-shell runbook into `.zerker/launch-proof/`, threads that path through the manifest/result contract, and `run_release_pack()` rewrites the launch manifest plus both packet archives after it refreshes the handoff-aware Phase-1 surfaces.
- Tightened focused onboarding coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the restored release-pack path now asserts the runbook contract, the refreshed gate snapshot, the rebuilt 14-file operator packet, and the correct launch-proof-vs-release-pack expectations for isolated proof generation.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 98 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 39 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; now regenerates launch proof, handoff, `CLEAN_SHELL_PUBLIC_VERIFY.md`, and a ready `14/14` operator packet before stopping on the expected `launch_assets` plus `public_verify_evidence` blockers
- `python3 -m zerker_memory prelaunch --summary-only` -> expected non-zero; only `launch_assets` and `public_verify_evidence` remain as strict-publish blockers
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight now verifies the rebuilt operator packet with `Local alpha gate: ok with warnings (launch_assets, public_verify_evidence)` and still reports only the expected `0/5` public-verify logs and `0/8` launch assets as open work

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run restored the repo-local refresh command and made the outbound operator packet match the live Phase-1 gate snapshot again.

## 2026-06-01 - Operator Packet Snapshot Gate

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the clean-shell handoff archive was already structurally correct, but the last repo-local outbound check still hid the live gate snapshot and launch-asset storyboard, and `release-pack --summary-only` could briefly report stale packet state after regenerating the launch docs.
- Expanded [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-operator-packet --summary-only` now prints the current local-alpha versus strict-publish gate snapshot, the launch-assets directory, and the full eight-asset storyboard directly from `launch-proof.json`.
- Kept the post-refresh packet state truthful by rebuilding the operator and return archives after the final `release-pack` regeneration pass, then aligned focused verifier coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py) with the richer 14-file summary surface.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 98 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 39 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the pack and now reports `Operator packet: ok (14/14 files packed)` plus `Return packet: pending (archive ok at .zerker/launch-proof/public-verify-return-packet.tar.gz; pending public verify evidence, launch assets)`
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> passed; summary now shows `Local alpha gate: ok with warnings (launch_assets, public_verify_evidence)`, `Strict publish gate: blocked (launch_assets, public_verify_evidence)`, and the full eight expected launch assets
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; repo-local Phase-1 state is `Launch proof: ok`, `Operator packet: ok`, `Local alpha gate: ok with warnings (launch_assets, public_verify_evidence)`, `Strict publish gate: blocked (launch_assets, public_verify_evidence)`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local preflight still reports only the expected `0/5` public-verify logs and `0/8` launch assets as open blockers

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator: verify the outbound archive locally with `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the last local outbound packet check self-contained and kept the regenerated packet archives truthful after `release-pack`.

## 2026-06-01 - Launch Proof Transcript Snapshot Refresh

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, so the highest-leverage local work was tightening the proof packet itself; the generated launch-proof transcript could still carry a stale `Launch proof: missing` snapshot inside a freshly generated pack, which made the outbound Phase-1 evidence set internally contradictory.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `run_launch_proof()` still writes the transcript early enough for launch-proof readiness checks, then rewrites that transcript at the end with the post-pack status snapshot instead of leaving the stale pre-pack release view in the final artifact.
- Tightened focused onboarding coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the standalone launch-proof contract now asserts `Launch proof: ok` in the generated transcript and status summary and rejects the stale `Launch proof: missing` wording in those final proof-pack artifacts.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 137 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch pack and kept strict publish blocked only on `launch_assets` and `public_verify_evidence`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still reports `0/5` public-verify logs and `0/8` launch assets while refreshing the launch pack
- `rg -n "Launch proof: missing|Launch proof: ok" .zerker/launch-proof/terminal-transcript.txt` -> only `Launch proof: ok`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator; execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run removed the last stale launch-proof snapshot inside the generated transcript so the outbound proof pack no longer contradicts its own final status.


## 2026-06-01 - Installer Public Repo Alignment

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the launch docs and proof packet already pointed operators at `zerkerlabs/zerker-memory`, but the shipped `install.sh` bootstrap still defaulted to the old `zerker-memory/zerker-memory` clone URL, which would have broken the clean-shell alpha path before the external proof run even started.
- Updated [`install.sh`](install.sh) so clean-shell bootstrap now clones `https://github.com/zerkerlabs/zerker-memory.git` by default instead of the stale owner/repo path.
- Tightened the strict public-URL audit in [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem prelaunch --summary-only` now scans `install.sh` for placeholder or stale repo-owner drift, then aligned focused onboarding and release-smoke coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py) with the current 14-file operator packet plus runbook contract.
- Updated [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the remaining Phase-1 launch gap is now framed as live public publish proof plus launch collateral, not uncertainty about the target GitHub owner/repo.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 98 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 39 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory prelaunch --summary-only` -> expected non-zero; `public_urls: ok (no placeholders)` and remaining blockers stayed limited to `launch_assets` plus `public_verify_evidence`
- `python3 scripts/release_smoke.py --summary-only` -> passed; release summary now shows `Operator packet: ok (14/14 files packed)`, surfaces `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and still reports only the expected `0/5` public-verify logs and `0/8` launch assets as open Phase-1 gaps

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm the live installer now clones the `zerkerlabs/zerker-memory` repo, run `zmem verify-public-verify --summary-only`, capture the full eight-asset storyboard, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run removed a stale bootstrap URL and made the strict prelaunch gate catch that drift before another chat forwards the operator packet.

## 2026-06-01 - Launch Asset Gate-Truth Fix

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, but the shipped launch-asset storyboard still told the operator to capture `release-pack-summary.png` with prelaunch `ok` even though strict publish is intentionally blocked on `public_verify_evidence` and `launch_assets`.
- Fixed the generated launch-asset contract in [`zerker_memory/cli.py`](zerker_memory/cli.py) so the `release-pack-summary` shot now asks for the current strict-publish gate result instead of a false green prelaunch state.
- Added a focused onboarding regression assertion in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), then regenerated the repo-local proof pack so `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, `.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md`, and `.zerker/launch-proof/launch-proof.json` now match the real Phase-1 gate.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 97 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 38 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; regenerated the launch-proof pack and kept strict publish blocked only on `public_verify_evidence` and `launch_assets`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still reports `0/5` public-verify logs and `0/8` launch assets
- `rg -n 'strict publish gate result' .zerker/launch-proof/CAPTURE_CHECKLIST.md .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md .zerker/launch-proof/launch-proof.json` -> passed; regenerated proof surfaces now carry the corrected capture wording

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then hand `docs/CLEAN_SHELL_PUBLIC_VERIFY.md` plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, capture the full eight-asset storyboard with the now-correct `release-pack-summary` instruction, run `zmem verify-launch-assets --summary-only`, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run removed a false-green instruction from the shipped asset contract so that sidecar can execute without improvising around a contradictory checklist.

## 2026-06-01 - Clean-Shell Public Verify Runbook

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: external access is still blocked here, but the repo still needed one durable Phase-1 send/receive checklist outside generated `.zerker/launch-proof/` state so another chat could brief the operator and accept the returned packet without re-reading the whole build log.
- Added [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md), a repo-stable runbook that captures the repo-local preflight, outbound operator packet contract, clean-shell execution steps, required logs, required launch assets, receive-side acceptance rules, and the exact external blocker.
- Linked that runbook from README, QUICKSTART, DAY1 setup, launch audit/checklist/plan, PRODUCT_STATUS, and landing proof copy so the current Phase-1 handoff loop has one non-generated source of truth before a fresh proof pack is regenerated.

Verification:

- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still reports the same external blockers: `0/5` public-verify logs and `0/8` launch assets.
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero; `Launch proof: ok`, `Handoff: ok`, outbound operator packet ready, strict publish still blocked on `public_verify_evidence` and `launch_assets`.
- `python3 -m zerker_memory prelaunch --summary-only` -> expected non-zero; only `launch_assets` and `public_verify_evidence` remain as blockers.
- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 135 tests OK
- `rg -n "CLEAN_SHELL_PUBLIC_VERIFY" README.md QUICKSTART.md docs/DAY1_AGENT_SETUP.md docs/PUBLIC_LAUNCH_AUDIT.md docs/GITHUB_RELEASE_CHECKLIST.md docs/LAUNCH_PLAN.md docs/PRODUCT_STATUS.md landing/index.html docs/CLEAN_SHELL_PUBLIC_VERIFY.md` -> passed; new runbook is wired into the launch-facing docs and landing proof copy.

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Run `python3 scripts/release_smoke.py --summary-only`, then use [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) plus `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to brief the clean-shell operator: execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, capture the full eight-asset storyboard, run `zmem verify-launch-assets --summary-only`, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made that handoff durable at the repo-doc level instead of requiring a regenerated packet or prior chat context.

## 2026-06-01 - Public Verify Summary Asset Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: `public-verify-summary.md` was already the cross-chat run-state artifact, but it still forced another chat to open the launch-asset checklist and finalize script separately before it could tell whether the packet was ready for handback.
- Expanded the generated `.zerker/launch-proof/public-verify-summary.md` so it now carries launch-asset progress, the capture-checklist path, the finalize-script path, the return-packet archive path, and an explicit expected-launch-assets section beside the existing clean-shell log summary.
- Refreshed `run_launch_proof()` so the first generated proof packet rewrites that summary again after the manifest exists, making the initial outbound handoff self-contained instead of waiting for a later `release-pack` refresh.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 135 tests OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_surfaces_public_verify_contract_in_readme_and_report -q` -> OK
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_verify_operator_packet_archive_reports_ready_packet -q` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> expected non-zero because strict publish is still blocked on `public_verify_evidence` and `launch_assets`; regenerated `.zerker/launch-proof/public-verify-summary.md`
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight still verifies status, release-pack, operator packet, launch assets, return packet, and strict `prelaunch`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Hand the refreshed `.zerker/launch-proof/public-verify-summary.md` and `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to the clean-shell operator, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the full eight-asset storyboard, run `zmem verify-launch-assets --summary-only`, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the single summary artifact self-contained enough to brief that operator without opening multiple markdown files.

## 2026-06-01 - Release Smoke Summary Preflight

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the launch contract already had strong CLI-level proof, but `scripts/release_smoke.py` still forced a full temp-install run and gave no fast repo-local preflight for the separate-chat operator loop.
- Added `python3 scripts/release_smoke.py --summary-only`, a no-reinstall Phase-1 preflight that runs the shipped repo-local `status`, `release-pack`, `verify-operator-packet`, `verify-launch-assets`, `verify-return-packet`, and strict `prelaunch` summaries in one terminal pass.
- Added focused helper coverage for the new summary path and refreshed README, QUICKSTART, DAY1 setup, and PRODUCT_STATUS so the user-facing release commands now distinguish between the repo-local preflight and the final packaged-install proof run.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 135 tests OK
- `python3 -m py_compile scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 scripts/release_smoke.py --summary-only` -> passed; prints the one-screen Phase-1 preflight, confirms `Required install mode: packaged` in the operator packet, reports `0/8` launch assets and `0/5` public-verify logs, and reruns strict `prelaunch` as blocked on those two gates
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Use `python3 scripts/release_smoke.py --summary-only` as the repo-local preflight before handing work to another chat, then forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the full eight-asset storyboard, run `zmem verify-launch-assets --summary-only`, finalize the return packet, and accept handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; the new summary-only smoke path is the repo-local preflight that should be run before that handoff.

## 2026-06-01 - Operator Packet Contract Summary

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the outbound operator packet was structurally verified, but the receiving chat still had to open the manifest or separate handoff docs to confirm the actual packaged-install contract before executing the external pass.
- Extended `zmem verify-operator-packet --summary-only` so the outbound packet check now prints the required `packaged` install mode, public-verify script path, expected clean-shell logs, result receipt path, compact run-summary path, finalize-script path, and return-packet archive path directly from the embedded manifest.
- Tightened the release-smoke summary guardrails and focused onboarding tests around that richer operator-packet output, and refreshed README, QUICKSTART, and Day-1 setup docs so the user-facing Phase-1 handoff flow matches the shipped verifier surface.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 133 tests OK
- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` -> passed; now prints `Required install mode: packaged`, the five expected log names, `Result receipt: public-verify-result.json`, `Run summary: public-verify-summary.md`, and the finalize/archive paths
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers`; fresh-workspace proof flow enforced the richer operator-packet summary while the expected packaged-install external blocker remained unchanged

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, use `zmem verify-operator-packet ... --summary-only` as the one-screen preflight, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the full eight-asset storyboard, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the outbound verifier itself self-describing enough for a separate chat to preflight the packet from one terminal command.

## 2026-05-31 - Public Verify Run Summary Artifact

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the outbound operator packet already carried the script, logs directory, and JSON receipt, but another chat still had to open multiple raw files to tell whether the clean-shell pass was pending, failed, or packaged-clean.
- Added generated `.zerker/launch-proof/public-verify-summary.md` output to the Phase-1 contract, taught `PUBLIC_VERIFY_COMMANDS.sh` to refresh it beside `public-verify-result.json`, and packed it into both the outbound operator archive and the returned packet so the clean-shell proof state is glanceable before and after handoff.
- Surfaced that summary path in `zmem status --summary-only`, `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, and `zmem verify-return-packet --summary-only`, tightened packet verification so both packet directions now require the summary artifact, and refreshed launch-facing docs/landing copy to keep the shipped operator contract aligned.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 133 tests OK
- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> correctly blocked strict publish locally on `public_verify_evidence` and `launch_assets`; now prints `Public verify summary: .zerker/launch-proof/public-verify-summary.md` and `Operator packet: ok (13/13 files packed)`
- `python3 -m zerker_memory prelaunch --summary-only` -> correctly blocked strict publish locally on `public_verify_evidence` and `launch_assets`
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers`; fresh-workspace proof path now creates and verifies the public-verify summary artifact end to end

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt/run summary remain pending under `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/public-verify-result.json`, and `.zerker/launch-proof/public-verify-summary.md`.

Next:

- Forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, inspect `public-verify-summary.md` plus `public-verify-result.json`, capture the full eight-asset storyboard, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run made the outbound and return packet self-summarizing for the next chat.

## 2026-05-31 - Launch Packet Gate Snapshot Surfacing

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the outbound launch packet already named the exact commands and files, but several generated handoff/checklist surfaces still ended with an `unknown` prelaunch state, which forced another chat or operator to infer whether the pack was locally launch-ready or still blocked.
- Threaded the actual release-gate snapshot into the generated Phase-1 proof packet: `CAPTURE_CHECKLIST.md`, `LAUNCH_ASSET_HANDOFF.md`, `PUBLIC_VERIFY_CHECKLIST.md`, and `PUBLIC_VERIFY_HANDOFF.md` now state the current local-alpha and strict-publish gate status directly instead of leaving the operator with a placeholder.
- Reused the shared gate-status formatter so those packet surfaces stay textually aligned with `zmem status --summary-only`, and tightened `scripts/release_smoke.py` to assert the new gate snapshot sections exist for both `zmem launch-proof` and `zmem release-pack --summary-only`.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 133 tests OK
- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> correctly blocked strict publish locally on `public_verify_evidence` and `launch_assets` while regenerating the launch packet
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; `Launch proof: ok`, `Local alpha gate: ok with warnings (launch_assets, public_verify_evidence)`, `Strict publish gate: blocked (launch_assets, public_verify_evidence)`
- `rg -n "gate snapshot|Current Gate Snapshot" .zerker/launch-proof/CAPTURE_CHECKLIST.md .zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md .zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md .zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md` -> confirmed the regenerated packet now carries the concrete gate snapshot lines
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers`; fresh-workspace launch-proof and release-pack paths both enforced the new gate-snapshot surface

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- Forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the full eight-asset storyboard, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run removed the last `unknown` gate-state ambiguity from the outbound proof packet.

## 2026-05-31 - Launch Proof Handoff Asset Count Alignment

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the shipped verifier and manifest already required eight return assets whenever handoff proof existed, but standalone `zmem launch-proof` and `bash scripts/launch_proof.sh` could still regenerate six-asset checklists/handoffs and hand an operator an incomplete storyboard.
- Hardened the generated launch-asset contract so the checklist and handoff surfaces now state the exact `zmem verify-launch-assets --summary-only` completion bar (`6/6` without handoff, `8/8` with handoff) instead of leaving that acceptance threshold implicit.
- Fixed `run_launch_proof()` to reuse the same handoff-aware asset plan as the manifest, verifier, release-pack, and release smoke when `.zerker/handoff/` already exists, so `CAPTURE_CHECKLIST.md`, `LAUNCH_ASSET_HANDOFF.md`, `PUBLIC_VERIFY_HANDOFF.md`, and the wrapped `scripts/launch_proof.sh` path no longer drift back to the six-asset proof-only storyboard after a handoff has already been packaged.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 133 tests OK
- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `bash scripts/launch_proof.sh` -> passed; regenerated `.zerker/launch-proof/CAPTURE_CHECKLIST.md` now includes `Required capture set: 8 assets total`, `handoff-restore-terminal`, and `ui-handoff-restore`
- `python3 -m zerker_memory release-pack --summary-only` -> correctly blocked strict publish locally on `public_verify_evidence` and `launch_assets`
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> correctly blocked at `0/8 captured` and listed all eight missing deliverables
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; release gate still focused on operator packet, clean-shell proof, launch assets, and return packet
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers`; fresh-workspace launch-proof/release-pack path stayed aligned on the eight-asset return contract

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- Forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` from a clean networked shell, capture the full eight-asset storyboard now named in `CAPTURE_CHECKLIST.md`, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture; this run removed the local contract split that could have caused another chat to return an incomplete packet.

## 2026-05-31 - Public Verify Attempt Receipt

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo could already generate the public-verify operator packet, but separate chats still could not tell from shipped surfaces whether the clean-shell proof was merely pending or had already failed on packaged-install verification without reading raw logs.
- Extended the generated `.zerker/launch-proof/public-verify-result.json` receipt so it now records `status`, `next_step`, timestamps, the required install mode, and the observed `scripts/release_smoke.py` `install_mode` when the clean-shell script can detect it from the saved log.
- Threaded that richer receipt back into `public_verify_status()`, `verify-return-packet`, the generated `PUBLIC_VERIFY_COMMANDS.sh`, and launch-facing docs so `zmem release-pack --summary-only` and the receive-side proof path now surface `pending` vs `failed` plus packaged-install requirements directly in the shipped operator contract.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 132 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; repo root still correctly reports `launch_proof_artifacts`, `launch_assets`, and `public_verify_evidence` as blockers before release-pack refresh
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally and now reports `last receipt: pending clean-shell public verify run; required install_mode packaged`
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers`; generated launch-proof/return-packet summaries now surface the richer pending receipt details

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then from a clean networked shell run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm the resulting receipt records a non-wrapper install mode, capture the required launch assets under `.zerker/launch-proof/assets/`, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; this run sharpened the shipped receipt contract so that external operator handback is easier to assess from another chat.

## 2026-05-31 - Status Launch-Gate Focus

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the shipped repo-local proof pack already had the right Phase-1 contract, but `zmem status --summary-only` could still dilute the next-step list with generic UI and agent smoke prompts after launch-proof and handoff were already present.
- Tightened `build_status_next_steps()` so repo-local status output stays focused on the active Phase-1 launch gate whenever release blockers remain: outbound operator-packet verification, the clean-shell proof script, launch-asset verification, and return-packet handback now take precedence over generic `zmem ui` and agent smoke guidance.
- Added focused onboarding coverage for both sides of the behavior, repaired one stale public-verify wording assertion, and updated README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, CURRENT_STATE, and automation memory so the documented `status --summary-only` contract matches the shipped CLI behavior.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 130 tests OK
- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only` -> passed and now lists only the Phase-1 launch-gate steps: `verify-operator-packet`, `PUBLIC_VERIFY_COMMANDS.sh`, launch-asset verification, and return-packet handback
- `python3 -m zerker_memory prelaunch --summary-only` -> correctly failed strict publish with `launch_assets: blocker` and `public_verify_evidence: blocker` while keeping the same focused next steps

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the outbound packet, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, capture the required assets into `.zerker/launch-proof/assets/`, run `zmem verify-launch-assets --summary-only`, then rebuild and hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the local improvement here is that the one-screen status surface now stays on that exact launch gate instead of suggesting unrelated next actions.

## 2026-05-31 - Console Launch Asset Verification

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the CLI already had `zmem verify-launch-assets`, but the operator console still could not run or summarize that check even though launch assets are now a strict publish blocker.
- Added a `Verify Launch Assets` action to `zmem ui`, a matching dashboard API route, and a Proof Inspector launch-asset summary so the console can now validate the screenshot/GIF storyboard from the same surface that already runs release-pack, handoff restore, and return-packet verification.
- Updated focused dashboard coverage plus README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, CURRENT_STATE, and landing copy so the Phase-1 operator contract now exposes both remaining evidence checks inside the local console.

Verification:

- `python3 -m unittest tests.test_dashboard -q` -> 13 tests OK
- `python3 -m py_compile zerker_memory/dashboard.py tests/test_dashboard.py` -> OK
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> correctly failed with `Assets: failed (0/8 captured)` and listed the missing asset paths
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only` -> passed and still reports `Strict publish gate: blocked (launch_assets, public_verify_evidence)`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the required assets under `.zerker/launch-proof/assets/`, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, then accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the local improvement now is that `zmem ui` can validate the launch-asset set before the return packet is finalized or accepted.

## 2026-05-31 - Release Smoke Operator Packet Gate

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the outbound operator packet had become part of the shipped Phase-1 contract, but `scripts/release_smoke.py` still only exercised the receive-side return-packet check and could miss a regression in `zmem verify-operator-packet`.
- Tightened `scripts/release_smoke.py` so the fresh-workspace launch path now runs `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` after generating launch proof, before the existing launch-assets and return-packet checks.
- Added focused release-smoke helper coverage for the operator-packet summary surface and refreshed launch-facing docs/state so the shipped Phase-1 smoke contract now proves both packet directions before external handoff.

Verification:

- `python3 -m unittest tests.test_release_smoke -q` -> 36 tests OK
- `python3 -m py_compile scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while now exercising `verify-operator-packet`, `verify-launch-assets`, `verify-return-packet`, `release-pack`, and strict `prelaunch`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the operator packet or handoff brief, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the required assets under `.zerker/launch-proof/assets/`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, then accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the shipped smoke path proves the outbound bundle before another operator receives it.

## 2026-05-31 - Launch Asset Contract Verifier

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the repo could already verify the outbound operator packet and the final returned packet, but the in-between screenshot/GIF storyboard still depended on prose checklists instead of one narrow contract check before packet finalization.
- Added `zmem verify-launch-assets [--summary-only]`, which verifies `.zerker/launch-proof/assets/` against the embedded `launch-proof.json` storyboard and reports the exact missing launch screenshots/GIFs before handback.
- Threaded that verifier through the shipped Phase-1 operator loop: `PUBLIC_VERIFY_COMMANDS.sh`, `FINALIZE_RETURN_PACKET.sh`, `CAPTURE_CHECKLIST.md`, `LAUNCH_ASSET_HANDOFF.md`, `PUBLIC_VERIFY_HANDOFF.md`, `PUBLIC_VERIFY_CHECKLIST.md`, the status next-step guidance, `scripts/release_smoke.py`, focused tests, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy now all tell the operator to run `zmem verify-launch-assets --summary-only` after asset capture and before rebuilding the return packet.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 128 tests OK
- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while exercising the new `verify-launch-assets` command and the updated finalize/handoff contract end to end
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; strict publish still reports only `launch_assets` and `public_verify_evidence` as blockers
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> correctly failed with `0/8 captured`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the required assets under `.zerker/launch-proof/assets/`, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and only then accept the handback with `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the asset pass has the same contract-level verification as the outbound and return packet steps.

## 2026-05-31 - Release Smoke Operator Packet Gate

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the outbound operator packet had become part of the shipped Phase-1 contract, but `scripts/release_smoke.py` still only exercised the receive-side return-packet check and could miss a regression in `zmem verify-operator-packet`.
- Tightened `scripts/release_smoke.py` so the fresh-workspace launch path now runs `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` after generating launch proof, before the existing launch-assets and return-packet checks.
- Added focused release-smoke helper coverage for the operator-packet summary surface and refreshed launch-facing docs/state so the shipped Phase-1 smoke contract now proves both packet directions before external handoff.

Verification:

- `python3 -m unittest tests.test_release_smoke -q` -> 36 tests OK
- `python3 -m py_compile scripts/release_smoke.py tests/test_release_smoke.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while now exercising `verify-operator-packet`, `verify-launch-assets`, `verify-return-packet`, `release-pack`, and strict `prelaunch`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward the operator packet or handoff brief, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the required assets under `.zerker/launch-proof/assets/`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, then accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the shipped smoke path proves the outbound bundle before another operator receives it.

## 2026-05-31 - Public Verify Status Contract Repair

## 2026-05-31 - Public Verify Attempt Receipt

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was the right next move now: the repo could already generate the public-verify operator packet, but separate chats still could not tell from shipped surfaces whether the clean-shell proof was merely pending or had already failed on packaged-install verification without reading raw logs.
- Extended the generated `.zerker/launch-proof/public-verify-result.json` receipt so it now records `status`, `next_step`, timestamps, the required install mode, and the observed `scripts/release_smoke.py` `install_mode` when the clean-shell script can detect it from the saved log.
- Threaded that richer receipt back into `public_verify_status()`, `verify-return-packet`, the generated `PUBLIC_VERIFY_COMMANDS.sh`, and launch-facing docs so `zmem release-pack --summary-only` and the receive-side proof path now surface `pending` vs `failed` plus packaged-install requirements directly in the shipped operator contract.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 132 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; repo root still correctly reports `launch_proof_artifacts`, `launch_assets`, and `public_verify_evidence` as blockers before release-pack refresh
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally and now reports `last receipt: pending clean-shell public verify run; required install_mode packaged`
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers`; generated launch-proof/return-packet summaries now surface the richer pending receipt details

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- Run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then from a clean networked shell run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm the resulting receipt records a non-wrapper install mode, capture the required launch assets under `.zerker/launch-proof/assets/`, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; this run sharpened the shipped receipt contract so that external operator handback is easier to assess from another chat.

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the shipped Phase-1 release path had a repo-local regression: `python3 -m unittest discover -q` was failing on the public-verify readiness wording, which weakened the launch contract even though the external blocker was unchanged.
- Tightened `public_verify_status()` so a passing `public-verify-result.json` always keeps the stable `result ok` marker in the status details while still appending the richer receipt summary when present.
- Kept the rest of the Phase-1 operator flow unchanged: release-pack, prelaunch, launch-asset verification, outbound packet verification, and return-packet handling all still point at the same external proof path and strict publish blockers.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 94 tests OK
- `python3 -m py_compile zerker_memory/cli.py` -> OK
- `python3 -m unittest discover -q` -> 222 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; strict publish still blocked only on `launch_assets` and `public_verify_evidence`
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally while preserving the same Phase-1 next steps
- `python3 -m zerker_memory prelaunch --summary-only` -> correctly failed strict publish locally on `launch_assets` and `public_verify_evidence`
- `python3 -m zerker_memory verify-launch-assets --summary-only` -> correctly failed with `0/8 captured`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the required assets under `.zerker/launch-proof/assets/`, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and only then accept the handback with `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; this run kept the local Phase-1 contract green so that external proof is the only meaningful next move.

## 2026-05-31 - Release Guidance Operator Preflight

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the shipped operator commands already existed, but the one-screen release guidance still skipped the outbound `verify-operator-packet` preflight and `zmem status --summary-only` could repeat the launch-asset instruction while strict publish was blocked.
- Tightened `prelaunch_next_steps()` and `build_status_next_steps()` so the Phase-1 critical path now starts with `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then points at `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, then points at `.zerker/launch-proof/CAPTURE_CHECKLIST.md` plus `zmem verify-launch-assets --summary-only`, before the return-packet handback step.
- Deduplicated overlapping strict-publish/status guidance so `zmem status --summary-only`, `zmem prelaunch --summary-only`, and `zmem release-pack --summary-only` now present the same clean operator sequence instead of mixing old asset-only wording with the newer Phase-1 verification contract.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 93 tests OK
- `python3 -m py_compile zerker_memory/cli.py tests/test_cli_onboarding.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed and now shows `Operator packet: ok` plus the ordered `verify-operator-packet` -> `PUBLIC_VERIFY_COMMANDS.sh` -> `verify-launch-assets` -> return-packet sequence without duplicate asset guidance
- `python3 -m zerker_memory prelaunch --summary-only --allow-placeholders` -> passed with warnings and now starts `Next:` with `verify-operator-packet` before the clean-shell script and asset verification
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally while showing the same ordered Phase-1 next steps
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while preserving the updated release/prelaunch guidance contract

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` or `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, capture the required assets under `.zerker/launch-proof/assets/`, run `zmem verify-launch-assets --summary-only`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, then accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that every shipped operator summary tells the same ordered preflight-to-handback sequence before another chat takes over.

## 2026-05-31 - Strict Launch Asset Publish Gate

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the shipped Phase-1 roadmap already requires the screenshot/GIF pass, but strict `zmem prelaunch` still treated empty `.zerker/launch-proof/assets/` as a warning instead of a real publish blocker.
- Tightened `run_prelaunch_check` so missing launch assets are now a blocker for strict publish while staying a warning for `--allow-placeholders` local-alpha runs, which makes the CLI and dashboard release gate match the actual Phase-1 launch contract.
- Updated focused onboarding coverage, `scripts/release_smoke.py`, README, QUICKSTART, PRODUCT_STATUS, CURRENT_STATE, and landing copy so all shipped operator surfaces now say the same thing: Phase 1 is not publish-ready until both the clean-shell evidence set and the final launch screenshots/GIFs exist.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 125 tests OK
- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory prelaunch --summary-only` -> correctly failed strict publish with both `launch_assets: blocker` and `public_verify_evidence: blocker`
- `python3 -m zerker_memory status --summary-only` -> passed and now reports `Strict publish gate: blocked (launch_assets, public_verify_evidence)`
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while preserving the stricter prelaunch contract

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the required assets under `.zerker/launch-proof/assets/`, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, then accept the handback only after `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that the shipped strict gate no longer understates the missing launch-asset work.

## 2026-05-31 - Outbound Operator Packet Verification

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the repo could already verify the returned packet, but it still had no symmetric check for the outbound clean-shell bundle before another chat or operator received it.
- Added `zmem verify-operator-packet [archive] [--summary-only]`, which verifies `.zerker/launch-proof/public-verify-operator-packet.tar.gz` against the embedded `launch-proof.json` contract and required outbound artifacts before handoff.
- Surfaced `Operator packet: ok|pending` in `zmem status --summary-only`, `zmem launch-proof --summary-only`, and `zmem release-pack --summary-only`, updated `scripts/release_smoke.py` to enforce that human-readable line, and refreshed README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, CURRENT_STATE, and landing copy so the Phase-1 operator loop now has a local preflight check on both the send and receive sides.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 125 tests OK
- `python3 -m py_compile zerker_memory/cli.py scripts/release_smoke.py tests/test_cli_onboarding.py tests/test_release_smoke.py` -> OK

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- Before forwarding `.zerker/launch-proof/public-verify-operator-packet.tar.gz` to another chat or operator, run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, then continue the existing clean-shell proof path: run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the required assets, run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, and only accept handback after `zmem verify-return-packet ... --summary-only` reports `Ready: yes`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the orchestrator can verify the outbound bundle before sending it and the returned bundle before accepting it.

## 2026-05-31 - Return Packet Finalize Script

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the repo already had the outbound operator packet, the asset handoff, and the receive-side verifier, but the clean-shell operator still had no single last-step command to rebuild and self-check the return packet after screenshots were saved.
- Added generated `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, a narrow clean-shell finalize step that repacks `launch-proof.json`, `public-verify-logs/`, `public-verify-result.json`, and `assets/`, then runs `zmem verify-return-packet ... --summary-only` locally before handback.
- Surfaced that finalize script in `launch-proof.json`, `PUBLIC_VERIFY_CHECKLIST.md`, `PUBLIC_VERIFY_HANDOFF.md`, `PUBLIC_VERIFY_COMMANDS.sh`, the launch-proof README/report, `zmem status --summary-only`, `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, the dashboard release surfaces, `scripts/release_smoke.py`, focused tests, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so the external operator loop now ends with an explicit rebuild-and-verify handback step instead of a manual archive assumption.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_dashboard tests.test_cli_onboarding -q` -> 135 tests OK
- `python3 -m py_compile zerker_memory/cli.py zerker_memory/dashboard.py scripts/release_smoke.py` -> OK
- `python3 -m unittest discover -q` -> 214 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while verifying the new finalize-script contract through launch-proof, release-pack, first-run, and release smoke

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` or `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, save the required assets under `.zerker/launch-proof/assets/`, then run `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` and only hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` once it reports `Ready: yes`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the clean-shell operator has an explicit local finalize/self-check step before returning the packet.

## 2026-05-31 - Receive-Side Return Packet Handoff

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. This slice was the right next move because the repo already had the outbound clean-shell packet and the receive-side verifier, but the receiving/orchestrator chat still had to reconstruct the exact acceptance contract by hand before trusting a returned packet.
- Added generated `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md`, a copy-ready receive-side brief that tells the orchestrator exactly when to run `zmem verify-return-packet`, which roots and filenames must be present, and which acceptance rules must hold before Phase 1 can be marked complete.
- Surfaced that new receive-side handoff in `zmem status --summary-only`, `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, `launch-proof.json`, the launch-proof report, the dashboard release surfaces, `scripts/release_smoke.py`, focused tests, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy, and added it to `.zerker/launch-proof/public-verify-operator-packet.tar.gz` so the outbound clean-shell bundle now covers both the send-side and receive-side operator loop.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_dashboard -q` -> 101 tests OK
- `python3 -m py_compile zerker_memory/cli.py zerker_memory/dashboard.py` -> OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while verifying the new receive-side handoff path through launch-proof and release-pack
- `python3 -m zerker_memory launch-proof --summary-only` -> passed and now prints `Receive-side handoff: .zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md`
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally while reporting the expected Phase-1 blockers and the new receive-side handoff path
- `python3 -m zerker_memory status --summary-only --skip-eval` -> reports `Receive-side handoff: .zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md` alongside the existing public-verify and return-packet paths

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` or `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the checklist assets into `.zerker/launch-proof/assets/`, then hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` and use `.zerker/launch-proof/RECEIVE_VERIFY_HANDOFF.md` plus `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` before accepting the packet.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the orchestrator chat has a generated receive-side brief instead of reconstructing the acceptance contract from status output and scattered docs.

## 2026-05-31 - Public Verify Operator Packet

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell, with the screenshot/GIF asset pass still pending beside it. This slice was the right next move because the generated clean-shell and asset handoff docs were already self-contained, but a separate operator still had to gather several generated files manually before starting the external pass.
- Added generated `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, a single outbound bundle containing the manifest, proof README/report, capture checklist, both handoff briefs, the public-verify checklist/script, the placeholder result receipt, and the return-packet archive so another clean-shell chat can be briefed with one file.
- Surfaced that outbound packet in `zmem status --summary-only`, `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, `launch-proof.json`, release smoke, focused tests, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, CURRENT_STATE, BUILD_LOG, and landing copy so the remaining external Phase-1 pass now has both a one-file forward packet and a one-file return packet.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke tests.test_dashboard -q` -> 135 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while verifying the new outbound operator packet across launch-proof and release-pack
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally while reporting the expected Phase-1 blockers and the new `Operator packet archive: .zerker/launch-proof/public-verify-operator-packet.tar.gz`
- `python3 -m zerker_memory status --summary-only --skip-eval` -> reports `Launch proof: ok`, `Public verify: pending`, `Launch assets: pending`, `Return packet: pending`, and now includes `Operator packet archive: .zerker/launch-proof/public-verify-operator-packet.tar.gz`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, forward `.zerker/launch-proof/public-verify-operator-packet.tar.gz` or `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then use `.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md` and `.zerker/launch-proof/CAPTURE_CHECKLIST.md` to capture the required screenshots/GIFs into `.zerker/launch-proof/assets/` before handing back `.zerker/launch-proof/public-verify-return-packet.tar.gz`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the external operator can be briefed with one outbound tarball instead of a file list.

## 2026-05-31 - Self-Contained Launch Asset Handoff

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell, with the screenshot/GIF asset pass still pending beside it. This slice was the right next move because the clean-shell operator already had `PUBLIC_VERIFY_HANDOFF.md`, but the launch-asset capture pass still lacked its own single generated brief even though Phase 1 cannot close without those saved files.
- Added generated `.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md`, a copy-ready operator brief that names the exact launch-asset storyboard, save paths, success criteria, and return contract for the screenshot/GIF pass.
- Surfaced that new handoff artifact in `zmem status --summary-only`, `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, `launch-proof.json`, the proof report/dashboard, release smoke, focused tests, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so the remaining screenshot/GIF work is now as self-contained as the clean-shell public-verify work.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 89 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while verifying the new launch-asset handoff artifact across launch-proof and release-pack
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally while reporting the expected Phase-1 blockers: missing clean-shell public-verify logs and missing launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, forward `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then use `.zerker/launch-proof/LAUNCH_ASSET_HANDOFF.md` and `.zerker/launch-proof/CAPTURE_CHECKLIST.md` to capture the required screenshots/GIFs into `.zerker/launch-proof/assets/` before handing back `.zerker/launch-proof/public-verify-return-packet.tar.gz`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the asset-capture operator gets a separate generated brief instead of reconstructing the shot list from the checklist and report.

## 2026-05-31 - Self-Contained Public Verify Handoff

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell. This slice was the right next move because the repo already generated `PUBLIC_VERIFY_HANDOFF.md`, but that brief still made a separate clean-shell operator cross-reference other artifacts to know the exact evidence set they had to return.
- Expanded generated `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md` so it now embeds Phase-1 success criteria directly: the exact five expected clean-shell log filenames, the required launch asset deliverables, and the exact return-packet roots plus one-file tarball shortcut.
- Updated focused CLI coverage plus README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so the shipped claim matches the new handoff contract: the external operator brief is now self-sufficient instead of only pointing at the other generated files.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 89 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while exercising the broadened handoff artifact contract end to end
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally while still reporting the expected Phase-1 blockers: missing clean-shell public-verify logs and missing launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, forward `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the checklist assets into `.zerker/launch-proof/assets/`, then hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` and verify it with `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` or the matching `zmem ui` return-packet action.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the forwarded operator brief already names the exact logs, assets, and packet roots that must come back.

## 2026-05-31 - Console Return Packet Verification

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell. This slice was the right next move because the repo already had a receive-side `zmem verify-return-packet ...` CLI check, but the same receive-side proof path was still missing from `zmem ui`, even though Phase 1 already depends on the console for release-pack and handoff-restore launch capture.
- Added a dedicated `Verify Return Packet` action to `zmem ui`, backed by a new dashboard API/helper that verifies `.zerker/launch-proof/public-verify-return-packet.tar.gz` against the shipped launch-proof contract and renders the receive-side status, missing paths, failed steps, and counts directly in the Proof Inspector.
- Updated focused dashboard coverage plus README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so the shipped console contract now includes the receive-side return-packet verification step alongside release-pack, launch-proof, handoff, and handoff-restore.

Verification:

- `python3 -m unittest tests.test_dashboard -q` -> 12 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally while still reporting the expected Phase-1 blockers: missing clean-shell public-verify logs and missing launch assets
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; release block now remains locally consistent with `Launch proof: ok`, `Public verify: pending`, `Launch assets: pending`, and `Strict publish gate: blocked (public_verify_evidence)`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, forward `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the checklist assets into `.zerker/launch-proof/assets/`, then hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` and verify it from either `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` or the new `zmem ui` return-packet action.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the receiving operator can validate the returned proof packet from the same console surface already used for release-pack and handoff restore.

## 2026-05-31 - Public Verify Operator Handoff Artifact

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell. This slice was the right next move because external launch proof is still blocked here, but the repo still made a separate clean-shell chat stitch together the operator brief from status output, the checklist, and the script instead of handing them one copy-ready document.
- Added generated `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, a single operator-facing Phase-1 artifact that states the phase, the external blocker, the exact clean-shell script/checklist/report inputs, the required evidence capture, the return-packet handback, and the receive-side `zmem verify-return-packet ... --summary-only` command.
- Surfaced that handoff artifact in `zmem status --summary-only`, `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, the launch-proof manifest/report, release smoke, focused tests, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so separate chats now have one stable file to forward instead of reconstructing the clean-shell contract by hand.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke tests.test_dashboard -q` -> 134 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while verifying the new `PUBLIC_VERIFY_HANDOFF.md` artifact across launch-proof and release-pack

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, forward `.zerker/launch-proof/PUBLIC_VERIFY_HANDOFF.md`, run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the checklist assets into `.zerker/launch-proof/assets/`, then hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` and verify it with `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the orchestrator can hand another chat one generated markdown brief instead of reconstructing the proof contract from multiple surfaces.

## 2026-05-31 - Return Packet Receive-Side Verification

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the repo already told an external operator which tarball to hand back, but the receiving/orchestrator side still had no direct way to verify that returned packet without unpacking it by hand.
- Added `zmem verify-return-packet [archive] [--summary-only]`, a narrow receive-side Phase-1 command that validates the returned public-verify archive against the embedded `launch-proof.json` contract, required roots, expected clean-shell logs, machine-readable `public-verify-result.json`, and planned launch assets before another chat accepts the handoff.
- Updated `scripts/release_smoke.py`, focused CLI coverage, the generated proof-pack README/report/checklist copy, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so the shipped Phase-1 operator contract now includes the receive-side verification command alongside the return-packet archive.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 123 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while exercising the new `verify-return-packet --summary-only` blocked-state contract end to end

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt remain pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the checklist assets into `.zerker/launch-proof/assets/`, then hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` and verify it with `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the orchestrator chat has a single receive-side command to validate the returned proof packet before marking Phase 1 complete.

## 2026-05-30 - Status Proof Pack Handoff Surface

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the proof pack already had the script, checklist, result receipt, and return-packet archive, but the main one-screen status surface still made the external operator reconstruct those paths from other commands.
- Extended `zmem status --summary-only` so the repo release block now prints the exact capture checklist, public-verify checklist, public-verify script, public-verify logs dir, public-verify result receipt, and return-packet archive paths directly alongside the existing readiness lines.
- Tightened the status next-step contract so once launch-proof and handoff exist it now explicitly tells the operator to hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` or the equivalent four-path packet after the clean-shell pass; updated focused tests plus README, QUICKSTART, DAY1 setup, and PRODUCT_STATUS to match.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_dashboard -q` -> 98 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; release block now prints `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, `PUBLIC_VERIFY_CHECKLIST.md`, `PUBLIC_VERIFY_COMMANDS.sh`, `public-verify-result.json`, and `public-verify-return-packet.tar.gz`, and Next now includes the explicit return-packet handback step
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers` in the restricted environment while exercising the updated status/release-path contract end to end

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell public-verify logs/result receipt are still pending under `.zerker/launch-proof/public-verify-logs/` plus `.zerker/launch-proof/public-verify-result.json`.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the checklist assets into `.zerker/launch-proof/assets/`, then hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` or the equivalent four-path packet.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the default one-screen repo status tells a separate operator exactly which proof files to use and what to return.

## 2026-05-30 - Return Packet Readiness Validation

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the repo could generate a one-file public-verify return packet, but it still could not tell a separate chat whether that tarball was merely present or actually ready to hand back.
- Added return-packet archive validation to the existing release surfaces: `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, and `zmem status --summary-only` now report whether `.zerker/launch-proof/public-verify-return-packet.tar.gz` is pending, stale, invalid, or ready based on the manifest contract, clean-shell logs/result receipt, and expected launch assets.
- Tightened focused smoke and CLI coverage so the archive must contain the expected roots and, once evidence exists, the expected logs and asset outputs too; updated README, QUICKSTART, day-1 setup, product status, and landing copy to describe the new return-packet readiness signal.

Verification:

- `/Users/zzo/.pyenv/versions/3.10.15/bin/python -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 120 tests OK
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python -m unittest tests.test_dashboard` -> 11 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python -m zerker_memory launch-proof --summary-only` -> passed; now prints `Return packet: pending (archive ok at .zerker/launch-proof/public-verify-return-packet.tar.gz; pending public verify evidence, launch assets)`
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally and now prints the same return-packet readiness line alongside the script, logs dir, and result receipt
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed; verified the new return-packet readiness line through the full release-smoke path with `install_mode: editable`
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py --require-install-mode packaged` -> passed serially with `install_mode: editable`, confirming the packaged requirement still holds after the return-packet validation change

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, so the new return-packet validator correctly leaves the archive in `pending` state until an external operator completes the clean-shell proof and captures the launch assets.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, capture the checklist assets into `.zerker/launch-proof/assets/`, then hand back the now-validated `.zerker/launch-proof/public-verify-return-packet.tar.gz` archive or the equivalent four-path packet.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that the receiving chat can tell immediately whether the returned tarball is complete enough to trust.

## 2026-05-30 - Public Verify Return Packet Archive

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the proof pack already defined the exact return packet, but the clean-shell operator still had to hand back four separate paths manually and the placeholder bundle was not stable before that pass.
- Added a first-class `.zerker/launch-proof/public-verify-return-packet.tar.gz` contract to the launch-proof manifest, summary-only CLI surfaces, generated README/report/checklist copy, and launch-facing docs so the clean-shell operator now has a one-file handoff option in addition to the explicit four-path packet.
- Taught `PUBLIC_VERIFY_COMMANDS.sh` to refresh that archive automatically on exit, and fixed `zmem launch-proof` to create the empty `public-verify-logs/` directory up front so the placeholder tarball already contains `launch-proof.json`, `public-verify-logs/`, `public-verify-result.json`, and `assets/` before the external run starts.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 119 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory launch-proof --summary-only` -> passed; summary now prints `Return packet archive: .zerker/launch-proof/public-verify-return-packet.tar.gz`
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally and now surfaces the same archive path alongside the script, logs dir, and result receipt
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment while verifying the new archive contract across launch-proof and release-pack
- `python3 scripts/release_smoke.py --require-install-mode packaged` -> correctly failed in this restricted environment because editable install could not fetch `setuptools>=64` and could not run `bdist_wheel`, so the smoke fell back to `local-wrappers`
- `python3 - <<'PY' ... tarfile.open('.zerker/launch-proof/public-verify-return-packet.tar.gz') ...` -> archive contents verified as `launch-proof.json`, `public-verify-logs`, `public-verify-result.json`, and `assets`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the real clean-shell return packet or archive remains pending until an external operator runs `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then hand back either the exact packet named in `.zerker/launch-proof/launch-proof.json` or the generated `.zerker/launch-proof/public-verify-return-packet.tar.gz` archive after the screenshots/GIFs land under `.zerker/launch-proof/assets/`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the improvement now is that the operator can return one tarball instead of manually collecting four separate paths.

## 2026-05-30 - Public Verify Return Packet Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the generated proof pack already told an external operator what to run, but it still did not clearly say which files had to come back to the orchestrator after that clean-shell pass.
- Extended the generated launch-proof manifest with a machine-readable `return_packet` contract that names the exact hand-back set: `launch-proof.json`, `public-verify-logs/`, `public-verify-result.json`, and `assets/`.
- Rewrote the generated public-verify checklist, proof README, and HTML report so the clean-shell operator now sees an explicit `Return Packet` section alongside the command sequence and expected logs, rather than inferring the hand-back set from scattered prose.
- Updated focused smoke coverage plus launch-facing docs/landing copy so this external handoff contract fails tests if it disappears from the generated proof surfaces.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 119 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment while verifying the new return-packet manifest/checklist/report contract
- `python3 -m zerker_memory launch-proof --summary-only` -> passed; regenerated `.zerker/launch-proof/` after the proof-pack contract change
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally and refreshed the updated checklist/report surfaces with the new return-packet contract

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the clean-shell return packet remains pending until an external operator actually runs `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then hand back the exact return packet named in `.zerker/launch-proof/launch-proof.json`: the updated manifest, `public-verify-logs/`, `public-verify-result.json`, and `assets/`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that the generated proof pack states exactly which four paths must be returned to the orchestrator after that pass.

## 2026-05-30 - Public Verify Result Receipt

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the repo already tracked the five clean-shell logs, but it still lacked one machine-readable receipt that could tell separate chats or an external operator whether that public-verify pass actually succeeded.
- Added a generated `.zerker/launch-proof/public-verify-result.json` contract to the launch-proof pack: the manifest, README, HTML report, checklists, release-pack summary, and dashboard now all surface the result path alongside the script and logs directory.
- Tightened public-verify truthfulness so readiness now requires both the expected clean-shell logs and a valid result receipt; `PUBLIC_VERIFY_COMMANDS.sh` now overwrites the placeholder with per-step pass/fail details, and `scripts/release_smoke.py` plus focused coverage fail if that artifact disappears from the shipped proof surface.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke tests.test_dashboard -q` -> 130 tests OK
- `python3 -m unittest discover -s tests -q` -> 209 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment while verifying the new public-verify result receipt contract
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally and now prints `Public verify result: .zerker/launch-proof/public-verify-result.json`
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; release state now reports `Launch proof: ok`, `Public verify: pending`, and keeps the strict next step on the clean-shell public-verify pass
- `python3 -m zerker_memory prelaunch --summary-only` -> correctly failed strict publish; still blocked on missing clean-shell logs and launch assets

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, and the new `.zerker/launch-proof/public-verify-result.json` receipt will remain a pending placeholder until an external operator actually runs `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm the five expected logs land under `.zerker/launch-proof/public-verify-logs/`, confirm `.zerker/launch-proof/public-verify-result.json` flips from the pending placeholder to a passing receipt, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then capture the remaining checklist assets under `.zerker/launch-proof/assets/`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that the operator handoff has a single result receipt to return, not just five loose log files.

## 2026-05-30 - Release Guidance Critical Path Ordering

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the latest shipped operator surfaces now exposed the real gate, but `zmem status --summary-only` still repeated launch-asset guidance and could prioritize screenshot capture ahead of the clean-shell public-verify pass.
- Fixed Phase-1 next-step ordering so strict publish guidance now prioritizes `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` before launch-asset capture when both remain incomplete, matching the actual launch critical path instead of suggesting screenshots first.
- Deduplicated status-summary guidance by teaching `build_status_next_steps()` to append only the first unique strict-publish step, so the one-screen operator handoff no longer repeats the same `.zerker/launch-proof/CAPTURE_CHECKLIST.md` instruction twice.
- Added focused onboarding coverage for both behaviors so separate-chat/operator handoff fails tests if the clean-shell public verify step falls behind launch assets again or if the status summary regresses back to duplicate next steps.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 86 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 33 tests OK
- `python3 -m unittest discover -s tests -q` -> 209 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; `Next:` now lists clean-shell public verify first, launch-asset capture second, with no duplicate capture-checklist line
- `python3 -m zerker_memory prelaunch --summary-only` -> correctly failed strict publish and now lists clean-shell public verify before launch-asset capture
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, but they now follow the clean-shell public-verify step consistently across the CLI handoff surfaces.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm the five expected logs land under `.zerker/launch-proof/public-verify-logs/`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then capture the remaining checklist assets under `.zerker/launch-proof/assets/`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that the shipped one-screen CLI handoff points operators at the real Phase-1 critical path without duplicated instructions.

## 2026-05-30 - Console Launch Gate Visibility

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the CLI and proof pack already surfaced the real gate, but `zmem ui` and the local smoke harness still lagged the shipped truth that strict publish must stay blocked until clean-shell evidence exists.
- Extended the `zmem ui` release surface so the console now shows public-verify readiness, launch-asset readiness, the exact checklist/script paths, strict-publish blockers, and the current `0/5` and `0/8` evidence counts directly in the release panel and proof summaries instead of leaving operators to infer them from CLI output.
- Aligned `scripts/release_smoke.py` with the shipped Phase-1 contract: the smoke run now treats strict `release-pack --summary-only` and `prelaunch --summary-only` as intentionally blocked before clean-shell logs exist, and verifies that those summaries surface the expected public-verify and launch-asset blocker states instead of requiring a false green publish result.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_dashboard -q` -> 44 tests OK
- `python3 -m unittest discover -s tests -q` -> 207 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and now verifies that strict `release-pack` / `prelaunch` stay truthfully blocked on `public_verify_evidence` plus launch-asset capture until external proof exists
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish locally and still reports `Public verify: pending`, `Launch assets: pending`, `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, and `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`
- `python3 - <<'PY' ... build_release_readiness_state ...` -> confirmed console payload now exposes `public_verify_expected_count=5`, `public_verify_present_count=0`, `launch_assets_expected_count=8`, and `launch_assets_present_count=0`

Blockers:

- Phase 1 is still externally blocked on proving the live public repo/raw `install.sh` URL from a clean networked shell; that cannot be completed here.
- `python3 scripts/release_smoke.py --require-install-mode packaged` still cannot pass in this network-restricted environment because editable install cannot fetch `setuptools>=64` / `bdist_wheel`.
- Final screenshots/GIFs are still missing under `.zerker/launch-proof/assets/`, so strict publish remains correctly blocked even though the local proof/report surfaces are now clearer.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm the five expected logs land under `.zerker/launch-proof/public-verify-logs/`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then capture the remaining checklist assets under `.zerker/launch-proof/assets/`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that a separate chat can open `zmem ui` and see the exact missing public-verify and launch-asset evidence from one release panel.

## 2026-05-30 - Public Verify Gate Truthfulness

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the repo already tracked missing screenshots/GIFs, but the strict publish surfaces still let the clean-shell public-verify evidence remain implicit instead of first-class.
- Added first-class public-verify readiness tracking from the generated launch-proof manifest and `.zerker/launch-proof/public-verify-logs/`: status/reporting code now counts expected clean-shell logs, summarizes what is missing, and exposes that state alongside launch-proof, handoff, and launch assets.
- Tightened release truthfulness so `zmem status --summary-only`, `zmem release-pack --summary-only`, and strict `zmem prelaunch --summary-only` now surface `public_verify_evidence` directly; the strict publish gate stays blocked until the clean-shell log set exists, while the local alpha path keeps it as a warning.
- Expanded onboarding/release-smoke coverage so the new public-verify readiness signal is tested in status, prelaunch, release-pack, and helper-level manifest/log accounting.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 116 tests OK
- `python3 -m unittest discover -s tests -q` -> passed in latest run
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; now reports `Public verify: pending (contract pending (.zerker/launch-proof/public-verify-logs))` and `Strict publish gate: blocked (launch_proof_artifacts, public_verify_evidence)` before launch-proof exists
- `python3 -m zerker_memory prelaunch --summary-only` -> correctly failed with `public_verify_evidence: blocker (0/5 logs captured in .zerker/launch-proof/public-verify-logs; missing curl-install.log, first-run.log, release-pack.log, ...)`
- `python3 -m zerker_memory release-pack --summary-only` -> correctly failed strict publish in this local repo and now reports `Public verify: pending` plus the exact clean-shell log directory next step

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- Strict publish is now intentionally truthful: until `.zerker/launch-proof/public-verify-logs/` contains the clean-shell install, first-run, release-pack, packaged release-smoke, and prelaunch logs, `zmem prelaunch` will stay blocked.
- Actual launch screenshots/GIFs are still pending under `.zerker/launch-proof/assets/`, and the packaged-install smoke still needs a normal networked shell.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm the five expected logs land under `.zerker/launch-proof/public-verify-logs/`, then rerun `python3 scripts/release_smoke.py --require-install-mode packaged` and finish the screenshot/GIF checklist under `.zerker/launch-proof/assets/`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture; the difference now is that separate chats can see strict publish is still blocked by missing public-verify logs without reading prose.

## 2026-05-30 - Launch Asset Readiness Surface

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the proof pack already knew which screenshots/GIFs to capture, but the main CLI/operator surfaces still did not treat launch-asset readiness as first-class state.
- Added a stable launch-asset output contract under `.zerker/launch-proof/assets/`: `launch-proof.json` now includes `launch_assets_dir_path` plus per-asset `output_path` entries, `zmem launch-proof` creates that directory, and the generated README/checklists/report now tell operators exactly where each screenshot/GIF should land.
- Surfaced launch-asset readiness in the repo-local gates without pretending the external blocker is solved: `zmem status --summary-only`, `zmem release-pack --summary-only`, and `zmem prelaunch --summary-only` now report whether the final launch assets are still pending, while preserving the strict publish/public-verify contract and the existing packaged-install smoke flow.
- Tightened `scripts/release_smoke.py`, focused onboarding tests, and launch-facing docs/landing copy so launch verification now fails if the manifest drops the assets output contract or if the human-readable summaries stop surfacing the new launch-asset readiness state.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 82 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 32 tests OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 114 tests OK
- `python3 -m unittest discover -s tests -q` -> 203 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory prelaunch --summary-only` -> passed; now reports `launch_assets: warning (0/8 captured in .zerker/launch-proof/assets; missing install-status.png, first-run-status.png, release-pack-summary.png, ...)`
- `python3 -m zerker_memory release-pack --summary-only` -> passed; now reports `Launch assets: pending` plus the capture-directory next step while regenerating proof and handoff artifacts
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified first-run, direct module smoke, MCP, launch-proof, release-pack, handoff, handoff restore, strict prelaunch, and the new launch-asset output contract

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but that gap is now explicit and localized: the missing outputs are tracked under `.zerker/launch-proof/assets/` instead of staying implicit in prose docs.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then follow `.zerker/launch-proof/CAPTURE_CHECKLIST.md` and save the resulting screenshots/GIFs under `.zerker/launch-proof/assets/` until the release-pack and prelaunch summaries stop reporting launch assets as pending.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the difference now is that a separate chat can verify progress by looking only at `.zerker/launch-proof/assets/`, the capture checklist, and the summary-only CLI output.

## 2026-05-30 - Launch Asset Storyboard Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the remaining local gap was no longer proof generation itself, but the final screenshot/GIF handoff still left too much operator improvisation around the exact `zmem ui` and handoff-restore deliverables.
- Extended the generated launch-proof pack with a machine-readable launch-asset storyboard under `launch-proof.json`, covering the exact deliverables, commands, and capture focus for install status, first-run status, release-pack summary, proof report, transcript proof, `ui-release-pack`, and, when handoff artifacts exist, `handoff-restore-terminal` plus `ui-handoff-restore`.
- Rewrote the generated `.zerker/launch-proof/CAPTURE_CHECKLIST.md`, `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md`, `.zerker/launch-proof/README.md`, and `.zerker/launch-proof/index.html` surfaces so they now point operators at the same explicit storyboard instead of a loose prose sequence, with the release-pack path carrying the receive-side restore assets automatically.
- Tightened `scripts/release_smoke.py` plus focused onboarding/release-smoke coverage so launch verification now fails if the manifest drops the launch asset storyboard or if the release-pack proof pack stops naming the `ui-release-pack` and `ui-handoff-restore` capture contract.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 82 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 32 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory release-pack --summary-only` -> passed; regenerated proof pack and handoff surfaces with the explicit launch asset checklist/storyboard
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified first-run, direct module smoke, MCP, launch-proof, release-pack, handoff, handoff restore, strict prelaunch, and the new launch-asset manifest contract

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the generated proof pack now specifies the exact capture set; the remaining gap is running that clean-shell pass and recording the assets.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then capture the exact `install-status`, `first-run-status`, `release-pack-summary`, `proof-report-overview`, `transcript-proof`, `ui-release-pack`, `handoff-restore-terminal`, and `ui-handoff-restore` assets called out by `.zerker/launch-proof/CAPTURE_CHECKLIST.md`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the difference now is that a separate chat can execute the generated storyboard from `launch-proof.json` or `CAPTURE_CHECKLIST.md` without reconstructing the shot list.

## 2026-05-30 - Portable CLI Public Verify Handoff

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the generated proof pack had already become portable, but the terminal summaries still leaked creator-machine absolute paths and ended with a vague publish step instead of the exact clean-shell operator contract.
- Normalized `zmem launch-proof --summary-only` and `zmem release-pack --summary-only` into portable handoff surfaces: repo-local paths now render as `.zerker/...` in the terminal output, and launch-proof next steps now keep the UI/open commands copyable across machines.
- Tightened the ready-to-publish `zmem prelaunch`/`zmem release-pack` next-step contract so the local-green path now points directly at `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, `.zerker/launch-proof/public-verify-logs/`, and `.zerker/launch-proof/CAPTURE_CHECKLIST.md` instead of only saying to publish the repo/tag.
- Added focused coverage for absolute-path normalization and the new clean-shell next-step contract so the CLI handoff fails tests if those portable operator surfaces regress.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 114 tests OK
- `python3 -m unittest discover -s tests -q` -> 203 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory launch-proof --summary-only` -> passed; summary now prints `.zerker/...` artifact paths and copyable repo-local next steps
- `python3 -m zerker_memory release-pack --summary-only` -> passed; summary now prints the public verify script path and explicit clean-shell capture steps
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified first-run, direct module smoke, MCP, launch-proof, release-pack, handoff, handoff restore, strict prelaunch, and the updated terminal summary contract

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the terminal/operator handoff is now portable; the remaining gap is executing the clean-shell pass and capturing the resulting proof assets.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then keep `.zerker/launch-proof/public-verify-logs/` plus the screenshots/GIFs called out by `.zerker/launch-proof/CAPTURE_CHECKLIST.md` as the final Phase-1 proof set.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the difference now is that separate chats can hand an operator the terminal summary itself without machine-specific path cleanup.

## 2026-05-30 - Public Verify Front-And-Center Proof Pack

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the generated proof pack already shipped the script, checklist, manifest, and logs dir, but the main review surfaces still treated the clean-shell packaged-install pass as secondary even though that is now the only material launch gate left.
- Promoted the clean-shell public verify pass to a first-class generated proof-pack surface: `.zerker/launch-proof/README.md` now includes a dedicated `Clean-Shell Public Verify` section with the exact command sequence and expected log filenames, and `.zerker/launch-proof/index.html` now foregrounds the same script, logs dir, commands, and expected logs.
- Added focused onboarding coverage so launch-proof generation now fails tests if the proof-pack README/report stop surfacing the public packaged-install contract prominently enough for external operator handoff.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 112 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified first-run, direct module smoke, MCP, launch-proof, release-pack, handoff, handoff restore, strict prelaunch, and the updated proof-pack review surfaces

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the proof pack now puts the external packaged-install contract directly in the generated README/report instead of requiring an operator to cross-reference multiple docs first.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then keep `.zerker/launch-proof/public-verify-logs/` plus the screenshots/GIFs called out by `.zerker/launch-proof/CAPTURE_CHECKLIST.md` as the final Phase-1 proof set.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the difference now is that the generated proof-pack README/report themselves tell that operator exactly what to run and what logs to keep.

## 2026-05-30 - Public Verify Manifest Contract

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the proof pack already had the script, checklist, and logs dir, but it still lacked one machine-readable contract for the clean-shell public verify pass that separate chats and an external operator could audit without re-reading prose.
- Extended generated `.zerker/launch-proof/launch-proof.json` so it now carries the public verify contract directly: packaged-install requirement, expected clean-shell command sequence, expected per-step log filenames, and the relative script/checklist/log-dir paths.
- Tightened focused coverage plus `scripts/release_smoke.py` so launch verification now fails if `launch-proof` stops shipping that clean-shell contract alongside the existing readiness status.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 111 tests OK
- `python3 -m unittest discover -s tests -q` -> 200 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory launch-proof --summary-only` -> passed and regenerated repo-local `.zerker/launch-proof/`
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and verified launch-proof, release-pack, handoff, handoff restore, first-run, direct module smoke, MCP, and the new public-verify manifest contract

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the proof pack now carries the clean-shell proof contract in machine-readable form, so the remaining gap is external execution and capture rather than local operator ambiguity.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then keep `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/launch-proof.json`, and the console/handoff-restore assets from `.zerker/launch-proof/CAPTURE_CHECKLIST.md` as the final Phase-1 proof set.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; separate chats can now key off `launch-proof.json` instead of inferring the clean-shell proof contract from markdown.

## 2026-05-30 - Portable Proof Pack Paths

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the generated proof pack was still leaking creator-machine absolute paths into the checklists, which weakened the external operator handoff even after the verify script itself became portable.
- Fixed `zmem launch-proof` and `zmem release-pack --summary-only` so the generated `.zerker/launch-proof/CAPTURE_CHECKLIST.md` and `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md` now render repo-relative proof, handoff, log-dir, and console-command paths instead of host-specific absolute filesystem paths.
- Tightened focused onboarding coverage around the generated checklists so launch-proof artifact generation now fails tests if those external-facing proof surfaces regress back to machine-specific paths.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 110 tests OK
- `python3 -m unittest discover -s tests -q` -> 199 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and verified launch-proof, release-pack, handoff, handoff restore, first-run, direct module smoke, MCP, and the updated proof-pack path contract
- `python3 -m zerker_memory release-pack --summary-only` -> passed and regenerated repo-local `.zerker/launch-proof/` / `.zerker/handoff/`
- Regenerated `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md` and `.zerker/launch-proof/CAPTURE_CHECKLIST.md` now point at `.zerker/...` paths rather than `/Users/...` creator-machine paths

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the packaged proof handoff is now path-portable enough for the external operator pass instead of assuming the creator machine layout.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then capture the console/handoff assets from `.zerker/launch-proof/CAPTURE_CHECKLIST.md` using the now-portable `.zerker/...` proof references.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the difference now is that the generated proof pack no longer requires path translation from the originating machine.

## 2026-05-30 - Launch Proof Status Truthfulness

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the new machine-readable launch-proof manifest was still embedding a stale pre-generation status snapshot, which made separate chats and the eventual external operator handoff see `Launch proof: missing` even after the proof pack existed.
- Fixed `zmem launch-proof` so it now recomputes status after writing the proof artifacts, then rewrites `launch-proof.json`, the HTML report, and the returned payload with that post-generation state instead of the stale pre-generation snapshot.
- Tightened focused onboarding coverage plus `scripts/release_smoke.py` so the launch-proof contract now checks the manifest status when a repo release surface is present, preventing the proof pack from silently regressing back to contradictory readiness output.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 110 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory launch-proof --summary-only` -> passed and regenerated `.zerker/launch-proof/`
- `python3 -c 'import json, pathlib; d=json.loads(pathlib.Path(".zerker/launch-proof/launch-proof.json").read_text()); print(d["status_summary"])'` -> manifest now reports `Launch proof: ok`, `Handoff: ok`, `Local alpha gate: ok`, and `Strict publish gate: ok`
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified launch-proof, release-pack, handoff, handoff restore, first-run, direct module smoke, MCP, and the updated launch-proof manifest contract

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the proof pack and manifest now agree about repo-local readiness, so the remaining launch work is capture and external verification rather than local contract ambiguity.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then keep `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/launch-proof.json`, and the console/handoff-restore assets from `.zerker/launch-proof/CAPTURE_CHECKLIST.md` as the final Phase-1 proof set.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the difference now is that the handoff manifest and report tell that operator the post-generation truth instead of a stale local blocker.

## 2026-05-30 - Launch Proof Manifest

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because external verification is still blocked here, so the highest-leverage local improvement was to give the proof pack one machine-readable contract that can survive separate chats and the eventual external handoff.
- Added generated `.zerker/launch-proof/launch-proof.json` output to `zmem launch-proof`, carrying the proof-pack artifact paths, action ID, and status snapshot in one stable manifest analogous to the existing handoff manifest.
- Tightened `scripts/release_smoke.py`, focused onboarding/release-smoke coverage, and launch-facing docs/landing copy so launch verification now fails if `launch-proof` or `release-pack` stop refreshing that manifest or if the summary/docs stop surfacing it.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding -q` -> 110 tests OK
- `python3 -m unittest discover -s tests -q` -> 199 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and verified launch-proof, release-pack, handoff, handoff restore, first-run, direct module smoke, MCP, and the generated launch-proof manifest plus public verify script/checklists/log-dir contract

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the proof pack now has a machine-readable manifest plus the generated checklists/script/log target, so the external clean-shell pass has one tighter contract for artifact inventory and evidence capture.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then keep `.zerker/launch-proof/public-verify-logs/`, `.zerker/launch-proof/launch-proof.json`, and the console/handoff-restore assets from `.zerker/launch-proof/CAPTURE_CHECKLIST.md` as the final Phase-1 proof set.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the generated launch-proof manifest is now the machine-readable handoff anchor for that sidecar.

## 2026-05-30 - Portable Public Verify Script

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because the previous log-capture work still left one portability bug: the generated clean-shell script pointed its logs at the creator machine's absolute path instead of the proof pack beside the script.
- Fixed `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` to derive `public-verify-logs/` from the script directory itself, so the generated clean-shell proof artifact now keeps its evidence with the pack instead of hardcoding the source machine path.
- Tightened `scripts/release_smoke.py` plus focused onboarding/release-smoke coverage so launch verification now fails if `launch-proof` stops surfacing the public verify logs dir or if launch-proof/release-pack stop generating `PUBLIC_VERIFY_COMMANDS.sh`.

Verification:

- `python3 -m unittest tests.test_release_smoke -q` -> 31 tests OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 79 tests OK
- `python3 -m unittest discover -s tests -q` -> 199 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and verified launch-proof, release-pack, handoff, handoff restore, first-run, direct module smoke, MCP, and the generated public verify script/checklists/log-dir contract

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the generated proof pack now has a portable script-relative log target, so the external clean-shell pass can keep its terminal evidence beside the pack regardless of which machine generates it.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then keep `.zerker/launch-proof/public-verify-logs/` plus the console/handoff-restore assets from `.zerker/launch-proof/CAPTURE_CHECKLIST.md` as the final Phase-1 proof set.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the generated public verify script is now portable enough to hand directly to that sidecar.

## 2026-05-30 - Public Verify Log Capture

Shipped:

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live GitHub repo/raw installer from a clean networked shell. This slice was the right next move because external verification is still blocked here, so the highest-leverage local improvement was to make the generated clean-shell proof script preserve its own evidence instead of relying on manual terminal capture.
- Extended `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` so the clean-shell public alpha script now writes per-step logs for install, first-run, release-pack, packaged release-smoke, and prelaunch into `.zerker/launch-proof/public-verify-logs/`.
- Surfaced the generated public verify logs directory in `zmem launch-proof --summary-only`, `zmem release-pack --summary-only`, the launch-proof README/report/checklist output, and the launch-facing docs/landing copy so the next external pass has one explicit place to keep durable terminal evidence.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 78 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 30 tests OK
- `python3 -m unittest discover -s tests -q` -> 197 tests OK
- `python3 -m zerker_memory launch-proof --summary-only` -> passed; now prints `.zerker/launch-proof/public-verify-logs`
- `python3 -m zerker_memory release-pack --summary-only` -> passed; now prints `.zerker/launch-proof/public-verify-logs`
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified launch-proof, release-pack, handoff, handoff restore, first-run, direct module smoke, MCP, and the generated public verify artifacts

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the proof pack now also includes the generated `.zerker/launch-proof/public-verify-logs/` target so the external clean-shell run can leave terminal evidence behind alongside the existing capture and verify checklists.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, execute `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` or mirror its steps, confirm `python3 scripts/release_smoke.py --require-install-mode packaged` passes, then keep the resulting `.zerker/launch-proof/public-verify-logs/` output and capture the console/handoff-restore assets from `.zerker/launch-proof/CAPTURE_CHECKLIST.md`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture once network access is available; the generated logs directory is now the terminal-evidence handoff for that sidecar.

## 2026-05-30 - Public Verify Script And Repo-Path Fix

Shipped:

- Added a generated `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` artifact to `zmem launch-proof`, so the final clean-shell public alpha pass now has a copy-ready script instead of only prose checklists.
- Fixed the generated public verify checklist and launch-facing docs to include `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"` after the raw installer, matching the actual repo path created by `install.sh` before repo-local proof commands run.
- Extended launch-proof summaries, proof artifacts, README/QUICKSTART/DAY1/product status, the public launch audit, the GitHub release checklist, and landing copy so the shipped Phase-1 operator contract now points at the generated script plus the corrected clean-shell repo path.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 78 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 30 tests OK
- `python3 -m unittest discover -s tests -q` -> 197 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and verified `public_verify_script_path`, the generated clean-shell script/checklist, direct module smoke, first-run, launch-proof, handoff, handoff restore, `release-pack --summary-only`, and strict `prelaunch --summary-only`

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so `python3 scripts/release_smoke.py --require-install-mode packaged` still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the proof pack now includes both `.zerker/launch-proof/CAPTURE_CHECKLIST.md` and `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` to drive the local asset pass and the external clean-shell pass from one generated source of truth.

Next:

- From a clean networked shell against the live public repo, run the raw installer, `cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"`, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then capture the terminal, release-pack, console, and handoff-restore proof assets using `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh` and `.zerker/launch-proof/CAPTURE_CHECKLIST.md`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus screenshot/GIF capture using the generated public verify script and launch asset checklist once network access is available.

## 2026-05-29 - Generated Public Verify Checklist

Shipped:

- Added a generated `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md` artifact to `zmem launch-proof`, so the final clean-shell public alpha verification commands now live inside the proof pack instead of only in docs.
- Extended `zmem release-pack --summary-only` to refresh that public verify checklist with handoff and strict-prelaunch context, keeping the external packaged-install proof path tied to the same generated release artifacts as screenshots and console capture.
- Tightened release smoke, launch-proof summaries, docs, and landing copy so the shipped Phase-1 launch contract now treats the public verify checklist as a required generated artifact.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 78 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 30 tests OK
- `python3 -m unittest discover -s tests -q` -> 197 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and now also verified `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md` from both `launch-proof` and `release-pack`

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so the strict packaged-install gate still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the generated capture and public-verify checklists now encode both the local asset pass and the external clean-shell pass.

Next:

- From a clean networked shell against the live public repo, run the curl installer, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then use `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md` and `.zerker/launch-proof/CAPTURE_CHECKLIST.md` to capture the terminal, release-pack, console, and handoff-restore proof assets.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus the actual screenshot/GIF capture pass once network access is available.

## 2026-05-29 - Generated Launch Asset Checklist

Shipped:

- Added a generated `.zerker/launch-proof/CAPTURE_CHECKLIST.md` artifact to `zmem launch-proof`, so the proof pack now includes a concrete launch-asset sequence instead of leaving screenshots/GIFs spread across docs.
- Extended `zmem release-pack --summary-only` to refresh that checklist with the handoff manifest, handoff README, restore command, and strict-prelaunch status so the release-pack path now produces one screenshot-ready operator handoff.
- Updated release smoke plus launch-facing docs and landing copy so the shipped Phase-1 proof contract now treats the capture checklist as part of the generated launch pack.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 78 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 30 tests OK
- `python3 -m unittest discover -s tests -q` -> 197 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and now also verified the generated launch-proof capture checklist plus the release-pack refresh of that checklist

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so the strict packaged-install gate still needs a normal networked shell.
- Actual launch screenshots/GIFs are still pending, but the generated checklist now removes the remaining ambiguity in capture order and proof surfaces.

Next:

- From a clean networked shell against the live public repo, run the curl installer, rerun `python3 scripts/release_smoke.py --require-install-mode packaged`, then use `.zerker/launch-proof/CAPTURE_CHECKLIST.md` to capture the install, release-pack, console, and handoff-restore proof assets.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the external clean-shell publish audit plus the actual screenshot/GIF capture pass using the generated launch checklist once network access is available.

## 2026-05-29 - Strict Packaged Install Gate

Shipped:

- Added `--require-install-mode` to `scripts/release_smoke.py`, with a `packaged` alias that accepts real editable install paths and rejects `local-wrappers`.
- Fixed `scripts/release_smoke.py` argument handling so script-invocation flags now actually read `sys.argv[1:]`; the new strict gate would have been a no-op otherwise.
- Updated README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, the public launch audit, and the GitHub release checklist so the external clean-shell launch pass now uses `python3 scripts/release_smoke.py --require-install-mode packaged`.

Verification:

- `python3 -m unittest tests.test_release_smoke -q` -> 30 tests OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 108 tests OK
- `python3 -m unittest discover -s tests -q` -> 197 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified direct module smoke, first-run, handoff, handoff restore, `launch-proof --summary-only`, `release-pack --summary-only`, and strict `prelaunch --summary-only`
- `python3 scripts/release_smoke.py --require-install-mode packaged` -> failed as expected in the restricted environment with `install_mode=local-wrappers`, proving the new external packaged-install gate now fails fast instead of silently passing

Blockers:

- Phase 1 remains blocked on external proof of the live GitHub repo and raw `install.sh` URL from a clean networked shell; that cannot be completed from this restricted environment.
- In this restricted environment, editable install still cannot fetch `setuptools>=64` and cannot build `bdist_wheel`, so the strict packaged-install gate correctly fails before the public launch claim can be made.
- Launch screenshots/GIFs from `zmem ui` release-pack plus handoff restore are still pending once the external launch proof is complete.

Next:

- From a clean networked shell against the live public repo, run `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh | bash` and `python3 scripts/release_smoke.py --require-install-mode packaged`; once both pass, capture the launch screenshots/GIFs for the console release-pack and handoff-restore flow.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains the screenshot/GIF capture set for `zmem ui` release-pack/send/receive proof plus the external clean-shell publish audit once network access is available.

## 2026-05-29 - Launch Proof Summary-Only Flow

Shipped:

- Added `zmem launch-proof --summary-only`, giving the proof-only path the same compact operator-facing output style already used by `status`, `handoff`, `restore`, `prelaunch`, and `release-pack`.
- Added summary rendering plus CLI/release-smoke coverage so regressions in the human-readable launch-proof contract fail before tagging.
- Updated README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so launch docs now point operators at the terminal-first proof summary when they want artifact generation without the full release-pack refresh.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 105 tests OK
- `python3 -m unittest discover -s tests -q` -> 194 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and now also verified `zmem launch-proof --summary-only` alongside direct module smoke, first-run, handoff, handoff restore, `release-pack --summary-only`, and strict `prelaunch --summary-only`

Blockers:

- The strict publish gate and proof-only summary flow now pass locally, but the live GitHub repo/raw `install.sh` URL still needs one external clean-shell verification pass before the curl install path is fully proven.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch `setuptools>=64` or build `bdist_wheel`; packaged-install mode should be rerun in a normal networked shell.
- Treeship proof is still a local ready-to-publish artifact rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs from the console release-pack plus handoff-restore flow and the new `launch-proof --summary-only` terminal view.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains screenshot/GIF capture for the console release-pack plus handoff-restore path, and a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Strict Publish Gate Release Smoke

Shipped:

- Tightened `scripts/release_smoke.py` so the verified launch contract now runs `zmem release-pack --summary-only` and `zmem prelaunch --summary-only` without placeholder mode, instead of only exercising the placeholder-tolerant alpha path.
- Added focused release-smoke helper coverage so the human-readable release-pack and prelaunch summaries fail fast if the strict publish-ready operator output regresses.
- Updated README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, landing copy, and orchestration state so launch-facing docs now describe strict prelaunch verification as part of the shipped release path.

Verification:

- `python3 -m unittest tests.test_release_smoke -q` -> 25 tests OK
- `python3 -m unittest discover -s tests -q` -> 191 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and verified direct module smoke, first-run, launch-proof, handoff, handoff restore, `release-pack --summary-only`, and strict `prelaunch --summary-only`

Blockers:

- The strict publish gate now passes locally, but the live GitHub repo/raw `install.sh` URL still needs one external clean-shell verification pass before the curl install path is fully proven.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch `setuptools>=64` or build `bdist_wheel`; packaged-install mode should be rerun in a normal networked shell.
- Treeship proof is still a local ready-to-publish artifact rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs from the console release-pack plus handoff-restore flow now that strict prelaunch is already covered locally.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains screenshot/GIF capture for the console release-pack plus handoff-restore path, and a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Console Release Pack Action

Shipped:

- Extended `zmem ui` with a one-click Release Pack action so the local console now exposes the same combined launch operator path as `zmem release-pack --summary-only`.
- Added dashboard release-pack coverage by wiring the console to the existing combined helper and rendering the launch-proof, handoff, and prelaunch result in the proof inspector instead of forcing operators through three separate artifact actions first.
- Updated README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, landing copy, and orchestration state so launch-facing docs now describe the console as a first-class release-pack surface, not just a lower-level artifact console.

Verification:

- `python3 -m unittest tests.test_dashboard -q` -> 10 tests OK
- `python3 -m unittest discover -s tests -q` -> 189 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- The public repo/raw `install.sh` URL still needs an external clean-shell verification pass from a networked environment before the curl install path is truly launch-ready.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch `setuptools>=64` or build `bdist_wheel`; packaged-install mode should be rerun in a normal networked shell.
- Treeship proof is still a local ready-to-publish artifact rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs from the one-click console release-pack flow and receive-side restore path.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains screenshot/GIF capture for the console release-pack plus handoff-restore path, and a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Console Handoff Restore Action

Shipped:

- Extended `zmem ui` so the local review console can now restore `.zerker/handoff/` into a fresh import DB, making the receive-side proof path visible from the same surface that already generated launch-proof and handoff artifacts.
- Added collision-safe dashboard restore behavior under `.zerker/imports/` so repeated console restores stay non-destructive and do not require manual cleanup between proof runs.
- Updated README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, landing copy, and orchestration state so launch-facing docs now describe the console as a full send-and-receive proof surface.

Verification:

- `python3 -m unittest tests.test_dashboard -q` -> 9 tests OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 77 tests OK
- `python3 -m unittest discover -s tests -q` -> 188 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- The public repo/raw `install.sh` URL still needs an external clean-shell verification pass from a networked environment before the curl install path is truly launch-ready.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch `setuptools>=64` or build `bdist_wheel`; packaged-install mode should be rerun in a normal networked shell.
- Treeship proof is still a local ready-to-publish artifact rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs from the console now that it covers both handoff send and receive flows.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains screenshot/GIF capture for the console restore path plus a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Release Pack Operator Flow

Shipped:

- Added `zmem release-pack --summary-only`, a one-command repo-local release operator flow that refreshes `.zerker/handoff/`, `.zerker/launch-proof/`, and the prelaunch gate together.
- Updated `zmem status --summary-only` plus `zmem prelaunch` next-step guidance so when release artifacts are stale the CLI now points operators at the combined release-pack command instead of separate launch-proof and handoff refreshes.
- Updated release smoke, README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, launch audit, current state, and landing copy so the shortest shipped launch-refresh path is now the combined release-pack flow.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 100 tests OK
- `python3 -m unittest discover -s tests -q` -> 187 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and verified `release-pack --summary-only`, first-run, direct module smoke, launch-proof, handoff, handoff restore, agent installs, and MCP flows

Blockers:

- The public repo/raw `install.sh` URL still needs an external clean-shell verification pass from a networked environment before the curl install path is truly launch-ready.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch `setuptools>=64` or build `bdist_wheel`; packaged-install mode should be rerun in a normal networked shell.
- Treeship proof is still a local ready-to-publish artifact rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs from the release-pack path and console.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains release-pack/console screenshot capture plus a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Console Release Artifact Actions

Shipped:

- Extended `zmem ui` so the local review console now shows repo release readiness and can generate both launch-proof and shared handoff artifacts directly from the browser surface.
- Added dashboard API coverage for release-artifact generation by reusing the existing `zmem launch-proof` and `zmem handoff --summary-only` helpers instead of duplicating proof logic.
- Updated README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so day-1 operators now see the console as a first-class proof and handoff surface, not only the CLI.

Verification:

- `python3 -m unittest tests.test_dashboard -q` -> 8 tests OK
- `python3 -m unittest tests.test_cli_onboarding -q` -> 74 tests OK
- `python3 -m unittest discover -s tests -q` -> 184 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified first-run, direct module smoke, launch-proof, handoff, handoff restore, agent installs, and MCP flows

Blockers:

- The public repo/raw `install.sh` URL still needs an external clean-shell verification pass from a networked environment before the curl install path is truly launch-ready.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch `setuptools>=64` or build `bdist_wheel`; packaged-install mode should be rerun in a normal networked shell.
- Treeship proof is still a local ready-to-publish artifact rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs from the console now that it can generate launch-proof and handoff artifacts itself.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains launch asset capture plus a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Handoff Restore Manifest

Shipped:

- Extended `zmem handoff --summary-only` so the packaged handoff now includes `.zerker/handoff/handoff.json`, a machine-readable manifest that pins the exact snapshot, bundle, Treeship statement, and README for the transfer.
- Added one-command receive-side restore with `zmem --db .zerker/imported.sqlite restore --handoff-dir .zerker/handoff`, which verifies the packaged snapshot and bundle before restoring into an empty target store.
- Updated release smoke plus launch-facing docs so the shipped cross-machine path now proves both handoff creation and handoff receipt, not just the sender side.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 74 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 23 tests OK
- `python3 -m unittest discover -s tests -q` -> 182 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` and verified handoff manifest creation, `restore --handoff-dir`, direct module smoke, first-run, launch-proof, bundle, snapshot, agent installs, and MCP flows

Blockers:

- The public repo/raw `install.sh` URL still needs an external clean-shell verification pass from a networked environment; this run improved local portability but could not prove the live curl path.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch packaging dependencies or `bdist_wheel`; packaged-install mode should be rechecked in a normal networked shell.
- Treeship proof is still a local ready-to-publish artifact rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture screenshots/GIFs of `zmem status --summary-only`, `.zerker/launch-proof/`, `.zerker/handoff/`, and the new receive-side restore path.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains launch asset capture plus a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Status Release Readiness View

Shipped:

- Extended `zmem status --summary-only` so the one-screen operator view now includes launch-proof readiness, handoff readiness, and local-alpha versus strict-publish gate state when the full repo launch surface is present.
- Updated status next-step selection so once workspace proof exists it points directly at `zmem launch-proof` or `zmem handoff --summary-only` when those release artifacts are the missing blocker, instead of only repeating generic smoke guidance.
- Refreshed README, QUICKSTART, DAY1 setup, PRODUCT_STATUS, and landing copy so the shipped day-1 story now matches the new status behavior and repo-local release dashboard.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 72 tests OK
- `python3 -m unittest discover -s tests -q` -> 180 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` in the restricted environment and still verified direct module smoke, first-run, launch-proof, handoff, bundle, snapshot, and MCP flows
- `python3 -m zerker_memory handoff --summary-only` -> passed; refreshed `.zerker/handoff/README.md` plus verified snapshot, bundle, and Treeship statement in this repo
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed; reported `Launch proof: ok`, `Handoff: ok`, `Local alpha gate: ok`, `Strict publish gate: ok`
- `python3 -m zerker_memory prelaunch --summary-only` -> passed; all required files, launch-proof artifacts, handoff artifacts, and public URLs OK

Blockers:

- The public repo/raw `install.sh` URL still needs an external networked verification pass from a clean shell; this run improved the local dashboard but could not prove the live curl path.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch packaging dependencies or `bdist_wheel`; packaged-install mode should be rechecked in a normal networked shell.
- Treeship proof is still local ready-to-publish output rather than a fully signed public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs now that `zmem status --summary-only` shows the release gate in one screen.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains launch asset capture plus a clean-shell publish audit after external network verification is available.

## 2026-05-29 - Prelaunch Treeship Handoff Gate

Shipped:

- Tightened `zmem prelaunch` so `handoff_artifacts` now requires the shared README plus `.snapshot.json`, `.bundle.json`, and `.treeship.json` exports instead of treating any handoff JSON file as sufficient.
- Added onboarding coverage for the stricter release gate, including the passing placeholder-audit fixture with full handoff exports and a failure case when the Treeship handoff statement is missing.
- Updated README, QUICKSTART, and PRODUCT_STATUS so launch-facing copy now matches the shipped release contract: handoff proof is only launch-ready when the Treeship statement ships with the snapshot and bundle.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 93 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m unittest discover -s tests -q` -> 178 tests OK
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` and verified handoff snapshot, handoff bundle, handoff Treeship statement, launch-proof, first-run, MCP, and direct `python3 -m zerker_memory` smoke

Blockers:

- The public repo/raw `install.sh` URL still needs to exist before the curl install path can be externally verified from a clean shell.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch packaging dependencies or `bdist_wheel`; packaged-install mode should be rechecked in a normal networked shell.
- The Treeship path is still Treeship-ready rather than fully signed and published; this run tightened the local prelaunch gate, but external publish/verify still depends on the real Treeship CLI and public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, rerun `python3 scripts/release_smoke.py` in packaged-install mode, then capture launch screenshots/GIFs from `.zerker/launch-proof/` and `.zerker/handoff/`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains launch asset capture from `.zerker/launch-proof/` and `.zerker/handoff/`, plus a clean-shell publish audit after the public repo exists.

## 2026-05-29 - Handoff Treeship Proof

Shipped:

- Extended `zmem handoff` so action-backed handoffs now export a Treeship-ready statement alongside the verified snapshot and receipt bundle.
- Updated the handoff summary and generated `README.md` to surface the Treeship artifact plus the exact dry-run publish command for that action.
- Tightened `scripts/release_smoke.py` and launch-facing docs so the shipped handoff/release contract now requires the Treeship statement to be present, not just the snapshot and bundle.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke -q` -> 92 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m unittest discover -s tests -q` -> 177 tests OK
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` and verified handoff snapshot, handoff bundle, handoff Treeship statement, launch-proof, first-run, MCP, and direct `python3 -m zerker_memory` smoke

Blockers:

- The public repo/raw `install.sh` URL still needs to exist before the curl install path can be externally verified from a clean shell.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch packaging dependencies or `bdist_wheel`; packaged-install mode should be rechecked in a normal networked shell.
- The Treeship path is still Treeship-ready rather than fully signed and published; this run packages the statement and dry-run command, but the external publish/verify workflow still depends on the real Treeship CLI and public receipt flow.

Next:

- Verify the live public repo and raw installer from a clean networked shell, then capture launch screenshots/GIFs from `.zerker/launch-proof/` and `.zerker/handoff/` now that the handoff package includes the Treeship proof artifact.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains launch asset capture from `.zerker/launch-proof/` and `.zerker/handoff/`, plus a clean-shell publish audit after the public repo exists.

## 2026-05-29 - Python Module Runtime Reexec

Shipped:

- Added CLI runtime fallback so direct `python3 -m zerker_memory doctor` and `python3 -m zerker_memory status --summary-only` auto-reexec under a discovered Python 3.10+ interpreter when the shell default is older.
- Updated `scripts/release_smoke.py` so release verification now proves that direct module-entrypoint path in a fresh workspace, alongside the existing bootstrap, handoff, launch-proof, bundle, snapshot, and MCP checks.
- Updated README, QUICKSTART, day-1 setup, product status, current state, and landing copy so launch-facing docs describe the shipped runtime behavior instead of the old Python 3.9 workaround.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_doctor tests.test_release_smoke -q` -> 98 tests OK
- `python3 -m unittest discover -s tests -q` -> 177 tests OK
- `python3 -m zerker_memory doctor --skip-eval` -> passed via runtime reexec; `python_version: 3.10.15`
- `python3 -m zerker_memory status --summary-only --skip-eval` -> passed via runtime reexec; `Workspace ready: yes`, `Doctor: ok`, `Manual pack ready: yes`
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` and verified `python_module_smoke`, handoff, launch-proof, first-run, bundle, snapshot, and MCP flows

Blockers:

- The public repo/raw `install.sh` URL still needs to exist before the curl install path can be externally verified from a clean shell.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch packaging dependencies; packaged-install mode should be rechecked in a normal networked shell.
- The new runtime reexec path still depends on a discoverable Python 3.10+ interpreter on `PATH` or through `pyenv`; shells with only an old `python3` still need `bash install.sh` or manual venv creation.

Next:

- Create or publish `github.com/zerkerlabs/zerker-memory`, verify `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh | bash`, then rerun `python3 scripts/release_smoke.py` where packaging dependencies are reachable.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains proof screenshot/GIF capture plus a clean-shell publish audit after the public repo exists.

## 2026-05-29 - Handoff Release Gate

Shipped:

- Tightened `zmem prelaunch` so release readiness now requires `.zerker/handoff/README.md` plus verified handoff exports alongside the existing launch-proof artifacts.
- Updated `scripts/release_smoke.py` to prove `zmem handoff` end to end before `zmem launch-proof` and the first-run path, so the shipped launch contract now covers cross-machine restore artifacts too.
- Updated launch-facing docs and orchestration state so the final publish gate explicitly expects both proof capture and handoff artifacts.

Verification:

- `python3 -m unittest tests.test_cli_onboarding -q` -> 66 tests OK
- `python3 -m unittest tests.test_release_smoke -q` -> 22 tests OK
- `python3 -m unittest discover -s tests -q` -> 173 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory prelaunch --summary-only` -> passed; `handoff_artifacts: ok`, `launch_proof_artifacts: ok`, `public_urls: ok`
- `python3 scripts/release_smoke.py` -> passed; fell back to `install_mode: local-wrappers` and verified `zmem handoff`, `zmem launch-proof`, bundle, snapshot, and first-run flows

Blockers:

- The public repo/raw `install.sh` URL still needs to exist before the curl install path can be externally verified from a clean shell.
- In this restricted environment, release smoke still falls back to local wrappers because editable install cannot fetch packaging dependencies; packaged-install mode should be rechecked in a normal networked shell.

Next:

- Create or publish `github.com/zerkerlabs/zerker-memory`, verify `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh | bash`, then rerun `python3 scripts/release_smoke.py` where packaging dependencies are reachable.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains screenshot/GIF capture from `.zerker/launch-proof/` and `.zerker/handoff/`.

## 2026-05-29 - Zerker Labs Repo Target

Shipped:

- Set the public repository target to `zerkerlabs/zerker-memory`.
- Replaced launch-facing placeholder URLs in README, QUICKSTART, landing, pyproject metadata, launch plan, GitHub release checklist, and public launch audit.
- Updated orchestration state so the remaining blocker is no longer repo selection; it is creating/publishing that repo and verifying the live raw `install.sh` URL.

Verification:

- `rg` URL scan -> launch-facing raw install and GitHub metadata now point at `zerkerlabs/zerker-memory`; the only old placeholder text left is historical build-log context.
- `python3 -m zerker_memory prelaunch --summary-only` -> passed with `public_urls: ok`.
- `python3 -m unittest tests.test_cli_onboarding` -> 65 tests OK.

Blockers:

- The GitHub repo/raw `install.sh` URL still needs to exist publicly before the curl install command can be verified from a clean shell.

Next:

- Create or publish `github.com/zerkerlabs/zerker-memory`, verify `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh | bash`, then run the final release gate.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains screenshot/GIF capture from `.zerker/launch-proof/` and `.zerker/handoff/`.

## 2026-05-29 - Shared Handoff Pack

Shipped:

- Added `zmem handoff`, a one-command shared-memory transfer flow that writes `.zerker/handoff/README.md`, a verified snapshot, and the latest or selected action bundle when one exists.
- Kept the handoff path useful before a real action exists: snapshot-only workspaces still get a valid package plus README guidance telling operators how to regenerate the pack after `zmem inject` or `zmem agent smoke`.
- Updated README, QUICKSTART, day-1 setup, shared-memory docs, product status, and landing copy so the launch-facing proof story now points cross-machine review and multi-agent handoff at `zmem handoff --summary-only`.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 65 tests OK
- `python3 -m unittest discover -s tests` -> 171 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory handoff --summary-only` -> passed; wrote `.zerker/handoff/README.md`, verified snapshot, and verified latest bundle in this workspace

Blockers:

- The public repo is now chosen as `zerkerlabs/zerker-memory`, but the live GitHub repo/raw `install.sh` URL still needs to exist before external curl verification.
- The shell `python3` in this workspace is still `3.9.6`, so direct doctor/status outside the shipped bootstrap or supported interpreter path remains intentionally blocked.

Next:

- Create or publish `github.com/zerkerlabs/zerker-memory`, verify the live raw `install.sh` curl path, then run the final release gate.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains a launch/docs audit for any remaining placeholder GitHub URL copy plus real screenshot/GIF capture using the launch-proof and handoff artifact directories.

## 2026-05-29 - Launch Proof HTML Report

Shipped:

- Added a generated `.zerker/launch-proof/index.html` report to `zmem launch-proof`, giving launch reviewers a single local artifact that summarizes the proof pack, action ID, review commands, and status snapshot.
- Tightened `zmem prelaunch` so launch-proof readiness now requires that HTML report alongside the existing transcript, bundle, snapshot, and BT artifacts.
- Updated `scripts/release_smoke.py`, README, QUICKSTART, day-1 setup, product status, current state, and landing proof copy so the shipped proof path now points users at the HTML report before screenshots or demos.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 62 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 21 tests OK
- `python3 -m unittest discover -s tests` -> 168 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory launch-proof` -> passed; wrote `.zerker/launch-proof/index.html` plus refreshed transcript, bundle, snapshot, and BT exports
- `python3 -m zerker_memory prelaunch --allow-placeholders --summary-only` -> passed; reported only intentional public URL placeholder warnings
- `python3 scripts/release_smoke.py` -> passed; restricted sandbox fell back to `install_mode: local-wrappers` and still proved agent installs, MCP smoke, launch proof, HTML report, first-run, bundle, and snapshot flows

Blockers:

- Final public GitHub owner/repo is still not chosen, so strict publish readiness remains blocked on the placeholder install/repo URLs.

Next:

- Choose the final public GitHub owner/repo, replace placeholder URLs, verify the live raw `install.sh` curl path, then rerun plain `zmem prelaunch`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains turning `.zerker/launch-proof/index.html`, the transcript, and the local console into GIF/screenshot proof assets.

## 2026-05-29 - Prelaunch Release Gate

Shipped:

- Added `zmem prelaunch`, a release-manager audit that checks required release files, CLI entrypoints, `.gitignore` coverage for generated state, launch-proof artifacts, bootstrap readiness summary wiring, and unresolved public URL placeholders.
- Added `--allow-placeholders` so the current local alpha can pass while still warning about the final GitHub owner/repo placeholders; plain `zmem prelaunch` remains strict and blocks until those URLs are replaced.
- Updated README, public launch audit, GitHub release checklist, product status, and current orchestration state so future release runs know to use `zmem prelaunch`.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 62 tests OK
- `python3 -m unittest discover -s tests` -> 168 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory prelaunch --allow-placeholders --summary-only` -> passed; reported public URL placeholders as warnings
- `python3 -m zerker_memory prelaunch --summary-only` -> failed as expected on the unresolved public URL placeholders only
- `python3 scripts/release_smoke.py` -> passed; restricted sandbox fell back to `install_mode: local-wrappers` and still proved entrypoints, agent/MCP smoke, launch proof, first-run, bundle, and snapshot flows

Blockers:

- Final public GitHub owner/repo is still not chosen, so strict `zmem prelaunch` correctly blocks on placeholder install/repo URLs.

Next:

- Choose the final public GitHub owner/repo, replace placeholder URLs, verify the live raw `install.sh` curl path, then rerun plain `zmem prelaunch`.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar remains launch-proof GIF/screenshot capture from `.zerker/launch-proof/terminal-transcript.txt` and the local console.

## 2026-05-29 - First-Class Launch Proof CLI

Shipped:

- Added `zmem launch-proof`, a first-class CLI flow that refreshes `.zerker/launch-proof/` with a clean proof database, transcript, bundle, snapshot, BT export, status summary, and README in one command.
- Converted `scripts/launch_proof.sh` into a thin Python-picking wrapper around `zmem launch-proof`, so docs and operators can keep using the shell entrypoint without duplicating the proof logic.
- Updated release smoke, launch audit docs, release checklist, launch plan, current state, product status, and README so launch proof capture now leads with `zmem launch-proof` while still documenting the wrapper fallback.

Verification:

- `bash -n scripts/launch_proof.sh` -> OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 80 tests OK
- `python3 -m unittest discover -s tests` -> 165 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; auto-reexeced under Python 3.10, proved `zmem launch-proof` plus `bash scripts/launch_proof.sh`, and completed full release smoke with `install_mode: local-wrappers`

Blockers:

- The shell `python3` in this workspace is still `3.9.6`, so direct `python3 -m zerker_memory doctor` and `status` remain intentionally blocked outside the shipped Python 3.10+ bootstrap/reexec flows.
- Final public GitHub owner/repo is still not chosen, so public curl/install URLs and launch-facing GitHub links remain placeholders by design.

Next:

- Choose the final public GitHub owner/repo, replace placeholder install URLs, then capture terminal GIF/screenshots from `zmem launch-proof` and the local console for launch proof assets.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar for another run: turn `.zerker/launch-proof/terminal-transcript.txt` into terminal GIF/screenshots and capture the console against `.zerker/launch-proof/memory.sqlite`.

## 2026-05-29 - Agent-Aware Bootstrap Smoke

Shipped:

- Updated `install.sh` so bootstrap smoke is now agent-aware instead of codex-biased: the installer resolves a `SMOKE_AGENT`, defaults the safe manual-pack flow to `openclaw`, and runs both `zmem agent smoke` and `zmem agent mcp-smoke` against that target.
- Tightened `scripts/release_smoke.py` so release verification now fails if `install.sh` or `examples/first_run.sh` drift from the required bootstrap contract for status output, pack generation, and smoke commands.
- Refreshed README, QUICKSTART, day-1 setup, product status, release checklist, and landing copy so the public install story now documents the agent-aware smoke target and the supported `ZERKER_MEMORY_AGENT=hermes|generic` options.

Verification:

- `bash -n install.sh` -> OK
- `.venv/bin/python -m unittest tests.test_release_smoke` -> 21 tests OK
- `.venv/bin/python -m unittest discover -s tests` -> 163 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed; auto-reexeced under Python 3.10, validated the new bootstrap contract, and completed full release smoke with `install_mode: local-wrappers`

Blockers:

- The shell `python3` in this workspace is still `3.9.6`, so direct `python3 -m zerker_memory doctor` and `status` still intentionally report the Python-version blocker outside the shipped bootstrap/reexec flows.
- Final public GitHub owner/repo is still not chosen, so launch docs and curl install examples still intentionally point at placeholder public URLs.

Next:

- Choose the final public GitHub owner/repo, replace placeholder install URLs, and verify the live raw `install.sh` curl path from a clean shell.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar for a separate run: turn `.zerker/launch-proof/terminal-transcript.txt` into terminal GIF/screenshots and capture the local console proof view against `.zerker/launch-proof/memory.sqlite`.

## 2026-05-28 - Agent-Aware Status Next Steps

Shipped:

- Updated `zmem status --summary-only` so its ready-state next steps now follow the first configured agent artifact it actually finds instead of always assuming Codex.
- Kept the existing readiness ordering intact for incomplete setups: missing workspace files still point at `zmem init`, missing proof still points at `zmem eval`, and missing manual-pack artifacts still point at `zmem agent pack --summary-only` before the agent-specific smoke steps.
- Refreshed README, QUICKSTART, day-1 setup, product status, and landing copy so the launch-facing readiness story now explicitly says manual-target users get manual-target next steps.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 57 tests OK
- `python3 -m zerker_memory status --summary-only --skip-eval` -> printed `zmem agent smoke --agent openclaw` and `zmem agent mcp-smoke --agent openclaw` in this workspace, while still failing the known Python-version doctor gate under shell `python3`
- `python3 -m unittest discover -s tests` -> 163 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- The shell `python3` in this workspace is still `3.9.6`, so direct `python3 -m zerker_memory doctor` and `status` calls still intentionally report the Python-version blocker outside the shipped bootstrap/reexec flows.
- Final public GitHub owner/repo is still not chosen, so launch docs and curl install examples still intentionally point at placeholder public URLs.

Next:

- Choose the final public GitHub owner/repo, replace placeholder install URLs, and verify the live raw `install.sh` curl path from a clean shell.

Delegation/Handoff:

- Delegation was not used in this run. Intended sidecar for a separate run: turn `.zerker/launch-proof/terminal-transcript.txt` into terminal GIF/screenshots and capture the local console proof view against `.zerker/launch-proof/memory.sqlite`.

## 2026-05-28 - Launch Proof Capture Harness

Shipped:

- Added `scripts/launch_proof.sh`, a repeatable proof-asset harness that creates `.zerker/launch-proof/terminal-transcript.txt`, a launch proof README, a governed high-risk deploy receipt, bundle verification, snapshot verification, BT explanation, and BehaviorTree.CPP/Groot2 export artifacts.
- Updated `docs/PUBLIC_LAUNCH_AUDIT.md`, `docs/GITHUB_RELEASE_CHECKLIST.md`, `docs/LAUNCH_PLAN.md`, and README so launch proof capture now has one command: `bash scripts/launch_proof.sh`.
- Generated real local launch proof artifacts under `.zerker/launch-proof/`, including a transcript, bundle JSON, snapshot JSON, BT XML, and BT proof manifest.

Verification:

- `bash -n scripts/launch_proof.sh` -> OK
- `python3 -m unittest tests.test_release_smoke` -> 21 tests OK
- `bash scripts/launch_proof.sh` -> passed; wrote `.zerker/launch-proof/README.md`, verified receipt bundle, verified snapshot, explained BT fallback, exported Groot2 XML/proof manifest, and ended with `Proof ready: yes`
- `python3 -m zerker_memory eval` -> 11/11 passed

Blockers:

- Actual screenshots/GIFs are still not captured as image/video files; the transcript and artifacts are ready for capture.
- Final public GitHub owner/repo is still not chosen, so public install URLs remain placeholders.

Next:

- Choose the final public GitHub owner/repo, replace placeholder install URLs, and verify the live raw `install.sh` curl path from a clean shell.

Delegation/Handoff:

- Sidecar for another run if available: turn `.zerker/launch-proof/terminal-transcript.txt` into terminal GIF/screenshots and capture the local console with `zmem --db .zerker/launch-proof/memory.sqlite ui`.

## 2026-05-28 - Public Launch Audit

Shipped:

- Added `docs/PUBLIC_LAUNCH_AUDIT.md`, a final operator checklist for public repo URL replacement, live raw installer verification, generated-state cleanup, launch screenshots/GIFs, and alpha claim boundaries.
- Updated `docs/GITHUB_RELEASE_CHECKLIST.md` so the GitHub release path now explicitly requires replacing placeholder repo URLs, verifying the live curl installer, and completing the public launch audit.
- Updated `docs/LAUNCH_PLAN.md` so the launch install story leads with `bash install.sh`, the final curl installer URL, and `zmem status --summary-only`.
- Updated `docs/CURRENT_STATE.md` so future automation runs know the next critical path is choosing the final GitHub owner/repo and replacing placeholder install URLs.

Verification:

- `bash -n install.sh` -> OK
- `rg` launch audit pass -> remaining placeholder public URL references are intentional and now tracked in launch-audit/checklist docs until the final GitHub owner/repo is chosen.

Blockers:

- Final public GitHub owner/repo is still not chosen, so `zerker-memory/zerker-memory` and `<owner>/<repo>` remain placeholders by design.

Next:

- Choose the final public GitHub owner/repo, then replace placeholder install URLs and verify the live raw `install.sh` curl path from a clean shell.

Delegation/Handoff:

- Sidecar for another run if available: capture the proof assets listed in `docs/PUBLIC_LAUNCH_AUDIT.md`, especially terminal GIFs for `bash install.sh` and `bash examples/first_run.sh`.

## 2026-05-28 - Doctor Recovery Guidance

Shipped:

- Updated `zerker_memory/doctor.py` so failing Python-version checks now point day-1 users at `bash install.sh` first and, when a supported interpreter is discoverable locally, also print an exact Python 3.10+ `-m venv .venv` fallback command.
- Updated the terminal-first readiness summary so `zmem status --summary-only` also surfaces the same install-first guidance when the doctor blocker payload only reports a bare `python_version` failure.
- Refreshed README, QUICKSTART, day-1 setup, product status, and landing install copy so the documented first-run story matches the new recovery guidance.

Verification:

- `python3 -m unittest tests.test_doctor tests.test_cli_onboarding` -> 62 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory status --summary-only --skip-eval` -> printed `python_version: 3.9.6; Python >=3.10 required; fastest fix: bash install.sh; manual fix: /Users/zzo/.pyenv/versions/3.10.15/bin/python -m venv .venv`
- `python3 -m unittest discover -s tests` -> 162 tests OK

Blockers:

- The shell default `python3` in this workspace is still `3.9.6`, so direct `python3 -m zerker_memory doctor` and `status` still intentionally fail their readiness gate until Zerker runs from a Python 3.10+ interpreter or virtualenv; this slice only made the recovery path explicit in-product.

Next:

- Lock the final public GitHub org/repo URL, verify the live raw `install.sh` path, and replace the remaining placeholder curl/install copy with the final launch surface.

Delegation/Handoff:

- Intended sidecar if delegation is available in a later run: audit launch-facing docs and landing for any remaining placeholder GitHub URLs, alpha-boundary drift, or missing screenshot/GIF proof callouts.

## 2026-05-28 - First-Run Manual Pack Readiness

Shipped:

- Updated `examples/first_run.sh` to generate the manual-agent pack before its final `zmem status --summary-only` snapshot, so the verified first-run path now ends with the handoff artifacts already present.
- Tightened `tests/test_release_smoke.py` so bootstrap script coverage now asserts both `install.sh` and `examples/first_run.sh` include `zmem agent pack --summary-only` as part of the launch contract.
- Refreshed README, QUICKSTART, day-1 setup, product status, landing copy, and current-state docs so the first-run story now explicitly promises `Manual pack ready: yes` at the end of the verified bootstrap flow.

Verification:

- `bash -n examples/first_run.sh` -> OK
- `python3 -m unittest tests.test_release_smoke` -> 21 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `bash examples/first_run.sh` -> passed; printed `Manual agent pack summary` and ended with `Manual pack ready: yes`
- `python3 -m unittest discover -s tests` -> 161 tests OK

Blockers:

- The shell default `python3` in this workspace is still `3.9.6`, so direct `python3 -m zerker_memory status` and `doctor` calls still fail their version gate unless routed through a 3.10+ interpreter or the shipped bootstrap helpers.

Next:

- Lock the final public GitHub org/repo URL, license, and raw `install.sh` URL so the documented curl/bootstrap path can stop pointing at placeholders and become launch-ready.

Delegation/Handoff:

- Sidecar for another run if available: audit landing/docs for any remaining placeholder repo URLs, alpha-boundary wording drift, or screenshot/GIF gaps before public launch.

## 2026-05-28 - Bootstrap Readiness Summary

Shipped:

- Updated `install.sh` and `examples/first_run.sh` so both bootstrap paths now finish by printing `zmem status --summary-only`, putting the terminal-first readiness snapshot directly at the end of the first successful run.
- Updated `scripts/release_smoke.py` so release verification now fails if `bash examples/first_run.sh` stops printing the readiness summary, keeping the day-1 launch surface aligned with the documented contract.
- Refreshed README, QUICKSTART, day-1 setup, product status, and landing copy so the public install story now states that bootstrap flows end on the readiness summary automatically.

Verification:

- `bash -n install.sh` -> OK
- `bash -n examples/first_run.sh` -> OK
- `python3 -m unittest tests.test_release_smoke` -> 21 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `bash examples/first_run.sh` -> passed; ended by printing `Zerker Memory status`
- `python3 scripts/release_smoke.py` -> passed with `install_mode: local-wrappers`; now verifies `examples/first_run.sh` prints the readiness summary
- `python3 -m unittest discover -s tests` -> 161 tests OK
- `bash install.sh` -> passed in local-checkout mode; editable install fell back to local wrappers in this network-restricted sandbox and the script ended by printing `Zerker Memory status`

Blockers:

- The shell `python3` in this workspace is still `3.9.6`, so direct `python3 -m zerker_memory status` or `doctor` calls still fail their version gate unless run through the repo `.venv`, a discovered 3.10+ interpreter, or the bootstrap scripts.

Next:

- Align `examples/first_run.sh` with the install path by generating the manual-agent pack before printing status, so the first-run summary ends with `Manual pack ready: yes` instead of immediately pointing users at `zmem agent pack --summary-only`.

## 2026-05-28 - Terminal Readiness Status

Shipped:

- Added `zmem status` with `--summary` and `--summary-only` so day-1 users can see workspace files, proof counts, latest receipt, doctor blockers, and manual-agent handoff artifacts in one terminal-first readiness view.
- Added the new status command to the local console onboarding flow so the first-run UI now points users at the same compact readiness summary exposed by the CLI.
- Updated README, QUICKSTART, day-1 setup, product status, and landing install/proof copy so the launch-facing command path now includes `zmem status --summary-only`.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 56 tests OK
- `python3 -m unittest tests.test_dashboard` -> 6 tests OK
- `python3 -m zerker_memory status --summary-only --skip-eval` -> printed the new readiness summary and exited non-zero because `doctor` reported `python_version: 3.9.6; Python >=3.10 required`
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m unittest discover -s tests` -> 159 tests OK

Blockers:

- The shell `python3` in this workspace is still `3.9.6`, so `zmem doctor` and `zmem status` intentionally fail their readiness gate until Zerker runs from a Python 3.10+ interpreter or virtualenv.

Next:

- Surface `zmem status --summary-only` automatically at the end of `install.sh` and `examples/first_run.sh` so first-run users see the readiness snapshot without having to know the command first.

## 2026-05-28 - Release Smoke Offline Fallback

Shipped:

- Updated `scripts/release_smoke.py` to use the same install fallback ladder as `install.sh`: try isolated editable install first, retry with `--no-build-isolation`, then create local venv wrapper entrypoints if packaging dependencies still cannot be built or fetched.
- Added focused release-smoke coverage for the fallback decision path and wrapper generation so the restricted-environment behavior is explicit and regression-tested.
- Refreshed README, QUICKSTART, product status, release checklist, landing copy, and orchestration state so the launch-facing install contract now matches the verified restricted-sandbox behavior.

Verification:

- `python3 -m unittest tests.test_release_smoke` -> 19 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> passed in this network-restricted sandbox; isolated editable install failed on `setuptools>=64`, `--no-build-isolation` failed on missing `bdist_wheel`, then local venv wrappers completed the full smoke with `install_mode: local-wrappers`
- `python3 -m unittest discover -s tests` -> 154 tests OK

Blockers:

- Fully packaged fresh-venv editable install still depends on available packaging dependencies; the new smoke no longer blocks launch verification because it falls through to wrapper mode when that path is unavailable.

Next:

- Tighten public launch hygiene next: final GitHub org/repo metadata, release-note polish, and capture-ready proof assets now that both bootstrap and release smoke succeed in restricted environments.

## 2026-05-28 - Curl-Style Bootstrap

Shipped:

- Added root `install.sh` as the one-command bootstrap for clone and curl-style setup.
- The installer creates or updates a checkout, creates `.venv`, installs Zerker Memory, initializes `.zerker/`, runs eval and doctor, generates the manual-agent pack, and runs MCP smoke.
- Kept the default safe for new users: it does not write into Codex or Claude config files unless `ZERKER_MEMORY_AGENT=codex`, `ZERKER_MEMORY_AGENT=claude-code`, or another supported target opts in.
- Updated README, QUICKSTART, day-1 setup, product status, release checklist, and landing copy so the first user-facing install path is `bash install.sh`, with the curl command ready once the public repo URL is live.

Verification:

- `bash install.sh` -> passed in this network-restricted sandbox by falling back from isolated editable install to local venv wrapper entrypoints, then completing init, eval, doctor, manual pack generation, and MCP smoke.
- `bash -n install.sh` -> passed
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 67 tests OK

Next:

- Lock the final public GitHub org/repo URL, then verify the live `curl -fsSL .../install.sh | bash` path from a clean machine or clean temp user directory.

## 2026-05-28 - CI Launch Gate Hardening

Shipped:

- Strengthened `.github/workflows/test.yml` so repo CI no longer stops at unit tests plus eval: it now keeps the Python 3.10-3.12 matrix for `python -m unittest discover -s tests` and `zerker eval`, then adds a dedicated Python 3.10 `release-smoke` job that runs `bash examples/first_run.sh` and `python scripts/release_smoke.py`.
- Updated README, QUICKSTART, product status, and the GitHub release checklist so the documented launch contract now matches the CI gate that exercises it.
- Kept the slice intentionally narrow: no runtime behavior changes, just stronger always-on proof that the published install and release path stays working.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding` -> 67 tests OK
- `bash examples/first_run.sh` -> passed
- `python3 -m unittest discover -s tests` -> 151 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> failed at fresh-venv editable install in this network-restricted sandbox because `pip` could not fetch `setuptools>=64`

Blockers:

- Fresh packaged release smoke still depends on network access for build dependencies in this sandbox, so the end-to-end editable-install step cannot be fully revalidated here despite the script and first-run path passing elsewhere.

Next:

- Continue launch readiness work by tightening public repo/release metadata and capture-ready launch assets now that CI mirrors the documented install and smoke path.

## 2026-05-28 - End-User Day-1 Pack Polish

Shipped:

- Added `--summary` and `--summary-only` to `zmem agent pack`, so the combined OpenClaw/Hermes/generic handoff can now be used as a compact terminal-first onboarding command instead of a large JSON-only response.
- Kept the JSON contract stable for automation while adding text output with pack path, prompt path, verify-all command, per-target config/checklist paths, fallback snippet commands, post-install doctor status, and proof smoke commands.
- Updated README, QUICKSTART, day-1 setup, product status, landing install copy, release smoke, and orchestration state to point day-1 users at `zmem agent pack --summary-only`.
- Corrected landing copy so shipped BT recovery adapters are described as available now, not future work.

Verification:

- `bash examples/first_run.sh` -> passed
- `python3 -m unittest tests.test_cli_onboarding` -> 51 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 16 tests OK
- `python3 -m unittest discover -s tests` -> 151 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m zerker_memory agent pack --summary-only` -> passed
- `curl http://127.0.0.1:8781/` -> served current landing HTML from `landing/index.html`
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including fresh editable install, `zmem` / `zerker-memory` / `zerker` / `zerker-memory-mcp` entrypoints, init, provider doctor, agent installs, manual-target `--summary-only`, manual pack `--summary-only`, MCP smoke, bundle verify, snapshot verify, and `bash examples/first_run.sh`

Next:

- Continue launch repo hygiene and tighten any remaining docs that still feel too dense for a first-time user.

## 2026-05-28 - Manual Agent Pack Handoff

Shipped:

- Added `zmem agent pack`, a one-command manual-target onboarding path that refreshes the OpenClaw, Hermes, and generic MCP exports, rewrites their matching checklist artifacts, and writes a shared `.zerker/agents/manual-agent-pack.md` index for teammate or customer handoff.
- Kept the implementation aligned with the existing install flow by reusing `install_agent_preset`, so the pack output inherits the shipped post-install doctor checks, snippet fallbacks, and prompt/checklist generation instead of introducing a second onboarding path.
- Extended release-smoke coverage and refreshed README, QUICKSTART, day-1 setup, product status, and landing install copy so the new manual-target pack command is documented and exercised as a launch-facing onboarding surface.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 50 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 15 tests OK
- `python3 -m unittest discover -s tests` -> 149 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> reached the fresh-venv packaged install step, then failed in this network-restricted environment because `pip install -e .` could not fetch `setuptools>=64`

Next:

- Consider adding a plain-text `--summary` mode for `zmem agent pack` only if day-1 operators need a terminal-first view of the combined handoff instead of the JSON plus markdown artifact.

## 2026-05-28 - Release Smoke Python Auto-Reexec

Shipped:

- Updated `scripts/release_smoke.py` so the documented `python3 scripts/release_smoke.py` command now auto-reexecs itself with a discovered Python 3.10+ interpreter from `PATH` or `pyenv` when the shell default `python3` is too old.
- Added focused release-smoke unit coverage for direct interpreter checks, `PATH` candidate selection, `pyenv` fallback selection, and the reexec handoff.
- Refreshed README, QUICKSTART, product status, GitHub release checklist, and landing install copy so the launch-facing install/release contract now reflects the self-healing smoke path.

Verification:

- `python3 -m unittest tests.test_release_smoke` -> 14 tests OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 60 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> now passed the Python-version entry gate from shell `python3` and reexeced into the fresh-venv flow, then blocked locally because network-restricted `pip install -e .` could not fetch `setuptools>=64`

Next:

- Consider extracting the shared Python 3.10+ discovery logic into one reusable helper only if another shipped shell or release entrypoint needs the same fallback behavior.

## 2026-05-28 - Self-Contained Manual-Agent Checklist

Shipped:

- Updated the manual-target checklist artifact so `zmem agent install openclaw|hermes|generic` and `zmem agent checklist <preset>` now embed the exact `zerker-memory` MCP server JSON alongside the existing export path, doctor command, prompt path, snippet fallback, and proof smoke steps.
- Kept the existing `zmem agent snippet <preset>` command for copy-paste flows, but removed the need to run another CLI command when a teammate only has the generated markdown handoff and the target UI rejects whole-file JSON import.
- Refreshed README, QUICKSTART, product status, day-1 setup, and landing install copy so the shipped manual-agent contract now promises a fully self-contained checklist artifact.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 56 tests OK

Next:

- Consider adding the same self-contained snippet handoff to the local console onboarding only if real users still miss the manual-agent path after reading the checklist.

## 2026-05-28 - Default Manual-Agent Guide Flow

Shipped:

- Updated the manual-target onboarding helpers so `zmem agent guide openclaw|hermes|generic` now mirrors the shortest shipped path instead of teaching the older explicit `--config-path` flow for the default `.zerker/agents/*` export.
- Manual import guidance now prefers `zmem agent install <preset>` plus `zmem doctor --agent <preset>` when the default export path is in use, while still falling back to `--config-path` and `--agent-config` when a custom file location is requested.
- Refreshed README and day-1 setup docs so the human-facing install contract stays aligned with the simpler default manual-target flow.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 46 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 10 tests OK

Next:

- Consider exposing the generated manual-target guide as a standalone markdown artifact only if real users need a shareable handoff file beyond the install summary and checklist.

## 2026-05-28 - Agent Install Post-Install Doctor

Shipped:

- Added a post-install `doctor` block to `zmem agent install <preset>` so Codex, Claude Code, OpenClaw, Hermes, and generic installs now verify the written config plus `.zerker/AGENT_PROMPT.md` in the same command.
- Extended the human-readable `--summary` and `--summary-only` install output to print the immediate doctor result, so terminal-first users get a one-command proof signal instead of a follow-up instruction only.
- Updated release smoke, onboarding tests, README, QUICKSTART, product status, day-1 setup, and landing install copy so the documented install contract now matches the shipped one-command verification flow.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 53 tests OK
- `python3 -m unittest discover -s tests` -> 137 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> blocked locally because the default `python3` is 3.9
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged editable install, direct Codex/Claude Code installs, OpenClaw/Hermes/generic default exports, embedded post-install doctor verification for every preset, doctor verification, MCP smoke, proof export, snapshot verify, and `bash examples/first_run.sh`

Next:

- Consider exposing the same embedded post-install verification block on `zmem agent config <preset>` only if scripted exporters need a proof signal without performing an install.

## 2026-05-28 - Text-Only Manual Install Summary

Shipped:

- Added `--summary-only` to `zmem agent install <preset>` so manual-target installs can print the compact operator summary without the trailing JSON payload when a terminal-first user is not scripting the command.
- Kept the existing `--summary` plus `zerker.agent_install.v1` JSON path unchanged for automation while extending CLI and packaged release smoke coverage to verify the new text-only onboarding mode.
- Updated README, QUICKSTART, product status, day-1 setup, and landing install copy so the documented manual-target path now points users at `--summary-only` when they want the shortest copyable day-1 flow.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_release_smoke` -> 51 tests OK
- `python3 -m unittest discover -s tests` -> 135 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged editable install, manual-target `--summary-only` verification for OpenClaw/Hermes/generic, doctor verification, MCP smoke, proof export, snapshot verify, and `bash examples/first_run.sh`

Next:

- Add a `--format json|text` surface for `zmem agent install <preset>` only if more install commands need multiple operator-facing formats beyond the current summary toggles.

## 2026-05-28 - Manual Install Summary Flag

Shipped:

- Added `--summary` to `zmem agent install <preset>` so manual-target installs can print a compact operator view with the config path, checklist path, import step, snippet fallback, doctor command, prompt step, and smoke commands before the JSON payload.
- Kept the existing `zerker.agent_install.v1` JSON contract stable for automation while extending onboarding helpers and packaged release smoke coverage to verify the new human-readable summary path.
- Updated README, QUICKSTART, product status, day-1 setup, and landing install copy so the documented manual-target flow now points users at `zmem agent install openclaw|hermes|generic --summary` when they want a terminal-first setup path.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 40 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 9 tests OK
- `python3 -m unittest discover -s tests` -> 133 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> blocked locally because the default `python3` is older than 3.10
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> blocked in this environment because the fresh-venv `pip install -e .` step could not reach `setuptools>=64` with network access restricted

Next:

- Add a `--summary-only` or `--format text` path for `zmem agent install <preset>` so terminal-first users can skip JSON entirely when they are not scripting the command.

## 2026-05-28 - Inline Manual Install Preview

Shipped:

- Added an `install_preview` block to `zmem agent install openclaw|hermes|generic` so the install JSON now includes the exact import path, doctor command, first import step, snippet fallback, prompt path, and prompt step without requiring users to open the checklist artifact first.
- Extended onboarding coverage and packaged release smoke assertions so the new preview is verified for default manual-target installs, including path normalization across macOS `/var` and `/private/var` temp aliases.
- Updated README, QUICKSTART, day-1 setup, product status, and landing copy so the documented manual-target install flow matches the new inline preview behavior.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 39 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 8 tests OK
- `python3 -m unittest discover -s tests` -> 131 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged install verification for Codex, Claude Code, OpenClaw, Hermes, and generic; inline manual install preview verification; doctor verification; MCP smoke; proof export; snapshot verify; and `bash examples/first_run.sh`

Next:

- Make `zmem agent install <preset>` optionally print a compact human-readable summary for manual-target agents so terminal-first users do not need to parse JSON at all.

## 2026-05-28 - Manual Install Writes Checklist Artifact

Shipped:

- Updated `zmem agent install openclaw|hermes|generic` so the install flow now writes the project-local MCP export and the matching `.zerker/agents/<preset>-checklist.md` day-1 artifact in the same command.
- Added the checklist path and write status to `zerker.agent_install.v1` output so manual-target users immediately see the proof artifact without discovering a second command first.
- Extended onboarding tests, packaged release smoke, README, QUICKSTART, day-1 setup, product status, and landing copy so the documented manual-target install path matches the shipped one-command behavior.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 39 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 8 tests OK
- `python3 -m unittest discover -s tests` -> 131 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged install verification for Codex, Claude Code, OpenClaw, Hermes, and generic; automatic manual-target checklist artifact verification; doctor verification; MCP smoke; proof export; snapshot verify; and `bash examples/first_run.sh`

Next:

- Surface the manual-target checklist contents or first import step inline in `zmem agent install <preset>` output so a user can act without opening the markdown artifact first.

## 2026-05-28 - Manual Agent Checklist Artifact

Shipped:

- Added `zmem agent checklist <preset>` for OpenClaw, Hermes, and generic MCP agents so one command now refreshes the exported config, ensures `.zerker/AGENT_PROMPT.md` exists, and writes a shareable `.zerker/agents/<preset>-checklist.md` artifact.
- The checklist artifact bundles the exact exported config path, prompt path, doctor command, snippet fallback, and proof smoke commands into a day-1 import checklist instead of making manual-target users stitch those steps together from multiple commands.
- Extended `scripts/release_smoke.py` to generate and verify the new checklist artifacts for OpenClaw, Hermes, and generic installs, then updated README, QUICKSTART, day-1 setup, product status, release checklist, and landing install copy to point users at the new one-command path.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 39 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 7 tests OK
- `python3 -m unittest discover -s tests` -> 130 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged manual-agent checklist generation for OpenClaw, Hermes, and generic, plus doctor verification, MCP smoke, proof export, snapshot verify, and `bash examples/first_run.sh`

Next:

- Surface the generated manual-agent checklist path directly in `zmem agent install <preset>` output so manual-target users see the artifact without having to discover the separate checklist command first.

## 2026-05-28 - Generic MCP Install Path Proof

Shipped:

- Fixed the generic MCP preset so `zmem agent config generic`, `zmem agent install generic`, and `zmem agent guide generic` now point users at generic smoke commands instead of incorrectly telling them to use the `codex` agent ID.
- Extended packaged release smoke to install, snippet-check, and doctor-verify the default `.zerker/agents/generic-mcp.json` export alongside Codex, Claude Code, OpenClaw, and Hermes.
- Updated README, QUICKSTART, day-1 setup, product status, and landing install copy so the generic MCP client path is documented as a first-class manual-target onboarding flow.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 36 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 6 tests OK
- `python3 -m unittest discover -s tests` -> 126 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including default generic `.zerker/agents/generic-mcp.json` install, snippet validation, doctor verification, packaged MCP smoke, proof export, snapshot verify, and `bash examples/first_run.sh`

Next:

- Add a one-command proof bundle for manual-target agents that combines exported config path, prompt path, doctor command, and snippet fallback into a single copyable day-1 checklist artifact.

## 2026-05-28 - Default Manual Agent Export Paths

Shipped:

- Added stable project-local default export targets for manual-target agent installs: `zmem agent install openclaw`, `zmem agent install hermes`, and `zmem agent install generic` now write under `.zerker/agents/` without requiring `--config-path`.
- Expanded `zmem doctor --agent <preset>` to cover OpenClaw, Hermes, and generic exported configs so day-1 verification no longer requires an explicit `PRESET=PATH` for the default flow.
- Updated packaged release smoke, README, QUICKSTART, day-1 setup, product status, landing copy, and CLI help so the documented manual-target path matches the shipped default install behavior.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 35 tests OK
- `python3 -m unittest tests.test_doctor` -> 5 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 6 tests OK
- `python3 -m unittest discover -s tests` -> 125 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including default OpenClaw/Hermes `.zerker/agents/*` installs, agent doctor verification, packaged MCP smoke, proof export, snapshot verify, and `bash examples/first_run.sh`

Next:

- Add a packaged proof-of-import helper only if a real manual-target UI still needs a more constrained paste or file shape than the default `.zerker/agents/*` exports and `agent snippet` already provide.

## 2026-05-27 - Agent Guide Command

## 2026-05-28 - Single-Server Agent Snippet

Shipped:

- Added `zmem agent snippet <preset>` to print only the `zerker-memory` MCP server object for copy-paste into manual-target agent UIs.
- Updated manual-target onboarding guidance so OpenClaw and Hermes users can paste a single server entry when whole-file JSON import is rejected.
- Extended packaged release smoke to verify the new snippet command for manual-target presets.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 34 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 6 tests OK
- `python3 -m unittest discover -s tests` -> 123 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including manual-target snippet checks, packaged agent installs, doctor verification, MCP smoke, proof export, snapshot verify, and `bash examples/first_run.sh`

Next:

- Add an `--format toml/json` export mode only if a real target agent requires a different single-server shape.

Shipped:

- Added `zmem agent guide <preset>` to print a human-readable install, import, verification, prompt, and smoke path for each supported agent preset.
- Reused the existing preset/install/manual-import metadata so Codex and Claude Code show direct-install guidance while OpenClaw, Hermes, and generic MCP agents show the exact export-and-import path.
- Updated README, quickstart, day-1 setup, product status, and landing install copy so users can discover the guide before editing agent configs by hand.

Verification:

- `python3 -m unittest tests.test_cli_onboarding` -> 32 tests OK
- `python3 -m unittest discover -s tests` -> 120 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed

Next:

- Add a copy-paste helper that writes the single `mcpServers.zerker-memory` block for manual-target UIs that reject whole-file JSON imports.

Shipped:

- Added preset-specific `manual_import` guidance to `zmem agent config <preset>` and `zmem agent install <preset>` for OpenClaw, Hermes, and generic MCP agents.
- The CLI install/config payloads now tell users exactly where to import the exported JSON, when to copy only `mcpServers.zerker-memory`, and where `.zerker/AGENT_PROMPT.md` must be attached.
- Updated README, quickstart, day-1 setup, product status, and landing install copy so the docs match the shipped manual-target onboarding path.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_doctor` -> 33 tests OK
- `python3 -m unittest tests.test_release_smoke` -> 5 tests OK
- `python3 -m unittest discover -s tests` -> 117 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged OpenClaw/Hermes install exports, doctor verification, MCP smoke, bundle/snapshot proof, and `bash examples/first_run.sh`

Next:

- Add a human-readable `zmem agent` guide surface for manual-target presets so users do not have to inspect JSON output to see the import steps.

## 2026-05-27 - Manual Agent Config Doctor Verification

Shipped:

- Added `zmem doctor --agent-config <preset>=<path>` so OpenClaw, Hermes, generic MCP agents, and other manual-target installs can be verified without assuming a stable default config location.
- Kept the existing direct-install doctor flow for Codex and Claude Code, while extending the same `.zerker/AGENT_PROMPT.md` plus MCP-server verification story to exported JSON config files.
- Extended onboarding and doctor tests for the new CLI flag, explicit OpenClaw install path, and manual-config verification.
- Extended `scripts/release_smoke.py` to install OpenClaw and Hermes presets into temporary config files and verify them through the new doctor path.
- Updated README, quickstart, day-1 setup, product status, release checklist, and landing install flows to show the manual-target verification command.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_doctor tests.test_release_smoke` -> 37 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m unittest discover -s tests` -> 116 tests OK
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged OpenClaw/Hermes install exports plus `zmem doctor --agent-config ...` verification

Next:

- Add copy-ready import instructions per manual-target preset so OpenClaw and Hermes users can move from exported config JSON into their real tool UIs with less guesswork.

## 2026-05-27 - Agent Install Doctor Checks

Shipped:

- Added optional `zmem doctor --agent <preset>` verification for the supported direct-install targets: Codex and Claude Code.
- The doctor path now proves both that `.zerker/AGENT_PROMPT.md` exists in the project and that the real local agent config contains the `zerker-memory` MCP server block.
- Extended onboarding and doctor tests for the new CLI flags and agent-install verification cases.
- Updated `scripts/release_smoke.py` so the packaged smoke now verifies the new agent-install doctor path against default home-based Codex and Claude Code config targets as well as explicit temp targets.
- Updated README, quickstart, day-1 setup, product status, and landing install flows to show the post-install verification command.

Verification:

- `python3 -m unittest tests.test_cli_onboarding tests.test_doctor` -> 29 tests OK
- `python3 -m unittest tests.test_cli_onboarding tests.test_doctor tests.test_release_smoke` -> 34 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 -m unittest discover -s tests` -> 113 tests OK
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged doctor agent verification, packaged MCP smoke, and `bash examples/first_run.sh`

Next:

- Add a day-1 install verification path for manual-preset agents like OpenClaw and Hermes without requiring a stable default config location.

## 2026-05-27 - Direct Agent Install

Shipped:

- Added `zmem agent install <preset>` so day-1 users can install Zerker Memory directly into real local agent config files instead of manually copying JSON.
- Added default install targets for Codex (`~/.codex/config.toml`) and Claude Code (`~/.claude/mcp.json`) while keeping OpenClaw, Hermes, and generic presets on the explicit config-generation path.
- Made the install flow write `.zerker/AGENT_PROMPT.md` if needed, use absolute project-local DB/policy paths in installed MCP commands, and stay non-destructive unless `--force` is used.
- Extended `scripts/release_smoke.py` to verify packaged `zmem agent install codex` and `zmem agent install claude-code` against temporary config targets.
- Updated README, quickstart, day-1 setup, product status, release checklist, and landing install copy to point users at the new direct install path.

Verification:

- `python3 -m unittest tests.test_cli_onboarding`
- `python3 -m unittest tests.test_release_smoke`
- `python3 -m unittest discover -s tests` -> 109 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including packaged agent install checks and `bash examples/first_run.sh`
- Shell `python3` in this workspace is `Python 3.9.6`, so release smoke was run with Python 3.10.15 as required

Next:

- Add direct install targets or explicit patch guidance for OpenClaw and Hermes once their stable local config file paths are locked.

## 2026-05-27 - Verified First-Run Script

Shipped:

- Updated `examples/first_run.sh` to match the shipped day-1 flow: init with policy/prompt/MCP/provider config, run eval and doctor, prove `zmem agent smoke`, prove `zmem agent mcp-smoke`, then run a governed high-risk command.
- Made the first-run script resilient from a fresh checkout by resolving the repo root explicitly and choosing a Python 3.10+ interpreter, including common `pyenv` installs when `zmem` is not already on `PATH`.
- Extended `scripts/release_smoke.py` to run `bash examples/first_run.sh` after the packaged install so the documented install path is now part of release verification.
- Updated README, quickstart, day-1 setup, product status, release checklist, and landing install copy to point users at the verified first-run script.

Verification:

- `python3 -m unittest tests.test_release_smoke tests.test_cli_onboarding`
- `bash examples/first_run.sh`
- `python3 -m unittest discover -s tests` -> 103 tests OK
- `python3 -m zerker_memory eval` -> 11/11 passed
- `python3 scripts/release_smoke.py` -> failed as expected on shell `python3` 3.9 (`Python >=3.10 required for release smoke`)
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py` -> passed, including the packaged first-run script

Next:

- Add optional agent install helpers for real config-file targets once the public docs lock the exact Codex/Claude/OpenClaw destination paths.

## 2026-05-27 - MCP Stdio Smoke

Shipped:

- Added a real packaged MCP smoke flow to `scripts/release_smoke.py`.
- The packaged smoke now verifies stdio `initialize`, `tools/list`, `memory.remember`, `memory.inject`, `memory.why`, and `memory.verify` against the installed `zerker-memory-mcp` entrypoint.
- Added `zmem agent mcp-smoke` so users can run the same kind of protocol proof from a normal checkout.
- Added unit coverage for the stdio MCP smoke helper so local test runs exercise the same handshake without needing the release venv.
- Updated product status, day-1 setup, quickstart, release checklist, README, and landing install copy to include the MCP proof path.

Verification:

- `python3 -W error::ResourceWarning -m unittest tests.test_mcp tests.test_cli_onboarding`
- `python3 -m unittest tests.test_release_smoke tests.test_mcp`
- `python3 -m unittest discover -s tests`
- `python3 -m zerker_memory eval`
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py`

Next:

- Add generated config file targets for common local paths once the public repo docs choose exact Codex/Claude/OpenClaw config locations.

## 2026-05-27 - Agent Presets And Day-1 Smoke

Shipped:

- Added `zmem agent config <preset>` for Codex, Claude Code, OpenClaw, Hermes, and generic MCP agents.
- Added `zmem agent prompt` so users can print or write the durable-memory instruction prompt.
- Added `zmem agent smoke` to create a verifiable local memory decision for day-1 setup.
- Added release-smoke coverage for agent config generation and agent smoke.
- Updated README, quickstart, day-1 setup, product status, and release checklist docs.

Verification:

- `python3 -m unittest tests.test_cli_onboarding`
- `python3 -m unittest tests.test_release_smoke`
- `python3 -m unittest discover -s tests`
- `python3 -m zerker_memory eval`
- `/Users/zzo/.pyenv/versions/3.10.15/bin/python scripts/release_smoke.py`

Next:

- Add a true MCP protocol smoke that calls `memory.inject` over stdio.

## 2026-05-27 - BT Proof Export

Shipped:

- Added `zmem bt export <trace-id>` to emit a BehaviorTree.CPP/Groot2-ready XML artifact from governed BT traces.
- Added a JSON proof manifest sidecar with event hashes, explanation metadata, and exported node model details.
- Extended the eval harness, BT tests, and CLI parser coverage for the new BT export path.
- Updated README, product-status, and launch-plan docs to include the BT export command in the proof story.

Verification:

- `python3 -m unittest tests.test_bt tests.test_cli_onboarding tests.test_eval`
- `python3 -m unittest discover -s tests`
- `python3 -m zerker_memory eval`

Next:

- Capture a real Groot2/BehaviorTree.CPP demo asset and add it to the launch checklist.

## 2026-05-27 - BTPG Recovery Adapter

Shipped:

- Added a dependency-free BTPG transition normalizer for governed BT trace ingest.
- Added `BtMemory.ingest_btpg_transitions(...)` so planner-style recovery traces can enter the same explanation path as raw JSONL and `py_trees`.
- Extended the eval harness and BT unit tests to cover BTPG fallback and recovery transitions.

Verification:

- `python3 -m unittest tests.test_bt tests.test_eval`
- `python3 -m unittest discover -s tests`
- `python3 -m zerker_memory eval`

Next:

- Add BehaviorTree.CPP/Groot2 export so the BT proof path can move beyond local traces.

## 2026-05-27 - Launch Proof UX

Shipped:

- Refined the local console onboarding and proof inspector around a screenshot-ready launch proof path.
- Added a deploy-demo preset in `zmem ui` so launch flows can quickly generate a governed high-risk receipt.
- Refreshed the landing page with a dedicated proof-path section and GIF-ready command path.
- Updated product status and launch-plan docs to point launch assets at the new eval -> console -> bundle story.

Verification:

- `python3 -m unittest tests.test_dashboard`
- Browser-style static inspection of the updated landing and console markup

Next:

- Capture real launch assets from the proof path and add them to the repo/release checklist.

## 2026-05-27 - Day-1 Agent Launch Path

Shipped:

- Added day-1 setup guidance for MCP-capable agents, shell-based agents, persistent chat windows, existing memory providers, and proof export.
- Added shared/swarm memory guidance for shared local databases, shared review queues, snapshot handoff, and receipt bundle handoff.
- Updated README links to point users at the day-1 setup and shared-memory docs.
- Updated landing copy to name Codex, Claude Code, OpenClaw, Hermes, and other agent workflows.
- Fixed landing install code blocks so they do not overflow at narrower desktop widths.

Verification:

- `python3 -m zerker_memory eval` passed 9/9.
- Browser check confirmed landing install section shows the updated command path and no horizontal page overflow.

Next:

- Generate per-agent config presets instead of asking users to translate MCP docs by hand.
- Add a day-1 MCP integration smoke test.

## 2026-05-27 - Provider Live Smoke And Launch Readiness

Shipped:

- Expanded provider support around Mem0 and Zep.
- Added `zmem provider doctor --live` provider selection with repeated `--provider` flags.
- Added per-provider live overrides for base URL, API key, query, and user id.
- Added release-smoke support for `ZERKER_PROVIDER_LIVE_PROVIDERS`, so launch demos can probe only the intended provider adapters.
- Updated provider, release-smoke, onboarding, product-status, launch-plan, and README coverage.

Verification:

- `python3 -m unittest discover -s tests` passed 92 tests.
- `python3 -m zerker_memory eval` passed 9/9.

Next:

- Add hosted CI coverage for optional provider smoke using local mock services.
- Add Zep/Graphiti import examples to docs once the endpoint shape is proven against a real instance.

## 2026-05-27 - Release-Ready Python Alpha

Shipped:

- Consolidated packaging on `pyproject.toml`.
- Kept a minimal `setup.py` shim for compatibility.
- Removed split metadata from `setup.cfg`.
- Added `scripts/release_smoke.py` for fresh-venv install and CLI proof.
- Verified entrypoints: `zmem`, `zerker-memory`, `zerker`, `zerker-memory-mcp`.
- Verified init files, eval, provider doctor, demo, bundle verification, and snapshot verification from a fresh editable install.

Verification:

- `python3 -m unittest discover -s tests` passed.
- `python3 -m zerker_memory eval` passed.
- Python 3.10 fresh-venv strict release smoke passed.

Next:

- Publish package metadata/repo URL once the public GitHub repo exists.
- Add CI workflow around the release smoke.

## 2026-05-26 - Functional Local-First Memory Alpha

Shipped:

- Local SQLite memory store.
- CLI and MCP server.
- Local console.
- Typed memories: episodic, semantic, procedural, policy.
- Trust, authority, status, source, labels, and scope.
- Quarantine, queue, promote, reject.
- Lineage and descendant revocation.
- Symbolic policy gate before injection.
- Merkle event log.
- Action receipts, `why`, and receipt verification.
- Receipt bundles and bundle verification.
- Full-state snapshots, snapshot verification, and restore.
- Treeship-ready proof export and publish handoff.
- Provider governance scaffold with Mem0 import path.
- Behavior-tree recovery memory with trace ingest and fallback explanation.
- py_trees transition normalization helper.
- Static landing page.

Verification:

- Built-in eval passed.
- Unit tests passed for the covered slices.

Next:

- Make agent setup and launch onboarding obvious enough for a new user to succeed without a walkthrough.
