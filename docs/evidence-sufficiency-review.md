# Wave 5-A — evidence sufficiency review

Status: **not sufficient to pass the Wave 5 evidence gate (2026-07-16).** This
review records what can and cannot be claimed from the indexed artifacts. A
model result or historical source is not promoted to direct VICE evidence.

## Required questions

| Question | Current answer | Evidence class / citation |
|---|---|---|
| Selection uniqueness | **Unknown.** One-1541 transfer completed; mixed 1541+1571/all-three attempts stalled or contended. No 1,000/1,000 topology result. | VICE screen/REU qualified and harness-development-only results; `docs/drive-communication-engineering-record.md` §8.1–8.3; `build/protocol-experiments/results/protocol-matrix-20260716-133431.json` (qualified REU). |
| Polarity, DDR and ATNA | **Unknown at resolved-line level.** Register masks and open-collector model are documented, but no complete truth table with driver attribution exists. | Documentation/model; `docs/drive-communication-engineering-record.md` §§1–2. Snapshot-derived wire logs are explicitly non-evidence (`docs/iec-evidence-index.csv`). |
| Symbol mapping/order | **Partially answered.** MSB-first host plus drive `ROR` produced `$11→$88`; changing receiver to `ROL` yielded a complete one-1541 sum. Mapping for a final 2-bit wire code is not established. | Direct VICE effect observation, one-drive only; engineering record §8.1 and §8.2. |
| Setup/hold margins | **Unknown.** No accepted cycle-stamped line capture or p99/max sweep. | Matrix runs are harness-development-only; direct-monitor results are transport-only (`iec-evidence-index.csv`). |
| Resynchronization interval | **Unknown in VICE.** Simulator/model discusses byte or bounded bursts, but no measured safe prefix. | Model-only discussion in engineering record §4.2.1; `docs/wave4-experiment-results.json` (`evidence: modelled`). |
| ACK semantics | **Partially answered.** Four-edge simulator handshake passes injected cases; physical ACK release/ownership remains unresolved and mixed-drive runs stall. | Simulator-only and qualified REU evidence; `docs/drive-communication-engineering-record.md` §§4.3, 8.1. |
| Host/drive clock conversion | **Nominal values only.** Published/project clock figures and simulator ±100 ppm exist; no correlated host/drive cycle capture. | Engineering record §5 (reference/model), not timing evidence. |
| Screen blanking | **Requirement, not proof.** Blocking DEN routine now exists; pre-blanking runs are invalid for synchronous timing, and blanked matrix runs still did not complete all sums. | Engineering record §4.2.1 and §8.3; matrix artifacts marked harness-development-only. |
| C128 2 MHz behavior | **Untested/unknown.** No accepted native-mode 1/2 MHz transition or VIC-II interaction sweep is indexed. | TODO W4-D remains unchecked; no result in evidence index. |
| Topology/cable speed limits | **Unknown.** RC simulator assumptions (200 pF fixed, 100 pF/m, 1 kΩ, VIH=.7VCC) are explicit but not measured hardware limits. | Engineering record §6; `wave4-experiment-results.json` (modelled). |
| Checksum strength | **Design/model only.** Simulator exercises CRC failures; no measured BER or adversarial fault corpus. | Engineering record §7; simulation result is not physical evidence. |
| Retry policy | **Candidate policy only.** One same-rate retry then resync/slowdown is proposed and model-tested; no VICE fault-injection validation. | Engineering record §7; model-only Wave 4 JSON. |
| Downgrade policy | **Candidate policy only.** Persistent CRC failure should step down; thresholds/hysteresis are not measured. | Engineering record §7; simulation-only. |
| Recovery | **Partial.** Simulator reset/reselect and bus-release cases pass; real mixed-drive recovery and stuck-line boundedness are unproven. | Simulator-only plus failed VICE attempts (§8.2). |
| Stock fallback | **Supported as bootstrap concept, not end-to-end acceptance.** KERNAL/M-R/M-W/M-E works for model identification/upload; fast-mode escape/re-entry under faults is untested. | Engineering record §3 and §8.1; direct VICE functional observation. |

## Unknowns that block W5-C

1. Resolved-line truth tables and exact ATNA/DDR polarity for 1541, 1571 and 1581.
2. A selection token that is electrically passive for non-target drives and
   succeeds across every supported topology.
3. Cycle-stamped setup/hold, ACK-release, drift and resync distributions (p99 and
   max), with screen-on and blocking-blanked variants.
4. Native C128 1 MHz/2 MHz transitions, IRQ/NMI and raster-boundary behavior.
5. Measured cable/load limits and fault rates; simulator RC values are assumptions.
6. Physical checksum/retry/downgrade/recovery outcomes, including stuck-low/high.

## Focused experiments required before protocol specification

- Run a fresh-process, direct-monitor/REU truth-table fixture that records CIA/VIA
  DDR+latch, ATNA, resolved ATN/CLK/DATA/SRQ and per-driver attribution at each
  selection/ACK/release edge; repeat 1541/1571/1581 singly and mixed.
- Reduce selection to one candidate token and verify 1,000/1,000 unique target
  acquisitions with passive non-targets, then interrupt and reselect.
- Add cycle-stamped edge capture and sweep setup/hold/sample/ACK/byte-gap values;
  report min/median/p95/p99/max and a measured resync-safe prefix.
- Repeat timing fixture on C64 PAL/NTSC and C128 native 1/2 MHz with blocking DEN,
  IRQ/NMI and raster-boundary variants.
- Calibrate cable/load model against measured edge threshold crossings and inject
  deterministic versus random faults; measure retry, downgrade and bus-release
  outcomes.

Until these records exist, this document deliberately recommends **no normative
line encoding, timing, or speed constants**.
