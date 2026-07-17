"""100k live supervised memory operations across isolated VICE instances."""

import argparse, hashlib, json, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from vice_next_mcp.supervisor import Supervisor
from vice_next_mcp.transport_runtime import BinaryMonitorTransport


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executable", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--operations", type=int, default=100000)
    a = ap.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    each = max(1, a.operations // a.workers)
    rows = []
    lock = threading.Lock()

    def worker(index):
        s = Supervisor(a.executable)
        i = s.create("x64sc")
        t = BinaryMonitorTransport(s)
        passed = 0
        try:
            for n in range(each):
                address = 0x4000 + ((n * 4 + index * 0x100) & 0x1FFF)
                value = bytes(((index + n) & 255, (n >> 8) & 255, 0xA5, 0x5A))
                t.execute(i.id, "memory.write", address=address, data=value)
                got = t.execute(i.id, "memory.read", address=address, length=4)["result"]
                passed += got == value
            row = {
                "index": index,
                "instance_id": i.id,
                "pid": i.process.pid,
                "operations": each * 2,
                "passed_reads": passed,
                "status": "passed" if passed == each else "failed",
                "evidence": "live",
            }
            with lock:
                rows.append(row)
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        list(pool.map(worker, range(a.workers)))
    payload = {
        "schema": "vice-next-mcp/live-randomized-isolation/1",
        "evidence_class": "live",
        "executable": a.executable,
        "executable_sha256": hashlib.sha256(Path(a.executable).read_bytes()).hexdigest(),
        "requested_operations": a.operations,
        "workers": a.workers,
        "rows": sorted(rows, key=lambda x: x["index"]),
        "status": "passed" if all(x["status"] == "passed" for x in rows) else "failed",
    }
    (out / "live-randomized-isolation.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
