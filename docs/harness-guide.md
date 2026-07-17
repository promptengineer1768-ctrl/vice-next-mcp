# Harness guide

This guide documents the live supervised API. The supervisor owns process
leases, ports and teardown; the batch runner adds deterministic case ids and
isolated artifacts.

## Lifecycle and isolation

`ProcessController(artifact_root)` creates per-instance `config`, `media`,
`logs`, `traces`, `screenshots`, and `crashes` directories. `launch("c64", path)`
starts `x64sc`; `launch("c128", path)` starts `x128`, assigns an increasing or
ephemeral loopback port, waits for binary-monitor readiness, and returns a
`ViceProcess`. Always `await process.stop()` in `finally`. A crash raises
`LaunchError` with pid, exit code, command, stdout/stderr tails and executable
SHA-256. `InstancePaths.isolate_media()` copies writable disk images; only
verified read-only media may be shared.

The MCP `Instance` carries `instance_id`, `generation`, `lease_token`, machine,
lifecycle, execution state and capabilities. `StaticResolver` rejects unknown
ids, stale generations and missing leases. No mutable emulator state is shared.

## Operations

The schema is authoritative in `src/vice_next_mcp/catalog.py`. It includes run,
pause, instruction/cycle/frame stepping, predicate waits (`vice.run.until` and
`vice.marker.wait`), memory/register read/write, resources and disk/drive
configuration, autostart, screen capture, checkpoints/watchpoints and failure
bundles. The live supervisor transport currently provides memory, execution,
reset and snapshot effects. Keyboard, trace and IEC capture helpers remain
explicit capability gaps until native-monitor operations are implemented.
Every successful response includes instance/generation,
requested and resolved memspace, lifecycle/execution state, observation sequence,
completion predicate and evidence. Cancellation is JSON-RPC
`notifications/cancelled`; mutating cancellation reports that an effect may
have occurred.

## Parallel and serial workflows

Use `pytest -n auto`, `vice-next batch --workers 4 --base-port 6510`, or
`--base-port 0` for ephemeral ports. Each lease gets
unique artifact paths; cancellation must reap VICE, release ports and produce a
failure bundle. A parallel report will include an exact serial pytest node id.
For deterministic diagnosis, use the `serial_reproduction` command in the
JSON result and rerun it with `pytest -n 0`.

## Example patterns

```python
import asyncio, os
from vice_next_mcp.process import ProcessController

async def main():
    ctl = ProcessController("artifacts")
    proc = await ctl.launch("c64", os.environ["VICE_X64SC"])
    try:
        print(proc.instance_id, proc.monitor_port, proc.paths.root)
    finally:
        await proc.stop()
asyncio.run(main())
```

The pytest plugin exposes `vice_artifact_dir`, `vice_case_id`, and
`vice_instance_factory`; fixtures reap leases after each test.

## Troubleshooting

| Symptom | Check |
|---|---|
| Occupied port | choose `preferred_port=0`; inspect `LaunchError.details` |
| Early exit/modal crash | verify executable, ROMs and read `logs/{stdout,stderr}.log` |
| Stuck keyboard | cancel the operation; ensure W2-E releases queued keys |
| Snapshot/trace missing | treat as unsupported until a transport returns file evidence |
| Low emulation speed | reduce workers; record host load and VICE version |
| Orphan process | `await stop()` in `finally`; W2-E will add supervisor reaping |
| Parallel-only failure | rerun the exact node serially; compare instance/artifact ids |

## Migration

Companion projects should replace local `ViceMCP`/`ViceSession` helpers with a
resolver-backed `McpServer` only after native/MCP parity validation. Preserve
explicit target leases and result envelopes; remove keyboard/timing workarounds
only after the keyboard-effect matrix passes. No companion migration is part of
Wave 2.
