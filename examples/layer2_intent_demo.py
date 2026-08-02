"""Extract synthetic intent atoms and explicitly confirm one local action."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.intents import (
    AtomKind,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentExtractor,
    IntentLifecycle,
)
from cognitive_os.models import SourceKind
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "layer2_conversation.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        store = AppendOnlyEventStore(Path(directory) / "events.jsonl")
        source = IntentInbox(store).capture(
            fixture["raw_text"],
            kind=SourceKind(fixture["kind"]),
            source_id=fixture["source_id"],
            metadata=fixture["metadata"],
        )
        lifecycle = IntentLifecycle(store)
        atoms = IntentExtractor().extract(source)
        for atom in atoms:
            lifecycle.propose(atom)
        local_action = next(atom for atom in atoms if atom.kind == AtomKind.ACTIONABLE)
        before = list(lifecycle.actionable_atoms())
        lifecycle.confirm(
            local_action.atom_id,
            confirmation=ConfirmationRecord(
                actor_id="demo_owner",
                authority=ConfirmationAuthority.HUMAN,
                channel="synthetic_demo",
            ),
        )
        after = list(lifecycle.actionable_atoms())
        print(
            json.dumps(
                {
                    "atom_kinds": [atom.kind.value for atom in atoms],
                    "actionable_before_confirmation": len(before),
                    "actionable_after_confirmation": len(after),
                    "external_effects": False,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
