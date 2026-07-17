# VICE Next MCP

See [`MANUAL.md`](MANUAL.md) for the publication manual, protocol model, and
instrumented-capability rules. This project is GPLv2-or-later; see
[`COPYING`](COPYING).

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

Experimental replacement for the embedded VICE MCP build. This project keeps the
existing `vice-mcp` installation untouched and uses VICE's version-2 binary monitor
as the control boundary.

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
