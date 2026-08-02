# ADR 0006: Conservative private-data and scope defaults

## Status

Accepted for the local dry-run prototype.

## Decision

Raw source defaults to session-only handling. Local persistence must be explicit
and time bounded. Auditing is read-only; exact-source quarantine is a reversible
plan only; purge is not implemented. Archived branches are excluded from search
by default. Reasoning is single-project unless exact project identifiers
enumerate a cross-project scope.

## Consequences

The prototype rejects wildcard and ambient scope, raw-text archived search,
invalid retention windows, and purge requests. No data is removed by this ADR.
