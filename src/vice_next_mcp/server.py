import asyncio
import inspect
import json
import logging
from typing import Any, Awaitable, Callable
from .catalog import tool_definitions
from .errors import ViceError, invalid
from .operations import compatibility_result, error_context, invoke

LOGGER = logging.getLogger(__name__)

Notify = Callable[[dict[str, Any]], Awaitable[None]]


class McpServer:
    def __init__(self, resolver, *, compatibility_mode=None):
        if compatibility_mode not in (None, "legacy-bare-result-v1"):
            raise ValueError("unknown compatibility mode")
        self.resolver = resolver
        self.compatibility_mode = compatibility_mode
        self._cancel = {}
        self._initialized = False

    async def handle(self, message, notify=None):
        notify = notify or self._discard
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return self._rpc_error(
                message.get("id") if isinstance(message, dict) else None, -32600, "Invalid Request"
            )
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params", {})
        if method == "notifications/cancelled":
            token = params.get("requestId")
            event = self._cancel.get(token)
            if event:
                event.set()
            return None
        if method == "initialize":
            self._initialized = True
            return self._result(
                request_id,
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}, "logging": {}},
                    "serverInfo": {"name": "vice-next-mcp", "version": "0.1.0"},
                },
            )
        if method == "notifications/initialized":
            self._initialized = True
            return None
        if not self._initialized:
            return self._rpc_error(request_id, -32002, "Server not initialized")
        if method == "tools/list":
            return self._result(request_id, {"tools": tool_definitions()})
        if method != "tools/call":
            return self._rpc_error(request_id, -32601, "Method not found")
        event = asyncio.Event()
        self._cancel[request_id] = event
        instance = None
        try:
            name = params.get("name")
            arguments = params.get("arguments")
            if not isinstance(arguments, dict):
                raise invalid("tools/call arguments must be an object")
            arguments = dict(arguments)
            raw = {
                "operation": name,
                "operation_id": arguments.pop("operation_id", None),
                "target": arguments.pop("target", None),
                "deadline_ms": arguments.pop("deadline_ms", None),
                "arguments": arguments,
            }
            self._validate_request(raw)
            instance = await self.resolver.resolve(raw["target"])

            async def progress(value, text):
                sent = notify(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/progress",
                        "params": {
                            "progressToken": request_id,
                            "progress": value,
                            "total": 1.0,
                            "message": text,
                        },
                    }
                )
                if inspect.isawaitable(sent):
                    await sent

            envelope = await invoke(instance, raw, event, progress)
            payload = compatibility_result(envelope, self.compatibility_mode)
            return self._result(
                request_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(payload, separators=(",", ":"))}
                    ],
                    "structuredContent": payload,
                    "isError": False,
                },
            )
        except ViceError as exc:
            envelope = {
                "ok": False,
                "context": (
                    error_context(instance, raw.get("operation_id"))
                    if instance
                    else self._fallback_context(raw if "raw" in locals() else {})
                ),
                "error": exc.as_dict(),
            }
            return self._result(
                request_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(envelope, separators=(",", ":"))}
                    ],
                    "structuredContent": envelope,
                    "isError": True,
                },
            )
        except Exception as exc:
            LOGGER.exception(
                "MCP request failed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "operation": raw.get("operation") if "raw" in locals() else None,
                },
            )
            return self._rpc_error(
                request_id, -32603, "Internal error", {"type": type(exc).__name__}
            )
        finally:
            self._cancel.pop(request_id, None)

    def _validate_request(self, request):
        import uuid

        if not isinstance(request.get("operation"), str):
            raise invalid("operation is required")
        try:
            uuid.UUID(request.get("operation_id", ""))
        except (ValueError, TypeError, AttributeError):
            raise invalid("operation_id must be a UUID")
        if not isinstance(request.get("target"), dict):
            raise invalid("target is required")
        deadline = request.get("deadline_ms")
        if not isinstance(deadline, int) or not 1 <= deadline <= 3600000:
            raise invalid("deadline_ms is out of range")

    def emit_event(self, event):
        return {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {"level": "info", "data": event},
        }

    @staticmethod
    async def _discard(_):
        pass

    @staticmethod
    def _result(i, result):
        return {"jsonrpc": "2.0", "id": i, "result": result}

    @staticmethod
    def _rpc_error(i, code, message, data=None):
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": i, "error": error}

    @staticmethod
    def _fallback_context(request):
        return {
            "instance_id": "00000000-0000-0000-0000-000000000000",
            "generation": 1,
            "operation_id": request.get("operation_id") or "00000000-0000-0000-0000-000000000000",
            "machine": {
                "class": "unknown",
                "model": "unknown",
                "emulator": "unknown",
                "version": "unknown",
            },
            "memspace": {"requested": None, "resolved": "not_applicable"},
            "lifecycle": "stopped",
            "execution_state": "unknown",
            "time": {"meaningful": False, "observation_sequence": 0},
        }
