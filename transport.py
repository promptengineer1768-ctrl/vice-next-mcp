from __future__ import annotations
from dataclasses import dataclass
from .supervisor import Supervisor, InstanceLease

@dataclass(frozen=True)
class OperationEvidence:
    operation:str; instance_id:str; generation:int; state:str; effect:dict

class BinaryMonitorTransport:
    def __init__(self, supervisor:Supervisor): self.supervisor=supervisor
    def execute(self,instance_id,operation,**params):
        i=self.supervisor.get(instance_id); m=i.monitor
        if not m: raise RuntimeError('instance has no live monitor')
        if operation=='memory.read': result=m.memory(int(params['address']),int(params['length']))
        elif operation=='memory.write': result=m.memory_write(int(params['address']),bytes(params['data']))
        elif operation=='run': m.resume(); i.state='running'; result=None
        elif operation=='pause': m.ping(); i.state='paused'; result=None
        elif operation=='reset': result=m.reset(int(params.get('target',0)))
        elif operation=='snapshot.save': result=m.dump(params['path'])
        elif operation=='snapshot.load': result=m.undump(params['path'])
        else: raise ValueError(f'unknown operation {operation}')
        return {'result':result,'evidence':OperationEvidence(operation, i.id,i.generation,i.state,{'command':operation}).__dict__}
