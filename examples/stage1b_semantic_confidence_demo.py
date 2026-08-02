"""Extract typed confidence without turning confidence into authority."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.intents import IntentExtractor, IntentLifecycle
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "stage1b_semantic_confidence.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        ledger_path = Path(directory) / "events.jsonl"
        store = AppendOnlyEventStore(ledger_path)
        source = IntentInbox(store).capture(
            fixture["raw_text"],
            source_id=fixture["source_id"],
            metadata={"fixture": "stage1b_synthetic"},
        )
        atoms = IntentExtractor().extract(source)
        lifecycle = IntentLifecycle(store)
        for atom in atoms:
            lifecycle.propose(atom)
        observed = [
            {
                "kind": atom.kind.value,
                "band": atom.semantic_confidence.band.value,
            }
            for atom in atoms
        ]
        restarted = IntentLifecycle(AppendOnlyEventStore(ledger_path))
        packet = {
            "schema_version": "1.0",
            "external_effects": False,
            "expected_classification_matches": observed == fixture["expected"],
            "atoms": [atom.to_dict() for atom in atoms],
            "actionable_before_human_confirmation": [
                atom.atom_id for atom in lifecycle.actionable_atoms()
            ],
            "restart_preserves_confidence": all(
                restarted.current(atom.atom_id).semantic_confidence
                == atom.semantic_confidence
                for atom in atoms
            ),
        }
        print(json.dumps(packet, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
