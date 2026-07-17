# VICE Next MCP Manual

## Purpose

VICE Next MCP is a supervised Model Context Protocol server for official VICE
3.10 binary-monitor sessions. It provides lifecycle control, memory/register
operations, snapshots, keyboard input, and capability-gated instrumentation.

## Installation

Requires Python 3.11 or newer:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e .
py -m pytest
```

Set `VICE_X64SC` and/or `VICE_X128` to the official VICE executables. Launches
use `-default` so incompatible user configuration files are not loaded.

## MCP lifecycle

Initialize the server, list tools, then call operations with an `operation_id`,
`target` (`instance_id`, generation, and lease token), and `deadline_ms`.
Every mutating operation returns completion evidence and an instance generation.
Restart preserves the logical instance ID and increments its generation.

## Instrumented capabilities

The stock VICE monitor advertises only standard capabilities. Set
`VICE_MCP_INSTRUMENTED=1` when using the instrumented binary to advertise
physical keyboard matrix and RESTORE operations. The catalog also defines:

- `vice.iec.observe` — resolved IEC bus state;
- `vice.c128.timing.sample` — C128 cycle/raster sample;
- `vice.vdc.timing.sample` — VDC raster and busy-until sample.

These are intentionally unavailable unless a transport bridge supplies the
corresponding native observer data; the server never fabricates evidence.

Keyboard matrix injection is supported for C64, C64-fast, C128, VIC-20,
Plus/4, C16, PET, CBM-II, CBM 5x0, C64DTV, and SCPU64 VICE executables. IEC
observer coverage is available for C64, C64DTV, Plus/4, and VIC-20; PET is
deliberately excluded because its IEC implementation does not use the shared
resolved-bus path.

## Design rules

The MCP server communicates with VICE through the binary monitor and keeps
transport I/O off the server request thread. Unsupported capabilities fail
explicitly. Evidence includes operation, instance, generation, and observed
effect so callers can reject stale or contradictory results.

## License

This server is released under the GNU General Public License version 2 or any
later version. See [`COPYING`](COPYING).
