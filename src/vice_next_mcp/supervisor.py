from __future__ import annotations
import contextlib, os, socket, struct, subprocess, tempfile, threading, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from .monitor_sync import BinaryMonitor
from .catalog import OPS
from .process import PortAllocator, Reservation


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
    port_reservation: Reservation | None = None
    iec_trace_path: Path | None = None
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
        headless=True,
        artifact_root=None,
    ):
        self.executable = executable
        self.monitor_host = monitor_host
        self.monitor_port = monitor_port
        self.startup_timeout = startup_timeout
        self.workdir = workdir
        self.headless = headless
        self.artifact_root = Path(
            artifact_root or Path(tempfile.gettempdir()) / "vice-next-mcp-artifacts"
        )
        self._allocator = PortAllocator(monitor_host)
        self._instances = {}
        self._lock = threading.RLock()

    def _port(self):
        return self._allocator.reserve(self.monitor_port)

    def create(
        self,
        machine="x64sc",
        *,
        executable=None,
        extra_args=(),
        autostart=None,
        instance_id=None,
        generation=1,
        headless=None,
    ):
        exe = executable or self.executable or machine
        reservation = self._port()
        port = reservation.port
        ident = instance_id or str(uuid.uuid4())
        gen = generation
        # Official VICE accepts the version-2 monitor endpoint as a single URI;
        # the separate legacy address/port switches silently fail on 3.10.
        endpoint = f"ip4://{self.monitor_host}:{port}"
        # ``-default`` is intentional: VICE otherwise loads the user's global
        # vice.conf (often created by an older 3.9 install).  That produces a
        # modal "configuration file version mismatch" dialog before the
        # monitor can come up, making supervised/headless launches flaky.
        # Every experiment is configured through explicit argv/resources, so
        # starting from built-in defaults is both reproducible and version safe.
        use_headless = self.headless if headless is None else bool(headless)
        args = [
            exe,
            "-default",
            "-binarymonitor",
            "-binarymonitoraddress",
            endpoint,
            "-autostartprgmode",
            "1",
            "-console",
        ] + list(extra_args)
        env = os.environ.copy()
        trace_path = None
        if os.environ.get("VICE_MCP_INSTRUMENTED") == "1":
            trace_dir = self.artifact_root / ident / f"generation-{gen}" / "traces"
            trace_dir.mkdir(parents=True, exist_ok=True)
            trace_path = trace_dir / "iec.jsonl"
            env["VICE_IEC_TRACE_FILE"] = str(trace_path)
        if use_headless:
            # SDL's dummy video backend prevents emulator windows from being
            # created while retaining the monitor and emulation core.
            env.setdefault("SDL_VIDEODRIVER", "dummy")
        try:
            reservation.handoff()
            proc = subprocess.Popen(
                args,
                cwd=self.workdir or None,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            self._allocator.release(reservation)
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
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(2)
            if proc.poll() is None:
                proc.kill()
                proc.wait(2)
            self._allocator.release(reservation)
            inst = Instance(ident, gen, machine, proc, None, InstanceState.FAILED)
            self._instances[ident] = inst
            raise TimeoutError("VICE monitor did not start")
        instrumented = {
            "vice.keyboard.matrix",
            "vice.keyboard.restore",
            "vice.iec.observe",
            "vice.iec.capture.start",
            "vice.iec.capture.read",
            "vice.iec.capture.stop",
            "vice.iec.capture.status",
            "vice.c128.timing.sample",
            "vice.vdc.timing.sample",
        }
        supported = set(OPS) - instrumented
        # Instrumented VICE builds advertise the extension explicitly.  Keep
        # stock VICE conservative so callers receive a structured
        # unsupported-capability error instead of a misleading fallback.
        if os.environ.get("VICE_MCP_INSTRUMENTED") == "1":
            supported |= instrumented - {"vice.keyboard.matrix"}
        inst = Instance(
            ident,
            gen,
            machine,
            proc,
            mon,
            InstanceState.RUNNING,
            port_reservation=reservation,
            iec_trace_path=trace_path,
            capabilities=supported
            | {"memory.read", "memory.write", "run", "pause", "reset", "snapshot", "keyboard.feed"},
        )
        self._instances[ident] = inst
        if autostart:
            filename = str(autostart).encode()
            if len(filename) > 0xFF:
                raise ValueError("VICE autostart path must be at most 255 bytes")
            # VICE command $DD is: run byte, uint16 file index, uint8 length,
            # then the filename.  The former three-byte header shifted the
            # length into the file-index field and malformed every request.
            mon.call(0xDD, struct.pack("<BHB", 1, 0, len(filename)) + filename)
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
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(i.process.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                i.process.terminate()
            try:
                i.process.wait(2)
            except subprocess.TimeoutExpired:
                i.process.kill()
                i.process.wait(2)
        if i.port_reservation is not None:
            self._allocator.release(i.port_reservation)
            i.port_reservation = None
        i.state = InstanceState.STOPPED

    def restart(self, instance_id):
        i = self.get(instance_id)
        machine = i.machine
        generation = i.generation + 1
        self.stop(instance_id)
        # Restart preserves the logical instance identity while advancing its
        # generation, so leases and artifact paths can detect stale handles.
        return self.create(machine, instance_id=instance_id, generation=generation)

    def close(self):
        for i in self.list():
            if i.state not in (InstanceState.STOPPED,):
                self.stop(i.id)
