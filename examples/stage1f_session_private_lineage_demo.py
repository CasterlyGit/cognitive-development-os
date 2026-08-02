import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.data_policy import PrivateDataPolicy, PrivateDataPolicyEngine
from cognitive_os.private_lineage import (
    PrivateContentUnavailable,
    PrivateLineageSession,
    SessionContentVault,
)
from cognitive_os.store import AppendOnlyEventStore


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "stage1f_session_private_lineage.json"
FORBIDDEN_FIELDS = frozenset(("raw_text", "statement", "metadata"))


def _payload_keys(value):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            found.add(key)
            found.update(_payload_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_payload_keys(child))
    return found


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    policy = PrivateDataPolicy.conservative_default(fixture["home_project_id"])

    with TemporaryDirectory() as directory:
        ledger_path = Path(directory) / "structural-events.jsonl"
        store = AppendOnlyEventStore(ledger_path)
        session = PrivateLineageSession(store, SessionContentVault(), policy)
        source = session.capture(
            fixture["source_text"],
            source_id=fixture["source_id"],
            metadata=fixture["metadata"],
        )
        atoms = session.extract_and_record(source.source_id)
        before_restart = session.snapshot().to_dict()
        events = store.read_all()
        persisted_keys = set()
        for event in events:
            persisted_keys.update(_payload_keys(event.payload))
        content_available_during_session = (
            session.materialize_source(source.source_id).raw_text
            == fixture["source_text"]
        )
        removed_references = session.end_session()

        restarted = PrivateLineageSession(
            AppendOnlyEventStore(ledger_path), SessionContentVault(), policy
        )
        content_unavailable_after_restart = False
        try:
            restarted.materialize_source(source.source_id)
        except PrivateContentUnavailable:
            content_unavailable_after_restart = True
        after_restart = restarted.snapshot().to_dict()
        audit = PrivateDataPolicyEngine(policy).audit_legacy_storage(events)

    print(
        json.dumps(
            {
                "schema_version": "2.0",
                "source_count": len(before_restart["sources"]),
                "atom_count": len(atoms),
                "structural_snapshot_restart_safe": before_restart == after_restart,
                "content_available_during_session": content_available_during_session,
                "session_references_removed": removed_references,
                "content_unavailable_after_restart": (
                    content_unavailable_after_restart
                ),
                "forbidden_payload_fields_absent": FORBIDDEN_FIELDS.isdisjoint(
                    persisted_keys
                ),
                "legacy_migration_required_for_v2_events": audit.migration_required,
                "external_effects": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
