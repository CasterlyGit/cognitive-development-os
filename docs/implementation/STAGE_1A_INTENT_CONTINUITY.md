# Stage 1A — Intent continuity and cognitive branch core

## Outcome

The local continuity aggregate turns an accepted set of graph atoms into an
immutable plan version, opens a child branch at an exact atom and plan-version
anchor, and preserves explicitly inherited atom/source lineage. The child is
read-only. It may collect branch-only proposals, then be promoted, archived, or
discarded through an explicit event.

Human promotion is the only write-back path. It requires the exact current
parent version and creates a new accepted version that names the superseded
version and source branch. The prior version remains reconstructable. Every
operation has a deterministic event identity: exact retries do not append, and
changed input under the same operation ID fails closed.

## Verification

```bash
python3 -m unittest -v tests.test_continuity
python3 -m unittest discover -v
python3 -m examples.stage1a_intent_continuity_demo
```

Expected: 13 focused tests and 48 total tests pass. The demo shows revision 1
becoming `superseded`, revision 2 becoming `accepted`, the child becoming
`promoted`, identical event counts across replay, identical reconstruction after
restart, and `external_effects: false`.

## Degraded paths

Tests fail closed for missing or excessive inherited context, anchors outside
the inherited set, duplicate proposals, conflicting operation-ID reuse, stale
parent plans, system promotion authority, unconfirmed actionable proposals,
terminal branch writes, and unknown future history events. Failures append no
continuity event.

## Public-data audit

The fixture contains only synthetic statements and identifiers. It contains no
raw private transcript, recording, credential, user path, external payload, or
claim about a live integration.

## Limits

This slice does not perform semantic inference, define private retention or
archived-search defaults, connect to PR #13's pipeline, render a Sidecar UI,
dispatch a worker, invoke Paver at runtime, access Krish, call a network service,
or grant execution/effect authority. It proves one-level child branches from the
accepted path; nested branch trees remain later work. Intent promotion is not
effect approval.
