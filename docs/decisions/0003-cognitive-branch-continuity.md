# ADR 0003: Cognitive branch continuity and plan supersession

- Status: proposed
- Date: 2026-08-02

## Context

Side questions must not derail or silently rewrite the accepted intent path.
The system also needs to restart from durable evidence and reject a decision
made against an older parent state. PR #13's decision packet and PR #14's Krish
contract are separate review gates and are not dependencies for this local core.

## Decision

Use one append-only continuity aggregate for branch and accepted-plan events.
The root represents the accepted path. A child records its parent, exact anchor,
base accepted-plan version, and explicitly inherited atom/source lineage. It is
read-only: it can record branch-only proposals but cannot mutate the parent or
intent graph.

Promotion requires explicit human authority and the exact current parent-plan
version. One promotion event closes the child as promoted, supersedes the prior
accepted version, and creates a new immutable version. Stale state fails before
append. Caller-supplied operation identifiers map to deterministic event IDs;
an exact retry returns the existing result, while changed input under the same
identifier fails closed. Archive and discard are explicit terminal events.

## Consequences

- A review can compare the old plan, branch lineage, promotion, and new plan.
- Restart reconstructs accepted and superseded versions rather than trusting a
  mutable summary.
- Branches inherit only selected context; this slice does not define ambient
  transcript access, private retention duration, or archived-search defaults.
- Promotion changes accepted intent structure but grants no execution or
  external-effect permission.

## Verification

Focused tests cover isolation, lineage, authority, stale state, idempotent
replay, restart, invalid anchors, unconfirmed action, terminal closure, and
unknown history. A synthetic demo replaces one accepted atom through a child
branch while preserving the superseded version and producing no external
effect.

## Supersession

None. A later accepted ADR may supersede this proposal while retaining it.
