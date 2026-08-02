from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
from typing import Any, Dict, Iterable, Optional, Tuple

from .graph import GraphSnapshot
from .intents import AtomState, ConfirmationAuthority, ConfirmationRecord
from .models import Event
from .store import AppendOnlyEventStore, DuplicateEventError, StreamRevisionError


class ContinuityError(RuntimeError):
    """Raised when branch or accepted-plan history would become ambiguous."""


class BranchAccess(str, Enum):
    ACCEPTED_PATH = "accepted_path"
    READ_ONLY = "read_only"


class BranchStatus(str, Enum):
    ACTIVE = "active"
    PROMOTED = "promoted"
    ARCHIVED = "archived"
    DISCARDED = "discarded"


class PlanVersionStatus(str, Enum):
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class BranchProposal:
    atom_id: str
    source_id: str

    def to_dict(self) -> Dict[str, str]:
        return {"atom_id": self.atom_id, "source_id": self.source_id}

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "BranchProposal":
        return cls(atom_id=value["atom_id"], source_id=value["source_id"])


@dataclass(frozen=True)
class CognitiveBranch:
    branch_id: str
    parent_branch_id: Optional[str]
    anchor_atom_id: Optional[str]
    base_plan_version_id: str
    inherited_atom_ids: Tuple[str, ...]
    inherited_source_ids: Tuple[str, ...]
    proposals: Tuple[BranchProposal, ...]
    access: BranchAccess
    status: BranchStatus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "parent_branch_id": self.parent_branch_id,
            "anchor_atom_id": self.anchor_atom_id,
            "base_plan_version_id": self.base_plan_version_id,
            "inherited_atom_ids": list(self.inherited_atom_ids),
            "inherited_source_ids": list(self.inherited_source_ids),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "access": self.access.value,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CognitiveBranch":
        return cls(
            branch_id=value["branch_id"],
            parent_branch_id=value.get("parent_branch_id"),
            anchor_atom_id=value.get("anchor_atom_id"),
            base_plan_version_id=value["base_plan_version_id"],
            inherited_atom_ids=tuple(value["inherited_atom_ids"]),
            inherited_source_ids=tuple(value["inherited_source_ids"]),
            proposals=tuple(
                BranchProposal.from_dict(item) for item in value.get("proposals", [])
            ),
            access=BranchAccess(value["access"]),
            status=BranchStatus(value["status"]),
        )


@dataclass(frozen=True)
class IntentPlanVersion:
    plan_version_id: str
    branch_id: str
    revision: int
    atom_ids: Tuple[str, ...]
    source_ids: Tuple[str, ...]
    atom_lineage: Tuple[BranchProposal, ...]
    supersedes_plan_version_id: Optional[str]
    promoted_from_branch_id: Optional[str]
    status: PlanVersionStatus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_version_id": self.plan_version_id,
            "branch_id": self.branch_id,
            "revision": self.revision,
            "atom_ids": list(self.atom_ids),
            "source_ids": list(self.source_ids),
            "atom_lineage": [item.to_dict() for item in self.atom_lineage],
            "supersedes_plan_version_id": self.supersedes_plan_version_id,
            "promoted_from_branch_id": self.promoted_from_branch_id,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "IntentPlanVersion":
        return cls(
            plan_version_id=value["plan_version_id"],
            branch_id=value["branch_id"],
            revision=int(value["revision"]),
            atom_ids=tuple(value["atom_ids"]),
            source_ids=tuple(value["source_ids"]),
            atom_lineage=tuple(
                BranchProposal.from_dict(item) for item in value["atom_lineage"]
            ),
            supersedes_plan_version_id=value.get("supersedes_plan_version_id"),
            promoted_from_branch_id=value.get("promoted_from_branch_id"),
            status=PlanVersionStatus(value["status"]),
        )


