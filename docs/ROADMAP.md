# Issue-based roadmap

GitHub Issues define meaningful product work; pull requests deliver one coherent
verified slice. This file is an index, not a second tracker.

## Completed

- [#1 — Intent Inbox and append-only source/event store](https://github.com/CasterlyGit/cognitive-development-os/issues/1)
- [#3 — Intent-atom extraction and confirmation lifecycle](https://github.com/CasterlyGit/cognitive-development-os/issues/3)

## Current sequence

1. [#6 — Living intent graph](https://github.com/CasterlyGit/cognitive-development-os/issues/6)
2. [#7 — Dry-run PR-plan compiler and execution brief](https://github.com/CasterlyGit/cognitive-development-os/issues/7), after #6
3. [#8 — End-to-end decision packet](https://github.com/CasterlyGit/cognitive-development-os/issues/8), after #7
4. [#9 — Separate Krish integration proposal](https://github.com/CasterlyGit/cognitive-development-os/issues/9), only after the dry run is robust

## Workflow

- Use one issue and `codex/` branch per meaningful layer.
- Require tests, a runnable synthetic fixture, an implementation report, and a
  public-data audit before opening a PR.
- Low-risk repository-local layers may merge after CI and independent scope
  review pass.
- Risky, cross-cutting, permission-expanding, or external-effect work requires a
  human decision.
- Auto-merge is not an integration permission and never applies to Krish.
