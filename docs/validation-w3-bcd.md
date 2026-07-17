# Wave 3 B–D validation

The effect suites in `tests/test_w3_validation.py` validate observable keyboard
events, snapshot structure/fingerprint round-trips, non-empty ordered trace files,
and cycle-stamped I/O/IEC capture with driver attribution. They run without a live
VICE binary so results are deterministic and suitable for regression CI.

Run from this directory:

```text
pytest -q tests/test_w3_validation.py
```

The suite currently covers C128 queue semantics, 1,000 queued key effects,
RESTORE/hold cancellation, structural VSF validation and fingerprint rejection,
trace event ordering, filtered I/O timestamps, IEC driver attribution, and a
fixed-address memory sample comparable to REU observation. Live official-VICE
keyboard matrices, PAL/NTSC/warp permutations, drive snapshot state, and sustained
event-rate/drop testing remain gaps requiring emulator fixtures.
