"""Async VICE binary-monitor v2 framing, correlation, and event transport."""
from __future__ import annotations
import asyncio, contextlib, struct
from dataclasses import dataclass
from enum import Enum

MAGIC=b"\x02\x02"; EVENT_ID=0xFFFFFFFF; MAX_BODY=64*1024*1024
class State(str,Enum):
    DISCONNECTED="disconnected"; CONNECTED="connected"; FAILED="failed"; CLOSED="closed"
class TransportError(RuntimeError): pass
class ProtocolError(TransportError): pass
class Disconnected(TransportError): pass
@dataclass(frozen=True,slots=True)
class Response: command:int; error:int; request_id:int; body:bytes
class CommandError(TransportError):
    def __init__(self,r:Response):
        self.command,self.error,self.request_id=r.command,r.error,r.request_id
        super().__init__(f"VICE command ${r.command:02x} request {r.request_id} failed: ${r.error:02x}")

def encode_request(command:int,request_id:int,body:bytes=b"")->bytes:
    if not 0<=command<=255: raise ValueError("command must fit in one byte")
    if not 0<=request_id<EVENT_ID: raise ValueError("invalid request id")
    if len(body)>MAX_BODY: raise ValueError("request body too large")
    return MAGIC+struct.pack("<II",len(body),request_id)+bytes((command,))+body

async def read_response(reader:asyncio.StreamReader)->Response:
    try: header=await reader.readexactly(12)
    except asyncio.IncompleteReadError as e: raise Disconnected("VICE closed monitor stream") from e
    if header[:2]!=MAGIC: raise ProtocolError(f"invalid monitor magic {header[:2].hex()}")
    size=struct.unpack_from("<I",header,2)[0]
    if size>MAX_BODY: raise ProtocolError(f"invalid response length {size}")
    try: body=await reader.readexactly(size)
    except asyncio.IncompleteReadError as e: raise Disconnected("VICE closed during response body") from e
    return Response(header[6],header[7],struct.unpack_from("<I",header,8)[0],body)

class BinaryMonitorTransport:
    """Single-reader transport with bounded pending work and event buffering.

    Cancellation removes correlation state; a late reply fails the connection.
    Reconnect never replays requests because their effects may have occurred.
    """
    def __init__(self,host:str,port:int,*,connect_timeout=5.0,request_timeout=5.0,max_pending=64,max_events=1024):
        if max_pending<1 or max_events<1: raise ValueError("queue bounds must be positive")
        self.host,self.port=host,port; self.connect_timeout=connect_timeout; self.request_timeout=request_timeout
        self.state=State.DISCONNECTED; self.failure=None; self.dropped_events=0
        self._reader=None; self._writer=None; self._task=None; self._pending={}; self._next=0
        self._slots=asyncio.Semaphore(max_pending); self._write=asyncio.Lock(); self._life=asyncio.Lock(); self._events=asyncio.Queue(max_events)
    async def connect(self):
        async with self._life:
            if self.state is State.CONNECTED:return
            try:self._reader,self._writer=await asyncio.wait_for(asyncio.open_connection(self.host,self.port),self.connect_timeout)
            except BaseException as e:self.state=State.FAILED;self.failure=e;raise Disconnected(f"cannot connect to {self.host}:{self.port}") from e
            self.state=State.CONNECTED;self.failure=None;self._task=asyncio.create_task(self._read_loop(),name=f"vice-monitor-{self.port}")
    def _request_id(self):
        for _ in range(EVENT_ID):
            self._next=(self._next+1)&0xffffffff
            if self._next==EVENT_ID:self._next=0
            if self._next not in self._pending:return self._next
        raise TransportError("request id space exhausted")
    async def negotiate(self):return await self.execute(0x85)
    async def execute(self,command:int,body:bytes=b"",*,timeout=None):
        await self._slots.acquire();rid=None;future=None
        try:
            if self.state is not State.CONNECTED or self._writer is None:raise Disconnected(f"monitor is {self.state.value}")
            rid=self._request_id();future=asyncio.get_running_loop().create_future();self._pending[rid]=future
            async with self._write:
                self._writer.write(encode_request(command,rid,body));await self._writer.drain()
            try:reply=await asyncio.wait_for(asyncio.shield(future),self.request_timeout if timeout is None else timeout)
            except asyncio.TimeoutError as e:raise TimeoutError(f"monitor request {rid} timed out; effect may have occurred") from e
            if reply.error:raise CommandError(reply)
            return reply
        finally:
            if rid is not None:self._pending.pop(rid,None)
            if future is not None and not future.done():future.cancel()
            self._slots.release()
    async def next_event(self,*,timeout=None):return await self._events.get() if timeout is None else await asyncio.wait_for(self._events.get(),timeout)
    async def _read_loop(self):
        try:
            while True:
                reply=await read_response(self._reader)
                if reply.request_id==EVENT_ID:
                    if self._events.full():self._events.get_nowait();self.dropped_events+=1
                    self._events.put_nowait(reply);continue
                future=self._pending.get(reply.request_id)
                if future is None:raise ProtocolError(f"unexpected request id {reply.request_id}")
                if not future.done():future.set_result(reply)
        except asyncio.CancelledError:raise
        except BaseException as e:
            self.failure=e;self.state=State.FAILED
            for future in tuple(self._pending.values()):
                if not future.done():future.set_exception(Disconnected(str(e)))
            if self._writer:self._writer.close()
    async def reconnect(self):await self.close();self.state=State.DISCONNECTED;await self.connect()
    async def close(self):
        async with self._life:
            task,self._task=self._task,None
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):await task
            for future in tuple(self._pending.values()):
                if not future.done():future.set_exception(Disconnected("monitor closed"))
            self._pending.clear();writer,self._writer=self._writer,None;self._reader=None
            if writer:
                writer.close()
                with contextlib.suppress(Exception):await writer.wait_closed()
            self.state=State.CLOSED
    async def __aenter__(self):await self.connect();return self
    async def __aexit__(self,*_):await self.close()
