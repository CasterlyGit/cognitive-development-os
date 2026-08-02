from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Set, Tuple

from .compiler import CompileRequest, CompiledProposal, PRCompiler, RiskLevel
from .graph import EdgeKind, GraphSnapshot, IntentEdge
from .intents import ConfidenceBand, IntentAtom, SemanticConfidence
from .store import AppendOnlyEventStore


class DecisionLoopError(RuntimeError):
    """Raised when the local MVP loop cannot advance safely."""


class RelationshipDecision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True)
class ProjectScope:
    project_id: str
    label: str
    owned_paths: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "label": self.label,
            "owned_paths": list(self.owned_paths),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ProjectScope":
        return cls(
            project_id=value["project_id"],
            label=value["label"],
            owned_paths=tuple(value["owned_paths"]),
        )


@dataclass(frozen=True)
class ScopedIntent:
    project_id: str
    atom: IntentAtom

    def to_dict(self) -> Dict[str, Any]:
        return {"project_id": self.project_id, "atom": self.atom.to_dict()}

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ScopedIntent":
        return cls(
            project_id=value["project_id"], atom=IntentAtom.from_dict(value["atom"])
        )


@dataclass(frozen=True)
class RelationshipEvidence:
    source_id: str
    rationale: str

    def to_dict(self) -> Dict[str, str]:
        return {"source_id": self.source_id, "rationale": self.rationale}

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "RelationshipEvidence":
        return cls(source_id=value["source_id"], rationale=value["rationale"])


@dataclass(frozen=True)
class RelationshipProposal:
    proposal_id: str
    kind: EdgeKind
    source_atom_id: str
    target_atom_id: str
    evidence: Tuple[RelationshipEvidence, ...]
    confidence: SemanticConfidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "kind": self.kind.value,
            "source_atom_id": self.source_atom_id,
            "target_atom_id": self.target_atom_id,
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence.to_dict(),
        }


@dataclass(frozen=True)
class RouteSimulation:
    selected_route: str
    paver_lookup: str
    explanation: str
    scoped_project_ids: Tuple[str, ...]
    owned_paths: Tuple[str, ...]
    permission_class: str
    test_double: bool = True
    external_effects: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_route": self.selected_route,
            "paver_lookup": self.paver_lookup,
            "explanation": self.explanation,
            "scoped_project_ids": list(self.scoped_project_ids),
            "owned_paths": list(self.owned_paths),
            "permission_class": self.permission_class,
            "test_double": self.test_double,
            "external_effects": self.external_effects,
        }


@dataclass(frozen=True)
class VerificationEvidence:
    evidence_id: str
    description: str
    passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "description": self.description,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "VerificationEvidence":
        return cls(
            evidence_id=value["evidence_id"],
            description=value["description"],
            passed=value["passed"],
        )


