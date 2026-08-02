# Issue-based roadmap

GitHub Issues define meaningful product work; pull requests deliver one coherent
verified slice. This file is an index, not a second tracker.

The [big vision](VISION.md) is the product north star and dependency roadmap.
This page remains the compact index of live GitHub delivery state.

## Completed

- [#1 — Intent Inbox and append-only source/event store](https://github.com/CasterlyGit/cognitive-development-os/issues/1)
- [#3 — Intent-atom extraction and confirmation lifecycle](https://github.com/CasterlyGit/cognitive-development-os/issues/3)
- [#6 — Living intent graph](https://github.com/CasterlyGit/cognitive-development-os/issues/6)
- [#7 — Dry-run PR-plan compiler and execution brief](https://github.com/CasterlyGit/cognitive-development-os/issues/7)

## Open review gates

1. [#8 — End-to-end decision packet](https://github.com/CasterlyGit/cognitive-development-os/issues/8) in PR #13
2. [#16 — North-star vision](https://github.com/CasterlyGit/cognitive-development-os/issues/16) in PR #17
3. [#9 — Separate Krish integration proposal](https://github.com/CasterlyGit/cognitive-development-os/issues/9) in PR #14, stacked on PR #13 and not authorized for integration

## Next execution path

1. [#18 — Stage 1A intent continuity and cognitive branch core](https://github.com/CasterlyGit/cognitive-development-os/issues/18) in [PR #19](https://github.com/CasterlyGit/cognitive-development-os/pull/19), stacked on the vision review branch but independent of PR #13/#14 runtime code
2. [#20 — Stage 1B typed semantic confidence](https://github.com/CasterlyGit/cognitive-development-os/issues/20) in [PR #21](https://github.com/CasterlyGit/cognitive-development-os/pull/21), stacked for linear review but independently testable
3. [#22 — Stage 1C redacted structural lineage export](https://github.com/CasterlyGit/cognitive-development-os/issues/22) in [PR #23](https://github.com/CasterlyGit/cognitive-development-os/pull/23), stacked on the typed Stage 1 state
4. [#24 — Stage 1D atomic continuity stream revisions](https://github.com/CasterlyGit/cognitive-development-os/issues/24), stacked as restart/idempotency hardening
5. Local retention, deletion, and archived-branch policy after the named human defaults are settled

The [capability execution graph](EXECUTION_GRAPH.md) records dependencies and
the precise boundary between these review gates and later stages.

## Workflow

- Use one issue and `codex/` branch per meaningful layer.
- Require tests, a runnable synthetic fixture, an implementation report, and a
  public-data audit before opening a PR.
- Low-risk repository-local layers may merge after CI and independent scope
  review pass.
- Risky, cross-cutting, permission-expanding, or external-effect work requires a
  human decision.
- Auto-merge is not an integration permission and never applies to Krish.
