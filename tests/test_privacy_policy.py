from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.privacy_policy import (
    ArchivedSearchRequest,
    PrivacyPolicyError,
    PrivacyPolicyService,
    ReasoningScope,
    RetentionMode,
    RetentionPolicy,
)
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


class PrivacyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = AppendOnlyEventStore(Path(self.temp.name) / "events.jsonl")
        self.inbox = IntentInbox(self.store)
        self.service = PrivacyPolicyService(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_default_retention_is_session_only_and_opt_in_requires_window(self):
        self.assertEqual(RetentionMode.SESSION_ONLY, RetentionPolicy().mode)
        with self.assertRaises(PrivacyPolicyError):
            RetentionPolicy(RetentionMode.LOCAL_TIME_BOUNDED)
        self.assertEqual(24, RetentionPolicy(RetentionMode.LOCAL_TIME_BOUNDED, 24).window_hours)

    def test_scope_and_archived_search_fail_closed(self):
        scope = ReasoningScope(("project-a",))
        self.assertFalse(scope.is_cross_project)
        request = ArchivedSearchRequest(scope, ("archived-branch",))
        self.assertTrue(request.structural_only)
        for projects in ((), ("*",), ("project-a", "project-a")):
            with self.subTest(projects=projects), self.assertRaises(PrivacyPolicyError):
                ReasoningScope(projects)
        with self.assertRaises(PrivacyPolicyError):
            ArchivedSearchRequest(scope, ("*",))
        with self.assertRaises(PrivacyPolicyError):
            ArchivedSearchRequest(scope, ("archived-branch",), structural_only=False)

    def test_audit_is_read_only_and_finds_legacy_source_content(self):
        self.inbox.capture("Synthetic private source", source_id="src-a")
        self.store.append("other", "note", {"statement": "synthetic"})
        before = self.store.read_all()
        audit = self.service.audit_legacy_retention()
        self.assertFalse(audit.mutated)
        self.assertEqual(before, self.store.read_all())
        self.assertEqual(["payload.raw_text", "payload.statement"], [item.path for item in audit.findings])

    def test_quarantine_plan_is_deterministic_reversible_and_effect_free(self):
        source = self.inbox.capture("Synthetic private source", source_id="src-a")
        first = self.service.plan_quarantine(["src-a"])
        second = self.service.plan_quarantine(["src-a"])
        self.assertEqual(first, second)
        self.assertEqual((source.content_sha256,), first.source_content_hashes)
        self.assertTrue(first.reversible)
        self.assertTrue(first.local_only)
        self.assertFalse(first.external_effects)
        with self.assertRaises(PrivacyPolicyError):
            self.service.plan_quarantine(["missing"])
        with self.assertRaises(PrivacyPolicyError):
            self.service.request_purge(["src-a"])


if __name__ == "__main__":
    unittest.main()
