"""Raw live evidence for official VICE keyboard-feed (not matrix) behavior."""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vice_next_mcp.supervisor import Supervisor
from vice_next_mcp.transport_runtime import BinaryMonitorTransport

def main():
    out = ROOT / "validation" / "results" / "w3-b-keyboard-feed-live.json"
    rows=[]
    default = r"C:\tmp\vice-official-sdl2-3.10\SDL2VICE-3.10-win64"
    for machine, exe_name in (("x64sc","x64sc.exe"),("x128","x128.exe")):
        exe = os.environ.get("VICE_" + machine.upper(), str(Path(default) / exe_name))
        row={"machine":machine,"executable":exe,"timestamp":time.time(),
             "operation":"vice.keyboard.type","physical_matrix":False,
             "native_backend":"VICE binary monitor 0x72 API v2",
             "compatibility_shadow":True}
        if not Path(exe).exists(): row.update(status="unavailable"); rows.append(row); continue
        sup=Supervisor(exe, startup_timeout=15)
        try:
            inst=sup.create(machine)
            result=BinaryMonitorTransport(sup).keyboard_type(inst.id,"W3B")
            observed=list(inst.monitor.memory(0x0277,3))
            row.update(status="pass",instance_id=inst.id,generation=inst.generation,
                       result=result["result"],evidence=result["evidence"],
                       observed_kernal_buffer=observed)
        except Exception as exc:
            row.update(status="error",error=repr(exc))
        finally: sup.close()
        rows.append(row)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"schema":"w3-b-keyboard-feed-live/1","rows":rows},indent=2)+"\n",encoding="utf-8")
    print(out)
if __name__ == "__main__": main()
