# Phase 1 External Operator Brief

Use this as the single durable repo-level brief for the remaining Phase-1 launch gate when another chat or operator has to finish the clean-shell public proof, capture the launch assets, and hand back the return packet.

Current phase: `Phase 1 - Public Alpha Launch Gate`.
Top remaining blocker: external proof of the live public repo and raw installer from a clean networked shell, plus the missing six clean-shell proof logs and eight launch assets.
Why this brief exists: the generated packet, verifier summaries, runbook, operator prompt, and asset checklist are already aligned locally, but orchestration across separate chats still benefits from one pinned repo doc that spans send, run, capture, and accept.

If you need the short version instead of this full brief, start with [`docs/CLEAN_SHELL_VERIFICATION_CHECKLIST.md`](CLEAN_SHELL_VERIFICATION_CHECKLIST.md).

## Use This Brief When

- the current shell cannot verify the live public GitHub repo or raw installer directly
- you need to brief a separate clean-shell chat or human operator
- you need one durable source outside generated `.zerker/launch-proof/` state

## Repo-Local Preflight

Run these before handing work to another shell:

```bash
bash scripts/gstack_check.sh
python3 scripts/release_smoke.py --summary-only
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
```

Expected state:

- `bash scripts/gstack_check.sh` reports `GSTACK_OK` or `GSTACK_MISSING` for this repo shell without changing the launch-gate contract.
- `release-pack` reports `Launch proof: ok` and `Handoff: ok`
- `verify-operator-packet` reports `Ready: yes`
- the only remaining blockers are `public_verify_evidence` and `launch_assets`

## Forward Together

Send these three files together to the clean-shell operator:

```text
.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md
.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md
.zerker/launch-proof/public-verify-operator-packet.tar.gz
```

If generated packet state is stale, refresh it first with `zmem release-pack --summary-only`.

## Public Targets

The clean-shell proof must validate these exact public endpoints:

- `https://github.com/zerkerlabs/zmem`
- `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`

## Clean-Shell Run

1. Run the raw installer once to create the clean repo path:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
```

2. Copy the forwarded operator packet archive into that repo at `.zerker/launch-proof/public-verify-operator-packet.tar.gz`.
3. Restore the outbound packet into that repo:

```bash
mkdir -p .zerker/launch-proof
tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof
```

4. Open `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`.
5. Run `.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh`.
6. Run `zmem verify-public-verify --summary-only`.

Important:

- The first raw install is bootstrap-only.
- `PUBLIC_VERIFY_COMMANDS.sh` reruns the raw installer and records `public-verify-logs/curl-install.log` as the proof log.
- The observed install mode must satisfy `packaged`.

## Required Proof Logs

The clean-shell run must return these six logs under `.zerker/launch-proof/public-verify-logs/`:

- `operator-packet-verify.log`
- `curl-install.log`
- `first-run.log`
- `release-pack.log`
- `packaged-release-smoke.log`
- `prelaunch.log`

Command-to-log map:

1. `python3 -m zerker_memory verify-operator-packet ".zerker/launch-proof/public-verify-operator-packet.tar.gz" --summary-only` -> `public-verify-logs/operator-packet-verify.log`
   Confirm: reports `Ready: yes` before the live public proof steps start.
2. `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash` -> `public-verify-logs/curl-install.log`
   Confirm: ends on `Zerker Memory status`.
3. `bash examples/first_run.sh` -> `public-verify-logs/first-run.log`
   Confirm: ends on `Manual pack ready: yes`.
4. `zmem release-pack --summary-only` -> `public-verify-logs/release-pack.log`
   Confirm: shows the public verify script, operator packet, and `Prelaunch: blocked` pending external proof.
5. `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`
   Confirm: passes with `install_mode` satisfying `packaged` and without `local-wrappers` fallback.
6. `zmem prelaunch` -> `public-verify-logs/prelaunch.log`
   Confirm: passes without placeholder warnings before tagging.

## Launch Asset Pass

After `zmem verify-public-verify --summary-only` reports `Ready: yes`:

1. Open `.zerker/launch-proof/CAPTURE_CHECKLIST.md`.
2. Keep `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` open while capturing.
3. Save every asset under `.zerker/launch-proof/assets/`.
4. Run `zmem verify-launch-assets --summary-only`.

Required assets:

- `assets/install-status.png`
- `assets/first-run-status.png`
- `assets/release-pack-summary.png`
- `assets/proof-report-overview.png`
- `assets/transcript-proof.png`
- `assets/ui-release-pack.gif`
- `assets/handoff-restore-terminal.png`
- `assets/ui-handoff-restore.gif`

If generated asset docs are stale or unavailable, use [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](LAUNCH_ASSET_OPERATOR_PROMPT.md) as the durable fallback brief.

## Finalize And Hand Back

After the clean-shell proof and asset pass both succeed:

```bash
.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
```

Hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` only when the verify command reports `Ready: yes`.

## Receive-Side Acceptance

The orchestrator chat should accept the handback only when all of these are true:

- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`
- all six clean-shell proof logs are present
- `.zerker/launch-proof/public-verify-result.json` is passing
- `.zerker/launch-proof/public-verify-summary.md` is present
- all eight launch assets are present

If any item is missing or failed, reject the packet and send it back for another clean-shell run instead of editing proof locally.

## Stop Conditions

Stop and hand back the failure state instead of improvising local fixes if:

- the public repo is not `https://github.com/zerkerlabs/zmem`
- the raw installer is not `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`
- the packaged clean-shell proof falls back to `local-wrappers` or any non-`packaged` install mode
- `zmem verify-public-verify --summary-only` does not report `Ready: yes`
- `zmem verify-launch-assets --summary-only` does not report `8/8 captured`
- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` does not report `Ready: yes`

## External Blocker

This repo still cannot complete Phase 1 in the current restricted environment because it cannot prove the live public GitHub repo and raw installer from a clean networked shell. Until that external run exists, strict publish remains intentionally blocked.
