# Architecture decision records

Material product, safety, data, or integration decisions are recorded here.
Accepted records are not rewritten to change their conclusion; a later record
may supersede one while preserving its provenance.

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-dry-run-control-plane-boundary.md) | accepted | Keep the initial control plane local and dry-run only |
| [0002](0002-krish-integration-gates.md) | proposed | Gate any future Krish integration behind versioning, reconciliation, approvals, and human-only merge |
| [0003](0003-cognitive-branch-continuity.md) | proposed | Isolate child branches and supersede accepted plans only through explicit promotion |
| [0004](0004-public-lineage-export-boundary.md) | proposed | Export structural lineage through scoped references without raw-source fields |
| [0005](0005-continuity-stream-revision.md) | proposed | Bind continuity validation to an atomic stream-local append revision |
| [0006](0006-private-data-and-scope-defaults.md) | accepted | Keep private-data and reasoning scope defaults explicit and fail closed |

## Record template

Each ADR states its status, context, decision, consequences, verification, and
supersession relationship where applicable. Permission-expanding decisions need
explicit human approval before their status can become `accepted`.
