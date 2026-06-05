# ZMem Launch Readiness

Current launch stance: local alpha is dogfood-ready; public alpha publish is blocked until the public repo exists and the clean-shell proof plus launch assets are captured.

## Product Positioning

Launch as:

> Local-first verifiable memory for AI agents.

Public promise:

> ZMem gives every memory provenance, policy, receipts, and a trust gate before it influences action.

Keep the homepage memory-first. Use "context" only for the temporary task input an agent receives after policy-gated memory injection.

## Repo Plan

Recommended public repo:

```text
zerkerlabs/zerker-memory
```

Why:

- Matches the public product/domain name.
- Matches the raw installer contract already documented in release proof.
- Keeps the repo short while preserving the Python package name `zerker-memory`.
- Avoids shipping under the current stale local remote, which points at an unrelated template repo.

Current local finding:

```text
origin   https://github.com/rezker1/nextjs-with-supabase.git
template https://github.com/rezker1/nextjs-ai-chatbot.git
```

Do not push ZMem to either of those remotes.

Codex can create the GitHub repo only after GitHub auth is fixed and the target owner is confirmed. Current `gh auth status` reports the `rezker1` token is invalid.

## Site Plan

Recommended day-1 site:

```text
https://zmem.sh
```

Use `zmem.sh` as the public launch domain now. It is short, CLI-shaped, and pairs well with `treeship.dev` as the proof layer.

Recommended path:

1. Ship `zmem.sh` as the public site.
2. Host the code under `zerkerlabs/zerker-memory`.
3. Keep `zerker.ai/memory` or `memory.zerker.ai` as optional redirects from the broader Zerker surface.
4. Use `treeship.dev` as a visible proof companion, not a prerequisite the user must understand before installing ZMem.

## What Is Ready

From `zmem status --summary-only`:

- Workspace ready: yes.
- Doctor: ok.
- Memory proof ready: yes.
- Release packet ready: yes.
- Strict publish ready: no.
- Manual MCP pack ready: yes.
- Local alpha gate: ok with warnings.

Built product surface:

- Local SQLite memory.
- Typed memories and review queue.
- Policy-gated injection.
- Provenance and authority controls.
- Receipts, `why`, verify, bundles, snapshots, handoff/restore.
- Event Merkle root and selected-memory Merkle trees.
- MCP server and agent setup packs.
- Local dashboard.
- Landing page.
- Release proof and public verify packet machinery.

## Public Publish Blockers

Strict publish remains blocked on:

```text
launch_assets
public_verify_evidence
```

Required evidence:

- Clean-shell public verify logs under `.zerker/launch-proof/public-verify-logs/`.
- `.zerker/launch-proof/public-verify-result.json`.
- `.zerker/launch-proof/public-verify-summary.md`.
- Eight launch screenshots/GIFs under `.zerker/launch-proof/assets/`.
- Final verified return packet at `.zerker/launch-proof/public-verify-return-packet.tar.gz`.

## Next Actions

1. Fix GitHub auth.

```bash
gh auth login -h github.com
```

2. Confirm repo owner:

```text
zerkerlabs
```

3. Create `zerkerlabs/zerker-memory` as a public MIT repo.

4. Push only the ZMem project files, not the unrelated current parent repo state.

5. Run the release checks:

```bash
python3 -m unittest discover
python3 scripts/release_smoke.py
zmem release-pack --summary-only
zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only
```

6. Run clean-shell public verify from the generated operator packet.

7. Capture the launch assets.

8. Finalize and verify the return packet.

9. Publish the site on the Zerker web surface.

10. Tag:

```text
v0.1.0-alpha
```

## Decision Needed From User

- Confirm GitHub owner: `zerkerlabs` or personal account.
- Confirm site target: `zmem.sh`.
- Re-authenticate GitHub CLI so Codex can create/push the repo.
