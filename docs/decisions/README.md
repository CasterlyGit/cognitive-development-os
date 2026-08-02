# Architecture decision records

Material product, safety, data, or integration decisions are recorded here.
Accepted records are not rewritten to change their conclusion; a later record
may supersede one while preserving its provenance.

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-dry-run-control-plane-boundary.md) | accepted | Keep the initial control plane local and dry-run only |
| [0002](0002-krish-integration-gates.md) | proposed | Gate any future Krish integration behind versioning, reconciliation, approvals, and human-only merge |
| [0003](0003-cognitive-branch-continuity.md) | accepted | Isolate child branches and supersede accepted plans only through explicit promotion |
| [0004](0004-public-lineage-export-boundary.md) | accepted | Export structural lineage through scoped references without raw-source fields |
| [0005](0005-continuity-stream-revision.md) | accepted | Bind continuity validation to an atomic stream-local append revision |
| [0006](0006-private-data-and-reasoning-scope-defaults.md) | accepted | Default to session-only raw data, exact archived scope, reversible deletion planning, and single-project reasoning |
| [0007](0007-session-private-content-and-structural-lineage.md) | accepted | Keep v2 private content in a process-local session vault while immutable events retain strict structural lineage |
| [0008](0008-bind-current-accepted-plan-to-draft-packet.md) | accepted | Bind the exact current accepted plan version and scoped graph to a draft-only decision packet |

## Record template

Each ADR states its status, context, decision, consequences, verification, and
supersession relationship where applicable. Permission-expanding decisions need
explicit human approval before their status can become `accepted`.
