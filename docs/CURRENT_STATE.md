# Current State

This is the short orchestration dashboard for Zerker Memory. Every autonomous build run should update this file after it updates `docs/BUILD_LOG.md`.

## Latest Shipped

`2026-06-05 - Capture Checklist Now Carries The Full Handback Contract`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was right now: the generated `CAPTURE_CHECKLIST.md` was still the weakest forwarded Phase-1 asset surface because it named the storyboard but did not fully carry the pre-asset verify gate, durable fallback docs, or the finalize-and-receive-side acceptance contract on one screen.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so generated `.zerker/launch-proof/CAPTURE_CHECKLIST.md` now includes an explicit `Asset Pass Gate` section, the durable Phase-1 fallback doc set, the `verify-public-verify` prerequisite, the rerun-`FINALIZE_RETURN_PACKET.sh` handback step, and the `verify-return-packet` receive-side acceptance rule.
- Tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the generated capture checklist now fails fast if those standalone handoff cues disappear from future Phase-1 packets.

`2026-06-05 - Status Summary Separates Release Packet Readiness From Publish Readiness`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was right now: `zmem status --summary-only` is still the first Phase-1 handoff surface, and it was incorrectly leading with `Release proof ready: yes` even while that same screen still showed `Public verify: pending`, `Launch assets: pending`, and `Strict publish gate: blocked`.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the top status summary now says `Release packet ready` for the generated local handoff bundle state and separately says `Strict publish ready` for the actual Phase-1 external-proof gate, instead of conflating the two under the older `Release proof ready` label.
- Tightened focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and synced [`docs/LAUNCH_READINESS_NOW.md`](docs/LAUNCH_READINESS_NOW.md) so the new status wording stays aligned with the shipped launch-gate semantics.

`2026-06-05 - Public Verify Summary Restored Operator-Packet Preflight Step`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was right now: the local audit initially looked clean, but `python3 scripts/release_smoke.py --summary-only` exposed a real Phase-1 regression where generated `.zerker/launch-proof/public-verify-summary.md` still omitted the operator-packet preflight command from its command-log map even though the shipped verifier and runbook now require that sixth proof log.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `render_public_verify_result_summary()` now renders its command-log map from the shared `PUBLIC_VERIFY_LOG_SPECS` contract instead of a stale hard-coded five-step list, which restores the missing `verify-operator-packet -> operator-packet-verify.log` step in generated `public-verify-summary.md`.
- Tightened the run handoff in [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) and [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) so the next automation run starts from the fixed Phase-1 contract rather than the earlier wording-audit detour.

`2026-06-05 - Phase-1 Live Contract Audit Closed With No Remaining Non-Historical Drift`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was right now: after the `6/6` log contract shipped, the highest-leverage local-adjacent move was to verify whether any live launch-facing repo surfaces still referenced the old `5/5` or five-command wording before another automation run spent time re-auditing the same question.
- Audited the live repo surfaces with `rg` across `README.md`, `QUICKSTART.md`, `docs/`, `landing/`, `zerker_memory/`, `tests/`, `scripts/`, and `install.sh`, excluding historical run logs; no remaining non-historical `five-log`, `five-command`, `0/5`, or `5/5` references were found outside historical notes in [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) and prior shipped-entry prose in this dashboard.
- Updated this dashboard plus [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) to record that the local launch contract audit is complete, so the next offline run can move directly to a new adjacent Phase-1 artifact instead of repeating the same wording audit.

`2026-06-05 - Public Verify Contract Requires Operator-Packet Preflight Log`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing six clean-shell proof logs and eight launch assets. Why this slice was right now: the generated clean-shell script already wrote `operator-packet-verify.log`, but the shipped receive-side contract, terminal summaries, and launch docs still described only five required logs, which weakened the handback audit for the one external proof loop that still blocks Phase 1.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the shipped public-verify contract now requires `operator-packet-verify.log` everywhere that matters: the manifest-backed expected log list, command-log map, `verify-public-verify` completion rule, return-packet handback copy, and generated fallback docs/prompts.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so summary-contract coverage, receive-side verification samples, and pending/ready log-count assertions now fail if the repo drops back to the older `5/5` proof bar.

