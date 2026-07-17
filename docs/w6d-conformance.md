# W6-D VICE conformance/regression matrix

`validation/conformance_matrix.py` exercises the final reference protocol over
20 Wave-4 configurations: C64 PAL/NTSC and C128 1/2 MHz hosts, with 1541,
1571, 1581, mixed two-drive, and mixed three-drive topologies. Each case sends
at least 10,000 deterministic 32-byte blocks by default and runs a seeded
randomized transient-fault cohort. The runner checks payload delivery,
retry/recovery, transition trace activity, and that all open-collector lines
are released at completion.

Run from this directory:

```text
python validation/conformance_matrix.py --blocks 10000 --faults 100 --seed 109
```

The JSON report is `validation/results/w6d_conformance.json` and includes the
exact command, seed, case parameters, model trace counts, and a report hash.
Results currently carry `evidence: "modelled"`: no live VICE monitor was
available for this run, so these are reference-model regression results rather
than measured emulator timing. A future direct-monitor run may reuse the same
case IDs and schema, setting `evidence` to `measured` and adding captured
cycle-stamped transitions. Modelled and measured records must not be merged.
