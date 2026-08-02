# ADR 0004: Public lineage export boundary

- Status: proposed
- Date: 2026-08-02

## Context

Branch and plan evidence must be reviewable without placing private source or
stable local identifiers in public artifacts. Redacting values after building a
raw payload is fragile because a new field can accidentally escape the filter.
The vision already requires private source to remain private by default, while
retention duration, deletion behavior, and archived search remain human choices.

## Decision

Define a separate typed public schema that has no fields for raw source, atom
statements, source spans, metadata, timestamps, content hashes, or local IDs.
Before rendering, validate local source digests, exact atom/source spans, graph
lineage, branch lineage, immutable plan lineage, and current-plan pointers.

Replace every source, atom, branch, plan, and continuity identifier with a
deterministic HMAC reference under a local 256-bit export-scope key. The key is
not emitted; only its public scope fingerprint is. A different key yields
unlinkable references. Requests to include raw source or statements fail closed
rather than selecting a broader schema.

## Consequences

- Public review can show classifications, confidence, branch structure,
  promotion, supersession, and current-plan state without source content.
- The packet does not expose the key, local IDs, or source/content hashes needed
  to recover or correlate private records.
- Reviewers who need exact private source must use a separate future local
  interface under a policy not defined here.
- This decision does not choose retention, deletion, metadata allowlists,
  archived search, cross-project export, or any external publication action.

## Verification

Tests cover leak sentinels and forbidden schema fields, scope unlinkability,
deterministic restart export, raw-export rejection, missing/duplicate/corrupt
source, atom/span mismatch, branch/plan lineage mismatch, and invalid current
plan pointers. The synthetic demo reports no external effect.

## Supersession

None. A later accepted ADR may supersede this proposal while retaining it.
