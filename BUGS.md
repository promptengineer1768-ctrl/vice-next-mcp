# Confirmed Bugs

## Fixed in source; rebuild pending: binary-monitor RESTORE lacked an effect protocol

### Reproduction

1. Start the supplied HeadlessVICE binary and send `0x74` with RESTORE row
   `-3`, column `0`, press/release payloads.
2. The binary monitor returns success for both requests.
3. Run the C64 RESTORE acceptance case and observe that no NMI or prompt
   recovery occurs.

### Root cause

The current monitor protocol acknowledges the command but provides neither a
capability negotiation record nor an effect acknowledgement. A command-level
success response is therefore insufficient evidence that the emulator asserted
the RESTORE/NMI line.

### Fix and remaining verification

`vice/src/monitor/monitor_binary.c` now defines command/response `0x74` as a
strict one-byte RESTORE state protocol. It validates the payload, calls
`machine_set_restore_key()`, and echoes the requested state only after the
machine NMI source has been updated. `vice-next-mcp` now uses that native
protocol rather than encoding RESTORE as a fictitious matrix row. Matrix input
remains unavailable until it receives a separate command number and protocol.

The supplied HeadlessVICE binary predates this source change. It must be
rebuilt and the rebuilt `x64sc.exe` exercised by the real C64 RESTORE test
before this entry can be closed; the old binary's empty success reply remains
insufficient evidence of an NMI.

## Supervisor autostart emits a malformed binary-monitor 0xDD body

### Reproduction

1. Start an instrumented `x64sc` instance through `Supervisor.create(...,
   autostart=<existing PRG or D64>)`.
2. Observe the body constructed in `src/vice_next_mcp/supervisor.py`: it is
   `bytes((run, 0, filename_length)) + filename`.
3. Compare it with VICE `monitor_binary_process_autostart`, which decodes a
   one-byte run flag, a **two-byte** little-endian file index, then a one-byte
   filename length before the filename.

Minimal equivalent failing call:

```python
monitor.call(0xDD, bytes((1, 0, len(path.encode()))) + path.encode())
```

### Expected

The command body is `struct.pack("<BHB", run, file_index, len(filename)) +
filename`, and VICE accepts the autostart request.

### Actual

The three-byte header shifts the filename length into the high byte of the file
index and the first filename byte into the length field. VICE rejects the
request or interprets a malformed filename/index.

### Impact

`Supervisor.create(..., autostart=...)` is unreliable for real emulator
fixtures. Downstream harnesses can fail before application code starts, or
misdiagnose the resulting empty/stale screen as a target-program hang.

### Evidence

- `src/vice_next_mcp/supervisor.py` constructs a three-byte header.
- VICE's `src/monitor/monitor_binary.c` reads `body[0]`, a uint16 at `body[1]`,
  `body[3]`, and the filename beginning at `body[4]`.
- A Compiler 2 live probe using the correct four-byte `<BHB>` encoding entered
  the expected IEC loader path; mounting its D64 with VICE `-8 <image>` also
  produced the expected loader status and stable serial-transfer execution.
