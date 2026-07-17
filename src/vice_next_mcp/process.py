"""Official VICE launch, filesystem isolation, and exact-tree cleanup."""

from __future__ import annotations
import asyncio, contextlib, ctypes, hashlib, os, shutil, signal, socket, subprocess, threading, time, uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from .monitor import BinaryMonitorTransport

SUPPORTED = {
    "c64": "x64sc",
    "c128": "x128",
    "vic20": "xvic",
    "plus4": "xplus4",
    "c16": "xplus4",
    "pet": "xpet",
}
WRITABLE = {".d64", ".d71", ".d81", ".g64", ".g71", ".p64", ".tap"}


class LaunchError(RuntimeError):
    def __init__(self, message, *, details):
        self.details = details
        super().__init__(message)


@dataclass(slots=True)
class Reservation:
    port: int
    sock: socket.socket

    def handoff(self):
        with contextlib.suppress(OSError):
            self.sock.close()


class PortAllocator:
    def __init__(self, host="127.0.0.1"):
        self.host = host
        self._lock = threading.RLock()
        self._claims = set()

    def reserve(self, preferred=0):
        with self._lock:
            for candidate in (range(preferred, 65536) if preferred else (0,)):
                sock = socket.socket()
                try:
                    if os.name == "nt":
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    sock.bind((self.host, candidate))
                    port = sock.getsockname()[1]
                    if port in self._claims:
                        sock.close()
                        continue
                    self._claims.add(port)
                    return Reservation(port, sock)
                except OSError:
                    sock.close()
        raise LaunchError("no free loopback port", details={"preferred": preferred})

    def release(self, item):
        with self._lock:
            item.handoff()
            self._claims.discard(item.port)

    def is_claimed(self, port):
        with self._lock:
            return port in self._claims


@dataclass(frozen=True, slots=True)
class InstancePaths:
    root: Path
    config: Path
    media: Path
    logs: Path
    traces: Path
    screenshots: Path
    crashes: Path

    @classmethod
    def create(cls, base, instance_id, generation):
        root = Path(base).resolve() / instance_id / f"generation-{generation}"
        dirs = [root / x for x in ("config", "media", "logs", "traces", "screenshots", "crashes")]
        for p in dirs:
            p.mkdir(parents=True, exist_ok=False)
        return cls(root, *dirs)

    def isolate_media(self, source, *, shared_read_only=False):
        source = Path(source).resolve(strict=True)
        if shared_read_only:
            if source.suffix.lower() in WRITABLE or source.stat().st_mode & 0o222:
                raise ValueError("shared media is not guaranteed read-only")
            return source
        target = self.media / source.name
        shutil.copy2(source, target)
        return target


@dataclass(slots=True)
class CrashDetails:
    pid: int
    exit_code: int | None
    command: tuple[str, ...]
    stdout_tail: tuple[str, ...]
    stderr_tail: tuple[str, ...]
    executable_sha256: str


@dataclass(slots=True)
class ViceProcess:
    instance_id: str
    generation: int
    machine: str
    command: tuple[str, ...]
    monitor_port: int
    paths: InstancePaths
    process: asyncio.subprocess.Process
    allocator: PortAllocator
    reservation: Reservation
    executable_sha256: str
    stdout_tail: deque = field(default_factory=lambda: deque(maxlen=200))
    stderr_tail: deque = field(default_factory=lambda: deque(maxlen=200))
    pumps: list = field(default_factory=list)

    def details(self):
        return CrashDetails(
            self.process.pid,
            self.process.returncode,
            self.command,
            tuple(self.stdout_tail),
            tuple(self.stderr_tail),
            self.executable_sha256,
        )

    async def stop(self, timeout=5.0):
        try:
            if self.process.returncode is None:
                if os.name == "nt":
                    killer = await asyncio.create_subprocess_exec(
                        "taskkill",
                        "/PID",
                        str(self.process.pid),
                        "/T",
                        "/F",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(killer.wait(), timeout)
                else:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
            return self.details()
        finally:
            self.allocator.release(self.reservation)
            for task in self.pumps:
                task.cancel()
            await asyncio.gather(*self.pumps, return_exceptions=True)


class ProcessController:
    def __init__(self, artifact_root, *, allocator=None):
        self.artifact_root = Path(artifact_root)
        self.allocator = allocator or PortAllocator()

    @staticmethod
    def validate(machine, executable):
        if machine not in SUPPORTED:
            raise ValueError("unsupported machine; choose c64, c128, vic20, plus4, c16, or pet")
        executable = Path(executable).resolve(strict=True)
        if executable.stem.lower() != SUPPORTED[machine]:
            raise ValueError(f"{machine} requires {SUPPORTED[machine]}")
        return executable

    @staticmethod
    def command(executable, port, extra_flags=()):
        if extra_flags:
            raise ValueError("flags require a verified launch profile")
        # These are the exact launch flags proven by the direct-monitor baseline.
        # Do not inherit a user's persistent vice.conf.  A config generated by
        # VICE 3.9 causes a blocking version-mismatch dialog under 3.10.
        return (
            str(executable),
            "-default",
            "-binarymonitor",
            "-binarymonitoraddress",
            f"ip4://127.0.0.1:{port}",
        )

    @staticmethod
    def digest(path):
        h = hashlib.sha256()
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1048576), b""):
                h.update(chunk)
        return h.hexdigest()

    async def launch(
        self,
        machine,
        executable,
        *,
        instance_id=None,
        generation=1,
        preferred_port=0,
        readiness_timeout=10.0,
    ):
        executable = self.validate(machine, executable)
        instance_id = instance_id or str(uuid.uuid4())
        paths = InstancePaths.create(self.artifact_root, instance_id, generation)
        claim = self.allocator.reserve(preferred_port)
        command = self.command(executable, claim.port)
        claim.handoff()
        kwargs = {}
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
        else:
            kwargs["start_new_session"] = True
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=paths.root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=flags,
                **kwargs,
            )
        except BaseException:
            self.allocator.release(claim)
            raise
        item = ViceProcess(
            instance_id,
            generation,
            machine,
            command,
            claim.port,
            paths,
            process,
            self.allocator,
            claim,
            self.digest(executable),
        )
        item.pumps = [
            asyncio.create_task(
                self._pump(process.stdout, item.stdout_tail, paths.logs / "stdout.log")
            ),
            asyncio.create_task(
                self._pump(process.stderr, item.stderr_tail, paths.logs / "stderr.log")
            ),
        ]
        deadline = time.monotonic() + readiness_timeout
        last = None
        while time.monotonic() < deadline:
            if process.returncode is not None:
                await asyncio.gather(*item.pumps, return_exceptions=True)
                details = asdict(item.details())
                self.allocator.release(claim)
                raise LaunchError("VICE exited before readiness", details=details)
            try:
                tx = BinaryMonitorTransport(
                    "127.0.0.1", claim.port, connect_timeout=0.2, request_timeout=0.5
                )
                await tx.connect()
                await tx.negotiate()
                await tx.close()
                return item
            except BaseException as e:
                last = e
                await asyncio.sleep(0.05)
        details = asdict(item.details()) | {"phase": "monitor_readiness", "last_error": repr(last)}
        await item.stop()
        raise LaunchError("VICE readiness timed out", details=details)

    @staticmethod
    async def _pump(stream, tail, destination):
        if stream is None:
            return
        with destination.open("w", encoding="utf-8", errors="replace") as log:
            while data := await stream.readline():
                line = data.decode(errors="replace").rstrip("\r\n")
                tail.append(line)
                log.write(line + "\n")
                log.flush()
