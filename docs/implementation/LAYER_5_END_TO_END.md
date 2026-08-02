# Layer 5 — End-to-end dry run and decision packet

## Outcome

The local `cognitive-os` CLI now carries a versioned synthetic manifest through
the complete control-plane slice:

```text
raw conversation -> immutable source -> deterministic source-grounded atoms
-> explicit human confirmation -> dependency/conflict/cluster graph
-> dry-run PR plan + deep execution brief -> one-decision packet
```

Missing confirmation returns `awaiting_confirmation` and emits no graph or
proposal. A paused run can continue after the manifest receives the exact bounded
human confirmation. Completed runs are idempotent by `run_id` plus a canonical
input digest: identical restart/replay adds no events; changed input under a
completed identifier fails closed.

## Run

Use a temporary or ignored local ledger because the store preserves exact raw
source text:

```bash
python3 -m cognitive_os.cli run \
  --manifest examples/fixtures/layer5_end_to_end.json \
  --store /tmp/cognitive-os-demo.jsonl
```

Or run the self-checking temporary-ledger demo:

```bash
python3 -m examples.layer5_end_to_end_demo
```

## Verification

```bash
python3 -m unittest -v tests.test_pipeline
python3 -m unittest discover -v
```

Expected: 11 pipeline tests and 49 total tests pass. The demo reports
`dry_run_complete`, one primary decision, `external_effects: false`, stable
replay output, an unchanged event count, and a readable restarted store.

## Degraded paths

Tests cover missing/partial confirmation, system authority, confirmation scope
escape, paused-run continuation, identical replay, changed-input idempotency conflict, bad
indexes, dependency cycles, raw-source restart preservation, and CLI JSON output.

## Limits and data handling

The manifest still supplies explicit relationship indexes and bounded scope; no
semantic planner infers them yet. The deterministic rule extractor can
under-classify unfamiliar phrasing. Local ledgers contain raw source and must
remain private/ignored; public fixtures are synthetic. The CLI performs no
network, GitHub, Krish, merge, deployment, or background-service action.
