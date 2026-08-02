# ADR 0005: Atomic continuity stream revision

- Status: proposed
- Date: 2026-08-02

## Context

Deterministic operation IDs make exact retries idempotent, but they do not by
themselves prevent a distinct local writer from changing the continuity stream
between command validation and append. Appending a decision based on stale state
could make later reconstruction fail closed after the invalid event is already
durable.

## Decision

The append-only store accepts an optional expected revision for the target
stream. Readers take a shared file lock so they cannot observe a partial append.
Under the existing exclusive append lock, the store counts only events belonging
to the target stream and compares the actual revision before appending.

Every continuity command projects events and captures their count from the same
read, then supplies that revision to append. If another distinct command wins,
the loser appends nothing and returns a retryable stale-state error. If the same
operation wins concurrently, deterministic operation identity reconciles the
loser to the one existing event.

## Consequences

- Validation and durability share one optimistic-concurrency boundary.
- Unrelated source or graph streams do not cause false conflicts.
- Retry remains caller-controlled; this layer does not silently rerun a command
  against changed intent.
- This is local file-ledger concurrency, not distributed consensus, a lease, or
  an external-state guarantee.

## Verification

Store tests cover correct, stale, unrelated-stream, and invalid revisions.
Continuity tests inject a distinct competing event and an exact competing retry
between projection and append. The distinct loser remains retryable, the exact
retry produces one event, and both winning histories reconstruct successfully.

## Supersession

None. A later accepted ADR may supersede this proposal while retaining it.
