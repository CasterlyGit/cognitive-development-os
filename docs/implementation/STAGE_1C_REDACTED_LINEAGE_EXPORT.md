# Stage 1C — Redacted structural lineage export

## Outcome

`PublicContinuityExporter` converts the exact local Stage 1 graph/continuity
state into a typed structural packet. It first validates source content digests,
exact atom spans, graph/source identity, branch inheritance/proposals, immutable
plan lineage, supersession references, and current-plan pointers.

The public schema contains classifications, confidence, confirmation state,
branch structure, plan revisions, promotion/supersession, and current-plan
pointers. All identifiers become deterministic, export-scope-specific public
HMAC references under a local 256-bit export-scope key; the key is never emitted.
The schema contains no raw text, statement, source span, metadata,
timestamp, content hash, actor, operation ID, or local identifier. Requests for
raw source or statements are rejected.

## Verification

```bash
python3 -m unittest -v tests.test_privacy
python3 -m unittest discover -v
python3 -m examples.stage1c_redacted_lineage_demo
```

Expected: 9 focused tests and 66 total tests pass. The demo rebuilds graph and
continuity state after restart, exports two branches and two plan versions,
reports `raw_source_included: false`, `statements_included: false`,
`leak_sentinels_absent: true`, and `external_effects: false`.

## Degraded paths

Tests fail closed for raw/statement export requests, empty scopes, missing or
duplicate sources, mismatched content digests, incorrect atom spans, branch or
plan lineage drift, and invalid current-plan pointers. Different export scopes
produce disjoint public references; exact repeat and restart exports match.

## Public-data audit

The fixture intentionally contains synthetic `PRIVATE_*` values in source text,
metadata, local IDs, branches, continuity, and actor data. Tests and the demo
prove those sentinels are absent from serialized public output.

## Limits

This does not publish anything, reveal source locally, define retention or
deletion, search archives, allow metadata, export across projects, connect to PR
#13, render a UI, access Krish, invoke an executor, or grant any external effect.
