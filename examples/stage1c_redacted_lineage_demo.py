"""Export branch continuity while proving private fixture markers stay local."""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.continuity import IntentContinuity
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentExtractor,
)
from cognitive_os.privacy import PublicContinuityExporter
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "stage1c_redacted_lineage.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        ledger_path = Path(directory) / "events.jsonl"
        store = AppendOnlyEventStore(ledger_path)
        inbox = IntentInbox(store)
        graph = IntentGraph(fixture["graph_id"], store)
        sources = []
        for value in fixture["atoms"]:
            source = inbox.capture(
                value["raw_text"],
                source_id=value["source_id"],
                metadata={"owner": "PRIVATE_OWNER@example.invalid"},
            )
            sources.append(source)
            extracted = IntentExtractor().extract(source)[0]
            graph.add_atom(
                replace(
                    extracted,
                    atom_id=value["atom_id"],
                    state=AtomState(value["state"]),
                )
            )
        for dependent, prerequisite in fixture["dependencies"]:
            graph.add_dependency(dependent, prerequisite)

        continuity = IntentContinuity(fixture["continuity_id"], store)
        root = continuity.initialize_root(
            graph.snapshot(),
            branch_id=fixture["root_branch_id"],
            atom_ids=fixture["root_atom_ids"],
            operation_id="stage1c-root",
        )
        v1 = root.current_plan(fixture["root_branch_id"])
        continuity.open_child(
            graph.snapshot(),
            branch_id=fixture["child_branch_id"],
            parent_branch_id=fixture["root_branch_id"],
            anchor_atom_id="current_path",
            inherited_atom_ids=("current_path", "constraint"),
            expected_parent_plan_version_id=v1.plan_version_id,
            operation_id="stage1c-open-child",
        )
        continuity.propose_atom(
            graph.snapshot(),
            branch_id=fixture["child_branch_id"],
            atom_id="alternative",
            operation_id="stage1c-propose",
        )
        continuity.promote(
            graph.snapshot(),
            branch_id=fixture["child_branch_id"],
            selected_atom_ids=("alternative",),
            replace_atom_ids=("current_path",),
            expected_parent_plan_version_id=v1.plan_version_id,
            confirmation=ConfirmationRecord(
                actor_id="PRIVATE_HUMAN",
                authority=ConfirmationAuthority.HUMAN,
                channel="synthetic_fixture",
            ),
            operation_id="stage1c-promote",
        )

        restarted_store = AppendOnlyEventStore(ledger_path)
        packet = PublicContinuityExporter(fixture["export_scope_key"]).export(
            IntentGraph(fixture["graph_id"], restarted_store).snapshot(),
            IntentContinuity(
                fixture["continuity_id"], restarted_store
            ).snapshot(),
            IntentInbox(restarted_store).sources(),
        )
        packet_value = packet.to_dict()
        encoded = json.dumps(packet_value, sort_keys=True)
        output = {
            "schema_version": "1.0",
            "external_effects": False,
            "leak_sentinels_absent": all(
                marker not in encoded for marker in fixture["leak_sentinels"]
            ),
            "packet": packet_value,
        }
        print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