`2026-06-05 - Public Repo Target Normalized To zerker-memory`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was right now: the automation brief and recent handoff notes had already converged on `zerkerlabs/zerker-memory`, but the shipped installer default, release CLI summaries, tests, and several launch docs still pointed at `zerkerlabs/zmem`, which made the Phase-1 clean-shell proof target ambiguous.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py), [`install.sh`](install.sh), [`scripts/release_smoke.py`](scripts/release_smoke.py), [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`landing/index.html`](landing/index.html), and the active launch docs so the public GitHub repo target and raw installer URL now consistently point to `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` while keeping the product and CLI name `zmem`.
- Tightened [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) around the same public target so the Phase-1 proof surfaces, generated manifests, and installer contract now fail fast if they drift back to the old repo URL.

`2026-06-05 - Generated Launch-Proof Artifacts Carry Durable Phase-1 Fallbacks`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was right now: the terminal-first surfaces were already aligned, but another chat could still lose the durable repo-level fallback path when it only received generated `.zerker/launch-proof/` artifacts.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem launch-proof --summary-only`, the generated launch-proof HTML report, and the generated `LAUNCH_ASSET_HANDOFF.md`, `PUBLIC_VERIFY_HANDOFF.md`, and `RECEIVE_VERIFY_HANDOFF.md` now all repeat the durable fallback set: [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md), [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md), [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md), and [`docs/LAUNCH_ASSET_BOARD.html`](docs/LAUNCH_ASSET_BOARD.html).
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the launch-proof summary contract and generated-artifact coverage now fail if those durable fallback references disappear from the forwarded proof surfaces.

`2026-06-05 - Durable Phase-1 Fallbacks Surfaced In Terminal Summaries`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was right now: the repo already had durable Phase-1 fallback docs, but the main terminal/operator surfaces still mostly assumed another chat would open packet-local `.zerker/launch-proof/` files first.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem status --summary-only`, `zmem release-pack --summary-only`, `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, and prelaunch/status next-step guidance now surface the durable repo-level fallback set: [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md), [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md), [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md), and [`docs/LAUNCH_ASSET_BOARD.html`](docs/LAUNCH_ASSET_BOARD.html).
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and synced [`docs/GITHUB_RELEASE_CHECKLIST.md`](docs/GITHUB_RELEASE_CHECKLIST.md) so the durable fallback doc set is now part of the enforced Phase-1 summary contract instead of living only in prose docs.

`2026-06-05 - Durable Phase-1 External Operator Brief`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was right now: the local packet, verifier, runbook, prompt, compact summary, and asset-board surfaces were already aligned, but there was still no single pinned repo doc another chat could use end-to-end for send, run, capture, and receive-side acceptance.
- Added durable [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md) so the repo now has one orchestrator-facing Phase-1 handoff doc that combines repo-local preflight, the forward-together triplet, clean-shell proof steps, the five-log contract, the eight-asset pass, finalize/return-packet acceptance, and stop conditions.
- Synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the main launch-facing surfaces now point at that single durable brief before falling back to the narrower runbook, prompt, and asset brief.

`2026-06-05 - Durable Launch Asset Operator Prompt`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was right now: the clean-shell public-verify loop already had durable repo-level fallback docs, but the screenshot/GIF pass still depended too heavily on generated `.zerker/launch-proof/` artifacts when another chat needed a stable asset-capture brief.
- Added durable [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](docs/LAUNCH_ASSET_OPERATOR_PROMPT.md) so the repo now has one copy-ready Phase-1 screenshot/GIF brief that mirrors the shipped eight-asset storyboard, save paths, verification bar, finalize step, and receive-side acceptance command.
- Synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`docs/PUBLIC_LAUNCH_AUDIT.md`](docs/PUBLIC_LAUNCH_AUDIT.md) so the main launch-facing surfaces now point at that durable asset-capture fallback alongside the existing clean-shell runbook and operator prompt.

`2026-06-05 - Status Summary Separates Memory Proof From Release Proof`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing five clean-shell proof logs and eight launch assets. Why this slice was right now: `zmem status --summary-only` is still the first day-1 and release-orchestration surface, and it was incorrectly showing `Proof ready: yes` even when the release proof path was still missing and the alpha gate was blocked.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the status summary now says `Memory proof ready` for the local receipt/eval surface and separately says `Release proof ready` for the launch-proof packet state, without changing the existing release readiness logic or next-step contract.
- Tightened [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the status-summary renderer now fails fast if those labels drift and start conflating the two proof surfaces again.

`2026-06-05 - Release Pack Summary Carries Full Phase-1 Brief`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: `zmem release-pack --summary-only` is the shortest repo-local Phase-1 refresh and the documented starting point, but it still stopped short of the full clean-shell command-log contract and launch-asset cue map that the verifier surfaces already carried.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only` now also prints the packet-local runbook line, required `packaged` install mode, the exact five-command clean-shell log contract, `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, and the full eight-shot command/capture cue map inline.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so Phase-1 smoke now fails if the release-pack summary loses that one-screen operator brief, and synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) to describe the stronger release-pack surface.

`2026-06-05 - Operator Surfaces Carry Asset Cue Map`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the launch-asset verifier already had the full eight-shot cue map, but the two main forwarded/operator surfaces still made another chat bounce back out to the checklist or board before running the screenshot/GIF pass.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, and generated `.zerker/launch-proof/public-verify-summary.md` now all print the launch-asset board path plus the full eight-shot command/capture cue map inline beside the clean-shell command-log contract.
- Tightened [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) around those operator surfaces and synced [`README.md`](README.md) so the local Phase-1 docs now describe the stronger one-screen handoff surface.

`2026-06-04 - Hydration Boundary Captured For Orientation`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets, but this run was blocked earlier because several required orientation inputs remain macOS `compressed,dataless` placeholders in the local workspace.
- Confirmed the exact local boundary instead of guessing through it: `README.md`, `QUICKSTART.md`, `docs/BUILD_LOG.md`, `docs/PRODUCT_STATUS.md`, `docs/DAY1_AGENT_SETUP.md`, `tests/test_release_smoke.py`, and `zerker_memory/cli.py` are still `compressed,dataless`, while `docs/CURRENT_STATE.md` remained readable enough to recover the last shipped Phase-1 baseline.
- Updated [`docs/REPO_HYDRATION_BLOCKER_2026-06-04.md`](docs/REPO_HYDRATION_BLOCKER_2026-06-04.md) with the new status boundary: `python3 -m zerker_memory eval` still passes here, but a fresh `python3 -m zerker_memory status --summary-only` did not return promptly during orientation under the same partially hydrated workspace.

`2026-06-04 - Durable Launch Asset Audit Exactness`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the generated packet already carried the exact eight-asset storyboard, but the durable repo-level launch audit still reduced that blocker to generic proof categories and could mis-brief another chat when `.zerker/launch-proof/` was stale or unavailable.
- Updated [`docs/PUBLIC_LAUNCH_AUDIT.md`](docs/PUBLIC_LAUNCH_AUDIT.md) so the durable launch checklist now mirrors the exact Phase-1 asset contract: all eight required deliverables, the command and capture cue for each asset, and the receive-side acceptance bar of `verify-public-verify`, `verify-launch-assets`, finalize, and `verify-return-packet`.
- Updated [`landing/index.html`](landing/index.html) so the public proof-path section now states the real Phase-1 completion contract and includes `zmem verify-launch-assets --summary-only` in the GIF-ready command path.

`2026-06-04 - Clean-Shell Bootstrap Contract Clarified`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the packet, verifier, and runbook surfaces were already aligned locally, but the last high-risk local ambiguity was whether the operator should treat the first raw install as the recorded proof step instead of the bootstrap needed to create the clean repo path before restoring the packet.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the operator-packet verifier, public-verify verifier, `public-verify-summary.md`, fallback clean-shell runbook/prompt, generated script banner, and public-verify handoff now all explicitly say: bootstrap once to create the repo path, then let `PUBLIC_VERIFY_COMMANDS.sh` rerun the raw installer and record `public-verify-logs/curl-install.log`.
- Synced the durable repo docs [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) and [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md), and tightened [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so this contract now fails fast if it drifts off the generated packet surfaces again.

`2026-06-04 - Compact Summary Outbound Verify Cue`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the compact `public-verify-summary.md` artifact was already a likely forwarded handoff surface, but it still skipped the repo-local outbound archive verification step and could let another chat forward the bundle without rerunning the last local gate first.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so generated `.zerker/launch-proof/public-verify-summary.md` now explicitly tells the orchestrator to run `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` before forwarding the clean-shell bundle.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) so the compact summary contract now fails fast if that outbound verification cue disappears again.

`2026-06-04 - Public Launch Audit Strictness Sync`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the shipped CLI, packet, and verifier surfaces already enforced the strict packaged-install send/receive contract, but the durable repo-level `docs/PUBLIC_LAUNCH_AUDIT.md` still described the older placeholder-tolerant publish flow and could send another chat through the wrong launch checklist.
- Updated [`docs/PUBLIC_LAUNCH_AUDIT.md`](docs/PUBLIC_LAUNCH_AUDIT.md) so the final launch audit now matches the shipped Phase-1 contract: repo-local `verify-operator-packet` before handoff, clean-shell `--require-install-mode packaged`, receive-side `verify-public-verify` / `verify-launch-assets` / `verify-return-packet`, plain `zmem prelaunch` before tagging, and the exact outbound triplet to hand to the clean-shell operator.

`2026-06-04 - Packaged Verify Mode Alignment`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the shipped clean-shell contract already allowed the `venv-pth` packaged-install fallback in `scripts/release_smoke.py`, but the receive-side CLI verification path still rejected that same mode and could falsely fail a legitimate returned proof packet.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the Phase-1 verifier contract now treats `venv-pth` as satisfying the `packaged` install requirement, matching the existing release-smoke fallback contract instead of rejecting valid clean-shell proof.
- Added focused regression coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) proving both `zmem verify-public-verify --summary-only` and `zmem verify-return-packet --summary-only` accept a passing `venv-pth` receipt under the packaged requirement.

`2026-06-04 - Atomic Packet Archive Writes`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: a real local handoff race still remained, because overlapping `zmem release-pack --summary-only` and `zmem verify-operator-packet --summary-only` reads could catch the operator packet or return packet tarball mid-write and report a false `archive invalid`.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the operator-packet and return-packet tarballs are now written to temp files and atomically replaced only after the full archive finishes, which keeps parallel verifier/status/read paths from seeing half-written packet archives.
- Added focused regression coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) proving failed packet rewrites preserve the last good archive instead of corrupting the clean-shell handoff surface.

`2026-06-04 - Launch Asset Verifier Cue Map`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the operator-packet and public-verify verifier surfaces were already terminal-first, but `zmem verify-launch-assets --summary-only` still made another chat open the checklist or launch-asset board to recover the exact per-shot command and capture cue.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-launch-assets --summary-only` now prints the full per-shot cue map inline for every required launch asset: deliverable filename, capture ID, source command, capture cue, and output path, while keeping the finalize-before-handback step on the same screen.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and refreshed [`tests/test_release_smoke.py`](tests/test_release_smoke.py) plus [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), then synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs and release preflight now describe the stronger asset-verifier surface consistently.

