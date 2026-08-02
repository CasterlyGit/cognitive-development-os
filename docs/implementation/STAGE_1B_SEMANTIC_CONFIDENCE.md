# Stage 1B — Typed semantic confidence

## Outcome

Every newly extracted atom carries a `SemanticConfidence` with a typed band,
integer score in thousandths, and a sorted set of privacy-safe signal labels.
The deterministic local extractor emits:

- high confidence for clear exploration, action, decision, or constraint form;
- medium exploration for hedged action or decision language;
- medium constraint for hedged safety language, preserving the safety signal;
- low exploration when no decisive signal exists; and
- explicit `unassessed` confidence when replaying historical `rules_v1` atoms.

Confidence is interpretation metadata only. Clear actions and decision requests
still await human confirmation, and system authority cannot confirm them.

## Verification

```bash
python3 -m unittest -v tests.test_semantic_confidence
python3 -m unittest discover -v
python3 -m examples.stage1b_semantic_confidence_demo
```

Expected: 9 focused tests and 57 total tests pass. The demo's four synthetic
segments resolve to medium exploration, high actionable-awaiting-confirmation,
high constraint, and low exploration. It reconstructs confidence after restart,
has no actionable atom before human confirmation, and reports
`external_effects: false`.

## Degraded paths

Tests cover hedged action, signal-free text, hedged constraint language,
confidence/authority separation, system confirmation rejection, legacy replay,
invalid score/band/signal combinations, graph restart, determinism, and
privacy-safe evidence labels.

## Public-data audit

The demo uses one synthetic source and fixed structural signal names. Confidence
evidence never includes raw source fragments. No private transcript, recording,
credential, user path, external payload, or live-integration claim is present.

## Limits

This is not a learned semantic model, probability calibration, evidence of user
outcome, or permission signal. It makes no network/model call, cannot confirm an
atom, does not change branch policy or PR #13, and grants no execution, adapter,
Krish, merge, deployment, or other external authority.
