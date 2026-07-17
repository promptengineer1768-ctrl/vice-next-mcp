"""Bridge the supervised live VICE instances into the MCP operation server."""

from __future__ import annotations
import asyncio
from typing import Any

from .model import Instance as McpInstance
from .server import McpServer
from .supervisor import Supervisor
from .transport_runtime import BinaryMonitorTransport


class SupervisorResolver:
    def __init__(self, supervisor: Supervisor):
        self.supervisor = supervisor

    async def resolve(self, target: dict[str, Any]) -> McpInstance:
        item = self.supervisor.get(target.get("instance_id"))
        if target.get("generation") != item.generation:
            raise ValueError("stale instance generation")
        if target.get("lease_token") != item.lease_token:
            raise ValueError("valid instance lease required")
        return McpInstance(
            instance_id=item.id,
            generation=item.generation,
            lease_token=item.lease_token or "",
            machine={"class": item.machine, "model": item.machine, "emulator": "VICE"},
            lifecycle=item.state.value,
            execution_state="running" if item.state.value == "running" else item.state.value,
            capabilities=set(item.capabilities),
            transport=SupervisorTransport(self.supervisor, item.id),
        )


class SupervisorTransport:
    def __init__(self, supervisor: Supervisor, instance_id: str):
        self.runtime = BinaryMonitorTransport(supervisor)
        self.instance_id = instance_id

    async def execute(self, operation, arguments, *, operation_id, deadline_ms, cancel, progress):
        if cancel.is_set():
            raise RuntimeError("cancelled")
        runtime_operation = operation[5:] if operation.startswith("vice.") else operation
        if runtime_operation == "keyboard.type":
            result = await asyncio.to_thread(
                self.runtime.keyboard_type, self.instance_id, arguments["text"]
            )
        elif runtime_operation == "keyboard.matrix":
            # Do not silently fall back to KERNAL injection: the binary monitor
            # has no row/column transition primitive.
            result = await asyncio.to_thread(
                self.runtime.keyboard_matrix,
                self.instance_id,
                row=arguments["row"],
                column=arguments["column"],
                action=arguments["action"],
                frames=arguments.get("frames", 1),
            )
        elif runtime_operation == "keyboard.restore":
            result = await asyncio.to_thread(
                self.runtime.keyboard_restore, self.instance_id, action=arguments["action"]
            )
        else:
            result = await asyncio.to_thread(
                self.runtime.execute, self.instance_id, runtime_operation, **arguments
            )
        value = result["result"]
        if isinstance(value, (bytes, bytearray)):
            value = list(value)
        return {
            "result": value,
            "accepted": {**result, "result": value},
            "evidence": result["evidence"],
            "effect_occurred": True,
        }

    async def observe_effect(
        self, operation, arguments, accepted, *, operation_id, deadline_ms, cancel, progress
    ):
        await progress(1.0, f"{operation} completed")
        return {
            "result": accepted.get("result"),
            "effect_occurred": True,
            "evidence": [accepted["evidence"]],
            "completion_kind": "live-monitor-observed",
        }


class LiveMcpRuntime:
    def __init__(self, supervisor: Supervisor, *, compatibility_mode=None):
        self.supervisor = supervisor
        self.server = McpServer(
            SupervisorResolver(supervisor), compatibility_mode=compatibility_mode
        )

    async def handle(self, message, notify=None):
        return await self.server.handle(message, notify)
