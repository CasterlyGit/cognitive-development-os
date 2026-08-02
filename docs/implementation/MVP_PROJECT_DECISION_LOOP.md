# MVP: Project Decision Loop

Status: implemented locally for issue #36; review required before merge.

## Product claim

The MVP demonstrates one complete, local-only decision loop. A user explicitly
declares exactly two project scopes, reviews a source-backed cross-project
relationship proposal, makes an exact accept/reject decision, and receives a
dependency-closed draft plan, bounded route simulation, verification record,
and concise decision timeline.

This is not a dispatcher or external integration. Paver capability lookup and
Codex packet handling are in-process test doubles. The loop starts no process,
uses no network, scans no storage, and grants no execution authority.

## MVP acceptance ledger

| Capability | Evidence |
| --- | --- |
| Exactly two opt-in project scopes | Manifest validation rejects any other count and any intent outside the declared identities. |
| Source-backed relationship proposal | Both endpoint source IDs, rationale, typed confidence, and a deterministic proposal ID are required. |
| Human accept/reject | A non-empty human actor and exact proposal decision are persisted; a changed retry fails closed. |
| Coherent next move | The existing `PRCompiler` computes the dependency closure, excluded intent, constraints, and P1 draft-only brief. |
| Bounded route | Paver-match and Codex-fallback test doubles preserve exact project IDs, owned paths, and permission class. |
| Outcome evidence and continuity | Local JSONL events reconstruct the requested outcome, observed result, approval, blocker, next decision, and four-step timeline. |
| Degraded behavior | Focused tests cover rejection, evidence failure, scope escape, missing provenance, absent human identity, stale changes, and restart/idempotency. |

## Run the investor demo

The fixture is deliberately synthetic and the store is local:

```bash
python3 -m pip install -e .
cognitive-os mvp \
  --manifest examples/fixtures/mvp_project_decision_loop.json \
  --store /tmp/cognitive-os-mvp.jsonl \
  --decision accept \
  --human-actor demo_owner
```

Use a new store path and `--decision reject` to demonstrate the fail-closed
branch. For a restart/idempotency proof with a temporary ledger:

```bash
python3 -m examples.mvp_project_decision_loop_demo
```

The readable JSON result leads with the two scopes and proposal, then shows
included/excluded intent, uncertainty, the draft plan, route receipt,
verification, timeline, safety limits, and `external_effects: false`.

## Public-data and privacy audit

- The committed fixture names only fictional Atlas and Beacon projects.
- Every public source ID begins with `synthetic_`.
- No `raw_text`, source metadata, absolute local path, conversation, credential,
  external identifier, or real project content is present.
- User-supplied manifests and JSONL stores remain local and should use an
  ignored/private path. The MVP has no export command.
- The runtime reads only the explicitly supplied manifest and store paths; it
  performs no directory discovery.

The focused privacy assertion lives in
`tests/test_project_decision_loop.py::test_public_fixture_contains_only_declared_synthetic_provenance`.

## Known limits and post-MVP roadmap

The interface is JSON/CLI, evidence observations are fixture-provided rather
than independently collected, and only one exact two-project relationship is
reviewed per loop. There is no general multi-project field, live Paver or Codex
runtime, Control Room, Sidecar, adapter, Krish access, or external effect.

The single best next investment is an independent local evidence evaluator for
the same fixed loop. It should verify declared artifacts instead of accepting
fixture observations, while retaining the exact scopes, P1 boundary, and human
decision contract. Only after real decision-loop usage demonstrates an
interface problem should a minimal visual Control Room be considered. Permission
simulation and each external capability remain later, separately authorized
work.
