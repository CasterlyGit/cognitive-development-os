# Cognitive Development OS

Cognitive Development OS is a local-first control plane for turning messy,
ongoing conversational intent into dependency-aware, reviewable work. Krish is
the eventual user-facing personal AI OS; this project builds the bounded
planning, permission, review, and learning layer without modifying Krish.

The current implementation is an early dry-run prototype. It performs no
network calls, starts no background services, does not integrate with Krish,
and cannot merge or deploy anything.

## Run the verified prototype

```bash
python3 -m unittest discover -v
python3 -m examples.stage1a_intent_continuity_demo
python3 -m examples.stage1b_semantic_confidence_demo
python3 -m examples.stage1c_redacted_lineage_demo
python3 -m examples.stage1d_stream_revision_demo
```

Implementation proceeds as independently reviewable layers. Reports and proof
for completed layers live in `docs/implementation/`.

Project direction and decisions are public in the [architecture index](docs/ARCHITECTURE.md),
[big vision](docs/VISION.md), [issue-based roadmap](docs/ROADMAP.md), and
[ADR index](docs/decisions/README.md).

## Status

Implemented layers include a typed, append-only Intent Inbox/event ledger, a
conservative intent-atom lifecycle with explicit human confirmation boundaries,
and a restart-safe dependency/conflict/cluster intent graph. A dry-run PR
Compiler now emits dependency-closed plans and bounded Codex execution briefs;
the end-to-end decision packet remains a separate review gate. The Stage 1A
review branch adds local cognitive branches and immutable accepted-plan versions:
children are read-only, and only explicit human promotion can create a
superseding parent version. None of these artifacts authorize writes to other
repositories or services.

The Stage 1B review branch adds typed, deterministic semantic-confidence
metadata. Hedged action falls back to exploration, historical atoms replay as
explicitly unassessed, and confidence never confirms intent or grants authority.

The Stage 1C review branch can render branch and plan lineage as a structural
public packet with scope-specific pseudonymous references. Its schema has no raw
source, statement, span, metadata, timestamp, content-hash, or local-ID field.

The Stage 1D review branch ties every continuity command to the exact stream
revision it projected, so a distinct concurrent writer fails the pending append
without poisoning history while an exact racing retry reconciles idempotently.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
