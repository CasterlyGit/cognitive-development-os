from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Tuple

from .compiler import (
    CompileRequest,
    CompiledProposal,
    CompilerError,
    PRCompiler,
    PermissionClass,
)
from .continuity import (
    BranchAccess,
    BranchStatus,
    ContinuitySnapshot,
    IntentPlanVersion,
    PlanVersionStatus,
)
from .graph import EdgeKind, GraphSnapshot, IntentCluster
from .intents import AtomState
from .pipeline import DecisionChoice, DecisionPacket, PrimaryDecision


class AcceptedPlanPacketError(RuntimeError):
    """Raised when an accepted plan cannot be bound to a safe draft packet."""


@dataclass(frozen=True)
class AcceptedPlanCompileRequest:
    branch_id: str
    expected_plan_version_id: str
    compile_request: CompileRequest


@dataclass(frozen=True)
class AcceptedPlanBinding:
    schema_version: str
    binding_id: str
    continuity_id: str
    branch_id: str
    plan_version_id: str
    plan_revision: int
    plan_version_sha256: str
    graph_scope_sha256: str
    compiled_plan_id: str
    accepted_atom_ids: Tuple[str, ...]
    accepted_source_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "binding_id": self.binding_id,
            "continuity_id": self.continuity_id,
            "branch_id": self.branch_id,
            "plan_version_id": self.plan_version_id,
            "plan_revision": self.plan_revision,
            "plan_version_sha256": self.plan_version_sha256,
            "graph_scope_sha256": self.graph_scope_sha256,
            "compiled_plan_id": self.compiled_plan_id,
            "accepted_atom_ids": list(self.accepted_atom_ids),
            "accepted_source_ids": list(self.accepted_source_ids),
        }


@dataclass(frozen=True)
class AcceptedPlanPacket:
    schema_version: str
    binding: AcceptedPlanBinding
    proposal: CompiledProposal
    decision_packet: DecisionPacket
    external_effects: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "binding": self.binding.to_dict(),
            "proposal": self.proposal.to_dict(),
            "decision_packet": self.decision_packet.to_dict(),
            "external_effects": self.external_effects,
        }


