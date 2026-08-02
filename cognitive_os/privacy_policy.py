"""Local, read-only privacy and reasoning-scope policy primitives.

These models deliberately prepare audits and quarantine plans without changing a
ledger or touching any external system. Applying a quarantine or purging data is
outside this module's authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Dict, Iterable, Tuple

from .models import Event
from .store import AppendOnlyEventStore


class PrivacyPolicyError(ValueError):
    """Raised when a privacy or reasoning request exceeds the local policy."""


class RetentionMode(str, Enum):
    SESSION_ONLY = "session_only"
    LOCAL_TIME_BOUNDED = "local_time_bounded"


@dataclass(frozen=True)
class RetentionPolicy:
    mode: RetentionMode = RetentionMode.SESSION_ONLY
    window_hours: int | None = None

    def __post_init__(self) -> None:
        if self.mode is RetentionMode.SESSION_ONLY:
            if self.window_hours is not None:
                raise PrivacyPolicyError("session-only retention cannot set a window")
            return
        if (
            isinstance(self.window_hours, bool)
            or not isinstance(self.window_hours, int)
            or not 1 <= self.window_hours <= 24 * 365
        ):
            raise PrivacyPolicyError(
                "local time-bounded retention requires an explicit 1..8760 hour window"
            )


@dataclass(frozen=True)
class ReasoningScope:
    project_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.project_ids:
            raise PrivacyPolicyError("reasoning scope must name at least one project")
        if len(set(self.project_ids)) != len(self.project_ids):
            raise PrivacyPolicyError("reasoning scope cannot repeat project identifiers")
        for project_id in self.project_ids:
            if not isinstance(project_id, str) or not project_id.strip() or "*" in project_id:
                raise PrivacyPolicyError("reasoning scope rejects empty or wildcard projects")

    @property
    def is_cross_project(self) -> bool:
        return len(self.project_ids) > 1


@dataclass(frozen=True)
class ArchivedSearchRequest:
    scope: ReasoningScope
    branch_ids: Tuple[str, ...]
    structural_only: bool = True

    def __post_init__(self) -> None:
        if not self.branch_ids:
            raise PrivacyPolicyError("archived search must name exact branches")
        if not self.structural_only:
            raise PrivacyPolicyError("archived search is structural-only")
        for branch_id in self.branch_ids:
            if not isinstance(branch_id, str) or not branch_id.strip() or "*" in branch_id:
                raise PrivacyPolicyError("archived search rejects empty or wildcard branches")


@dataclass(frozen=True)
class LegacyFieldFinding:
    event_id: str
    sequence: int
    path: str


@dataclass(frozen=True)
class LegacyLedgerAudit:
    findings: Tuple[LegacyFieldFinding, ...]
    event_count: int
    mutated: bool = False


@dataclass(frozen=True)
class QuarantinePlan:
    plan_id: str
    source_ids: Tuple[str, ...]
    source_content_hashes: Tuple[str, ...]
    reversible: bool = True
    local_only: bool = True
    external_effects: bool = False


class PrivacyPolicyService:
    """Produces deterministic, read-only privacy evidence from a local ledger."""

    _RETAINED_FIELDS = frozenset({"raw_text", "statement"})

    def __init__(self, store: AppendOnlyEventStore) -> None:
        self.store = store

    def audit_legacy_retention(self) -> LegacyLedgerAudit:
        events = self.store.read_all()
        findings = []
        for event in events:
            for path in self._retained_paths(event.payload):
                findings.append(LegacyFieldFinding(event.event_id, event.sequence, path))
        return LegacyLedgerAudit(tuple(findings), len(events))

    def plan_quarantine(self, source_ids: Iterable[str]) -> QuarantinePlan:
        requested = tuple(sorted(set(source_ids)))
        if not requested or any(not isinstance(item, str) or not item.strip() for item in requested):
            raise PrivacyPolicyError("quarantine requires exact non-empty source identifiers")
        hashes: Dict[str, str] = {}
        for event in self.store.read_all():
            if event.event_type != "source.captured":
                continue
            source_id = event.payload.get("source_id")
            content_hash = event.payload.get("content_sha256")
            if source_id in requested:
                if not isinstance(content_hash, str) or len(content_hash) != 64:
                    raise PrivacyPolicyError("source has no valid content hash")
                hashes[source_id] = content_hash
        if set(hashes) != set(requested):
            raise PrivacyPolicyError("quarantine source is absent or ambiguous")
        canonical = json.dumps(
            {"source_ids": requested, "content_hashes": [hashes[item] for item in requested]},
            separators=(",", ":"),
            sort_keys=True,
        )
        return QuarantinePlan(
            plan_id="quarantine_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24],
            source_ids=requested,
            source_content_hashes=tuple(hashes[item] for item in requested),
        )

    def request_purge(self, source_ids: Iterable[str]) -> None:
        del source_ids
        raise PrivacyPolicyError("irreversible purge is not implemented; require exact human action")

    @classmethod
    def _retained_paths(cls, value: Any, path: str = "payload") -> Tuple[str, ...]:
        if isinstance(value, dict):
            paths = []
            for key in sorted(value):
                child_path = path + "." + str(key)
                if key in cls._RETAINED_FIELDS:
                    paths.append(child_path)
                paths.extend(cls._retained_paths(value[key], child_path))
            return tuple(paths)
        if isinstance(value, list):
            paths = []
            for index, item in enumerate(value):
                paths.extend(cls._retained_paths(item, "%s[%d]" % (path, index)))
            return tuple(paths)
        return ()
