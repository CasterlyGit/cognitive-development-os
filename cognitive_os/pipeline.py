from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from .compiler import CompileRequest, CompiledProposal, PRCompiler, RiskLevel
from .graph import EdgeKind, GraphSnapshot, IntentCluster, IntentGraph
from .intents import (
    AtomState,
    ConfirmationAuthority,
    ConfirmationRecord,
    IntentAtom,
    IntentExtractor,
    IntentLifecycle,
    IntentLifecycleError,
)
from .models import SourceKind, SourceRecord
from .store import AppendOnlyEventStore, IntentInbox


class DryRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceInput:
    source_id: str
    kind: SourceKind
    raw_text: str
    metadata: Dict[str, str]


@dataclass(frozen=True)
class RelationshipIndexes:
    source_index: int
    target_index: int


@dataclass(frozen=True)
class ClusterIndexes:
    cluster_id: str
    label: str
    member_indexes: Tuple[int, ...]


@dataclass(frozen=True)
class PlanRequestSpec:
    title: str
    outcome: str
    target_indexes: Tuple[int, ...]
    owned_paths: Tuple[str, ...]
    acceptance_criteria: Tuple[str, ...]
    verification_steps: Tuple[str, ...]
    explicit_exclusions: Tuple[str, ...]
    risk: RiskLevel
    max_atoms: int


@dataclass(frozen=True)
class DryRunManifest:
    run_id: str
    graph_id: str
    source: SourceInput
    confirmed_atom_indexes: Tuple[int, ...]
    confirmation: ConfirmationRecord
    dependencies: Tuple[RelationshipIndexes, ...]
    conflicts: Tuple[RelationshipIndexes, ...]
    clusters: Tuple[ClusterIndexes, ...]
    plan: PlanRequestSpec

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "DryRunManifest":
        try:
            source = value["source"]
            confirmation = value["confirmation"]
            plan = value["plan"]
            return cls(
                run_id=value["run_id"],
                graph_id=value["graph_id"],
                source=SourceInput(
                    source_id=source["source_id"],
                    kind=SourceKind(source["kind"]),
                    raw_text=source["raw_text"],
                    metadata=dict(source.get("metadata", {})),
                ),
                confirmed_atom_indexes=tuple(value.get("confirmed_atom_indexes", [])),
                confirmation=ConfirmationRecord(
                    actor_id=confirmation["actor_id"],
                    authority=ConfirmationAuthority(confirmation["authority"]),
                    channel=confirmation["channel"],
                ),
                dependencies=tuple(
                    RelationshipIndexes(int(pair[0]), int(pair[1]))
                    for pair in value.get("dependencies", [])
                ),
                conflicts=tuple(
                    RelationshipIndexes(int(pair[0]), int(pair[1]))
                    for pair in value.get("conflicts", [])
                ),
                clusters=tuple(
                    ClusterIndexes(
                        cluster_id=cluster["cluster_id"],
                        label=cluster["label"],
                        member_indexes=tuple(cluster["member_indexes"]),
                    )
                    for cluster in value.get("clusters", [])
                ),
                plan=PlanRequestSpec(
                    title=plan["title"],
                    outcome=plan["outcome"],
                    target_indexes=tuple(plan["target_indexes"]),
                    owned_paths=tuple(plan["owned_paths"]),
                    acceptance_criteria=tuple(plan["acceptance_criteria"]),
                    verification_steps=tuple(plan["verification_steps"]),
                    explicit_exclusions=tuple(plan.get("explicit_exclusions", [])),
                    risk=RiskLevel(plan["risk"]),
                    max_atoms=int(plan.get("max_atoms", 8)),
                ),
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise DryRunError("invalid dry-run manifest: %s" % exc) from exc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "graph_id": self.graph_id,
            "source": {
                "source_id": self.source.source_id,
                "kind": self.source.kind.value,
                "raw_text": self.source.raw_text,
                "metadata": self.source.metadata,
            },
            "confirmed_atom_indexes": list(self.confirmed_atom_indexes),
            "confirmation": self.confirmation.to_dict(),
            "dependencies": [
                [item.source_index, item.target_index] for item in self.dependencies
            ],
            "conflicts": [
                [item.source_index, item.target_index] for item in self.conflicts
            ],
            "clusters": [
                {
                    "cluster_id": item.cluster_id,
                    "label": item.label,
                    "member_indexes": list(item.member_indexes),
                }
                for item in self.clusters
            ],
            "plan": {
                "title": self.plan.title,
                "outcome": self.plan.outcome,
                "target_indexes": list(self.plan.target_indexes),
                "owned_paths": list(self.plan.owned_paths),
                "acceptance_criteria": list(self.plan.acceptance_criteria),
                "verification_steps": list(self.plan.verification_steps),
                "explicit_exclusions": list(self.plan.explicit_exclusions),
                "risk": self.plan.risk.value,
                "max_atoms": self.plan.max_atoms,
            },
        }