@dataclass(frozen=True)
class ContinuitySnapshot:
    continuity_id: str
    branches: Dict[str, CognitiveBranch]
    plan_versions: Dict[str, IntentPlanVersion]
    current_plan_ids: Dict[str, str]

    def current_plan(self, branch_id: str) -> IntentPlanVersion:
        try:
            return self.plan_versions[self.current_plan_ids[branch_id]]
        except KeyError as exc:
            raise ContinuityError("branch %s has no accepted plan" % branch_id) from exc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "continuity_id": self.continuity_id,
            "branches": {
                branch_id: branch.to_dict()
                for branch_id, branch in sorted(self.branches.items())
            },
            "plan_versions": [
                version.to_dict()
                for version in sorted(
                    self.plan_versions.values(),
                    key=lambda item: (item.branch_id, item.revision),
                )
            ],
            "current_plan_ids": dict(sorted(self.current_plan_ids.items())),
        }


class IntentContinuity:
    """Local event-sourced cognitive branches and immutable accepted plans."""

    def __init__(self, continuity_id: str, store: AppendOnlyEventStore) -> None:
        if not continuity_id.strip():
            raise ValueError("continuity_id must be non-empty")
        self.continuity_id = continuity_id
        self.store = store

    def snapshot(self) -> ContinuitySnapshot:
        snapshot, _ = self._snapshot_with_revision()
        return snapshot

    def _snapshot_with_revision(self) -> Tuple[ContinuitySnapshot, int]:
        events = self.store.events_for(self.continuity_id)
        branches: Dict[str, CognitiveBranch] = {}
        versions: Dict[str, IntentPlanVersion] = {}
        current_plan_ids: Dict[str, str] = {}
        for event in events:
            if event.event_type == "continuity.root_initialized":
                if branches or versions:
                    raise ContinuityError("root initialization must be the first event")
                branch = CognitiveBranch.from_dict(event.payload["branch"])
                version = IntentPlanVersion.from_dict(event.payload["plan_version"])
                self._validate_root(branch, version)
                branches[branch.branch_id] = branch
                versions[version.plan_version_id] = version
                current_plan_ids[branch.branch_id] = version.plan_version_id
            elif event.event_type == "branch.opened":
                branch = CognitiveBranch.from_dict(event.payload["branch"])
                self._replay_open(branch, branches, versions, current_plan_ids)
                branches[branch.branch_id] = branch
            elif event.event_type == "branch.atom_proposed":
                branch_id = event.payload["branch_id"]
                proposal = BranchProposal.from_dict(event.payload["proposal"])
                branch = self._active_child(branch_id, branches)
                known_ids = set(branch.inherited_atom_ids)
                known_ids.update(item.atom_id for item in branch.proposals)
                if proposal.atom_id in known_ids:
                    raise ContinuityError("duplicate or inherited branch proposal")
                if not proposal.atom_id.strip() or not proposal.source_id.strip():
                    raise ContinuityError("branch proposal lineage must be non-empty")
                branches[branch_id] = replace(
                    branch, proposals=branch.proposals + (proposal,)
                )
            elif event.event_type == "branch.promoted":
                self._replay_promotion(
                    event, branches, versions, current_plan_ids
                )
            elif event.event_type in ("branch.archived", "branch.discarded"):
                branch_id = event.payload["branch_id"]
                branch = self._active_child(branch_id, branches)
                status = (
                    BranchStatus.ARCHIVED
                    if event.event_type == "branch.archived"
                    else BranchStatus.DISCARDED
                )
                branches[branch_id] = replace(branch, status=status)
            else:
                raise ContinuityError(
                    "unsupported continuity event %s" % event.event_type
                )
        if not branches and (versions or current_plan_ids):
            raise ContinuityError("continuity history has no root")
        return (
            ContinuitySnapshot(
                continuity_id=self.continuity_id,
                branches=branches,
                plan_versions=versions,
                current_plan_ids=current_plan_ids,
            ),
            len(events),
        )

    def initialize_root(
        self,
        graph: GraphSnapshot,
        *,
        branch_id: str,
        atom_ids: Iterable[str],
        operation_id: str,
    ) -> ContinuitySnapshot:
        ordered_atom_ids = self._ordered_atoms(graph, atom_ids)
        request = {
            "branch_id": branch_id,
            "atom_ids": list(ordered_atom_ids),
        }
        replay = self._replayed(operation_id, "continuity.root_initialized", request)
        if replay:
            return self.snapshot()
        current, stream_revision = self._snapshot_with_revision()
        if current.branches:
            raise ContinuityError("continuity root is already initialized")
        self._require_identifier(branch_id, "branch_id")
        self._validate_accepted_atoms(graph, ordered_atom_ids)
        source_ids = self._source_ids(graph, ordered_atom_ids)
        version = self._plan_version(
            branch_id=branch_id,
            revision=1,
            atom_ids=ordered_atom_ids,
            source_ids=source_ids,
            atom_lineage=self._lineage(graph, ordered_atom_ids),
            supersedes=None,
            promoted_from=None,
        )
        branch = CognitiveBranch(
            branch_id=branch_id,
            parent_branch_id=None,
            anchor_atom_id=None,
            base_plan_version_id=version.plan_version_id,
            inherited_atom_ids=ordered_atom_ids,
            inherited_source_ids=source_ids,
            proposals=(),
            access=BranchAccess.ACCEPTED_PATH,
            status=BranchStatus.ACTIVE,
        )
        self._append_operation(
            operation_id,
            "continuity.root_initialized",
            request,
            {"branch": branch.to_dict(), "plan_version": version.to_dict()},
            expected_stream_revision=stream_revision,
        )
        return self.snapshot()

    def open_child(
        self,
        graph: GraphSnapshot,
        *,
        branch_id: str,
        parent_branch_id: str,
        anchor_atom_id: str,
        inherited_atom_ids: Iterable[str],
        expected_parent_plan_version_id: str,
        operation_id: str,
    ) -> ContinuitySnapshot:
        inherited = tuple(dict.fromkeys(inherited_atom_ids))
        request = {
            "branch_id": branch_id,
            "parent_branch_id": parent_branch_id,
            "anchor_atom_id": anchor_atom_id,
            "inherited_atom_ids": list(inherited),
            "expected_parent_plan_version_id": expected_parent_plan_version_id,
        }
        replay = self._replayed(operation_id, "branch.opened", request)
        if replay:
            return self.snapshot()
        self._require_identifier(branch_id, "branch_id")
        snapshot, stream_revision = self._snapshot_with_revision()
        if branch_id in snapshot.branches:
            raise ContinuityError("branch %s already exists" % branch_id)
        parent = snapshot.branches.get(parent_branch_id)
        if (
            parent is None
            or parent.status != BranchStatus.ACTIVE
            or parent.access != BranchAccess.ACCEPTED_PATH
        ):
            raise ContinuityError("parent must be the active accepted path")
        current_plan = snapshot.current_plan(parent_branch_id)
        if current_plan.plan_version_id != expected_parent_plan_version_id:
            raise ContinuityError("stale parent plan version")
        if not inherited:
            raise ContinuityError("child branch must inherit explicit context")
        if anchor_atom_id not in inherited:
            raise ContinuityError("branch anchor must be inherited")
        if not set(inherited).issubset(current_plan.atom_ids):
            raise ContinuityError("child can inherit only from the accepted parent plan")
        ordered = self._ordered_atoms(graph, inherited)
        source_ids = self._source_ids(graph, ordered)
        branch = CognitiveBranch(
            branch_id=branch_id,
            parent_branch_id=parent_branch_id,
            anchor_atom_id=anchor_atom_id,
            base_plan_version_id=current_plan.plan_version_id,
            inherited_atom_ids=ordered,
            inherited_source_ids=source_ids,
            proposals=(),
            access=BranchAccess.READ_ONLY,
            status=BranchStatus.ACTIVE,
        )
        self._append_operation(
            operation_id,
            "branch.opened",
            request,
            {"branch": branch.to_dict()},
            expected_stream_revision=stream_revision,
            causation_id=current_plan.plan_version_id,
        )
        return self.snapshot()

    def propose_atom(
        self,
        graph: GraphSnapshot,
        *,
        branch_id: str,
        atom_id: str,
        operation_id: str,
    ) -> ContinuitySnapshot:
        request = {"branch_id": branch_id, "atom_id": atom_id}
        replay = self._replayed(operation_id, "branch.atom_proposed", request)
        if replay:
            return self.snapshot()
        snapshot, stream_revision = self._snapshot_with_revision()
        branch = self._active_child(branch_id, snapshot.branches)
        if atom_id not in graph.atoms:
            raise ContinuityError("proposal references missing atom %s" % atom_id)
        if atom_id in branch.inherited_atom_ids or any(
            item.atom_id == atom_id for item in branch.proposals
        ):
            raise ContinuityError("proposal is already visible on the branch")
        proposal = BranchProposal(
            atom_id=atom_id, source_id=graph.atoms[atom_id].source_id
        )
        self._append_operation(
            operation_id,
            "branch.atom_proposed",
            request,
            {"branch_id": branch_id, "proposal": proposal.to_dict()},
            expected_stream_revision=stream_revision,
            causation_id=branch.base_plan_version_id,
        )
        return self.snapshot()

    def promote(
        self,
        graph: GraphSnapshot,
        *,
        branch_id: str,
        selected_atom_ids: Iterable[str],
        replace_atom_ids: Iterable[str],
        expected_parent_plan_version_id: str,
        confirmation: ConfirmationRecord,
        operation_id: str,
    ) -> ContinuitySnapshot:
        selected = tuple(dict.fromkeys(selected_atom_ids))
        replaced = tuple(dict.fromkeys(replace_atom_ids))
        request = {
            "branch_id": branch_id,
            "selected_atom_ids": list(selected),
            "replace_atom_ids": list(replaced),
            "expected_parent_plan_version_id": expected_parent_plan_version_id,
            "confirmation": confirmation.to_dict(),
        }
        replay = self._replayed(operation_id, "branch.promoted", request)
        if replay:
            return self.snapshot()
        self._require_human(confirmation)
        snapshot, stream_revision = self._snapshot_with_revision()
        branch = self._active_child(branch_id, snapshot.branches)
        if branch.parent_branch_id is None:
            raise ContinuityError("root branch cannot be promoted")
        parent_plan = snapshot.current_plan(branch.parent_branch_id)
        if parent_plan.plan_version_id != expected_parent_plan_version_id:
            raise ContinuityError("stale parent plan version")
        if branch.base_plan_version_id != parent_plan.plan_version_id:
            raise ContinuityError("branch is based on a stale parent plan")
        proposal_ids = {item.atom_id for item in branch.proposals}
        if not selected or not set(selected).issubset(proposal_ids):
            raise ContinuityError("promotion must select branch-only proposals")
        if not set(replaced).issubset(parent_plan.atom_ids):
            raise ContinuityError("promotion can replace only accepted parent atoms")
        self._validate_accepted_atoms(graph, selected)
        next_ids = set(parent_plan.atom_ids).difference(replaced).union(selected)
        ordered = self._ordered_atoms(graph, next_ids)
        if not ordered:
            raise ContinuityError("promotion cannot create an empty plan")
        source_ids = self._source_ids(graph, ordered)
        version = self._plan_version(
            branch_id=branch.parent_branch_id,
            revision=parent_plan.revision + 1,
            atom_ids=ordered,
            source_ids=source_ids,
            atom_lineage=self._lineage(graph, ordered),
            supersedes=parent_plan.plan_version_id,
            promoted_from=branch_id,
        )
        self._append_operation(
            operation_id,
            "branch.promoted",
            request,
            {
                "branch_id": branch_id,
                "parent_branch_id": branch.parent_branch_id,
                "expected_parent_plan_version_id": expected_parent_plan_version_id,
                "selected_atom_ids": list(selected),
                "replace_atom_ids": list(replaced),
                "confirmation": confirmation.to_dict(),
                "plan_version": version.to_dict(),
            },
            expected_stream_revision=stream_revision,
            causation_id=branch.base_plan_version_id,
        )
        return self.snapshot()

    def archive(
        self, *, branch_id: str, actor_id: str, reason: str, operation_id: str
    ) -> ContinuitySnapshot:
        return self._close_branch(
            branch_id=branch_id,
            actor_id=actor_id,
            reason=reason,
            operation_id=operation_id,
            event_type="branch.archived",
        )

    def discard(
        self, *, branch_id: str, actor_id: str, reason: str, operation_id: str
    ) -> ContinuitySnapshot:
        return self._close_branch(
            branch_id=branch_id,
            actor_id=actor_id,
            reason=reason,
            operation_id=operation_id,
            event_type="branch.discarded",
        )

    def _close_branch(
        self,
        *,
        branch_id: str,
        actor_id: str,
        reason: str,
        operation_id: str,
        event_type: str,
    ) -> ContinuitySnapshot:
        request = {"branch_id": branch_id, "actor_id": actor_id, "reason": reason}
        replay = self._replayed(operation_id, event_type, request)
        if replay:
            return self.snapshot()
        if not actor_id.strip() or not reason.strip():
            raise ContinuityError("branch closure requires actor and reason")
        snapshot, stream_revision = self._snapshot_with_revision()
        branch = self._active_child(branch_id, snapshot.branches)
        self._append_operation(
            operation_id,
            event_type,
            request,
            {"branch_id": branch_id, "actor_id": actor_id, "reason": reason},
            expected_stream_revision=stream_revision,
            causation_id=branch.base_plan_version_id,
        )
        return self.snapshot()

    def _replay_promotion(
        self,
        event: Event,
        branches: Dict[str, CognitiveBranch],
        versions: Dict[str, IntentPlanVersion],
        current_plan_ids: Dict[str, str],
    ) -> None:
        branch_id = event.payload["branch_id"]
        parent_branch_id = event.payload["parent_branch_id"]
        branch = self._active_child(branch_id, branches)
        if branch.parent_branch_id != parent_branch_id:
            raise ContinuityError("promotion parent does not match branch lineage")
        expected = event.payload["expected_parent_plan_version_id"]
        if current_plan_ids.get(parent_branch_id) != expected:
            raise ContinuityError("promotion history contains a stale parent version")
        previous = versions.get(expected)
        if previous is None or previous.status != PlanVersionStatus.ACCEPTED:
            raise ContinuityError("promotion references missing accepted plan")
        version = IntentPlanVersion.from_dict(event.payload["plan_version"])
        if version.plan_version_id in versions:
            raise ContinuityError("duplicate plan version in history")
        if (
            version.branch_id != parent_branch_id
            or version.revision != previous.revision + 1
            or version.supersedes_plan_version_id != previous.plan_version_id
            or version.promoted_from_branch_id != branch_id
            or version.status != PlanVersionStatus.ACCEPTED
        ):
            raise ContinuityError("invalid promoted plan lineage")
        self._validate_plan_version(version)
        selected = set(event.payload["selected_atom_ids"])
        proposals = {item.atom_id for item in branch.proposals}
        replaced = set(event.payload["replace_atom_ids"])
        expected_atoms = set(previous.atom_ids).difference(replaced).union(selected)
        if (
            not selected
            or not selected.issubset(proposals)
            or not replaced.issubset(previous.atom_ids)
            or set(version.atom_ids) != expected_atoms
        ):
            raise ContinuityError("promoted plan does not match branch proposal")
        confirmation = event.payload["confirmation"]
        if (
            confirmation.get("authority") != ConfirmationAuthority.HUMAN.value
            or not confirmation.get("actor_id", "").strip()
            or not confirmation.get("channel", "").strip()
        ):
            raise ContinuityError("promotion history lacks human authority")
        versions[previous.plan_version_id] = replace(
            previous, status=PlanVersionStatus.SUPERSEDED
        )
        versions[version.plan_version_id] = version
        current_plan_ids[parent_branch_id] = version.plan_version_id
        branches[branch_id] = replace(branch, status=BranchStatus.PROMOTED)

    @staticmethod
    def _validate_root(
        branch: CognitiveBranch, version: IntentPlanVersion
    ) -> None:
        IntentContinuity._validate_plan_version(version)
        if (
            branch.parent_branch_id is not None
            or branch.anchor_atom_id is not None
            or branch.access != BranchAccess.ACCEPTED_PATH
            or branch.status != BranchStatus.ACTIVE
            or branch.base_plan_version_id != version.plan_version_id
            or branch.inherited_atom_ids != version.atom_ids
            or branch.inherited_source_ids != version.source_ids
            or branch.proposals
            or version.branch_id != branch.branch_id
            or version.revision != 1
            or version.supersedes_plan_version_id is not None
            or version.promoted_from_branch_id is not None
            or version.status != PlanVersionStatus.ACCEPTED
        ):
            raise ContinuityError("invalid root continuity record")

    @staticmethod
    def _validate_plan_version(version: IntentPlanVersion) -> None:
        lineage_atom_ids = tuple(item.atom_id for item in version.atom_lineage)
        lineage_source_ids = tuple(
            sorted({item.source_id for item in version.atom_lineage})
        )
        if (
            version.revision < 1
            or not version.atom_ids
            or len(set(version.atom_ids)) != len(version.atom_ids)
            or lineage_atom_ids != version.atom_ids
            or lineage_source_ids != version.source_ids
            or any(
                not item.atom_id.strip() or not item.source_id.strip()
                for item in version.atom_lineage
            )
        ):
            raise ContinuityError("invalid plan-version provenance")

    @staticmethod
    def _replay_open(
        branch: CognitiveBranch,
        branches: Dict[str, CognitiveBranch],
        versions: Dict[str, IntentPlanVersion],
        current_plan_ids: Dict[str, str],
    ) -> None:
        if branch.branch_id in branches:
            raise ContinuityError("duplicate branch in history")
        parent = branches.get(branch.parent_branch_id or "")
        base = versions.get(branch.base_plan_version_id)
        if (
            parent is None
            or parent.status != BranchStatus.ACTIVE
            or parent.access != BranchAccess.ACCEPTED_PATH
            or current_plan_ids.get(parent.branch_id) != branch.base_plan_version_id
            or base is None
            or branch.anchor_atom_id not in branch.inherited_atom_ids
            or not set(branch.inherited_atom_ids).issubset(base.atom_ids)
            or branch.access != BranchAccess.READ_ONLY
            or branch.status != BranchStatus.ACTIVE
            or branch.proposals
        ):
            raise ContinuityError("invalid child branch lineage")
        lineage = {item.atom_id: item.source_id for item in base.atom_lineage}
        expected_sources = tuple(
            sorted({lineage[atom_id] for atom_id in branch.inherited_atom_ids})
        )
        if branch.inherited_source_ids != expected_sources:
            raise ContinuityError("invalid inherited source lineage")

    @staticmethod
    def _active_child(
        branch_id: str, branches: Dict[str, CognitiveBranch]
    ) -> CognitiveBranch:
        branch = branches.get(branch_id)
        if branch is None:
            raise ContinuityError("unknown branch %s" % branch_id)
        if branch.parent_branch_id is None:
            raise ContinuityError("operation requires a child branch")
        if branch.status != BranchStatus.ACTIVE:
            raise ContinuityError("branch %s is not active" % branch_id)
        if branch.access != BranchAccess.READ_ONLY:
            raise ContinuityError("child branch must remain read-only")
        return branch

    def _replayed(
        self, operation_id: str, event_type: str, request: Dict[str, Any]
    ) -> Optional[Event]:
        self._require_identifier(operation_id, "operation_id")
        event_id = self._operation_event_id(operation_id)
        request_digest = self._digest(request)
        for event in self.store.read_all():
            if event.event_id != event_id:
                continue
            if (
                event.stream_id == self.continuity_id
                and event.event_type == event_type
                and event.payload.get("operation_id") == operation_id
                and event.payload.get("request_digest") == request_digest
            ):
                return event
            raise ContinuityError("operation_id was already used for different input")
        return None

    def _append_operation(
        self,
        operation_id: str,
        event_type: str,
        request: Dict[str, Any],
        payload: Dict[str, Any],
        *,
        expected_stream_revision: int,
        causation_id: Optional[str] = None,
    ) -> Event:
        value = dict(payload)
        value["operation_id"] = operation_id
        value["request_digest"] = self._digest(request)
        try:
            return self.store.append(
                self.continuity_id,
                event_type,
                value,
                event_id=self._operation_event_id(operation_id),
                causation_id=causation_id,
                expected_stream_revision=expected_stream_revision,
            )
        except DuplicateEventError:
            replayed = self._replayed(operation_id, event_type, request)
            if replayed is None:
                raise ContinuityError("operation replay could not be reconciled")
            return replayed
        except StreamRevisionError as exc:
            replayed = self._replayed(operation_id, event_type, request)
            if replayed is not None:
                return replayed
            raise ContinuityError(
                "continuity changed during append; retry from fresh state"
            ) from exc

    def _operation_event_id(self, operation_id: str) -> str:
        return "continuity_op_%s" % self._digest(
            {"continuity_id": self.continuity_id, "operation_id": operation_id}
        )

    def _plan_version(
        self,
        *,
        branch_id: str,
        revision: int,
        atom_ids: Tuple[str, ...],
        source_ids: Tuple[str, ...],
        atom_lineage: Tuple[BranchProposal, ...],
        supersedes: Optional[str],
        promoted_from: Optional[str],
    ) -> IntentPlanVersion:
        identity = {
            "continuity_id": self.continuity_id,
            "branch_id": branch_id,
            "revision": revision,
            "atom_ids": list(atom_ids),
            "source_ids": list(source_ids),
            "atom_lineage": [item.to_dict() for item in atom_lineage],
            "supersedes": supersedes,
            "promoted_from": promoted_from,
        }
        return IntentPlanVersion(
            plan_version_id="intent_plan_%s" % self._digest(identity),
            branch_id=branch_id,
            revision=revision,
            atom_ids=atom_ids,
            source_ids=source_ids,
            atom_lineage=atom_lineage,
            supersedes_plan_version_id=supersedes,
            promoted_from_branch_id=promoted_from,
            status=PlanVersionStatus.ACCEPTED,
        )

    @staticmethod
    def _ordered_atoms(
        graph: GraphSnapshot, atom_ids: Iterable[str]
    ) -> Tuple[str, ...]:
        requested = tuple(dict.fromkeys(atom_ids))
        if not requested:
            raise ContinuityError("at least one atom is required")
        missing = [atom_id for atom_id in requested if atom_id not in graph.atoms]
        if missing:
            raise ContinuityError("missing atom %s" % missing[0])
        selected = set(requested)
        return tuple(
            atom_id for atom_id in graph.topological_order() if atom_id in selected
        )

    @staticmethod
    def _source_ids(
        graph: GraphSnapshot, atom_ids: Iterable[str]
    ) -> Tuple[str, ...]:
        return tuple(sorted({graph.atoms[atom_id].source_id for atom_id in atom_ids}))

    @staticmethod
    def _lineage(
        graph: GraphSnapshot, atom_ids: Iterable[str]
    ) -> Tuple[BranchProposal, ...]:
        return tuple(
            BranchProposal(atom_id=atom_id, source_id=graph.atoms[atom_id].source_id)
            for atom_id in atom_ids
        )

    @staticmethod
    def _validate_accepted_atoms(
        graph: GraphSnapshot, atom_ids: Iterable[str]
    ) -> None:
        for atom_id in atom_ids:
            atom = graph.atoms[atom_id]
            if atom.requires_human_confirmation and atom.state != AtomState.CONFIRMED:
                raise ContinuityError(
                    "accepted plan includes unconfirmed atom %s" % atom_id
                )

    @staticmethod
    def _require_human(confirmation: ConfirmationRecord) -> None:
        if (
            confirmation.authority != ConfirmationAuthority.HUMAN
            or not confirmation.actor_id.strip()
            or not confirmation.channel.strip()
        ):
            raise ContinuityError("promotion requires explicit human authority")

    @staticmethod
    def _require_identifier(value: str, label: str) -> None:
        if not value.strip():
            raise ContinuityError("%s must be non-empty" % label)

    @staticmethod
    def _digest(value: Dict[str, Any]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()[:20]
