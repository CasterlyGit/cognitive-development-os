import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.data_policy import (
    PrivateDataPolicy,
    PrivateDataPolicyEngine,
    RawRetentionMode,
)
from cognitive_os.private_lineage import (
    PrivateContentUnavailable,
    PrivateLineageError,
    PrivateLineageSession,
    SessionContentVault,
)
from cognitive_os.store import AppendOnlyEventStore
from cognitive_os.models import SourceKind


class PrivateLineageSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        self.policy = PrivateDataPolicy.conservative_default(
            "cognitive-development-os"
        )
        self.vault = SessionContentVault()
        self.session = PrivateLineageSession(self.store, self.vault, self.policy)

    def tearDown(self):
        self.temp.cleanup()

    def _capture_and_extract(self):
        source = self.session.capture(
            "Build a private structural path. Do not retain raw source.",
            source_id="source_private_v2",
            metadata={"private-label": "PRIVATE_METADATA_SENTINEL"},
        )
        atoms = self.session.extract_and_record(source.source_id)
        return source, atoms

    def test_ledger_contains_structural_lineage_without_private_content(self):
        source, atoms = self._capture_and_extract()
        serialized = self.path.read_text(encoding="utf-8")
        for forbidden in (
            source.raw_text,
            "PRIVATE_METADATA_SENTINEL",
            "private-label",
            '"raw_text"',
            '"statement"',
            '"metadata"',
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertIn(source.content_sha256, serialized)
        for atom in atoms:
            self.assertNotIn(atom.statement, serialized)

    def test_content_materializes_only_while_exact_session_vault_exists(self):
        source, atoms = self._capture_and_extract()
        self.assertEqual(source, self.session.materialize_source(source.source_id))
        self.assertEqual(atoms[0], self.session.materialize_atom(atoms[0].atom_id))
        removed = self.session.end_session()
        self.assertEqual(1, removed)
        with self.assertRaises(PrivateContentUnavailable):
            self.session.materialize_source(source.source_id)
        with self.assertRaises(PrivateContentUnavailable):
            self.session.materialize_atom(atoms[0].atom_id)

    def test_restart_preserves_structure_but_not_session_content(self):
        source, atoms = self._capture_and_extract()
        before = self.session.snapshot().to_dict()
        restarted = PrivateLineageSession(
            AppendOnlyEventStore(self.path), SessionContentVault(), self.policy
        )
        self.assertEqual(before, restarted.snapshot().to_dict())
        with self.assertRaises(PrivateContentUnavailable):
            restarted.materialize_source(source.source_id)
        with self.assertRaises(PrivateContentUnavailable):
            restarted.materialize_atom(atoms[0].atom_id)

    def test_exact_recapture_and_extraction_are_idempotent(self):
        source, atoms = self._capture_and_extract()
        before = len(self.store.read_all())
        replayed = self.session.capture(
            source.raw_text,
            source_id=source.source_id,
            metadata={"private-label": "PRIVATE_METADATA_SENTINEL"},
        )
        replayed_atoms = self.session.extract_and_record(source.source_id)
        self.assertEqual(source.content_sha256, replayed.content_sha256)
        self.assertEqual(atoms, replayed_atoms)
        self.assertEqual(before, len(self.store.read_all()))
        with self.assertRaises(PrivateLineageError):
            self.session.capture("Different source.", source_id=source.source_id)
        with self.assertRaises(PrivateLineageError):
            self.session.capture(
                source.raw_text,
                source_id=source.source_id,
                metadata={"private-label": "different-session-metadata"},
            )

    def test_persistent_or_cross_project_policy_is_not_silently_enabled(self):
        persistent = PrivateDataPolicy(
            project_ids=("cognitive-development-os",),
            raw_retention=RawRetentionMode.LOCAL_EXPIRING,
            retention_days=7,
            retention_approval_id="approval_retention",
            quarantine_days=7,
            archived_search=self.policy.archived_search,
            cross_project_approval_id=None,
        )
        with self.assertRaises(PrivateLineageError):
            PrivateLineageSession(self.store, SessionContentVault(), persistent)
        cross_project = PrivateDataPolicy(
            project_ids=("cognitive-development-os", "other-project"),
            raw_retention=RawRetentionMode.SESSION_ONLY,
            retention_days=0,
            retention_approval_id=None,
            quarantine_days=7,
            archived_search=self.policy.archived_search,
            cross_project_approval_id="approval_exact_projects",
        )
        with self.assertRaises(PrivateLineageError):
            PrivateLineageSession(self.store, SessionContentVault(), cross_project)

    def test_capture_rejects_type_confusion_without_writing(self):
        invalid_calls = (
            lambda: self.session.capture(True, source_id="source_bool"),
            lambda: self.session.capture("valid text", source_id=True),
            lambda: self.session.capture("valid text", source_id=" source_space "),
            lambda: self.session.capture(
                "valid text", source_id="source_kind", kind="chat"
            ),
            lambda: self.session.capture(
                "valid text", source_id="source_metadata", metadata=("not", "pairs")
            ),
        )
        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(PrivateLineageError):
                    call()
        self.assertEqual([], self.store.read_all())

        accepted = self.session.capture(
            "valid text", source_id="source_valid", kind=SourceKind.NOTE
        )
        self.assertEqual(SourceKind.NOTE, accepted.kind)

    def test_duplicate_or_corrupt_structural_history_fails_closed(self):
        source, _ = self._capture_and_extract()
        descriptor = self.session.snapshot().sources[source.source_id]
        self.store.append(
            source.source_id,
            PrivateLineageSession.SOURCE_EVENT,
            descriptor.to_dict(),
        )
        with self.assertRaises(PrivateLineageError):
            self.session.snapshot()

    def test_structural_payloads_are_json_and_forbidden_field_free(self):
        self._capture_and_extract()
        forbidden = {"raw_text", "statement", "metadata"}

        def keys(value):
            found = set()
            if isinstance(value, dict):
                for key, child in value.items():
                    found.add(key)
                    found.update(keys(child))
            elif isinstance(value, list):
                for child in value:
                    found.update(keys(child))
            return found

        for line in self.path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            self.assertTrue(forbidden.isdisjoint(keys(value["payload"])))

        audit = PrivateDataPolicyEngine(self.policy).audit_legacy_storage(
            self.store.read_all()
        )
        self.assertFalse(audit.migration_required)
        self.assertEqual(0, audit.events_with_private_fields)

    def test_private_payload_extensions_and_invalid_spans_fail_closed(self):
        source, atoms = self._capture_and_extract()
        source_payload = self.session.snapshot().sources[source.source_id].to_dict()
        source_payload["raw_text"] = "must not be accepted"
        with self.assertRaises(PrivateLineageError):
            type(self.session.snapshot().sources[source.source_id]).from_dict(
                source_payload
            )

        atom_payload = self.session.snapshot().atoms[atoms[0].atom_id].to_dict()
        atom_payload["semantic_confidence"]["score_millis"] = "700"
        with self.assertRaises(PrivateLineageError):
            type(self.session.snapshot().atoms[atoms[0].atom_id]).from_dict(atom_payload)

        oversized = self.session.snapshot().atoms[atoms[0].atom_id].to_dict()
        oversized["source_end"] = len(source.raw_text) + 1
        self.store.append(
            "oversized_atom",
            PrivateLineageSession.ATOM_EVENT,
            dict(oversized, atom_id="oversized_atom"),
        )
        with self.assertRaises(PrivateLineageError):
            self.session.snapshot()

    def test_unknown_private_event_type_fails_closed(self):
        path = Path(self.temp.name) / "unknown-events.jsonl"
        store = AppendOnlyEventStore(path)
        session = PrivateLineageSession(store, SessionContentVault(), self.policy)
        store.append("future", "private_source.future_v3", {})
        with self.assertRaises(PrivateLineageError):
            session.snapshot()


if __name__ == "__main__":
    unittest.main()