@dataclass(frozen=True)
class ProjectDecisionManifest:
    schema_version: str
    loop_id: str
    projects: Tuple[ProjectScope, ...]
    intents: Tuple[ScopedIntent, ...]
    local_dependencies: Tuple[Tuple[str, str], ...]
    proposal_kind: EdgeKind
    proposal_source_atom_id: str
    proposal_target_atom_id: str
    proposal_evidence: Tuple[RelationshipEvidence, ...]
    proposal_confidence: SemanticConfidence
    compile_request: CompileRequest
    paver_capability_match: bool
    evidence: Tuple[VerificationEvidence, ...]

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ProjectDecisionManifest":
        compile_value = value["compile"]
        proposal = value["relationship_proposal"]
        route = value["route_simulation"]
        return cls(
            schema_version=value["schema_version"],
            loop_id=value["loop_id"],
            projects=tuple(ProjectScope.from_dict(item) for item in value["projects"]),
            intents=tuple(ScopedIntent.from_dict(item) for item in value["intents"]),
            local_dependencies=tuple(tuple(item) for item in value.get("local_dependencies", [])),
            proposal_kind=EdgeKind(proposal["kind"]),
            proposal_source_atom_id=proposal["source_atom_id"],
            proposal_target_atom_id=proposal["target_atom_id"],
            proposal_evidence=tuple(
                RelationshipEvidence.from_dict(item) for item in proposal["evidence"]
            ),
            proposal_confidence=SemanticConfidence.from_dict(proposal["confidence"]),
            compile_request=CompileRequest(
                title=compile_value["title"],
                outcome=compile_value["outcome"],
                target_atom_ids=tuple(compile_value["target_atom_ids"]),
                owned_paths=tuple(compile_value["owned_paths"]),
                acceptance_criteria=tuple(compile_value["acceptance_criteria"]),
                verification_steps=tuple(compile_value["verification_steps"]),
                explicit_exclusions=tuple(compile_value["explicit_exclusions"]),
                risk=RiskLevel(compile_value["risk"]),
                max_atoms=int(compile_value.get("max_atoms", 8)),
            ),
            paver_capability_match=route["paver_capability_match"],
            evidence=tuple(VerificationEvidence.from_dict(item) for item in value["evidence"]),
        )

    def normalized_value(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "loop_id": self.loop_id,
            "projects": [item.to_dict() for item in self.projects],
            "intents": [item.to_dict() for item in self.intents],
            "local_dependencies": [list(item) for item in self.local_dependencies],
            "relationship_proposal": {
                "kind": self.proposal_kind.value,
                "source_atom_id": self.proposal_source_atom_id,
                "target_atom_id": self.proposal_target_atom_id,
                "evidence": [item.to_dict() for item in self.proposal_evidence],
                "confidence": self.proposal_confidence.to_dict(),
            },
            "compile": {
                "title": self.compile_request.title,
                "outcome": self.compile_request.outcome,
                "target_atom_ids": list(self.compile_request.target_atom_ids),
                "owned_paths": list(self.compile_request.owned_paths),
                "acceptance_criteria": list(self.compile_request.acceptance_criteria),
                "verification_steps": list(self.compile_request.verification_steps),
                "explicit_exclusions": list(self.compile_request.explicit_exclusions),
                "risk": self.compile_request.risk.value,
                "max_atoms": self.compile_request.max_atoms,
            },
            "route_simulation": {
                "paver_capability_match": self.paver_capability_match
            },
            "evidence": [item.to_dict() for item in self.evidence],
        }


