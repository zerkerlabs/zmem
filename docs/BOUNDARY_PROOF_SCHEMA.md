# Boundary Proof Schema

This is the proposed payload profile for proving actor-checker boundaries without turning the checker's own self-report into "proof." ZMem is the first concrete emitter, but the profile should remain provider-neutral so Treeship can support memory, guard, approval, and workflow checkers.

## Principle

Treeship proves the boundary record. It does not draw the boundary or judge the action.

ZMem decides which memory can influence an action. Treeship signs the receipt that makes that decision portable and verifiable.

## What This Must Prove

A boundary proof should prove:

- the actor's proposal or action was content-addressed;
- the checker was a distinct signed authority;
- the checker decision was signed by the checker or by the system acting as the checker;
- the policy reference and digest used for the decision were committed;
- the evidence diet was committed by digest;
- the evidence was frozen before or at the decision boundary;
- the decision was allow, deny, or partial;
- provider-specific outcome details were carried without making the core schema provider-specific.

It must not claim to prove:

- that the policy was correct;
- that the model's hidden reasoning was faithful;
- that an excluded input was never physically accessible unless that exclusion follows from an enforceable capture mechanism;
- that Treeship itself made the decision.

## Proven Zone

These fields are intended to be cryptographically meaningful.

```json
{
  "schema": "treeship.boundary.v1",
  "kind": "boundary.proof",
  "subject_ref": "art_<actor-signed-proposal-or-action>",
  "actor": {
    "uri": "agent://codex",
    "keyid": "key_actor..."
  },
  "checker": {
    "uri": "system://zmem",
    "keyid": "key_checker..."
  },
  "decision": "allow",
  "outcome": {
    "profile": "memory.proof",
    "injected": 3,
    "withheld": 2
  },
  "policy": {
    "ref": "policy://zmem/default#v1",
    "digest": "sha256:..."
  },
  "diet_root": "sha256:...",
  "diet": [
    {
      "type": "memory_bundle",
      "digest": "sha256:..."
    },
    {
      "type": "tool_result",
      "digest": "sha256:..."
    }
  ],
  "committed_at": {
    "anchor": "merkle://...#<index>",
    "ts": "2026-06-06T00:00:00Z"
  }
}
```

### Core Fields

- `subject_ref`: content-addressed reference to the actor proposal or action. Prefer a Treeship artifact ID when available.
- `actor.keyid`: key that signed or owns the actor proposal.
- `checker.keyid`: key that signed or owns the checker decision. A verifier can check that actor and checker keys differ.
- `decision`: neutral core decision. Use `allow`, `deny`, or `partial`.
- `outcome`: provider-specific result summary. For ZMem, this can include injected and withheld memory counts.
- `policy.digest`: digest of the policy used to ask the authorizing question.
- `diet`: typed evidence inputs committed by digest.
- `diet_root`: stable aggregate hash of the diet entries.
- `committed_at`: ordering anchor showing the diet was frozen at the decision boundary.

## Asserted Zone

Some useful user-facing facts are not proof by themselves. Keep them visibly separate.

```json
{
  "asserted": {
    "policy_excludes_echo": [
      "chain_of_thought",
      "scratchpad",
      "agent_self_narration"
    ],
    "capture_boundary": "mcp-runtime-hook",
    "notes": "Policy declares these classes forbidden; absence is checked against committed diet types."
  }
}
```

The verify page may render these facts, but it should label them as asserted or policy-derived, not as independently proven facts.

## Exclusion Rule

Do not make `verifier_excluded_inputs` a top-level proven field.

A free-form exclusion list is only a self-report. Instead:

1. the signed policy declares allowed and forbidden input classes;
2. the receipt commits the actual evidence diet by type and digest;
3. verification checks whether every committed diet type is allowed by the policy;
4. the verify page may render policy-forbidden classes as an explanation.

This turns "the checker says it did not look" into "the committed diet matches the policy's allowed input classes."

## Disagreement Receipts

Deny and partial decisions should be first-class. A proof system that records only approvals becomes a notary for the actor's story.

For ZMem, disagreement outcomes include:

- memory withheld;
- candidate quarantined;
- candidate rejected;
- memory revoked;
- no grounded memory found;
- memory dropped because of token budget;
- memory superseded by newer evidence.

These outcomes should be queryable over time so an operator can answer: has this checker ever produced a costly disagreement?

## Verify Page Requirements

Public verify pages should visually separate:

- proven fields: actor key, checker key, key distinction, decision, policy digest, diet root, committed anchor, signed time;
- asserted fields: policy exclusion echo, capture boundary notes, human-readable comments.

For a ZMem memory proof, the page should eventually summarize:

- system: `system://zmem`;
- kind/profile: `memory.proof`;
- decision: `allow`, `deny`, or `partial`;
- outcome: injected count, withheld count;
- policy digest;
- diet root;
- bundle hash;
- Merkle root;
- signed time;
- whether the proof verified client-side.

## Launch Sequence

Do not block ZMem launch on a new Treeship statement type.

Use this as a payload profile inside the existing receipt flow:

```bash
treeship attest receipt --system system://zmem --kind memory.proof --payload-file proof.json
```

Next steps:

1. Have ZMem emit a `treeship.boundary.v1` shaped payload for memory proof receipts.
2. Keep current ZMem fallback for older Treeship CLIs.
3. Add Treeship docs explaining boundary proofs and what they do not prove.
4. Add verify-page rendering for proven vs asserted zones.
5. Only after ZMem and a second checker system both emit the shape, consider a dedicated Treeship statement type.

