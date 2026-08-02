# Layer 2 — Intent atoms and confirmation lifecycle

## Outcome

The control plane conservatively extracts source-grounded intent atoms from
messy text and distinguishes exploration, actionable intent, constraints, and
decision requests. Every atom retains an exact character span into its immutable
source. Ambiguous text remains exploration.

Actionable and decision-request atoms begin in `awaiting_confirmation`. An
append-only lifecycle permits confirmation only through a typed record whose
authority is `human`; missing identity/channel, system authority, duplicate
proposal, replayed confirmation, and invalid transitions fail closed.

## Verification

```bash
python3 -m unittest -v tests.test_intents
python3 -m examples.layer2_intent_demo
```

Expected: 10 tests pass. The demo reports four atom kinds, zero actionable atoms
before confirmation, one afterward, and `external_effects: false`.

## Limits

The extractor is intentionally a deterministic `rules_v1` baseline, not a
semantic language model. It can under-classify unfamiliar actionable phrasing as
exploration; that conservative failure is safer than silently upgrading unclear
conversation into executable intent. Confirmation records are local evidence,
not cryptographic identity or permission receipts for consequential actions.

No atom causes execution, network access, GitHub mutation, or Krish mutation.
