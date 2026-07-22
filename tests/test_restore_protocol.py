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


def test_restore_uses_one_byte_effect_protocol() -> None:
    """RESTORE requires the rebuilt VICE state echo after NMI assertion."""
    response = Response(0x74, 0, 1, b"\x01")
    monitor = _monitor_with_response(response, b"\x01")
    monitor.keyboard_restore(True)


def test_restore_rejects_legacy_empty_success() -> None:
    """The pre-fix binary's empty success cannot be accepted as NMI evidence."""
    monitor = _monitor_with_response(Response(0x74, 0, 1, b""), b"\x01")
    with pytest.raises(RuntimeError, match="did not acknowledge"):
        monitor.keyboard_restore(True)


def test_keyboard_matrix_is_not_aliased_to_restore_command() -> None:
    """Matrix injection remains unavailable until assigned another command."""
    monitor = object.__new__(BinaryMonitor)
    with pytest.raises(RuntimeError, match="no keyboard-matrix command"):
        monitor.keyboard_matrix(3, 7, False)
