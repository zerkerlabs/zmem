# v0.1.7 Hardening Review

Date: 2026-07-16

This note records the disposition of the independent `v0.1.6` adversarial re-test. It separates reproduced defects from compatibility-sensitive design work so the release can be hardened without silently changing proof semantics.

## Re-Test Result

The reviewer independently reproduced and confirmed all three `v0.1.6` fixes:

- `~` paths expand before use.
- MCP rejects string values such as `"False"` for boolean inputs.
- Concurrent event writers retain one linear `prev_event_hash` chain.

## Current Candidate

The `codex/v0.1.7-hardening` candidate addresses bounded defects that do not alter stored memory or receipt-chain compatibility:

| Surface | Candidate behavior | Acceptance evidence |
| --- | --- | --- |
| `zmem run` | Implicit context is mode `0600` and deleted after the command; explicit context paths are retained | Child process observes `0600`; parent observes deletion |
| MCP framing | Request line, JSON depth, and result limit are bounded | Oversized, deeply nested, and limit `101` requests are rejected |
| MCP errors | Expected input errors stay actionable; unexpected details are not returned | Injected runtime secret does not reach JSON-RPC output |
| Operator files | Snapshot and restore stay under the configured I/O root | Paths outside the root are rejected |
| Provider connections | MCP callers select a provider, not an endpoint or credential | URL/key overrides are rejected; trusted provider config is used |
| Provider governance | Numeric trust values must be finite | `NaN` is rejected |
| LLM benchmarks | Generated answers remain pending until judged | Pending records do not count as failures or accuracy |
| Public claims | Hosted judge output requires review | `public_benchmark_claim` remains `false` |

Local and private provider endpoints remain valid. The security boundary is who configures the connection, not whether the endpoint is public.

## Merkle v2 Disposition

Do not change roots in this candidate.

The current tree combines fixed-width hexadecimal child hashes, so the review's variable-length concatenation example is not the demonstrated receipt vulnerability. The concrete v1 ambiguity is shape binding: because an odd final leaf is duplicated, `[a, b, c]` and `[a, b, c, c]` produce the same root.

A v2 design should still add leaf/node/root domain separation, leaf position, and explicit leaf count. It can ship only when all of these are true:

1. Hard-coded v1 roots and proofs remain valid.
2. New receipts record a distinct algorithm identifier.
3. Verification dispatches from each receipt's recorded algorithm.
4. One bundle can verify mixed v1 and v2 receipts.
5. Snapshot, restore, handoff, and Treeship export preserve the algorithm identifier.
6. Historical receipts are never rewritten.

## Next Security Slices

1. Replace unpinned installer execution with a versioned artifact and checksum or a pinned source revision.
2. Bind provider credentials to an explicitly approved endpoint host while preserving localhost and private-network deployments.
3. Make generated config writes atomic and add backups for existing agent configuration files.
4. Specify and test Merkle v2 compatibility before implementing the new root algorithm.

In-process mutation APIs and operator MCP are trusted local capabilities, not remote authorization systems. Stronger authorization can be added, but it should not be misrepresented as a default-profile remote exploit.

## Verification

- Full Python suite: `1,260` tests passed with two expected optional skips.
- Built-in product eval: `11/11` passed.
- Strict release smoke: passed with public proof `6/6`, launch assets `8/8`, and return packet ready.
- Focused MCP, provider, runner, benchmark, and benchmark-script regressions: passed.
