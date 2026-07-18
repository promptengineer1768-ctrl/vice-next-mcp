"""Contracts for the binary-monitor RESTORE/NMI extension."""

from __future__ import annotations

import pytest

from vice_next_mcp.monitor_sync import BinaryMonitor, Response


def _monitor_with_response(response: Response, expected_body: bytes) -> BinaryMonitor:
    """Return a monitor whose command response is deterministic."""
    monitor = object.__new__(BinaryMonitor)

    def call(command: int, body: bytes = b"") -> Response:
        assert command == 0x74
        assert body == expected_body
        return response

    monitor.call = call  # type: ignore[method-assign]
    return monitor


def test_restore_uses_one_byte_native_state_protocol() -> None:
    """RESTORE press is distinct from keyboard matrix coordinates."""
    response = Response(0x74, 0, 1, b"\x01")
    monitor = _monitor_with_response(response, b"\x01")
    monitor.keyboard_restore(True)


def test_restore_rejects_acknowledgement_without_effect_state() -> None:
    """An empty old-monitor reply cannot be mistaken for a real NMI event."""
    monitor = _monitor_with_response(Response(0x74, 0, 1, b""), b"\x01")
    with pytest.raises(RuntimeError, match="invalid acknowledgement"):
        monitor.keyboard_restore(True)
