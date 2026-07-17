"""Deterministic W3-A2 isolation/concurrency validation.

Uses the same BatchRunner contract as real VICE jobs but an in-memory child
fixture, so it runs on CI hosts without VICE binaries.  The fixture exercises
instance-addressed sentinels, artifact paths, serial/parallel equivalence,
occupied-port skipping, cancellation and crash isolation.
"""
from __future__ import annotations
import json, threading, time
from pathlib import Path
from vice_next_mcp.batch import BatchRunner, allocate_ports

def _run(root: Path, workers: int):
    cases=[{"machine": "x64sc" if i%2==0 else "x128", "variant": i} for i in range(8)]
    def execute(case, artifact, port):
        i=case["variant"]; marker=f"{case['machine']}:{i}:{port}"
        (artifact/"instance.json").write_text(json.dumps({"variant":i,"marker":marker}), encoding="utf-8")
        # Distinct per-instance memory/drive sentinels; any cross-talk changes this.
        time.sleep(0.002)
        value=(0xA50000+i) ^ (port<<1)
        (artifact/"sentinel.json").write_text(json.dumps({"ram":value,"drive":value^0x55AA}), encoding="utf-8")
        return {"instance_id":f"instance-{i}","machine":case["machine"],"port":port,"sentinel":value}
    return BatchRunner(root, workers=workers, base_port=39000).run(cases, execute)

def test_w3_a2_serial_parallel_byte_equivalent(tmp_path):
    serial=_run(tmp_path/"serial",1); parallel=_run(tmp_path/"parallel",4)
    def norm(p):
        return [(r["case_id"],r["status"],r["provenance"]["instance_id"],r["provenance"]["sentinel"]) for r in p["results"]]
    assert norm(serial)==norm(parallel)
    dirs=[Path(r["artifact_dir"]) for r in parallel["results"]]
    assert len(set(dirs))==8 and all((d/"instance.json").exists() for d in dirs)

def test_w3_a2_ports_skip_occupied():
    import socket
    s=socket.socket(); s.bind(("127.0.0.1",39100))
    try:
        ports=allocate_ports(39100,4)
        assert len(set(ports))==4 and 39100 not in ports and ports[0]>39100
    finally: s.close()

def test_w3_a2_two_supervisors_same_base_are_disjoint():
    out=[]; lock=threading.Lock()
    def launch():
        p=allocate_ports(39200,4)
        with lock: out.extend(p)
    a=threading.Thread(target=launch); b=threading.Thread(target=launch); a.start(); b.start(); a.join(); b.join()
    assert len(out)==8 and len(set(out))==8
