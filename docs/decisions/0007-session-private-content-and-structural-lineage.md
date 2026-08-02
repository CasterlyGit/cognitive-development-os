# ADR 0007: Session-private content and immutable structural lineage

- Status: accepted
- Date: 2026-08-02

## Context

The original event path embeds source text, extracted statements, and metadata
inside immutable events. Stage 1E therefore could define a session-only default
but could not enforce it for new capture. Rewriting the legacy ledger would mix
a useful new boundary with migration and deletion risk.

## Decision

Add a v2 local capture and extraction path with two stores:

- a process-local session vault holds the exact `SourceRecord`, including raw
  text and metadata; and
- the append-only ledger holds strict structural source and atom descriptors:
  type, state, exact spans, semantic confidence, lineage identifiers, and
  SHA-256 content bindings.

The v2 path accepts only the conservative session-only, single-project policy.
Persistent retention and cross-project scope fail closed. Materialization
requires the session vault to hold content matching every structural binding.
After session end or process restart, structural history reconstructs but
private content is unavailable.

Structural payload schemas reject missing or unexpected fields, malformed
types, private payload extensions, unknown v2 event types, duplicate lineage,
and mismatched stream routing. Exact retries reconcile without duplicate
events; conflicting identifier reuse fails closed.

## Consequences

- New v2 events do not persist raw text, statement text, or metadata.
- Immutable structural history remains restart-safe and reviewable.
- Content digests remain local correlation material and are not added to the
  public lineage export.
- Clearing the Python vault drops process references; it is not a secure-memory
  erasure guarantee.
- The legacy path and its embedded private fields remain unchanged. No
  migration, compaction, quarantine, deletion, or retention timer is implied.

## Verification

Focused tests scan every v2 payload for forbidden fields, audit the events with
the Stage 1E privacy auditor, exercise exact retry and conflicting reuse,
reconstruct structural snapshots after restart, and prove content access fails
after the vault is cleared. A synthetic demo repeats the boundary with a
temporary ledger and reports no external effects.

## Supersession

None. A later ADR may define a read-only legacy migration plan or an approved
expiring private vault without weakening this session-only default.
