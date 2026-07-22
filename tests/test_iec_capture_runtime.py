import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vice_next_mcp.iec_capture import IECTraceReader


def instance(path: Path):
    return SimpleNamespace(id="instance-1", iec_trace_path=path)


def write_event(path: Path, clock: int, *, partial=False):
    event = {
        "clock": clock,
        "cpu_bus": 255,
        "cpu_port": 255,
        "drv_port": 255,
        "drv_bus": [255] * 16,
        "drv_data": [255] * 16,
        "drive_context": [{"unit": 8, "cycle": clock + 3, "pc": 0xEAA0, "semantic": "receiving"}],
    }
    with path.open("ab") as stream:
        stream.write(json.dumps(event).encode())
        if not partial:
            stream.write(b"\n")


def test_capture_window_is_cycle_stamped_sequenced_and_incremental(tmp_path):
    path = tmp_path / "iec.jsonl"
    write_event(path, 1)
    reader = IECTraceReader()
    target = instance(path)
    reader.start(target)
    write_event(path, 20)
    write_event(path, 25)

    first = reader.read(target, limit=1)
    second = reader.stop(target)

    assert [x["host_cycle"] for x in first["events"]] == [20]
    assert [x["sequence"] for x in first["events"] + second["events"]] == [1, 2]
    assert first["events"][0]["drive_cycles_available"] is True
    assert first["events"][0]["host_drive_cycles"] == [
        {"unit": 8, "host_cycle": 20, "drive_cycle": 23}
    ]
    assert second["active"] is False


def test_partial_record_is_not_claimed_complete(tmp_path):
    path = tmp_path / "iec.jsonl"
    path.touch()
    reader = IECTraceReader()
    target = instance(path)
    reader.start(target)
    write_event(path, 10, partial=True)

    result = reader.read(target)

    assert result["events"] == []
    assert result["complete"] is False


def test_capture_rejects_uninstrumented_instance():
    with pytest.raises(RuntimeError, match="not launched"):
        IECTraceReader().start(SimpleNamespace(id="stock", iec_trace_path=None))
