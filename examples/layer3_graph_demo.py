"""Build and restart a living intent graph from a synthetic conversation."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentExtractor,
    IntentLifecycle,
)
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "layer3_graph.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        path = Path(directory) / "events.jsonl"
        store = AppendOnlyEventStore(path)
        source = IntentInbox(store).capture(
            fixture["raw_text"], source_id=fixture["source_id"]
        )
        lifecycle = IntentLifecycle(store)
        atoms = IntentExtractor().extract(source)
        for item in atoms:
            lifecycle.propose(item)
        confirmation = ConfirmationRecord(
            actor_id="demo_owner",
            authority=ConfirmationAuthority.HUMAN,
            channel="synthetic_demo",
        )
        for index in fixture["confirm_action_indexes"]:
            atoms[index] = lifecycle.confirm(
                atoms[index].atom_id, confirmation=confirmation
            )

        graph = IntentGraph("graph_demo", store)
        for item in atoms:
            graph.add_atom(item)
        for dependent_index, prerequisite_index in fixture["dependencies"]:
            graph.add_dependency(
                atoms[dependent_index].atom_id, atoms[prerequisite_index].atom_id
            )
        for first_index, second_index in fixture["conflicts"]:
            graph.add_conflict(atoms[first_index].atom_id, atoms[second_index].atom_id)
        for cluster in fixture["clusters"]:
            graph.define_cluster(
                cluster["cluster_id"],
                cluster["label"],
                [atoms[index].atom_id for index in cluster["member_indexes"]],
            )

        restarted = IntentGraph("graph_demo", AppendOnlyEventStore(path)).snapshot()
        print(
            json.dumps(
                {
                    "atom_count": len(restarted.atoms),
                    "cluster_count": len(restarted.clusters),
                    "conflict_count": len(restarted.conflicts()),
                    "dependency_count": sum(
                        len(restarted.dependencies_of(atom_id))
                        for atom_id in restarted.atoms
                    ),
                    "restart_rebuilt_graph": True,
                    "external_effects": False,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
