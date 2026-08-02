from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import re
from typing import Any, Dict, Iterable, List
from uuid import uuid4

from .models import Event, SourceRecord
from .store import AppendOnlyEventStore


class AtomKind(str, Enum):
    EXPLORATION = "exploration"
    ACTIONABLE = "actionable"
    CONSTRAINT = "constraint"
    DECISION_REQUEST = "decision_request"


class AtomState(str, Enum):
    PROPOSED = "proposed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ConfirmationAuthority(str, Enum):
    HUMAN = "human"
    SYSTEM = "system"


class ConfidenceBand(str, Enum):
    UNASSESSED = "unassessed"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class SemanticConfidence:
    """Deterministic interpretation evidence; never an authority signal."""

    band: ConfidenceBand
    score_millis: int
    signals: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.score_millis <= 1000:
            raise ValueError("confidence score_millis must be between 0 and 1000")
        if tuple(sorted(set(self.signals))) != self.signals:
            raise ValueError("confidence signals must be unique and sorted")
        if any(not signal.strip() for signal in self.signals):
            raise ValueError("confidence signals must be non-empty")
        valid_range = {
            ConfidenceBand.UNASSESSED: self.score_millis == 0 and not self.signals,
            ConfidenceBand.LOW: self.score_millis < 400 and bool(self.signals),
            ConfidenceBand.MEDIUM: 400 <= self.score_millis < 800 and bool(self.signals),
            ConfidenceBand.HIGH: 800 <= self.score_millis <= 1000 and bool(self.signals),
        }
        if not valid_range[self.band]:
            raise ValueError("confidence band does not match score or signals")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "band": self.band.value,
            "score_millis": self.score_millis,
            "signals": list(self.signals),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "SemanticConfidence":
        return cls(
            band=ConfidenceBand(value["band"]),
            score_millis=int(value["score_millis"]),
            signals=tuple(value["signals"]),
        )

    @classmethod
    def unassessed(cls) -> "SemanticConfidence":
        return cls(
            band=ConfidenceBand.UNASSESSED,
            score_millis=0,
            signals=(),
        )


@dataclass(frozen=True)
class ConfirmationRecord:
    actor_id: str
    authority: ConfirmationAuthority
    channel: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "actor_id": self.actor_id,
            "authority": self.authority.value,
            "channel": self.channel,
        }


@dataclass(frozen=True)
class IntentAtom:
    atom_id: str
    source_id: str
    kind: AtomKind
    statement: str
    source_start: int
    source_end: int
    state: AtomState
    requires_human_confirmation: bool
    extraction_method: str = "rules_v1"
    semantic_confidence: SemanticConfidence = field(
        default_factory=SemanticConfidence.unassessed
    )

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        value["state"] = self.state.value
        value["semantic_confidence"] = self.semantic_confidence.to_dict()
        return value

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "IntentAtom":
        return cls(
            atom_id=value["atom_id"],
            source_id=value["source_id"],
            kind=AtomKind(value["kind"]),
            statement=value["statement"],
            source_start=int(value["source_start"]),
            source_end=int(value["source_end"]),
            state=AtomState(value["state"]),
            requires_human_confirmation=bool(value["requires_human_confirmation"]),
            extraction_method=value.get("extraction_method", "rules_v1"),
            semantic_confidence=(
                SemanticConfidence.from_dict(value["semantic_confidence"])
                if "semantic_confidence" in value
                else SemanticConfidence.unassessed()
            ),
        )


class IntentLifecycleError(RuntimeError):
    pass


