# ADR 0006: Conservative private-data and reasoning-scope defaults

- Status: accepted
- Date: 2026-08-02

## Context

The branch and lineage model needs explicit defaults for raw retention,
deletion, archived search, and cross-project reasoning before storage migration
or multi-project work can be safe. The existing ledger embeds raw source,
statements, and metadata, so a policy model must identify that gap without
claiming that deletion already works.

## Decision

Raw source is session-only by default. Persisting raw content is a separate,
local-only opt-in with an exact approval identifier and a maximum 30-day
window. This does not authorize persistence yet.

Deletion first produces a deterministic, exact-source quarantine plan with a
seven-day recovery window. The plan is reversible and effect-free. Irreversible
purge is deliberately unimplemented and requires a separate exact human action.

Structural search sees active and promoted branches by default. Archived
branches require exact branch identifiers; discarded branches and raw-text
search are not included. Reasoning is single-project by default. A
cross-project policy must enumerate every project and cite an explicit scope
approval; wildcards and ambient local scanning are invalid.

## Consequences

- The product has conservative typed defaults without silently deleting data.
- A privacy-safe audit can report legacy private field names and counts without
  returning event identifiers, source identifiers, or field values.
- Current embedded raw payloads remain a migration blocker; the next storage
  layer must separate private content from immutable structural lineage.
- None of these defaults grant search, deletion, cross-project access, or an
  external effect.

## Verification

Tests cover bounded persistence, exact approvals, wildcard rejection,
single-project defaults, exact archived scope, raw-query rejection,
deterministic quarantine plans, purge rejection, and privacy-safe legacy
auditing. A synthetic demo produces no external effects.

## Supersession

None. A later accepted ADR may add an exact storage mechanism while preserving
these defaults and authority boundaries.
