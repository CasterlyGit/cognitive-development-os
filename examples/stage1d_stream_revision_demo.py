"""Show stream-local compare-and-append rejecting a stale local writer."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.store import AppendOnlyEventStore, StreamRevisionError


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "stage1d_stream_revision.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        store = AppendOnlyEventStore(Path(directory) / "events.jsonl")
        store.append(
            fixture["target_stream"],
            fixture["first_event"],
            {"synthetic": True},
            expected_stream_revision=0,
        )
        store.append(
            fixture["unrelated_stream"],
            fixture["unrelated_event"],
            {"synthetic": True},
            expected_stream_revision=0,
        )
        before_stale = len(store.read_all())
        stale_rejected = False
        try:
            store.append(
                fixture["target_stream"],
                fixture["stale_event"],
                {"synthetic": True},
                expected_stream_revision=0,
            )
        except StreamRevisionError:
            stale_rejected = True
        after_stale = len(store.read_all())
        store.append(
            fixture["target_stream"],
            fixture["next_event"],
            {"synthetic": True},
            expected_stream_revision=1,
        )
        target_events = store.events_for(fixture["target_stream"])
        packet = {
            "schema_version": "1.0",
            "external_effects": False,
            "stale_write_rejected": stale_rejected,
            "stale_rejection_appended_nothing": before_stale == after_stale,
            "unrelated_stream_did_not_conflict": len(
                store.events_for(fixture["unrelated_stream"])
            )
            == 1,
            "target_event_types": [event.event_type for event in target_events],
            "target_revision": len(target_events),
        }
        print(json.dumps(packet, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
