from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.project_decision_loop import (
    DecisionLoopError,
    ProjectDecisionLoop,
    ProjectDecisionManifest,
    RelationshipDecision,
)
from cognitive_os.store import AppendOnlyEventStore


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "mvp_project_decision_loop.json"


def fixture_value():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class ProjectDecisionLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def run_value(self, value, decision=RelationshipDecision.ACCEPT, actor="owner"):
        return ProjectDecisionLoop(AppendOnlyEventStore(self.path)).run(
            ProjectDecisionManifest.from_dict(value), decision, human_actor=actor
        )

    def test_accepted_loop_is_dependency_closed_bounded_and_evidence_backed(self):
        result = self.run_value(fixture_value())
        self.assertEqual(
            ["atlas_contract", "atlas_schema", "beacon_summary"],
            sorted(result["included_intent"]),
        )
        self.assertEqual(["beacon_animation_idea"], result["excluded_intent"])
        self.assertEqual("accepted", result["relationship_proposal"]["status"])
        self.assertEqual(
            "codex_packet_test_double",
            result["bounded_route_simulation"]["selected_route"],
        )
        self.assertEqual("P1_draft_only", result["bounded_route_simulation"]["permission_class"])
        self.assertFalse(result["external_effects"])
        self.assertEqual("verified_in_test_double", result["verification"]["observed_result"])
        self.assertEqual(4, len(result["timeline"]))

    def test_restart_and_exact_retry_are_idempotent(self):
        value = fixture_value()
        first = self.run_value(value)
        event_count = len(AppendOnlyEventStore(self.path).read_all())
        second = self.run_value(value)
        self.assertEqual(first, second)
        self.assertEqual(event_count, len(AppendOnlyEventStore(self.path).read_all()))

    def test_rejection_blocks_before_plan_and_route(self):
        result = self.run_value(fixture_value(), RelationshipDecision.REJECT)
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["bounded_route_simulation"])
        self.assertEqual("blocked_before_plan", result["verification"]["observed_result"])
        self.assertEqual(3, len(result["timeline"]))

    def test_existing_decision_cannot_be_changed_on_retry(self):
        value = fixture_value()
        self.run_value(value, RelationshipDecision.REJECT)
        with self.assertRaisesRegex(DecisionLoopError, "different exact decision"):
            self.run_value(value, RelationshipDecision.ACCEPT)

    def test_exactly_two_scopes_are_required_without_discovery(self):
        value = fixture_value()
        value["projects"].append(
            {"project_id": "ambient", "label": "Ambient", "owned_paths": ["ambient"]}
        )
        with self.assertRaisesRegex(DecisionLoopError, "exactly two"):
            self.run_value(value)
        self.assertEqual([], AppendOnlyEventStore(self.path).read_all())

    def test_proposal_requires_both_exact_source_records(self):
        value = fixture_value()
        value["relationship_proposal"]["evidence"] = value["relationship_proposal"]["evidence"][:1]
        with self.assertRaisesRegex(DecisionLoopError, "both exact endpoint sources"):
            self.run_value(value)

    def test_confidence_never_substitutes_for_human_identity(self):
        with self.assertRaisesRegex(DecisionLoopError, "human actor"):
            self.run_value(fixture_value(), actor="  ")

    def test_compile_scope_escape_fails_closed(self):
        value = fixture_value()
        value["compile"]["owned_paths"].append("unselected/project")
        with self.assertRaisesRegex(DecisionLoopError, "escaped"):
            self.run_value(value)

    def test_unreviewed_cross_project_dependency_fails_closed(self):
        value = fixture_value()
        value["local_dependencies"].append(["beacon_summary", "atlas_schema"])
        with self.assertRaisesRegex(DecisionLoopError, "one project"):
            self.run_value(value)

    def test_failed_observation_is_a_transparent_blocker(self):
        value = fixture_value()
        value["evidence"][0]["passed"] = False
        result = self.run_value(value)
        self.assertEqual("blocked_by_evidence", result["verification"]["observed_result"])
        self.assertIsNotNone(result["verification"]["blocker"])
        self.assertEqual("P1_draft_only", result["bounded_route_simulation"]["permission_class"])

    def test_paver_match_remains_a_non_executing_test_double(self):
        value = fixture_value()
        value["route_simulation"]["paver_capability_match"] = True
        result = self.run_value(value)
        route = result["bounded_route_simulation"]
        self.assertEqual("paver_test_double", route["selected_route"])
        self.assertTrue(route["test_double"])
        self.assertFalse(route["external_effects"])

    def test_manifest_change_after_initialization_is_rejected(self):
        value = fixture_value()
        self.run_value(value)
        changed = deepcopy(value)
        changed["compile"]["outcome"] = "A divergent outcome."
        with self.assertRaisesRegex(DecisionLoopError, "stale or divergent"):
            self.run_value(changed)

    def test_public_fixture_contains_only_declared_synthetic_provenance(self):
        value = fixture_value()
        encoded = json.dumps(value, sort_keys=True)
        self.assertNotIn('"raw_text"', encoded)
        self.assertNotIn('"metadata"', encoded)
        self.assertTrue(
            all(
                item["atom"]["source_id"].startswith("synthetic_")
                for item in value["intents"]
            )
        )
        self.assertEqual(
            {"atlas", "beacon"},
            {item["project_id"] for item in value["projects"]},
        )


if __name__ == "__main__":
    unittest.main()
