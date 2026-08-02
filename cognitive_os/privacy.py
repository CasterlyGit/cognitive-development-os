from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any, Dict, Iterable, Optional, Tuple

from .continuity import (
    BranchAccess,
    CognitiveBranch,
    ContinuitySnapshot,
    IntentPlanVersion,
    PlanVersionStatus,
)
from .graph import GraphSnapshot
from .intents import SemanticConfidence
from .models import SourceRecord


class PrivacyExportError(RuntimeError):
    """Raised when a public export could be incomplete or disclose local data."""


@dataclass(frozen=True)
class PublicSourceRecord:
    source_ref: str
    kind: str

    def to_dict(self) -> Dict[str, str]:
        return {"source_ref": self.source_ref, "kind": self.kind}


@dataclass(frozen=True)
class PublicAtomRecord:
    atom_ref: str
    source_ref: str
    kind: str
    state: str
    requires_human_confirmation: bool
    extraction_method: str
    semantic_confidence: SemanticConfidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "atom_ref": self.atom_ref,
            "source_ref": self.source_ref,
            "kind": self.kind,
            "state": self.state,
            "requires_human_confirmation": self.requires_human_confirmation,
            "extraction_method": self.extraction_method,
            "semantic_confidence": self.semantic_confidence.to_dict(),
        }


@dataclass(frozen=True)
class PublicBranchRecord:
    branch_ref: str
    parent_branch_ref: Optional[str]
    anchor_atom_ref: Optional[str]
    base_plan_ref: str
    inherited_atom_refs: Tuple[str, ...]
    inherited_source_refs: Tuple[str, ...]
    proposal_atom_refs: Tuple[str, ...]
    access: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_ref": self.branch_ref,
            "parent_branch_ref": self.parent_branch_ref,
            "anchor_atom_ref": self.anchor_atom_ref,
            "base_plan_ref": self.base_plan_ref,
            "inherited_atom_refs": list(self.inherited_atom_refs),
            "inherited_source_refs": list(self.inherited_source_refs),
            "proposal_atom_refs": list(self.proposal_atom_refs),
            "access": self.access,
            "status": self.status,
        }


@dataclass(frozen=True)
class PublicPlanVersionRecord:
    plan_ref: str
    branch_ref: str
    revision: int
    atom_refs: Tuple[str, ...]
    source_refs: Tuple[str, ...]
    supersedes_plan_ref: Optional[str]
    promoted_from_branch_ref: Optional[str]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_ref": self.plan_ref,
            "branch_ref": self.branch_ref,
            "revision": self.revision,
            "atom_refs": list(self.atom_refs),
            "source_refs": list(self.source_refs),
            "supersedes_plan_ref": self.supersedes_plan_ref,
            "promoted_from_branch_ref": self.promoted_from_branch_ref,
            "status": self.status,
        }


@dataclass(frozen=True)
class PublicContinuityPacket:
    schema_version: str
    export_scope_ref: str
    continuity_ref: str
    raw_source_included: bool
    statements_included: bool
    sources: Tuple[PublicSourceRecord, ...]
    atoms: Tuple[PublicAtomRecord, ...]
    branches: Tuple[PublicBranchRecord, ...]
    plan_versions: Tuple[PublicPlanVersionRecord, ...]
    current_plan_refs: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "export_scope_ref": self.export_scope_ref,
            "continuity_ref": self.continuity_ref,
            "raw_source_included": self.raw_source_included,
            "statements_included": self.statements_included,
            "sources": [item.to_dict() for item in self.sources],
            "atoms": [item.to_dict() for item in self.atoms],
            "branches": [item.to_dict() for item in self.branches],
            "plan_versions": [item.to_dict() for item in self.plan_versions],
            "current_plan_refs": dict(sorted(self.current_plan_refs.items())),
        }


