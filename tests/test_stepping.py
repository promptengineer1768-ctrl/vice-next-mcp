from vice_next_mcp.monitor_sync import BinaryMonitor


def fake_monitor(monkeypatch):
    monitor = object.__new__(BinaryMonitor)
    calls = []
    monkeypatch.setattr(monitor, "call", lambda command, body=b"": calls.append((command, body)))
    return monitor, calls


def test_instruction_step_repeats_cpu_neutral_command(monkeypatch):
    monitor, calls = fake_monitor(monkeypatch)
    assert monitor.step_instruction(3) == {
        "count": 3,
        "command": "0x71",
        "execution_state": "paused",
    }
    assert [command for command, _ in calls] == [0x71, 0x71, 0x71]


def test_step_over_uses_same_primitive_for_z80_and_6502(monkeypatch):
    monitor, calls = fake_monitor(monkeypatch)
    assert monitor.step_over(2)["over"] is True
    assert [command for command, _ in calls] == [0x71, 0x71]


def test_step_count_is_bounded(monkeypatch):
    monitor, _ = fake_monitor(monkeypatch)
    for value in (0, 100001):
        try:
            monitor.step_instruction(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid count accepted")
