from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

Progress = Callable[[float, str], Awaitable[None]]
class ViceTransport(Protocol):
    async def execute(self, operation: str, arguments: dict[str, Any], *, operation_id: str,
                      deadline_ms: int, cancel: Any, progress: Progress) -> dict[str, Any]: ...
    async def observe_effect(self, operation: str, arguments: dict[str, Any], accepted: dict[str, Any], *,
                             operation_id: str, deadline_ms: int, cancel: Any,
                             progress: Progress) -> dict[str, Any]: ...

@dataclass(slots=True)
class Instance:
    instance_id: str
    generation: int
    lease_token: str
    machine: dict[str, str]
    lifecycle: str
    execution_state: str
    capabilities: set[str]
    transport: ViceTransport
    observation_sequence: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    def next_sequence(self):
        self.observation_sequence += 1
        return self.observation_sequence

class InstanceResolver(Protocol):
    async def resolve(self, target: dict[str, Any]) -> Instance: ...

class StaticResolver:
    def __init__(self, instances): self.instances = {x.instance_id: x for x in instances}
    async def resolve(self, target):
        from .errors import ViceError
        value = self.instances.get(target.get("instance_id"))
        if value is None: raise ViceError("INSTANCE_NOT_FOUND", "instance does not exist", {"instance_id": target.get("instance_id")})
        if target.get("generation") != value.generation: raise ViceError("STALE_GENERATION", "instance generation is stale", {"expected": value.generation})
        if target.get("lease_token") != value.lease_token: raise ViceError("LEASE_REQUIRED", "a valid instance lease is required")
        return value
