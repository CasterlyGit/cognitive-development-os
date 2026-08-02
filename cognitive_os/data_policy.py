from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Dict, Iterable, Optional, Tuple

from .models import Event


class DataPolicyError(RuntimeError):
    """Raised when a privacy or reasoning request exceeds its explicit scope."""


class RawRetentionMode(str, Enum):
    SESSION_ONLY = "session_only"
    LOCAL_EXPIRING = "local_expiring"


class ArchivedSearchMode(str, Enum):
    EXACT_BRANCH_ONLY = "exact_branch_only"


class DeletionMode(str, Enum):
    QUARANTINE = "quarantine"
    PURGE = "purge"


def _exact_ids(values: Iterable[str], label: str) -> Tuple[str, ...]:
    provided = tuple(values)
    try:
        resolved = tuple(dict.fromkeys(provided))
    except TypeError as exc:
        raise DataPolicyError("%s contains a non-scalar identifier" % label) from exc
    if not resolved:
        raise DataPolicyError("%s must name at least one exact identifier" % label)
    for value in resolved:
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            or any(character in value for character in "*?[]")
        ):
            raise DataPolicyError("%s contains an invalid or wildcard identifier" % label)
    return resolved


@dataclass(frozen=True)
class PrivateDataPolicy:
    project_ids: Tuple[str, ...]
    raw_retention: RawRetentionMode
    retention_days: int
    retention_approval_id: Optional[str]
    quarantine_days: int
    archived_search: ArchivedSearchMode
    cross_project_approval_id: Optional[str]

    @classmethod
    def conservative_default(cls, home_project_id: str) -> "PrivateDataPolicy":
        return cls(
            project_ids=(home_project_id,),
            raw_retention=RawRetentionMode.SESSION_ONLY,
            retention_days=0,
            retention_approval_id=None,
            quarantine_days=7,
            archived_search=ArchivedSearchMode.EXACT_BRANCH_ONLY,
            cross_project_approval_id=None,
        ).validated()

    def validated(self) -> "PrivateDataPolicy":
        projects = _exact_ids(self.project_ids, "project_ids")
        if projects != self.project_ids:
            raise DataPolicyError("project_ids must be unique and ordered")
        if isinstance(self.retention_days, bool) or not isinstance(
            self.retention_days, int
        ):
            raise DataPolicyError("retention_days must be an integer")
        if isinstance(self.quarantine_days, bool) or not isinstance(
            self.quarantine_days, int
        ):
            raise DataPolicyError("quarantine_days must be an integer")
        if not 1 <= self.quarantine_days <= 30:
            raise DataPolicyError("quarantine_days must be between 1 and 30")
        if self.raw_retention == RawRetentionMode.SESSION_ONLY:
            if self.retention_days != 0 or self.retention_approval_id is not None:
                raise DataPolicyError(
                    "session-only raw data cannot carry a persistence window or approval"
                )
        elif self.raw_retention == RawRetentionMode.LOCAL_EXPIRING:
            if not 1 <= self.retention_days <= 30:
                raise DataPolicyError(
                    "local raw retention must expire within 1 to 30 days"
                )
            if (
                not isinstance(self.retention_approval_id, str)
                or not self.retention_approval_id.strip()
            ):
                raise DataPolicyError(
                    "local raw retention requires an explicit approval identifier"
                )
        else:
            raise DataPolicyError("unsupported raw retention mode")
        if len(projects) > 1 and (
            not isinstance(self.cross_project_approval_id, str)
            or not self.cross_project_approval_id.strip()
        ):
            raise DataPolicyError(
                "cross-project reasoning requires an explicit scope approval identifier"
            )
        if len(projects) == 1 and self.cross_project_approval_id is not None:
            raise DataPolicyError(
                "single-project policy cannot carry cross-project approval"
            )
        if self.archived_search != ArchivedSearchMode.EXACT_BRANCH_ONLY:
            raise DataPolicyError("unsupported archived search mode")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_ids": list(self.project_ids),
            "raw_retention": self.raw_retention.value,
            "retention_days": self.retention_days,
            "retention_approval_id": self.retention_approval_id,
            "quarantine_days": self.quarantine_days,
            "archived_search": self.archived_search.value,
            "cross_project_approval_id": self.cross_project_approval_id,
        }


@dataclass(frozen=True)
class StructuralSearchRequest:
    project_ids: Tuple[str, ...]
    branch_ids: Tuple[str, ...] = ()
    include_archived: bool = False
    raw_query: Optional[str] = None


@dataclass(frozen=True)
class StructuralSearchAuthorization:
    project_ids: Tuple[str, ...]
    branch_ids: Tuple[str, ...]
    visible_branch_statuses: Tuple[str, ...]
    structural_only: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_ids": list(self.project_ids),
            "branch_ids": list(self.branch_ids),
            "visible_branch_statuses": list(self.visible_branch_statuses),
            "structural_only": self.structural_only,
        }


@dataclass(frozen=True)
class DeletionRequest:
    project_id: str
    source_ids: Tuple[str, ...]
    mode: DeletionMode = DeletionMode.QUARANTINE


