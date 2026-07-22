# VICE Next MCP

See [`MANUAL.md`](MANUAL.md) for the publication manual, protocol model, and
instrumented-capability rules. This project is GPLv2-or-later; see
[`COPYING`](COPYING).

Keyboard matrix injection covers C64/C128, VIC-20, Plus/4/C16, PET, CBM-II,
CBM 5x0, C64DTV, and SCPU64 targets. IEC observers cover C64, C64DTV, Plus/4,
and VIC-20; PET is explicitly excluded.

> Experimental Wave 2 transport and MCP schema with supervised lifecycle and
> batch execution. Hardware/protocol evidence remains separately gated.

## Install and quick start

Python 3.11+ is required. From a clean checkout:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e .
py -m pytest
```

Set the appropriate VICE executable (`x64sc`, `x128`, `xvic`, `xplus4`, or
`xpet`) from the official
SDL2 VICE 3.10 Windows release. `ProcessController.validate()` enforces that
the executable matches `c64` (`x64sc`) or `c128` (`x128`), and launches the
binary monitor on an automatically reserved loopback port.

The current MCP surface is constructed with `McpServer(resolver)`. A resolver
returns an `Instance` (instance id, generation, lease token, capabilities and a
`ViceTransport`). Call `initialize`, then `tools/list`/`tools/call`; each call
must include `operation_id`, `target` and `deadline_ms`.

Example Codex MCP configuration (adapt the working directory as needed):

```json
{"mcpServers":{"vice-next":{"command":"py","args":["-m","vice_next_mcp.server"]}}}
```

The package provides a supervised launcher and batch CLI. Run one live instance
with `py examples/single_smoke.py`, or run a JSON matrix:

```powershell
vice-next batch --cases examples/cases.json --workers 2 --base-port 6510
```
Use `VICE_MCP_BASE_PORT=0` (or omit `--base-port`) for ephemeral ports. Each
case receives a stable id, a fresh artifact directory and a serial reproduction
hint in `results.json`.

### Parallel-session isolation

Each launch reserves its native-monitor port with both an exclusive loopback
socket and a cross-process lease file. The socket is handed off immediately
before VICE starts; the lease remains until teardown, preventing independent
pytest workers and MCP servers from selecting the same port. Stale leases from
dead owners are reclaimed automatically.

Mutable disk/tape media is copied into a generation-specific directory. Config,
logs, traces, screenshots, crash evidence, snapshots, and temporary files also
live beneath that generation root. Teardown stops the owned VICE process tree,
drains log pumps, and releases only the caller's token-matched port lease.

Experimental replacement for the embedded VICE MCP build. This project keeps the
existing `vice-mcp` installation untouched and uses VICE's version-2 binary monitor
as the control boundary.

### Instrumented IEC capture

Set `VICE_MCP_INSTRUMENTED=1` and launch an instrumented VICE build. Each instance
receives a unique `VICE_IEC_TRACE_FILE` beneath its generation artifact directory.
Use `vice.iec.capture.start`, `read`, `status`, and `stop` to consume an isolated
logical window of resolved, cycle-stamped bus events. Results add a monotonic
sequence, normalize VICE's `clock` as `host_cycle`, report malformed/partial records,
and state whether drive-cycle stamps are actually present. `vice.iec.observe` returns
the newest complete recorder event without opening a capture window.

The current VICE recorder writes directly rather than through a bounded ring, so it
does not expose an overflow counter; responses report
`source_overflow_supported=false` instead of making a completeness claim that the
source cannot prove. Current recorder records contain host cycles and drive CPU
context, but no drive CPU cycle counter (`drive_cycles_available=false`).

## Evidence for the replacement

- Official SDL2 VICE 3.10 completed 1,000 native-monitor transactions with no
  failures at 15,630 transactions/second.
- The MCP-packaged VICE 3.10 completed the same direct test with no failures at
  10,709 transactions/second.
- The packaged executable produced a Windows null-read application error when
  invoked through an ordinary direct/version-probing path.
- MCP snapshot restore, trace-file creation, and drive-memory extraction have
  independently produced missing or contradictory evidence.

The emulator's native monitor is therefore the reference transport. A future MCP
adapter should translate MCP calls into binary-monitor requests and must not access
VICE internals from the HTTP server thread.

## Runtime

The validated runtime is official `SDL2VICE-3.10-win64.zip`, release `3.10.0`, from
`VICE-Team/svn-mirror`. The runtime is deliberately not checked into this folder.
Set `VICE_X64SC` to its `x64sc.exe` path.

## Test

From the `multi` repository:

```powershell
py -m tests.vice_direct_reliability --vice $env:VICE_X64SC --samples 500
```

The reusable protocol client is `multi/tests/vice_binary_monitor.py`.

## MCP adapter acceptance criteria

1. 10,000 mixed main/drive reads with zero transport errors.
2. Snapshot round trips reproduce main and every enabled drive's memory.
3. Trace start either creates a readable file or returns a hard error.
4. Every response includes its target memspace and paused/running state.
5. No modal Windows error boxes; child crashes become structured MCP errors.
6. Communication experiments must produce the same bytes through direct and MCP
   paths before MCP results are accepted as evidence.

### CPU stepping
ice.step.instruction and ice.step.over accept a bounded count (1-100000). Both issue VICE binary-monitor command 0x71 once per instruction and leave the monitor paused. The primitive is CPU-neutral and works for 6502-family machines and the C128 Z80. VICE's binary monitor has no distinct source-level 
ext command, so step.over is intentionally instruction stepping with explicit evidence.
