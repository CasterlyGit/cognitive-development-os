import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.data_policy import (
    DataPolicyError,
    DeletionRequest,
    PrivateDataPolicy,
    PrivateDataPolicyEngine,
    StructuralSearchRequest,
)
from cognitive_os.intents import IntentExtractor, IntentLifecycle
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "stage1e_private_data_policy.json"


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    policy = PrivateDataPolicy.conservative_default(fixture["home_project_id"])
    engine = PrivateDataPolicyEngine(policy)

    active_search = engine.authorize_search(
        StructuralSearchRequest(project_ids=(fixture["home_project_id"],))
    )
    archived_search = engine.authorize_search(
        StructuralSearchRequest(
            project_ids=(fixture["home_project_id"],),
            branch_ids=(fixture["exact_archived_branch_id"],),
            include_archived=True,
        )
    )
    ambient_cross_project_rejected = False
    try:
        engine.authorize_search(
            StructuralSearchRequest(
                project_ids=(fixture["home_project_id"], "ambient-other-project")
            )
        )
    except DataPolicyError:
        ambient_cross_project_rejected = True

    with TemporaryDirectory() as directory:
        store = AppendOnlyEventStore(Path(directory) / "legacy-events.jsonl")
        source = IntentInbox(store).capture(
            "Synthetic private source used only to prove the audit.",
            source_id=fixture["quarantine_source_ids"][0],
        )
        IntentLifecycle(store).propose(IntentExtractor().extract(source)[0])
        events = store.read_all()
        quarantine = engine.plan_deletion(
            DeletionRequest(
                project_id=fixture["home_project_id"],
                source_ids=tuple(fixture["quarantine_source_ids"]),
            ),
            events,
        )
        audit = engine.audit_legacy_storage(events)

    print(
        json.dumps(
            {
                "schema_version": "1.0",
                "policy": policy.to_dict(),
                "active_search": active_search.to_dict(),
                "archived_search_requires_exact_branch": (
                    "archived" in archived_search.visible_branch_statuses
                    and archived_search.branch_ids
                    == (fixture["exact_archived_branch_id"],)
                ),
                "ambient_cross_project_rejected": ambient_cross_project_rejected,
                "quarantine_plan": quarantine.to_dict(),
                "legacy_storage_audit": audit.to_dict(),
                "external_effects": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
