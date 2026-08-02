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

## Gated

| Gate | Depends on | What remains gated |
| --- | --- | --- |
| PR #13: end-to-end decision packet | Merged Layers 1–4 | Human review of the first cross-cutting dry-run packet |
| PR #17: public north-star vision | Merged evidence and truthful claim audit | Human/independent scope review of the governing specification |
| PR #19 / issue #18: branch continuity core | Merged Layers 1–4; stacked only for the PR #17 document | Read-only child branches, explicit promotion, immutable plan versions |
| PR #21 / issue #20: typed semantic confidence | Layer 2; stacked on Stage 1A for linear review | Confidence evidence, hedged-action fallback, historical replay compatibility |
| PR #23 / issue #22: redacted lineage export | Stage 1A and 1B typed state | Structural public review packet with scoped pseudonymous references and no raw fields |
| PR #14: disabled Krish contract proposal | PR #13 | Contract review only; no integration authority |

## Next

1. Merge or revise the Stage 1A branch core after review.
2. Define and test local retention, deletion, and archived-branch search after
   the human selects those privacy defaults.
3. Connect branch-aware accepted-plan versions to the decision packet after PR
   #13's interface is accepted. This must preserve the separate gate rather than
   importing its unreviewed code here.
4. Begin the opt-in multi-project intent field only after its reasoning scope is
   explicitly chosen.

## Deferred or rejected

Worker dispatch, the Paver runtime rail, outcome learning, Control Room/Sidecar
UI, effect simulators, and live adapters remain downstream of the internal
branch and verification path. Krish access, live GitHub/deployment/Codex effects,
the general Graph Architect Workbench, automatic merge, and ambient chat access
remain deferred or rejected exactly as recorded in `VISION.md`.
