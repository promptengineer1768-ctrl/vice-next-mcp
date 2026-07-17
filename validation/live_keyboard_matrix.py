"""Probe native keyboard matrix/RESTORE support without claiming text-feed parity.

The official VICE 3.10 binary monitor exposes keyboard-feed (0x72), but does
not expose a row/column transition or RESTORE/NMI event.  This probe records
the attempted calls and their explicit rejection, making that limitation
machine-readable and regression-testable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vice_next_mcp.supervisor import Supervisor  # noqa: E402
from vice_next_mcp.transport_runtime import BinaryMonitorTransport  # noqa: E402


def main() -> None:
    default = Path(r"C:\tmp\vice-official-sdl2-3.10\SDL2VICE-3.10-win64")
    rows: list[dict] = []
    for machine, name in (("x64sc", "x64sc.exe"), ("x128", "x128.exe")):
        exe = Path(os.environ.get("VICE_" + machine.upper(), str(default / name)))
        row = {
            "machine": machine,
            "executable": str(exe),
            "timestamp": time.time(),
            "backend": "VICE 3.10 binary monitor",
            "keyboard_feed_command": "0x72 (API v2)",
            "physical_matrix": False,
            "restore_nmi": False,
            "probes": [],
        }
        if not exe.exists():
            row["status"] = "unavailable"
            rows.append(row)
            continue
        supervisor = Supervisor(str(exe), startup_timeout=15)
        try:
            instance = supervisor.create(machine)
            transport = BinaryMonitorTransport(supervisor)
            for operation, call in (
                (
                    "vice.keyboard.matrix",
                    lambda: transport.keyboard_matrix(instance.id, row=1, column=2, action="press"),
                ),
                (
                    "vice.keyboard.restore",
                    lambda: transport.keyboard_restore(instance.id, action="press"),
                ),
            ):
                try:
                    call()
                    probe = {"operation": operation, "status": "unexpectedly-supported"}
                    row["status"] = "error"
                except Exception as exc:  # expected, explicit capability boundary
                    probe = {
                        "operation": operation,
                        "status": "unsupported",
                        "error_type": type(exc).__name__,
                        "reason": str(exc),
                    }
                row["probes"].append(probe)
            row.setdefault("status", "pass")
            row["instance_id"] = instance.id
            row["generation"] = instance.generation
        except Exception as exc:
            row.update(status="error", error=repr(exc))
        finally:
            supervisor.close()
        rows.append(row)
    out = ROOT / "validation" / "results" / "w3-b-keyboard-matrix-live.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"schema": "w3-b-keyboard-matrix-live/1", "rows": rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(out)


if __name__ == "__main__":
    main()
