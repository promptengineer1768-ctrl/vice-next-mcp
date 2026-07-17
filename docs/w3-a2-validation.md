# W3-A2 multi-instance isolation validation

`tests/test_w3_a2_isolation.py` validates the BatchRunner contract with a
deterministic child fixture (no VICE binary required). It covers serial versus
parallel equivalence, per-instance sentinel/artifact isolation, occupied-port
skipping, and two supervisors sharing one base port. Real launches use
`ProcessController` and the same per-instance tree (`<run>/<instance>/generation-*`).

## Capacity guidance

The validation matrix is 1/2/4/8 workers. Start at four workers on a typical
desktop; increase to eight only when aggregate emulator speed remains stable
and memory has at least 1 GB per x64sc/x128 process. Sixteen is an optional
stress tier, not the default. The hard limit is the first tier showing a
cross-talk, port-collision, orphan, or deterministic-result failure.

Run from this project:

```text
python -m pytest tests/test_w3_a2_isolation.py -q
```

Every result carries an instance ID and physical artifact directory. A failed
parallel case must be rerun with the exact serial node command emitted by the
batch runner (`pytest -n 0 <nodeid>`).
## Live process-isolation evidence

`validation/live_w3.py` launches two official VICE SDL2 processes concurrently,
waits for each binary monitor to become ready, records PID/port/artifact-root
leases, and shuts both down. Run it with:

```text
python validation/live_w3.py --executable C:\\tmp\\vice-official-sdl2-3.10\\SDL2VICE-3.10-win64\\x64sc.exe --output validation/results/live-w3-a2 --soak 3
```

The resulting `live-w3.json` is tagged `evidence_class: live`. Keyboard,
snapshot, and I/O effect fields remain explicitly `unavailable` until the
supervised MCP operation layer is present; unit/simulation results must not be
promoted to live evidence.
