"""Wave 3 effect-based validation for keyboard, snapshots/traces, and I/O capture.

These tests exercise observable artifacts/events rather than merely response shapes.
"""

import json
import struct

from vice_next_mcp.keyboard import KeyboardAction, KeyboardQueue
from vice_next_mcp.capture import IECapture, IOCapture, MemoryCapture
from vice_next_mcp.snapshot import fingerprint, validate_snapshot, SnapshotError
from vice_next_mcp.trace import TraceWriter


def test_w3b_keyboard_effects_and_cancel(tmp_path):
    q = KeyboardQueue("C128")
    q.enqueue(
        [
            KeyboardAction("press", "A"),
            KeyboardAction("release", "A"),
            KeyboardAction("restore", "RESTORE"),
            KeyboardAction("release", "RESTORE"),
        ]
    )
    ev = q.tick(4, running=True)
    assert [e["kind"] for e in ev] == ["press", "release", "restore", "release"]
    assert q.status()["held"] == []
    q.enqueue([KeyboardAction("hold", "SHIFT", frames=100)])
    q.cancel()
    assert q.status()["pending"] == 0 and q.status()["held"] == []


def test_w3b_long_sequence_no_drop_or_duplicate():
    q = KeyboardQueue()
    actions = [KeyboardAction("press", str(i % 10)) for i in range(1000)]
    q.enqueue(actions)
    result = q.drain()
    assert result.completed == 1000
    assert len(q.events) == 1000


def test_w3c_snapshot_roundtrip_and_fingerprint_rejection(tmp_path):
    p = tmp_path / "state.vsf"
    # Minimal structurally valid VSF with one module.
    p.write_bytes(b"VICE Snapshot File" + b"C64MEM\0\0" + b"\0" * 4 + struct.pack("<I", 3) + b"abc")
    info = validate_snapshot(p, required_modules=("C64MEM",))
    assert info["fingerprint"] == fingerprint(p)
    before = info["fingerprint"]
    p.write_bytes(p.read_bytes() + b"x")
    assert fingerprint(p) != before
    try:
        validate_snapshot(tmp_path / "wrong.bin")
    except SnapshotError:
        pass
    else:
        raise AssertionError("missing snapshot accepted")


def test_w3c_trace_nonempty_events_and_order(tmp_path):
    p = tmp_path / "trace.jsonl"
    t = TraceWriter(p, metadata={"machine": "C64"})
    t.start()
    t.event({"cycle": 10, "address": 0xA000, "registers": {"pc": 0x1234}})
    out = t.stop()
    assert out["event_count"] == 1 and out["size"] > 0
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    assert rows[0]["type"] == "trace_start" and rows[-1]["type"] == "trace_stop"
    assert rows[1]["cycle"] == 10


def test_w3d_io_timestamps_driver_attribution_and_memory_comparison(tmp_path):
    c = IOCapture(addresses={0xDD00}, memspaces={"cpu"})
    c.start()
    c.record(100, "write", 0xDD00, 1, "cpu")
    c.record(101, "write", 0xD000, 2, "cpu")
    assert len(c.export()) == 1 and c.events[0].cycle == 100
    iec = IECapture()
    iec.start()
    iec.line(120, clk=0, data=1, drivers={"host": {"clk": 0}})
    row = iec.export()[0]
    assert row["cycle"] == 120 and row["details"]["details"]["drivers"]["host"]["clk"] == 0
    mem = MemoryCapture(addresses={0x1000})
    mem.start()
    mem.sample(200, 0x1000, 0x55)
    # REU fixed-address sampling observes the same value; cycle is retained for alias analysis.
    assert mem.export()[0]["value"] == 0x55
    (tmp_path / "io.json").write_text(
        json.dumps({"io": c.export(), "iec": iec.export(), "reu": mem.export()})
    )
