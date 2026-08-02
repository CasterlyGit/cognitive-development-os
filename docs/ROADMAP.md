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
- [#8 — End-to-end decision packet](https://github.com/CasterlyGit/cognitive-development-os/issues/8)

## Open review gates

1. [#9 — Separate Krish integration proposal](https://github.com/CasterlyGit/cognitive-development-os/issues/9), documentation only; no live integration

## Next execution path

1. Define conservative local retention, deletion, and archived-search defaults.
2. Add the opt-in, project-scoped intent field with evidence-backed relationship proposals.
3. Connect accepted continuity plan versions to the verified decision packet without enabling execution.

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
