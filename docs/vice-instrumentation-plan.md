# Instrumented VICE plan

The local VICE source copy is:

`C:\Users\me\Documents\Coding Projects\tools\vice-mcp\vice`

This is a VICE 3.10-era source tree. The missing capabilities are not absent
from the emulator; they are absent from the stock binary-monitor API.

## Keyboard matrix and RESTORE

Existing internal hooks:

- `src/keyboard.c`: `keyboard_set_keyarr()` and
  `keyboard_set_keyarr_any()` already mutate matrix rows/columns and special
  RESTORE entries.
- `src/keyboard.c`: `keyboard_restore_pressed()` and
  `keyboard_restore_released()` already drive the machine RESTORE signal.
- `src/keyboard.h`: matrix dimensions and key-array declarations are already
  exported.
- `src/c64/c64keyboard.c`: `c64keyboard_restore_key()` converts RESTORE into
  the C64 NMI source.
- `src/monitor/monitor_binary.c`: command `0x72` currently only feeds PETSCII
  text through `kbdbuf_feed()`.

Smallest change: add version-3 binary-monitor commands for matrix press/release
and RESTORE press/release, with structured acknowledgements and optional event
records containing emulated cycle, row, column, action, and machine. The Python
transport and capability catalog must negotiate API version 3 and reject these
operations on older VICE builds.

## IEC resolved levels and driver attribution

Existing internal state and convergence point:

- `src/iecbus/iecbus.h`: `iecbus_t` contains CPU bus, drive bus, per-unit drive
  data, and port state.
- `src/iecbus/iecbus.c`: `iecbus_cpu_write_conf1/2/3()` and the corresponding
  read/resolution paths calculate the effective open-collector bus.
- `src/iecbus/iecbus.c`: existing debug helpers log CPU/drive/bus transitions,
  but they are not exported as structured callbacks.

Smallest change: add a main-thread callback immediately after each bus
resolution. Emit `maincpu_clk`, resolved ATN/CLK/DATA, CPU asserted mask, and a
per-unit driver mask for each line. Buffer events in a bounded ring; expose a
binary-monitor drain command and an overflow counter. This avoids claiming
atomic sampling when the event ring overflowed.

## C128 1/2 MHz, VIC-II, raster, IRQ/NMI

Existing internal hooks:

- `src/viciisc/vicii-cycle.c`: `vicii_cycle()` advances raster line/cycle and
  handles raster IRQ timing.
- `src/viciisc/vicii-irq.c`: raster IRQ set/clear and trigger paths are already
  centralized.
- `src/c128/c128cpu.c`: C128 CPU clock/fast-mode transitions and `CLK_ADD`
  logic are centralized.

Smallest change: add a sampled event callback at VIC cycle boundaries and mode
transitions. Emit emulated clock, raster line/cycle, VIC IRQ state, CPU IRQ/NMI
state, and C128 fast-mode state into the same bounded event-ring abstraction.
The monitor should support filtered event subscriptions and explicit overflow
metadata rather than attempting to return an unbounded trace in one response.

## Work estimate and validation order

1. Keyboard commands and transport: roughly 1–2 engineering days.
2. IEC callback, driver masks, ring buffer, and monitor drain: roughly 2–4 days.
3. VIC/C128 cycle and interrupt events, filtering, and stress tests: roughly
   2–5 days.
4. Build a headless Windows VICE artifact, negotiate monitor API v3, then rerun
   W3-B, W3-D, and W4-D against that artifact.

This is a feasible instrumentation fork, not a request for a different released
VICE version. The stock VICE 3.10 executable remains the baseline; the fork must
be identified separately in provenance and must never be mixed with stock live
evidence.
