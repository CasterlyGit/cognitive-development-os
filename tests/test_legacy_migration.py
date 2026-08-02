import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.data_policy import PrivateDataPolicy
from cognitive_os.graph import IntentGraph
from cognitive_os.intents import (
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentExtractor,
    IntentLifecycle,
)
from cognitive_os.legacy_migration import (
    LegacyMigrationError,
    LegacyMigrationPlanner,
    LegacyMigrationRequest,
)
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


class LegacyMigrationPlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "legacy.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        inbox = IntentInbox(self.store)
        self.sentinel = "PRIVATE_RAW_SENTINEL"
        source = inbox.capture(
            "Build a synthetic migration plan. Do not execute it. " + self.sentinel,
            source_id="source_scoped",
            metadata={"private_label": "PRIVATE_METADATA_SENTINEL"},
        )
        atoms = IntentExtractor().extract(source)
        lifecycle = IntentLifecycle(self.store)
        graph = IntentGraph("graph_legacy", self.store)
        for atom in atoms:
            lifecycle.propose(atom)
            if atom.requires_human_confirmation:
                atom = lifecycle.confirm(
                    atom.atom_id,
                    confirmation=ConfirmationRecord(
                        actor_id="synthetic_owner",
                        authority=ConfirmationAuthority.HUMAN,
                        channel="unit_test",
                    ),
                )
            graph.add_atom(atom)
        inbox.capture("Unscoped synthetic source.", source_id="source_unscoped")
        self.policy = PrivateDataPolicy.conservative_default("cognitive-development-os")
        self.planner = LegacyMigrationPlanner(self.policy)

    def tearDown(self):
        self.temp.cleanup()

    def request(self):
        events = self.store.read_all()
        return LegacyMigrationRequest(
            project_id="cognitive-development-os",
            source_ids=("source_scoped",),
            expected_ledger_sha256=self.planner.ledger_sha256(events),
        )

    def test_plan_is_exact_redacted_and_non_executable(self):
        plan = self.planner.plan(self.request(), self.store.read_all())
        value = plan.to_dict()
        serialized = json.dumps(value, sort_keys=True)
        self.assertEqual(("source_scoped",), plan.source_ids)
        self.assertEqual(1, len(plan.sources))
        self.assertGreaterEqual(len(plan.atoms), 2)
        self.assertGreater(plan.scoped_private_event_count, 1)
        self.assertEqual(1, plan.unscoped_private_event_count)
        self.assertFalse(plan.executable)
        self.assertFalse(plan.writes_performed)
        self.assertFalse(plan.external_effects)
        self.assertFalse(plan.raw_values_included)
        self.assertTrue(plan.requires_exact_human_approval_for_execution)
        self.assertNotIn(self.sentinel, serialized)
        self.assertNotIn("PRIVATE_METADATA_SENTINEL", serialized)
        self.assertNotIn("Build a synthetic migration plan", serialized)
        self.assertIn("raw_text", serialized)
        self.assertIn("statement", serialized)

    def test_restart_is_deterministic_and_planning_writes_nothing(self):
        events_before = self.store.read_all()
        first = self.planner.plan(self.request(), events_before).to_dict()
        restarted_store = AppendOnlyEventStore(self.path)
        restarted_planner = LegacyMigrationPlanner(self.policy)
        restarted_events = restarted_store.read_all()
        second = restarted_planner.plan(
            LegacyMigrationRequest(
                project_id="cognitive-development-os",
                source_ids=("source_scoped",),
                expected_ledger_sha256=restarted_planner.ledger_sha256(
                    restarted_events
                ),
            ),
            restarted_events,
        ).to_dict()
        self.assertEqual(first, second)
        self.assertEqual(events_before, self.store.read_all())

    def test_stale_ledger_digest_fails_closed(self):
        request = self.request()
        self.store.append("other", "dry_run.completed", {"structural": True})
        with self.assertRaisesRegex(LegacyMigrationError, "changed"):
            self.planner.plan(request, self.store.read_all())

    def test_missing_duplicate_or_wildcard_source_fails_closed(self):
        events = self.store.read_all()
        digest = self.planner.ledger_sha256(events)
        for source_ids in (("missing",), ("source_*",), ("source_scoped",) * 2):
            with self.subTest(source_ids=source_ids):
                with self.assertRaises(LegacyMigrationError):
                    self.planner.plan(
                        LegacyMigrationRequest(
                            project_id="cognitive-development-os",
                            source_ids=source_ids,
                            expected_ledger_sha256=digest,
                        ),
                        events,
                    )

        with self.assertRaisesRegex(LegacyMigrationError, "exact tuple"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=["source_scoped"],
                    expected_ledger_sha256=digest,
                ),
                events,
            )

        source_event = next(
            event for event in events if event.event_type == "source.captured"
        )
        self.store.append(
            source_event.stream_id, source_event.event_type, source_event.payload
        )
        duplicated = self.store.read_all()
        with self.assertRaisesRegex(LegacyMigrationError, "one legacy capture"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=("source_scoped",),
                    expected_ledger_sha256=self.planner.ledger_sha256(duplicated),
                ),
                duplicated,
            )

    def test_cross_project_and_unknown_private_event_fail_closed(self):
        with self.assertRaisesRegex(LegacyMigrationError, "project scope"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="other-project",
                    source_ids=("source_scoped",),
                    expected_ledger_sha256=self.planner.ledger_sha256(
                        self.store.read_all()
                    ),
                ),
                self.store.read_all(),
            )
        self.store.append(
            "unknown",
            "unknown.private_event",
            {"source_id": "source_scoped", "raw_text": "hidden"},
        )
        events = self.store.read_all()
        with self.assertRaisesRegex(LegacyMigrationError, "unsupported"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=("source_scoped",),
                    expected_ledger_sha256=self.planner.ledger_sha256(events),
                ),
                events,
            )

    def test_corrupt_source_digest_and_atom_type_confusion_fail_closed(self):
        events = self.store.read_all()
        source_event = next(
            event for event in events if event.event_type == "source.captured"
        )
        source_event.payload["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(LegacyMigrationError, "digest"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=("source_scoped",),
                    expected_ledger_sha256=self.planner.ledger_sha256(events),
                ),
                events,
            )

        events = self.store.read_all()
        atom_event = next(
            event for event in events if event.event_type == "atom.proposed"
        )
        atom_event.payload["source_start"] = True
        with self.assertRaisesRegex(LegacyMigrationError, "provenance"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=("source_scoped",),
                    expected_ledger_sha256=self.planner.ledger_sha256(events),
                ),
                events,
            )

        events = self.store.read_all()
        atom_event = next(
            event for event in events if event.event_type == "atom.proposed"
        )
        atom_event.payload["requires_human_confirmation"] = False
        with self.assertRaisesRegex(LegacyMigrationError, "provenance"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=("source_scoped",),
                    expected_ledger_sha256=self.planner.ledger_sha256(events),
                ),
                events,
            )

    def test_conflicting_atom_copy_or_projection_state_fails_closed(self):
        events = self.store.read_all()
        graph_atom = next(
            event for event in events if event.event_type == "graph.atom_added"
        )
        changed = dict(graph_atom.payload)
        changed["extraction_method"] = "different_method"
        self.store.append("another_graph", "graph.atom_added", changed)
        values = self.store.read_all()
        with self.assertRaisesRegex(LegacyMigrationError, "conflicting identity"):
            self.planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=("source_scoped",),
                    expected_ledger_sha256=self.planner.ledger_sha256(values),
                ),
                values,
            )

        other_path = Path(self.temp.name) / "state.jsonl"
        other_store = AppendOnlyEventStore(other_path)
        source = IntentInbox(other_store).capture(
            "Build state verification.", source_id="source_state"
        )
        atom = IntentExtractor().extract(source)[0]
        lifecycle = IntentLifecycle(other_store)
        lifecycle.propose(atom)
        confirmed = lifecycle.confirm(
            atom.atom_id,
            confirmation=ConfirmationRecord(
                actor_id="synthetic_owner",
                authority=ConfirmationAuthority.HUMAN,
                channel="unit_test",
            ),
        )
        graph = IntentGraph("graph_state", other_store)
        graph.add_atom(confirmed)
        other_store.append(
            "graph_state",
            "graph.atom_state_updated",
            {"atom_id": atom.atom_id, "state": "rejected"},
        )
        planner = LegacyMigrationPlanner(self.policy)
        values = other_store.read_all()
        with self.assertRaisesRegex(LegacyMigrationError, "disagree"):
            planner.plan(
                LegacyMigrationRequest(
                    project_id="cognitive-development-os",
                    source_ids=("source_state",),
                    expected_ledger_sha256=planner.ledger_sha256(values),
                ),
                values,
            )


if __name__ == "__main__":
    unittest.main()
