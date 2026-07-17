"""Live supervised multi-instance isolation check."""

from __future__ import annotations
import argparse, hashlib, json, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from vice_next_mcp.supervisor import Supervisor
from vice_next_mcp.transport_runtime import BinaryMonitorTransport


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executable", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    rows = []

    def one(index):
        s = Supervisor(a.executable)
        i = s.create("x64sc")
        lease = s.lease(i.id)
        t = BinaryMonitorTransport(s)
        address = 0x2000 + index * 4
        value = bytes((index, 0xA5, index ^ 0xFF, 0x5A))
        try:
            t.execute(i.id, "memory.write", address=address, data=value)
            read = t.execute(i.id, "memory.read", address=address, length=4)["result"]
            row = {
                "index": index,
                "instance_id": i.id,
                "pid": i.process.pid,
                "port": i.monitor.socket.getpeername()[1],
                "address": address,
                "readback": list(read),
                "isolated": read == value,
                "evidence": "live-supervisor",
            }
            with lock:
                rows.append(row)
            return row
        finally:
            lease.release()
            s.close()

    started = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        list(pool.map(one, range(a.workers)))
    payload = {
        "schema": "vice-next-mcp/live-supervisor-soak/1",
        "evidence_class": "live",
        "executable": a.executable,
        "executable_sha256": hashlib.sha256(Path(a.executable).read_bytes()).hexdigest(),
        "workers": a.workers,
        "elapsed_ms": int((time.time() - started) * 1000),
        "rows": sorted(rows, key=lambda x: x["index"]),
        "status": (
            "passed" if len(rows) == a.workers and all(r["isolated"] for r in rows) else "failed"
        ),
    }
    (out / "live-supervisor-soak.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
