# Architecture index

Cognitive Development OS is a local-first control plane between messy human
intent and bounded implementation work. Krish is the eventual user-facing local
assistant; Codex remains a bounded implementation executor. This repository does
not modify or replace either product.

The [big vision](VISION.md) defines the eventual Control Room and the status of
each major product concept. This document describes the structure implemented or
proposed in the repository today.

## System flow

```text
conversation -> immutable source -> intent atoms -> intent graph
             -> coherent graph cut -> dry-run PR plan + execution brief
             -> decision packet -> later, explicitly approved adapters
```

Human confirmation separates exploration from accepted actionable intent.
Consequential effects require a separate exact-effect approval boundary; intent
confirmation never implies permission to publish, merge, deploy, delete, spend,
message, or mutate another system.

## Runtime layers

| Layer | Public issue | Status | Boundary |
|---|---:|---|---|
| Intent Inbox and event store | [#1](https://github.com/CasterlyGit/cognitive-development-os/issues/1) | implemented | Local append-only capture |
| Intent atoms and lifecycle | [#3](https://github.com/CasterlyGit/cognitive-development-os/issues/3) | implemented | Human confirmation required |
| Intent graph | [#6](https://github.com/CasterlyGit/cognitive-development-os/issues/6) | implemented | Dependencies, conflicts, clusters |
| PR-plan compiler | [#7](https://github.com/CasterlyGit/cognitive-development-os/issues/7) | implemented | Draft artifacts only |
| End-to-end dry run | [#8](https://github.com/CasterlyGit/cognitive-development-os/issues/8) | planned | No external effects |
| Krish integration proposal | [#9](https://github.com/CasterlyGit/cognitive-development-os/issues/9) | deferred | Documentation only; new authorization required |

## Durable decisions

Architecture decisions are immutable Markdown records in
[`docs/decisions/`](decisions/README.md). Accepted records are superseded by a
new record rather than silently rewritten.

## Non-goals in the current phase

- Live Krish, GitHub, deployment, merge, or background-service adapters.
- Treating a PR or passing executor run as proof of the user outcome.
- Storing real voice recordings or private conversation fixtures in Git.
- Weakening human approval because a plan or model is confident.
