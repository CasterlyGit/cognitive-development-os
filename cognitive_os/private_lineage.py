from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Dict, Optional, Tuple

from .data_policy import PrivateDataPolicy, RawRetentionMode
from .intents import AtomKind, AtomState, IntentAtom, IntentExtractor, SemanticConfidence
from .models import SourceKind, SourceRecord, utc_now
from .store import (
    AppendOnlyEventStore,
    DuplicateEventError,
    StreamRevisionError,
)


class PrivateLineageError(RuntimeError):
    """Raised when private content and structural lineage cannot be reconciled."""


class PrivateContentUnavailable(PrivateLineageError):
    """Raised when session-only content is no longer available."""


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PrivateLineageError("%s must be a lowercase SHA-256 digest" % label)
    return value


def _require_exact_keys(value: Any, expected: set[str], label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise PrivateLineageError("%s must be an object" % label)
    actual = set(value)
    if actual != expected:
        raise PrivateLineageError(
            "%s fields differ: missing=%s unexpected=%s"
            % (
                label,
                sorted(str(key) for key in expected - actual),
                sorted(str(key) for key in actual - expected),
            )
        )
    return value


@dataclass(frozen=True)
class StructuralSourceRecord:
    source_id: str
    kind: SourceKind
    captured_at: str
    content_sha256: str
    content_length: int
    retention_mode: RawRetentionMode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "2.0",
            "source_id": self.source_id,
            "kind": self.kind.value,
            "captured_at": self.captured_at,
            "content_sha256": self.content_sha256,
            "content_length": self.content_length,
            "retention_mode": self.retention_mode.value,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "StructuralSourceRecord":
        try:
            value = _require_exact_keys(
                value,
                {
                    "schema_version",
                    "source_id",
                    "kind",
                    "captured_at",
                    "content_sha256",
                    "content_length",
                    "retention_mode",
                },
                "structural source record",
            )
            if value["schema_version"] != "2.0":
                raise ValueError("unsupported schema version")
            source_id = value["source_id"]
            captured_at = value["captured_at"]
            if not isinstance(source_id, str) or not source_id.strip():
                raise TypeError("source_id must be a non-empty string")
            if not isinstance(captured_at, str) or not captured_at.strip():
                raise TypeError("captured_at must be a non-empty string")
            content_length = value["content_length"]
            if (
                isinstance(content_length, bool)
                or not isinstance(content_length, int)
                or content_length <= 0
            ):
                raise TypeError("content_length must be a positive integer")
            return cls(
                source_id=source_id,
                kind=SourceKind(value["kind"]),
                captured_at=captured_at,
                content_sha256=_require_digest(
                    value["content_sha256"], "content_sha256"
                ),
                content_length=content_length,
                retention_mode=RawRetentionMode(value["retention_mode"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PrivateLineageError(
                "invalid structural source record: %s" % exc
            ) from exc


@dataclass(frozen=True)
class StructuralIntentAtom:
    atom_id: str
    source_id: str
    kind: AtomKind
    source_start: int
    source_end: int
    statement_sha256: str
    state: AtomState
    requires_human_confirmation: bool
    extraction_method: str
    semantic_confidence: SemanticConfidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "2.0",
            "atom_id": self.atom_id,
            "source_id": self.source_id,
            "kind": self.kind.value,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "statement_sha256": self.statement_sha256,
            "state": self.state.value,
            "requires_human_confirmation": self.requires_human_confirmation,
            "extraction_method": self.extraction_method,
            "semantic_confidence": self.semantic_confidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "StructuralIntentAtom":
        try:
            value = _require_exact_keys(
                value,
                {
                    "schema_version",
                    "atom_id",
                    "source_id",
                    "kind",
                    "source_start",
                    "source_end",
                    "statement_sha256",
                    "state",
                    "requires_human_confirmation",
                    "extraction_method",
                    "semantic_confidence",
                },
                "structural intent atom",
            )
            if value["schema_version"] != "2.0":
                raise ValueError("unsupported schema version")
            atom_id = value["atom_id"]
            source_id = value["source_id"]
            extraction_method = value["extraction_method"]
            for label, resolved in (
                ("atom_id", atom_id),
                ("source_id", source_id),
                ("extraction_method", extraction_method),
            ):
                if not isinstance(resolved, str) or not resolved.strip():
                    raise TypeError("%s must be a non-empty string" % label)
            source_start = value["source_start"]
            source_end = value["source_end"]
            if (
                isinstance(source_start, bool)
                or not isinstance(source_start, int)
                or isinstance(source_end, bool)
                or not isinstance(source_end, int)
                or source_start < 0
                or source_end <= source_start
            ):
                raise ValueError("source span is invalid")
            confirmation = value["requires_human_confirmation"]
            if not isinstance(confirmation, bool):
                raise TypeError("requires_human_confirmation must be boolean")
            confidence = _require_exact_keys(
                value["semantic_confidence"],
                {"band", "score_millis", "signals"},
                "semantic confidence",
            )
            score = confidence["score_millis"]
            signals = confidence["signals"]
            if isinstance(score, bool) or not isinstance(score, int):
                raise TypeError("semantic confidence score_millis must be an integer")
            if not isinstance(signals, list) or any(
                not isinstance(signal, str) for signal in signals
            ):
                raise TypeError("semantic confidence signals must be a string array")
            return cls(
                atom_id=atom_id,
                source_id=source_id,
                kind=AtomKind(value["kind"]),
                source_start=source_start,
                source_end=source_end,
                statement_sha256=_require_digest(
                    value["statement_sha256"], "statement_sha256"
                ),
                state=AtomState(value["state"]),
                requires_human_confirmation=confirmation,
                extraction_method=extraction_method,
                semantic_confidence=SemanticConfidence.from_dict(confidence),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PrivateLineageError(
                "invalid structural intent atom: %s" % exc
            ) from exc


@dataclass(frozen=True)
class PrivateLineageSnapshot:
    sources: Dict[str, StructuralSourceRecord]
    atoms: Dict[str, StructuralIntentAtom]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sources": [
                self.sources[source_id].to_dict()
                for source_id in sorted(self.sources)
            ],
            "atoms": [
                self.atoms[atom_id].to_dict() for atom_id in sorted(self.atoms)
            ],
        }


class SessionContentVault:
    """Process-local raw content. Clearing drops references, not secure memory."""

    def __init__(self) -> None:
        self._sources: Dict[str, SourceRecord] = {}

    def put(self, source: SourceRecord) -> SourceRecord:
        if not isinstance(source, SourceRecord):
            raise PrivateLineageError("session vault accepts SourceRecord values only")
        if _digest_text(source.raw_text) != source.content_sha256:
            raise PrivateLineageError("session content digest mismatch")
        existing = self._sources.get(source.source_id)
        if existing is not None and existing != source:
            raise PrivateLineageError("session source identifier has conflicting content")
        self._sources[source.source_id] = source
        return source

    def get(self, source_id: str) -> SourceRecord:
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise PrivateContentUnavailable(
                "session-only content is unavailable for %s" % source_id
            ) from exc

    def clear(self) -> int:
        removed = len(self._sources)
        self._sources.clear()
        return removed


class PrivateLineageSession:
    """Session-only content with restart-safe structural source/atom lineage."""

    SOURCE_EVENT = "private_source.captured_v2"
    ATOM_EVENT = "private_atom.proposed_v2"

    def __init__(
        self,
        store: AppendOnlyEventStore,
        vault: SessionContentVault,
        policy: PrivateDataPolicy,
    ) -> None:
        self.store = store
        self.vault = vault
        self.policy = policy.validated()
        if self.policy.raw_retention != RawRetentionMode.SESSION_ONLY:
            raise PrivateLineageError(
                "this v2 slice implements session-only content; persistence is gated"
            )
        if len(self.policy.project_ids) != 1:
            raise PrivateLineageError(
                "this v2 slice requires the single-project default"
            )

    def capture(
        self,
        raw_text: str,
        *,
        kind: SourceKind = SourceKind.CHAT,
        metadata: Optional[Dict[str, str]] = None,
        source_id: str,
    ) -> SourceRecord:
        if (
            not isinstance(raw_text, str)
            or not raw_text.strip()
            or not isinstance(source_id, str)
            or not source_id.strip()
            or source_id != source_id.strip()
        ):
            raise PrivateLineageError(
                "raw_text must be non-empty and source_id must be exact"
            )
        if not isinstance(kind, SourceKind):
            raise PrivateLineageError("kind must be a SourceKind")
        if metadata is not None and not isinstance(metadata, dict):
            raise PrivateLineageError("session metadata must be an object")
        resolved_metadata = dict(metadata or {})
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in resolved_metadata.items()
        ):
            raise PrivateLineageError("session metadata must contain string pairs")
        content_sha256 = _digest_text(raw_text)
        existing = self._source_descriptor(source_id)
        if existing is not None:
            if (
                existing.kind != kind
                or existing.content_sha256 != content_sha256
                or existing.content_length != len(raw_text)
                or existing.retention_mode != RawRetentionMode.SESSION_ONLY
            ):
                raise PrivateLineageError(
                    "source_id already identifies different structural content"
                )
            return self.vault.put(
                SourceRecord(
                    source_id=source_id,
                    kind=kind,
                    raw_text=raw_text,
                    captured_at=existing.captured_at,
                    content_sha256=content_sha256,
                    metadata=resolved_metadata,
                )
            )
        descriptor = StructuralSourceRecord(
            source_id=source_id,
            kind=kind,
            captured_at=utc_now(),
            content_sha256=content_sha256,
            content_length=len(raw_text),
            retention_mode=RawRetentionMode.SESSION_ONLY,
        )
        try:
            self.store.append(
                source_id,
                self.SOURCE_EVENT,
                descriptor.to_dict(),
                event_id=self._event_id(self.SOURCE_EVENT, source_id),
                expected_stream_revision=0,
            )
        except (DuplicateEventError, StreamRevisionError):
            winner = self._source_descriptor(source_id)
            if (
                winner is None
                or winner.kind != kind
                or winner.content_sha256 != content_sha256
                or winner.content_length != len(raw_text)
                or winner.retention_mode != RawRetentionMode.SESSION_ONLY
            ):
                raise PrivateLineageError(
                    "concurrent source capture has conflicting structural content"
                )
            descriptor = winner
        return self.vault.put(
            SourceRecord(
                source_id=source_id,
                kind=kind,
                raw_text=raw_text,
                captured_at=descriptor.captured_at,
                content_sha256=content_sha256,
                metadata=resolved_metadata,
            )
        )

    def extract_and_record(self, source_id: str) -> Tuple[IntentAtom, ...]:
        source = self.materialize_source(source_id)
        atoms = tuple(IntentExtractor().extract(source))
        for atom in atoms:
            descriptor = StructuralIntentAtom(
                atom_id=atom.atom_id,
                source_id=atom.source_id,
                kind=atom.kind,
                source_start=atom.source_start,
                source_end=atom.source_end,
                statement_sha256=_digest_text(atom.statement),
                state=atom.state,
                requires_human_confirmation=atom.requires_human_confirmation,
                extraction_method=atom.extraction_method,
                semantic_confidence=atom.semantic_confidence,
            )
            self._append_atom_once(descriptor)
        return atoms

    def snapshot(self) -> PrivateLineageSnapshot:
        sources: Dict[str, StructuralSourceRecord] = {}
        atoms: Dict[str, StructuralIntentAtom] = {}
        for event in self.store.read_all():
            if event.event_type == self.SOURCE_EVENT:
                descriptor = StructuralSourceRecord.from_dict(event.payload)
                if event.stream_id != descriptor.source_id or descriptor.source_id in sources:
                    raise PrivateLineageError("duplicate or misrouted structural source")
                sources[descriptor.source_id] = descriptor
            elif event.event_type == self.ATOM_EVENT:
                descriptor = StructuralIntentAtom.from_dict(event.payload)
                if event.stream_id != descriptor.atom_id or descriptor.atom_id in atoms:
                    raise PrivateLineageError("duplicate or misrouted structural atom")
                atoms[descriptor.atom_id] = descriptor
            elif event.event_type.startswith("private_"):
                raise PrivateLineageError(
                    "unsupported private lineage event type %s" % event.event_type
                )
        for atom in atoms.values():
            if atom.source_id not in sources:
                raise PrivateLineageError("structural atom references a missing source")
            if atom.source_end > sources[atom.source_id].content_length:
                raise PrivateLineageError("structural atom span exceeds source length")
        return PrivateLineageSnapshot(sources=sources, atoms=atoms)

    def materialize_source(self, source_id: str) -> SourceRecord:
        descriptor = self._source_descriptor(source_id)
        if descriptor is None:
            raise PrivateLineageError("unknown structural source %s" % source_id)
        source = self.vault.get(source_id)
        if (
            source.kind != descriptor.kind
            or source.captured_at != descriptor.captured_at
            or source.content_sha256 != descriptor.content_sha256
            or len(source.raw_text) != descriptor.content_length
            or _digest_text(source.raw_text) != descriptor.content_sha256
        ):
            raise PrivateLineageError("session content does not match structural lineage")
        return source

    def materialize_atom(self, atom_id: str) -> IntentAtom:
        descriptor = self.snapshot().atoms.get(atom_id)
        if descriptor is None:
            raise PrivateLineageError("unknown structural atom %s" % atom_id)
        source = self.materialize_source(descriptor.source_id)
        if descriptor.source_end > len(source.raw_text):
            raise PrivateLineageError("structural atom span exceeds source content")
        statement = source.raw_text[descriptor.source_start : descriptor.source_end]
        if _digest_text(statement) != descriptor.statement_sha256:
            raise PrivateLineageError("structural atom statement digest mismatch")
        return IntentAtom(
            atom_id=descriptor.atom_id,
            source_id=descriptor.source_id,
            kind=descriptor.kind,
            statement=statement,
            source_start=descriptor.source_start,
            source_end=descriptor.source_end,
            state=descriptor.state,
            requires_human_confirmation=descriptor.requires_human_confirmation,
            extraction_method=descriptor.extraction_method,
            semantic_confidence=descriptor.semantic_confidence,
        )

    def end_session(self) -> int:
        return self.vault.clear()

    def _source_descriptor(
        self, source_id: str
    ) -> Optional[StructuralSourceRecord]:
        events = self.store.events_for(source_id)
        if not events:
            return None
        if len(events) != 1 or events[0].event_type != self.SOURCE_EVENT:
            raise PrivateLineageError("source stream contains ambiguous history")
        descriptor = StructuralSourceRecord.from_dict(events[0].payload)
        if descriptor.source_id != source_id:
            raise PrivateLineageError("source event is routed to the wrong stream")
        return descriptor

    def _append_atom_once(self, descriptor: StructuralIntentAtom) -> None:
        events = self.store.events_for(descriptor.atom_id)
        if events:
            if (
                len(events) == 1
                and events[0].event_type == self.ATOM_EVENT
                and events[0].payload == descriptor.to_dict()
            ):
                return
            raise PrivateLineageError("atom stream contains conflicting history")
        try:
            self.store.append(
                descriptor.atom_id,
                self.ATOM_EVENT,
                descriptor.to_dict(),
                event_id=self._event_id(self.ATOM_EVENT, descriptor.atom_id),
                causation_id=descriptor.source_id,
                expected_stream_revision=0,
            )
        except (DuplicateEventError, StreamRevisionError):
            events = self.store.events_for(descriptor.atom_id)
            if (
                len(events) != 1
                or events[0].event_type != self.ATOM_EVENT
                or events[0].payload != descriptor.to_dict()
            ):
                raise PrivateLineageError(
                    "concurrent atom proposal has conflicting structural content"
                )

    @staticmethod
    def _event_id(event_type: str, stream_id: str) -> str:
        identity = (event_type + ":" + stream_id).encode("utf-8")
        return "private_v2_%s" % hashlib.sha256(identity).hexdigest()
