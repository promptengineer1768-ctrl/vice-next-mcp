from __future__ import annotations
from dataclasses import dataclass
from .supervisor import Supervisor, InstanceLease
from .iec_capture import IECTraceReader


@dataclass(frozen=True)
class OperationEvidence:
    operation: str
    instance_id: str
    generation: int
    state: str
    effect: dict


class BinaryMonitorTransport:
    def __init__(self, supervisor: Supervisor):
        self.supervisor = supervisor
        self.iec = IECTraceReader()

    @staticmethod
    def _memspace(value):
        return {"cpu": 0, "drive8": 1, "drive9": 2, "drive10": 3, "drive11": 4}.get(value, value)

    def execute(self, instance_id, operation, **params):
        i = self.supervisor.get(instance_id)
        m = i.monitor
        if not m:
            raise RuntimeError("instance has no live monitor")
        memspace = self._memspace(params.get("memspace", 0))
        if operation == "memory.read":
            result = m.memory(
                int(params["address"]),
                int(params["length"]),
                int(memspace),
                int(params.get("bank", 0)),
            )
        elif operation == "memory.write":
            result = m.memory_write(
                int(params["address"]),
                bytes(params["data"]),
                int(memspace),
                int(params.get("bank", 0)),
            )
        elif operation == "registers.get":
            result = m.registers(int(memspace))
        elif operation == "registers.set":
            result = m.registers_set(params["values"], int(memspace))
        elif operation == "run":
            m.resume()
            i.state = "running"
            result = None
        elif operation == "pause":
            m.ping()
            i.state = "paused"
            result = None
        elif operation == "step.instruction":
            result = m.step_instruction(int(params.get("count", 1)))
            i.state = "paused"
        elif operation == "step.over":
            result = m.step_over(int(params.get("count", 1)))
            i.state = "paused"
        elif operation == "reset":
            result = m.reset(int(params.get("target", 0)))
        elif operation == "snapshot.save":
            result = m.dump(params["path"])
        elif operation == "snapshot.load":
            result = m.undump(params["path"])
        elif operation == "iec.observe":
            result = self.iec.observe(i)
        elif operation == "iec.capture.start":
            result = self.iec.start(i)
        elif operation == "iec.capture.read":
            result = self.iec.read(
                i, limit=int(params.get("limit", 1000)), capture_id=params.get("capture_id")
            )
        elif operation == "iec.capture.stop":
            result = self.iec.stop(
                i, limit=int(params.get("limit", 10000)), capture_id=params.get("capture_id")
            )
        elif operation == "iec.capture.status":
            result = self.iec.status(i, capture_id=params.get("capture_id"))
        elif operation == "c128.timing.sample":
            raise RuntimeError(
                "instrumented VICE event bridge is not connected to this monitor session"
            )
        else:
            raise ValueError(f"unknown operation {operation}")
        return {
            "result": result,
            "evidence": OperationEvidence(
                operation, i.id, i.generation, i.state, {"command": operation}
            ).__dict__,
        }

    def keyboard_type(self, instance_id: str, text: str):
        """Feed PETSCII through VICE's official binary-monitor keyboard API."""
        if not isinstance(text, str) or len(text) > 255:
            raise ValueError("text must contain at most 255 characters")
        i = self.supervisor.get(instance_id)
        # The monitor consumes PETSCII keyboard-buffer bytes, not host newline
        # bytes.  Translate line feeds so ``keyboard.type("RUN\\n")`` behaves
        # like pressing RETURN on a C64, matching the public MCP contract.
        data = bytes(0x0D if ch == "\n" else ord(ch) & 0x7F for ch in text)
        i.monitor.keyboard_feed(data)
        return {
            "result": {"count": len(data), "mode": "vice-binary-keyboard-feed"},
            "evidence": OperationEvidence(
                "keyboard.type",
                i.id,
                i.generation,
                i.state,
                {
                    "monitor_command": "0x72",
                    "api_version": 2,
                    "physical_matrix": False,
                    "compatibility_shadow": False,
                    "count": len(data),
                },
            ).__dict__,
        }

    def keyboard_matrix(
        self, instance_id: str, *, row: int, column: int, action: str = "press", frames: int = 1
    ):
        """Set a physical cell through the instrumented VICE monitor."""
        if not 0 <= int(row) <= 7 or not 0 <= int(column) <= 7:
            raise ValueError("matrix row and column must be in 0..7")
        if action not in {"press", "release", "hold"}:
            raise ValueError("matrix action must be press, release, or hold")
        i = self.supervisor.get(instance_id)
        if "vice.keyboard.matrix" not in i.capabilities:
            raise RuntimeError(
                "native VICE matrix injection is unavailable; instrumented VICE is required"
            )
        pressed = action in {"press", "hold"}
        for _ in range(int(frames)):
            i.monitor.keyboard_matrix(row, column, pressed)
        return {
            "result": {
                "row": int(row),
                "column": int(column),
                "action": action,
                "frames": int(frames),
            },
            "evidence": OperationEvidence(
                "keyboard.matrix",
                i.id,
                i.generation,
                i.state,
                {"monitor_command": "0x74", "physical_matrix": True},
            ).__dict__,
        }

    def keyboard_restore(self, instance_id: str, *, action: str):
        if action not in {"press", "release"}:
            raise ValueError("RESTORE action must be press or release")
        i = self.supervisor.get(instance_id)
        if "vice.keyboard.restore" not in i.capabilities:
            raise RuntimeError(
                "native VICE RESTORE injection is unavailable; instrumented VICE is required"
            )
        i.monitor.keyboard_restore(action == "press")
        return {
            "result": {"action": action},
            "evidence": OperationEvidence(
                "keyboard.restore",
                i.id,
                i.generation,
                i.state,
                {"monitor_command": "0x74", "physical_restore": True},
            ).__dict__,
        }
