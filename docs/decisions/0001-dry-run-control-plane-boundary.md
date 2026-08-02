# ADR 0001: Dry-run control-plane boundary

- Status: accepted
- Date: 2026-08-01

## Context

The product must learn to preserve conversational intent, expose dependencies,
and prepare bounded implementation work before it can safely invoke another
system. Krish is a separate user-facing assistant, and its live integration and
merge gates are not established contracts here.

## Decision

The initial runtime is local and dry-run only. It may preserve structured local
state, validate plans, and render review artifacts. It may not invoke Krish,
create external work, merge, deploy, or run as a background service.

Intent confirmation and effect authorization remain separate. A later live
adapter requires a versioned contract, idempotency, external-state
reconciliation, exact-effect approval, and a mechanically enforced human-only
merge path.

## Consequences

The first useful product is a reviewable decision packet rather than autonomous
execution. Integration work is slower by design, but unsafe assumptions become
testable before external effects exist.

## Verification

Current layer demos run from synthetic fixtures in temporary directories. Tests
and CI require no network service, credentials, or Krish checkout.
