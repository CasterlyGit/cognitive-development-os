import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.project_decision_loop import (
    ProjectDecisionLoop,
    ProjectDecisionManifest,
    RelationshipDecision,
)
from cognitive_os.store import AppendOnlyEventStore


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "mvp_project_decision_loop.json"


def main() -> None:
    manifest = ProjectDecisionManifest.from_dict(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    with TemporaryDirectory() as directory:
        path = Path(directory) / "mvp-events.jsonl"
        first = ProjectDecisionLoop(AppendOnlyEventStore(path)).run(
            manifest,
            RelationshipDecision.ACCEPT,
            human_actor="synthetic_owner",
        )
        restarted = ProjectDecisionLoop(AppendOnlyEventStore(path)).run(
            manifest,
            RelationshipDecision.ACCEPT,
            human_actor="synthetic_owner",
        )

    output = dict(first)
    output["restart_idempotent"] = first == restarted
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
