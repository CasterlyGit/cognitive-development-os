from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from .models import Event, SourceKind, SourceRecord, utc_now


class StoreError(RuntimeError):
    """Base error for event-store invariant failures."""


class CorruptStoreError(StoreError):
    pass


class DuplicateEventError(StoreError):
    pass


class StreamRevisionError(StoreError):
    def __init__(self, stream_id: str, expected: int, actual: int) -> None:
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            "stream %s revision changed: expected %d, actual %d"
            % (stream_id, expected, actual)
        )


class AppendOnlyEventStore:
    """A single-file JSONL ledger with process-safe, fsynced appends."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read_all(self) -> List[Event]:
        if not self.path.exists():
            return []
        events: List[Event] = []
        seen_ids = set()
        with self.path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        raise CorruptStoreError("blank ledger line at %d" % line_number)
                    try:
                        event = Event.from_dict(json.loads(line))
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        raise CorruptStoreError(
                            "invalid ledger event at line %d: %s" % (line_number, exc)
                        ) from exc
                    if event.sequence != line_number:
                        raise CorruptStoreError(
                            "non-monotonic sequence at line %d: got %d"
                            % (line_number, event.sequence)
                        )
                    if event.event_id in seen_ids:
                        raise CorruptStoreError("duplicate event_id %s" % event.event_id)
                    seen_ids.add(event.event_id)
                    events.append(event)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return events

    def append(
        self,
        stream_id: str,
        event_type: str,
        payload: Dict[str, Any],
        *,
        event_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        expected_stream_revision: Optional[int] = None,
    ) -> Event:
        if not stream_id.strip() or not event_type.strip():
            raise ValueError("stream_id and event_type must be non-empty")
        if expected_stream_revision is not None and (
            isinstance(expected_stream_revision, bool)
            or not isinstance(expected_stream_revision, int)
            or expected_stream_revision < 0
        ):
            raise ValueError("expected_stream_revision must be a non-negative integer")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        resolved_event_id = event_id or str(uuid4())
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.seek(0)
                lines = handle.readlines()
                existing = []
                for index, line in enumerate(lines, start=1):
                    try:
                        parsed = Event.from_dict(json.loads(line))
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        raise CorruptStoreError(
                            "cannot append after corrupt line %d: %s" % (index, exc)
                        ) from exc
                    if parsed.sequence != index:
                        raise CorruptStoreError("cannot append after invalid sequence")
                    existing.append(parsed)
                if expected_stream_revision is not None:
                    actual_stream_revision = sum(
                        item.stream_id == stream_id for item in existing
                    )
                    if actual_stream_revision != expected_stream_revision:
                        raise StreamRevisionError(
                            stream_id,
                            expected_stream_revision,
                            actual_stream_revision,
                        )
                if any(item.event_id == resolved_event_id for item in existing):
                    raise DuplicateEventError(resolved_event_id)
                event = Event(
                    event_id=resolved_event_id,
                    sequence=len(existing) + 1,
                    stream_id=stream_id,
                    event_type=event_type,
                    occurred_at=utc_now(),
                    payload=payload,
                    causation_id=causation_id,
                )
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                return event
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def events_for(self, stream_id: str) -> List[Event]:
        return [event for event in self.read_all() if event.stream_id == stream_id]


class IntentInbox:
    def __init__(self, store: AppendOnlyEventStore) -> None:
        self.store = store

    def capture(
        self,
        raw_text: str,
        *,
        kind: SourceKind = SourceKind.CHAT,
        metadata: Optional[Dict[str, str]] = None,
        source_id: Optional[str] = None,
    ) -> SourceRecord:
        if not raw_text.strip():
            raise ValueError("raw_text must contain non-whitespace content")
        record = SourceRecord(
            source_id=source_id or "src_%s" % uuid4().hex,
            kind=kind,
            raw_text=raw_text,
            captured_at=utc_now(),
            content_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            metadata=dict(metadata or {}),
        )
        self.store.append(
            stream_id=record.source_id,
            event_type="source.captured",
            payload=record.to_dict(),
        )
        return record

    def sources(self) -> Iterable[SourceRecord]:
        for event in self.store.read_all():
            if event.event_type == "source.captured":
                yield SourceRecord.from_dict(event.payload)
