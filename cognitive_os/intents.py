from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        value["state"] = self.state.value
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
            kind = self._classify(statement)
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
                )
            )
        return atoms

    def _classify(self, statement: str) -> AtomKind:
        if self._constraint.search(statement):
            return AtomKind.CONSTRAINT
        if self._decision.search(statement):
            return AtomKind.DECISION_REQUEST
        if self._exploration.search(statement):
            return AtomKind.EXPLORATION
        if self._action.search(statement):
            return AtomKind.ACTIONABLE
        return AtomKind.EXPLORATION


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
        event = self.store.append(
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
