"""Minimal binary-monitor v2 client used by the runtime package."""

from __future__ import annotations
import socket, struct, threading, zlib
from dataclasses import dataclass
from pathlib import Path


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

    @staticmethod
    def _items(body: bytes):
        """Yield size-prefixed binary-monitor array items."""
        if len(body) < 2:
            raise RuntimeError("truncated VICE monitor item array")
        count = struct.unpack_from("<H", body)[0]
        offset = 2
        for _ in range(count):
            if offset >= len(body):
                raise RuntimeError("truncated VICE monitor item size")
            size = body[offset]
            offset += 1
            end = offset + size
            if size == 0 or end > len(body):
                raise RuntimeError("invalid VICE monitor item size")
            yield body[offset:end]
            offset = end
        if offset != len(body):
            raise RuntimeError("unexpected trailing VICE monitor item data")

    def registers_available(self, memspace: int = 0):
        """Return register metadata reported by official monitor command $83."""
        result = []
        for item in self._items(self.call(0x83, bytes((memspace,))).body):
            if len(item) < 3 or len(item) != 3 + item[2]:
                raise RuntimeError("invalid VICE register-description item")
            result.append(
                {
                    "id": item[0],
                    "bits": item[1],
                    "name": item[3:].decode("ascii"),
                }
            )
        return result

    def registers(self, memspace: int = 0):
        """Return named register values from official monitor command $31."""
        metadata = {item["id"]: item for item in self.registers_available(memspace)}
        values = {}
        for item in self._items(self.call(0x31, bytes((memspace,))).body):
            if len(item) < 2:
                raise RuntimeError("invalid VICE register-value item")
            register_id = item[0]
            if register_id not in metadata:
                raise RuntimeError(f"VICE returned unknown register id {register_id}")
            values[metadata[register_id]["name"]] = int.from_bytes(item[1:], "little")
        return values

    def registers_set(self, values, memspace: int = 0):
        """Set named registers with $32 and return VICE's read-back values."""
        metadata = {item["name"].upper(): item for item in self.registers_available(memspace)}
        body = bytearray((memspace,))
        body.extend(struct.pack("<H", len(values)))
        for name, value in values.items():
            key = str(name).upper()
            if key not in metadata:
                raise ValueError(f"unknown VICE register {name!r}")
            bits = int(metadata[key]["bits"])
            if bits > 16 or not 0 <= int(value) < (1 << bits):
                raise ValueError(f"value for VICE register {name!r} does not fit {bits} bits")
            body.extend((3, int(metadata[key]["id"])))
            body.extend(struct.pack("<H", int(value)))
        response = self.call(0x32, bytes(body))
        # $32 uses the same register response layout as $31. Decode the
        # response when supplied, otherwise perform the contractually useful
        # read-back explicitly.
        if response.body:
            by_id = {item["id"]: item for item in metadata.values()}
            readback = {}
            for item in self._items(response.body):
                readback[by_id[item[0]]["name"]] = int.from_bytes(item[1:], "little")
            return readback
        current = self.registers(memspace)
        return {
            metadata[str(name).upper()]["name"]: current[metadata[str(name).upper()]["name"]]
            for name in values
        }

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
        """Set one native VICE keyboard-matrix cell (monitor command $74)."""
        if not -5 <= int(row) <= 15 or not 0 <= int(column) <= 7:
            raise ValueError("keyboard matrix coordinates out of range")
        self.call(0x74, struct.pack("<bBB", int(row), int(column), int(bool(pressed))))

    def keyboard_restore(self, pressed: bool) -> None:
        """Assert or release RESTORE through its native matrix pseudo-cell."""
        self.keyboard_matrix(-3, 0, pressed)

    def screenshot_png(self, path: str | Path, *, include_border: bool = True) -> Path:
        """Capture VICE's indexed display and encode it as a portable PNG."""
        display = self.call(0x84, bytes((0, 0))).body
        info_size = struct.unpack_from("<I", display)[0]
        if info_size != 13 or len(display) < 21:
            raise RuntimeError("invalid VICE display response")
        width, height, x, y, inner_width, inner_height = struct.unpack_from("<6H", display, 4)
        depth = display[16]
        length = struct.unpack_from("<I", display, 17)[0]
        pixels = display[21 : 21 + length]
        if depth != 8 or len(pixels) != width * height:
            raise RuntimeError("unsupported VICE display format")
        palette = self.call(0x91, b"\x00").body
        rgb = [item for item in self._items(palette)]
        if not include_border:
            rows = [pixels[(y + row) * width + x : (y + row) * width + x + inner_width] for row in range(inner_height)]
            width, height, pixels = inner_width, inner_height, b"".join(rows)
        raw = b"".join(b"\0" + bytes(component for index in pixels[row * width : (row + 1) * width] for component in rgb[index]) for row in range(height))
        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        result = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(result)
        return output

    def dump(self, path):
        p = str(path).encode()
        self.call(0x41, bytes((1, 1, len(p))) + p)

    def undump(self, path):
        p = str(path).encode()
        return self.call(0x42, bytes((len(p),)) + p).body
