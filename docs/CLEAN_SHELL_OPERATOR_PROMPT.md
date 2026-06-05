# Clean-Shell Operator Prompt

Paste the block below into a separate chat or hand it to the clean-shell operator as-is.

```text
You are the clean-shell operator for Zerker Memory Phase 1 public proof.
Prove the public repo `https://github.com/zerkerlabs/zerker-memory` and raw installer `https://raw.githubusercontent.com/zerkerlabs/zerker-memory/main/install.sh` from a clean networked shell.

Success criteria:
- Run the shipped operator packet, not an improvised local flow.
- Treat the first raw install as bootstrap-only so the clean repo exists for packet restore.
- Let `PUBLIC_VERIFY_COMMANDS.sh` rerun the raw installer and record `public-verify-logs/curl-install.log`.
- Save all six clean-shell logs under `.zerker/launch-proof/public-verify-logs/`, including `operator-packet-verify.log`.
- Ensure `.zerker/launch-proof/public-verify-result.json` records a passing packaged-install proof.
- Run `zmem verify-public-verify --summary-only` before the asset pass.
- Capture the full launch storyboard under `.zerker/launch-proof/assets/` and run `zmem verify-launch-assets --summary-only`.
- Run `FINALIZE_RETURN_PACKET.sh` and hand back `.zerker/launch-proof/public-verify-return-packet.tar.gz` only after the self-check passes.

Follow these files in order inside the restored packet:
1. `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`
2. `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md`
3. `.zerker/launch-proof/CAPTURE_CHECKLIST.md`

Constraints:
- Do not replace the public endpoints with local paths.
- Do not skip the packaged-install proof.
- Do not hand back partial logs or partial assets.

Required outputs for handback:
- `.zerker/launch-proof/public-verify-logs/`
- `.zerker/launch-proof/public-verify-result.json`
- `.zerker/launch-proof/public-verify-summary.md`
- `.zerker/launch-proof/public-verify-return-packet.tar.gz`

If any step fails, stop and report the failing command plus the saved log path instead of patching around it.
```

Reference files:

- Runbook: `.zerker/launch-proof/CLEAN_SHELL_PUBLIC_VERIFY.md`
- Checklist: `.zerker/launch-proof/PUBLIC_VERIFY_CHECKLIST.md`
- Launch asset checklist: `.zerker/launch-proof/CAPTURE_CHECKLIST.md`
- Finalize script: `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh`