`2026-06-03 - Verifier Command Log Map Surfacing`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the generated packet, checklist, and compact summary already carried the five-command proof contract, but the two terminal-first verifier surfaces another chat is most likely to run before and after handoff still required bouncing back into markdown to recover the exact command-to-log map.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-operator-packet --summary-only` and `zmem verify-public-verify --summary-only` now print the full five-command clean-shell command-log map inline, including the expected saved log path and success cue for each command.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and refreshed [`tests/test_release_smoke.py`](tests/test_release_smoke.py), then synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the Phase-1 verifier surfaces and launch-facing docs now describe the same terminal-first handoff contract.

`2026-06-03 - Public Verify Summary Log Map`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the clean-shell runbook and checklist already carried the exact five-command log contract, but the compact `public-verify-summary.md` artifact that another chat is most likely to forward on its own still did not restate that map.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the generated `.zerker/launch-proof/public-verify-summary.md` now includes the exact five-command clean-shell command-to-log map plus the existing success confirmations for `curl-install.log`, `first-run.log`, `release-pack.log`, `packaged-release-smoke.log`, and `prelaunch.log`.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py) and refreshed [`tests/test_release_smoke.py`](tests/test_release_smoke.py) so the Phase-1 preflight now fails if that compact summary loses the command-log contract again.

`2026-06-03 - Launch Asset Capture Board`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the Phase-1 checklist and verifier contract were already explicit, but the screenshot/GIF pass still made another chat bounce between the checklist, proof report, transcript, and handoff files instead of capturing from one stable reference surface.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem launch-proof` and `zmem release-pack --summary-only` now generate `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html`, ship it inside the operator packet, thread it through the manifest and report, and surface it from `zmem verify-launch-assets --summary-only` as the capture-ready board for the still-missing screenshots/GIFs.
- Tightened [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), then synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs now point operators at the new board instead of only the markdown checklist.

