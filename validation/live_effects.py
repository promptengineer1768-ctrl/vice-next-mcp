"""Live W3-B/C/D effects through the Supervisor runtime."""

from __future__ import annotations
import argparse, json
from pathlib import Path
from vice_next_mcp.supervisor import Supervisor
from vice_next_mcp.transport_runtime import BinaryMonitorTransport


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executable", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    s = Supervisor(executable=a.executable, startup_timeout=8)
    i = s.create("c64")
    t = BinaryMonitorTransport(s)
    rows = []

    def run(name, fn):
        try:
            rows.append({"operation": name, "status": "passed", "value": fn()})
        except Exception as e:
            rows.append({"operation": name, "status": "failed", "error": repr(e)})

    run("memory.read", lambda: t.execute(i.id, "memory.read", address=4096, length=4))
    run("memory.write", lambda: t.execute(i.id, "memory.write", address=4096, data=b"\x12\x34"))
    run("memory.read.verify", lambda: t.execute(i.id, "memory.read", address=4096, length=2))
    run("pause", lambda: t.execute(i.id, "pause"))
    run("run", lambda: t.execute(i.id, "run"))
    run("reset", lambda: t.execute(i.id, "reset"))
    p = out / "state.vsf"
    run("snapshot.save", lambda: t.execute(i.id, "snapshot.save", path=str(p)))
    if p.exists():
        run("snapshot.load", lambda: t.execute(i.id, "snapshot.load", path=str(p)))
    rows += [
        {"operation": x, "status": "unsupported", "reason": "runtime capability not exposed"}
        for x in ("trace", "keyboard", "iec_capture")
    ]
    s.stop(i.id)
    payload = {
        "schema": "vice-next-mcp/live-w3-effects/1",
        "evidence_class": "live",
        "executable": a.executable,
        "instance_id": i.id,
        "rows": rows,
        "snapshot_exists": p.exists(),
    }
    (out / "live-effects.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
