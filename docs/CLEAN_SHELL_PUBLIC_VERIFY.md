# Clean-Shell Public Verify

Use this repo-level runbook when Phase 1 is blocked on the final public installer proof and you need one stable checklist outside generated `.zerker/launch-proof/` state.

Current phase: `Phase 1 - Public Alpha Launch Gate`.
Top remaining blocker: external proof of the live public repo/raw installer from a clean networked shell, plus the final launch assets that must come back with that proof.
Why this checklist exists: the generated operator packet is the source of truth for a specific run, but another chat or operator still needs one durable repo doc that explains the outbound packet, the clean-shell commands, and the receive-side acceptance rules before the pack is refreshed.

## When To Use It

- Use this after `zmem release-pack --summary-only` refreshes `.zerker/launch-proof/` and `.zerker/handoff/`.
- Use this when you need to brief a separate clean-shell operator or chat before they open the generated pack.
- Use this when the current environment cannot prove the public GitHub/raw installer path directly.

## Repo-Local Preflight

Run these from the repo before handing work to another shell or operator:

```bash
python3 scripts/release_smoke.py --summary-only
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
```

Expected result:

- `release-pack` reports `Launch proof: ok` and `Handoff: ok`.
- `verify-operator-packet` reports `Ready: yes`.
- The remaining blockers are only `public_verify_evidence` and `launch_assets`.

The generated clean-shell script repeats that same operator-packet verification before it starts the live public proof steps, so a stale or incomplete forwarded archive fails fast instead of wasting the clean-shell run.

## Outbound Packet

Forward this file first when you want a one-file operator handoff:

```text
.zerker/launch-proof/public-verify-operator-packet.tar.gz
```

That archive should contain:

- `launch-proof.json`
- `README.md`
- `index.html`
- `CAPTURE_CHECKLIST.md`
- `LAUNCH_ASSET_HANDOFF.md`
- `PUBLIC_VERIFY_HANDOFF.md`
- `RECEIVE_VERIFY_HANDOFF.md`
- `CLEAN_SHELL_PUBLIC_VERIFY.md`
- `CLEAN_SHELL_OPERATOR_PROMPT.md`
- `PUBLIC_VERIFY_CHECKLIST.md`
- `PUBLIC_VERIFY_COMMANDS.sh`
- `FINALIZE_RETURN_PACKET.sh`
- `public-verify-result.json`
- `public-verify-summary.md`
- `public-verify-return-packet.tar.gz`

## Public Targets

The clean-shell proof must validate these exact public endpoints:

- GitHub repo: `https://github.com/zerkerlabs/zerker-memory`
- Raw installer: `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`

## Clean-Shell Operator Steps

1. Start from a clean networked shell against the public repo and confirm the repo URL is `https://github.com/zerkerlabs/zerker-memory`.
2. Run the raw installer once to bootstrap the clean repo path:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh | bash
cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
```

3. Copy the forwarded operator packet archive into the clean repo at `.zerker/launch-proof/public-verify-operator-packet.tar.gz`, then restore the generated proof packet:

```bash
mkdir -p .zerker/launch-proof
tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof
```

4. If you are briefing a separate chat, paste `.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md` first. Then open `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md` from that restored packet and run the generated public-verify script exactly as shipped:

```bash
.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh
```

That script now starts by running `python3 -m zerker_memory verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` and saves the output to `.zerker/launch-proof/public-verify-logs/operator-packet-verify.log` before it touches the live public proof steps.
The bootstrap install above is only for creating the repo path and restoring the packet; `PUBLIC_VERIFY_COMMANDS.sh` reruns the raw installer itself and records `public-verify-logs/curl-install.log` as the proof log.

5. Confirm the clean-shell logs were written under `.zerker/launch-proof/public-verify-logs/`.
6. Confirm `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install proof.
7. Run `zmem verify-public-verify --summary-only` and confirm it reports `Ready: yes`.
8. Confirm `.zerker/launch-proof/public-verify-summary.md` shows the same pass/fail state without opening raw logs.
9. Follow `.zerker/launch-proof/CAPTURE_CHECKLIST.md` and save the required assets under `.zerker/launch-proof/assets/`.
10. Run:

```bash
zmem verify-launch-assets --summary-only
.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh
```

11. Hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz`.

## Required Clean-Shell Logs

The return packet must contain these six logs:

- `operator-packet-verify.log`
- `curl-install.log`
- `first-run.log`
- `release-pack.log`
- `packaged-release-smoke.log`
- `prelaunch.log`

## Command Log Map

Use this map to avoid ambiguous handback logs. Each command below should save to the named file and satisfy the stated success cue:

1. `python3 -m zerker_memory verify-operator-packet ".zerker/launch-proof/public-verify-operator-packet.tar.gz" --summary-only` -> `public-verify-logs/operator-packet-verify.log`
   Confirm: reports `Ready: yes` before the live public proof steps start.
2. `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh | bash` -> `public-verify-logs/curl-install.log`
   Confirm: ends on `Zerker Memory status`.
3. `bash examples/first_run.sh` -> `public-verify-logs/first-run.log`
   Confirm: ends on `Manual pack ready: yes`.
4. `zmem release-pack --summary-only` -> `public-verify-logs/release-pack.log`
   Confirm: shows the public verify script, operator packet, and `Prelaunch: blocked` pending external proof.
5. `python3 scripts/release_smoke.py --require-install-mode packaged` -> `public-verify-logs/packaged-release-smoke.log`
   Confirm: passes with `install_mode` satisfying `packaged` and without `local-wrappers` fallback.
6. `zmem prelaunch` -> `public-verify-logs/prelaunch.log`
   Confirm: passes without placeholder warnings before tagging.

## Required Launch Assets

The return packet must also contain these eight deliverables:

- `assets/install-status.png`
- `assets/first-run-status.png`
- `assets/release-pack-summary.png`
- `assets/proof-report-overview.png`
- `assets/transcript-proof.png`
- `assets/ui-release-pack.gif`
- `assets/handoff-restore-terminal.png`
- `assets/ui-handoff-restore.gif`

## Stop Conditions

Stop the clean-shell pass and hand the failure state back instead of improvising a local fix if any of these happen:

- the public repo URL is not `https://github.com/zerkerlabs/zerker-memory`
- the raw installer URL is not `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh`
- `python3 scripts/release_smoke.py --require-install-mode packaged` falls back to local wrappers or records any install mode other than `packaged`
- `zmem verify-public-verify --summary-only` does not report `Ready: yes` after the generated script finishes
- `zmem verify-launch-assets --summary-only` does not report `8/8 captured`
- `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` or `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` does not report `Ready: yes`

## Receive-Side Acceptance

Do not accept the handback by inspection alone. Run:

```bash
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
```

Accept Phase 1 proof only when that command reports:

- `Ready: yes`
- all six clean-shell logs present
- a passing `public-verify-result.json`
- the compact `public-verify-summary.md`
- all required launch assets present

If any part is missing or failed, send the packet back for another clean-shell run instead of editing the proof locally.

## External Blocker

This repo still cannot finish the final packaged-install proof in the current restricted environment because it cannot verify the live public GitHub/raw installer path from a clean networked shell. Until that external run exists, Phase 1 remains blocked even if the local repo surfaces are healthy.
