from dataclasses import dataclass
from collections import deque
@dataclass(frozen=True)
class KeyboardAction: kind:str; value:object=None; frames:int=1; modifiers:tuple=()
@dataclass
class KeyboardResult: accepted:int; completed:int; cancelled:bool; stuck_keys:list; acknowledgement:str
class KeyboardQueue:
 def __init__(self,machine='C64',frame=0): self.machine=machine.upper(); self.frame=frame; self._q=deque(); self._held=set(); self.events=[]
 def enqueue(self,actions,start_frame=None):
  f=self.frame if start_frame is None else max(self.frame,start_frame)
  for a in actions:
   if isinstance(a,dict): a=KeyboardAction(**a)
   self._q.append((f,a)); f+=max(0,a.frames)
  return 'kbd-'+str(len(self.events)+len(self._q))
 def tick(self,frames=1,running=True,warp=False):
  self.frame+=max(0,frames); out=[]
  if not running:return out
  while self._q and self._q[0][0]<=self.frame:
   at,a=self._q.popleft(); k=a.kind.lower(); key=str(a.value)
   if k in ('press','matrix_press','restore','hold'): self._held.add(key)
   elif k in ('release','matrix_release'): self._held.discard(key)
   out.append({'frame':self.frame,'scheduled_frame':at,'kind':k,'value':a.value,'modifiers':list(a.modifiers),'machine':self.machine,'warp':warp})
  self.events.extend(out); return out
 def cancel(self): self._q.clear(); self._held.clear()
 def status(self): return {'frame':self.frame,'pending':len(self._q),'held':sorted(self._held),'machine':self.machine}
 def drain(self,max_frames=10000,running=True):
  n=len(self.events); target=self.frame+max_frames
  while self._q and self.frame<target:self.tick(1,running=running)
  c=bool(self._q)
  if c:self.cancel()
  d=len(self.events)-n; return KeyboardResult(d,d,c,sorted(self._held),'drained' if not c else 'timeout')
