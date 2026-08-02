# Stage 1E — Private-data and scope defaults

`PrivacyPolicyService` provides typed, local-only defaults before any storage
change: raw source is session-only unless an explicit time-bounded local policy
is supplied; audits only identify legacy `raw_text` or `statement` fields; and
quarantine plans are deterministic, reversible proposals rather than effects.

Reasoning scope must name exact project identifiers. Archived search requires
exact branches and is structural-only. Wildcards, ambient scope, raw-text
search, invalid retention windows, and purge requests fail closed.

## Verification

```bash
python3 -m unittest -v tests.test_privacy_policy
python3 -m examples.stage1e_privacy_scope_demo
python3 -m unittest discover -v
```

The demo uses a temporary synthetic ledger and reports `external_effects: false`.

## Limits

This layer does not delete, quarantine, compact, migrate, or remove files. It
does not perform raw-text search, access another project unless the scope names
it, connect to Krish, call a network service, or grant external authority.
