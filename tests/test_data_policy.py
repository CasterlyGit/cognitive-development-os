from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.data_policy import (
    DataPolicyError,
    DeletionMode,
    DeletionRequest,
    PrivateDataPolicy,
    PrivateDataPolicyEngine,
    RawRetentionMode,
    StructuralSearchRequest,
)
from cognitive_os.intents import IntentExtractor, IntentLifecycle
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


class PrivateDataPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = PrivateDataPolicy.conservative_default(
            "cognitive-development-os"
        )
        self.engine = PrivateDataPolicyEngine(self.policy)

    def test_default_is_session_only_single_project_and_reversible(self):
        self.assertEqual(RawRetentionMode.SESSION_ONLY, self.policy.raw_retention)
        self.assertEqual(0, self.policy.retention_days)
        self.assertEqual(("cognitive-development-os",), self.policy.project_ids)
        self.assertEqual(7, self.policy.quarantine_days)

    def test_local_retention_is_bounded_and_requires_explicit_approval(self):
        for days, approval in ((0, "approved"), (31, "approved"), (7, None)):
            with self.subTest(days=days, approval=approval):
                with self.assertRaises(DataPolicyError):
                    replace(
                        self.policy,
                        raw_retention=RawRetentionMode.LOCAL_EXPIRING,
                        retention_days=days,
                        retention_approval_id=approval,
                    ).validated()
        accepted = replace(
            self.policy,
            raw_retention=RawRetentionMode.LOCAL_EXPIRING,
            retention_days=7,
            retention_approval_id="approval_private_retention",
        ).validated()
        self.assertEqual(7, accepted.retention_days)

    def test_cross_project_scope_is_exact_opt_in_without_wildcards(self):
        with self.assertRaises(DataPolicyError):
            replace(
                self.policy,
                project_ids=("cognitive-development-os", "other-project"),
            ).validated()
        accepted = replace(
            self.policy,
            project_ids=("cognitive-development-os", "other-project"),
            cross_project_approval_id="approval_exact_project_set",
        ).validated()
        self.assertEqual(2, len(accepted.project_ids))
        with self.assertRaises(DataPolicyError):
            replace(
                self.policy,
                project_ids=("cognitive-development-os", "*"),
                cross_project_approval_id="approval_invalid_scope",
            ).validated()

    def test_search_excludes_archives_and_rejects_raw_or_ambient_scope(self):
        active = self.engine.authorize_search(
            StructuralSearchRequest(project_ids=("cognitive-development-os",))
        )
        self.assertEqual(("active", "promoted"), active.visible_branch_statuses)
        self.assertTrue(active.structural_only)
        with self.assertRaises(DataPolicyError):
            self.engine.authorize_search(
                StructuralSearchRequest(
                    project_ids=("cognitive-development-os",),
                    include_archived=True,
                )
            )
        archived = self.engine.authorize_search(
            StructuralSearchRequest(
                project_ids=("cognitive-development-os",),
                branch_ids=("branch_exact",),
                include_archived=True,
            )
        )
        self.assertIn("archived", archived.visible_branch_statuses)
        for request in (
            StructuralSearchRequest(
                project_ids=("cognitive-development-os",), raw_query="private text"
            ),
            StructuralSearchRequest(project_ids=("other-project",)),
            StructuralSearchRequest(project_ids=("*",)),
            StructuralSearchRequest(
                project_ids=("cognitive-development-os",),
                include_archived="true",
            ),
        ):
            with self.subTest(request=request):
                with self.assertRaises(DataPolicyError):
                    self.engine.authorize_search(request)

    def test_quarantine_plan_is_exact_deterministic_and_effect_free(self):
        request = DeletionRequest(
            project_id="cognitive-development-os",
            source_ids=("source_b", "source_a"),
        )
        with TemporaryDirectory() as directory:
            store = AppendOnlyEventStore(Path(directory) / "events.jsonl")
            inbox = IntentInbox(store)
            first_source = inbox.capture("Synthetic A", source_id="source_a")
            second_source = inbox.capture("Synthetic B", source_id="source_b")
            events = store.read_all()
        first = self.engine.plan_deletion(request, events)
        second = self.engine.plan_deletion(request, events)
        self.assertEqual(first, second)
        self.assertEqual(("source_a", "source_b"), first.source_ids)
        self.assertEqual(
            (first_source.content_sha256, second_source.content_sha256),
            first.source_content_hashes,
        )
        self.assertTrue(first.reversible)
        self.assertFalse(first.external_effects)
        self.assertEqual("quarantine_plan_only", first.action)
        with self.assertRaises(DataPolicyError):
            self.engine.plan_deletion(
                replace(request, mode=DeletionMode.PURGE), events
            )
        with self.assertRaises(DataPolicyError):
            self.engine.plan_deletion(
                replace(request, source_ids=("source_*",)), events
            )
        with self.assertRaises(DataPolicyError):
            self.engine.plan_deletion(
                replace(request, source_ids=("source_missing",)), events
            )

    def test_legacy_audit_reports_field_names_without_private_values(self):
        sentinel = "PRIVATE_SENTINEL_DO_NOT_REPORT"
        with TemporaryDirectory() as directory:
            store = AppendOnlyEventStore(Path(directory) / "events.jsonl")
            source = IntentInbox(store).capture(sentinel, source_id="source_private")
            atom = IntentExtractor().extract(source)[0]
            IntentLifecycle(store).propose(atom)
            audit = self.engine.audit_legacy_storage(store.read_all())
        packet = audit.to_dict()
        self.assertTrue(packet["migration_required"])
        self.assertFalse(packet["raw_values_included"])
        self.assertGreaterEqual(packet["events_with_private_fields"], 2)
        self.assertIn("raw_text", packet["private_field_counts"])
        self.assertIn("statement", packet["private_field_counts"])
        self.assertNotIn(sentinel, str(packet))
        self.assertNotIn("source_private", str(packet))


if __name__ == "__main__":
    unittest.main()
