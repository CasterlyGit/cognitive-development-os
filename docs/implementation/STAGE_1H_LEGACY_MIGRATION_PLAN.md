# Stage 1H — Exact legacy migration plan

## Outcome

The control plane can now inventory an exact set of legacy sources and produce
a deterministic, privacy-redacted migration plan bound to the full ledger
digest. It validates private-bearing source, lifecycle, and graph events and
derives the structural v2 source and atom records they would require.

The plan truthfully remains non-executable. It lists six missing capabilities,
including structural lifecycle/graph projections, atomic replacement and
quarantine, rollback verification, content disposition, and exact human
approval. Planning writes nothing and reports no external effect.

## Verification

```bash
python3 -m unittest -v tests.test_legacy_migration
python3 -m unittest discover -v
python3 -m examples.stage1h_legacy_migration_plan_demo
```

Expected: 7 focused tests and 129 total tests pass. The demo shows one exact
scoped source, structural atom targets, one remaining unscoped private event,
raw values absent, deterministic restart, zero planning writes, and all
execution/effect flags false.

## Degraded paths

The planner rejects stale ledger digests, missing/duplicate/wildcard source
scope, cross-project policy, unknown private-bearing events, misrouted sources
or atoms, bad content digests/spans/types, confirmation mismatch, duplicate or
conflicting atom copies, invalid lifecycle transitions, and disagreement
between lifecycle and graph state.

## Public-data audit

The fixture is synthetic. Plan serialization is checked against its raw source
and metadata sentinel. Output includes private field names and local identifiers
because it is an exact local review artifact, but no private field value.

## Limits

This layer only returns a plan value. It does not create a replacement ledger,
rewrite an event, persist content, move or quarantine a file, compact history,
delete or purge anything, claim secure erasure, update lifecycle/graph readers,
call a network or Krish adapter, invoke an executor, or create an external
effect. A later concrete ledger mutation requires exact target confirmation.
