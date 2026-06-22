# Clean-Shell Verification Checklist

Use this when Phase 1 is blocked on the external clean-shell proof and you need one short repo-level checklist instead of the longer brief or runbook.

Current phase: `Phase 1 - Public Alpha Launch Gate`.
Top remaining blocker: external proof of `https://github.com/zerkerlabs/zmem` and `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`, plus the missing `6/6` clean-shell logs and `8/8` launch assets.
Why this checklist exists: the repo already has a durable operator brief and a durable runbook, but the launch gate still benefits from one concise send-run-receive list for separate chats or operators.

## 1. Repo-Local Preflight

Run these in the repo before handing work to another shell:

```bash
bash scripts/gstack_check.sh
python3 scripts/release_smoke.py --summary-only
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
```

Pass when:

- `scripts/gstack_check.sh` reports `GSTACK_OK` or `GSTACK_MISSING`
- `release-pack` reports `Launch proof: ok` and `Handoff: ok`
- `verify-operator-packet` reports `Ready: yes`
- the remaining blockers are only `public_verify_evidence` and `launch_assets`

## 2. Forward The Exact Triplet

Send these three files together:

```text
.zerker/launch-proof/CLEAN_SHELL_OPERATOR_PROMPT.md
.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md
.zerker/launch-proof/public-verify-operator-packet.tar.gz
```

If packet-local files are stale, rerun `zmem release-pack --summary-only` first.

## 3. Clean-Shell Bootstrap

In the clean networked shell:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
cd "${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo"
mkdir -p .zerker/launch-proof
tar -xzf .zerker/launch-proof/public-verify-operator-packet.tar.gz -C .zerker/launch-proof
```

Pass when:

- the repo path is `${ZERKER_MEMORY_HOME:-$HOME/.zerker-memory}/repo`
- the restored packet contains `CLEAN_SHELL_PUBLIC_VERIFY.md`
- you treat this first curl install as bootstrap-only

## 4. Run The Public-Proof Script

Open `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`, then run:

```bash
.zerker/launch-proof/PUBLIC_VERIFY_COMMANDS.sh
zmem verify-public-verify --summary-only
```

Pass when:

- `verify-public-verify` reports `Ready: yes`
- `.zerker/launch-proof/public-verify-result.json` is passing
- the observed install mode satisfies `packaged`

## 5. Confirm The Six Logs

These files must exist under `.zerker/launch-proof/public-verify-logs/`:

- `operator-packet-verify.log`
- `curl-install.log`
- `first-run.log`
- `release-pack.log`
- `packaged-release-smoke.log`
- `prelaunch.log`

Success cues:

- `operator-packet-verify.log`: reports `Ready: yes`
- `curl-install.log`: ends on `Zerker Memory status`
- `first-run.log`: ends on `Manual pack ready: yes`
- `release-pack.log`: shows the public verify script and `Prelaunch: blocked`
- `packaged-release-smoke.log`: passes without `local-wrappers` fallback
- `prelaunch.log`: passes before tagging

## 6. Capture The Eight Launch Assets

After `verify-public-verify` is ready:

```bash
zmem verify-launch-assets --summary-only
```

Required outputs under `.zerker/launch-proof/assets/`:

- `install-status.png`
- `first-run-status.png`
- `release-pack-summary.png`
- `proof-report-overview.png`
- `transcript-proof.png`
- `ui-release-pack.gif`
- `handoff-restore-terminal.png`
- `ui-handoff-restore.gif`

Use `.zerker/launch-proof/CAPTURE_CHECKLIST.md` plus `.zerker/launch-proof/LAUNCH_ASSET_BOARD.html` while capturing.
Pass when `verify-launch-assets --summary-only` reports `8/8 captured`.

## 7. Finalize The Return Packet

Run:

```bash
.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh
zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only
```

Pass when `verify-return-packet` reports `Ready: yes`.

## 8. Receive-Side Acceptance

Only accept the handback when all of these are true:

- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports `Ready: yes`
- all six logs are present
- `public-verify-result.json` is passing
- `public-verify-summary.md` is present
- all eight assets are present

## 9. Stop Conditions

Stop and return the failure state instead of improvising if:

- the public repo is not `https://github.com/zerkerlabs/zmem`
- the raw installer is not `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`
- the packaged proof falls back to `local-wrappers` or another non-`packaged` mode
- `verify-public-verify` does not report `Ready: yes`
- `verify-launch-assets` does not report `8/8 captured`
- `verify-return-packet` does not report `Ready: yes`

## Related Docs

- Longer send-run-receive brief: [`docs/PHASE1_EXTERNAL_OPERATOR_BRIEF.md`](PHASE1_EXTERNAL_OPERATOR_BRIEF.md)
- Durable runbook: [`docs/CLEAN_SHELL_PUBLIC_VERIFY.md`](CLEAN_SHELL_PUBLIC_VERIFY.md)
- Copy-ready operator prompt: [`docs/CLEAN_SHELL_OPERATOR_PROMPT.md`](CLEAN_SHELL_OPERATOR_PROMPT.md)
- Durable asset prompt: [`docs/LAUNCH_ASSET_OPERATOR_PROMPT.md`](LAUNCH_ASSET_OPERATOR_PROMPT.md)
- Durable asset board: [`docs/LAUNCH_ASSET_BOARD.html`](LAUNCH_ASSET_BOARD.html)
