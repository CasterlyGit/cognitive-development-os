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
| Retention, deletion, and archived-search policy | Local source/branch evidence | A human privacy decision before implementation |
| Cross-project intent field | Defined opt-in scope | Evidence-backed relationship proposals and conflict decisions |
| Live Krish or other external adapter | Internal verification and new explicit authorization | A separate capability and permission decision |

## Next

1. Define and test local retention, deletion, and archived-branch search after
   the human selects those privacy defaults.
2. Connect branch-aware accepted-plan versions to the decision packet only after
   a scoped review confirms the desired local interface; this must preserve the
   no-effect boundary.
3. Begin the opt-in multi-project intent field only after its reasoning scope is
   explicitly chosen.

## Deferred or rejected

Worker dispatch, the Paver runtime rail, outcome learning, Control Room/Sidecar
UI, effect simulators, and live adapters remain downstream of the internal
branch and verification path. Krish access, live GitHub/deployment/Codex effects,
the general Graph Architect Workbench, automatic merge, and ambient chat access
remain deferred or rejected exactly as recorded in `VISION.md`.
