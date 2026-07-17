# Wave 5-B — candidate protocol comparison

This is a decision aid, not a final protocol specification. Timing numbers are
omitted where no direct p99/max measurement exists; model values are labelled as
such and must not be treated as budgets.

| Candidate | Throughput expectation | Margin / constraints | Implementation and compatibility | Fault recovery |
|---|---|---|---|---|
| Synchronous 2-bit bursts | Highest symbol rate in principle (four symbols/byte). No defensible bytes/s figure yet. | Sensitive to host/drive rate, phase drift, badlines, IRQ/DMA and cable rise time. Engineering estimate notes ~1.5% 1541/C64 rate difference and ~10-byte uncorrected window, but this is historical/model context, not a project measurement (`drive-communication-engineering-record.md` §4.2.1). | Small tight loops, but requires per-machine timing tables, screen blanking and clock calibration. C64/C128 2 MHz and mixed drives unvalidated. | Needs explicit resync and bounded abort; persistent timing faults require fallback. No physical fault corpus yet. |
| Asynchronous/handshaked 2-bit | Lower raw rate due to ACK edges; exact rate is unmeasured. | Frequent edge acknowledgement removes long-term drift and tolerates mixed clocks better. Still depends on polarity/ATNA and line-release correctness, currently unresolved. | Larger state machine but portable across C64/C128 and drive models if line primitives are proven. Four-edge simulator handshake passes model fault cases. | Best current recovery story in simulation (retry, reset/reselect, duplicate suppression), but not accepted as VICE physical evidence. |
| Hybrid: async control + negotiated synchronous bursts | Potentially near-sync payload rate while limiting drift with byte/block resync. No measured burst length or timing budget. | Negotiation/control can establish polarity, target and rate; payload remains exposed to display/IRQ/cable margins. Requires measured resync cadence and safe fallback. | Most complex: two modes, negotiation, calibration, burst scheduler and rollback. Offers broadest compatibility if evidence supports it. | Can fall back to async or stock IEC; downgrade hysteresis and exact thresholds remain unknown. |

## Timing-budget rule

No candidate currently has a justified worst-case budget. The required calculation
after focused capture is:

`budget = p99(or max) observed edge/handler delay + clock-drift over burst + cable rise-time margin + explicit safety margin`.

The safety margin must be recorded as a chosen factor (for example, 20% of the
measured limiting interval), not silently inferred. The current simulator's FAST /
MEDIUM / SAFE values (2/5/20 µs per bit) and RC parameters are model assumptions
(`docs/drive-communication-engineering-record.md` §6; `docs/wave4-experiment-results.json`)
and therefore are **not** timing budgets.

## Provisional recommendation (non-normative)

Keep the hybrid architecture as the experiment target: use stock IEC for
selection, an asynchronous handshake for negotiation/control and recovery, and
enable synchronous bursts only after measured calibration proves a safe prefix.
This is an engineering hypothesis, not a protocol decision. If truth-table or
timing experiments fail, retain the asynchronous path and stock fallback rather
than freezing synchronous constants.

## Evidence gaps that affect the comparison

- No accepted multi-drive selection result (all-three and 1541+1571 attempts
  stall/contend).
- No direct cycle-stamped I/O capture, p99/max setup/hold, or measured drift.
- No C128 native 2 MHz evidence.
- No physical cable/noise calibration or fault-injection distribution.
- Existing simulator passes are useful for finding deadlocks and state-machine
  bugs, but are `simulator-only`, as indexed in `docs/iec-evidence-index.csv`.

Therefore W5-B is complete as a comparison, while the Wave 5 evidence gate stays
open and W5-C must not write normative timing or line-ownership requirements.
