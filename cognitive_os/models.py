from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SourceKind(str, Enum):
    CHAT = "chat"
    VOICE_TRANSCRIPT = "voice_transcript"
    NOTE = "note"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    kind: SourceKind
    raw_text: str
    captured_at: str
    content_sha256: str
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        return value

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "SourceRecord":
        return cls(
            source_id=value["source_id"],
            kind=SourceKind(value["kind"]),
            raw_text=value["raw_text"],
            captured_at=value["captured_at"],
            content_sha256=value["content_sha256"],
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class Event:
    event_id: str
    sequence: int
    stream_id: str
    event_type: str
    occurred_at: str
    payload: Dict[str, Any]
    causation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Event":
        return cls(
            event_id=value["event_id"],
            sequence=int(value["sequence"]),
            stream_id=value["stream_id"],
            event_type=value["event_type"],
            occurred_at=value["occurred_at"],
            payload=dict(value["payload"]),
            causation_id=value.get("causation_id"),
        )


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str = ""


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
