from dataclasses import dataclass, asdict
import json


@dataclass
class CaptureEvent:
    cycle: int
    kind: str
    address: int | None = None
    value: int | None = None
    memspace: str = "cpu"
    details: dict | None = None


class IOCapture:
    def __init__(self, addresses=None, memspaces=None):
        self.addresses = set(addresses or [])
        self.memspaces = set(memspaces or [])
        self.events = []
        self.active = False

    def start(self):
        self.active = True
        return {"active": True}

    def stop(self):
        self.active = False
        return {"active": False, "events": len(self.events)}

    def record(self, cycle, kind, address=None, value=None, memspace="cpu", **details):
        if (
            self.active
            and (not self.addresses or address in self.addresses)
            and (not self.memspaces or memspace in self.memspaces)
        ):
            self.events.append(CaptureEvent(cycle, kind, address, value, memspace, details or None))

    def export(self, path=None):
        d = [asdict(e) for e in self.events]
        if path:
            open(path, "w", encoding="utf-8").write(json.dumps(d, indent=2))
        return d


class IECapture(IOCapture):
    def line(self, cycle, atn=None, clk=None, data=None, srq=None, drivers=None, **kw):
        self.record(
            cycle,
            "line",
            details={
                "atn": atn,
                "clk": clk,
                "data": data,
                "srq": srq,
                "drivers": drivers or {},
                **kw,
            },
        )


@dataclass
class DriveState:
    device: int
    model: str
    cycle: int = 0
    registers: dict | None = None
    via: dict | None = None
    iec: dict | None = None


class MemoryCapture(IOCapture):
    def sample(self, cycle, address, value, memspace="cpu"):
        self.record(cycle, "sample", address, value, memspace)


class ClockSync:
    def __init__(self):
        self.points = []

    def add(self, host_cycle, drive_cycle):
        self.points.append((host_cycle, drive_cycle))

    def correlate(self, host_cycle):
        if not self.points:
            return None
        h, d = self.points[-1]
        return d + host_cycle - h
