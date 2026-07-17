"""Capture raw MCP-envelope plus runtime snapshot evidence from real VICE."""
import argparse, asyncio, json, os, uuid
from pathlib import Path
from vice_next_mcp import LiveMcpRuntime, Supervisor
from vice_next_mcp.transport_runtime import BinaryMonitorTransport

async def run(exe: str, out: Path):
    s=Supervisor(exe); i=s.create('x64sc'); lease=s.lease(i.id); runtime=LiveMcpRuntime(s); rows=[]
    await runtime.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
    target={'instance_id':i.id,'generation':1,'lease_token':lease.token}
    args={'operation_id':str(uuid.uuid4()),'target':target,'deadline_ms':2000,'memspace':'cpu','bank':0,'address':4096,'length':2,'side_effects':'allow'}
    try:
        r=await runtime.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'vice.memory.read','arguments':args}})
        rows.append({'operation':'vice.memory.read','status':'passed' if not r['result']['isError'] else 'failed','response':r})
        t=BinaryMonitorTransport(s); p=out/'state.vsf';
        for op, kw in [('snapshot.save',{'path':str(p)}),('snapshot.load',{'path':str(p)})]:
            try: rows.append({'operation':op,'status':'passed','response':t.execute(i.id,op,**kw),'exists':p.exists()})
            except Exception as e: rows.append({'operation':op,'status':'failed','error':repr(e)})
        rows += [{'operation':x,'status':'unsupported','reason':'runtime capability not exposed'} for x in ('keyboard','trace','iec_capture')]
    finally:
        lease.release(); s.close()
    payload={'schema':'vice-next-mcp/live-mcp-effects/1','evidence_class':'live','executable':exe,'rows':rows}
    out.mkdir(parents=True,exist_ok=True); (out/'live-mcp-effects.json').write_text(json.dumps(payload,indent=2,default=str),encoding='utf-8'); print(json.dumps(payload,indent=2,default=str))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--executable',default=os.environ.get('VICE_X64SC',r'C:\tmp\vice-official-sdl2-3.10\SDL2VICE-3.10-win64\x64sc.exe')); ap.add_argument('--output',required=True); a=ap.parse_args(); asyncio.run(run(a.executable,Path(a.output)))
if __name__=='__main__': main()
