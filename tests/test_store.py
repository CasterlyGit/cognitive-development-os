import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cognitive_os.models import SourceKind
from cognitive_os.store import (
    AppendOnlyEventStore,
    CorruptStoreError,
    DuplicateEventError,
    IntentInbox,
    SourceConflictError,
)


class IntentInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.jsonl"
        self.store = AppendOnlyEventStore(self.path)
        self.inbox = IntentInbox(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_capture_preserves_exact_raw_source_and_survives_restart(self):
        raw = "Maybe explore local status.\nBut don't change Krish yet."
        source = self.inbox.capture(raw, kind=SourceKind.VOICE_TRANSCRIPT)

        restarted = IntentInbox(AppendOnlyEventStore(self.path))
        loaded = list(restarted.sources())

        self.assertEqual([raw], [item.raw_text for item in loaded])
        self.assertEqual(source.content_sha256, loaded[0].content_sha256)
        self.assertEqual(1, self.store.read_all()[0].sequence)

    def test_rejects_empty_source_without_writing(self):
        with self.assertRaises(ValueError):
            self.inbox.capture("  \n")
        self.assertFalse(self.path.exists())

    def test_duplicate_event_id_is_rejected(self):
        self.store.append("stream", "one", {}, event_id="same")
        with self.assertRaises(DuplicateEventError):
            self.store.append("stream", "two", {}, event_id="same")
        self.assertEqual(1, len(self.store.read_all()))

    def test_corrupt_partial_line_fails_closed(self):
        self.path.write_text('{"sequence": 1', encoding="utf-8")
        with self.assertRaises(CorruptStoreError):
            self.store.read_all()
        with self.assertRaises(CorruptStoreError):
            self.store.append("stream", "event", {})

    def test_non_monotonic_history_fails_closed(self):
        event = self.store.append("stream", "one", {})
        value = event.to_dict()
        value["sequence"] = 8
        self.path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        with self.assertRaises(CorruptStoreError):
            self.store.read_all()

    def test_same_source_capture_is_idempotent(self):
        first = self.inbox.capture("Synthetic intent.", source_id="stable")
        second = self.inbox.capture("Synthetic intent.", source_id="stable")
        self.assertEqual(first, second)
        self.assertEqual(1, len(self.store.read_all()))

    def test_source_id_cannot_be_reused_for_different_content(self):
        self.inbox.capture("First synthetic intent.", source_id="stable")
        with self.assertRaises(SourceConflictError):
            self.inbox.capture("Changed synthetic intent.", source_id="stable")
        self.assertEqual(1, len(self.store.read_all()))


if __name__ == "__main__":
    unittest.main()
