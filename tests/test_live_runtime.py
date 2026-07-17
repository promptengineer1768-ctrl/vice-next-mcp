import asyncio
import os
import uuid

import pytest

from vice_next_mcp import LiveMcpRuntime, Supervisor
from vice_next_mcp.transport_runtime import BinaryMonitorTransport


@pytest.mark.live
def test_live_mcp_memory_effect():
    exe = os.environ.get(
        "VICE_X64SC", r"C:\tmp\vice-official-sdl2-3.10\SDL2VICE-3.10-win64\x64sc.exe"
    )
    if not os.path.exists(exe):
        pytest.skip("official x64sc unavailable")

    async def run():
        supervisor = Supervisor(exe)
        instance = supervisor.create("x64sc")
        lease = supervisor.lease(instance.id)
        try:
            runtime = LiveMcpRuntime(supervisor)
            await runtime.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            result = await runtime.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "vice.memory.read",
                        "arguments": {
                            "operation_id": str(uuid.uuid4()),
                            "target": {
                                "instance_id": instance.id,
                                "generation": 1,
                                "lease_token": lease.token,
                            },
                            "deadline_ms": 2000,
                            "memspace": "cpu",
                            "bank": 0,
                            "address": 0,
                            "length": 1,
                            "side_effects": "allow",
                        },
                    },
                }
            )
            assert "result" in result, result
            assert result["result"]["isError"] is False, result
            assert result["result"]["structuredContent"]["completion"]["effect_occurred"]
            typed = BinaryMonitorTransport(supervisor).keyboard_type(instance.id, "HELLO")
            assert typed["result"]["count"] == 5
            assert list(instance.monitor.memory(0x0277, 5)) == list(b"HELLO")
        finally:
            lease.release()
            supervisor.close()

    asyncio.run(run())
