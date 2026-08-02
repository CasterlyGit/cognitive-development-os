# Krish integration proposal — not authorized or enabled

## Status

This is a contract and rollout proposal only. It does not authorize or implement
a Krish connection, capability probe, issue creation, executor queue, GitHub
write, merge, credential access, or background service. Krish remains the
eventual user-facing local assistant; Cognitive Development OS remains its
control-plane architecture, and Codex remains a bounded implementation executor.

## Proposed boundary

The control plane would send a versioned `KrishHandoffProposal` to a future
approved local Krish service. The handoff carries the accepted intent and plan
identifiers, a canonical plan digest, exact target project and owned paths,
acceptance/evidence contracts, exclusions, risk, permission class, and required
merge policy. Credentials never enter the handoff.

Version 1 in this repository permits only `draft_issue_proposal` with
`P1_draft_only`, no approval receipt, and `human_only` as the required merge
policy. Unknown major versions or permission semantics fail closed.

## Idempotency and state reconciliation

The idempotency key is SHA-256 over the canonical effect payload. Any change to
intent, plan digest, target, scope, evidence, exclusions, risk, permission, or
merge policy changes the key. Reusing a key with a different payload is a hard
conflict.

A future live adapter must reconcile before every create or retry:

1. Query external state by `handoff_id` and idempotency key.
2. Compare the canonical payload digest and version.
3. If the exact effect already exists, normalize current state without creating
   a duplicate.
4. If the key exists with a different digest, quarantine the handoff.
5. If state is missing or unparseable, stop; absence is not permission to retry.
6. Record a new attempt identifier without deleting prior failure evidence.

Normalized adapter events should be monotonic and include `accepted`, `blocked`,
`draft_rendered`, `issue_created`, `queued`, `implementation_ready`,
`verification_failed`, `stopped`, and `reconciled`. A PR URL is delivery state,
not outcome proof.

## Separate approval boundaries

| Proposed effect | Minimum class | Required evidence |
|---|---|---|
| Render a local Krish story draft | P1 | Valid v1 contract |
| Read a scoped capability snapshot | P0 plus approved service connection | Exact endpoint and data scope |
| Create one exact GitHub issue | P3 | Fresh receipt bound to repository, title/body digest, and owned paths |
| Queue that issue for execution | Separate P3 | Fresh receipt bound to issue identity and work packet digest |
| Open a PR | P3 | Adapter result plus exact branch/repository scope |
| Merge | P4, human-only | Not exposed to the OS integration identity |

Intent confirmation is never an effect receipt. Approval to create an issue is
not approval to queue it, open a PR, merge, or deploy.

## Mechanically enforced human-only merge

Live integration remains blocked until all of these are independently proven:

- Krish advertises `merge_policy: human_only` through a stable capability
  contract, not a prompt convention.
- The OS integration identity has no merge-capable token, command, or tool.
- Krish's automated reviewer cannot merge OS-originated work.
- Repository rules require a human-controlled merge path and cannot be bypassed
  by the adapter identity.
- An integration test attempts direct and indirect merge paths and proves each
  is denied.
- Changing merge policy invalidates compatibility and quarantines the adapter.

## Proposed rollout gates

1. **Contract fixtures (current):** validate offline draft payloads and degraded
   capability snapshots. No Krish access.
2. **Read-only capability probe:** requires new authorization, a stable local
   service endpoint, scoped identity, lifecycle ownership, and privacy review.
3. **Draft rendering:** compare a local Krish Subsystem Story against the source
   plan; still no GitHub write.
4. **Explicit issue creation:** only after exact P3 receipt and reconciliation.
5. **Separate executor queue:** only after a second exact P3 receipt.

No rollout gate adds merge permission. Background operation is a separate future
decision.

## Material decisions before implementation

The recommended next decision is whether to design the future integration around
a narrow local service surfaced through a Codex plugin/MCP, or a separately
approved local CLI contract. That choice must settle identity, process lifecycle,
state scope, and consent before code is added. No choice is needed in this phase;
the live path remains disabled.
