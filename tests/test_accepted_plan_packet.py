from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.accepted_plan_packet import (
    AcceptedPlanCompileRequest,
    AcceptedPlanPacketCompiler,
    AcceptedPlanPacketError,
)
from cognitive_os.compiler import CompileRequest, PermissionClass, RiskLevel
from cognitive_os.continuity import IntentContinuity
from cognitive_os.graph import (
    EdgeKind,
    GraphSnapshot,
    IntentCluster,
    IntentEdge,
    IntentGraph,
)
from cognitive_os.intents import (
    AtomKind,
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentAtom,
)
from cognitive_os.store import AppendOnlyEventStore


def atom(atom_id, kind=AtomKind.ACTIONABLE, state=AtomState.CONFIRMED):
    statement = "Synthetic accepted intent for %s." % atom_id
    return IntentAtom(
        atom_id=atom_id,
        source_id="src_%s" % atom_id,
        kind=kind,
        statement=statement,
        source_start=0,
        source_end=len(statement),
        state=state,
        requires_human_confirmation=kind
        in (
            AtomKind.ACTIONABLE,
            AtomKind.DECISION_REQUEST,
        ),
    )


class AcceptedPlanPacketCompilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        graph = IntentGraph("graph_accepted_packet", self.store)
        for item in (
            atom("foundation"),
            atom("old_path"),
            atom("new_path"),
            atom("outside"),
            atom("constraint", AtomKind.CONSTRAINT, AtomState.PROPOSED),
        ):
            graph.add_atom(item)
        graph.add_dependency("old_path", "foundation")
        graph.add_dependency("new_path", "foundation")
        self.graph = graph
        continuity = IntentContinuity("continuity_accepted_packet", self.store)
        root = continuity.initialize_root(
            graph.snapshot(),
            branch_id="accepted_path",
            atom_ids=("foundation", "old_path", "constraint"),
            operation_id="initialize-root",
        )
        self.v1 = root.current_plan("accepted_path")
        continuity.open_child(
            graph.snapshot(),
            branch_id="side_branch",
            parent_branch_id="accepted_path",
            anchor_atom_id="old_path",
            inherited_atom_ids=("old_path", "constraint"),
            expected_parent_plan_version_id=self.v1.plan_version_id,
            operation_id="open-side",
        )
        continuity.propose_atom(
            graph.snapshot(),
            branch_id="side_branch",
            atom_id="new_path",
            operation_id="propose-new",
        )
        promoted = continuity.promote(
            graph.snapshot(),
            branch_id="side_branch",
            selected_atom_ids=("new_path",),
            replace_atom_ids=("old_path",),
            expected_parent_plan_version_id=self.v1.plan_version_id,
            confirmation=ConfirmationRecord(
                actor_id="synthetic_owner",
                authority=ConfirmationAuthority.HUMAN,
                channel="unit_test",
            ),
            operation_id="promote-new",
        )
        self.v2 = promoted.current_plan("accepted_path")
        graph.define_cluster(
            "accepted_cluster",
            "Accepted plan",
            ("foundation", "new_path", "constraint"),
        )
        self.continuity = continuity.snapshot()
        self.snapshot = graph.snapshot()
        self.compiler = AcceptedPlanPacketCompiler()

    def tearDown(self):
        self.temp.cleanup()

    def request(self, target_atom_ids=("new_path",), version_id=None, branch=None):
        return AcceptedPlanCompileRequest(
            branch_id=branch or "accepted_path",
            expected_plan_version_id=version_id or self.v2.plan_version_id,
            compile_request=CompileRequest(
                title="Compile the accepted synthetic plan",
                outcome="Produce one accepted-plan-bound decision packet.",
                target_atom_ids=target_atom_ids,
                owned_paths=("cognitive_os/accepted_plan_packet.py",),
                acceptance_criteria=("Bind the exact accepted plan version.",),
                verification_steps=(
                    "python3 -m unittest -v tests.test_accepted_plan_packet",
                ),
                explicit_exclusions=("Do not execute the brief.",),
                risk=RiskLevel.LOW,
            ),
        )

    def test_promoted_current_plan_compiles_to_bound_draft_packet(self):
        packet = self.compiler.compile(self.snapshot, self.continuity, self.request())
        self.assertEqual(self.v2.plan_version_id, packet.binding.plan_version_id)
        self.assertEqual(2, packet.binding.plan_revision)
        self.assertEqual(
            ("foundation", "new_path"), packet.proposal.plan.selected_atom_ids
        )
        self.assertEqual(
            PermissionClass.DRAFT_ONLY, packet.proposal.plan.permission_class
        )
        self.assertTrue(packet.proposal.plan.dry_run)
        self.assertTrue(packet.proposal.plan.requires_human_approval_for_execution)
        self.assertEqual(
            "accepted_plan_dry_run_complete", packet.decision_packet.status
        )
        self.assertFalse(packet.external_effects)
        self.assertFalse(packet.decision_packet.external_effects)
        self.assertIn(
            self.snapshot.atoms["constraint"].statement,
            packet.proposal.plan.constraints,
        )

    def test_restart_and_repeat_are_deterministic_and_write_no_events(self):
        before = len(self.store.read_all())
        first = self.compiler.compile(
            self.snapshot, self.continuity, self.request()
        ).to_dict()
        restarted_store = AppendOnlyEventStore(self.path)
        restarted_graph = IntentGraph(
            "graph_accepted_packet", restarted_store
        ).snapshot()
        restarted_continuity = IntentContinuity(
            "continuity_accepted_packet", restarted_store
        ).snapshot()
        second = (
            AcceptedPlanPacketCompiler()
            .compile(restarted_graph, restarted_continuity, self.request())
            .to_dict()
        )
        self.assertEqual(first, second)
        self.assertEqual(before, len(self.store.read_all()))

    def test_stale_or_superseded_plan_version_fails_closed(self):
        with self.assertRaisesRegex(AcceptedPlanPacketError, "stale"):
            self.compiler.compile(
                self.snapshot,
                self.continuity,
                self.request(version_id=self.v1.plan_version_id),
            )
        corrupt = replace(
            self.continuity,
            current_plan_ids={"accepted_path": self.v1.plan_version_id},
        )
        with self.assertRaisesRegex(AcceptedPlanPacketError, "not accepted"):
            self.compiler.compile(
                self.snapshot,
                corrupt,
                self.request(version_id=self.v1.plan_version_id),
            )

    def test_child_branch_and_outside_target_fail_closed(self):
        with self.assertRaisesRegex(AcceptedPlanPacketError, "accepted-path"):
            self.compiler.compile(
                self.snapshot,
                self.continuity,
                self.request(branch="side_branch"),
            )
        with self.assertRaisesRegex(AcceptedPlanPacketError, "targets"):
            self.compiler.compile(
                self.snapshot,
                self.continuity,
                self.request(target_atom_ids=("outside",)),
            )

    def test_missing_or_changed_atom_lineage_fails_closed(self):
        atoms = dict(self.snapshot.atoms)
        del atoms["new_path"]
        missing = replace(self.snapshot, atoms=atoms)
        with self.assertRaisesRegex(AcceptedPlanPacketError, "missing"):
            self.compiler.compile(missing, self.continuity, self.request())

        atoms = dict(self.snapshot.atoms)
        atoms["new_path"] = replace(atoms["new_path"], source_id="different")
        changed = replace(self.snapshot, atoms=atoms)
        with self.assertRaisesRegex(AcceptedPlanPacketError, "lineage changed"):
            self.compiler.compile(changed, self.continuity, self.request())

    def test_unconfirmed_accepted_action_fails_closed(self):
        atoms = dict(self.snapshot.atoms)
        atoms["new_path"] = replace(
            atoms["new_path"], state=AtomState.AWAITING_CONFIRMATION
        )
        changed = replace(self.snapshot, atoms=atoms)
        with self.assertRaisesRegex(AcceptedPlanPacketError, "no longer confirmed"):
            self.compiler.compile(changed, self.continuity, self.request())

    def test_outgoing_dependency_and_cross_boundary_conflict_fail_closed(self):
        dependency = replace(
            self.snapshot,
            edges=self.snapshot.edges
            + (IntentEdge("new_path", "outside", EdgeKind.DEPENDS_ON),),
        )
        with self.assertRaisesRegex(AcceptedPlanPacketError, "dependency escapes"):
            self.compiler.compile(dependency, self.continuity, self.request())

        conflict = replace(
            self.snapshot,
            edges=self.snapshot.edges
            + (IntentEdge("new_path", "outside", EdgeKind.CONFLICTS_WITH),),
        )
        with self.assertRaisesRegex(AcceptedPlanPacketError, "conflict crosses"):
            self.compiler.compile(conflict, self.continuity, self.request())

    def test_cross_boundary_relevant_cluster_fails_closed(self):
        clusters = dict(self.snapshot.clusters)
        clusters["crossing"] = IntentCluster(
            cluster_id="crossing",
            label="Crossing cluster",
            member_atom_ids=("new_path", "outside"),
        )
        crossing = GraphSnapshot(
            graph_id=self.snapshot.graph_id,
            atoms=self.snapshot.atoms,
            edges=self.snapshot.edges,
            clusters=clusters,
        )
        with self.assertRaisesRegex(AcceptedPlanPacketError, "cluster crosses"):
            self.compiler.compile(crossing, self.continuity, self.request())


if __name__ == "__main__":
    unittest.main()
