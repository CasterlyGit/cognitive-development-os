"""Show a side branch changing an accepted plan without rewriting history."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.continuity import IntentContinuity
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    AtomKind,
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentAtom,
)
from cognitive_os.models import SourceKind
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "stage1a_intent_continuity.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        ledger_path = Path(directory) / "events.jsonl"
        store = AppendOnlyEventStore(ledger_path)
        inbox = IntentInbox(store)
        graph = IntentGraph(fixture["graph_id"], store)
        for value in fixture["atoms"]:
            source = inbox.capture(
                value["statement"],
                kind=SourceKind.NOTE,
                source_id=value["source_id"],
                metadata={"fixture": "stage1a_synthetic"},
            )
            graph.add_atom(
                IntentAtom(
                    atom_id=value["atom_id"],
                    source_id=source.source_id,
                    kind=AtomKind(value["kind"]),
                    statement=value["statement"],
                    source_start=0,
                    source_end=len(value["statement"]),
                    state=AtomState(value["state"]),
                    requires_human_confirmation=value["kind"] in (
                        "actionable",
                        "decision_request",
                    ),
                )
            )
        for dependent, prerequisite in fixture["dependencies"]:
            graph.add_dependency(dependent, prerequisite)

        continuity = IntentContinuity(fixture["continuity_id"], store)
        root = continuity.initialize_root(
            graph.snapshot(),
            branch_id=fixture["root_branch_id"],
            atom_ids=fixture["root_atom_ids"],
            operation_id="demo-initialize-root",
        )
        original_plan = root.current_plan(fixture["root_branch_id"])
        child = fixture["child"]
        continuity.open_child(
            graph.snapshot(),
            branch_id=child["branch_id"],
            parent_branch_id=fixture["root_branch_id"],
            anchor_atom_id=child["anchor_atom_id"],
            inherited_atom_ids=child["inherited_atom_ids"],
            expected_parent_plan_version_id=original_plan.plan_version_id,
            operation_id="demo-open-child",
        )
        continuity.propose_atom(
            graph.snapshot(),
            branch_id=child["branch_id"],
            atom_id=child["proposal_atom_id"],
            operation_id="demo-propose-alternative",
        )
        promoted = continuity.promote(
            graph.snapshot(),
            branch_id=child["branch_id"],
            selected_atom_ids=(child["proposal_atom_id"],),
            replace_atom_ids=child["replace_atom_ids"],
            expected_parent_plan_version_id=original_plan.plan_version_id,
            confirmation=ConfirmationRecord(
                actor_id="synthetic_human",
                authority=ConfirmationAuthority.HUMAN,
                channel="fixture",
            ),
            operation_id="demo-promote-alternative",
        )
        event_count = len(store.read_all())
        replayed = continuity.promote(
            graph.snapshot(),
            branch_id=child["branch_id"],
            selected_atom_ids=(child["proposal_atom_id"],),
            replace_atom_ids=child["replace_atom_ids"],
            expected_parent_plan_version_id=original_plan.plan_version_id,
            confirmation=ConfirmationRecord(
                actor_id="synthetic_human",
                authority=ConfirmationAuthority.HUMAN,
                channel="fixture",
            ),
            operation_id="demo-promote-alternative",
        )
        restarted = IntentContinuity(
            fixture["continuity_id"], AppendOnlyEventStore(ledger_path)
        ).snapshot()
        current = promoted.current_plan(fixture["root_branch_id"])
        packet = {
            "schema_version": "1.0",
            "external_effects": False,
            "original_plan": promoted.plan_versions[
                original_plan.plan_version_id
            ].to_dict(),
            "current_plan": current.to_dict(),
            "branch": promoted.branches[child["branch_id"]].to_dict(),
            "idempotent_replay": {
                "event_count_before": event_count,
                "event_count_after": len(store.read_all()),
                "unchanged": replayed.to_dict() == promoted.to_dict(),
            },
            "restart_reconstruction_equal": restarted.to_dict() == promoted.to_dict(),
        }
        print(json.dumps(packet, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
