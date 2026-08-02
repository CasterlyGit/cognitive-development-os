"""Demonstrate local-only privacy defaults without changing a ledger."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitive_os.privacy_policy import ArchivedSearchRequest, PrivacyPolicyError, PrivacyPolicyService, ReasoningScope, RetentionPolicy
from cognitive_os.store import AppendOnlyEventStore, IntentInbox


def main() -> None:
    with TemporaryDirectory() as directory:
        store = AppendOnlyEventStore(Path(directory) / "events.jsonl")
        source = IntentInbox(store).capture("Synthetic private source", source_id="src-demo")
        service = PrivacyPolicyService(store)
        before = store.read_all()
        audit = service.audit_legacy_retention()
        plan = service.plan_quarantine([source.source_id])
        wildcard_rejected = False
        try:
            ReasoningScope(("*",))
        except PrivacyPolicyError:
            wildcard_rejected = True
        archived = ArchivedSearchRequest(ReasoningScope(("demo-project",)), ("archived-1",))
        print(json.dumps({"external_effects": False, "default_retention": RetentionPolicy().mode.value, "audit_read_only": before == store.read_all() and not audit.mutated, "quarantine_reversible": plan.reversible, "archived_search_structural_only": archived.structural_only, "wildcard_scope_rejected": wildcard_rejected}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