`2026-06-03 - Release Smoke Refreshed Status Pass`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the Phase-1 packet and verifier surfaces were already aligned, but `python3 scripts/release_smoke.py --summary-only` still opened with a stale pre-refresh `status` snapshot instead of finishing on the refreshed operator packet state that another chat should actually use for handoff.
- Updated [`scripts/release_smoke.py`](scripts/release_smoke.py) so the summary-only preflight now reruns `python3 -m zerker_memory status --summary-only` immediately after `release-pack --summary-only`, which leaves the terminal on the current launch-proof/operator-packet state before the verifier sequence continues.
- Added focused regression coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs now describe the same refreshed-status preflight.

`2026-06-03 - Clean-Shell Command Log Contract`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the repo-local release loop was stable, but the generated clean-shell packet still required another chat to infer which exact command should create which saved proof log and what success cue each log had to show before handback.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so generated `PUBLIC_VERIFY_CHECKLIST.md`, `CAPTURE_CHECKLIST.md`, and the fallback packet-local `CLEAN_SHELL_PUBLIC_VERIFY.md` now all include the exact clean-shell command-to-log map plus per-log success cues for the five required proof logs.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and synced [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](docs/CLEAN_SHELL_PUBLIC_VERIFY.md) so the Phase-1 packet and durable docs now describe the same one-screen log contract.

