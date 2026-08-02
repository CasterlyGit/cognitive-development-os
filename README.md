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
python3 -m pip install -e .
cognitive-os run \
  --manifest examples/fixtures/layer5_end_to_end.json \
  --store /tmp/cognitive-os-demo.jsonl
```

Python 3.9 or newer is required. The project has no runtime dependency outside
the standard library.

Implementation proceeds as independently reviewable layers. Reports and proof
for completed layers live in `docs/implementation/`.

Project direction and decisions are public in the [architecture index](docs/ARCHITECTURE.md),
[issue-based roadmap](docs/ROADMAP.md), and [ADR index](docs/decisions/README.md).

## Status

Implemented layers include a typed, append-only Intent Inbox/event ledger, a
conservative intent-atom lifecycle with explicit human confirmation boundaries,
and a restart-safe dependency/conflict/cluster intent graph. A dry-run PR
Compiler now emits dependency-closed plans and bounded Codex execution briefs;
the local CLI connects the full dry run and returns one decision packet. None of
these artifacts authorize writes to other repositories or services.

Run the complete synthetic demo with a temporary private ledger:

```bash
python3 -m examples.layer5_end_to_end_demo
```

The event store preserves exact input text. Keep real-input ledgers under an
ignored/private path such as `data/`; never commit personal conversations.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
