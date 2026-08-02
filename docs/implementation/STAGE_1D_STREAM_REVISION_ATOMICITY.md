# Stage 1D — Atomic continuity stream revisions

## Outcome

The append-only ledger now supports an optional stream-local expected revision.
Readers hold a shared file lock so a projection cannot observe a partial append.
The store evaluates the revision inside the same exclusive file lock used for
the fsynced append. Events on unrelated streams do not affect the comparison.

Every continuity command projects its aggregate and captures the stream event
count from one read. The command supplies that revision when appending. A
distinct concurrent event makes the append fail without writing; the caller can
retry after projecting fresh state. An exact concurrent retry is recognized by
its deterministic operation ID and returns the one winning event.

## Verification

```bash
python3 -m unittest -v tests.test_store tests.test_continuity
python3 -m unittest discover -v
python3 -m examples.stage1d_stream_revision_demo
```

Expected: 23 focused tests and 71 total tests pass. The demo shows a stale target
revision rejected without append, an unrelated stream causing no conflict, the
correct next revision succeeding, and `external_effects: false`.

## Degraded paths

Tests cover negative, non-integer, and boolean revisions; stale target state;
unrelated streams; a distinct writer injected between projection and append;
exact-operation racing replay; retry after a distinct winner; and restart
projection after both race shapes.

## Public-data audit

The fixture contains only synthetic stream and event labels. No raw private
source, local path, credential, external payload, or runtime identifier is
present.

## Limits

This is an optimistic local-ledger guard. It does not add distributed locking,
automatic retries, a background service, external reconciliation, PR #13 packet
integration, Krish access, execution, merge, deployment, or effect authority.
