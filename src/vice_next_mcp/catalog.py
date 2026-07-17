from dataclasses import dataclass
from typing import Any
from .errors import invalid


@dataclass(frozen=True, slots=True)
class Operation:
    name: str
    description: str
    schema: dict[str, Any]
    mutating: bool
    completion: str

    def validate(self, value):
        if not isinstance(value, dict):
            raise invalid("arguments must be an object")
        keys, required = set(self.schema.get("properties", {})), set(
            self.schema.get("required", [])
        )
        if required - value.keys() or value.keys() - keys:
            raise invalid(
                "arguments do not match operation schema",
                missing=sorted(required - value.keys()),
                unknown=sorted(value.keys() - keys),
            )


def closed(required, properties):
    return {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": False,
    }


EMPTY = closed([], {})
MEM = {"oneOf": [{"type": "string"}, {"type": "integer", "minimum": 0, "maximum": 255}]}
OPS = {}


def add(name, description, schema=EMPTY, mutating=False, completion="reply"):
    OPS[name] = Operation(name, description, schema, mutating, completion)


for n in ("vice.ping", "vice.capabilities.get", "vice.version.get"):
    add(n, n)
for n in ("vice.run", "vice.pause"):
    add(n, n, mutating=True, completion="state_observation")
for n in ("vice.step.instruction", "vice.step.over"):
    add(
        n,
        n,
        closed([], {"count": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 1}}),
        True,
        "state_observation",
    )
for n in ("vice.advance.cycles", "vice.advance.frames"):
    add(
        n,
        n,
        closed(["count"], {"count": {"type": "integer", "minimum": 1, "maximum": 2147483647}}),
        True,
        "event",
    )
add(
    "vice.run.until",
    "Run until predicate",
    closed(
        ["predicate", "max_cycles"],
        {
            "predicate": {"type": "object"},
            "max_cycles": {"type": "integer", "minimum": 1},
            "leave_checkpoint": {"type": "boolean", "default": False},
        },
    ),
    True,
    "event",
)
for suffix, props, req, mutate, done in (
    ("list", {"memspace": MEM}, ["memspace"], False, "reply"),
    (
        "get",
        {"memspace": MEM, "names": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
        ["memspace", "names"],
        False,
        "reply",
    ),
    (
        "set",
        {"memspace": MEM, "values": {"type": "object", "minProperties": 1}},
        ["memspace", "values"],
        True,
        "read_back",
    ),
):
    add("vice.registers." + suffix, "Registers " + suffix, closed(req, props), mutate, done)
add(
    "vice.memory.read",
    "Memory read",
    closed(
        ["memspace", "bank", "address", "length", "side_effects"],
        {
            "memspace": MEM,
            "bank": {},
            "address": {"type": "integer", "minimum": 0, "maximum": 65535},
            "length": {"type": "integer", "minimum": 1, "maximum": 65536},
            "side_effects": {"enum": ["allow", "suppress"]},
        },
    ),
)
add(
    "vice.memory.write",
    "Memory write",
    closed(
        ["memspace", "bank", "address", "data", "side_effects", "verify"],
        {
            "memspace": MEM,
            "bank": {},
            "address": {"type": "integer", "minimum": 0, "maximum": 65535},
            "data": {"type": "string", "contentEncoding": "base64"},
            "side_effects": {"enum": ["allow", "suppress"]},
            "verify": {"enum": ["read_back", "extension_ack"]},
        },
    ),
    True,
    "read_back",
)
add(
    "vice.keyboard.type",
    "Feed PETSCII text through VICE's binary-monitor keyboard buffer",
    closed(["text"], {"text": {"type": "string", "maxLength": 255}}),
    True,
    "event",
)
add(
    "vice.keyboard.matrix",
    "Inject a physical row/column key transition (requires native event backend)",
    closed(
        ["row", "column", "action"],
        {
            "row": {"type": "integer", "minimum": 0, "maximum": 7},
            "column": {"type": "integer", "minimum": 0, "maximum": 7},
            "action": {"enum": ["press", "release", "hold"]},
            "frames": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 1},
        },
    ),
    True,
    "event",
)
add(
    "vice.keyboard.restore",
    "Assert/release the RESTORE key (requires native event backend)",
    closed(["action"], {"action": {"enum": ["press", "release"]}}),
    True,
    "event",
)
add(
    "vice.iec.observe",
    "Read resolved IEC bus state (instrumented VICE observer)",
    closed([], {}),
    False,
    "event",
)
add(
    "vice.c128.timing.sample",
    "Read cycle/raster timing sample (instrumented C128 VICE)",
    closed([], {}),
    False,
    "event",
)
add(
    "vice.vdc.timing.sample",
    "Read VDC raster position and busy-until timing (instrumented C128 VICE)",
    closed([], {}),
    False,
    "event",
)
add(
    "vice.marker.wait",
    "Wait for marker",
    closed(
        ["predicate"],
        {
            "predicate": {"type": "object"},
            "timeout_cycles": {"type": "integer", "minimum": 1},
            "stable_samples": {"type": "integer", "minimum": 1, "maximum": 100, "default": 1},
        },
    ),
    False,
    "event",
)
for suffix, props, req, mutate in (
    ("list", {"prefix": {"type": "string"}}, [], False),
    ("get", {"names": {"type": "array", "items": {"type": "string"}}}, ["names"], False),
    (
        "set",
        {"values": {"type": "object"}, "restart": {"enum": ["never", "if_required"]}},
        ["values", "restart"],
        True,
    ),
):
    add(
        "vice.resources." + suffix,
        "Resources " + suffix,
        closed(req, props),
        mutate,
        "read_back" if mutate else "reply",
    )
