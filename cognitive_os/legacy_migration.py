from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Iterable, Optional, Tuple

from .data_policy import PrivateDataPolicy, RawRetentionMode
from .intents import AtomKind, AtomState, ConfidenceBand, SemanticConfidence
from .models import Event, SourceKind
from .private_lineage import StructuralIntentAtom, StructuralSourceRecord


class LegacyMigrationError(RuntimeError):
    """Raised when a legacy migration plan cannot be produced unambiguously."""


PRIVATE_FIELDS = frozenset(("raw_text", "statement", "metadata"))
SUPPORTED_PRIVATE_EVENTS = frozenset(
    ("source.captured", "atom.proposed", "graph.atom_added")
)


def _sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_exact_keys(value: Any, expected: set[str], label: str) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise LegacyMigrationError("%s has an unsupported field set" % label)
    return value


def _private_fields(value: Any) -> Tuple[str, ...]:
    found = set()

    def collect(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in PRIVATE_FIELDS:
                    found.add(key)
                collect(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                collect(child)

    collect(value)
    return tuple(sorted(found))


def _require_identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or any(character in value for character in "*?[]")
    ):
        raise LegacyMigrationError("%s must be one exact identifier" % label)
    return value


@dataclass(frozen=True)
class LegacyMigrationRequest:
    project_id: str
    source_ids: Tuple[str, ...]
    expected_ledger_sha256: str


@dataclass(frozen=True)
class LegacyEventBinding:
    event_id: str
    sequence: int
    stream_id: str
    event_type: str
    private_fields: Tuple[str, ...]
    event_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "stream_id": self.stream_id,
            "event_type": self.event_type,
            "private_fields": list(self.private_fields),
            "event_sha256": self.event_sha256,
        }


@dataclass(frozen=True)
class LegacySourceMigration:
    source_id: str
    legacy_event: LegacyEventBinding
    structural_target: StructuralSourceRecord

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "legacy_event": self.legacy_event.to_dict(),
            "structural_target": self.structural_target.to_dict(),
        }


@dataclass(frozen=True)
class LegacyAtomMigration:
    atom_id: str
    source_id: str
    legacy_events: Tuple[LegacyEventBinding, ...]
    structural_target: StructuralIntentAtom

    def to_dict(self) -> Dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "source_id": self.source_id,
            "legacy_events": [event.to_dict() for event in self.legacy_events],
            "structural_target": self.structural_target.to_dict(),
        }


@dataclass(frozen=True)
class LegacyMigrationPlan:
    schema_version: str
    plan_id: str
    project_id: str
    source_ids: Tuple[str, ...]
    ledger_sha256: str
    sources: Tuple[LegacySourceMigration, ...]
    atoms: Tuple[LegacyAtomMigration, ...]
    scoped_private_event_count: int
    unscoped_private_event_count: int
    required_capabilities: Tuple[str, ...]
    action: str
    executable: bool
    writes_performed: bool
    external_effects: bool
    raw_values_included: bool
    requires_exact_human_approval_for_execution: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "source_ids": list(self.source_ids),
            "ledger_sha256": self.ledger_sha256,
            "sources": [source.to_dict() for source in self.sources],
            "atoms": [atom.to_dict() for atom in self.atoms],
            "scoped_private_event_count": self.scoped_private_event_count,
            "unscoped_private_event_count": self.unscoped_private_event_count,
            "required_capabilities": list(self.required_capabilities),
            "action": self.action,
            "executable": self.executable,
            "writes_performed": self.writes_performed,
            "external_effects": self.external_effects,
            "raw_values_included": self.raw_values_included,
            "requires_exact_human_approval_for_execution": (
                self.requires_exact_human_approval_for_execution
            ),
        }


@dataclass(frozen=True)
class _LegacySource:
    source_id: str
    kind: SourceKind
    raw_text: str
    captured_at: str
    content_sha256: str


@dataclass(frozen=True)
class _LegacyAtom:
    atom_id: str
    source_id: str
    kind: AtomKind
    statement: str
    source_start: int
    source_end: int
    state: AtomState
    requires_human_confirmation: bool
    extraction_method: str
    semantic_confidence: SemanticConfidence

    def identity(self) -> Dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "source_id": self.source_id,
            "kind": self.kind.value,
            "statement": self.statement,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "requires_human_confirmation": self.requires_human_confirmation,
            "extraction_method": self.extraction_method,
            "semantic_confidence": self.semantic_confidence.to_dict(),
        }


