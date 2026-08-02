# ADR 0002: Krish integration gates

- Status: proposed
- Date: 2026-08-01

## Context

The verified dry-run architecture can prepare a bounded plan, but Krish is a
separate user-facing assistant with its own runtime and GitHub workflow. A live
bridge would cross identity, state, credential, and consequential-effect
boundaries.

## Proposed decision

Adopt the versioned proposal contract and gated rollout in
[`KRISH_INTEGRATION_PROPOSAL.md`](../KRISH_INTEGRATION_PROPOSAL.md). Require
canonical idempotency, state reconciliation, distinct issue-create and queue
approvals, and mechanically enforced human-only merge before any live adapter.

## Consequences

The system may validate and render draft handoffs without gaining external
authority. Live integration requires a separate implementation decision and new
explicit authorization after Krish exposes a stable capability contract.

This ADR cannot become `accepted` merely because its offline tests pass.
