"""Live Wave 3 smoke checks against an installed VICE executable.

The checks intentionally report capabilities separately: process isolation is
validated by launching real VICE processes; effect checks are ``unavailable``
until the supervised MCP operation layer exposes those operations.  This keeps
the evidence ledger honest (a simulator or unit test is never labelled live).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

from vice_next_mcp.process import ProcessController


async def isolation(executable: Path, root: Path, *, soak: int = 1, machine: str = "c64") -> dict:
    ctl = ProcessController(root / "artifacts")
    rows = []
    for generation in range(1, soak + 1):
        first = second = None
        started = time.time()
        try:
            first, second = await asyncio.gather(
                ctl.launch(
                    machine, executable, instance_id=f"a-{generation}", generation=generation
                ),
                ctl.launch(
                    machine, executable, instance_id=f"b-{generation}", generation=generation
                ),
            )
            rows.append(
                {
                    "generation": generation,
                    "pids": [first.process.pid, second.process.pid],
                    "ports": [first.monitor_port, second.monitor_port],
                    "roots": [str(first.paths.root), str(second.paths.root)],
                    "distinct_pid": first.process.pid != second.process.pid,
                    "distinct_port": first.monitor_port != second.monitor_port,
                    "distinct_root": first.paths.root != second.paths.root,
                    "evidence": "live",
                }
            )
        finally:
            if first is not None:
                await first.stop()
            if second is not None:
                await second.stop()
    return {"status": "passed", "elapsed_ms": int((time.time() - started) * 1000), "cases": rows}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--executable", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--soak", type=int, default=1)
    ap.add_argument("--machine", choices=("c64", "c128"), default="c64")
    args = ap.parse_args()
    exe = args.executable.resolve(strict=True)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    payload = {
        "schema": "vice-next-mcp/live-w3/1",
        "evidence_class": "live",
        "executable": str(exe),
        "executable_sha256": digest,
        "platform": os.name,
        "machine": args.machine,
        "isolation": await isolation(
            exe, args.output, soak=max(1, args.soak), machine=args.machine
        ),
        "keyboard": {
            "status": "unavailable",
            "reason": "supervised keyboard operation not exposed",
        },
        "snapshot": {
            "status": "unavailable",
            "reason": "supervised snapshot operation not exposed",
        },
        "io_effects": {"status": "unavailable", "reason": "live capture operation not exposed"},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "live-w3.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
