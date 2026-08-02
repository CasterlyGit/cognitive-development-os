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
             -> read-only branch -> explicit promotion -> accepted plan version
             -> coherent graph cut -> dry-run PR plan + execution brief
             -> decision packet -> later, explicitly approved adapters

MVP: exactly two declared project scopes -> source-backed relationship proposal
   -> exact human decision -> dependency-closed plan -> route test double
   -> local verification record and decision timeline
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
| End-to-end dry run | [#8](https://github.com/CasterlyGit/cognitive-development-os/issues/8) | implemented | No external effects |
| Intent continuity, branch core | [#18](https://github.com/CasterlyGit/cognitive-development-os/issues/18) | implemented | Read-only child; human promotion only |
| Typed semantic confidence | [#20](https://github.com/CasterlyGit/cognitive-development-os/issues/20) | implemented | Interpretation evidence only; uncertain action becomes exploration |
| Redacted structural lineage export | [#22](https://github.com/CasterlyGit/cognitive-development-os/issues/22) | implemented | Pseudonymous references; raw source is schema-impossible |
| Atomic continuity stream revision | [#24](https://github.com/CasterlyGit/cognitive-development-os/issues/24) | implemented | Compare-and-append under the local ledger lock |
| Private-data and reasoning defaults | [#26](https://github.com/CasterlyGit/cognitive-development-os/issues/26) | implemented | Policy/audit only; legacy embedded data requires migration |
| Session-private content and structural lineage | [#30](https://github.com/CasterlyGit/cognitive-development-os/issues/30) | implemented | v2 path only; legacy data is unchanged |
| Accepted-plan-bound decision packet | [#32](https://github.com/CasterlyGit/cognitive-development-os/issues/32) | implemented | Pure local compile; no event writes or execution |
| Exact legacy migration planning | [#34](https://github.com/CasterlyGit/cognitive-development-os/issues/34) | implemented | Redacted plan only; mutation prerequisites remain gated |
| Project Decision Loop MVP | [#36](https://github.com/CasterlyGit/cognitive-development-os/issues/36) | implemented — review gate | Exactly two opt-in scopes; local JSONL; Paver/Codex test doubles only |
| Krish integration proposal | [#9](https://github.com/CasterlyGit/cognitive-development-os/issues/9) | contract implemented; integration deferred | Offline contract only; live path disabled |

The lean [capability execution graph](EXECUTION_GRAPH.md) separates merged,
review-gated, next, and deferred work without treating proposed code as active
runtime capability.

## Durable decisions

Architecture decisions are immutable Markdown records in
[`docs/decisions/`](decisions/README.md). Accepted records are superseded by a
new record rather than silently rewritten.

## Non-goals in the current phase

- Live Krish, GitHub, deployment, merge, or background-service adapters.
- Treating a PR or passing executor run as proof of the user outcome.
- Storing real voice recordings or private conversation fixtures in Git.
- Weakening human approval because a plan or model is confident.
