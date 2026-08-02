from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Set, Tuple

from .intents import AtomState, IntentAtom
from .store import AppendOnlyEventStore


class GraphError(RuntimeError):
    pass


class EdgeKind(str, Enum):
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"


@dataclass(frozen=True)
class IntentEdge:
    source_atom_id: str
    target_atom_id: str
    kind: EdgeKind

    def to_dict(self) -> Dict[str, str]:
        return {
            "source_atom_id": self.source_atom_id,
            "target_atom_id": self.target_atom_id,
            "kind": self.kind.value,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "IntentEdge":
        return cls(
            source_atom_id=value["source_atom_id"],
            target_atom_id=value["target_atom_id"],
            kind=EdgeKind(value["kind"]),
        )


@dataclass(frozen=True)
class IntentCluster:
    cluster_id: str
    label: str
    member_atom_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "label": self.label,
            "member_atom_ids": list(self.member_atom_ids),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "IntentCluster":
        return cls(
            cluster_id=value["cluster_id"],
            label=value["label"],
            member_atom_ids=tuple(value["member_atom_ids"]),
        )


@dataclass(frozen=True)
class GraphSnapshot:
    graph_id: str
    atoms: Dict[str, IntentAtom]
    edges: Tuple[IntentEdge, ...]
    clusters: Dict[str, IntentCluster]

    def dependencies_of(self, atom_id: str) -> Tuple[str, ...]:
        return tuple(
            sorted(
                edge.target_atom_id
                for edge in self.edges
                if edge.kind == EdgeKind.DEPENDS_ON
                and edge.source_atom_id == atom_id
            )
        )

    def conflicts(self) -> Tuple[IntentEdge, ...]:
        return tuple(edge for edge in self.edges if edge.kind == EdgeKind.CONFLICTS_WITH)

    def topological_order(self) -> Tuple[str, ...]:
        dependents: Dict[str, Set[str]] = {atom_id: set() for atom_id in self.atoms}
        indegree = {atom_id: 0 for atom_id in self.atoms}
        for edge in self.edges:
            if edge.kind != EdgeKind.DEPENDS_ON:
                continue
            dependents[edge.target_atom_id].add(edge.source_atom_id)
            indegree[edge.source_atom_id] += 1
        ready = sorted(atom_id for atom_id, degree in indegree.items() if degree == 0)
        ordered: List[str] = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for dependent in sorted(dependents[current]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort()
        if len(ordered) != len(self.atoms):
            raise GraphError("dependency graph contains a cycle")
        return tuple(ordered)


class IntentGraph:
    """Event-sourced projection of intent atoms and their relationships."""

    def __init__(self, graph_id: str, store: AppendOnlyEventStore) -> None:
        if not graph_id.strip():
            raise ValueError("graph_id must be non-empty")
        self.graph_id = graph_id
        self.store = store

    def snapshot(self) -> GraphSnapshot:
        atoms: Dict[str, IntentAtom] = {}
        edges: List[IntentEdge] = []
        clusters: Dict[str, IntentCluster] = {}
        for event in self.store.events_for(self.graph_id):
            if event.event_type == "graph.atom_added":
                atom = IntentAtom.from_dict(event.payload)
                if atom.atom_id in atoms:
                    raise GraphError("duplicate atom event %s" % atom.atom_id)
                atoms[atom.atom_id] = atom
            elif event.event_type == "graph.atom_state_updated":
                atom_id = event.payload["atom_id"]
                if atom_id not in atoms:
                    raise GraphError("state update references missing atom %s" % atom_id)
                value = atoms[atom_id].to_dict()
                value["state"] = AtomState(event.payload["state"]).value
                atoms[atom_id] = IntentAtom.from_dict(value)
            elif event.event_type == "graph.edge_added":
                edge = IntentEdge.from_dict(event.payload)
                self._validate_endpoints(edge.source_atom_id, edge.target_atom_id, atoms)
                if edge in edges:
                    raise GraphError("duplicate graph edge in history")
                edges.append(edge)
            elif event.event_type == "graph.cluster_defined":
                cluster = IntentCluster.from_dict(event.payload)
                if cluster.cluster_id in clusters:
                    raise GraphError("duplicate cluster event %s" % cluster.cluster_id)
                self._validate_cluster(cluster, atoms)
                clusters[cluster.cluster_id] = cluster
            else:
                raise GraphError("unsupported graph event %s" % event.event_type)
        snapshot = GraphSnapshot(
            graph_id=self.graph_id,
            atoms=atoms,
            edges=tuple(edges),
            clusters=clusters,
        )
        snapshot.topological_order()
        return snapshot

    def add_atom(self, atom: IntentAtom) -> GraphSnapshot:
        current = self.snapshot()
        if atom.atom_id in current.atoms:
            raise GraphError("atom %s already exists" % atom.atom_id)
        self.store.append(self.graph_id, "graph.atom_added", atom.to_dict())
        return self.snapshot()

    def sync_atom_state(self, atom: IntentAtom) -> GraphSnapshot:
        current = self.snapshot()
        previous = current.atoms.get(atom.atom_id)
        if previous is None:
            raise GraphError("cannot sync missing atom %s" % atom.atom_id)
        previous_identity = previous.to_dict()
        current_identity = atom.to_dict()
        previous_identity.pop("state")
        current_identity.pop("state")
        if previous_identity != current_identity:
            raise GraphError("atom provenance cannot change during state sync")
        if previous.state == atom.state:
            return current
        self.store.append(
            self.graph_id,
            "graph.atom_state_updated",
            {"atom_id": atom.atom_id, "state": atom.state.value},
        )
        return self.snapshot()

    def add_dependency(self, atom_id: str, prerequisite_atom_id: str) -> GraphSnapshot:
        current = self.snapshot()
        self._validate_endpoints(atom_id, prerequisite_atom_id, current.atoms)
        edge = IntentEdge(atom_id, prerequisite_atom_id, EdgeKind.DEPENDS_ON)
        if edge in current.edges:
            raise GraphError("dependency already exists")
        if self._would_create_cycle(current, atom_id, prerequisite_atom_id):
            raise GraphError("dependency would create a cycle")
        self.store.append(self.graph_id, "graph.edge_added", edge.to_dict())
        return self.snapshot()

    def add_conflict(self, first_atom_id: str, second_atom_id: str) -> GraphSnapshot:
        current = self.snapshot()
        self._validate_endpoints(first_atom_id, second_atom_id, current.atoms)
        first, second = sorted((first_atom_id, second_atom_id))
        edge = IntentEdge(first, second, EdgeKind.CONFLICTS_WITH)
        if edge in current.edges:
            raise GraphError("conflict already exists")
        self.store.append(self.graph_id, "graph.edge_added", edge.to_dict())
        return self.snapshot()

    def define_cluster(
        self, cluster_id: str, label: str, member_atom_ids: Iterable[str]
    ) -> GraphSnapshot:
        current = self.snapshot()
        if cluster_id in current.clusters:
            raise GraphError("cluster %s already exists" % cluster_id)
        cluster = IntentCluster(
            cluster_id=cluster_id,
            label=label,
            member_atom_ids=tuple(sorted(set(member_atom_ids))),
        )
        self._validate_cluster(cluster, current.atoms)
        self.store.append(self.graph_id, "graph.cluster_defined", cluster.to_dict())
        return self.snapshot()

    @staticmethod
    def _validate_endpoints(
        first_atom_id: str, second_atom_id: str, atoms: Dict[str, IntentAtom]
    ) -> None:
        if first_atom_id == second_atom_id:
            raise GraphError("self relationships are not allowed")
        missing = [value for value in (first_atom_id, second_atom_id) if value not in atoms]
        if missing:
            raise GraphError("relationship references missing atom %s" % missing[0])

    @staticmethod
    def _validate_cluster(
        cluster: IntentCluster, atoms: Dict[str, IntentAtom]
    ) -> None:
        if not cluster.cluster_id.strip() or not cluster.label.strip():
            raise GraphError("cluster id and label must be non-empty")
        if not cluster.member_atom_ids:
            raise GraphError("cluster must contain at least one atom")
        missing = [atom_id for atom_id in cluster.member_atom_ids if atom_id not in atoms]
        if missing:
            raise GraphError("cluster references missing atom %s" % missing[0])

    @staticmethod
    def _would_create_cycle(
        snapshot: GraphSnapshot, atom_id: str, prerequisite_atom_id: str
    ) -> bool:
        dependencies: Dict[str, Set[str]] = {
            existing_atom_id: set() for existing_atom_id in snapshot.atoms
        }
        for edge in snapshot.edges:
            if edge.kind == EdgeKind.DEPENDS_ON:
                dependencies[edge.source_atom_id].add(edge.target_atom_id)
        pending = [prerequisite_atom_id]
        visited: Set[str] = set()
        while pending:
            current = pending.pop()
            if current == atom_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(dependencies[current])
        return False
