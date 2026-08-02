"""Run the complete synthetic dry-run control plane in a temporary ledger."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.pipeline import DryRunControlPlane, DryRunManifest
from cognitive_os.store import AppendOnlyEventStore


def main() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "layer5_end_to_end.json"
    manifest = DryRunManifest.from_dict(
        json.loads(fixture_path.read_text(encoding="utf-8"))
    )
    with TemporaryDirectory() as directory:
        store = AppendOnlyEventStore(Path(directory) / "events.jsonl")
        control_plane = DryRunControlPlane(store)
        first = control_plane.run(manifest)
        event_count = len(store.read_all())
        replay = control_plane.run(manifest)
        output = first.to_dict()
        output["verification"] = {
            "idempotent_replay": replay.to_dict() == first.to_dict(),
            "event_count_unchanged": len(store.read_all()) == event_count,
            "restart_store_readable": len(
                AppendOnlyEventStore(store.path).read_all()
            )
            == event_count,
        }
        print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
