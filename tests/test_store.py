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
    StreamRevisionError,
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

    def test_expected_stream_revision_is_checked_under_append_lock(self):
        self.store.append("target", "one", {}, expected_stream_revision=0)
        before = len(self.store.read_all())
        with self.assertRaisesRegex(StreamRevisionError, "expected 0, actual 1"):
            self.store.append("target", "stale", {}, expected_stream_revision=0)
        self.assertEqual(before, len(self.store.read_all()))
        second = self.store.append(
            "target", "two", {}, expected_stream_revision=1
        )
        self.assertEqual("two", second.event_type)

    def test_stream_revision_ignores_unrelated_streams(self):
        self.store.append("other", "one", {})
        event = self.store.append(
            "target", "first", {}, expected_stream_revision=0
        )
        self.assertEqual("target", event.stream_id)

    def test_invalid_expected_stream_revision_is_rejected_without_write(self):
        for invalid in (-1, 1.5, True, "0"):
            with self.subTest(invalid=invalid):
                before = len(self.store.read_all())
                with self.assertRaises(ValueError):
                    self.store.append(
                        "target",
                        "invalid",
                        {},
                        expected_stream_revision=invalid,
                    )
                self.assertEqual(before, len(self.store.read_all()))


if __name__ == "__main__":
    unittest.main()
