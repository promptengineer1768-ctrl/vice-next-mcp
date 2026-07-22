import asyncio
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from vice_next_mcp.catalog import OPS
from vice_next_mcp.live_mcp import LiveMcpRuntime
from vice_next_mcp.supervisor import InstanceState


class SupervisorFixture:
    def __init__(self, trace_path: Path):
        self.item = SimpleNamespace(
            id="capture-instance",
            generation=1,
            lease_token="lease",
            machine="x64sc",
            monitor=object(),
            state=InstanceState.RUNNING,
            capabilities=set(OPS),
            iec_trace_path=trace_path,
        )

    def get(self, instance_id):
        assert instance_id == self.item.id
        return self.item


def request(instance, name, request_id, **arguments):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": {
                "operation_id": str(uuid.uuid4()),
                "target": {
                    "instance_id": instance.id,
                    "generation": instance.generation,
                    "lease_token": instance.lease_token,
                },
                "deadline_ms": 1000,
                **arguments,
            },
        },
    }


def payload(response):
    return response["result"]["structuredContent"]


def test_public_mcp_capture_lifecycle_reuses_one_reader(tmp_path):
    asyncio.run(public_mcp_capture_lifecycle(tmp_path))


async def public_mcp_capture_lifecycle(tmp_path):
    trace = tmp_path / "iec.jsonl"
    trace.touch()
    supervisor = SupervisorFixture(trace)
    runtime = LiveMcpRuntime(supervisor)
    await runtime.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})

    started = payload(await runtime.handle(request(supervisor.item, "vice.iec.capture.start", 1)))
    with trace.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "clock": 100,
                    "drive_context": [{"unit": 8, "cycle": 103}],
                }
            )
            + "\n"
        )
    capture_id = started["result"]["capture_id"]
    read = payload(
        await runtime.handle(
            request(supervisor.item, "vice.iec.capture.read", 2, capture_id=capture_id)
        )
    )
    status = payload(
        await runtime.handle(
            request(supervisor.item, "vice.iec.capture.status", 3, capture_id=capture_id)
        )
    )
    stopped = payload(
        await runtime.handle(
            request(supervisor.item, "vice.iec.capture.stop", 4, capture_id=capture_id)
        )
    )

    assert started["ok"] is True
    assert read["result"]["events"][0]["host_drive_cycles"] == [
        {"unit": 8, "host_cycle": 100, "drive_cycle": 103}
    ]
    assert status["result"]["capture_id"] == started["result"]["capture_id"]
    assert stopped["result"]["active"] is False


def test_capture_state_errors_are_structured(tmp_path):
    asyncio.run(capture_state_errors_are_structured(tmp_path))


async def capture_state_errors_are_structured(tmp_path):
    trace = tmp_path / "iec.jsonl"
    trace.touch()
    supervisor = SupervisorFixture(trace)
    runtime = LiveMcpRuntime(supervisor)
    await runtime.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})

    response = payload(await runtime.handle(request(supervisor.item, "vice.iec.capture.read", 1)))

    assert response["ok"] is False
    assert response["error"]["code"] == "STATE_CONFLICT"


def test_capture_id_mismatch_is_structured(tmp_path):
    asyncio.run(capture_id_mismatch_is_structured(tmp_path))


async def capture_id_mismatch_is_structured(tmp_path):
    trace = tmp_path / "iec.jsonl"
    trace.touch()
    supervisor = SupervisorFixture(trace)
    runtime = LiveMcpRuntime(supervisor)
    await runtime.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})
    payload(await runtime.handle(request(supervisor.item, "vice.iec.capture.start", 1)))

    response = payload(
        await runtime.handle(
            request(
                supervisor.item,
                "vice.iec.capture.status",
                2,
                capture_id="stale-capture",
            )
        )
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "STATE_CONFLICT"
