from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Set, Tuple

from .graph import EdgeKind, GraphSnapshot
from .intents import AtomKind, AtomState


class CompilerError(RuntimeError):
    pass


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionClass(str, Enum):
    DRAFT_ONLY = "P1_draft_only"


@dataclass(frozen=True)
class RoutePlan:
    architect_model: str = "sol"
    architect_effort: str = "medium"
    builder_model: str = "terra"
    builder_effort: str = "high"
    status_model: str = "luna"
    status_effort: str = "low"

    def to_dict(self) -> Dict[str, str]:
        return {
            "architect_model": self.architect_model,
            "architect_effort": self.architect_effort,
            "builder_model": self.builder_model,
            "builder_effort": self.builder_effort,
            "status_model": self.status_model,
            "status_effort": self.status_effort,
        }


@dataclass(frozen=True)
class CompileRequest:
    title: str
    outcome: str
    target_atom_ids: Tuple[str, ...]
    owned_paths: Tuple[str, ...]
    acceptance_criteria: Tuple[str, ...]
    verification_steps: Tuple[str, ...]
    explicit_exclusions: Tuple[str, ...]
    risk: RiskLevel
    max_atoms: int = 8


@dataclass(frozen=True)
class PullRequestPlan:
    schema_version: str
    plan_id: str
    graph_id: str
    title: str
    outcome: str
    selected_atom_ids: Tuple[str, ...]
    source_ids: Tuple[str, ...]
    dependency_map: Dict[str, Tuple[str, ...]]
    constraints: Tuple[str, ...]
    exclusions: Tuple[str, ...]
    acceptance_criteria: Tuple[str, ...]
    risk: RiskLevel
    permission_class: PermissionClass
    dry_run: bool
    requires_human_approval_for_execution: bool
    routes: RoutePlan

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "graph_id": self.graph_id,
            "title": self.title,
            "outcome": self.outcome,
            "selected_atom_ids": list(self.selected_atom_ids),
            "source_ids": list(self.source_ids),
            "dependency_map": {
                atom_id: list(dependencies)
                for atom_id, dependencies in sorted(self.dependency_map.items())
            },
            "constraints": list(self.constraints),
            "exclusions": list(self.exclusions),
            "acceptance_criteria": list(self.acceptance_criteria),
            "risk": self.risk.value,
            "permission_class": self.permission_class.value,
            "dry_run": self.dry_run,
            "requires_human_approval_for_execution": self.requires_human_approval_for_execution,
            "routes": self.routes.to_dict(),
        }


@dataclass(frozen=True)
class ExecutionBrief:
    schema_version: str
    brief_id: str
    plan_id: str
    executor: str
    reasoning_effort: str
    objective: str
    ordered_work: Tuple[str, ...]
    source_provenance: Tuple[str, ...]
    owned_paths: Tuple[str, ...]
    explicit_exclusions: Tuple[str, ...]
    acceptance_criteria: Tuple[str, ...]
    verification_steps: Tuple[str, ...]
    stop_conditions: Tuple[str, ...]
    permission_boundary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "brief_id": self.brief_id,
            "plan_id": self.plan_id,
            "executor": self.executor,
            "reasoning_effort": self.reasoning_effort,
            "objective": self.objective,
            "ordered_work": list(self.ordered_work),
            "source_provenance": list(self.source_provenance),
            "owned_paths": list(self.owned_paths),
            "explicit_exclusions": list(self.explicit_exclusions),
            "acceptance_criteria": list(self.acceptance_criteria),
            "verification_steps": list(self.verification_steps),
            "stop_conditions": list(self.stop_conditions),
            "permission_boundary": self.permission_boundary,
        }


@dataclass(frozen=True)
class CompiledProposal:
    plan: PullRequestPlan
    brief: ExecutionBrief

    def to_dict(self) -> Dict[str, Any]:
        return {"plan": self.plan.to_dict(), "brief": self.brief.to_dict()}


