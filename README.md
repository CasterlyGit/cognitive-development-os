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
```

Implementation proceeds as independently reviewable layers. Reports and proof
for completed layers live in `docs/implementation/`.

## Status

Implemented layers include a typed, append-only Intent Inbox/event ledger and a
conservative intent-atom lifecycle with explicit human confirmation boundaries.
Graph planning, PR-plan compilation, and the end-to-end decision packet are
being built as later layers. None of these plans authorize writes to other
repositories or services.

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
