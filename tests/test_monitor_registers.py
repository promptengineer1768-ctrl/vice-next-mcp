import struct
import os

import pytest

from vice_next_mcp.monitor_sync import BinaryMonitor, Response
from vice_next_mcp.supervisor import Supervisor


def monitor_with_responses(responses):
    monitor = object.__new__(BinaryMonitor)
    pending = iter(responses)
    monitor.call = lambda command, body=b"": next(pending)(command, body)
    return monitor


def available(command, body):
    assert (command, body) == (0x83, b"\x00")
    items = bytes((4, 0, 8, 1)) + b"A" + bytes((5, 3, 16, 2)) + b"PC"
    return Response(command, 0, 1, struct.pack("<H", 2) + items)


def test_registers_discovers_ids_and_decodes_values():
    def values(command, body):
        assert (command, body) == (0x31, b"\x00")
        return Response(command, 0, 2, b"\x02\x00\x03\x00\x2a\x00\x03\x03\x34\x12")

    monitor = monitor_with_responses((available, values))
    assert monitor.registers() == {"A": 0x2A, "PC": 0x1234}


def test_registers_set_uses_discovered_id_and_reads_back():
    def set_value(command, body):
        assert command == 0x32
        assert body == b"\x00\x01\x00\x03\x03\x00\x20"
        return Response(command, 0, 2, b"")

    def values(command, body):
        assert (command, body) == (0x31, b"\x00")
        return Response(command, 0, 3, b"\x02\x00\x03\x00\x00\x00\x03\x03\x00\x20")

    monitor = monitor_with_responses((available, set_value, available, values))
    assert monitor.registers_set({"PC": 0x2000}) == {"PC": 0x2000}


def test_registers_set_rejects_unknown_name():
    monitor = monitor_with_responses((available,))
    with pytest.raises(ValueError, match="unknown VICE register"):
        monitor.registers_set({"NOPE": 1})


def test_keyboard_restore_uses_native_press_release_protocol():
    def press(command, body):
        assert (command, body) == (0x74, b"\x01")
        return Response(command, 0, 1, b"\x01")

    def release(command, body):
        assert (command, body) == (0x74, b"\x00")
        return Response(command, 0, 2, b"\x00")

    monitor = monitor_with_responses((press, release))
    monitor.keyboard_restore(True)
    monitor.keyboard_restore(False)


def test_keyboard_matrix_has_no_restore_command_alias():
    with pytest.raises(RuntimeError, match="no keyboard-matrix command"):
        monitor_with_responses(()).keyboard_matrix(3, 0, True)


@pytest.mark.live
def test_official_vice_register_roundtrip():
    executable = os.environ.get("VICE_X64SC")
    if not executable or not os.path.isfile(executable):
        pytest.skip("official x64sc unavailable")
    supervisor = Supervisor(executable)
    instance = supervisor.create("x64sc")
    try:
        before = instance.monitor.registers()
        assert {"A", "X", "Y", "PC"} <= before.keys()
        expected = before["A"] ^ 0x5A
        assert instance.monitor.registers_set({"A": expected})["A"] == expected
        instance.monitor.registers_set({"A": before["A"]})
    finally:
        supervisor.close()
