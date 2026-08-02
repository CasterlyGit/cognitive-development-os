# Layer 1 — Intent Inbox and append-only event store

## Outcome

The local library can capture a synthetic chat, voice transcript, or note as an
immutable source record and append it to a restart-safe JSON Lines event ledger.
The exact source text and a SHA-256 content digest are preserved. Runtime data is
ignored by Git so real conversations are not accidentally committed.

## Invariants

- Events receive a monotonic sequence while holding an exclusive file lock.
- Each append is flushed and fsynced before it returns.
- Duplicate event identifiers are rejected.
- Partial, malformed, blank, or non-monotonic history fails closed.
- Empty source input creates no ledger.
- The store has no network, daemon, GitHub, or Krish integration.

## Verification

Run:

```bash
python3 -m unittest -v tests.test_store
```

Expected: 5 tests pass, including restart, duplicate, corrupt partial-line, and
non-monotonic-history paths.

Run the synthetic restart demo:

```bash
python3 -m examples.layer1_inbox_demo
```

Expected: one event, `source_preserved: true`, and a content digest. The demo
uses a temporary directory and leaves no conversational data behind.

## Review boundary

This layer includes only the typed source/event models, append-only ledger,
Intent Inbox, packaging metadata, and its tests. Intent interpretation and
confirmation are Layer 2.
