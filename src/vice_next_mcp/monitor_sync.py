"""Minimal binary-monitor v2 client used by the runtime package."""

from __future__ import annotations
import socket, struct, threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Response:
    command: int
    error: int
    request_id: int
    body: bytes


class BinaryMonitor:
    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.socket = socket.create_connection((host, port), timeout)
        self.socket.settimeout(timeout)
        self.timeout = timeout
        self._id = 0
        self._lock = threading.Lock()
        self.events = []

    def close(self):
        self.socket.close()

    def _exact(self, n):
        b = bytearray()
        while len(b) < n:
            x = self.socket.recv(n - len(b))
            if not x:
                raise ConnectionError("VICE monitor closed")
            b.extend(x)
        return bytes(b)

    def call(self, command, body=b""):
        with self._lock:
            self._id = (self._id + 1) & 0xFFFFFFFF
            rid = self._id
            self.socket.sendall(
                b"\x02\x02" + struct.pack("<II", len(body), rid) + bytes((command,)) + body
            )
            while True:
                h = self._exact(12)
                if h[:2] != b"\x02\x02":
                    raise RuntimeError("invalid monitor header")
                n = struct.unpack_from("<I", h, 2)[0]
                r = Response(h[6], h[7], struct.unpack_from("<I", h, 8)[0], self._exact(n))
                if r.request_id == 0xFFFFFFFF:
                    self.events.append(r)
                    continue
                if r.request_id != rid:
                    raise RuntimeError("request id mismatch")
                if r.error:
                    raise RuntimeError(f"VICE command {command:#x} failed: {r.error:#x}")
                return r

    def ping(self):
        self.call(0x81)

    def memory(self, start, length, memspace=0, bank=0):
        end = (start + length - 1) & 0xFFFF
        b = self.call(1, struct.pack("<BHHBH", 0, start & 0xFFFF, end, memspace, bank)).body
        n = struct.unpack_from("<H", b)[0] or 65536
        return b[2 : 2 + n]

    def memory_write(self, start, data, memspace=0, bank=0):
        end = (start + len(data) - 1) & 0xFFFF
        self.call(2, struct.pack("<BHHBH", 0, start & 0xFFFF, end, memspace, bank) + data)

    def resume(self):
        self.call(0xAA)

    def step_instruction(self, count: int = 1):
        """Execute exactly ``count`` CPU instructions while paused.

        Binary-monitor command ``0x71`` is CPU-neutral and therefore works
        for both the Z80 (C128) and 6502-family CPUs (C64/VIC-20/Plus4/PET).
        VICE leaves the monitor paused after each command.
        """
        count = int(count)
        if not 1 <= count <= 100000:
            raise ValueError("instruction count must be in 1..100000")
        for _ in range(count):
            self.call(0x71)
        return {"count": count, "command": "0x71", "execution_state": "paused"}

    def step_over(self, count: int = 1):
        """Step over instruction(s) using VICE's CPU-neutral single-step.

        The binary monitor has no separate source-level ``next`` primitive;
        this operation intentionally uses instruction stepping, preserving a
        deterministic and truthful contract for Z80 and 6502 targets.
        """
        result = self.step_instruction(count)
        return {**result, "over": True}

    def reset(self, target=0):
        self.call(0xCC, bytes((target,)))

    def keyboard_feed(self, data):
        """Feed PETSCII bytes through VICE's documented keyboard buffer API.

        This is deliberately named *feed*, not matrix input: VICE's binary
        monitor exposes no row/column key transition command.  Keeping this
        distinction prevents a KERNAL/keyboard-buffer operation from being
        reported as physical matrix evidence.
        """
        data = bytes(data)
        if len(data) > 255:
            raise ValueError("keyboard feed is limited to 255 bytes")
        self.call(0x72, bytes((len(data),)) + data)

    def keyboard_matrix(self, row: int, column: int, pressed: bool):
        """Reject matrix input until its distinct monitor extension exists."""
        if not -5 <= int(row) <= 15 or not 0 <= int(column) <= 7:
            raise ValueError("keyboard matrix coordinates out of range")
        raise RuntimeError(
            "VICE binary monitor has no matrix-input command; "
            "RESTORE uses its own 0x74 extension"
        )

    def keyboard_restore(self, pressed: bool) -> None:
        """Assert or release the native RESTORE/NMI source (extension 0x74)."""
        response = self.call(0x74, bytes((int(bool(pressed)),)))
        expected = bytes((int(bool(pressed)),))
        if response.body != expected:
            raise RuntimeError("VICE RESTORE command returned an invalid acknowledgement")

    def dump(self, path):
        p = str(path).encode()
        self.call(0x41, bytes((1, 1, len(p))) + p)

    def undump(self, path):
        p = str(path).encode()
        return self.call(0x42, bytes((len(p),)) + p).body