add(
    "vice.config.verify",
    "Verify config",
    closed(
        ["argv", "resources"],
        {"argv": {"type": "array", "items": {"type": "string"}}, "resources": {"type": "object"}},
    ),
    False,
    "read_back",
)
for suffix, props, req, mutate in (
    (
        "attach",
        {
            "unit": {"type": "integer", "minimum": 8, "maximum": 30},
            "path": {"type": "string"},
            "read_only": {"type": "boolean"},
        },
        ["unit", "path", "read_only"],
        True,
    ),
    ("detach", {"unit": {"type": "integer", "minimum": 8, "maximum": 30}}, ["unit"], True),
    ("list", {}, [], False),
):
    add(
        "vice.disk." + suffix,
        "Disk " + suffix,
        closed(req, props),
        mutate,
        "read_back" if mutate else "reply",
    )
add(
    "vice.drive.configure",
    "Configure drive",
    closed(
        ["unit", "model", "device_number", "enabled"],
        {
            "unit": {"type": "integer"},
            "model": {"type": "string"},
            "device_number": {"type": "integer"},
            "enabled": {"type": "boolean"},
        },
    ),
    True,
    "read_back",
)
add(
    "vice.autostart",
    "Autostart",
    closed(
        ["path", "mode"],
        {
            "path": {"type": "string"},
            "mode": {"enum": ["load_only", "load_and_run"]},
            "drive": {"type": "integer"},
            "program_index": {"type": "integer"},
        },
    ),
    True,
    "event",
)
add(
    "vice.screen.capture",
    "Screenshot",
    closed(
        ["format", "include_border"],
        {"format": {"enum": ["png", "rgba"]}, "include_border": {"type": "boolean"}},
    ),
    False,
    "file_validation",
)
for p in ("checkpoint", "watchpoint"):
    add(f"vice.{p}.list", f"List {p}s")
    add(
        f"vice.{p}.set",
        f"Set {p}",
        closed(
            ["memspace", "start", "end", "access", "enabled", "temporary"],
            {
                "memspace": MEM,
                "start": {"type": "integer"},
                "end": {"type": "integer"},
                "access": {"enum": ["exec", "load", "store"]},
                "enabled": {"type": "boolean"},
                "temporary": {"type": "boolean"},
            },
        ),
        True,
        "read_back",
    )
    for action, props in (
        ("delete", {"id": {"type": "integer"}}),
        ("toggle", {"id": {"type": "integer"}, "enabled": {"type": "boolean"}}),
    ):
        add(f"vice.{p}.{action}", f"{action} {p}", closed(list(props), props), True, "read_back")
add(
    "vice.failure.bundle",
    "Failure bundle",
    closed(
        ["reason", "memory_windows", "event_limit"],
        {
            "reason": {"type": "string"},
            "memory_windows": {"type": "array", "items": {"type": "object"}},
            "include_screen": {"type": "boolean", "default": True},
            "include_resources": {"type": "boolean", "default": True},
            "event_limit": {"type": "integer", "minimum": 0},
        },
    ),
    True,
    "file_validation",
)


def tool_definitions():
    return [
        {"name": x.name, "description": x.description, "inputSchema": x.schema}
        for x in OPS.values()
    ]
