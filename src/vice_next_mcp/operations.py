import asyncio
from typing import Any
from .catalog import OPS
from .errors import ViceError, verification

TRANSIENT = {"starting", "reset", "autostarting", "snapshotting", "shutting-down"}

def context(instance, operation_id, observed):
    timing = observed.get("time", {"meaningful":False})
    timing = {**timing, "observation_sequence":instance.next_sequence()}
    requested = observed.get("requested_memspace")
    resolved = observed.get("resolved_memspace", "not_applicable")
    return {"instance_id":instance.instance_id,"generation":instance.generation,"operation_id":operation_id,
            "machine":instance.machine,"memspace":{"requested":requested,"resolved":resolved},
            "lifecycle":observed.get("lifecycle",instance.lifecycle),
            "execution_state":observed.get("execution_state",instance.execution_state),"time":timing}

def error_context(instance, operation_id):
    return context(instance, operation_id, {})

async def invoke(instance, request, cancel, progress):
    operation_id=request["operation_id"]; name=request["operation"]; arguments=request["arguments"]
    op=OPS.get(name)
    if op is None: raise ViceError("UNSUPPORTED_COMMAND","unknown operation",{"operation":name})
    op.validate(arguments)
    if name not in instance.capabilities:
        raise ViceError("UNSUPPORTED_COMMAND","target lacks required capability",{"required":name,"machine":instance.machine})
    if op.mutating and instance.lifecycle in TRANSIENT:
        raise ViceError("STATE_CONFLICT","instance is in a transient lifecycle state",{"lifecycle":instance.lifecycle})
    if cancel.is_set(): raise ViceError("CANCELLED","operation cancelled before dispatch")
    try:
        accepted=await asyncio.wait_for(instance.transport.execute(name,arguments,operation_id=operation_id,
            deadline_ms=request["deadline_ms"],cancel=cancel,progress=progress),request["deadline_ms"]/1000)
        if cancel.is_set():
            raise ViceError("CANCELLED","operation cancelled after dispatch",effect_may_have_occurred=op.mutating)
        observed=await asyncio.wait_for(instance.transport.observe_effect(name,arguments,accepted,operation_id=operation_id,
            deadline_ms=request["deadline_ms"],cancel=cancel,progress=progress),request["deadline_ms"]/1000)
        if cancel.is_set():
            raise ViceError("CANCELLED","operation cancelled during effect observation",effect_may_have_occurred=op.mutating)
    except asyncio.TimeoutError:
        raise ViceError("TIMEOUT","completion predicate was not observed",{"phase":"effect_observation","deadline_ms":request["deadline_ms"]},True,op.mutating)
    evidence=observed.get("evidence")
    if not isinstance(evidence,list) or not evidence: raise verification("transport supplied no completion evidence",operation=name)
    if observed.get("effect_occurred",True) is not True: raise verification("completion evidence does not prove the effect",operation=name)
    instance.lifecycle=observed.get("lifecycle",instance.lifecycle)
    instance.execution_state=observed.get("execution_state",instance.execution_state)
    return {"ok":True,"context":context(instance,operation_id,observed),
            "completion":{"kind":observed.get("completion_kind",op.completion),"effect_occurred":True,"evidence":evidence},
            "result":observed.get("result",accepted.get("result",accepted))}

def compatibility_result(envelope, mode):
    """Explicit opt-in for audited vice-mcp clients that consumed bare results."""
    if mode == "legacy-bare-result-v1" and envelope.get("ok"): return envelope["result"]
    return envelope
