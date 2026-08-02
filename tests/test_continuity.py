from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.continuity import (
    BranchAccess,
    BranchStatus,
    ContinuityError,
    IntentContinuity,
    PlanVersionStatus,
)
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    AtomKind,
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentAtom,
)
from cognitive_os.store import AppendOnlyEventStore


def atom(
    atom_id,
    *,
    state=AtomState.CONFIRMED,
    kind=AtomKind.ACTIONABLE,
    source_id=None
):
    statement = "Synthetic intent for %s." % atom_id
    return IntentAtom(
        atom_id=atom_id,
        source_id=source_id or "src_%s" % atom_id,
        kind=kind,
        statement=statement,
        source_start=0,
        source_end=len(statement),
        state=state,
        requires_human_confirmation=kind in (
            AtomKind.ACTIONABLE,
            AtomKind.DECISION_REQUEST,
        ),
    )


class InjectingStore(AppendOnlyEventStore):
    """Inject one competing append immediately before a revision-checked append."""

    def __init__(self, path):
        super().__init__(path)
        self.before_revision_append = None

    def append(self, *args, **kwargs):
        callback = self.before_revision_append
        if callback is not None and kwargs.get("expected_stream_revision") is not None:
            self.before_revision_append = None
            callback()
        return super().append(*args, **kwargs)


class IntentContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        self.graph = IntentGraph("graph_continuity", self.store)
        for item in (
            atom("foundation"),
            atom("current_path"),
            atom(
                "constraint",
                kind=AtomKind.CONSTRAINT,
                state=AtomState.PROPOSED,
            ),
            atom("alternative"),
            atom("another_alternative"),
            atom("unconfirmed", state=AtomState.AWAITING_CONFIRMATION),
        ):
            self.graph.add_atom(item)
        self.graph.add_dependency("current_path", "foundation")
        self.graph.add_dependency("alternative", "foundation")
        self.graph.add_dependency("another_alternative", "foundation")
        self.continuity = IntentContinuity("continuity_fixture", self.store)
        self.root = self.continuity.initialize_root(
            self.graph.snapshot(),
            branch_id="main_path",
            atom_ids=("foundation", "current_path", "constraint"),
            operation_id="initialize-root",
        )
        self.v1 = self.root.current_plan("main_path")
        self.human = ConfirmationRecord(
            actor_id="local_owner",
            authority=ConfirmationAuthority.HUMAN,
            channel="codex_task",
        )

    def tearDown(self):
        self.temp.cleanup()

    def open_branch(self, branch_id="side_question", operation_id="open-side"):
        return self.continuity.open_child(
            self.graph.snapshot(),
            branch_id=branch_id,
            parent_branch_id="main_path",
            anchor_atom_id="current_path",
            inherited_atom_ids=("current_path", "constraint"),
            expected_parent_plan_version_id=self.v1.plan_version_id,
            operation_id=operation_id,
        )

    def propose(self, branch_id="side_question", atom_id="alternative"):
        return self.continuity.propose_atom(
            self.graph.snapshot(),
            branch_id=branch_id,
            atom_id=atom_id,
            operation_id="propose-%s-%s" % (branch_id, atom_id),
        )

    def promote(
        self,
        branch_id="side_question",
        atom_id="alternative",
        expected_plan_id=None,
        operation_id="promote-side",
        confirmation=None,
    ):
        return self.continuity.promote(
            self.graph.snapshot(),
            branch_id=branch_id,
            selected_atom_ids=(atom_id,),
            replace_atom_ids=("current_path",),
            expected_parent_plan_version_id=(
                expected_plan_id or self.v1.plan_version_id
            ),
            confirmation=confirmation or self.human,
            operation_id=operation_id,
        )

    def test_child_has_precise_anchor_explicit_context_and_source_lineage(self):
        snapshot = self.open_branch()
        branch = snapshot.branches["side_question"]
        self.assertEqual(BranchAccess.READ_ONLY, branch.access)
        self.assertEqual(BranchStatus.ACTIVE, branch.status)
        self.assertEqual("main_path", branch.parent_branch_id)
        self.assertEqual("current_path", branch.anchor_atom_id)
        self.assertEqual(self.v1.plan_version_id, branch.base_plan_version_id)
        self.assertEqual(
            ("constraint", "current_path"), branch.inherited_atom_ids
        )
        self.assertEqual(
            ("src_constraint", "src_current_path"), branch.inherited_source_ids
        )

    def test_branch_proposal_does_not_rewrite_parent_or_graph(self):
        self.open_branch()
        graph_events_before = len(self.store.events_for("graph_continuity"))
        snapshot = self.propose()
        branch = snapshot.branches["side_question"]
        self.assertEqual(
            [("alternative", "src_alternative")],
            [(item.atom_id, item.source_id) for item in branch.proposals],
        )
        self.assertEqual(self.v1, snapshot.current_plan("main_path"))
        self.assertEqual(
            graph_events_before, len(self.store.events_for("graph_continuity"))
        )

    def test_human_promotion_creates_new_version_and_preserves_history(self):
        self.open_branch()
        self.propose()
        snapshot = self.promote()
        v2 = snapshot.current_plan("main_path")
        self.assertEqual(2, v2.revision)
        self.assertEqual(self.v1.plan_version_id, v2.supersedes_plan_version_id)
        self.assertEqual("side_question", v2.promoted_from_branch_id)
        self.assertEqual(
            ("constraint", "foundation", "alternative"), v2.atom_ids
        )
        self.assertEqual(
            PlanVersionStatus.SUPERSEDED,
            snapshot.plan_versions[self.v1.plan_version_id].status,
        )
        self.assertEqual(PlanVersionStatus.ACCEPTED, v2.status)
        self.assertEqual(
            BranchStatus.PROMOTED, snapshot.branches["side_question"].status
        )
        self.assertEqual(2, len(snapshot.plan_versions))

    def test_restart_reconstructs_identical_branch_and_plan_history(self):
        self.open_branch()
        self.propose()
        before = self.promote().to_dict()
        restarted = IntentContinuity(
            "continuity_fixture", AppendOnlyEventStore(self.path)
        )
        self.assertEqual(before, restarted.snapshot().to_dict())

    def test_exact_retry_is_idempotent_after_state_changes(self):
        self.open_branch()
        self.propose()
        promoted = self.promote()
        event_count = len(self.store.read_all())
        replayed = self.promote()
        self.assertEqual(event_count, len(self.store.read_all()))
        self.assertEqual(promoted.to_dict(), replayed.to_dict())

    def test_distinct_concurrent_writer_rejects_without_poisoning_history(self):
        self.open_branch("target", "open-target")
        self.open_branch("other", "open-other")
        racing_store = InjectingStore(self.path)
        racing = IntentContinuity("continuity_fixture", racing_store)

        def competing_archive():
            IntentContinuity(
                "continuity_fixture", AppendOnlyEventStore(self.path)
            ).archive(
                branch_id="other",
                actor_id="competing_writer",
                reason="Synthetic race winner.",
                operation_id="competing-archive",
            )

        racing_store.before_revision_append = competing_archive
        with self.assertRaisesRegex(ContinuityError, "changed during append"):
            racing.propose_atom(
                self.graph.snapshot(),
                branch_id="target",
                atom_id="alternative",
                operation_id="racing-proposal",
            )
        restarted = IntentContinuity(
            "continuity_fixture", AppendOnlyEventStore(self.path)
        ).snapshot()
        self.assertEqual(BranchStatus.ARCHIVED, restarted.branches["other"].status)
        self.assertEqual(BranchStatus.ACTIVE, restarted.branches["target"].status)
        self.assertEqual((), restarted.branches["target"].proposals)

        retried = racing.propose_atom(
            self.graph.snapshot(),
            branch_id="target",
            atom_id="alternative",
            operation_id="racing-proposal",
        )
        self.assertEqual(
            ("alternative",),
            tuple(item.atom_id for item in retried.branches["target"].proposals),
        )

    def test_exact_concurrent_retry_reconciles_to_one_event(self):
        self.open_branch("target", "open-target")
        racing_store = InjectingStore(self.path)
        racing = IntentContinuity("continuity_fixture", racing_store)
        graph_snapshot = self.graph.snapshot()

        def competing_exact_retry():
            IntentContinuity(
                "continuity_fixture", AppendOnlyEventStore(self.path)
            ).propose_atom(
                graph_snapshot,
                branch_id="target",
                atom_id="alternative",
                operation_id="same-racing-proposal",
            )

        before = len(self.store.events_for("continuity_fixture"))
        racing_store.before_revision_append = competing_exact_retry
        reconciled = racing.propose_atom(
            graph_snapshot,
            branch_id="target",
            atom_id="alternative",
            operation_id="same-racing-proposal",
        )
        after = len(self.store.events_for("continuity_fixture"))
        self.assertEqual(before + 1, after)
        self.assertEqual(
            ("alternative",),
            tuple(
                item.atom_id for item in reconciled.branches["target"].proposals
            ),
        )

    def test_operation_id_reuse_with_changed_input_fails_closed(self):
        self.open_branch()
        before = len(self.store.read_all())
        with self.assertRaisesRegex(ContinuityError, "different input"):
            self.continuity.open_child(
                self.graph.snapshot(),
                branch_id="different_branch",
                parent_branch_id="main_path",
                anchor_atom_id="current_path",
                inherited_atom_ids=("current_path",),
                expected_parent_plan_version_id=self.v1.plan_version_id,
                operation_id="open-side",
            )
        self.assertEqual(before, len(self.store.read_all()))

    def test_stale_branch_cannot_promote_after_parent_advances(self):
        self.open_branch("first", "open-first")
        self.propose("first", "alternative")
        self.open_branch("stale", "open-stale")
        self.propose("stale", "another_alternative")
        self.promote(
            branch_id="first",
            atom_id="alternative",
            operation_id="promote-first",
        )
        before = len(self.store.read_all())
        with self.assertRaisesRegex(ContinuityError, "stale"):
            self.promote(
                branch_id="stale",
                atom_id="another_alternative",
                operation_id="promote-stale",
            )
        self.assertEqual(before, len(self.store.read_all()))
        self.assertEqual(
            BranchStatus.ACTIVE,
            self.continuity.snapshot().branches["stale"].status,
        )

    def test_system_authority_cannot_promote(self):
        self.open_branch()
        self.propose()
        before = len(self.store.read_all())
        with self.assertRaisesRegex(ContinuityError, "human authority"):
            self.promote(
                confirmation=ConfirmationRecord(
                    actor_id="router",
                    authority=ConfirmationAuthority.SYSTEM,
                    channel="internal",
                )
            )
        self.assertEqual(before, len(self.store.read_all()))

    def test_unconfirmed_action_cannot_enter_accepted_plan(self):
        self.open_branch()
        self.propose(atom_id="unconfirmed")
        before = len(self.store.read_all())
        with self.assertRaisesRegex(ContinuityError, "unconfirmed"):
            self.promote(atom_id="unconfirmed")
        self.assertEqual(before, len(self.store.read_all()))

    def test_invalid_anchor_or_inheritance_fails_without_append(self):
        for inherited in (("constraint",), ("current_path", "alternative")):
            with self.subTest(inherited=inherited):
                before = len(self.store.read_all())
                with self.assertRaises(ContinuityError):
                    self.continuity.open_child(
                        self.graph.snapshot(),
                        branch_id="invalid-%d" % before,
                        parent_branch_id="main_path",
                        anchor_atom_id="current_path",
                        inherited_atom_ids=inherited,
                        expected_parent_plan_version_id=self.v1.plan_version_id,
                        operation_id="invalid-%d" % before,
                    )
                self.assertEqual(before, len(self.store.read_all()))

    def test_nested_child_is_outside_the_one_level_slice(self):
        self.open_branch()
        before = len(self.store.read_all())
        with self.assertRaisesRegex(ContinuityError, "accepted path"):
            self.continuity.open_child(
                self.graph.snapshot(),
                branch_id="nested",
                parent_branch_id="side_question",
                anchor_atom_id="current_path",
                inherited_atom_ids=("current_path",),
                expected_parent_plan_version_id=self.v1.plan_version_id,
                operation_id="open-nested",
            )
        self.assertEqual(before, len(self.store.read_all()))

    def test_archive_and_discard_are_explicit_terminal_events(self):
        self.open_branch("archived", "open-archived")
        archived = self.continuity.archive(
            branch_id="archived",
            actor_id="local_owner",
            reason="Keep for later review.",
            operation_id="archive-branch",
        )
        self.assertEqual(
            BranchStatus.ARCHIVED, archived.branches["archived"].status
        )
        self.open_branch("discarded", "open-discarded")
        discarded = self.continuity.discard(
            branch_id="discarded",
            actor_id="local_owner",
            reason="Rejected experiment.",
            operation_id="discard-branch",
        )
        self.assertEqual(
            BranchStatus.DISCARDED, discarded.branches["discarded"].status
        )
        with self.assertRaisesRegex(ContinuityError, "not active"):
            self.continuity.propose_atom(
                self.graph.snapshot(),
                branch_id="discarded",
                atom_id="alternative",
                operation_id="write-after-discard",
            )

    def test_unknown_history_event_fails_closed(self):
        self.store.append("continuity_fixture", "branch.future_event", {})
        with self.assertRaisesRegex(ContinuityError, "unsupported"):
            self.continuity.snapshot()


if __name__ == "__main__":
    unittest.main()