class IntentExtractor:
    """Conservative local extractor: ambiguous language remains exploration."""

    _segments = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
    _constraint = re.compile(
        r"\b(don't|do not|must not|never|without|avoid|only after|unless)\b", re.I
    )
    _decision = re.compile(
        r"\b(should (?:we|i)|decide|choose|approve|permission|authorize)\b", re.I
    )
    _exploration = re.compile(
        r"\b(maybe|perhaps|explore|consider|wonder|what if|could we|idea)\b", re.I
    )
    _action = re.compile(
        r"\b(i want|please|build|create|implement|add|fix|change|remove|ship|make|start|continue|prepare)\b",
        re.I,
    )

    def extract(self, source: SourceRecord) -> List[IntentAtom]:
        atoms: List[IntentAtom] = []
        for match in self._segments.finditer(source.raw_text):
            raw_segment = match.group(0)
            leading = len(raw_segment) - len(raw_segment.lstrip())
            trailing = len(raw_segment.rstrip())
            statement = raw_segment.strip()
            if not statement:
                continue
            start = match.start() + leading
            end = match.start() + trailing
            kind, confidence = self._classify(statement)
            confirmation = kind in (AtomKind.ACTIONABLE, AtomKind.DECISION_REQUEST)
            atoms.append(
                IntentAtom(
                    atom_id="atom_%s" % uuid4().hex,
                    source_id=source.source_id,
                    kind=kind,
                    statement=statement,
                    source_start=start,
                    source_end=end,
                    state=(
                        AtomState.AWAITING_CONFIRMATION
                        if confirmation
                        else AtomState.PROPOSED
                    ),
                    requires_human_confirmation=confirmation,
                    extraction_method="rules_v2_confidence",
                    semantic_confidence=confidence,
                )
            )
        return atoms

    def _classify(self, statement: str) -> tuple[AtomKind, SemanticConfidence]:
        matches = {
            "action_signal": bool(self._action.search(statement)),
            "constraint_signal": bool(self._constraint.search(statement)),
            "decision_signal": bool(self._decision.search(statement)),
            "exploration_signal": bool(self._exploration.search(statement)),
        }
        signals = tuple(sorted(name for name, matched in matches.items() if matched))
        if matches["constraint_signal"]:
            if matches["exploration_signal"] or matches["decision_signal"]:
                return AtomKind.CONSTRAINT, SemanticConfidence(
                    ConfidenceBand.MEDIUM, 650, signals
                )
            return AtomKind.CONSTRAINT, SemanticConfidence(
                ConfidenceBand.HIGH, 950, signals
            )
        if matches["exploration_signal"]:
            if matches["action_signal"] or matches["decision_signal"]:
                return AtomKind.EXPLORATION, SemanticConfidence(
                    ConfidenceBand.MEDIUM, 500, signals
                )
            return AtomKind.EXPLORATION, SemanticConfidence(
                ConfidenceBand.HIGH, 900, signals
            )
        if matches["decision_signal"]:
            return AtomKind.DECISION_REQUEST, SemanticConfidence(
                ConfidenceBand.HIGH, 900, signals
            )
        if matches["action_signal"]:
            return AtomKind.ACTIONABLE, SemanticConfidence(
                ConfidenceBand.HIGH, 900, signals
            )
        return AtomKind.EXPLORATION, SemanticConfidence(
            ConfidenceBand.LOW, 200, ("no_decisive_signal",)
        )


class IntentLifecycle:
    def __init__(self, store: AppendOnlyEventStore) -> None:
        self.store = store

    def propose(self, atom: IntentAtom) -> Event:
        if self.store.events_for(atom.atom_id):
            raise IntentLifecycleError("atom %s is already proposed" % atom.atom_id)
        return self.store.append(
            atom.atom_id,
            "atom.proposed",
            atom.to_dict(),
            causation_id=atom.source_id,
        )

    def current(self, atom_id: str) -> IntentAtom:
        events = self.store.events_for(atom_id)
        if not events or events[0].event_type != "atom.proposed":
            raise IntentLifecycleError("unknown atom %s" % atom_id)
        atom = IntentAtom.from_dict(events[0].payload)
        for event in events[1:]:
            if event.event_type == "atom.confirmed":
                atom = replace(atom, state=AtomState.CONFIRMED)
            elif event.event_type == "atom.rejected":
                atom = replace(atom, state=AtomState.REJECTED)
            elif event.event_type == "atom.superseded":
                atom = replace(atom, state=AtomState.SUPERSEDED)
            else:
                raise IntentLifecycleError(
                    "unsupported lifecycle event %s" % event.event_type
                )
        return atom

    def confirm(
        self, atom_id: str, *, confirmation: ConfirmationRecord
    ) -> IntentAtom:
        atom = self.current(atom_id)
        if not confirmation.actor_id.strip() or not confirmation.channel.strip():
            raise IntentLifecycleError("confirmation requires actor and channel")
        if confirmation.authority != ConfirmationAuthority.HUMAN:
            raise IntentLifecycleError("only human authority can confirm intent")
        if atom.state != AtomState.AWAITING_CONFIRMATION:
            raise IntentLifecycleError(
                "atom %s is not awaiting confirmation" % atom_id
            )
        self.store.append(
            atom_id,
            "atom.confirmed",
            confirmation.to_dict(),
        )
        return self.current(atom_id)

    def reject(self, atom_id: str, *, actor: str, reason: str) -> IntentAtom:
        atom = self.current(atom_id)
        if atom.state not in (AtomState.PROPOSED, AtomState.AWAITING_CONFIRMATION):
            raise IntentLifecycleError("atom cannot be rejected from %s" % atom.state.value)
        if not actor.strip() or not reason.strip():
            raise IntentLifecycleError("rejection requires actor and reason")
        self.store.append(
            atom_id,
            "atom.rejected",
            {"actor": actor, "reason": reason},
        )
        return self.current(atom_id)

    def actionable_atoms(self) -> Iterable[IntentAtom]:
        atom_ids = {
            event.stream_id
            for event in self.store.read_all()
            if event.event_type == "atom.proposed"
        }
        for atom_id in sorted(atom_ids):
            atom = self.current(atom_id)
            if atom.kind == AtomKind.ACTIONABLE and atom.state == AtomState.CONFIRMED:
                yield atom
