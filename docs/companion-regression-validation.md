# W3-E companion-project regression validation

Recorded 2026-07-16. The machine-readable feature matrix is
`docs/companion-regression-matrix.json`.

## Execution

The new package's deterministic validation suite was run with:

```text
py -m pytest -q
36 passed, 0 failed, 0 skipped, 0.49 s
```

The companion repositories were audited statically (W1 harness call sites) but
were not launched: this checkout has no `VICE_BINARY`, MCP HTTP endpoint, or
companion fixture build selected. Therefore no live-suite pass is claimed. The
matrix records this as an explicit skip/blocker rather than a failure. Parallel
results are marked “serial substitute” because pytest-xdist and live emulator
instances were unavailable; no parallel evidence is promoted.

## Coverage and migration status

All public methods/direct `vice.*` calls found in the audited harnesses are rows
in the matrix: lifecycle/ping, memory, registers, execution, keyboard text and
matrix, autostart, screen/screenshot, disk, snapshots, and predicate waits.
Each row links to an effect or contract test in the local suite and identifies
the companion call sites. Live keyboard matrix permutations, disk state,
snapshot round trips, and companion-project migrations remain pending W3-B/C and
the native-parity gate. Timing workarounds (per-character delays, explicit
`execution.run`, KERNAL-buffer fallback, stable-screen polling) are intentionally
retained until those effects are validated; they are not counted as removed.

No companion source was edited. Adoption remains gated on W3-A parity, as
required by TODO.md.
