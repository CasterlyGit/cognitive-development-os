# Layer 6 — Krish integration proposal

## Outcome

The repository now contains a versioned, machine-readable draft handoff contract,
typed offline models, a synthetic proposal/capability snapshot, and a readiness
validator. The validator checks canonical idempotency, exact scope, draft-only
permission, version compatibility, separate create/queue capability, state
reconciliation, and mechanically human-only merge claims.

`IntegrationReadiness.live_enabled` is always `false` in this phase. Even an
ideal claimed capability snapshot retains the blocker that no live adapter
exists in this repository.

## Verification

```bash
python3 -m unittest -v tests.test_integration_contract
python3 -m examples.layer6_krish_contract_demo
python3 -m unittest discover -v
```

Expected on the clean `main` base: 9 focused tests and 44 total tests pass. The
demo reports a valid draft contract, multiple live-readiness blockers,
`live_enabled: false`, `krish_accessed: false`, and `external_effects: false`.

## Limits

No Krish source or runtime was read or changed. No service, adapter, credential,
GitHub effect, issue, queue, PR, merge, or background process is implemented.
ADR 0002 remains `proposed` and needs human review before later acceptance.
