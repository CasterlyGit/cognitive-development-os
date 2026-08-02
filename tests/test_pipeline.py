from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cognitive_os.cli import main as cli_main
from cognitive_os.graph import GraphError
from cognitive_os.pipeline import DryRunControlPlane, DryRunError, DryRunManifest
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


FIXTURE = Path(__file__).parents[1] / "examples" / "fixtures" / "layer5_end_to_end.json"


def fixture_value():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class DryRunControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        self.control_plane = DryRunControlPlane(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_raw_conversation_reaches_one_reviewable_decision_packet(self):
        result = self.control_plane.run(DryRunManifest.from_dict(fixture_value()))
        self.assertEqual("dry_run_complete", result.decision_packet.status)
        self.assertFalse(result.decision_packet.external_effects)
        self.assertIsNotNone(result.proposal)
        self.assertEqual(3, len(result.decision_packet.primary_decision.choices))
        self.assertEqual("accept_draft", result.decision_packet.primary_decision.recommended_key)
        self.assertEqual(2, len(result.proposal.plan.selected_atom_ids))

    def test_missing_confirmation_pauses_before_graph_compilation(self):
        value = fixture_value()
        value["confirmed_atom_indexes"] = [1]
        result = self.control_plane.run(DryRunManifest.from_dict(value))
        self.assertEqual("awaiting_confirmation", result.decision_packet.status)
        self.assertIsNone(result.proposal)
        self.assertFalse(any(event.event_type.startswith("graph.") for event in self.store.read_all()))

    def test_paused_run_resumes_after_exact_confirmation(self):
        value = fixture_value()
        value["confirmed_atom_indexes"] = [1]
        first = self.control_plane.run(DryRunManifest.from_dict(value))
        self.assertEqual("awaiting_confirmation", first.decision_packet.status)
        resumed = self.control_plane.run(DryRunManifest.from_dict(fixture_value()))
        self.assertEqual("dry_run_complete", resumed.decision_packet.status)

    def test_system_authority_cannot_cross_confirmation_boundary(self):
        value = fixture_value()
        value["confirmation"]["authority"] = "system"
        with self.assertRaisesRegex(DryRunError, "only human"):
            self.control_plane.run(DryRunManifest.from_dict(value))

    def test_confirmation_cannot_include_unrelated_intent(self):
        value = fixture_value()
        value["confirmed_atom_indexes"].append(4)
        with self.assertRaisesRegex(DryRunError, "unrelated atom"):
            self.control_plane.run(DryRunManifest.from_dict(value))

    def test_identical_completed_replay_is_idempotent(self):
        manifest = DryRunManifest.from_dict(fixture_value())
        first = self.control_plane.run(manifest)
        count = len(self.store.read_all())
        restarted = DryRunControlPlane(AppendOnlyEventStore(self.path))
        second = restarted.run(manifest)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(count, len(self.store.read_all()))

    def test_completed_run_id_rejects_changed_input(self):
        self.control_plane.run(DryRunManifest.from_dict(fixture_value()))
        changed = fixture_value()
        changed["plan"]["outcome"] = "A different outcome."
        with self.assertRaisesRegex(DryRunError, "different input"):
            self.control_plane.run(DryRunManifest.from_dict(changed))

    def test_out_of_range_relationship_fails_closed(self):
        value = fixture_value()
        value["dependencies"] = [[2, 99]]
        with self.assertRaisesRegex(DryRunError, "out of range"):
            self.control_plane.run(DryRunManifest.from_dict(value))

    def test_cyclic_manifest_fails_closed(self):
        value = fixture_value()
        value["dependencies"].append([1, 2])
        with self.assertRaisesRegex(GraphError, "cycle"):
            self.control_plane.run(DryRunManifest.from_dict(value))

    def test_raw_source_is_exact_after_restart(self):
        value = fixture_value()
        self.control_plane.run(DryRunManifest.from_dict(value))
        restarted = IntentInbox(AppendOnlyEventStore(self.path))
        restored = list(restarted.sources())
        self.assertEqual(value["source"]["raw_text"], restored[0].raw_text)

    def test_cli_emits_valid_json_and_reuses_store(self):
        store_path = Path(self.temp.name) / "cli.jsonl"
        output = StringIO()
        with patch("sys.stdout", output):
            code = cli_main(
                ["run", "--manifest", str(FIXTURE), "--store", str(store_path)]
            )
        self.assertEqual(0, code)
        parsed = json.loads(output.getvalue())
        self.assertEqual("dry_run_complete", parsed["decision_packet"]["status"])
        self.assertFalse(parsed["decision_packet"]["external_effects"])


if __name__ == "__main__":
    unittest.main()
