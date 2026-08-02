# Capability execution graph

This is the lean delivery graph derived from `VISION.md`. It distinguishes
merged evidence from review gates and orders only the next useful dependencies.
GitHub issues and pull requests remain the delivery records.

## Implemented on `main`

| Capability | Evidence | Enables |
| --- | --- | --- |
| Immutable local source capture and restart | Layers 1–2 | Lineage-bearing intent |
| Conservative intent lifecycle and human confirmation | Layer 2 | Accepted actionable atoms |
| Dependency, conflict, and cluster graph | Layer 3 | Coherent graph cuts |
| Dry-run PR plan and bounded execution brief | Layer 4 | Reviewable implementation proposals |
| End-to-end decision packet | PR #13 | One local, restart-safe decision packet |
| Draft-only Krish contract | PR #14 | Validated contract evidence without an adapter |
| Local cognitive branches and plan versions | PR #19 | Read-only branching with explicit human promotion |
| Typed semantic confidence | PR #21 | Safe interpretation metadata and exploration fallback |
| Redacted lineage export | PR #23 | Structural review packet without raw source |
| Atomic continuity stream revision | PR #25 | Fail-closed concurrent continuity appends |

## Gated

| Gate | Depends on | What remains gated |
| --- | --- | --- |
| Issue #26: conservative private-data policy | Merged Stage 1 lineage/export | Review typed defaults and the truthful legacy-storage migration warning |

## Next

1. Review the Stage 1E policy/audit slice without treating it as storage
   enforcement.
2. Separate private content from immutable structural lineage, default new raw
   content to session-only, and provide a safe migration plan for legacy events.
3. Connect branch-aware accepted-plan versions to the accepted decision packet
   without enabling execution.
4. Begin the opt-in multi-project intent field with a single-project default,
   exact project enumeration, and evidence-backed relationship proposals.

## Deferred or rejected

Worker dispatch, the Paver runtime rail, outcome learning, Control Room/Sidecar
UI, effect simulators, and live adapters remain downstream of the internal
branch and verification path. Krish access, live GitHub/deployment/Codex effects,
the general Graph Architect Workbench, automatic merge, and ambient chat access
remain deferred or rejected exactly as recorded in `VISION.md`.
