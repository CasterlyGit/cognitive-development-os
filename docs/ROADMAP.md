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
- [#9 — Disabled Krish contract proposal](https://github.com/CasterlyGit/cognitive-development-os/issues/9)
- [#16 — North-star vision](https://github.com/CasterlyGit/cognitive-development-os/issues/16)
- [#18 — Intent continuity and cognitive branch core](https://github.com/CasterlyGit/cognitive-development-os/issues/18)
- [#20 — Typed semantic confidence](https://github.com/CasterlyGit/cognitive-development-os/issues/20)
- [#22 — Redacted structural lineage export](https://github.com/CasterlyGit/cognitive-development-os/issues/22)
- [#24 — Atomic continuity stream revisions](https://github.com/CasterlyGit/cognitive-development-os/issues/24)
- [#26 — Conservative private-data and reasoning-scope defaults](https://github.com/CasterlyGit/cognitive-development-os/issues/26)
- [#30 — Session-private content and structural lineage](https://github.com/CasterlyGit/cognitive-development-os/issues/30)
- [#32 — Accepted-plan-bound decision packet](https://github.com/CasterlyGit/cognitive-development-os/issues/32)
- [#34 — Exact legacy migration planning](https://github.com/CasterlyGit/cognitive-development-os/issues/34)

## Open review gates

1. [#36 — Local Project Decision Loop MVP](https://github.com/CasterlyGit/cognitive-development-os/issues/36), exactly two opted-in scopes and simulated routing only

## Next execution path

1. Review the fixed Project Decision Loop MVP without treating its simulated
   Paver/Codex route as execution authority.
2. Stop at the MVP boundary. If further investment is approved, add an
   independent local evidence evaluator to this same loop before broadening the
   graph, interface, or permissions.

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
