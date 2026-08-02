# Stage 1F — Session-private content and structural lineage

## Outcome

The new v2 capture/extraction path enforces the Stage 1E session-only default
for new local inputs. Exact source text and metadata live in a process-local
vault. Immutable events contain only strict structural descriptors for sources
and intent atoms: kinds, spans, state, semantic confidence, lineage identifiers,
and SHA-256 content bindings.

The structural snapshot reconstructs identically after restart. Content can be
materialized only while the same session vault holds the exact digest-bound
source. Ending the session clears those references; a fresh process can inspect
lineage but content access fails closed.

## Verification

```bash
python3 -m unittest -v tests.test_private_lineage
python3 -m unittest discover -v
python3 -m examples.stage1f_session_private_lineage_demo
```

Expected: 10 focused tests and 114 total tests pass. The demo reports one
restart-safe structural source, extracted atoms, forbidden payload fields
absent, private content unavailable after restart, and no external effects.

## Degraded paths

Tests reject persistent or cross-project policy, conflicting content or
metadata reuse, content/digest or statement/span mismatch, duplicate or
misrouted lineage, malformed structural types, unexpected private fields,
unknown private-lineage event types, and corrupt history. Exact retries remain
idempotent.

## Public-data audit

The fixture is synthetic. Ledger payloads are recursively scanned for
`raw_text`, `statement`, and `metadata`, and the Stage 1E auditor reports that
v2 events do not require legacy private-field migration. Content digests stay
local and are excluded from public lineage packets.

## Limits

This is an opt-in v2 API alongside the legacy path, not a migration. The legacy
ledger still embeds private content. The vault is process memory, not encrypted
or secure-erased memory. No expiring persistent vault, search, rewrite,
compaction, quarantine execution, purge, external service, Krish access,
executor, or adapter is implemented.
