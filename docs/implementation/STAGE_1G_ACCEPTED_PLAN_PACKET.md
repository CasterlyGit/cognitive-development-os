# Stage 1G — Accepted-plan-bound decision packet

## Outcome

The current accepted continuity plan can now produce one deterministic local
decision packet through the existing PR Compiler. The bridge requires the exact
current plan-version identifier, validates every atom/source lineage pair, and
limits compilation to an accepted-only graph scope.

The output binds the immutable plan version, scoped graph digest, and compiled
plan identifier. It remains P1 draft-only, requires separate human approval for
execution, writes no events, and reports no external effects.

## Verification

```bash
python3 -m unittest -v tests.test_accepted_plan_packet
python3 -m unittest discover -v
python3 -m examples.stage1g_accepted_plan_packet_demo
```

Expected: 8 focused tests and 122 total tests pass. The demo promotes a
synthetic child branch, compiles the resulting revision 2 accepted plan,
reconstructs an identical packet after restart, records zero compile-time event
writes, and reports no external effects.

## Degraded paths

The bridge rejects stale or superseded versions, child/read-only branches,
targets outside the accepted plan, missing or changed atom/source lineage,
actionable intent that is no longer confirmed, outgoing dependencies outside
the plan, cross-boundary conflicts, and relevant clusters with unaccepted
members. Existing PR Compiler validation still rejects unsafe paths, incomplete
evidence contracts, internal conflicts, and non-actionable graph cuts.

## Public-data audit

The fixture contains only synthetic intent and identifiers. The binding and
decision packet are local review artifacts, not public lineage packets. They do
not contain credentials, personal data, or real conversation content.

## Limits

This layer reads supplied snapshots and returns values. It does not capture
source, mutate continuity, persist a packet, promote a branch, invoke an
executor, create or merge a pull request, call Krish, deploy, or make a network
request. A draft packet is evidence of coherent accepted intent, not execution
permission or proof of an outcome.
