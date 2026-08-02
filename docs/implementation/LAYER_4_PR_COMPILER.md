# Layer 4 — Dry-run PR Compiler

## Outcome

The PR Compiler converts one or more confirmed actionable targets into a
dependency-closed, conflict-free graph cut and emits two versioned artifacts:

- a `PullRequestPlan` describing outcome, ordered atoms, dependencies,
  constraints, exclusions, acceptance evidence, risk, permission, and routes;
- an `ExecutionBrief` giving bounded owned paths, ordered work, provenance,
  verification, exclusions, stop conditions, and an explicit permission boundary
  to a later Codex executor.

Artifact identifiers are deterministic hashes of canonical plan inputs. The
route plan records Sol/medium for architecture, Terra/high for implementation,
and Luna/low for structured status. Every proposal remains `P1_draft_only`,
`dry_run: true`, and requires human approval before any execution effect.

## Verification

```bash
python3 -m unittest -v tests.test_compiler
python3 -m unittest discover -v
python3 -m examples.layer4_compiler_demo
```

Expected: 10 compiler tests and 35 total tests pass. The demo prints a versioned
plan and brief selecting `typed_models` before `compile_cut`, carrying the
dry-run constraint and the unselected live-creation conflict into exclusions.

## Degraded paths

Compilation fails closed for missing or unconfirmed targets/dependencies,
non-actionable dependencies, internal conflicts, oversized cuts, unsafe or
ambiguous owned paths, blank fields, and missing acceptance/verification
contracts.

## Limits

This compiler creates in-memory/printed planning artifacts only. It does not
create a branch, GitHub issue, pull request, commit, queue entry, Krish handoff,
or other external effect. The repository's own development PR workflow is
separate from this product runtime.
