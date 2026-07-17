"""Minimal binary-monitor v2 client used by the runtime package."""
from __future__ import annotations
import socket, struct, threading
from dataclasses import dataclass

@dataclass(frozen=True)
class Response:
    command:int; error:int; request_id:int; body:bytes

class BinaryMonitor:
    def __init__(self, host:str, port:int, timeout:float=5.0):
        self.socket=socket.create_connection((host,port),timeout); self.socket.settimeout(timeout)
        self.timeout=timeout; self._id=0; self._lock=threading.Lock(); self.events=[]
    def close(self): self.socket.close()
    def _exact(self,n):
        b=bytearray()
        while len(b)<n:
            x=self.socket.recv(n-len(b))
            if not x: raise ConnectionError("VICE monitor closed")
            b.extend(x)
        return bytes(b)
    def call(self, command, body=b''):
        with self._lock:
            self._id=(self._id+1)&0xffffffff; rid=self._id
            self.socket.sendall(b'\x02\x02'+struct.pack('<II',len(body),rid)+bytes((command,))+body)
            while True:
                h=self._exact(12)
                if h[:2]!=b'\x02\x02': raise RuntimeError('invalid monitor header')
                n=struct.unpack_from('<I',h,2)[0]; r=Response(h[6],h[7],struct.unpack_from('<I',h,8)[0],self._exact(n))
                if r.request_id==0xffffffff: self.events.append(r); continue
                if r.request_id!=rid: raise RuntimeError('request id mismatch')
                if r.error: raise RuntimeError(f'VICE command {command:#x} failed: {r.error:#x}')
                return r
    def ping(self): self.call(0x81)
    def memory(self,start,length,memspace=0,bank=0):
        end=(start+length-1)&0xffff; b=self.call(1,struct.pack('<BHHBH',0,start&0xffff,end,memspace,bank)).body; n=struct.unpack_from('<H',b)[0] or 65536; return b[2:2+n]
    def memory_write(self,start,data,memspace=0,bank=0):
        end=(start+len(data)-1)&0xffff; self.call(2,struct.pack('<BHHBH',0,start&0xffff,end,memspace,bank)+data)
    def resume(self): self.call(0xaa)
    def reset(self,target=0): self.call(0xcc,bytes((target,)))
    def keyboard_feed(self, data):
        """Feed PETSCII bytes through VICE's documented keyboard buffer API.

        This is deliberately named *feed*, not matrix input: VICE's binary
        monitor exposes no row/column key transition command.  Keeping this
        distinction prevents a KERNAL/keyboard-buffer operation from being
        reported as physical matrix evidence.
        """
        data = bytes(data)
        if len(data) > 255: raise ValueError("keyboard feed is limited to 255 bytes")
        self.call(0x72, bytes((len(data),)) + data)
    def keyboard_matrix(self, row: int, column: int, pressed: bool):
        """Set one cell using the instrumented VICE 0x74 extension."""
        if not -5 <= int(row) <= 15 or not 0 <= int(column) <= 7:
            raise ValueError("keyboard matrix coordinates out of range")
        self.call(0x74, struct.pack('<bBB', int(row), int(column), 1 if pressed else 0))
    def dump(self,path):
        p=str(path).encode(); self.call(0x41,bytes((1,1,len(p)))+p)
    def undump(self,path):
        p=str(path).encode(); return self.call(0x42,bytes((len(p),))+p).body
