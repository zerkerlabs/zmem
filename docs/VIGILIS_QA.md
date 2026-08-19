# Vigilis QA gate (report-only)

[Vigilis](https://vigilis.dev) runs a thin end-to-end suite against the local
review dashboard on every PR, **attests the actual run**, and (on a real failure)
triages/heals the failing spec. It is **report-only**: it uploads a Playwright
report and an attestation bundle but does not block merges.

## What it checks
- The review console renders (Proof Inspector, Memory In Use, Memory Status).
- Promoting a queued memory removes it from the review queue.
- Rejecting a queued memory removes it from the review queue.
- Exporting a snapshot returns a typed, content-addressed proof artifact.

## Run it locally
```bash
python -m pip install -e .
export ZMEM_DB="$(mktemp -d)/zmem-ci.db"
python scripts/seed_review_state.py --db "$ZMEM_DB"
python -m zerker_memory.dashboard --db "$ZMEM_DB" --port 8765 &
cd qa && npm ci && npx playwright install chromium && npx playwright test
# attest the run (no secrets needed):
npx --no-install vigilis attest-run results.json --commit "$(git rev-parse HEAD)" --exit-code $?
```

## Attestation — what is proven, and how much
Attestation proves **what happened** (integrity/provenance), not that the
results are correct.

1. **QA-run receipt — every run, zero secrets.** `vigilis attest-run` hash-chains
   one record per spec plus a `qa_run` summary that binds the Playwright report
   digest (`sha256`), the commit SHA, the exit code, and the pass/fail counts. No
   model call, no API key. Written to `qa/.vigilis/attestation/` as
   `N artifacts, chain intact (unsigned)` and uploaded as a CI artifact. A missing
   bundle fails the upload (`if-no-files-found: error`) rather than passing silently.
2. **Triage/heal receipt — only on a real failure, needs `ANTHROPIC_API_KEY`.**
   When a spec actually fails and the key is set, Vigilis triages the failing
   spec (drift vs. real bug) and attests that decision too. Without the key this
   step is skipped (not failed); the QA-run receipt above is still produced.
3. **Signed receipts — optional, not wired by default.** The bundles above are
   **unsigned**. To upgrade to an independently-notarized signed receipt, install
   and configure the [Treeship](https://www.treeship.dev) CLI in the workflow and
   provide its credentials. This is **not** installed by default — do not assume
   signed receipts without it.

## Secrets
| Secret | Effect if set | If absent |
|--------|---------------|-----------|
| `ANTHROPIC_API_KEY` | Enables triage/heal + its receipt on real failures | Heal step skipped; QA-run receipt still produced |
| `TREESHIP_*` (+ Treeship CLI) | Signed, independently notarized receipts | Local **unsigned** bundle only |

## Make it blocking (later)
Remove `continue-on-error: true` from `.github/workflows/vigilis-qa.yml` once the
team trusts the signal.
