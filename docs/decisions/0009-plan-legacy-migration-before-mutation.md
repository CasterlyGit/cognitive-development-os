# ADR 0009: Plan legacy migration before any mutation

- Status: accepted
- Date: 2026-08-02

## Context

Stage 1F prevents new v2 source and atom events from embedding raw content, but
the original ledger path still stores source text, statements, and metadata in
immutable events. Rewriting that ledger now would exceed the proven runtime:
the lifecycle and graph still require full atom payloads, no replacement-ledger
or quarantine executor exists, and no exact destructive effect is approved.

## Decision

Add a read-only planner for one single-project, session-only policy. A request
must name exact source identifiers and the expected SHA-256 digest of the full
legacy ledger. Any state change makes the request stale.

The planner strictly validates one stream-aligned source event per requested
source, its content digest, all known private-bearing atom copies, exact source
spans, semantic confidence, lifecycle state, and graph state. It rejects
unknown private-bearing event types, ambiguous copies, conflicting projections,
type confusion, and unsupported history.

Output includes only local identifiers, private field names, counts, structural
source/atom targets, and cryptographic event/ledger fingerprints. It never
includes raw source, statement, or metadata values. It explicitly lists the
missing lifecycle/graph projections, content disposition, atomic replacement
and quarantine executor, rollback verification, and exact human approval.
`executable`, `writes_performed`, and `external_effects` remain false.

## Consequences

- Legacy privacy debt is now measurable and exact without pretending it is
  already migrated.
- A later executor can require the plan's exact ledger digest and prerequisites
  instead of rediscovering scope during a destructive action.
- Event and source identifiers remain local review material; this is not a
  public export.
- No file is written, replaced, moved, quarantined, compacted, or deleted.

## Verification

Tests cover redaction, deterministic restart, zero writes, stale ledgers,
missing/duplicate/wildcard sources, cross-project scope, unknown private events,
corrupt content digests, type confusion, confirmation mismatch, conflicting
atom copies, and inconsistent lifecycle/graph state. A synthetic demo reports
the exact plan boundary and all effect flags as false.

## Supersession

None. Implementing any prerequisite or executor requires a separate reviewed
ADR and does not itself authorize a ledger mutation.
