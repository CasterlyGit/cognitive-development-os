from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.continuity import IntentContinuity
from cognitive_os.graph import GraphSnapshot, IntentGraph
from cognitive_os.intents import (
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentExtractor,
)
from cognitive_os.privacy import PrivacyExportError, PublicContinuityExporter
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


class PublicContinuityExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        self.inbox = IntentInbox(self.store)
        self.graph = IntentGraph("local_graph_PRIVATE_GRAPH", self.store)
        self.sources = []
        values = (
            (
                "foundation",
                "local_src_PRIVATE_ALPHA",
                "Build PRIVATE_ALPHA local lineage.",
                AtomState.CONFIRMED,
            ),
            (
                "current_path",
                "local_src_PRIVATE_BETA",
                "Build PRIVATE_BETA mutable plan.",
                AtomState.CONFIRMED,
            ),
            (
                "constraint",
                "local_src_PRIVATE_GAMMA",
                "Do not publish PRIVATE_GAMMA source.",
                AtomState.PROPOSED,
            ),
            (
                "alternative",
                "local_src_PRIVATE_DELTA",
                "Create PRIVATE_DELTA immutable plan.",
                AtomState.CONFIRMED,
            ),
        )
        for atom_id, source_id, text, state in values:
            source = self.inbox.capture(
                text,
                source_id=source_id,
                metadata={
                    "owner": "PRIVATE_OWNER@example.invalid",
                    "private_note": "PRIVATE_METADATA",
                },
            )
            self.sources.append(source)
            extracted = IntentExtractor().extract(source)[0]
            self.graph.add_atom(
                replace(extracted, atom_id=atom_id, state=state)
            )
        self.graph.add_dependency("current_path", "foundation")
        self.graph.add_dependency("alternative", "foundation")
        self.continuity = IntentContinuity(
            "local_continuity_PRIVATE_ROOT", self.store
        )
        root = self.continuity.initialize_root(
            self.graph.snapshot(),
            branch_id="local_branch_PRIVATE_ACCEPTED",
            atom_ids=("foundation", "current_path", "constraint"),
            operation_id="private-root-operation",
        )
        v1 = root.current_plan("local_branch_PRIVATE_ACCEPTED")
        self.continuity.open_child(
            self.graph.snapshot(),
            branch_id="local_branch_PRIVATE_SIDECAR",
            parent_branch_id="local_branch_PRIVATE_ACCEPTED",
            anchor_atom_id="current_path",
            inherited_atom_ids=("current_path", "constraint"),
            expected_parent_plan_version_id=v1.plan_version_id,
            operation_id="private-open-operation",
        )
        self.continuity.propose_atom(
            self.graph.snapshot(),
            branch_id="local_branch_PRIVATE_SIDECAR",
            atom_id="alternative",
            operation_id="private-propose-operation",
        )
        self.snapshot = self.continuity.promote(
            self.graph.snapshot(),
            branch_id="local_branch_PRIVATE_SIDECAR",
            selected_atom_ids=("alternative",),
            replace_atom_ids=("current_path",),
            expected_parent_plan_version_id=v1.plan_version_id,
            confirmation=ConfirmationRecord(
                actor_id="PRIVATE_HUMAN",
                authority=ConfirmationAuthority.HUMAN,
                channel="private_fixture",
            ),
            operation_id="private-promote-operation",
        )
        self.exporter = PublicContinuityExporter("1" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def export(self, **kwargs):
        return self.exporter.export(
            self.graph.snapshot(), self.snapshot, self.sources, **kwargs
        )

    def test_packet_has_review_structure_without_private_values_or_fields(self):
        packet = self.export()
        encoded = json.dumps(packet.to_dict(), sort_keys=True)
        self.assertFalse(packet.raw_source_included)
        self.assertFalse(packet.statements_included)
        self.assertEqual(4, len(packet.sources))
        self.assertEqual(4, len(packet.atoms))
        self.assertEqual(2, len(packet.branches))
        self.assertEqual([1, 2], [item.revision for item in packet.plan_versions])
        for marker in (
            "PRIVATE_ALPHA",
            "PRIVATE_BETA",
            "PRIVATE_GAMMA",
            "PRIVATE_DELTA",
            "PRIVATE_OWNER",
            "PRIVATE_METADATA",
            "PRIVATE_ROOT",
            "PRIVATE_ACCEPTED",
            "PRIVATE_SIDECAR",
            "PRIVATE_HUMAN",
        ):
            self.assertNotIn(marker, encoded)
        for forbidden_field in (
            '"raw_text"',
            '"statement"',
            '"source_start"',
            '"source_end"',
            '"metadata"',
            '"captured_at"',
            '"content_sha256"',
            '"source_id"',
            '"atom_id"',
            '"branch_id"',
            '"plan_version_id"',
        ):
            self.assertNotIn(forbidden_field, encoded)

    def test_repeated_and_restarted_export_are_identical(self):
        first = self.export().to_dict()
        second = self.export().to_dict()
        restarted_graph = IntentGraph(
            "local_graph_PRIVATE_GRAPH", AppendOnlyEventStore(self.path)
        ).snapshot()
        restarted_continuity = IntentContinuity(
            "local_continuity_PRIVATE_ROOT", AppendOnlyEventStore(self.path)
        ).snapshot()
        restarted_sources = list(
            IntentInbox(AppendOnlyEventStore(self.path)).sources()
        )
        restarted = self.exporter.export(
            restarted_graph, restarted_continuity, restarted_sources
        ).to_dict()
        self.assertEqual(first, second)
        self.assertEqual(first, restarted)

    def test_different_export_scopes_produce_unlinkable_references(self):
        first = self.export().to_dict()
        second = PublicContinuityExporter("2" * 64).export(
            self.graph.snapshot(), self.snapshot, self.sources
        ).to_dict()
        first_refs = self._all_public_refs(first)
        second_refs = self._all_public_refs(second)
        self.assertTrue(first_refs)
        self.assertTrue(second_refs)
        self.assertTrue(first_refs.isdisjoint(second_refs))

    def test_raw_or_statement_export_request_is_rejected(self):
        for arguments in (
            {"include_raw_source": True},
            {"include_statements": True},
            {"include_raw_source": True, "include_statements": True},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(PrivacyExportError, "cannot include"):
                    self.export(**arguments)

    def test_missing_duplicate_or_digest_mismatched_source_fails_closed(self):
        with self.assertRaisesRegex(PrivacyExportError, "missing source"):
            self.exporter.export(
                self.graph.snapshot(), self.snapshot, self.sources[:-1]
            )
        with self.assertRaisesRegex(PrivacyExportError, "duplicate source"):
            self.exporter.export(
                self.graph.snapshot(), self.snapshot, self.sources + [self.sources[0]]
            )
        corrupt = replace(self.sources[0], content_sha256="0" * 64)
        with self.assertRaisesRegex(PrivacyExportError, "digest mismatch"):
            self.exporter.export(
                self.graph.snapshot(), self.snapshot, [corrupt] + self.sources[1:]
            )

    def test_atom_source_span_mismatch_fails_closed(self):
        atoms = dict(self.graph.snapshot().atoms)
        atoms["alternative"] = replace(
            atoms["alternative"], statement="PRIVATE_TAMPERED"
        )
        corrupt_graph = GraphSnapshot(
            graph_id=self.graph.graph_id,
            atoms=atoms,
            edges=self.graph.snapshot().edges,
            clusters=self.graph.snapshot().clusters,
        )
        with self.assertRaisesRegex(PrivacyExportError, "span mismatch"):
            self.exporter.export(corrupt_graph, self.snapshot, self.sources)

    def test_branch_or_plan_lineage_mismatch_fails_closed(self):
        branch_id = "local_branch_PRIVATE_SIDECAR"
        branches = dict(self.snapshot.branches)
        branches[branch_id] = replace(
            branches[branch_id], inherited_source_ids=("wrong_source",)
        )
        corrupt_branch = replace(self.snapshot, branches=branches)
        with self.assertRaisesRegex(PrivacyExportError, "branch inherited"):
            self.exporter.export(
                self.graph.snapshot(), corrupt_branch, self.sources
            )

        versions = dict(self.snapshot.plan_versions)
        current_id = self.snapshot.current_plan_ids[
            "local_branch_PRIVATE_ACCEPTED"
        ]
        versions[current_id] = replace(
            versions[current_id], source_ids=("wrong_source",)
        )
        corrupt_plan = replace(self.snapshot, plan_versions=versions)
        with self.assertRaisesRegex(PrivacyExportError, "plan-version"):
            self.exporter.export(
                self.graph.snapshot(), corrupt_plan, self.sources
            )

    def test_invalid_current_plan_pointer_fails_closed(self):
        corrupt = replace(
            self.snapshot,
            current_plan_ids={"local_branch_PRIVATE_ACCEPTED": "missing_plan"},
        )
        with self.assertRaisesRegex(PrivacyExportError, "current-plan"):
            self.exporter.export(self.graph.snapshot(), corrupt, self.sources)
        missing_index = replace(self.snapshot, current_plan_ids={})
        with self.assertRaisesRegex(PrivacyExportError, "incomplete"):
            self.exporter.export(
                self.graph.snapshot(), missing_index, self.sources
            )

    def test_export_scope_is_required(self):
        for invalid in ("", "1" * 63, "G" * 64, "A" * 64):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    PublicContinuityExporter(invalid)

    @staticmethod
    def _all_public_refs(value):
        refs = set()
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("_ref") and isinstance(item, str):
                    refs.add(item)
                elif key.endswith("_refs") and isinstance(item, list):
                    refs.update(entry for entry in item if isinstance(entry, str))
                else:
                    refs.update(PublicContinuityExportTests._all_public_refs(item))
        elif isinstance(value, list):
            for item in value:
                refs.update(PublicContinuityExportTests._all_public_refs(item))
        return refs


if __name__ == "__main__":
    unittest.main()
