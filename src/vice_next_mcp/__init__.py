"""External MCP adapter for current VICE."""

from .errors import ViceError
from .model import Instance, InstanceResolver, ViceTransport
from .server import McpServer
from .keyboard import KeyboardQueue, KeyboardAction, KeyboardResult
from .capture import IOCapture, IECapture, DriveState, MemoryCapture, ClockSync
from .batch import BatchRunner, CaseResult, case_id, allocate_ports
from .snapshot import SnapshotError, fingerprint, validate_snapshot, metadata
from .trace import TraceError, TraceWriter
from .supervisor import Supervisor, InstanceLease, InstanceState
from .transport_runtime import BinaryMonitorTransport, OperationEvidence
from .live_mcp import LiveMcpRuntime, SupervisorResolver

__all__ = [
    "Instance",
    "InstanceResolver",
    "McpServer",
    "ViceError",
    "ViceTransport",
    "KeyboardQueue",
    "KeyboardAction",
    "KeyboardResult",
    "IOCapture",
    "IECapture",
    "DriveState",
    "MemoryCapture",
    "ClockSync",
    "BatchRunner",
    "CaseResult",
    "case_id",
    "allocate_ports",
    "SnapshotError",
    "fingerprint",
    "validate_snapshot",
    "metadata",
    "TraceError",
    "TraceWriter",
    "Supervisor",
    "InstanceLease",
    "InstanceState",
    "BinaryMonitorTransport",
    "OperationEvidence",
    "LiveMcpRuntime",
    "SupervisorResolver",
]