`2026-06-03 - Release Pack Overlap Lock`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the operator packet, runbook, proof report, and verifier surfaces were already aligned, but the main local operator command, `zmem release-pack --summary-only`, could still crash when overlapping chats refreshed `.zerker/launch-proof/` concurrently.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so launch-proof and release-pack refreshes now serialize through a repo-local `.zerker/launch-proof.lock`, while launch-proof teardown now ignores disappearing-file races instead of crashing mid-refresh.
- Added focused regression coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and revalidated the broader Phase-1 release path so concurrent local refreshes now finish with the expected prelaunch-blocked output rather than tracebacking.

`2026-06-03 - Launch Proof Report Handoff Surface`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the CLI summaries, packet verifier, and handoff docs were already aligned, but the generated `.zerker/launch-proof/index.html` report still did not surface the operator prompt, runbook, and outbound packet triplet together on one proof screen.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the launch-proof HTML report now shows the clean-shell runbook, copy-ready operator prompt, outbound operator packet, and explicit forward-together triplet inside the `Clean-Shell Public Verify` section, while the artifact list now also carries the prompt and packet path directly.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs now match the stronger proof-report handoff surface.

`2026-06-03 - Status And Prelaunch Return-Packet Cue`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the dedicated public-verify and return-packet verifiers already enforced the right handback contract, but the most common operator entry points, `zmem status --summary-only` and `zmem prelaunch --summary-only`, still did not explicitly tell another chat to rerun finalize and confirm receive-side acceptance before handback.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the shared next-step builders for status and prelaunch now end with the explicit Phase-1 handback step: rerun `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`, then confirm `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` is ready before handback.
- Refreshed focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the launch-facing docs now match the stronger status/prelaunch handback wording.