@dataclass(frozen=True)
class DecisionChoice:
    key: str
    label: str
    effect: str

    def to_dict(self) -> Dict[str, str]:
        return {"key": self.key, "label": self.label, "effect": self.effect}


@dataclass(frozen=True)
class PrimaryDecision:
    question: str
    choices: Tuple[DecisionChoice, ...]
    recommended_key: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "choices": [choice.to_dict() for choice in self.choices],
            "recommended_key": self.recommended_key,
        }


@dataclass(frozen=True)
class DecisionPacket:
    schema_version: str
    status: str
    outcome: str
    evidence: Tuple[str, ...]
    material_risks: Tuple[str, ...]
    primary_decision: PrimaryDecision
    next_step: str
    external_effects: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "outcome": self.outcome,
            "evidence": list(self.evidence),
            "material_risks": list(self.material_risks),
            "primary_decision": self.primary_decision.to_dict(),
            "next_step": self.next_step,
            "external_effects": self.external_effects,
        }


@dataclass(frozen=True)
class DryRunResult:
    run_id: str
    source_id: str
    content_sha256: str
    atoms: Tuple[IntentAtom, ...]
    proposal: Optional[CompiledProposal]
    decision_packet: DecisionPacket

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source_id": self.source_id,
            "content_sha256": self.content_sha256,
            "atoms": [atom.to_dict() for atom in self.atoms],
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "decision_packet": self.decision_packet.to_dict(),
        }