class PublicContinuityExporter:
    """Build a structural packet whose schema has no raw-source fields."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, export_scope_key: str) -> None:
        if len(export_scope_key) != 64 or any(
            character not in "0123456789abcdef" for character in export_scope_key
        ):
            raise ValueError("export_scope_key must be 32 bytes of lowercase hex")
        self.export_scope_key = export_scope_key

    def export(
        self,
        graph: GraphSnapshot,
        continuity: ContinuitySnapshot,
        sources: Iterable[SourceRecord],
        *,
        include_raw_source: bool = False,
        include_statements: bool = False,
    ) -> PublicContinuityPacket:
        if include_raw_source or include_statements:
            raise PrivacyExportError(
                "public continuity export cannot include raw source or statements"
            )
        source_map = self._source_map(sources)
        referenced_atom_ids = self._referenced_atom_ids(continuity)
        self._validate_graph_lineage(graph, source_map, referenced_atom_ids)
        self._validate_continuity_lineage(graph, continuity)

        referenced_source_ids = {
            graph.atoms[atom_id].source_id for atom_id in referenced_atom_ids
        }
        public_sources = tuple(
            sorted(
                (
                    PublicSourceRecord(
                        source_ref=self._ref("source", source_id),
                        kind=source_map[source_id].kind.value,
                    )
                    for source_id in referenced_source_ids
                ),
                key=lambda item: item.source_ref,
            )
        )
        public_atoms = tuple(
            sorted(
                (
                    self._public_atom(graph, atom_id)
                    for atom_id in referenced_atom_ids
                ),
                key=lambda item: item.atom_ref,
            )
        )
        public_branches = tuple(
            sorted(
                (
                    self._public_branch(branch)
                    for branch in continuity.branches.values()
                ),
                key=lambda item: item.branch_ref,
            )
        )
        public_versions = tuple(
            sorted(
                (
                    self._public_plan(version)
                    for version in continuity.plan_versions.values()
                ),
                key=lambda item: (item.branch_ref, item.revision),
            )
        )
        current_plan_refs = {
            self._ref("branch", branch_id): self._ref("plan", plan_id)
            for branch_id, plan_id in continuity.current_plan_ids.items()
        }
        return PublicContinuityPacket(
            schema_version=self.SCHEMA_VERSION,
            export_scope_ref="public_scope_%s"
            % hashlib.sha256(bytes.fromhex(self.export_scope_key)).hexdigest()[:32],
            continuity_ref=self._ref("continuity", continuity.continuity_id),
            raw_source_included=False,
            statements_included=False,
            sources=public_sources,
            atoms=public_atoms,
            branches=public_branches,
            plan_versions=public_versions,
            current_plan_refs=current_plan_refs,
        )

    @staticmethod
    def _source_map(sources: Iterable[SourceRecord]) -> Dict[str, SourceRecord]:
        resolved: Dict[str, SourceRecord] = {}
        for source in sources:
            if source.source_id in resolved:
                raise PrivacyExportError(
                    "duplicate source record %s" % source.source_id
                )
            digest = hashlib.sha256(source.raw_text.encode("utf-8")).hexdigest()
            if digest != source.content_sha256:
                raise PrivacyExportError(
                    "source content digest mismatch for %s" % source.source_id
                )
            resolved[source.source_id] = source
        return resolved

    @staticmethod
    def _referenced_atom_ids(continuity: ContinuitySnapshot) -> Tuple[str, ...]:
        referenced = set()
        for branch in continuity.branches.values():
            referenced.update(branch.inherited_atom_ids)
            referenced.update(proposal.atom_id for proposal in branch.proposals)
            if branch.anchor_atom_id is not None:
                referenced.add(branch.anchor_atom_id)
        for version in continuity.plan_versions.values():
            referenced.update(version.atom_ids)
        if not referenced:
            raise PrivacyExportError("continuity packet has no referenced atoms")
        return tuple(sorted(referenced))

    @staticmethod
    def _validate_graph_lineage(
        graph: GraphSnapshot,
        sources: Dict[str, SourceRecord],
        atom_ids: Iterable[str],
    ) -> None:
        for atom_id in atom_ids:
            atom = graph.atoms.get(atom_id)
            if atom is None:
                raise PrivacyExportError("missing graph atom %s" % atom_id)
            source = sources.get(atom.source_id)
            if source is None:
                raise PrivacyExportError(
                    "missing source for graph atom %s" % atom_id
                )
            if (
                atom.source_start < 0
                or atom.source_end <= atom.source_start
                or atom.source_end > len(source.raw_text)
                or source.raw_text[atom.source_start : atom.source_end]
                != atom.statement
            ):
                raise PrivacyExportError(
                    "atom/source span mismatch for %s" % atom_id
                )

    @staticmethod
    def _validate_continuity_lineage(
        graph: GraphSnapshot, continuity: ContinuitySnapshot
    ) -> None:
        for branch in continuity.branches.values():
            base_version = continuity.plan_versions.get(branch.base_plan_version_id)
            if base_version is None:
                raise PrivacyExportError("branch references missing base plan")
            expected_base_branch = branch.parent_branch_id or branch.branch_id
            if base_version.branch_id != expected_base_branch:
                raise PrivacyExportError("branch base-plan lineage mismatch")
            if (
                branch.parent_branch_id is not None
                and branch.parent_branch_id not in continuity.branches
            ):
                raise PrivacyExportError("branch references missing parent")
            if (
                branch.anchor_atom_id is not None
                and branch.anchor_atom_id not in branch.inherited_atom_ids
            ):
                raise PrivacyExportError("branch anchor is outside inherited context")
            inherited_sources = tuple(
                sorted(
                    {
                        graph.atoms[atom_id].source_id
                        for atom_id in branch.inherited_atom_ids
                    }
                )
            )
            if inherited_sources != branch.inherited_source_ids:
                raise PrivacyExportError(
                    "branch inherited source lineage mismatch"
                )
            for proposal in branch.proposals:
                if graph.atoms[proposal.atom_id].source_id != proposal.source_id:
                    raise PrivacyExportError("branch proposal source lineage mismatch")
        for version in continuity.plan_versions.values():
            expected_lineage = tuple(
                (atom_id, graph.atoms[atom_id].source_id)
                for atom_id in version.atom_ids
            )
            observed_lineage = tuple(
                (item.atom_id, item.source_id) for item in version.atom_lineage
            )
            expected_sources = tuple(
                sorted({source_id for _, source_id in expected_lineage})
            )
            if (
                expected_lineage != observed_lineage
                or expected_sources != version.source_ids
            ):
                raise PrivacyExportError("plan-version source lineage mismatch")
            if (
                version.supersedes_plan_version_id is not None
                and version.supersedes_plan_version_id
                not in continuity.plan_versions
            ):
                raise PrivacyExportError("plan version supersedes a missing version")
            if (
                version.promoted_from_branch_id is not None
                and version.promoted_from_branch_id not in continuity.branches
            ):
                raise PrivacyExportError("plan version references missing branch")
        expected_current_branches = {
            branch.branch_id
            for branch in continuity.branches.values()
            if branch.access == BranchAccess.ACCEPTED_PATH
        }
        accepted_version_ids = {
            version.plan_version_id
            for version in continuity.plan_versions.values()
            if version.status == PlanVersionStatus.ACCEPTED
        }
        if (
            set(continuity.current_plan_ids) != expected_current_branches
            or set(continuity.current_plan_ids.values()) != accepted_version_ids
        ):
            raise PrivacyExportError("current-plan index is incomplete")
        for branch_id, plan_id in continuity.current_plan_ids.items():
            version = continuity.plan_versions.get(plan_id)
            if (
                branch_id not in continuity.branches
                or version is None
                or version.branch_id != branch_id
                or version.status != PlanVersionStatus.ACCEPTED
            ):
                raise PrivacyExportError("invalid current-plan pointer")

    def _public_atom(
        self, graph: GraphSnapshot, atom_id: str
    ) -> PublicAtomRecord:
        atom = graph.atoms[atom_id]
        return PublicAtomRecord(
            atom_ref=self._ref("atom", atom.atom_id),
            source_ref=self._ref("source", atom.source_id),
            kind=atom.kind.value,
            state=atom.state.value,
            requires_human_confirmation=atom.requires_human_confirmation,
            extraction_method=atom.extraction_method,
            semantic_confidence=atom.semantic_confidence,
        )

    def _public_branch(self, branch: CognitiveBranch) -> PublicBranchRecord:
        return PublicBranchRecord(
            branch_ref=self._ref("branch", branch.branch_id),
            parent_branch_ref=(
                self._ref("branch", branch.parent_branch_id)
                if branch.parent_branch_id is not None
                else None
            ),
            anchor_atom_ref=(
                self._ref("atom", branch.anchor_atom_id)
                if branch.anchor_atom_id is not None
                else None
            ),
            base_plan_ref=self._ref("plan", branch.base_plan_version_id),
            inherited_atom_refs=tuple(
                self._ref("atom", atom_id) for atom_id in branch.inherited_atom_ids
            ),
            inherited_source_refs=tuple(
                self._ref("source", source_id)
                for source_id in branch.inherited_source_ids
            ),
            proposal_atom_refs=tuple(
                self._ref("atom", proposal.atom_id)
                for proposal in branch.proposals
            ),
            access=branch.access.value,
            status=branch.status.value,
        )

    def _public_plan(self, version: IntentPlanVersion) -> PublicPlanVersionRecord:
        return PublicPlanVersionRecord(
            plan_ref=self._ref("plan", version.plan_version_id),
            branch_ref=self._ref("branch", version.branch_id),
            revision=version.revision,
            atom_refs=tuple(self._ref("atom", item) for item in version.atom_ids),
            source_refs=tuple(
                self._ref("source", item) for item in version.source_ids
            ),
            supersedes_plan_ref=(
                self._ref("plan", version.supersedes_plan_version_id)
                if version.supersedes_plan_version_id is not None
                else None
            ),
            promoted_from_branch_ref=(
                self._ref("branch", version.promoted_from_branch_id)
                if version.promoted_from_branch_id is not None
                else None
            ),
            status=version.status.value,
        )

    def _ref(self, kind: str, local_id: str) -> str:
        encoded = json.dumps(
            {"kind": kind, "local_id": local_id},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hmac.new(
            bytes.fromhex(self.export_scope_key), encoded, hashlib.sha256
        ).hexdigest()
        return "public_%s_%s" % (kind, digest[:32])
