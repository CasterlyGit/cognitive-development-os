# Architecture decision records

Material product, safety, data, or integration decisions are recorded here.
Accepted records are not rewritten to change their conclusion; a later record
may supersede one while preserving its provenance.

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-dry-run-control-plane-boundary.md) | accepted | Keep the initial control plane local and dry-run only |
| [0003](0003-cognitive-branch-continuity.md) | proposed | Isolate child branches and supersede accepted plans only through explicit promotion |

## Record template

Each ADR states its status, context, decision, consequences, verification, and
supersession relationship where applicable. Permission-expanding decisions need
explicit human approval before their status can become `accepted`.
