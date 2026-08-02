from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    AtomKind,
    AtomState,
    ConfidenceBand,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentAtom,
    IntentExtractor,
    IntentLifecycle,
    IntentLifecycleError,
    SemanticConfidence,
)
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


class SemanticConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        self.inbox = IntentInbox(self.store)
        self.extractor = IntentExtractor()

    def tearDown(self):
        self.temp.cleanup()

    def extract_one(self, text):
        source = self.inbox.capture(text)
        return self.extractor.extract(source)[0]

    def test_clear_signals_receive_typed_high_confidence(self):
        source = self.inbox.capture(
            "Explore a calm status view. Build the local prototype. "
            "Do not touch Krish. Should we enable queueing?"
        )
        atoms = self.extractor.extract(source)
        self.assertEqual(
            [
                AtomKind.EXPLORATION,
                AtomKind.ACTIONABLE,
                AtomKind.CONSTRAINT,
                AtomKind.DECISION_REQUEST,
            ],
            [atom.kind for atom in atoms],
        )
        self.assertTrue(
            all(
                atom.semantic_confidence.band == ConfidenceBand.HIGH
                for atom in atoms
            )
        )
        self.assertTrue(
            all(atom.extraction_method == "rules_v2_confidence" for atom in atoms)
        )

    def test_hedged_action_falls_back_to_exploration(self):
        atom = self.extract_one("Maybe build and ship the dashboard.")
        self.assertEqual(AtomKind.EXPLORATION, atom.kind)
        self.assertEqual(ConfidenceBand.MEDIUM, atom.semantic_confidence.band)
        self.assertEqual(
            ("action_signal", "exploration_signal"),
            atom.semantic_confidence.signals,
        )
        self.assertEqual(AtomState.PROPOSED, atom.state)
        self.assertFalse(atom.requires_human_confirmation)

    def test_statement_without_decisive_signal_is_low_confidence_exploration(self):
        atom = self.extract_one("A calm dashboard with blue accents.")
        self.assertEqual(AtomKind.EXPLORATION, atom.kind)
        self.assertEqual(ConfidenceBand.LOW, atom.semantic_confidence.band)
        self.assertEqual(("no_decisive_signal",), atom.semantic_confidence.signals)

    def test_hedged_safety_language_remains_a_constraint_without_authority(self):
        atom = self.extract_one("Maybe do not build the live adapter.")
        self.assertEqual(AtomKind.CONSTRAINT, atom.kind)
        self.assertEqual(ConfidenceBand.MEDIUM, atom.semantic_confidence.band)
        self.assertFalse(atom.requires_human_confirmation)

    def test_high_confidence_action_still_requires_human_confirmation(self):
        atom = self.extract_one("Build the local prototype.")
        self.assertEqual(ConfidenceBand.HIGH, atom.semantic_confidence.band)
        self.assertEqual(AtomState.AWAITING_CONFIRMATION, atom.state)
        lifecycle = IntentLifecycle(self.store)
        lifecycle.propose(atom)
        self.assertEqual([], list(lifecycle.actionable_atoms()))
        with self.assertRaises(IntentLifecycleError):
            lifecycle.confirm(
                atom.atom_id,
                confirmation=ConfirmationRecord(
                    actor_id="extractor",
                    authority=ConfirmationAuthority.SYSTEM,
                    channel="internal",
                ),
            )
        self.assertEqual([], list(lifecycle.actionable_atoms()))

    def test_serialization_preserves_confidence_and_legacy_is_unassessed(self):
        atom = self.extract_one("Build the local prototype.")
        self.assertEqual(atom, IntentAtom.from_dict(atom.to_dict()))
        legacy = atom.to_dict()
        legacy.pop("semantic_confidence")
        legacy["extraction_method"] = "rules_v1"
        restored = IntentAtom.from_dict(legacy)
        self.assertEqual(ConfidenceBand.UNASSESSED, restored.semantic_confidence.band)
        self.assertEqual(0, restored.semantic_confidence.score_millis)

    def test_invalid_confidence_payloads_fail_closed(self):
        invalid_values = (
            {"band": "high", "score_millis": 1200, "signals": ["action_signal"]},
            {"band": "high", "score_millis": 300, "signals": ["action_signal"]},
            {
                "band": "medium",
                "score_millis": 500,
                "signals": ["exploration_signal", "action_signal"],
            },
            {"band": "unassessed", "score_millis": 0, "signals": ["legacy"]},
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SemanticConfidence.from_dict(value)

    def test_graph_restart_preserves_confidence_exactly(self):
        atom = self.extract_one("Build the local prototype.")
        graph = IntentGraph("graph_confidence", self.store)
        graph.add_atom(atom)
        restarted = IntentGraph(
            "graph_confidence", AppendOnlyEventStore(self.path)
        ).snapshot()
        self.assertEqual(atom, restarted.atoms[atom.atom_id])

    def test_confidence_is_deterministic_and_evidence_is_privacy_safe(self):
        first = self.extract_one("Could we build a local preview?")
        second = self.extract_one("Could we build a local preview?")
        self.assertEqual(first.kind, second.kind)
        self.assertEqual(first.semantic_confidence, second.semantic_confidence)
        allowed = {
            "action_signal",
            "constraint_signal",
            "decision_signal",
            "exploration_signal",
            "no_decisive_signal",
        }
        self.assertTrue(set(first.semantic_confidence.signals).issubset(allowed))
        self.assertNotIn("preview", " ".join(first.semantic_confidence.signals))


if __name__ == "__main__":
    unittest.main()
