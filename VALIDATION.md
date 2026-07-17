# VICE Next MCP release validation

Status: experimental, source package only. W2-E/W2-F runtime and documentation are
implemented. Live evidence covers supervised MCP effects, keyboard feed, snapshots,
drive memory, ordered trace events, and C128 register interactions. Physical matrix,
resolved IEC ownership, and cycle-accurate timing remain capability gaps.

## Raw evidence

- [Native-monitor parity result](validation/results/native_monitor_parity.json) â€” **blocked**: 10,000-operation corpus is specified, but no runnable MCP endpoint was supplied. The result records official x64sc/x128 hashes, seed, fragmented packets and unsolicited-event requirements.
- [W3-A2 isolation validation](docs/w3-a2-validation.md) and live result artifacts â€” 1/2/4/8/16-worker runs, same-base supervisors, crash cleanup, serial/parallel probes, and xdist-worker restart pass. A one-hour soak is not a release requirement.
- [W3-Bâ€“D result summary](docs/w3-bcd-results.json) and live artifacts â€” keyboard feed, 100-iteration snapshots, drive memory, and ordered trace effects pass; physical matrix and resolved IEC capture are explicitly unsupported by the upstream monitor.

Run reproducibly from this directory:

```powershell
py -m pip install -e .
py -m pytest -q
py -m pytest tests/test_w3_a2_isolation.py -q
py -m pytest tests/test_w3_validation.py -q
```

## Source and binary provenance

The complete source/test/schema inventory is hashed in [SHA256SUMS.txt](SHA256SUMS.txt).
Regenerate it with:

```powershell
$root=(Resolve-Path .).Path
Get-ChildItem $root -Recurse -File | ? {$_.FullName -notmatch '\\.pytest_cache|__pycache__|VALIDATION.md|SHA256SUMS.txt'} | %% { "$( (Get-FileHash $_ -Algorithm SHA256).Hash.ToLower() )  $($_.FullName.Substring($root.Length+1))" } | Sort-Object
```

Validated emulator inputs (not redistributed): SDL2VICE-3.10-win64.zip,
SHA-256 `DFA7E0223EA1357BAE988B5C88B332C3B8F80DC3C7A2B51233F50BAB5263DCA5`;
x64sc SHA-256 `9a5fb20348f41cce263a359e7daed2691a211afb9d39399ee45af8092e8da87e`;
x128 SHA-256 `cefadb9f8677bceaca6426cf86d201760faf21879afdf9cb0a70395e48fff5b4`.

## Install, launch, Codex, rollback

Install Python 3.11+, create a virtual environment, and run `py -m pip install -e .`.
Set `VICE_X64SC` or `VICE_X128` to an official executable. Launch the module with
`py -m vice_next_mcp.server`; the supervisor reserves loopback monitor ports and
creates per-instance directories. Codex MCP configuration:

The launcher passes VICE 3.10's `-default` switch for every supervised process.
This is intentional: it prevents a user-level VICE 3.9 `vice.ini`/`vice.conf`
from being loaded and triggering the unsupported configuration-version dialog.
Experiment settings must therefore be supplied through the supervised launch
profile, not by mutating the global VICE settings directory.

```json
{"mcpServers":{"vice-next":{"command":"py","args":["-m","vice_next_mcp.server"]}}}
```

Rollback is removal of the `vice-next` entry and reactivation of the prior
`vice-mcp` configuration. Do not delete or overwrite the old installation.

## Concurrency, capacity, and isolation

The tested live contract supports 1/2/4/8/16 workers; begin at four and use
eight or sixteen only with at least 1 GB RAM per VICE process and stable emulation speed.
Sixteen remains a stress tier, not the safe default. Use `--workers N --base-port P`; ports are reserved atomically and
occupied ports skipped. Every instance has a UUID/lease, generation directory,
private config/log/snapshot/trace/screenshot tree, and copied writable disks.

For failed parallel cases, rerun the exact serial pytest node printed by the batch
runner (`pytest -n 0 <nodeid>`). Serial reproduction is mandatory before accepting
parallel evidence. A crashed child is isolated and reported; cancellation must reap
its process, lease, port, and artifacts without affecting other instances.

## Release decision

Completed: source inventory, hashes, install/config/rollback and isolation procedure;
deterministic W3-A2 and W3-Bâ€“D model tests, plus the documented live artifacts below.
Pending: companion regressions, physical IEC capture,
cycle-accurate C128 timing, and all Wave 4/5 protocol evidence. The old embedded
`vice-mcp` build is unsupported for experimental evidence because its snapshot,
trace-file, drive-memory extraction, and occasional null-read behavior are unreliable.


## Newly collected live artifacts

- `validation/results/live-supervisor-soak/live-supervisor-soak.json`: four concurrent supervised x64sc instances with isolated memory, PIDs, ports, and artifacts.
- `validation/results/live-w3-effects/live-mcp-effects.json`: MCP memory effect and snapshot save/load through the supervised runtime.
- `validation/results/live-w3-effects/live-drive-effects.json`: drive-8 memory and VIA-window effect validation.


- `validation/results/live-supervisor-soak8/live-supervisor-soak.json`: eight concurrent supervised x64sc instances passed.
- `validation/results/live-supervisor-soak-x128/live-supervisor-soak.json`: four concurrent supervised x128 instances passed.
- `validation/results/live-randomized-isolation/live-randomized-isolation.json`: 100,000 requested live memory operations across four isolated x64sc instances passed.
- `validation/results/w3-b-keyboard-feed-live.json`: x64sc/x128 keyboard feed passed; physical matrix remains unsupported.
- `validation/results/w3-b-keyboard-matrix-live.json`: x64sc/x128 row/column and RESTORE/NMI probes explicitly rejected by the upstream binary monitor; see `docs/w3-b-live-keyboard.md`.
- `validation/results/w3d-live-capture.json`: ordered live PC/register/CIA/VIA events and drive sentinel validation passed; resolved IEC driver attribution remains unsupported.

