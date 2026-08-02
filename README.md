# Cognitive Development OS

Cognitive Development OS is a local-first control plane for turning messy,
ongoing conversational intent into dependency-aware, reviewable work. Krish is
the eventual user-facing personal AI OS; this project builds the bounded
planning, permission, review, and learning layer without modifying Krish.

The current implementation is an early dry-run prototype. It performs no
network calls, starts no background services, does not integrate with Krish,
and cannot merge or deploy anything.

## Evaluation path

1. Run the local verification suite. It requires Python 3.9+ and no runtime
   dependency outside the standard library:

   ```bash
   python3 -m unittest discover -v
   ```

2. Run the synthetic end-to-end dry run with its temporary ledger:

```bash
python3 -m pip install -e .
cognitive-os run \
  --manifest examples/fixtures/layer5_end_to_end.json \
  --store /tmp/cognitive-os-demo.jsonl
python3 -m examples.layer5_end_to_end_demo
```

3. Inspect the implementation reports for the [end-to-end decision
packet](docs/implementation/LAYER_5_END_TO_END.md), the [draft-only Krish
contract](docs/implementation/LAYER_6_KRISH_PROPOSAL.md), and the Stage 1
[continuity](docs/implementation/STAGE_1A_INTENT_CONTINUITY.md), [confidence](docs/implementation/STAGE_1B_SEMANTIC_CONFIDENCE.md), [redacted
lineage](docs/implementation/STAGE_1C_REDACTED_LINEAGE_EXPORT.md), and
[stream-revision](docs/implementation/STAGE_1D_STREAM_REVISION_ATOMICITY.md)
layers, plus the [private-data policy](docs/implementation/STAGE_1E_PRIVATE_DATA_POLICY.md)
and review-gated [session-private lineage](docs/implementation/STAGE_1F_SESSION_PRIVATE_LINEAGE.md).
Those reports link each implemented claim to focused tests and a
synthetic demonstration.
4. Read the [architecture index](docs/ARCHITECTURE.md), [decision records](docs/decisions/README.md), and [roadmap](docs/ROADMAP.md) for the current
decision boundaries and deferred work.

The remaining commands exercise focused Stage 1 demonstrations:

```bash
python3 -m examples.stage1a_intent_continuity_demo
python3 -m examples.stage1b_semantic_confidence_demo
python3 -m examples.stage1c_redacted_lineage_demo
python3 -m examples.stage1d_stream_revision_demo
python3 -m examples.stage1e_private_data_policy_demo
python3 -m examples.stage1f_session_private_lineage_demo
```

## Status

Implemented layers include a typed, append-only Intent Inbox/event ledger, a
conservative intent-atom lifecycle with explicit human confirmation boundaries,
and a restart-safe dependency/conflict/cluster intent graph. The dry-run PR
Compiler emits dependency-closed plans and bounded execution briefs; the local
CLI returns one decision packet. Stage 1 adds local cognitive branches,
deterministic confidence metadata, redacted structural lineage export, and
stream-revision atomicity. The repository also contains a validated,
draft-only Krish contract; it intentionally does not create an adapter.

None of these artifacts authorize writes to other repositories or services.
They do not make network calls, access Krish, invoke a coding agent, create or
merge pull requests, deploy, or start a background service.

Run the complete synthetic demo with a temporary private ledger:

```bash
python3 -m examples.layer5_end_to_end_demo
```

The legacy event path preserves exact input text. Keep real-input ledgers under
an ignored/private path such as `data/`; never commit personal conversations.
The opt-in Stage 1F v2 path instead keeps content in process-local session memory
and persists structural lineage only; it does not migrate legacy events.

Human confirmation, confidence, and a dry-run plan are not permission signals.
Children are read-only, and only explicit human promotion can create a
superseding parent version. Public lineage packets contain structural,
scope-specific pseudonymous references rather than raw source or local IDs.
Continuity commands bind to the exact projected stream revision, so competing
writes fail closed or reconcile only an exact idempotent retry.

Stage 1E adds typed conservative data-policy defaults:
session-only raw source, exact-scope structural search, single-project reasoning,
and effect-free reversible quarantine plans. Its audit deliberately reports that
the legacy ledger still embeds private fields; no deletion or retention
enforcement is claimed yet.

The Stage 1F review branch enforces session-only storage for new v2 capture and
extraction: raw source, statements, and metadata are absent from immutable
events, while digest-bound structure survives restart. Clearing the vault drops
process references but does not claim secure-memory erasure.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
