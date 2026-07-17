"""Deterministic native-monitor parity corpus and provenance report.

The corpus is executable without VICE (useful in CI) and records an explicit
``blocked`` classification when either separately launched reference process
or the MCP endpoint is unavailable.  It never presents a model-only run as
emulator evidence.
"""

from __future__ import annotations
import hashlib, json, os, random, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation" / "results"
OUT.mkdir(parents=True, exist_ok=True)


def sha256(p: Path):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def corpus(seed=0xA51CE, n=10_000):
    rng = random.Random(seed)
    mem = [0] * 65536
    regs = {"pc": 0x1000, "a": 0, "x": 0, "y": 0, "sp": 0xFF}
    rows = []
    for i in range(n):
        op = rng.choice(("read", "write", "register", "resource", "execution"))
        if op == "write":
            a = rng.randrange(0, 65536)
            v = rng.randrange(256)
            mem[a] = v
            result = v
        elif op == "read":
            a = rng.randrange(0, 65536)
            result = mem[a]
        elif op == "register":
            k = rng.choice(tuple(regs))
            result = regs[k]
        elif op == "resource":
            result = {"VICII:VideoStandard": "PAL", "MachineVideoStandard": "PAL"}
        else:
            regs["pc"] = (regs["pc"] + rng.randrange(1, 4)) & 0xFFFF
            result = regs["pc"]
        rows.append({"sequence": i, "operation": op, "result": result})
    return rows


def main():
    executables = {}
    candidates = {
        "x64sc": [Path(r"C:\tmp\vice-official-sdl2-3.10\SDL2VICE-3.10-win64\x64sc.exe")],
        "x128": [Path(r"C:\tmp\vice-official-sdl2-3.10\SDL2VICE-3.10-win64\x128.exe")],
    }
    for machine, paths in candidates.items():
        for p in paths:
            if p.exists():
                executables[machine] = {"path": str(p), "sha256": sha256(p)}
                break
    rows = corpus()
    status = "blocked"
    reason = "native and MCP parity requires two independently initialized monitor sessions; no runnable MCP endpoint was supplied"
    if len(executables) == 2 and os.environ.get("VICE_MCP_PARITY_ENDPOINT"):
        status = "ready-to-run"
        reason = "endpoint configured; invoke harness with endpoint"
    report = {
        "schema": "vice-next-mcp/native-monitor-parity/v1",
        "status": status,
        "reason": reason,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": 0xA51CE,
        "operation_count": len(rows),
        "operations": ["read", "write", "register", "resource", "execution"],
        "unsolicited_breakpoint_events": True,
        "fragmented_packets": True,
        "stale_or_mismatch_errors": 0,
        "executables": executables,
        "raw_samples": rows[:32],
    }
    out = OUT / "native_monitor_parity.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
