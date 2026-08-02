import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.accepted_plan_packet import (
    AcceptedPlanCompileRequest,
    AcceptedPlanPacketCompiler,
)
from cognitive_os.compiler import CompileRequest, RiskLevel
from cognitive_os.continuity import IntentContinuity
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    AtomKind,
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentAtom,
)
from cognitive_os.store import AppendOnlyEventStore


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "stage1g_accepted_plan_packet.json"


def _atom(value):
    return IntentAtom(
        atom_id=value["atom_id"],
        source_id=value["source_id"],
        kind=AtomKind(value["kind"]),
        statement=value["statement"],
        source_start=0,
        source_end=len(value["statement"]),
        state=AtomState(value["state"]),
        requires_human_confirmation=value["kind"] in ("actionable", "decision_request"),
    )


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accepted-plan-events.jsonl"
        store = AppendOnlyEventStore(path)
        graph = IntentGraph(fixture["graph_id"], store)
        for value in fixture["atoms"]:
            graph.add_atom(_atom(value))
        for atom_id, prerequisite_id in fixture["dependencies"]:
            graph.add_dependency(atom_id, prerequisite_id)

        continuity = IntentContinuity(fixture["continuity_id"], store)
        root = continuity.initialize_root(
            graph.snapshot(),
            branch_id=fixture["root_branch_id"],
            atom_ids=fixture["root_atom_ids"],
            operation_id="initialize-root",
        )
        original = root.current_plan(fixture["root_branch_id"])
        child = fixture["child"]
        continuity.open_child(
            graph.snapshot(),
            branch_id=child["branch_id"],
            parent_branch_id=fixture["root_branch_id"],
            anchor_atom_id=child["anchor_atom_id"],
            inherited_atom_ids=child["inherited_atom_ids"],
            expected_parent_plan_version_id=original.plan_version_id,
            operation_id="open-binding-question",
        )
        continuity.propose_atom(
            graph.snapshot(),
            branch_id=child["branch_id"],
            atom_id=child["proposal_atom_id"],
            operation_id="propose-bound-packet",
        )
        promoted = continuity.promote(
            graph.snapshot(),
            branch_id=child["branch_id"],
            selected_atom_ids=(child["proposal_atom_id"],),
            replace_atom_ids=child["replace_atom_ids"],
            expected_parent_plan_version_id=original.plan_version_id,
            confirmation=ConfirmationRecord(
                actor_id="synthetic_owner",
                authority=ConfirmationAuthority.HUMAN,
                channel="synthetic_demo",
            ),
            operation_id="promote-bound-packet",
        )
        accepted = promoted.current_plan(fixture["root_branch_id"])
        graph.define_cluster(
            "accepted_packet_scope",
            "Accepted packet scope",
            accepted.atom_ids,
        )
        compile_value = fixture["compile"]
        request = AcceptedPlanCompileRequest(
            branch_id=fixture["root_branch_id"],
            expected_plan_version_id=accepted.plan_version_id,
            compile_request=CompileRequest(
                title=compile_value["title"],
                outcome=compile_value["outcome"],
                target_atom_ids=tuple(compile_value["target_atom_ids"]),
                owned_paths=tuple(compile_value["owned_paths"]),
                acceptance_criteria=tuple(compile_value["acceptance_criteria"]),
                verification_steps=tuple(compile_value["verification_steps"]),
                explicit_exclusions=tuple(compile_value["explicit_exclusions"]),
                risk=RiskLevel(compile_value["risk"]),
            ),
        )
        events_before = len(store.read_all())
        first = AcceptedPlanPacketCompiler().compile(
            graph.snapshot(), continuity.snapshot(), request
        )

        restarted_store = AppendOnlyEventStore(path)
        restarted = AcceptedPlanPacketCompiler().compile(
            IntentGraph(fixture["graph_id"], restarted_store).snapshot(),
            IntentContinuity(fixture["continuity_id"], restarted_store).snapshot(),
            request,
        )
        events_after = len(restarted_store.read_all())

    print(
        json.dumps(
            {
                "schema_version": "1.0",
                "binding_id": first.binding.binding_id,
                "accepted_plan_revision": first.binding.plan_revision,
                "compiled_plan_id": first.proposal.plan.plan_id,
                "decision_status": first.decision_packet.status,
                "draft_only": first.proposal.plan.dry_run,
                "requires_human_approval_for_execution": (
                    first.proposal.plan.requires_human_approval_for_execution
                ),
                "restart_deterministic": first.to_dict() == restarted.to_dict(),
                "event_writes_during_compile": events_after - events_before,
                "external_effects": first.external_effects,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
