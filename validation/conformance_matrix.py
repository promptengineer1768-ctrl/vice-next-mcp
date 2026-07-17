"""Deterministic W6-D protocol conformance/regression matrix.

The matrix uses the reference IEC model when a live VICE monitor is not
available.  Results explicitly label modelled versus measured observations so
they cannot be mistaken for emulator timing evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "multi"
sys.path.insert(0, str(ROOT / "src"))
from tools.iec_simulator import (  # noqa: E402
    CableModel, ClockDomain, DriveReply, IecClusterSimulator, LinkExhausted,
    NTSC_C64_HZ, PAL_C64_HZ, DRIVE_2MHZ_HZ, DRIVE_1541_HZ,
)


@dataclass
class CaseResult:
    case_id: str
    evidence: str
    host: str
    drives: list[int]
    blocks: int
    passed: int
    faults: int
    fault_recovered: int
    transitions_checked: int
    failures: list[str]
    model: dict


def configurations() -> list[tuple[str, float, dict[int, float]]]:
    hosts = [("c64-pal", PAL_C64_HZ), ("c64-ntsc", NTSC_C64_HZ),
             ("c128-1mhz", PAL_C64_HZ), ("c128-2mhz", DRIVE_2MHZ_HZ)]
    topologies = [("1541", {8: DRIVE_1541_HZ}), ("1571", {8: DRIVE_2MHZ_HZ}),
                 ("1581", {8: DRIVE_2MHZ_HZ}), ("mixed-2", {8: DRIVE_1541_HZ, 9: DRIVE_2MHZ_HZ}),
                 ("mixed-3", {8: DRIVE_1541_HZ, 9: DRIVE_2MHZ_HZ, 10: DRIVE_2MHZ_HZ})]
    return [(f"{h}-{t}", hz, drives) for h, hz in hosts for t, drives in topologies]


def run_case(case_id: str, host_hz: float, clocks: dict[int, float], blocks: int, faults: int, seed: int) -> CaseResult:
    rng = random.Random(seed)
    simulator = IecClusterSimulator({d: 1 for d in clocks}, deadline=max(100_000, (blocks + faults + 1) * 100_000), host_clock=ClockDomain(host_hz),
                                     drive_clocks={d: ClockDomain(hz) for d, hz in clocks.items()})
    passed = recovered = checked = 0
    failures: list[str] = []
    for i in range(blocks):
        device = sorted(clocks)[i % len(clocks)]
        payload = bytes(rng.randrange(256) for _ in range(32))
        try:
            result = simulator.adaptive_transaction(device, 1, payload, reply=DriveReply(0, payload),
                                                     cable=CableModel(1.0), transient_noise_attempts=set())
            if result.reply.body != payload:
                failures.append(f"block {i}: payload mismatch")
            else:
                passed += 1
            checked += sum(1 for e in simulator.bus.trace if e.action.startswith("device") or "complete" in e.action)
        except Exception as exc:  # pragma: no cover - retained in report
            failures.append(f"block {i}: {type(exc).__name__}: {exc}")
    for j in range(faults):
        device = sorted(clocks)[j % len(clocks)]
        payload = bytes(rng.randrange(256) for _ in range(8))
        try:
            # One transient fault must be retried at the same speed and recover.
            result = simulator.adaptive_transaction(device, 2, payload, reply=DriveReply(0, payload),
                                                     cable=CableModel(1.0), transient_noise_attempts={0}, retries_per_speed=1)
            recovered += int(result.reply.body == payload and len(result.attempts) >= 2)
        except LinkExhausted as exc:
            failures.append(f"fault {j}: {exc}")
    idle = all(not ep.pulls for ep in simulator.bus.endpoints.values())
    if not idle:
        failures.append("bus not released after matrix")
    return CaseResult(case_id, "modelled", case_id.split("-", 1)[0], sorted(clocks), blocks, passed,
                      faults, recovered, checked, failures,
                      {"trace_events": len(simulator.bus.trace), "bus_idle": idle,
                       "seed": seed, "clock_hz": host_hz})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--blocks", type=int, default=10_000)
    ap.add_argument("--faults", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0x6D)
    ap.add_argument("--output", type=Path, default=Path("validation/results/w6d_conformance.json"))
    args = ap.parse_args()
    results = [run_case(cid, hz, drives, args.blocks, args.faults, args.seed + n) for n, (cid, hz, drives) in enumerate(configurations())]
    report = {"schema": "w6d-conformance-1", "evidence": "modelled", "measured_cases": 0,
              "parameters": {"blocks": args.blocks, "faults": args.faults, "seed": args.seed},
              "results": [asdict(r) for r in results]}
    report["summary"] = {"cases": len(results), "passed": sum(r.passed for r in results),
                          "faults_recovered": sum(r.fault_recovered for r in results),
                          "failures": sum(len(r.failures) for r in results)}
    report["reproducibility"] = {"command": "python validation/conformance_matrix.py --blocks 10000 --faults 100 --seed %d" % args.seed,
                                  "sha256": hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 1 if report["summary"]["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
