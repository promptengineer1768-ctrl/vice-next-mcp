"""Per-instance reader for the instrumented VICE IEC JSONL recorder."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CaptureSession:
    capture_id: str
    path: Path
    offset: int
    sequence: int = 0
    active: bool = True
    malformed_records: int = 0
    pending: bytes = field(default_factory=bytes)


class IECTraceReader:
    """Own logical capture windows over a recorder opened when VICE starts."""

    def __init__(self):
        self._sessions: dict[str, CaptureSession] = {}
        self._lock = threading.RLock()

    def start(self, instance) -> dict:
        path = getattr(instance, "iec_trace_path", None)
        if path is None:
            raise RuntimeError("instance was not launched with instrumented IEC recording")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        with self._lock:
            previous = self._sessions.get(instance.id)
            if previous and previous.active:
                raise RuntimeError("an IEC capture is already active for this instance")
            session = CaptureSession(uuid.uuid4().hex, path, path.stat().st_size)
            self._sessions[instance.id] = session
            return self._status(session)

    def read(self, instance, *, limit: int = 1000) -> dict:
        with self._lock:
            session = self._session(instance)
            events = self._drain(session, limit)
            return {**self._status(session), "events": events}

    def observe(self, instance) -> dict:
        path = getattr(instance, "iec_trace_path", None)
        if path is None or not Path(path).exists():
            raise RuntimeError("instance has no instrumented IEC trace")
        last = None
        with Path(path).open("rb") as stream:
            for raw in stream:
                try:
                    last = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
        if last is None:
            raise RuntimeError("instrumented IEC trace contains no complete event")
        return self._normalize(last, None)

    def stop(self, instance, *, limit: int = 10000) -> dict:
        with self._lock:
            session = self._session(instance)
            events = self._drain(session, limit)
            session.active = False
            return {**self._status(session), "events": events}

    def status(self, instance) -> dict:
        with self._lock:
            return self._status(self._session(instance))

    def _session(self, instance) -> CaptureSession:
        session = self._sessions.get(instance.id)
        if session is None:
            raise RuntimeError("no IEC capture has been started for this instance")
        return session

    def _drain(self, session: CaptureSession, limit: int) -> list[dict]:
        if limit < 1:
            return []
        with session.path.open("rb") as stream:
            stream.seek(session.offset)
            chunk = stream.read()
            session.offset = stream.tell()
        data = session.pending + chunk
        lines = data.split(b"\n")
        session.pending = lines.pop()
        events = []
        consumed = 0
        for index, raw in enumerate(lines):
            if len(events) >= limit:
                remainder = b"\n".join(lines[index:])
                session.pending = remainder + b"\n" + session.pending
                break
            consumed += 1
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                session.malformed_records += 1
                continue
            session.sequence += 1
            events.append(self._normalize(event, session.sequence))
        return events

    @staticmethod
    def _normalize(event: dict, sequence: int | None) -> dict:
        result = dict(event)
        if sequence is not None:
            result["sequence"] = sequence
        result["host_cycle"] = result.get("clock")
        result["drive_cycles_available"] = any(
            isinstance(item, dict) and item.get("cycle") is not None
            for item in result.get("drive_context", [])
        )
        return result

    @staticmethod
    def _status(session: CaptureSession) -> dict:
        return {
            "capture_id": session.capture_id,
            "active": session.active,
            "path": str(session.path),
            "next_sequence": session.sequence + 1,
            "malformed_records": session.malformed_records,
            "source_overflow_supported": False,
            "complete": session.malformed_records == 0 and not session.pending,
        }