@dataclass(frozen=True)
class QuarantinePlan:
    plan_id: str
    project_id: str
    source_ids: Tuple[str, ...]
    source_content_hashes: Tuple[str, ...]
    recovery_window_days: int
    reversible: bool
    external_effects: bool
    action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "source_ids": list(self.source_ids),
            "source_content_hashes": list(self.source_content_hashes),
            "recovery_window_days": self.recovery_window_days,
            "reversible": self.reversible,
            "external_effects": self.external_effects,
            "action": self.action,
        }


@dataclass(frozen=True)
class LegacyStorageAudit:
    event_count: int
    events_with_private_fields: int
    private_field_counts: Dict[str, int]
    migration_required: bool
    raw_values_included: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_count": self.event_count,
            "events_with_private_fields": self.events_with_private_fields,
            "private_field_counts": dict(sorted(self.private_field_counts.items())),
            "migration_required": self.migration_required,
            "raw_values_included": self.raw_values_included,
        }


class PrivateDataPolicyEngine:
    """Evaluates local policy without searching, deleting, or mutating storage."""

    PRIVATE_FIELD_NAMES = frozenset(("raw_text", "statement", "metadata"))

    def __init__(self, policy: PrivateDataPolicy) -> None:
        self.policy = policy.validated()

    def authorize_search(
        self, request: StructuralSearchRequest
    ) -> StructuralSearchAuthorization:
        if not isinstance(request.include_archived, bool):
            raise DataPolicyError("include_archived must be a boolean")
        projects = _exact_ids(request.project_ids, "search project_ids")
        if not set(projects).issubset(self.policy.project_ids):
            raise DataPolicyError("search exceeds the approved project scope")
        if request.raw_query is not None:
            raise DataPolicyError("raw-text search is outside the structural index")
        branch_ids = tuple(request.branch_ids)
        if branch_ids:
            branch_ids = _exact_ids(branch_ids, "branch_ids")
        if request.include_archived:
            if self.policy.archived_search != ArchivedSearchMode.EXACT_BRANCH_ONLY:
                raise DataPolicyError("archived search is disabled")
            if not branch_ids:
                raise DataPolicyError(
                    "archived search must name exact branch identifiers"
                )
            statuses = ("active", "promoted", "archived")
        else:
            statuses = ("active", "promoted")
        return StructuralSearchAuthorization(
            project_ids=projects,
            branch_ids=branch_ids,
            visible_branch_statuses=statuses,
            structural_only=True,
        )

    def plan_deletion(
        self, request: DeletionRequest, events: Iterable[Event]
    ) -> QuarantinePlan:
        project_id = _exact_ids((request.project_id,), "deletion project_id")[0]
        if project_id not in self.policy.project_ids:
            raise DataPolicyError("deletion request exceeds the approved project scope")
        source_ids = tuple(sorted(_exact_ids(request.source_ids, "source_ids")))
        if request.mode == DeletionMode.PURGE:
            raise DataPolicyError(
                "irreversible purge is not implemented and requires a separate exact human action"
            )
        if request.mode != DeletionMode.QUARANTINE:
            raise DataPolicyError("unsupported deletion mode")
        source_hashes: Dict[str, str] = {}
        for event in events:
            if event.event_type != "source.captured":
                continue
            source_id = event.payload.get("source_id")
            if source_id not in source_ids:
                continue
            content_hash = event.payload.get("content_sha256")
            if (
                source_id in source_hashes
                or event.stream_id != source_id
                or not isinstance(content_hash, str)
                or len(content_hash) != 64
                or any(character not in "0123456789abcdef" for character in content_hash)
            ):
                raise DataPolicyError(
                    "deletion source has ambiguous or invalid structural lineage"
                )
            source_hashes[source_id] = content_hash
        if set(source_hashes) != set(source_ids):
            raise DataPolicyError("deletion source is absent from the local ledger")
        ordered_hashes = tuple(source_hashes[source_id] for source_id in source_ids)
        identity = {
            "project_id": project_id,
            "source_ids": list(source_ids),
            "source_content_hashes": list(ordered_hashes),
            "recovery_window_days": self.policy.quarantine_days,
            "action": "quarantine_plan_only",
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()[:20]
        return QuarantinePlan(
            plan_id="quarantine_%s" % digest,
            project_id=project_id,
            source_ids=source_ids,
            source_content_hashes=ordered_hashes,
            recovery_window_days=self.policy.quarantine_days,
            reversible=True,
            external_effects=False,
            action="quarantine_plan_only",
        )

    def audit_legacy_storage(self, events: Iterable[Event]) -> LegacyStorageAudit:
        event_count = 0
        affected_events = 0
        counts = {field: 0 for field in sorted(self.PRIVATE_FIELD_NAMES)}
        for event in events:
            event_count += 1
            found = set()
            self._collect_private_field_names(event.payload, found)
            if found:
                affected_events += 1
            for field in found:
                counts[field] += 1
        counts = {field: count for field, count in counts.items() if count}
        return LegacyStorageAudit(
            event_count=event_count,
            events_with_private_fields=affected_events,
            private_field_counts=counts,
            migration_required=bool(counts),
            raw_values_included=False,
        )

    @classmethod
    def _collect_private_field_names(
        cls, value: Any, found: set
    ) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in cls.PRIVATE_FIELD_NAMES:
                    found.add(key)
                cls._collect_private_field_names(child, found)
        elif isinstance(value, (list, tuple)):
            for child in value:
                cls._collect_private_field_names(child, found)