class PRCompiler:
    SCHEMA_VERSION = "1.0"

    def compile(
        self, snapshot: GraphSnapshot, request: CompileRequest
    ) -> CompiledProposal:
        self._validate_request(request)
        selected = self._dependency_closure(snapshot, request.target_atom_ids)
        if len(selected) > request.max_atoms:
            raise CompilerError(
                "graph cut has %d atoms, above max_atoms=%d"
                % (len(selected), request.max_atoms)
            )
        self._validate_selected_atoms(snapshot, selected)
        self._reject_internal_conflicts(snapshot, selected)
        ordered = tuple(
            atom_id
            for atom_id in snapshot.topological_order()
            if atom_id in selected
        )
        constraints = self._relevant_constraints(snapshot, selected)
        external_conflicts = self._external_conflict_exclusions(snapshot, selected)
        exclusions = tuple(
            dict.fromkeys(request.explicit_exclusions + external_conflicts)
        )
        source_ids = tuple(
            sorted({snapshot.atoms[atom_id].source_id for atom_id in selected})
        )
        dependency_map = {
            atom_id: tuple(
                dependency
                for dependency in snapshot.dependencies_of(atom_id)
                if dependency in selected
            )
            for atom_id in ordered
        }
        digest_input = {
            "graph_id": snapshot.graph_id,
            "title": request.title,
            "outcome": request.outcome,
            "selected_atom_ids": list(ordered),
            "owned_paths": list(request.owned_paths),
            "acceptance_criteria": list(request.acceptance_criteria),
            "verification_steps": list(request.verification_steps),
            "exclusions": list(exclusions),
            "risk": request.risk.value,
        }
        plan_id = "plan_%s" % self._digest(digest_input)
        routes = RoutePlan()
        plan = PullRequestPlan(
            schema_version=self.SCHEMA_VERSION,
            plan_id=plan_id,
            graph_id=snapshot.graph_id,
            title=request.title.strip(),
            outcome=request.outcome.strip(),
            selected_atom_ids=ordered,
            source_ids=source_ids,
            dependency_map=dependency_map,
            constraints=constraints,
            exclusions=exclusions,
            acceptance_criteria=request.acceptance_criteria,
            risk=request.risk,
            permission_class=PermissionClass.DRAFT_ONLY,
            dry_run=True,
            requires_human_approval_for_execution=True,
            routes=routes,
        )
        brief_id = "brief_%s" % self._digest(
            {"plan_id": plan_id, "verification_steps": request.verification_steps}
        )
        brief = ExecutionBrief(
            schema_version=self.SCHEMA_VERSION,
            brief_id=brief_id,
            plan_id=plan_id,
            executor=routes.builder_model,
            reasoning_effort=routes.builder_effort,
            objective=request.outcome.strip(),
            ordered_work=tuple(snapshot.atoms[atom_id].statement for atom_id in ordered),
            source_provenance=source_ids,
            owned_paths=request.owned_paths,
            explicit_exclusions=exclusions + constraints,
            acceptance_criteria=request.acceptance_criteria,
            verification_steps=request.verification_steps,
            stop_conditions=(
                "Stop before any network or external-system effect.",
                "Stop if work would escape owned_paths.",
                "Stop and report if a verification step fails.",
                "Stop if intent, dependency, or permission state is ambiguous.",
            ),
            permission_boundary=(
                "P1 draft only. This brief authorizes no push, PR creation, merge, "
                "deployment, message, deletion, purchase, or Krish mutation."
            ),
        )
        return CompiledProposal(plan=plan, brief=brief)

    def _dependency_closure(
        self, snapshot: GraphSnapshot, target_atom_ids: Iterable[str]
    ) -> Set[str]:
        selected: Set[str] = set()
        pending = list(target_atom_ids)
        while pending:
            atom_id = pending.pop()
            if atom_id not in snapshot.atoms:
                raise CompilerError("target references missing atom %s" % atom_id)
            if atom_id in selected:
                continue
            selected.add(atom_id)
            pending.extend(snapshot.dependencies_of(atom_id))
        return selected

    @staticmethod
    def _validate_selected_atoms(snapshot: GraphSnapshot, selected: Set[str]) -> None:
        for atom_id in sorted(selected):
            atom = snapshot.atoms[atom_id]
            if atom.kind != AtomKind.ACTIONABLE:
                raise CompilerError(
                    "graph cut includes non-actionable atom %s (%s)"
                    % (atom_id, atom.kind.value)
                )
            if atom.state != AtomState.CONFIRMED:
                raise CompilerError(
                    "graph cut includes unconfirmed atom %s (%s)"
                    % (atom_id, atom.state.value)
                )

    @staticmethod
    def _reject_internal_conflicts(
        snapshot: GraphSnapshot, selected: Set[str]
    ) -> None:
        for edge in snapshot.conflicts():
            if edge.source_atom_id in selected and edge.target_atom_id in selected:
                raise CompilerError(
                    "graph cut contains conflict between %s and %s"
                    % (edge.source_atom_id, edge.target_atom_id)
                )

    @staticmethod
    def _relevant_constraints(
        snapshot: GraphSnapshot, selected: Set[str]
    ) -> Tuple[str, ...]:
        cluster_ids = {
            cluster.cluster_id
            for cluster in snapshot.clusters.values()
            if selected.intersection(cluster.member_atom_ids)
        }
        constraint_ids: Set[str] = set()
        for cluster_id in cluster_ids:
            constraint_ids.update(snapshot.clusters[cluster_id].member_atom_ids)
        return tuple(
            snapshot.atoms[atom_id].statement
            for atom_id in sorted(constraint_ids)
            if snapshot.atoms[atom_id].kind == AtomKind.CONSTRAINT
        )

    @staticmethod
    def _external_conflict_exclusions(
        snapshot: GraphSnapshot, selected: Set[str]
    ) -> Tuple[str, ...]:
        exclusions: List[str] = []
        for edge in snapshot.conflicts():
            inside = None
            outside = None
            if edge.source_atom_id in selected and edge.target_atom_id not in selected:
                inside, outside = edge.source_atom_id, edge.target_atom_id
            elif edge.target_atom_id in selected and edge.source_atom_id not in selected:
                inside, outside = edge.target_atom_id, edge.source_atom_id
            if inside and outside:
                exclusions.append(
                    "Do not combine %s with conflicting intent: %s"
                    % (inside, snapshot.atoms[outside].statement)
                )
        return tuple(sorted(exclusions))

    @staticmethod
    def _validate_request(request: CompileRequest) -> None:
        required_text = (request.title, request.outcome)
        if any(not value.strip() for value in required_text):
            raise CompilerError("title and outcome must be non-empty")
        if not request.target_atom_ids:
            raise CompilerError("at least one target atom is required")
        if not request.owned_paths:
            raise CompilerError("owned_paths must be explicit")
        if not request.acceptance_criteria or not request.verification_steps:
            raise CompilerError("acceptance criteria and verification steps are required")
        if request.max_atoms < 1:
            raise CompilerError("max_atoms must be positive")
        for path in request.owned_paths:
            parsed = PurePosixPath(path)
            if (
                not path.strip()
                or parsed.is_absolute()
                or ".." in parsed.parts
                or "\\" in path
                or any(character in path for character in "*?[]")
            ):
                raise CompilerError("unsafe owned path %s" % path)
        for collection in (
            request.acceptance_criteria,
            request.verification_steps,
            request.explicit_exclusions,
        ):
            if any(not value.strip() for value in collection):
                raise CompilerError("request lists cannot contain blank values")

    @staticmethod
    def _digest(value: Dict[str, Any]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()[:16]
