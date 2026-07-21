"""Contracts for the binary-monitor RESTORE/NMI extension."""

from __future__ import annotations

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


def test_restore_uses_native_matrix_pseudo_cell() -> None:
    """RESTORE uses the documented negative-row physical matrix cell."""
    response = Response(0x74, 0, 1, b"")
    monitor = _monitor_with_response(response, b"\xfd\x00\x01")
    monitor.keyboard_restore(True)


def test_keyboard_matrix_uses_signed_row_payload() -> None:
    monitor = _monitor_with_response(Response(0x74, 0, 1, b""), b"\x03\x07\x00")
    monitor.keyboard_matrix(3, 7, False)
