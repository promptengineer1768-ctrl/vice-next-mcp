from dataclasses import dataclass
from collections import deque
from typing import Any


@dataclass(frozen=True)
class KeyboardAction:
    kind: str
    value: object = None
    frames: int = 1
    modifiers: tuple[str, ...] = ()


@dataclass
class KeyboardResult:
    accepted: int
    completed: int
    cancelled: bool
    stuck_keys: list[str]
    acknowledgement: str


class KeyboardQueue:
    def __init__(self, machine: str = "C64", frame: int = 0) -> None:
        self.machine = machine.upper()
        self.frame = frame
        self._q: deque[tuple[int, KeyboardAction]] = deque()
        self._held: set[str] = set()
        self.events: list[dict[str, Any]] = []

    def enqueue(
        self, actions: list[KeyboardAction | dict[str, Any]], start_frame: int | None = None
    ) -> str:
        f = self.frame if start_frame is None else max(self.frame, start_frame)
        for a in actions:
            if isinstance(a, dict):
                a = KeyboardAction(**a)
            self._q.append((f, a))
            f += max(0, a.frames)
        return "kbd-" + str(len(self.events) + len(self._q))

    def tick(
        self, frames: int = 1, running: bool = True, warp: bool = False
    ) -> list[dict[str, Any]]:
        self.frame += max(0, frames)
        out: list[dict[str, Any]] = []
        if not running:
            return out
        while self._q and self._q[0][0] <= self.frame:
            at, a = self._q.popleft()
            k = a.kind.lower()
            key = str(a.value)
            if k in ("press", "matrix_press", "restore", "hold"):
                self._held.add(key)
            elif k in ("release", "matrix_release"):
                self._held.discard(key)
            out.append(
                {
                    "frame": self.frame,
                    "scheduled_frame": at,
                    "kind": k,
                    "value": a.value,
                    "modifiers": list(a.modifiers),
                    "machine": self.machine,
                    "warp": warp,
                }
            )
        self.events.extend(out)
        return out

    def cancel(self) -> None:
        self._q.clear()
        self._held.clear()

    def status(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "pending": len(self._q),
            "held": sorted(self._held),
            "machine": self.machine,
        }

    def drain(self, max_frames: int = 10000, running: bool = True) -> KeyboardResult:
        n = len(self.events)
        target = self.frame + max_frames
        while self._q and self.frame < target:
            self.tick(1, running=running)
        c = bool(self._q)
        if c:
            self.cancel()
        d = len(self.events) - n
        return KeyboardResult(d, d, c, sorted(self._held), "drained" if not c else "timeout")
