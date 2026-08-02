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

## Current sequence

1. [#8 — End-to-end decision packet](https://github.com/CasterlyGit/cognitive-development-os/issues/8)
2. [#9 — Separate Krish integration proposal](https://github.com/CasterlyGit/cognitive-development-os/issues/9), only after the dry run is robust

## Workflow

- Use one issue and `codex/` branch per meaningful layer.
- Require tests, a runnable synthetic fixture, an implementation report, and a
  public-data audit before opening a PR.
- Low-risk repository-local layers may merge after CI and independent scope
  review pass.
- Risky, cross-cutting, permission-expanding, or external-effect work requires a
  human decision.
- Auto-merge is not an integration permission and never applies to Krish.
