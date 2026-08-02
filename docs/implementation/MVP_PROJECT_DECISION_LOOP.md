# MVP: Project Decision Loop

Status: implemented locally for issues #36 and #38; review required before merge.

## Product claim

The MVP is one complete local decision product. A user sees intent from exactly
two opted-in synthetic project scopes, reviews a source-backed cross-project
relationship proposal, and makes an explicit Approve/Reject decision. The app
then shows the resulting dependency-closed plan or blocker, bounded route state,
verification evidence, next decision, and concise timeline.

The click is not a mock. It invokes the real `ProjectDecisionLoop`, persists
actual append-only JSONL events, compiles the real draft plan, and reconstructs
the same result after an app restart. Only external Paver/Codex execution is
simulated. The app binds to localhost, makes no outbound network call, scans no
ambient storage, and grants no execution authority.

## MVP acceptance ledger

| Capability | Evidence |
| --- | --- |
| Exactly two opt-in scopes | Manifest validation rejects any other count and any intent outside the declared identities. |
| Source-backed proposal | Both endpoint source IDs, rationale, typed confidence, and a deterministic proposal ID are required. |
| Human decision | Approve/Reject calls the real backend with an exact proposal ID and local decision token; changed retries fail closed. |
| Coherent next move | The existing `PRCompiler` computes the dependency closure, exclusions, and P1 draft-only brief. |
| Bounded route | Paver-match and Codex-fallback test doubles preserve exact project IDs, owned paths, and permission class. |
| Evidence and continuity | Local events reconstruct outcome, approval, evidence, blocker, next decision, and timeline after restart. |
| Guided interface | Bundled HTML/CSS/JavaScript explains projects, evidence, choice, result, and limits without a parallel workflow. |
| Degraded behavior | Tests cover rejection, evidence failure, scope escape, stale proposals, missing local token, divergent history, and restart. |

## Launch the investor demo

Install once:

```bash
python3 -m pip install -e .
```

Then use one launch command:

```bash
mkdir -p data && cognitive-os-ui --store data/project-decision-loop.jsonl --open
```

The browser opens the synthetic Atlas/Beacon relationship. Approve produces a
real local three-step dependency closure, simulated route receipt, three
evidence records, and four-event timeline. Reject records the exact human
decision and a transparent blocker without creating a plan or route. Use a
different ignored store path to demonstrate the opposite decision.

The JSON CLI remains available for machine inspection:

```bash
python3 -m examples.mvp_project_decision_loop_demo
```

## Real-app verification

- Focused HTTP/UI integration tests performed both real backend transitions.
- Approval was clicked in the running app and rendered the exact plan, P1 route
  receipt, evidence set, next decision, and four-event timeline.
- Rejection was clicked in a separate running app and rendered no plan, no
  route, a persisted blocker, and a three-event trace.
- The approval server was stopped and restarted against the same JSONL store;
  the approved outcome, plan, and timeline reappeared without another decision.
- Full-page visual inspection confirmed the initial and approved layouts; the
  browser console contained no errors.

## Public-data and privacy audit

- The committed fixture names only fictional Atlas and Beacon projects.
- Every public source ID begins with `synthetic_`; no raw transcript, metadata,
  credential, external identifier, absolute path, or real project content is
  present.
- User-supplied manifests and JSONL stores stay in an ignored/private path. The
  MVP has no export command.
- The runtime reads only the supplied manifest and store paths. It performs no
  directory discovery.
- The visual app serves bundled assets from `127.0.0.1`, has a same-origin
  content-security policy, and makes no outbound request.

The focused public-fixture assertion lives in
`tests/test_project_decision_loop.py::test_public_fixture_contains_only_declared_synthetic_provenance`.

## Known limits and post-MVP boundary

This is one guided synthetic decision, not a configurable dashboard. Evidence
observations are fixture-provided rather than independently collected, and only
one exact two-project relationship is reviewed per loop. There is no general
multi-project field, live Paver or Codex runtime, broad Control Room, Sidecar,
adapter, Krish access, or external effect.

The single best next investment is an independent local evidence evaluator for
the same fixed loop. It should verify declared artifacts while retaining the
exact scopes, P1 boundary, human decision contract, and simple guided interface.
Every external capability remains later, separately authorized work.