class ProjectDecisionLoop:
    """Local, event-sourced two-project decision loop with simulated routing."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, store: AppendOnlyEventStore) -> None:
        self.store = store

    def preview(self, manifest: ProjectDecisionManifest) -> Dict[str, Any]:
        """Build the safe pre-decision view without writing local state."""
        proposal = self._validate(manifest)
        intents = {item.atom.atom_id: item for item in manifest.intents}
        source = intents[proposal.source_atom_id]
        target = intents[proposal.target_atom_id]
        by_project = []
        for project in manifest.projects:
            project_intents = [
                item.atom.to_dict()
                for item in manifest.intents
                if item.project_id == project.project_id
            ]
            by_project.append(dict(project.to_dict(), intents=project_intents))
        return {
            "schema_version": self.SCHEMA_VERSION,
            "mvp": "Project Decision Loop",
            "loop_id": manifest.loop_id,
            "project_scopes": by_project,
            "relationship_proposal": proposal.to_dict(),
            "notice": {
                "source_project_id": source.project_id,
                "source_statement": source.atom.statement,
                "target_project_id": target.project_id,
                "target_statement": target.atom.statement,
                "plain_language": (
                    "%s needs an outcome from %s before its next move is coherent."
                    % (source.project_id.title(), target.project_id.title())
                ),
            },
            "decision_required": (
                "Approve or reject this relationship. Confidence explains the "
                "proposal but cannot decide for you."
            ),
            "if_approved": (
                "Create one dependency-closed, P1 draft-only plan and simulate "
                "the bounded route locally."
            ),
            "will_not_happen": (
                "No code runs, no service is contacted, and no external permission is granted."
            ),
            "external_effects": False,
        }

    def run(
        self,
        manifest: ProjectDecisionManifest,
        decision: RelationshipDecision,
        *,
        human_actor: str,
    ) -> Dict[str, Any]:
        proposal = self._validate(manifest)
        if not human_actor.strip():
            raise DecisionLoopError("an explicit human actor is required")
        stream_id = "mvp:%s" % manifest.loop_id
        manifest_digest = self._digest(manifest.normalized_value())
        self._append_once(
            stream_id,
            "mvp.initialized",
            {
                "manifest_digest": manifest_digest,
                "manifest": manifest.normalized_value(),
                "proposal": proposal.to_dict(),
            },
        )
        self._append_decision_once(stream_id, proposal, decision, human_actor)

        proposal_status = "accepted" if decision == RelationshipDecision.ACCEPT else "rejected"
        if decision == RelationshipDecision.REJECT:
            evidence = {
                "requested_outcome": manifest.compile_request.outcome,
                "observed_result": "blocked_before_plan",
                "approval_state": "relationship_rejected_by_human",
                "evidence": [],
                "blocker": "The cross-project relationship was explicitly rejected.",
                "next_decision": "Revise the proposal evidence or keep the projects independent.",
            }
            self._append_once(stream_id, "mvp.verification_recorded", evidence)
            return self._report(stream_id, manifest, proposal, proposal_status, None, None, evidence)

        compiled = self._compile(manifest, proposal)
        route = self._simulate_route(manifest, compiled)
        self._append_once(stream_id, "mvp.route_simulated", route.to_dict())
        passed = bool(manifest.evidence) and all(item.passed for item in manifest.evidence)
        evidence = {
            "requested_outcome": manifest.compile_request.outcome,
            "observed_result": "verified_in_test_double" if passed else "blocked_by_evidence",
            "approval_state": "relationship_accepted_by_human",
            "evidence": [item.to_dict() for item in manifest.evidence],
            "blocker": None if passed else "One or more required observations failed or were absent.",
            "next_decision": (
                "Review the draft plan; execution still requires separate permission."
                if passed
                else "Correct the failed observation before reconsidering the route."
            ),
        }
        self._append_once(stream_id, "mvp.verification_recorded", evidence)
        return self._report(
            stream_id, manifest, proposal, proposal_status, compiled, route, evidence
        )

    def _validate(self, manifest: ProjectDecisionManifest) -> RelationshipProposal:
        if manifest.schema_version != self.SCHEMA_VERSION:
            raise DecisionLoopError("unsupported MVP manifest schema")
        if not manifest.loop_id.strip() or len(manifest.projects) != 2:
            raise DecisionLoopError("exactly two explicitly declared project scopes are required")
        project_ids = tuple(item.project_id for item in manifest.projects)
        if len(set(project_ids)) != 2 or any(not item.strip() for item in project_ids):
            raise DecisionLoopError("project identities must be unique and non-empty")
        if any(not project.owned_paths for project in manifest.projects):
            raise DecisionLoopError("each project scope requires explicit owned paths")
        for project in manifest.projects:
            for path in project.owned_paths:
                parsed = PurePosixPath(path)
                if (
                    not path.strip()
                    or parsed.is_absolute()
                    or ".." in parsed.parts
                    or "\\" in path
                    or any(character in path for character in "*?[]")
                ):
                    raise DecisionLoopError("project scope contains an unsafe path")
        intents = {item.atom.atom_id: item for item in manifest.intents}
        if len(intents) != len(manifest.intents) or not intents:
            raise DecisionLoopError("intent identities must be unique and non-empty")
        if any(item.project_id not in project_ids for item in manifest.intents):
            raise DecisionLoopError("intent escaped the explicitly selected projects")
        for source_id, target_id in manifest.local_dependencies:
            source_intent = intents.get(source_id)
            target_intent = intents.get(target_id)
            if (
                source_intent is None
                or target_intent is None
                or source_id == target_id
                or source_intent.project_id != target_intent.project_id
            ):
                raise DecisionLoopError(
                    "local dependencies must connect distinct known intents in one project"
                )
        source = intents.get(manifest.proposal_source_atom_id)
        target = intents.get(manifest.proposal_target_atom_id)
        if source is None or target is None or source.project_id == target.project_id:
            raise DecisionLoopError("the proposal must connect known intents in different projects")
        expected_sources = {source.atom.source_id, target.atom.source_id}
        evidence_sources = {item.source_id for item in manifest.proposal_evidence}
        if not manifest.proposal_evidence or evidence_sources != expected_sources:
            raise DecisionLoopError("proposal evidence must cite both exact endpoint sources")
        if any(not item.rationale.strip() for item in manifest.proposal_evidence):
            raise DecisionLoopError("proposal evidence rationale must be non-empty")
        if manifest.proposal_confidence.band == ConfidenceBand.UNASSESSED:
            raise DecisionLoopError("relationship confidence must be assessed")
        if not isinstance(manifest.paver_capability_match, bool):
            raise DecisionLoopError("Paver test-double match must be boolean")
        evidence_ids = tuple(item.evidence_id for item in manifest.evidence)
        required_evidence = {
            "dependency_closure",
            "scope_preserved",
            "permission_preserved",
        }
        if set(evidence_ids) != required_evidence or len(evidence_ids) != 3:
            raise DecisionLoopError("the three exact MVP evidence records are required")
        if any(
            not item.evidence_id.strip()
            or not item.description.strip()
            or not isinstance(item.passed, bool)
            for item in manifest.evidence
        ):
            raise DecisionLoopError("MVP evidence records are invalid")
        allowed_paths = {path for project in manifest.projects for path in project.owned_paths}
        if not set(manifest.compile_request.owned_paths).issubset(allowed_paths):
            raise DecisionLoopError("compile paths escaped the opted-in project scopes")
        proposal_value = {
            "loop_id": manifest.loop_id,
            "kind": manifest.proposal_kind.value,
            "source_atom_id": source.atom.atom_id,
            "target_atom_id": target.atom.atom_id,
            "evidence": [item.to_dict() for item in manifest.proposal_evidence],
            "confidence": manifest.proposal_confidence.to_dict(),
        }
        return RelationshipProposal(
            proposal_id="rel_%s" % self._digest(proposal_value)[:20],
            kind=manifest.proposal_kind,
            source_atom_id=source.atom.atom_id,
            target_atom_id=target.atom.atom_id,
            evidence=manifest.proposal_evidence,
            confidence=manifest.proposal_confidence,
        )

    def _compile(
        self, manifest: ProjectDecisionManifest, proposal: RelationshipProposal
    ) -> CompiledProposal:
        atoms = {item.atom.atom_id: item.atom for item in manifest.intents}
        edges = [
            IntentEdge(source_id, target_id, EdgeKind.DEPENDS_ON)
            for source_id, target_id in manifest.local_dependencies
        ]
        edges.append(
            IntentEdge(
                proposal.source_atom_id, proposal.target_atom_id, proposal.kind
            )
        )
        snapshot = GraphSnapshot(
            graph_id="mvp_graph:%s" % manifest.loop_id,
            atoms=atoms,
            edges=tuple(edges),
            clusters={},
        )
        snapshot.topological_order()
        return PRCompiler().compile(snapshot, manifest.compile_request)

    def _simulate_route(
        self, manifest: ProjectDecisionManifest, compiled: CompiledProposal
    ) -> RouteSimulation:
        declared_projects = tuple(sorted(item.project_id for item in manifest.projects))
        declared_paths = {path for item in manifest.projects for path in item.owned_paths}
        brief_paths = set(compiled.brief.owned_paths)
        if not brief_paths.issubset(declared_paths):
            raise DecisionLoopError("simulated route attempted to expand owned scope")
        if compiled.brief.permission_boundary.find("P1 draft only") < 0:
            raise DecisionLoopError("simulated route attempted to expand permission")
        if manifest.paver_capability_match:
            selected = "paver_test_double"
            lookup = "matched_synthetic_capability"
            explanation = "A synthetic verified capability matched; no command was invoked."
        else:
            selected = "codex_packet_test_double"
            lookup = "no_match"
            explanation = "No synthetic capability matched; a bounded Codex packet was inspected but not dispatched."
        return RouteSimulation(
            selected_route=selected,
            paver_lookup=lookup,
            explanation=explanation,
            scoped_project_ids=declared_projects,
            owned_paths=compiled.brief.owned_paths,
            permission_class=compiled.plan.permission_class.value,
        )

    def _append_decision_once(
        self,
        stream_id: str,
        proposal: RelationshipProposal,
        decision: RelationshipDecision,
        actor: str,
    ) -> None:
        payload = {
            "proposal_id": proposal.proposal_id,
            "decision": decision.value,
            "actor": actor.strip(),
            "authority": "human",
        }
        existing = [
            event
            for event in self.store.events_for(stream_id)
            if event.event_type == "mvp.relationship_decided"
        ]
        if existing:
            if len(existing) == 1 and existing[0].payload == payload:
                return
            raise DecisionLoopError("relationship already has a different exact decision")
        self.store.append(stream_id, "mvp.relationship_decided", payload)

    def _append_once(self, stream_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        existing = [
            event for event in self.store.events_for(stream_id) if event.event_type == event_type
        ]
        if existing:
            if len(existing) == 1 and existing[0].payload == payload:
                return
            raise DecisionLoopError("%s history is stale or divergent" % event_type)
        self.store.append(stream_id, event_type, payload)

    def _report(
        self,
        stream_id: str,
        manifest: ProjectDecisionManifest,
        proposal: RelationshipProposal,
        proposal_status: str,
        compiled: Optional[CompiledProposal],
        route: Optional[RouteSimulation],
        verification: Dict[str, Any],
    ) -> Dict[str, Any]:
        selected = set(compiled.plan.selected_atom_ids) if compiled else set()
        all_ids = {item.atom.atom_id for item in manifest.intents}
        timeline = []
        labels = {
            "mvp.initialized": "Two project scopes and a source-backed proposal were recorded.",
            "mvp.relationship_decided": "A human made the exact relationship decision.",
            "mvp.route_simulated": "The bounded route was evaluated by test doubles.",
            "mvp.verification_recorded": "Observed evidence and the next decision were recorded.",
        }
        for event in self.store.events_for(stream_id):
            if event.event_type not in labels:
                raise DecisionLoopError("unsupported MVP history event %s" % event.event_type)
            timeline.append(
                {
                    "sequence": event.sequence,
                    "event": event.event_type,
                    "summary": labels[event.event_type],
                }
            )
        uncertainty = [
            "Confidence is interpretation metadata only: %s (%d/1000)."
            % (proposal.confidence.band.value, proposal.confidence.score_millis)
        ]
        if proposal.kind == EdgeKind.CONFLICTS_WITH:
            uncertainty.append("The proposed relationship is an explicit conflict.")
        return {
            "schema_version": self.SCHEMA_VERSION,
            "mvp": "Project Decision Loop",
            "loop_id": manifest.loop_id,
            "project_scopes": [item.to_dict() for item in manifest.projects],
            "relationship_proposal": dict(proposal.to_dict(), status=proposal_status),
            "included_intent": sorted(selected),
            "excluded_intent": sorted(all_ids - selected),
            "conflicts_or_uncertainty": uncertainty,
            "plan": compiled.plan.to_dict() if compiled else None,
            "bounded_route_simulation": route.to_dict() if route else None,
            "verification": verification,
            "timeline": timeline,
            "external_effects": False,
            "limits": [
                "Local JSONL state only; no unrelated storage is scanned.",
                "Paver and Codex behavior is simulated by in-process test doubles.",
                "Relationship approval does not authorize execution or any external effect.",
            ],
        }

    @staticmethod
    def _digest(value: Dict[str, Any]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