class LegacyMigrationPlanner:
    """Builds an exact, effect-free plan; it never mutates the supplied ledger."""

    SCHEMA_VERSION = "1.0"
    REQUIRED_CAPABILITIES = (
        "structural lifecycle projection for v2 atom events",
        "structural graph projection for v2 atom events",
        "approved content disposition at migration time",
        "atomic replacement-ledger and quarantine executor",
        "rollback and restart-equivalence verification",
        "exact human approval for the target ledger effect",
    )

    def __init__(self, policy: PrivateDataPolicy) -> None:
        self.policy = policy.validated()
        if (
            len(self.policy.project_ids) != 1
            or self.policy.raw_retention != RawRetentionMode.SESSION_ONLY
        ):
            raise LegacyMigrationError(
                "legacy migration planning requires session-only single-project policy"
            )

    @staticmethod
    def ledger_sha256(events: Iterable[Event]) -> str:
        return _sha256([event.to_dict() for event in events])

    def plan(
        self, request: LegacyMigrationRequest, events: Iterable[Event]
    ) -> LegacyMigrationPlan:
        values = tuple(events)
        project_id = _require_identifier(request.project_id, "project_id")
        if project_id not in self.policy.project_ids:
            raise LegacyMigrationError("request exceeds the approved project scope")
        if not isinstance(request.source_ids, tuple):
            raise LegacyMigrationError("source_ids must be an exact tuple")
        source_ids = tuple(
            sorted(
                _require_identifier(item, "source_id") for item in request.source_ids
            )
        )
        if not source_ids or len(set(source_ids)) != len(source_ids):
            raise LegacyMigrationError("source_ids must be non-empty and unique")
        if (
            not isinstance(request.expected_ledger_sha256, str)
            or len(request.expected_ledger_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in request.expected_ledger_sha256
            )
        ):
            raise LegacyMigrationError("expected ledger digest is invalid")
        ledger_digest = self.ledger_sha256(values)
        if ledger_digest != request.expected_ledger_sha256:
            raise LegacyMigrationError("legacy ledger changed; plan from fresh state")

        source_set = set(source_ids)
        private_events = [event for event in values if _private_fields(event.payload)]
        for event in private_events:
            if event.event_type not in SUPPORTED_PRIVATE_EVENTS:
                raise LegacyMigrationError(
                    "unsupported private-bearing event %s" % event.event_type
                )

        source_events: Dict[str, list[Event]] = {item: [] for item in source_ids}
        atom_events: Dict[str, list[Tuple[Event, _LegacyAtom]]] = {}
        unscoped = 0
        parsed_sources: Dict[str, _LegacySource] = {}

        for event in private_events:
            payload_source_id = event.payload.get("source_id")
            if not isinstance(payload_source_id, str):
                raise LegacyMigrationError("private event has no exact source lineage")
            if payload_source_id not in source_set:
                unscoped += 1
                continue
            if event.event_type == "source.captured":
                source_events[payload_source_id].append(event)

        for source_id in source_ids:
            matches = source_events[source_id]
            if len(matches) != 1:
                raise LegacyMigrationError(
                    "requested source must have one legacy capture event"
                )
            source = self._parse_source(matches[0])
            parsed_sources[source_id] = source

        for event in private_events:
            payload_source_id = event.payload.get("source_id")
            if (
                payload_source_id not in source_set
                or event.event_type == "source.captured"
            ):
                continue
            atom = self._parse_atom(event, parsed_sources[payload_source_id])
            atom_events.setdefault(atom.atom_id, []).append((event, atom))

        source_plans = tuple(
            LegacySourceMigration(
                source_id=source_id,
                legacy_event=self._binding(source_events[source_id][0]),
                structural_target=StructuralSourceRecord(
                    source_id=source_id,
                    kind=parsed_sources[source_id].kind,
                    captured_at=parsed_sources[source_id].captured_at,
                    content_sha256=parsed_sources[source_id].content_sha256,
                    content_length=len(parsed_sources[source_id].raw_text),
                    retention_mode=RawRetentionMode.SESSION_ONLY,
                ),
            )
            for source_id in source_ids
        )
        atom_plans = tuple(
            self._atom_plan(atom_id, candidates, values)
            for atom_id, candidates in sorted(atom_events.items())
        )
        scoped_count = sum(
            1
            for event in private_events
            if event.payload.get("source_id") in source_set
        )
        identity = {
            "project_id": project_id,
            "source_ids": list(source_ids),
            "ledger_sha256": ledger_digest,
            "sources": [item.to_dict() for item in source_plans],
            "atoms": [item.to_dict() for item in atom_plans],
            "scoped_private_event_count": scoped_count,
            "unscoped_private_event_count": unscoped,
            "required_capabilities": list(self.REQUIRED_CAPABILITIES),
            "action": "plan_only",
        }
        return LegacyMigrationPlan(
            schema_version=self.SCHEMA_VERSION,
            plan_id="legacy_migration_%s" % _sha256(identity)[:20],
            project_id=project_id,
            source_ids=source_ids,
            ledger_sha256=ledger_digest,
            sources=source_plans,
            atoms=atom_plans,
            scoped_private_event_count=scoped_count,
            unscoped_private_event_count=unscoped,
            required_capabilities=self.REQUIRED_CAPABILITIES,
            action="plan_only",
            executable=False,
            writes_performed=False,
            external_effects=False,
            raw_values_included=False,
            requires_exact_human_approval_for_execution=True,
        )

    @staticmethod
    def _parse_source(event: Event) -> _LegacySource:
        value = _require_exact_keys(
            event.payload,
            {
                "source_id",
                "kind",
                "raw_text",
                "captured_at",
                "content_sha256",
                "metadata",
            },
            "legacy source",
        )
        source_id = _require_identifier(value["source_id"], "source_id")
        if event.stream_id != source_id:
            raise LegacyMigrationError("legacy source is routed to the wrong stream")
        raw_text = value["raw_text"]
        captured_at = value["captured_at"]
        metadata = value["metadata"]
        if (
            not isinstance(raw_text, str)
            or not raw_text.strip()
            or not isinstance(captured_at, str)
            or not captured_at.strip()
            or not isinstance(metadata, dict)
            or any(
                not isinstance(key, str) or not isinstance(item, str)
                for key, item in metadata.items()
            )
        ):
            raise LegacyMigrationError("legacy source has invalid private fields")
        content_sha256 = value["content_sha256"]
        if content_sha256 != _text_sha256(raw_text):
            raise LegacyMigrationError("legacy source content digest is invalid")
        try:
            kind = SourceKind(value["kind"])
        except (TypeError, ValueError) as exc:
            raise LegacyMigrationError("legacy source kind is invalid") from exc
        return _LegacySource(
            source_id=source_id,
            kind=kind,
            raw_text=raw_text,
            captured_at=captured_at,
            content_sha256=content_sha256,
        )

    @staticmethod
    def _parse_atom(event: Event, source: _LegacySource) -> _LegacyAtom:
        base_keys = {
            "atom_id",
            "source_id",
            "kind",
            "statement",
            "source_start",
            "source_end",
            "state",
            "requires_human_confirmation",
            "extraction_method",
        }
        actual = set(event.payload)
        if actual not in (base_keys, base_keys | {"semantic_confidence"}):
            raise LegacyMigrationError("legacy atom has an unsupported field set")
        value = event.payload
        atom_id = _require_identifier(value["atom_id"], "atom_id")
        source_id = _require_identifier(value["source_id"], "source_id")
        statement = value["statement"]
        start = value["source_start"]
        end = value["source_end"]
        confirmation = value["requires_human_confirmation"]
        method = value["extraction_method"]
        if (
            source_id != source.source_id
            or not isinstance(statement, str)
            or not statement
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(source.raw_text)
            or source.raw_text[start:end] != statement
            or not isinstance(confirmation, bool)
            or confirmation
            != (
                value["kind"]
                in (AtomKind.ACTIONABLE.value, AtomKind.DECISION_REQUEST.value)
            )
            or not isinstance(method, str)
            or not method.strip()
        ):
            raise LegacyMigrationError("legacy atom provenance is invalid")
        if event.event_type == "atom.proposed" and event.stream_id != atom_id:
            raise LegacyMigrationError("legacy atom proposal is misrouted")
        try:
            kind = AtomKind(value["kind"])
            state = AtomState(value["state"])
            confidence = LegacyMigrationPlanner._parse_confidence(
                value.get("semantic_confidence")
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise LegacyMigrationError("legacy atom type is invalid") from exc
        return _LegacyAtom(
            atom_id=atom_id,
            source_id=source_id,
            kind=kind,
            statement=statement,
            source_start=start,
            source_end=end,
            state=state,
            requires_human_confirmation=confirmation,
            extraction_method=method,
            semantic_confidence=confidence,
        )

    @staticmethod
    def _parse_confidence(value: Optional[Dict[str, Any]]) -> SemanticConfidence:
        if value is None:
            return SemanticConfidence.unassessed()
        value = _require_exact_keys(
            value, {"band", "score_millis", "signals"}, "semantic confidence"
        )
        score = value["score_millis"]
        signals = value["signals"]
        if (
            isinstance(score, bool)
            or not isinstance(score, int)
            or not isinstance(signals, list)
            or any(not isinstance(signal, str) for signal in signals)
        ):
            raise LegacyMigrationError("semantic confidence types are invalid")
        return SemanticConfidence(
            band=ConfidenceBand(value["band"]),
            score_millis=score,
            signals=tuple(signals),
        )

    def _atom_plan(
        self,
        atom_id: str,
        candidates: list[Tuple[Event, _LegacyAtom]],
        events: Tuple[Event, ...],
    ) -> LegacyAtomMigration:
        first = candidates[0][1]
        graph_streams = [
            event.stream_id
            for event, _ in candidates
            if event.event_type == "graph.atom_added"
        ]
        if len(set(graph_streams)) != len(graph_streams):
            raise LegacyMigrationError("legacy graph has duplicate atom history")
        if any(
            candidate.identity() != first.identity() for _, candidate in candidates[1:]
        ):
            raise LegacyMigrationError("legacy atom copies have conflicting identity")
        states = {
            self._final_state(event, candidate, events)
            for event, candidate in candidates
        }
        if len(states) != 1:
            raise LegacyMigrationError("legacy atom projections disagree on state")
        state = next(iter(states))
        return LegacyAtomMigration(
            atom_id=atom_id,
            source_id=first.source_id,
            legacy_events=tuple(
                self._binding(event)
                for event, _ in sorted(candidates, key=lambda item: item[0].sequence)
            ),
            structural_target=StructuralIntentAtom(
                atom_id=first.atom_id,
                source_id=first.source_id,
                kind=first.kind,
                source_start=first.source_start,
                source_end=first.source_end,
                statement_sha256=_text_sha256(first.statement),
                state=state,
                requires_human_confirmation=first.requires_human_confirmation,
                extraction_method=first.extraction_method,
                semantic_confidence=first.semantic_confidence,
            ),
        )

    @staticmethod
    def _final_state(
        origin: Event, atom: _LegacyAtom, events: Tuple[Event, ...]
    ) -> AtomState:
        state = atom.state
        if origin.event_type == "atom.proposed":
            if state not in (AtomState.PROPOSED, AtomState.AWAITING_CONFIRMATION):
                raise LegacyMigrationError(
                    "legacy proposal has an invalid initial state"
                )
            stream = [event for event in events if event.stream_id == atom.atom_id]
            if not stream or stream[0].event_id != origin.event_id:
                raise LegacyMigrationError("legacy lifecycle history is ambiguous")
            for event in stream[1:]:
                transitions = {
                    "atom.confirmed": AtomState.CONFIRMED,
                    "atom.rejected": AtomState.REJECTED,
                    "atom.superseded": AtomState.SUPERSEDED,
                }
                if event.event_type not in transitions:
                    raise LegacyMigrationError("legacy lifecycle event is unsupported")
                target = transitions[event.event_type]
                allowed = {
                    "atom.confirmed": state == AtomState.AWAITING_CONFIRMATION,
                    "atom.rejected": state
                    in (AtomState.PROPOSED, AtomState.AWAITING_CONFIRMATION),
                    "atom.superseded": state == AtomState.CONFIRMED,
                }
                if not allowed[event.event_type]:
                    raise LegacyMigrationError("legacy lifecycle transition is invalid")
                state = target
        elif origin.event_type == "graph.atom_added":
            for event in events:
                if (
                    event.sequence < origin.sequence
                    and event.stream_id == origin.stream_id
                    and event.event_type == "graph.atom_state_updated"
                    and event.payload.get("atom_id") == atom.atom_id
                ):
                    raise LegacyMigrationError("graph state predates atom history")
                if (
                    event.sequence <= origin.sequence
                    or event.stream_id != origin.stream_id
                    or event.event_type != "graph.atom_state_updated"
                    or event.payload.get("atom_id") != atom.atom_id
                ):
                    continue
                _require_exact_keys(
                    event.payload, {"atom_id", "state"}, "graph atom state update"
                )
                try:
                    state = AtomState(event.payload["state"])
                except (TypeError, ValueError) as exc:
                    raise LegacyMigrationError("graph atom state is invalid") from exc
        return state

    @staticmethod
    def _binding(event: Event) -> LegacyEventBinding:
        return LegacyEventBinding(
            event_id=event.event_id,
            sequence=event.sequence,
            stream_id=event.stream_id,
            event_type=event.event_type,
            private_fields=_private_fields(event.payload),
            event_sha256=_sha256(event.to_dict()),
        )