class AcceptedPlanPacketCompiler:
    """Pure bridge from one current accepted plan to a draft decision packet."""

    SCHEMA_VERSION = "1.0"

    def compile(
        self,
        graph: GraphSnapshot,
        continuity: ContinuitySnapshot,
        request: AcceptedPlanCompileRequest,
    ) -> AcceptedPlanPacket:
        version = self._current_accepted_version(continuity, request)
        self._validate_lineage(graph, version)
        scoped_graph = self._accepted_scope(graph, version)
        targets = request.compile_request.target_atom_ids
        if not targets or not set(targets).issubset(version.atom_ids):
            raise AcceptedPlanPacketError(
                "compiler targets must be inside the accepted plan version"
            )
        try:
            proposal = PRCompiler().compile(scoped_graph, request.compile_request)
        except CompilerError as exc:
            raise AcceptedPlanPacketError(
                "accepted plan compilation failed: %s" % exc
            ) from exc
        if (
            proposal.plan.permission_class != PermissionClass.DRAFT_ONLY
            or not proposal.plan.dry_run
            or not proposal.plan.requires_human_approval_for_execution
        ):
            raise AcceptedPlanPacketError(
                "compiled proposal exceeds the draft-only permission boundary"
            )
        if not set(proposal.plan.selected_atom_ids).issubset(version.atom_ids):
            raise AcceptedPlanPacketError("compiled graph cut escaped accepted intent")
        if not set(proposal.plan.source_ids).issubset(version.source_ids):
            raise AcceptedPlanPacketError(
                "compiled source lineage escaped accepted intent"
            )

        version_digest = self._digest(version.to_dict())
        graph_digest = self._digest(self._graph_value(scoped_graph))
        binding_identity = {
            "continuity_id": continuity.continuity_id,
            "branch_id": request.branch_id,
            "plan_version_id": version.plan_version_id,
            "plan_revision": version.revision,
            "plan_version_sha256": version_digest,
            "graph_scope_sha256": graph_digest,
            "compiled_plan_id": proposal.plan.plan_id,
        }
        binding = AcceptedPlanBinding(
            schema_version=self.SCHEMA_VERSION,
            binding_id="accepted_binding_%s" % self._digest(binding_identity)[:20],
            continuity_id=continuity.continuity_id,
            branch_id=request.branch_id,
            plan_version_id=version.plan_version_id,
            plan_revision=version.revision,
            plan_version_sha256=version_digest,
            graph_scope_sha256=graph_digest,
            compiled_plan_id=proposal.plan.plan_id,
            accepted_atom_ids=version.atom_ids,
            accepted_source_ids=version.source_ids,
        )
        decision = self._decision_packet(binding, proposal)
        return AcceptedPlanPacket(
            schema_version=self.SCHEMA_VERSION,
            binding=binding,
            proposal=proposal,
            decision_packet=decision,
            external_effects=False,
        )

    @staticmethod
    def _current_accepted_version(
        continuity: ContinuitySnapshot, request: AcceptedPlanCompileRequest
    ) -> IntentPlanVersion:
        if (
            not isinstance(request.branch_id, str)
            or not request.branch_id.strip()
            or request.branch_id != request.branch_id.strip()
            or not isinstance(request.expected_plan_version_id, str)
            or not request.expected_plan_version_id.strip()
            or request.expected_plan_version_id
            != request.expected_plan_version_id.strip()
            or not isinstance(request.compile_request, CompileRequest)
        ):
            raise AcceptedPlanPacketError("accepted-plan request is invalid")
        branch = continuity.branches.get(request.branch_id)
        if branch is None:
            raise AcceptedPlanPacketError("accepted branch is missing")
        if (
            branch.parent_branch_id is not None
            or branch.access != BranchAccess.ACCEPTED_PATH
            or branch.status != BranchStatus.ACTIVE
        ):
            raise AcceptedPlanPacketError(
                "only the active accepted-path branch can compile"
            )
        current_id = continuity.current_plan_ids.get(request.branch_id)
        if current_id != request.expected_plan_version_id:
            raise AcceptedPlanPacketError("expected plan version is stale")
        version = continuity.plan_versions.get(current_id)
        if (
            version is None
            or version.plan_version_id != current_id
            or version.branch_id != request.branch_id
            or version.status != PlanVersionStatus.ACCEPTED
            or isinstance(version.revision, bool)
            or not isinstance(version.revision, int)
            or version.revision < 1
            or not version.atom_ids
            or len(set(version.atom_ids)) != len(version.atom_ids)
        ):
            raise AcceptedPlanPacketError("current plan version is not accepted")
        return version

    @staticmethod
    def _validate_lineage(graph: GraphSnapshot, version: IntentPlanVersion) -> None:
        if tuple(item.atom_id for item in version.atom_lineage) != version.atom_ids:
            raise AcceptedPlanPacketError("plan atom lineage is not exact")
        expected_sources = tuple(
            sorted({item.source_id for item in version.atom_lineage})
        )
        if expected_sources != version.source_ids:
            raise AcceptedPlanPacketError("plan source lineage is not exact")
        for lineage in version.atom_lineage:
            atom = graph.atoms.get(lineage.atom_id)
            if atom is None:
                raise AcceptedPlanPacketError("accepted atom is missing from the graph")
            if atom.source_id != lineage.source_id:
                raise AcceptedPlanPacketError("accepted atom source lineage changed")
            if atom.requires_human_confirmation and atom.state != AtomState.CONFIRMED:
                raise AcceptedPlanPacketError(
                    "accepted actionable intent is no longer confirmed"
                )

    @staticmethod
    def _accepted_scope(
        graph: GraphSnapshot, version: IntentPlanVersion
    ) -> GraphSnapshot:
        accepted = set(version.atom_ids)
        scoped_edges = []
        for edge in graph.edges:
            source_inside = edge.source_atom_id in accepted
            target_inside = edge.target_atom_id in accepted
            if edge.kind == EdgeKind.DEPENDS_ON and source_inside and not target_inside:
                raise AcceptedPlanPacketError(
                    "accepted dependency escapes the plan version"
                )
            if edge.kind == EdgeKind.CONFLICTS_WITH and source_inside != target_inside:
                raise AcceptedPlanPacketError(
                    "accepted conflict crosses the plan-version boundary"
                )
            if source_inside and target_inside:
                scoped_edges.append(edge)

        scoped_clusters: Dict[str, IntentCluster] = {}
        for cluster_id, cluster in graph.clusters.items():
            members = set(cluster.member_atom_ids)
            if members.intersection(accepted) and not members.issubset(accepted):
                raise AcceptedPlanPacketError(
                    "relevant cluster crosses the plan-version boundary"
                )
            if members and members.issubset(accepted):
                scoped_clusters[cluster_id] = cluster

        scoped = GraphSnapshot(
            graph_id=graph.graph_id,
            atoms={atom_id: graph.atoms[atom_id] for atom_id in version.atom_ids},
            edges=tuple(scoped_edges),
            clusters=scoped_clusters,
        )
        scoped.topological_order()
        return scoped

    def _decision_packet(
        self, binding: AcceptedPlanBinding, proposal: CompiledProposal
    ) -> DecisionPacket:
        return DecisionPacket(
            schema_version=self.SCHEMA_VERSION,
            status="accepted_plan_dry_run_complete",
            outcome=(
                "The current accepted plan version is bound to one reviewable "
                "draft PR plan and execution brief."
            ),
            evidence=(
                "Accepted plan %s revision %d was selected by exact identifier."
                % (binding.plan_version_id, binding.plan_revision),
                "%d accepted atom/source lineage records match the graph scope."
                % len(binding.accepted_atom_ids),
                "Scoped graph digest %s binds dependencies, conflicts, and clusters."
                % binding.graph_scope_sha256,
                "Compiled plan %s remains P1 draft-only." % proposal.plan.plan_id,
                "No event write or external effect occurred.",
            ),
            material_risks=(
                "This packet validates a local snapshot, not a live executor outcome.",
                "Any later graph or accepted-plan change requires a new binding.",
            ),
            primary_decision=PrimaryDecision(
                question=(
                    "Is this accepted-plan-bound draft coherent enough to retain "
                    "for review?"
                ),
                choices=(
                    DecisionChoice(
                        "accept_draft",
                        "Accept draft",
                        "Retain the packet without executing it.",
                    ),
                    DecisionChoice(
                        "revise",
                        "Revise",
                        "Change accepted intent or compiler scope and bind again.",
                    ),
                    DecisionChoice(
                        "reject",
                        "Reject",
                        "Do not retain or execute this draft.",
                    ),
                ),
                recommended_key="accept_draft",
            ),
            next_step=(
                "Review the bound plan and brief; execution requires separate "
                "exact authorization."
            ),
            external_effects=False,
        )

    @staticmethod
    def _graph_value(graph: GraphSnapshot) -> Dict[str, Any]:
        return {
            "graph_id": graph.graph_id,
            "atoms": [
                graph.atoms[atom_id].to_dict() for atom_id in sorted(graph.atoms)
            ],
            "edges": [
                edge.to_dict()
                for edge in sorted(
                    graph.edges,
                    key=lambda item: (
                        item.kind.value,
                        item.source_atom_id,
                        item.target_atom_id,
                    ),
                )
            ],
            "clusters": [
                graph.clusters[cluster_id].to_dict()
                for cluster_id in sorted(graph.clusters)
            ],
        }

    @staticmethod
    def _digest(value: Dict[str, Any]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()