`2026-06-03 - Return Packet Receive-Side Contract`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the outbound packet, runbook, and clean-shell verifier were already explicit, but the receive-side return-packet summary was still too terse for another chat to accept or reject a handback from one screen.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-return-packet --summary-only` now restates the receive-side handoff path, expected logs root, `packaged` install requirement, pinned public targets, finalize-script path, and the rerun-then-finalize contract when a packet is incomplete.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), and [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md) so the launch-facing docs now match the stronger receive-side acceptance surface.

`2026-06-02 - Compact Public Verify Summary Contract`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the repo already had a durable runbook, operator prompt, outbound packet, and receive-side brief, but the compact `public-verify-summary.md` artifact was still the weakest forwarded surface because it did not restate the full outbound and handback contract in one file.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the generated `public-verify-summary.md` now includes the open-first runbook path, operator prompt path, outbound packet path, unpack command, forward-together triplet, verify-before-assets command, verify-after-assets command, and receive-side `verify-return-packet` acceptance command beside the existing pinned public targets and asset/log status.
- Tightened [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the launch-facing docs now match the stronger compact-summary contract.

`2026-06-02 - Launch Asset Storyboard Surfacing`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the operator packet already carried the exact asset storyboard, but `zmem verify-launch-assets --summary-only` still only listed missing filenames, which left the screenshot/GIF pass as the weakest terminal-first handoff surface in the loop.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem verify-launch-assets --summary-only` now prints the full eight-shot storyboard inline from the launch-proof manifest, including each deliverable filename, capture ID, output path, and the finalize step to rerun before handback.
- Tightened the summary contract in [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and [`tests/test_release_smoke.py`](tests/test_release_smoke.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), and [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md) so the launch-facing docs now match the richer asset-verifier surface.

`2026-06-02 - Outbound Handoff Triplet Surfacing`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the operator packet, runbook, and prompt already existed, but the main release summaries still made another chat infer which files to forward together before starting the real clean-shell pass.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only`, `zmem verify-operator-packet --summary-only`, `zmem verify-public-verify --summary-only`, plus the generated status/prelaunch next-step guidance now all repeat the exact outbound handoff triplet: `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz`.
- Tightened the summary-contract checks in [`scripts/release_smoke.py`](scripts/release_smoke.py), refreshed focused coverage in [`tests/test_release_smoke.py`](tests/test_release_smoke.py) and [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py), and updated [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), and [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md) so the shipped docs now match the new copy-ready handoff wording.

`2026-06-02 - Public Verify Summary Target Pinning`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: the generated clean-shell packet already pinned the exact public targets everywhere except the compact `public-verify-summary.md` artifact that another chat is most likely to forward on its own.
- Updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so the generated `public-verify-summary.md` now restates the expected public repo URL, raw installer URL, and the packaged-install completion rule directly from the launch-proof manifest.
- Kept focused coverage aligned in [`tests/test_cli_onboarding.py`](tests/test_cli_onboarding.py) and refreshed launch-facing docs in [`README.md`](README.md), [`QUICKSTART.md`](QUICKSTART.md), [`docs/DAY1_AGENT_SETUP.md`](docs/DAY1_AGENT_SETUP.md), [`docs/PRODUCT_STATUS.md`](docs/PRODUCT_STATUS.md), and [`landing/index.html`](landing/index.html) so the shipped Phase-1 summary surfaces now agree on the same proof targets and done condition.

`2026-06-02 - Offline Packaged Smoke Unblock`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: external proof was still blocked here, but the highest-leverage remaining local gap was the repo-local packaged smoke path still collapsing to `local-wrappers` in a fresh restricted venv.
- Updated [`scripts/release_smoke.py`](scripts/release_smoke.py) so the install fallback chain now inserts a venv-local `.pth` import bootstrap before the wrapper-only fallback, and the packaged requirement now accepts `venv-pth` while still rejecting `local-wrappers`.
- Mirrored the same bootstrap in `install.sh`, refreshed the fallback wording in the launch docs, and locked the fallback contract with focused release-smoke and onboarding coverage.

`2026-06-02 - Copy-Ready Clean-Shell Operator Prompt`

- Current phase: `Phase 1 - Public Alpha Launch Gate`. Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell plus the missing launch assets. Why this slice was right now: external proof was still blocked here, so the highest-leverage local slice was removing the last handoff reconstruction step; another chat still had to restate the operator task manually before starting the clean-shell pass.
- Added durable [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](docs/CLEAN_SHELL_OPERATOR_PROMPT.md) and updated [`zerker_memory/cli.py`](zerker_memory/cli.py) so `zmem release-pack --summary-only` now generates and ships `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` inside the operator packet, carries that path in the manifest, and surfaces it through status, release-pack, public-verify, and operator-packet summaries.
- Updated launch-facing docs so the orchestrator now pairs the outbound packet with the shipped operator prompt instead of paraphrasing the flow.

## Current Verification

- `test -d ~/.Codex/skills/gstack/bin && echo GSTACK_OK || echo GSTACK_MISSING` -> `GSTACK_OK`.
- `python3 -m unittest tests.test_cli_onboarding.CliOnboardingTest.test_run_launch_proof_writes_transcript_and_artifacts -q` -> 1 test OK.
- `python3 -m unittest tests.test_release_smoke -q` -> 43 tests OK.
- `python3 -m zerker_memory eval` -> 11/11 passed.
- `python3 -m zerker_memory release-pack --summary-only` -> expected blocked state; `.zerker/launch-proof/CAPTURE_CHECKLIST.md` refreshed and strict publish still blocked only on `0/6` clean-shell logs plus `0/8` launch assets.
- `python3 scripts/release_smoke.py --summary-only` -> passed; repo-local Phase-1 preflight remains healthy with the same external blockers.
- `sed -n '1,260p' .zerker/launch-proof/CAPTURE_CHECKLIST.md` -> verified the generated checklist now carries the asset-pass gate, durable fallback docs, finalize step, and receive-side acceptance command inline.

## Known Blockers

- Phase 1 is still externally blocked on proving `https://github.com/zerkerlabs/zerker-memory` and `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell; this environment cannot complete that proof.
- Strict publish remains intentionally blocked until `.zerker/launch-proof/public-verify-logs/` contains the six clean-shell logs, including `operator-packet-verify.log`, `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install run, and `.zerker/launch-proof/assets/` contains the eight launch screenshots/GIFs.
- This run strengthened the generated asset handoff contract locally, but it did not generate the missing networked evidence or captured launch assets.

## Next Recommended Slice

- If external access is available, start from [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md), rerun `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only`, forward `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md`, `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, and `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, then run the clean-shell packaged proof and use the stronger `.zerker/launch-proof/CAPTURE_CHECKLIST.md` for the screenshot/GIF pass against `https://github.com/zerkerlabs/zerker-memory`.
- If external access is still unavailable, only pick another narrow Phase-1 generated-artifact polish slice if a similarly weak forwarded surface is found; otherwise do not spend another run restating the now-aligned asset handback contract.

## Launch Readiness

- Local alpha gate: `ok with warnings (launch_assets, public_verify_evidence)`.
- Strict publish gate: `blocked (launch_assets, public_verify_evidence)`.
- Operator packet: ready (`16/16 files packed`) and pinned to `zerkerlabs/zerker-memory`.
- Generated capture checklist: now independently carries the pre-asset proof gate, durable fallback docs, and receive-side handback rule for forwarded asset-capture loops.

## Active Delegated Sidecar Work

- No active delegated sidecar work in this run. Intended sidecar remains the external clean-shell publish audit plus eight-asset screenshot/GIF capture once networked execution is available.
