from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.intents import (
    AtomKind,
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentExtractor,
    IntentLifecycle,
    IntentLifecycleError,
)
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


class IntentExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = AppendOnlyEventStore(Path(self.temp.name) / "events.jsonl")
        self.source = IntentInbox(self.store).capture(
            "Maybe explore a status view. Build the local prototype. "
            "Do not touch Krish. Should we enable queueing?"
        )
        self.atoms = IntentExtractor().extract(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_distinguishes_exploration_action_constraint_and_decision(self):
        self.assertEqual(
            [
                AtomKind.EXPLORATION,
                AtomKind.ACTIONABLE,
                AtomKind.CONSTRAINT,
                AtomKind.DECISION_REQUEST,
            ],
            [atom.kind for atom in self.atoms],
        )

    def test_every_atom_points_to_exact_raw_source_span(self):
        for atom in self.atoms:
            excerpt = self.source.raw_text[atom.source_start : atom.source_end]
            self.assertEqual(atom.statement, excerpt)

    def test_ambiguous_statement_fails_safe_to_exploration(self):
        source = IntentInbox(self.store).capture("A dashboard with calm colors.")
        atom = IntentExtractor().extract(source)[0]
        self.assertEqual(AtomKind.EXPLORATION, atom.kind)
        self.assertFalse(atom.requires_human_confirmation)

    def test_actionable_and_decision_atoms_await_confirmation(self):
        gated = [atom for atom in self.atoms if atom.requires_human_confirmation]
        self.assertTrue(gated)
        self.assertTrue(all(atom.state == AtomState.AWAITING_CONFIRMATION for atom in gated))

    def test_atom_ids_are_deterministic_for_same_source(self):
        repeated = IntentExtractor().extract(self.source)
        self.assertEqual(
            [atom.atom_id for atom in self.atoms],
            [atom.atom_id for atom in repeated],
        )


class IntentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = AppendOnlyEventStore(Path(self.temp.name) / "events.jsonl")
        source = IntentInbox(self.store).capture("Build a local prototype.")
        self.atom = IntentExtractor().extract(source)[0]
        self.lifecycle = IntentLifecycle(self.store)
        self.lifecycle.propose(self.atom)
        self.human_confirmation = ConfirmationRecord(
            actor_id="local_owner",
            authority=ConfirmationAuthority.HUMAN,
            channel="codex_task",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_action_is_not_executable_until_human_confirmation(self):
        self.assertEqual([], list(self.lifecycle.actionable_atoms()))
        confirmed = self.lifecycle.confirm(
            self.atom.atom_id, confirmation=self.human_confirmation
        )
        self.assertEqual(AtomState.CONFIRMED, confirmed.state)
        self.assertEqual([self.atom.atom_id], [a.atom_id for a in self.lifecycle.actionable_atoms()])

    def test_confirmation_without_actor_fails_closed(self):
        with self.assertRaises(IntentLifecycleError):
            self.lifecycle.confirm(
                self.atom.atom_id,
                confirmation=ConfirmationRecord(
                    actor_id="",
                    authority=ConfirmationAuthority.HUMAN,
                    channel="codex_task",
                ),
            )
        self.assertEqual(AtomState.AWAITING_CONFIRMATION, self.lifecycle.current(self.atom.atom_id).state)

    def test_confirmation_cannot_be_replayed(self):
        self.lifecycle.confirm(self.atom.atom_id, confirmation=self.human_confirmation)
        with self.assertRaises(IntentLifecycleError):
            self.lifecycle.confirm(self.atom.atom_id, confirmation=self.human_confirmation)

    def test_system_authority_cannot_confirm(self):
        with self.assertRaises(IntentLifecycleError):
            self.lifecycle.confirm(
                self.atom.atom_id,
                confirmation=ConfirmationRecord(
                    actor_id="extractor",
                    authority=ConfirmationAuthority.SYSTEM,
                    channel="internal",
                ),
            )
        self.assertEqual([], list(self.lifecycle.actionable_atoms()))

    def test_duplicate_proposal_is_rejected(self):
        with self.assertRaises(IntentLifecycleError):
            self.lifecycle.propose(self.atom)

    def test_rejected_action_never_becomes_actionable(self):
        rejected = self.lifecycle.reject(
            self.atom.atom_id, actor="human", reason="not now"
        )
        self.assertEqual(AtomState.REJECTED, rejected.state)
        self.assertEqual([], list(self.lifecycle.actionable_atoms()))


if __name__ == "__main__":
    unittest.main()
