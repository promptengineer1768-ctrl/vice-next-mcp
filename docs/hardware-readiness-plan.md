# Real-hardware readiness plan (W6-E)

**Status: test plan only — no real-hardware validation has been performed.**
The VICE/REU and simulator results are useful for fixtures and failure taxonomy,
but do not establish electrical margins. Fast mode MUST remain feature-gated until
the corresponding matrix row has a signed capture and repeat pass.

## Provisional defaults

Use stock IEC (speed code `00`) whenever a matrix row is not marked `validated`.
For a deliberately enabled experimental link, start at simulator SAFE (20 us/bit),
one 1541, the shortest cable, display blanked for synchronous transfers, and a
single 256-byte-or-smaller block. Retry a CRC/timeout once, then resynchronise and
downgrade; two failures at SAFE abort to stock IEC and release all lines. Do not
promote automatically. FAST (2 us/bit) and MEDIUM (5 us/bit) are *candidate* values
only; they are not hardware guarantees. A successful run caches a profile only for
the exact host/video, drive model, topology and cable identifier.

## Equipment and safety

Use a sacrificial C64/C128, one known-good 1541, 1571 and 1581, switchable REU,
logic analyser (ATN/CLK/DATA/SRQ plus trigger), oscilloscope probes with minimal
capacitance, current-limited supplies, and known IEC cables. Never connect or
disconnect a drive while powered. Record ROM revisions, device numbers, pull-ups,
terminators, cable part/length, temperature, and peripherals (printer, IEC
network adapter, cartridge, user-port devices) for every run.

## Matrix and order

Run each row in isolation, then repeat three times after power-cycle. A row is
validated only after 1,000 clean blocks, 100 injected-fault blocks, no stuck line,
and an independently reviewed capture. Begin with one short cable and one 1541;
add length and loads only after the preceding row passes.

1. Cable lengths: 0.5 m, 1 m, 2 m, 3 m, and the longest available (measure cable
   capacitance if possible); topologies with 1, 2, 3 and 4 daisy-chained drives.
2. Models: homogeneous 1541, 1571, 1581, then mixed 1541+1571, 1541+1581,
   1571+1581 and all three; assign every device number 8–11 and verify passive
   drives never assert CLK/DATA.
3. Hosts: C64 PAL and NTSC; C128 PAL and NTSC at 1 MHz; C128 native 2 MHz with
   blocking VIC-II blanking, and explicit 1↔2 MHz transitions at block boundaries.
4. REU absent/present (record model and size). Repeat with common peripherals
   attached one at a time (printer, cartridge, IEC expansion/SD adapter) and then
   the intended worst-case combination.

For each row capture idle levels, selection, first symbol, ACK/NAK, release,
resynchronisation, abort and fallback. Log cycle/time stamps from the host and
drive where available, plus real edge rise/fall and threshold crossings.

## Failure capture and triage

On any failure stop sending, release outputs, and capture at least 2 ms before and
10 ms after the trigger (longer for timeout). Save analyser native format and CSV,
protocol counters, negotiated profile, raw screen/REU sample, host/drive registers,
CIA/VIA DDR+latches/ATNA, line owners, supply voltage, ambient temperature, ROM
and executable hashes, complete command line, and a monotonic run UUID. Classify
exactly one primary cause: `transport`, `timeout`, `stuck_low`, `contention`,
`crc_noise`, `crc_timing`, `wrong_drive`, `reset`, or `unknown`; retain secondary
observations. Never label an unobserved run hardware-pass.

## Feeding captures back into the simulator

Use `tools/import_hardware_capture.py` (or the documented CSV schema) to convert
each capture into a replay fixture. Calibrate pull-up/capacitance and VIH/VIL from
measured threshold crossings; add measured clock ratio and edge jitter distributions
without replacing existing nominal vectors. Re-run the same payload and fault seed
in `src/tools/iec_simulator.py`; a fixture is accepted only when line ownership,
error class, retry count and final state agree. Keep raw capture hashes and a link
to the checklist row. A mismatch creates a regression test and blocks speed
promotion until explained.

## Exit criteria

W6-E is complete only when every supported configuration has a validated row,
conservative defaults are updated from measured p99 margins, persistent signal
integrity failures downgrade (rather than retry forever), and all failures leave an
idle bus. Until then, ship stock IEC as the only default.
