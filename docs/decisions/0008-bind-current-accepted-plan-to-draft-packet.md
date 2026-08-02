# ADR 0008: Bind the current accepted plan to a draft packet

- Status: accepted
- Date: 2026-08-02

## Context

The continuity aggregate preserves immutable accepted plan versions, while the
PR Compiler produces dependency-closed draft plans from a graph snapshot. Until
now those capabilities were independent: a compiled packet did not prove which
accepted plan version authorized its intent scope.

## Decision

Add a pure local bridge that accepts an exact branch identifier, expected
current plan-version identifier, graph snapshot, continuity snapshot, and
existing compiler request.

Only the active root accepted path may compile. The expected version must still
be current and accepted. Every atom/source lineage pair is checked against the
graph, and actionable intent must still be confirmed. The bridge projects an
accepted-only graph: an outgoing dependency, cross-boundary conflict, or
relevant cluster crossing the plan-version boundary fails closed.

The existing PR Compiler then produces a P1 draft-only plan and brief. A binding
records deterministic SHA-256 digests of the accepted version and scoped graph,
plus the compiled plan identifier. The decision packet reports no event write
or external effect and reiterates that execution requires separate exact
authorization.

## Consequences

- A reviewable packet now names the immutable accepted plan version it derives
  from instead of compiling from ambient graph state.
- Repeating compilation or reconstructing projections after restart produces
  the same packet and writes no events.
- Unaccepted intent cannot enter through dependency, conflict, or cluster
  relationships silently; the accepted plan must be revised explicitly.
- The packet is local and contains local lineage identifiers. It is not the
  public redacted lineage export.

## Verification

Focused tests cover promoted current-plan compilation, deterministic restart,
zero event writes, stale/superseded versions, child branches, outside targets,
missing or changed lineage, lost confirmation, and cross-boundary graph
relationships. A synthetic demo promotes a branch and compiles the resulting
accepted plan without executing it.

## Supersession

None. A later execution stage may consume the bound packet only after adding
effect-scoped approval, stale-state reconciliation, and outcome verification.