class DryRunControlPlane:
    SCHEMA_VERSION = "1.0"

    def __init__(self, store: AppendOnlyEventStore) -> None:
        self.store = store

    def run(self, manifest: DryRunManifest) -> DryRunResult:
        self._validate_identity(manifest)
        input_digest = self._digest(manifest.to_dict())
        completion_events = [
            event
            for event in self.store.events_for(manifest.run_id)
            if event.event_type == "dry_run.completed"
        ]
        if len(completion_events) > 1:
            raise DryRunError("run has duplicate completion events")
        if completion_events and completion_events[0].payload["input_digest"] != input_digest:
            raise DryRunError("run_id already completed with different input")

        source = IntentInbox(self.store).capture(
            manifest.source.raw_text,
            kind=manifest.source.kind,
            metadata=manifest.source.metadata,
            source_id=manifest.source.source_id,
        )
        atoms = IntentExtractor().extract(source)
        self._validate_indexes(manifest, atoms)
        self._validate_source_spans(source, atoms)
        lifecycle = IntentLifecycle(self.store)
        atoms = self._propose_or_resume(lifecycle, atoms)

        required_indexes = self._required_confirmation_indexes(manifest, atoms)
        provided_indexes = set(manifest.confirmed_atom_indexes)
        unexpected = provided_indexes - required_indexes
        if unexpected:
            raise DryRunError(
                "confirmation scope includes unrelated atom index %d" % min(unexpected)
            )
        atoms = self._apply_confirmations(
            lifecycle, atoms, provided_indexes, manifest.confirmation
        )
        missing = required_indexes - provided_indexes
        if missing:
            packet = self._awaiting_confirmation_packet(atoms, missing, source)
            return DryRunResult(
                run_id=manifest.run_id,
                source_id=source.source_id,
                content_sha256=source.content_sha256,
                atoms=tuple(atoms),
                proposal=None,
                decision_packet=packet,
            )

        snapshot = self._build_or_resume_graph(manifest, atoms)
        request = CompileRequest(
            title=manifest.plan.title,
            outcome=manifest.plan.outcome,
            target_atom_ids=tuple(atoms[index].atom_id for index in manifest.plan.target_indexes),
            owned_paths=manifest.plan.owned_paths,
            acceptance_criteria=manifest.plan.acceptance_criteria,
            verification_steps=manifest.plan.verification_steps,
            explicit_exclusions=manifest.plan.explicit_exclusions,
            risk=manifest.plan.risk,
            max_atoms=manifest.plan.max_atoms,
        )
        proposal = PRCompiler().compile(snapshot, request)
        packet = self._complete_packet(source, atoms, proposal)
        result = DryRunResult(
            run_id=manifest.run_id,
            source_id=source.source_id,
            content_sha256=source.content_sha256,
            atoms=tuple(atoms),
            proposal=proposal,
            decision_packet=packet,
        )
        if not completion_events:
            self.store.append(
                manifest.run_id,
                "dry_run.completed",
                {
                    "input_digest": input_digest,
                    "plan_id": proposal.plan.plan_id,
                    "decision_status": packet.status,
                    "external_effects": False,
                },
            )
        return result

    @staticmethod
    def _validate_identity(manifest: DryRunManifest) -> None:
        if not manifest.run_id.strip() or not manifest.graph_id.strip():
            raise DryRunError("run_id and graph_id must be non-empty")
        if manifest.run_id == manifest.graph_id or manifest.run_id == manifest.source.source_id:
            raise DryRunError("run, graph, and source identifiers must be distinct")

    @staticmethod
    def _validate_indexes(
        manifest: DryRunManifest, atoms: List[IntentAtom]
    ) -> None:
        indexes: List[int] = list(manifest.confirmed_atom_indexes)
        indexes.extend(manifest.plan.target_indexes)
        for item in manifest.dependencies + manifest.conflicts:
            indexes.extend((item.source_index, item.target_index))
        for cluster in manifest.clusters:
            indexes.extend(cluster.member_indexes)
        for index in indexes:
            if not isinstance(index, int) or isinstance(index, bool):
                raise DryRunError("atom indexes must be integers")
            if index < 0 or index >= len(atoms):
                raise DryRunError("atom index %s is out of range" % index)

    @staticmethod
    def _validate_source_spans(source: SourceRecord, atoms: List[IntentAtom]) -> None:
        for atom in atoms:
            if source.raw_text[atom.source_start : atom.source_end] != atom.statement:
                raise DryRunError("atom source span does not match raw source")

    @staticmethod
    def _propose_or_resume(
        lifecycle: IntentLifecycle, atoms: List[IntentAtom]
    ) -> List[IntentAtom]:
        resumed: List[IntentAtom] = []
        for atom in atoms:
            try:
                existing = lifecycle.current(atom.atom_id)
            except IntentLifecycleError:
                lifecycle.propose(atom)
                existing = atom
            expected = atom.to_dict()
            actual = existing.to_dict()
            expected.pop("state")
            actual.pop("state")
            if expected != actual:
                raise DryRunError("atom identity changed during resume")
            resumed.append(existing)
        return resumed

    @staticmethod
    def _required_confirmation_indexes(
        manifest: DryRunManifest, atoms: List[IntentAtom]
    ) -> Set[int]:
        dependencies: Dict[int, Set[int]] = {index: set() for index in range(len(atoms))}
        for item in manifest.dependencies:
            dependencies[item.source_index].add(item.target_index)
        closure: Set[int] = set()
        pending = list(manifest.plan.target_indexes)
        while pending:
            index = pending.pop()
            if index in closure:
                continue
            closure.add(index)
            pending.extend(dependencies[index])
        return {index for index in closure if atoms[index].requires_human_confirmation}

    @staticmethod
    def _apply_confirmations(
        lifecycle: IntentLifecycle,
        atoms: List[IntentAtom],
        indexes: Set[int],
        confirmation: ConfirmationRecord,
    ) -> List[IntentAtom]:
        updated = list(atoms)
        for index in sorted(indexes):
            atom = lifecycle.current(atoms[index].atom_id)
            if atom.state == AtomState.CONFIRMED:
                updated[index] = atom
                continue
            try:
                updated[index] = lifecycle.confirm(
                    atom.atom_id, confirmation=confirmation
                )
            except IntentLifecycleError as exc:
                raise DryRunError(str(exc)) from exc
        return updated

    def _build_or_resume_graph(
        self, manifest: DryRunManifest, atoms: List[IntentAtom]
    ) -> GraphSnapshot:
        graph = IntentGraph(manifest.graph_id, self.store)
        snapshot = graph.snapshot()
        for atom in atoms:
            if atom.atom_id not in snapshot.atoms:
                snapshot = graph.add_atom(atom)
            else:
                snapshot = graph.sync_atom_state(atom)
        for item in manifest.dependencies:
            source_id = atoms[item.source_index].atom_id
            target_id = atoms[item.target_index].atom_id
            edge_exists = any(
                edge.kind == EdgeKind.DEPENDS_ON
                and edge.source_atom_id == source_id
                and edge.target_atom_id == target_id
                for edge in snapshot.edges
            )
            if not edge_exists:
                snapshot = graph.add_dependency(source_id, target_id)
        for item in manifest.conflicts:
            first = atoms[item.source_index].atom_id
            second = atoms[item.target_index].atom_id
            canonical = tuple(sorted((first, second)))
            edge_exists = any(
                edge.kind == EdgeKind.CONFLICTS_WITH
                and (edge.source_atom_id, edge.target_atom_id) == canonical
                for edge in snapshot.edges
            )
            if not edge_exists:
                snapshot = graph.add_conflict(first, second)
        for item in manifest.clusters:
            expected = IntentCluster(
                cluster_id=item.cluster_id,
                label=item.label,
                member_atom_ids=tuple(
                    sorted({atoms[index].atom_id for index in item.member_indexes})
                ),
            )
            existing = snapshot.clusters.get(item.cluster_id)
            if existing is None:
                snapshot = graph.define_cluster(
                    item.cluster_id,
                    item.label,
                    [atoms[index].atom_id for index in item.member_indexes],
                )
            elif existing != expected:
                raise DryRunError("cluster changed during resume")
        return snapshot

    def _awaiting_confirmation_packet(
        self, atoms: List[IntentAtom], missing: Set[int], source: SourceRecord
    ) -> DecisionPacket:
        statements = "; ".join(atoms[index].statement for index in sorted(missing))
        return DecisionPacket(
            schema_version=self.SCHEMA_VERSION,
            status="awaiting_confirmation",
            outcome="Source preserved and intent atoms extracted; compilation is paused.",
            evidence=(
                "Raw source preserved with SHA-256 %s." % source.content_sha256,
                "%d source-grounded atoms extracted with exact spans." % len(atoms),
                "No graph cut or execution brief was compiled.",
            ),
            material_risks=(
                "Actionable language has not received explicit human confirmation.",
            ),
            primary_decision=PrimaryDecision(
                question="Confirm this actionable intent, revise it, or reject it: %s"
                % statements,
                choices=(
                    DecisionChoice("confirm", "Confirm", "Permit dry-run planning only."),
                    DecisionChoice("revise", "Revise", "Change the interpreted intent."),
                    DecisionChoice("reject", "Reject", "Keep it non-actionable."),
                ),
                recommended_key="revise",
            ),
            next_step="Update confirmed_atom_indexes only after the human chooses confirm.",
            external_effects=False,
        )

    def _complete_packet(
        self,
        source: SourceRecord,
        atoms: List[IntentAtom],
        proposal: CompiledProposal,
    ) -> DecisionPacket:
        return DecisionPacket(
            schema_version=self.SCHEMA_VERSION,
            status="dry_run_complete",
            outcome="A reviewable PR plan and bounded execution brief were compiled.",
            evidence=(
                "Raw source preserved with SHA-256 %s." % source.content_sha256,
                "%d atom spans match the immutable source." % len(atoms),
                "Graph cut %s is dependency-closed and conflict-free."
                % proposal.plan.plan_id,
                "Plan and brief use schema %s and P1 draft-only permission."
                % proposal.plan.schema_version,
                "No external effect occurred.",
            ),
            material_risks=(
                "Rule-based extraction may under-classify unfamiliar phrasing.",
                "This dry run does not prove a live executor or integration path.",
            ),
            primary_decision=PrimaryDecision(
                question="Is this dry-run plan coherent enough to retain for future review?",
                choices=(
                    DecisionChoice(
                        "accept_draft",
                        "Accept draft",
                        "Retain the proposal; do not execute it.",
                    ),
                    DecisionChoice(
                        "revise", "Revise", "Change intent, graph, scope, or evidence."
                    ),
                    DecisionChoice(
                        "reject", "Reject", "Discard the proposal from future planning."
                    ),
                ),
                recommended_key="accept_draft",
            ),
            next_step="Review the plan and brief; execution requires separate authorization.",
            external_effects=False,
        )

    @staticmethod
    def _digest(value: Dict[str, Any]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()
