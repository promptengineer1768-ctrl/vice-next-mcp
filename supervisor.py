from __future__ import annotations
import os, socket, subprocess, tempfile, threading, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from .monitor import BinaryMonitor


class InstanceState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class Instance:
    id: str
    generation: int
    machine: str
    process: subprocess.Popen | None
    monitor: BinaryMonitor | None
    state: InstanceState = InstanceState.STARTING
    lease_token: str | None = None
    created: float = field(default_factory=time.time)
    capabilities: set[str] = field(
        default_factory=lambda: {"memory.read", "memory.write", "run", "pause", "reset", "snapshot"}
    )


class InstanceLease:
    def __init__(self, supervisor: "Supervisor", instance_id: str, token: str):
        self._s = supervisor
        self.instance_id = instance_id
        self.token = token
        self.released = False

    @property
    def instance(self):
        return self._s.get(self.instance_id)

    def release(self):
        if not self.released:
            self._s.release(self)
            self.released = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()


class Supervisor:
    def __init__(
        self,
        executable: str | None = None,
        monitor_host="127.0.0.1",
        monitor_port=0,
        startup_timeout=8.0,
        workdir=None,
    ):
        self.executable = executable
        self.monitor_host = monitor_host
        self.monitor_port = monitor_port
        self.startup_timeout = startup_timeout
        self.workdir = workdir
        self._instances = {}
        self._lock = threading.RLock()

    def _port(self):
        if self.monitor_port:
            return self.monitor_port
        s = socket.socket()
        s.bind((self.monitor_host, 0))
        p = s.getsockname()[1]
        s.close()
        return p

    def create(self, machine="x64sc", *, executable=None, extra_args=(), autostart=None):
        exe = executable or self.executable or machine
        port = self._port()
        ident = str(uuid.uuid4())
        gen = 1
        args = [
            exe,
            "-binarymonitor",
            "-binarymonitoraddress",
            self.monitor_host,
            "-binarymonitorport",
            str(port),
            "-autostartprgmode",
            "1",
            "-console",
        ] + list(extra_args)
        try:
            proc = subprocess.Popen(
                args, cwd=self.workdir or None, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except OSError:
            inst = Instance(ident, gen, machine, None, None, InstanceState.FAILED)
            self._instances[ident] = inst
            raise
        deadline = time.monotonic() + self.startup_timeout
        mon = None
        while time.monotonic() < deadline and proc.poll() is None:
            try:
                mon = BinaryMonitor(self.monitor_host, port)
                mon.ping()
                break
            except OSError:
                time.sleep(0.05)
            except Exception:
                time.sleep(0.05)
        if mon is None:
            proc.terminate()
            inst = Instance(ident, gen, machine, proc, None, InstanceState.FAILED)
            self._instances[ident] = inst
            raise TimeoutError("VICE monitor did not start")
        inst = Instance(ident, gen, machine, proc, mon, InstanceState.RUNNING)
        self._instances[ident] = inst
        if autostart:
            mon.call(0xDD, bytes((1, 0, len(str(autostart).encode()))) + str(autostart).encode())
        return inst

    # ``start`` is the explicit lifecycle spelling used by the CLI and MCP.
    start = create

    def get(self, instance_id):
        with self._lock:
            if instance_id not in self._instances:
                raise KeyError(instance_id)
            return self._instances[instance_id]

    def list(self):
        return list(self._instances.values())

    def describe(self, instance_id):
        i = self.get(instance_id)
        return {
            "id": i.id,
            "generation": i.generation,
            "machine": i.machine,
            "state": i.state.value,
            "leased": bool(i.lease_token),
            "capabilities": sorted(i.capabilities),
        }

    def lease(self, instance_id):
        with self._lock:
            i = self.get(instance_id)
            if i.lease_token:
                raise RuntimeError("instance already leased")
            t = uuid.uuid4().hex
            i.lease_token = t
            return InstanceLease(self, instance_id, t)

    def release(self, lease):
        with self._lock:
            i = self.get(lease.instance_id)
            if i.lease_token != lease.token:
                raise RuntimeError("invalid lease")
            i.lease_token = None

    def stop(self, instance_id, *, kill=False):
        i = self.get(instance_id)
        if i.monitor:
            try:
                i.monitor.close()
            except Exception:
                pass
        if i.process and i.process.poll() is None:
            i.process.terminate()
            try:
                i.process.wait(2)
            except subprocess.TimeoutExpired:
                i.process.kill()
        i.state = InstanceState.STOPPED

    def restart(self, instance_id):
        i = self.get(instance_id)
        machine = i.machine
        self.stop(instance_id)
        return self.create(machine)

    def close(self):
        for i in self.list():
            if i.state not in (InstanceState.STOPPED,):
                self.stop(i.id)
