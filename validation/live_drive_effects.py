"""Live drive memspace/register probe through the supervised runtime."""
import argparse, hashlib, json
from pathlib import Path
from vice_next_mcp.supervisor import Supervisor
from vice_next_mcp.transport_runtime import BinaryMonitorTransport

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--executable',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True); s=Supervisor(a.executable); i=s.create('x64sc',extra_args=('-drive8type','1541')); t=BinaryMonitorTransport(s); rows=[]
    try:
        before=t.execute(i.id,'memory.read',address=0x0200,length=4,memspace=1)['result']
        marker=bytes((0x8E,0xA5,0x11,0x7C)); t.execute(i.id,'memory.write',address=0x0200,length=4,data=marker,memspace=1)
        after=t.execute(i.id,'memory.read',address=0x0200,length=4,memspace=1)['result']
        rows.append({'memspace':1,'address':'0x0200','readback':list(after),'passed':after==marker,'evidence':'live'})
        rows.append({'register_window':'0x1800','value':list(t.execute(i.id,'memory.read',address=0x1800,length=4,memspace=1)['result']),'evidence':'live'})
        t.execute(i.id,'memory.write',address=0x0200,length=4,data=before,memspace=1)
    finally: s.close()
    payload={'schema':'vice-next-mcp/live-drive-effects/1','evidence_class':'live','executable':a.executable,'executable_sha256':hashlib.sha256(Path(a.executable).read_bytes()).hexdigest(),'rows':rows,'status':'passed' if rows[0]['passed'] else 'failed'}
    (out/'live-drive-effects.json').write_text(json.dumps(payload,indent=2),encoding='utf-8'); print(json.dumps(payload,indent=2))
if __name__=='__main__': main()
