# Vigilis QA gate (report-only)

[Vigilis](https://vigilis.dev) runs a thin end-to-end suite against the local
review dashboard on every PR and **attests** the agent's triage/heal decisions.
It is **report-only**: it uploads a Playwright report and an attestation bundle
but does not block merges.

## What it checks
- The review console renders (Proof Inspector, Memory In Use, Memory Status).
- Promoting a queued memory removes it from the review queue.
- Rejecting a queued memory removes it from the review queue.
- Exporting a snapshot produces a proof artifact.

## Run it locally
```bash
python -m pip install -e .
export ZMEM_DB="$(mktemp -d)/zmem-ci.db"
python scripts/seed_review_state.py --db "$ZMEM_DB"
python -m zerker_memory.dashboard --db "$ZMEM_DB" --port 8765 &
cd qa && npm install && npx playwright install chromium && npx playwright test
```

## Attestation
- **Zero secrets:** without Treeship, Vigilis writes a hash-chained, **unsigned**
  attestation bundle to `.vigilis/attestation/` ("N artifacts, chain intact").
  It is verifiable and auditable — it proves *what the agent did*, not that its
  judgment was correct.
- **Signed receipts:** set `ANTHROPIC_API_KEY` (required for the agent to run at
  all) and, optionally, the `TREESHIP_*` secrets to seal an independently
  notarized receipt. Without `ANTHROPIC_API_KEY` the E2E specs still run; the
  attested triage/heal step is skipped.

## Make it blocking (later)
Remove `continue-on-error: true` from `.github/workflows/vigilis-qa.yml` once the
team trusts the signal.
