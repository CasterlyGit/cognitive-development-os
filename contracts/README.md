# Contract proposals

Contracts in this directory are versioned, machine-readable boundaries. They do
not create adapters or grant authority.

- [`krish-handoff-v1.schema.json`](krish-handoff-v1.schema.json) permits only a
  local `draft_issue_proposal` with `P1_draft_only`, no approval receipt, and a
  required `human_only` merge policy.

Readers must reject unknown major versions, unknown permission semantics,
non-canonical idempotency keys, unsafe scope, and incompatible capability state.
See the [Krish integration proposal](../docs/KRISH_INTEGRATION_PROPOSAL.md).
