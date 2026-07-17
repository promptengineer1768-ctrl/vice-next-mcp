"""Trace artifact writer with strict start/stop evidence semantics."""
from __future__ import annotations
import hashlib, json, os, uuid
from pathlib import Path

class TraceError(ValueError): pass

class TraceWriter:
    def __init__(self,path,trace_id=None,metadata=None):
        self.path=Path(path); self.trace_id=trace_id or str(uuid.uuid4()); self.metadata=metadata or {}; self._fh=None; self.event_count=0
    def start(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._fh=self.path.open("w",encoding="utf-8",newline="\n")
        self._fh.write(json.dumps({"type":"trace_start","trace_id":self.trace_id,"metadata":self.metadata})+"\n"); self._fh.flush(); os.fsync(self._fh.fileno()); return {"trace_id":self.trace_id,"path":str(self.path)}
    def event(self,event):
        if self._fh is None: raise TraceError("trace is not started")
        self._fh.write(json.dumps(event,separators=(",",":"))+"\n"); self._fh.flush(); self.event_count+=1
    def stop(self,*,expect_events=True):
        if self._fh is None: raise TraceError("trace is not started")
        self._fh.write(json.dumps({"type":"trace_stop","trace_id":self.trace_id,"event_count":self.event_count})+"\n"); self._fh.flush(); os.fsync(self._fh.fileno()); self._fh.close(); self._fh=None
        if not self.path.is_file() or self.path.stat().st_size == 0: raise TraceError("trace file was not created")
        lines=self.path.read_text(encoding="utf-8").splitlines(); events=[x for x in lines if json.loads(x).get("type") not in ("trace_start","trace_stop")]
        if expect_events and not events: raise TraceError("trace completed without readable events")
        h=hashlib.sha256(self.path.read_bytes()).hexdigest()
        return {"path":str(self.path),"size":self.path.stat().st_size,"event_count":len(events),"fingerprint":h}
