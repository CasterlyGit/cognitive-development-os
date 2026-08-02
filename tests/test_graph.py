from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.graph import EdgeKind, GraphError, IntentGraph
from cognitive_os.intents import AtomKind, AtomState, IntentAtom
from cognitive_os.store import AppendOnlyEventStore


def atom(atom_id, state=AtomState.CONFIRMED, kind=AtomKind.ACTIONABLE):
    return IntentAtom(
        atom_id=atom_id,
        source_id="src_fixture",
        kind=kind,
        statement="Synthetic statement for %s." % atom_id,
        source_start=0,
        source_end=10,
        state=state,
        requires_human_confirmation=kind == AtomKind.ACTIONABLE,
    )


class IntentGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        self.graph = IntentGraph("graph_fixture", self.store)
        for atom_id in ("a", "b", "c"):
            self.graph.add_atom(atom(atom_id))

    def tearDown(self):
        self.temp.cleanup()

    def test_dependency_order_survives_restart(self):
        self.graph.add_dependency("c", "b")
        self.graph.add_dependency("b", "a")
        restarted = IntentGraph("graph_fixture", AppendOnlyEventStore(self.path))
        self.assertEqual(("a", "b", "c"), restarted.snapshot().topological_order())
        self.assertEqual(("b",), restarted.snapshot().dependencies_of("c"))

    def test_cycle_is_rejected_without_poisoning_history(self):
        self.graph.add_dependency("b", "a")
        self.graph.add_dependency("c", "b")
        before = len(self.store.read_all())
        with self.assertRaisesRegex(GraphError, "cycle"):
            self.graph.add_dependency("a", "c")
        self.assertEqual(before, len(self.store.read_all()))
        self.assertEqual(("a", "b", "c"), self.graph.snapshot().topological_order())

    def test_missing_and_self_relationships_are_rejected_without_append(self):
        before = len(self.store.read_all())
        with self.assertRaisesRegex(GraphError, "missing"):
            self.graph.add_dependency("a", "missing")
        with self.assertRaisesRegex(GraphError, "self"):
            self.graph.add_conflict("a", "a")
        self.assertEqual(before, len(self.store.read_all()))

    def test_conflict_is_symmetric_and_duplicate_is_rejected(self):
        snapshot = self.graph.add_conflict("c", "a")
        conflict = snapshot.conflicts()[0]
        self.assertEqual(("a", "c"), (conflict.source_atom_id, conflict.target_atom_id))
        self.assertEqual(EdgeKind.CONFLICTS_WITH, conflict.kind)
        with self.assertRaisesRegex(GraphError, "already"):
            self.graph.add_conflict("a", "c")

    def test_cluster_requires_known_members_and_survives_restart(self):
        snapshot = self.graph.define_cluster("delivery", "Delivery", ["b", "a", "a"])
        self.assertEqual(("a", "b"), snapshot.clusters["delivery"].member_atom_ids)
        restarted = IntentGraph("graph_fixture", AppendOnlyEventStore(self.path))
        self.assertEqual("Delivery", restarted.snapshot().clusters["delivery"].label)
        with self.assertRaisesRegex(GraphError, "missing"):
            self.graph.define_cluster("bad", "Bad", ["missing"])

    def test_empty_cluster_is_rejected(self):
        with self.assertRaisesRegex(GraphError, "at least one"):
            self.graph.define_cluster("empty", "Empty", [])

    def test_atom_state_sync_preserves_provenance(self):
        pending = atom("pending", state=AtomState.AWAITING_CONFIRMATION)
        self.graph.add_atom(pending)
        confirmed = replace(pending, state=AtomState.CONFIRMED)
        snapshot = self.graph.sync_atom_state(confirmed)
        self.assertEqual(AtomState.CONFIRMED, snapshot.atoms["pending"].state)
        changed_source = replace(confirmed, source_id="different")
        with self.assertRaisesRegex(GraphError, "provenance"):
            self.graph.sync_atom_state(changed_source)

    def test_unknown_graph_event_fails_closed(self):
        self.store.append("graph_fixture", "graph.future_event", {})
        with self.assertRaisesRegex(GraphError, "unsupported"):
            self.graph.snapshot()

    def test_corrupt_cyclic_history_fails_closed_on_rebuild(self):
        self.graph.add_dependency("b", "a")
        self.graph.add_dependency("c", "b")
        self.store.append(
            "graph_fixture",
            "graph.edge_added",
            {
                "source_atom_id": "a",
                "target_atom_id": "c",
                "kind": "depends_on",
            },
        )
        with self.assertRaisesRegex(GraphError, "cycle"):
            self.graph.snapshot()

    def test_duplicate_atom_is_rejected(self):
        before = len(self.store.read_all())
        with self.assertRaisesRegex(GraphError, "already"):
            self.graph.add_atom(atom("a"))
        self.assertEqual(before, len(self.store.read_all()))


if __name__ == "__main__":
    unittest.main()
