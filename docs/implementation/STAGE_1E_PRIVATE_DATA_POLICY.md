# Stage 1E — Conservative private-data policy

## Outcome

The control plane now has typed conservative defaults for raw retention,
deletion planning, archived search, and reasoning scope:

- raw source is session-only unless local, expiring persistence is explicitly
  approved for no more than 30 days;
- deletion produces only an exact-source, digest-bound, reversible seven-day
  quarantine plan after verifying each source in the local ledger;
- irreversible purge is rejected because no purge executor or exact effect
  receipt exists;
- structural search excludes archived and discarded branches by default;
- archived search must name exact branch identifiers and never accepts raw text;
- reasoning is single-project unless an approved policy enumerates every
  project; and
- wildcard identifiers and ambient scope fail closed.

The read-only legacy audit reports only private field names and aggregate event
counts. It intentionally proves that the current ledger still embeds raw source,
statement, and metadata fields, so storage migration remains required.

## Verification

```bash
python3 -m unittest -v tests.test_data_policy
python3 -m unittest discover -v
python3 -m examples.stage1e_private_data_policy_demo
```

Expected: 6 focused tests and 104 total tests pass. The demo shows session-only
retention, active-only default search, exact archived scope, ambient
cross-project rejection, an effect-free quarantine plan, and a privacy-safe
legacy migration warning.

## Degraded paths

Tests reject missing or wildcard identifiers, ambient project scope,
cross-project policies without approval, persistence without approval, windows
outside 1–30 days, raw-text search, archive search without exact branches,
irreversible purge, and non-boolean archive flags.

## Public-data audit

The fixture and demo use synthetic project, branch, and source identifiers. The
legacy audit output contains no raw values or local event/source identifiers.

## Limits

This layer evaluates policy and prepares review artifacts only. It does not
move, encrypt, redact, compact, quarantine, delete, retain, or search data. The
current ledger still contains embedded private fields and must not be presented
as retention-compliant. No network, Krish, executor, or external adapter exists.
