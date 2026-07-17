import asyncio, json, uuid
from functools import wraps
import pytest
from vice_next_mcp.catalog import OPS
from vice_next_mcp.model import Instance, StaticResolver
from vice_next_mcp.server import McpServer

INSTANCE=str(uuid.uuid4()); TOKEN="x"*43
def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs): return asyncio.run(function(*args, **kwargs))
    return wrapper
class Effects:
    def __init__(self):
        self.dispatched=[]; self.release=asyncio.Event(); self.release.set(); self.cancel_seen=False
    async def execute(self,operation,arguments,**kw):
        self.dispatched.append((operation,arguments)); await kw["progress"](.25,"accepted"); return {"reply":7}
    async def observe_effect(self,operation,arguments,accepted,**kw):
        while not self.release.is_set():
            if kw["cancel"].is_set(): self.cancel_seen=True; return {"evidence":[{"cancelled":True}],"result":{}}
            await asyncio.sleep(0)
        return {"evidence":[{"kind":"fixture","operation":operation}],"result":{"operation":operation},
                "time":{"meaningful":True,"host_cycle":100,"frame":2}}

def setup(capabilities=None,compat=None):
    transport=Effects(); instance=Instance(INSTANCE,1,TOKEN,{"class":"C64","model":"PAL","emulator":"x64sc","version":"3.10"},"stopped","paused",capabilities or set(OPS),transport)
    return McpServer(StaticResolver([instance]),compatibility_mode=compat),transport
async def initialize(server): await server.handle({"jsonrpc":"2.0","id":0,"method":"initialize","params":{}})
def call(name="vice.run",arguments=None,request_id=1):
    return {"jsonrpc":"2.0","id":request_id,"method":"tools/call","params":{"name":name,"arguments":{"operation_id":str(uuid.uuid4()),"target":{"instance_id":INSTANCE,"generation":1,"lease_token":TOKEN},"deadline_ms":1000,**(arguments or {})}}}
def payload(response): return response["result"]["structuredContent"]

@async_test
async def test_initialize_and_tool_list_have_closed_schemas():
    server,_=setup(); response=await server.handle({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}})
    assert response["result"]["serverInfo"]["name"]=="vice-next-mcp"
    listed=await server.handle({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
    tools=listed["result"]["tools"]
    assert {x["name"] for x in tools}==set(OPS)
    assert all(x["inputSchema"]["additionalProperties"] is False for x in tools)

@async_test
async def test_missing_capability_rejected_before_transport_dispatch():
    server,transport=setup({"vice.ping"}); await initialize(server)
    response=await server.handle(call())
    assert payload(response)["error"]["code"]=="UNSUPPORTED_COMMAND"; assert transport.dispatched==[]

@async_test
async def test_success_waits_for_effect_evidence_and_emits_progress():
    server,transport=setup(); await initialize(server); transport.release.clear(); notes=[]
    task=asyncio.create_task(server.handle(call(),notes.append)); await asyncio.sleep(0)
    assert not task.done(); transport.release.set(); response=await task; value=payload(response)
    assert value["ok"] and value["completion"]["effect_occurred"]
    assert value["context"]["time"]=={"meaningful":True,"host_cycle":100,"frame":2,"observation_sequence":1}
    assert notes[0]["method"]=="notifications/progress"

@async_test
async def test_cancellation_notification_is_structured_error():
    server,transport=setup(); await initialize(server); transport.release.clear()
    task=asyncio.create_task(server.handle(call(request_id=44))); await asyncio.sleep(0)
    await server.handle({"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":44}})
    response=await task
    assert payload(response)["error"]["code"]=="CANCELLED"; assert payload(response)["error"]["effect_may_have_occurred"]

@async_test
async def test_invalid_request_and_unknown_arguments_do_not_dispatch():
    server,transport=setup(); await initialize(server)
    response=await server.handle(call(arguments={"bogus":1}))
    assert payload(response)["error"]["code"]=="INVALID_REQUEST"; assert transport.dispatched==[]

@async_test
async def test_explicit_legacy_mode_returns_audited_bare_shape():
    server,_=setup(compat="legacy-bare-result-v1"); await initialize(server)
    assert payload(await server.handle(call()))=={"operation":"vice.run"}

@pytest.mark.parametrize("name,args",[
 ("vice.registers.set",{"memspace":"computer","values":{"PC":4096}}),
 ("vice.memory.write",{"memspace":"computer","bank":"cpu","address":4096,"data":"AQI=","side_effects":"suppress","verify":"read_back"}),
 ("vice.resources.set",{"values":{"WarpMode":True},"restart":"never"}),
 ("vice.disk.attach",{"unit":8,"path":"C:/fixture.d64","read_only":False}),
 ("vice.autostart",{"path":"C:/fixture.prg","mode":"load_only"}),
 ("vice.checkpoint.set",{"memspace":"computer","start":4096,"end":4096,"access":"store","enabled":True,"temporary":False}),
 ("vice.screen.capture",{"format":"png","include_border":True}),
 ("vice.failure.bundle",{"reason":"fixture","memory_windows":[],"event_limit":10}),
])
@async_test
async def test_core_operations_propagate_verified_effect(name,args):
    server,transport=setup(); await initialize(server); value=payload(await server.handle(call(name,args)))
    assert value["result"]["operation"]==name
    assert value["completion"]["evidence"]==[{"kind":"fixture","operation":name}]
    assert transport.dispatched[-1]==(name,args)

@async_test
async def test_jsonrpc_errors_are_separate_from_domain_errors():
    server,_=setup()
    assert (await server.handle({"jsonrpc":"2.0","id":1,"method":"tools/list"}))["error"]["code"]==-32002
    await initialize(server)
    assert (await server.handle({"jsonrpc":"2.0","id":2,"method":"nope"}))["error"]["code"]==-32601
