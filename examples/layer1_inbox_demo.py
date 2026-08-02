"""Capture a synthetic conversation into a temporary append-only ledger."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.models import SourceKind
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "layer1_intent.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        store = AppendOnlyEventStore(Path(directory) / "events.jsonl")
        inbox = IntentInbox(store)
        source = inbox.capture(
            fixture["raw_text"],
            kind=SourceKind(fixture["kind"]),
            source_id=fixture["source_id"],
            metadata=fixture["metadata"],
        )
        restarted = IntentInbox(AppendOnlyEventStore(store.path))
        restored = list(restarted.sources())
        print(
            json.dumps(
                {
                    "event_count": len(store.read_all()),
                    "source_id": source.source_id,
                    "source_preserved": restored[0].raw_text == fixture["raw_text"],
                    "content_sha256": source.content_sha256,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
