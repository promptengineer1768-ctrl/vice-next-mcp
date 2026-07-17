import pytest

from vice_next_mcp.snapshot import SnapshotError, ensure_path, validate_snapshot
from vice_next_mcp.trace import TraceError, TraceWriter


def test_trace_requires_readable_event(tmp_path):
    writer = TraceWriter(tmp_path / "trace.jsonl")
    writer.start()
    with pytest.raises(TraceError):
        writer.stop()


def test_trace_round_trip(tmp_path):
    writer = TraceWriter(tmp_path / "trace.jsonl")
    started = writer.start()
    writer.event({"cycle": 12, "address": 0xDD00})
    result = writer.stop()
    assert started["trace_id"]
    assert result["event_count"] == 1
    assert result["size"] > 0


def test_snapshot_requires_structural_magic_and_confines_path(tmp_path):
    bad = tmp_path / "bad.vsf"
    bad.write_bytes(b"not a snapshot")
    with pytest.raises(SnapshotError):
        validate_snapshot(bad)
    with pytest.raises(SnapshotError):
        ensure_path(tmp_path.parent / "escape.vsf", tmp_path)
