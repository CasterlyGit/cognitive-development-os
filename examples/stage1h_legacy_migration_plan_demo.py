import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.data_policy import PrivateDataPolicy
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentExtractor,
    IntentLifecycle,
)
from cognitive_os.legacy_migration import (
    LegacyMigrationPlanner,
    LegacyMigrationRequest,
)
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "stage1h_legacy_migration_plan.json"


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    policy = PrivateDataPolicy.conservative_default(fixture["home_project_id"])
    with TemporaryDirectory() as directory:
        path = Path(directory) / "legacy-events.jsonl"
        store = AppendOnlyEventStore(path)
        inbox = IntentInbox(store)
        source_value = fixture["source"]
        source = inbox.capture(
            source_value["raw_text"],
            source_id=source_value["source_id"],
            metadata=source_value["metadata"],
        )
        lifecycle = IntentLifecycle(store)
        graph = IntentGraph(fixture["graph_id"], store)
        for atom in IntentExtractor().extract(source):
            lifecycle.propose(atom)
            if atom.requires_human_confirmation:
                atom = lifecycle.confirm(
                    atom.atom_id,
                    confirmation=ConfirmationRecord(
                        actor_id="synthetic_owner",
                        authority=ConfirmationAuthority.HUMAN,
                        channel="synthetic_demo",
                    ),
                )
            graph.add_atom(atom)
        unscoped = fixture["unscoped_source"]
        inbox.capture(unscoped["raw_text"], source_id=unscoped["source_id"])

        planner = LegacyMigrationPlanner(policy)
        events = store.read_all()
        request = LegacyMigrationRequest(
            project_id=fixture["home_project_id"],
            source_ids=(source.source_id,),
            expected_ledger_sha256=planner.ledger_sha256(events),
        )
        event_count_before = len(events)
        first = planner.plan(request, events)
        serialized = json.dumps(first.to_dict(), sort_keys=True)

        restarted_store = AppendOnlyEventStore(path)
        restarted_planner = LegacyMigrationPlanner(policy)
        restarted_events = restarted_store.read_all()
        restarted = restarted_planner.plan(request, restarted_events)

    print(
        json.dumps(
            {
                "schema_version": "1.0",
                "plan_id": first.plan_id,
                "scoped_source_count": len(first.sources),
                "scoped_atom_count": len(first.atoms),
                "scoped_private_event_count": first.scoped_private_event_count,
                "unscoped_private_event_count": first.unscoped_private_event_count,
                "required_capability_count": len(first.required_capabilities),
                "raw_values_absent": (
                    source_value["raw_text"] not in serialized
                    and source_value["metadata"]["fixture_class"] not in serialized
                ),
                "restart_deterministic": first.to_dict() == restarted.to_dict(),
                "event_writes_during_planning": (
                    len(restarted_events) - event_count_before
                ),
                "executable": first.executable,
                "writes_performed": first.writes_performed,
                "external_effects": first.external_effects,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
