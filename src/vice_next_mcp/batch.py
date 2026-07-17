"""Deterministic, isolated experiment matrix runner (no third party dependencies)."""

from __future__ import annotations
import csv, hashlib, json, os, re, socket, time, uuid, threading, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Iterable

_PORT_LOCK = threading.Lock()
_RESERVED_PORTS: set[int] = set()


def case_id(case: dict[str, Any]) -> str:
    raw = json.dumps(case, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:80] or "case"


def allocate_ports(base: int | None, count: int, occupied: Iterable[int] = ()) -> list[int]:
    """Atomically reserve ports across concurrent supervisors.

    Reservations remain held until ``release_ports`` is called, preventing the
    classic find-free/close/reuse race between supervisors.
    """
    with _PORT_LOCK:
        used = set(occupied) | _RESERVED_PORTS
        out = []
        sockets = []
        try:
            for i in range(count):
                preferred = (base + i) if base else 0
                for p in range(preferred, 65536) if preferred else [0]:
                    s = socket.socket()
                    (
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                        if os.name == "nt"
                        else None
                    )
                    try:
                        s.bind(("127.0.0.1", p))
                        actual = s.getsockname()[1]
                    except OSError:
                        s.close()
                        continue
                    if actual in used:
                        s.close()
                        continue
                    used.add(actual)
                    out.append(actual)
                    sockets.append(s)
                    break
                else:
                    raise RuntimeError("no free ports")
            _RESERVED_PORTS.update(out)
            return out
        finally:
            for s in sockets:
                s.close()


def release_ports(ports: Iterable[int]) -> None:
    with _PORT_LOCK:
        for port in ports:
            _RESERVED_PORTS.discard(int(port))


@dataclass
class CaseResult:
    case_id: str
    status: str
    artifact_dir: str
    duration_ms: int
    provenance: dict[str, Any]
    error: str | None = None
    serial_reproduction: str | None = None


class BatchRunner:
    def __init__(
        self, artifact_root: str | Path, *, workers: int = 1, base_port: int | None = None
    ):
        self.root = Path(artifact_root)
        self.workers = max(1, int(workers))
        self.base_port = base_port

    def run(
        self,
        cases: Iterable[dict[str, Any]],
        execute: Callable[[dict[str, Any], Path, int], dict[str, Any] | None],
        *,
        fail_fast=False,
        cancel: threading.Event | None = None,
    ) -> dict[str, Any]:
        run_id = uuid.uuid4().hex
        root = self.root / run_id
        root.mkdir(parents=True, exist_ok=True)
        items = []
        for c in cases:
            cid = case_id(c)
            d = root / f"{sanitize(cid)}"
            d.mkdir()
            items.append((c, cid, d))
        ports = allocate_ports(self.base_port, len(items))
        results = []

        def one(index_item):
            index, (c, cid, d) = index_item
            started = time.monotonic()
            prov = {
                "run_id": run_id,
                "case_id": cid,
                "command": c.get("command"),
                "machine": c.get("machine"),
                "variant": c.get("variant"),
                "port": ports[index],
            }
            if cancel and cancel.is_set():
                return CaseResult(
                    cid,
                    "cancelled",
                    str(d),
                    0,
                    prov,
                    "cancelled before start",
                    f"pytest -n 0 {c.get('nodeid','')}",
                )
            try:
                extra = execute(c, d, ports[index])
                prov.update(extra or {})
                return CaseResult(
                    cid, "passed", str(d), int((time.monotonic() - started) * 1000), prov
                )
            except Exception as e:
                return CaseResult(
                    cid,
                    "failed",
                    str(d),
                    int((time.monotonic() - started) * 1000),
                    prov,
                    repr(e),
                    f"pytest -n 0 {c.get('nodeid','')}",
                )

        try:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futs = [pool.submit(one, x) for x in enumerate(items)]
                for f in as_completed(futs):
                    r = f.result()
                    results.append(r)
                    if fail_fast and r.status == "failed":
                        if cancel:
                            cancel.set()
                        for x in futs:
                            x.cancel()
        finally:
            release_ports(ports)
        results.sort(key=lambda r: r.case_id)
        payload = {
            "run_id": run_id,
            "results": [asdict(r) for r in results],
            "progress": {"terminal": len(results), "total": len(items)},
        }
        (root / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        with (root / "results.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "status", "artifact_dir", "duration_ms"])
            w.writeheader()
            [w.writerow({k: getattr(r, k) for k in w.fieldnames}) for r in results]
        return payload
