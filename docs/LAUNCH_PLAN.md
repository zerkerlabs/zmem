# Zerker Memory Launch Plan

## Launch Thesis

ZMem is not another memory provider.

It is a governance layer for agent memory:

```text
Recall providers find candidate memory.
ZMem decides what may influence action.
Treeship proves what happened.
```

Public line:

> Governed memory for agents that act.

Longer line:

> ZMem gives AI agents local-first memory with authority checks, quarantine, lineage, revocation, Merkle receipts, and MCP integration.

## Repo Readiness

Already present:

- MIT license.
- README.
- Quickstart.
- Contribution guide.
- Adoption strategy.
- One-pager.
- MCP config example.
- Dogfood guide.
- Agent prompt template.
- Frontier alignment doc.
- Tests.
- CI workflow.
- `zmem eval`.
- `zmem doctor`.

Before publishing:

- Create a clean GitHub repo.
- Use `zerkerlabs/zmem` as the final public repo URL.
- Verify the raw installer URL works from a clean shell.
- Run `python3 scripts/release_smoke.py --summary-only`, `zmem release-pack --summary-only`, and `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` before handing work to another shell.
- Remove local generated `.zerker/` files from the working tree.
- Confirm `.gitignore` excludes local DBs and exports.
- Capture the Phase 1 launch-proof return set from the generated packet, not an ad hoc demo path.
- Require the clean-shell operator to prove `https://github.com/zerkerlabs/zmem` and `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`.
- Require `zmem verify-public-verify --summary-only` to pass before the screenshot/GIF pass starts.
- Capture and return the exact eight launch assets now required by the verifier:
  - `assets/install-status.png`
  - `assets/first-run-status.png`
  - `assets/release-pack-summary.png`
  - `assets/proof-report-overview.png`
  - `assets/transcript-proof.png`
  - `assets/ui-release-pack.gif`
  - `assets/handoff-restore-terminal.png`
  - `assets/ui-handoff-restore.gif`
- Accept handback only through `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only`.
- Generate repeatable launch proof artifacts with `zmem launch-proof` or `bash scripts/launch_proof.sh`.
- Use `docs/CLEAN_SHELL_PUBLIC_VERIFY.md` as the durable runbook for the outbound operator packet, clean-shell pass, and receive-side acceptance loop.
- Add GitHub repo URL to `pyproject.toml`.
- Run `make verify` in Python 3.10+.
- Tag `v0.1.1` for the current launch checkpoint. The earlier `v0.1.0` tag already exists and must not be moved.
- Complete `docs/PUBLIC_LAUNCH_AUDIT.md`.

## Product Packaging

Required before public announcement:

1. One-command proof:

```bash
zmem eval
```

2. Readiness check:

```bash
zmem doctor
```

3. MCP integration:

```bash
zmem --db .zerker/memory.sqlite mcp
```

4. Agent wrapper:

```bash
zmem run --agent codex --task "deploy service" --risk high --scope project -- your-agent-command
```

5. Proof export:

```bash
zmem export <action-id> --format treeship --out-dir .zerker/exports
zmem treeship doctor
zmem treeship publish <action-id> --dry-run --command-template "treeship prove {statement} --action {action_id}"
zmem bt export trace_demo_recovery --out-dir .zerker/exports
```

The Treeship export should carry the verified receipt bundle so launch demos can show local proof, bundle hash, and portable statement output in one step. The BT export should add a screenshot-ready BehaviorTree.CPP/Groot2 artifact plus a provenance manifest for recovery demos.

For live provider demos and release smoke, set `ZERKER_PROVIDER_LIVE_PROVIDERS` to `mem0`, `zep`, or `mem0,zep` so verification only probes the adapters you explicitly intend to show.

## Landing Page Sections

1. Hero
   - Headline: "Governed memory for agents that act."
   - Subcopy: "Local-first memory with symbolic policy gates, lineage, revocation, and receipts."
   - Primary CTA: "Run `zmem eval`"
   - Secondary CTA: "View GitHub"

2. Problem
   - Agents remember the wrong things.
   - Memory providers retrieve context but rarely govern authority.
   - Persistent memory poisoning is a long-game attack.

3. Difference
   - Neural recall.
   - Symbolic control.
   - Cryptographic proof.

4. How It Works
   - Recall candidates.
   - Quarantine untrusted memory.
   - Promote policy.
   - Inject authorized context.
   - Explain and export receipts.

5. Integrations
   - MCP.
   - Mem0 overlay.
   - Treeship-ready export.
   - Future Zep/Graphiti, Letta, LangMem.

6. Demo
   - Add deploy policy.
   - Add poisoned candidate.
   - Run high-risk task.
   - Show injected/withheld receipt.

7. Install
   - `bash install.sh`
   - `curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash`
   - `zmem status --summary-only`

## Visual Direction

Style:

- Calm, technical, premium.
- Dark neutral background, warm white text, restrained green/amber trust signals.
- Avoid generic AI gradients and purple-blue SaaS sameness.
- Use a live memory graph/circuit canvas as the first-viewport visual.
- Make product proof concrete through terminal blocks and receipt snippets.

Design language:

- Proof ledger.
- Local graph.
- Gate.
- Receipt.
- Chain of custody.

Avoid:

- "AI remembers you" consumer positioning.
- Blockchain language.
- Quantum claims.
- Overstated security guarantees.

## First Announcement

Draft:

> Most agent memory systems ask: what should the agent remember?
>
> Zerker asks: what is memory allowed to influence?
>
> Today we are open-sourcing a local-first memory control plane for AI agents: MCP, quarantine, symbolic policy gates, lineage, revocation, Merkle receipts, and Treeship-ready exports.
>
> Run `zmem eval` to see the proof.
