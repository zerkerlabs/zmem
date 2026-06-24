# ZMem Launch List

Public domain: `https://zmem.sh`

Public repo target: `https://github.com/zerkerlabs/zmem`

Raw installer target: `https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh`

## Launch Claim

ZMem is local-first verifiable memory for AI agents.

It gives agents memory that survives restarts, can be inspected before it influences action, and produces receipts for what was used, withheld, and changed.

## Must Ship For Public Alpha

Current verified status as of `2026-06-24T00:08:53Z`: all repo-local proof gates below pass, including packaged clean-shell evidence, `8/8` launch assets, return-packet verification, and `prelaunch --summary-only`.

- Public GitHub repo exists at `zerkerlabs/zmem`.
- `zmem.sh` points to the launch site.
- README, QUICKSTART, install script, release checklist, and proof pack all use `zerkerlabs/zmem`.
- Local install path works from a clean shell:

```bash
curl -fsSL https://raw.githubusercontent.com/zerkerlabs/zmem/main/install.sh | bash
```

- `python3 -m unittest discover -s tests` passes.
- `zmem eval` passes.
- `python3 scripts/release_smoke.py --summary-only` passes.
- `python3 scripts/release_smoke.py --require-install-mode packaged` passes in the clean-shell proof.
- `zmem release-pack --summary-only` refreshes `.zerker/launch-proof/`.
- `zmem verify-operator-packet .zerker/launch-proof/public-verify-operator-packet.tar.gz --summary-only` passes.
- Clean-shell public verify logs exist under `.zerker/launch-proof/public-verify-logs/`.
- `.zerker/launch-proof/public-verify-result.json` records a passing packaged install.
- `.zerker/launch-proof/public-verify-summary.md` summarizes the public proof.
- Eight launch screenshots/GIFs exist under `.zerker/launch-proof/assets/`.
- `zmem verify-launch-assets --summary-only` reports `8/8 captured`.
- `.zerker/launch-proof/FINALIZE_RETURN_PACKET.sh` rebuilds the return packet.
- `zmem verify-return-packet .zerker/launch-proof/public-verify-return-packet.tar.gz --summary-only` reports ready.
- Treeship `0.12.0+` proof path is documented as optional public proof publishing.

## Must Be Clear In Product UX

- ZMem works standalone and local-first.
- Treeship is the proof publication layer, not a day-one dependency.
- Keep the public name `ZMem` for this launch despite the known Microsoft Defender name collision; mitigate through open-source transparency, clean-shell proof, public installer logs, and clear local-first security posture rather than another late rename.
- Default user story is memory-first:
  - install;
  - connect agent through MCP;
  - inject governed memory;
  - inspect why memory was used or withheld;
  - export/restore/handoff;
  - optionally publish a proof URL.
- Use `memory`, not `context`, for durable state.
- Use `context` only for temporary task input delivered to an agent.
- Do not overclaim Guard/Gateway as shipped products.

## Launch Copy

Primary:

> ZMem: local-first memory for agents, with receipts.

Secondary:

> Agents do not just need memory. They need memory you can inspect, govern, and prove.

Proof line:

> ZMem governs memory influence. Treeship can publish the receipt.

Boundary line:

> ZMem does not trust the agent's story about memory. It records what memory was available, what policy allowed, what was withheld, and what proof verifies the action.

Security posture:

> ZMem is open source, local-first, and inspectable. The public launch proof captures the exact installer target, clean-shell logs, release smoke result, and return packet before strict publish goes green.

## Day-One Demo Path

```bash
zmem init --with-policy --with-agent-prompt --with-mcp-config --with-provider-config
zmem agent install claude-code --summary-only
zmem demo
zmem why <action-id>
zmem verify <action-id>
zmem bundle <action-id> --out-dir .zerker/exports
zmem snapshot --out-dir .zerker/exports
zmem handoff --summary-only
zmem treeship publish <action-id>
```

The `zmem treeship publish` step is optional for public proof; local memory proof works without it.

## Next Build After Launch

### Simpler Proof UX

- Add `zmem proof <action-id>` as the simple local proof export command.
- Add `zmem publish <action-id>` as the simple public proof command.
- Keep `zmem treeship ...` as advanced plumbing.

### Boundary Proof Payload

- Move ZMem Treeship payloads toward `treeship.boundary.v1`.
- Keep proven fields separate from asserted fields.
- Record policy digest, diet root, committed anchor, injected count, and withheld count.
- Do not claim to prove hidden reasoning or excluded inputs unless the policy/diet mechanism makes that checkable.

### Benchmark Harness

- Build `zmem bench` for LongMemEval and LoCoMo.
- Record accuracy, F1, recall@k, latency, token counts, abstention, and temporal/update correctness.
- Emit benchmark receipts, per-question bundles, and optional Treeship proof URLs.

### Retrieval Depth

- Strengthen SQLite FTS/BM25.
- Add optional embeddings.
- Add reranking.
- Add temporal metadata and conflict/update handling.
- Add context packing budgets.
- Add multi-hop query decomposition.

### Operator Visibility

- Make withheld/rejected/quarantined memory prominent in the dashboard.
- Add views for "what was allowed," "what was withheld," and "what changed since checkpoint."
- Add scoped sub-agent memory packets for handoff.
