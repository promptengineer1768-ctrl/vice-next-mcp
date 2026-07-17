# VICE Next MCP architecture

Status: Wave 1 design contract. The normative wire shapes are in
`schemas/api.schema.json`; this document defines behavior and ownership.

## 1. Decision and boundaries

The first implementation is an **external MCP supervisor/adapter** controlling one
unmodified official VICE child per instance through binary monitor protocol v2.
This keeps HTTP/MCP work outside VICE, contains crashes, and makes official VICE the
reference runtime. An embedded adapter is a possible later transport, but it must
implement the same `ViceTransport` contract and dispatch every VICE access through a
main-thread trap. Request handlers never access VICE globals.

```text
MCP clients -> SupervisorEndpoint -> InstanceRegistry -> InstanceActor
                                                   |-> ProcessController
                                                   |-> ViceTransport
                                                        |-> BinaryMonitorTransport
                                                        `-> EmbeddedTrapTransport (later)
```

`ViceTransport.execute(request) -> completion` is asynchronous, cancellable at the
adapter boundary, and yields correlated replies/events. It exposes `connect`,
`negotiate`, `execute`, `subscribe`, and `close`. Transport results contain raw VICE
error/command/request IDs plus observed state; they never claim a domain effect.

## 2. Ownership and serialization

Each instance has exactly one **InstanceActor** owning its child handle, monitor
socket, request-id allocator, event decoder, lifecycle, operation queue, lease, and
generation. Only that actor reads or writes its monitor stream. This is required
because monitor replies and unsolicited events share a stream and protocol requests
are not evidence that arbitrary VICE state is concurrently safe.

All state-changing operations are FIFO serialized per instance. Initial release also
serializes reads on the same actor. Concurrent reads may be enabled per capability
only after a version/machine-specific stress test proves that separate monitor
connections return correctly correlated, coherent results while the emulator runs;
never on one socket. Supervisor-only registry reads may run concurrently under an
RW lock. Cross-instance actors run independently.

A handler must resolve `{instance_id, generation, lease_token}` once at admission.
It retains that immutable `InstanceRef` through completion. It must reject a missing
or stale generation and must not re-resolve after restart. Mutations require the
active lease token; reads require it by default (a future `shared_read` capability
may relax this explicitly). No process-global current machine, memspace, port,
working directory, or resource map is permitted.

## 3. Instance identity, leases, ports, and launch

`instance_id` is a random UUIDv4 stable for the logical instance. `generation` is a
monotonic unsigned integer incremented before each new child is exposed, including
restart after crash. Every response and event carries both. A lease contains a
random 256-bit bearer token (returned once), experiment ID, issue/expiry times and
generation. Lease expiry/release cancels queued mutations; it does not kill the
instance unless requested. Restart invalidates every token.

The registry records child PID/handle, lifecycle, machine, executable fingerprint,
monitor/MCP ports, config/resource overlay, paths, capabilities and last failure.
One supervisor MCP endpoint is used. Every instance operation has required
`instance_id`, `generation`, and `lease_token`; schemas set `additionalProperties:
false`. (`shared_read`, if ever added, requires a new versioned request schema.) There
is no implicit default instance. Only instance creation/listing and the host-level
capacity probe omit a target; restart/stop/get, batches and experiments target or
create explicitly identified instances.

The supervisor accepts `--base-port` or `VICE_MCP_BASE_PORT` (CLI wins). For worker N,
it searches upward from `base_port + N`, skipping conflicts, independently for the
native-monitor and any per-instance auxiliary/MCP port. Allocation occurs in one
locked `PortAllocator`: bind exclusive loopback reservation sockets first, record
the allocation, spawn the child, and retain the reservation until the child is ready
to bind. Because a child cannot bind a held TCP port, Windows launch uses a brokered
handoff: reservation ownership is transferred to a small launcher that closes the
socket immediately before child creation while the allocator mutex and registry
claim remain held; readiness failure tears down the child and claim. Linux/macOS may
pass inherited descriptors only if VICE supports them; otherwise use the same
handoff. The allocator probes for theft after spawn and never reallocates a claimed
port. Actual ports are returned in metadata. Bind is loopback unless explicitly
configured and authenticated.

Platform launchers share argv construction and readiness semantics:

* Windows first: `CreateProcessW`, job object with kill-on-close, hidden/no modal UI,
  redirected stdout/stderr, explicit executable path and argv, monitor readiness
  probe, and crash exit-code capture.
* Linux: `posix_spawn`, process group/PDEATHSIG wrapper, pipes, readiness probe.
* macOS: `posix_spawn`, process group, pipes, readiness probe.

Shell interpolation is forbidden. Overlays are per-instance directories generated
from allow-listed settings. Startup is successful only after the process remains
alive, the monitor accepts a connection, `vice.info` and register/bank discovery
succeed, and observed machine matches the request.

## 4. Lifecycle and execution state

Lifecycle and execution are separate fields. Lifecycle states are `starting`,
`running`, `stopped`, `monitor-active`, `reset`, `autostarting`, `snapshotting`,
`crashed`, and `shutting-down`. Execution is `unknown`, `running`, `paused`, or
`terminated`.

Allowed lifecycle transitions:

```text
create -> starting -> running <-> stopped <-> monitor-active
                         |           |              |
                         +---------> reset ----------+--> running/stopped
                         +---------> autostarting ----+--> running/stopped
                         +---------> snapshotting ----+--> running/stopped
any live state -> crashed
any nonterminal state -> shutting-down -> stopped
crashed/stopped --restart--> starting (generation + 1)
```

`monitor-active` means monitor command processing has stopped CPU execution. `stopped`
means no operation is advancing emulation: it can be a healthy paused child or the
terminal post-shutdown state, distinguished by execution `paused` versus `terminated`.
Transient states remember their prior stable state. Illegal transitions return
`STATE_CONFLICT`. Reset/autostart/snapshot operations block incompatible requests.
Child exit atomically changes lifecycle to `crashed`, execution to `terminated`,
fails in-flight/queued work, revokes the lease, and emits one crash event.

## 5. Response envelope, time, and errors

Every success and failure uses the schema envelope. Required context is
`instance_id`, `generation`, machine identity, requested and resolved memspace
(`not_applicable` is explicit), execution state, lifecycle, operation ID, and
monotonic observation sequence. `time` always records whether timestamps are
meaningful. When meaningful it includes host cycle and frame; drive operations also
include drive cycle and the correlation quality. Values are observations taken after
the completion predicate, never guessed from wall clock.

Errors are structured and stable: `CHILD_PROCESS_CRASHED` includes pid/exit/signal
and bounded logs; `TIMEOUT` includes phase, deadline, cancellation and last observed
state; `UNSUPPORTED_COMMAND` includes required/missing capability and machine/version;
`VICE_MONITOR_ERROR` includes monitor command, request ID and native error byte.
Also defined are `INVALID_REQUEST`, `INSTANCE_NOT_FOUND`, `STALE_GENERATION`,
`LEASE_REQUIRED`, `LEASE_CONFLICT`, `STATE_CONFLICT`, `TRANSPORT_ERROR`,
`VERIFICATION_FAILED`, and `CANCELLED`. Retriability is explicit. Errors must not be
translated into successful empty results.

## 6. Capabilities

Discovery is performed after monitor negotiation and whenever machine/config changes.
It combines emulator/version, machine, monitor command probes, register/bank lists,
drive inventory, resources, and extension handshake. Capabilities are named,
versioned, scoped (`supervisor`, `instance`, `host`, `drive`), and include constraints
and evidence (`native`, `extension`, or `derived`). Tools remain discoverable at the
MCP server level, but invocation is rejected with `UNSUPPORTED_COMMAND` before any
effect when the target lacks the capability; clients use `vice.capabilities.get` to
render only supported actions. No operation may silently no-op.

## 7. Effect-completion contract

A monitor reply means command acceptance only unless the mapping below says it is the
effect. A successful MCP response is emitted only after its **completion predicate**
is observed. Verification uses bounded emulator-aware polling/events and a deadline.
Timeout returns `TIMEOUT`, never partial success. Cancellation is successful only
after the operation is proven not to be running or reports `effect_may_have_occurred`.

Rules:

* Writes re-read and compare the resolved target unless side effects make reads
  unsafe; those require an extension acknowledgement at the exact emulated cycle.
* Run/pause/step/advance verify execution and cycle/PC deltas. A pause reply alone is
  insufficient.
* File operations use canonical server-side paths. Success requires close/fsync,
  existence, nonzero/structural validation where applicable, and fingerprint.
* Reset/autostart wait for reset/autostart completion event plus observable state.
* Snapshot load additionally compares required host and enabled-drive state probes;
  snapshot save structurally validates modules.
* Keyboard success means the accepted sequence drained at specified frame spacing;
  observable-result predicates, when requested, must also pass.
* Resource/disk/config changes are read back from VICE, not only from overlay files.
* Checkpoint/watch success means registration is readable; hit events carry the
  event's cycle before wait returns.
* Capture/trace stop succeeds only after the writer is closed and validated events
  exist when events were expected.

Each response declares `completion.kind`, evidence, and whether the effect occurred.
Tests inject delayed replies, crashes, stale generations, lost events, and files that
appear late to prove no early success.

## 8. Operation mapping and thread ownership

All rows execute on the instance actor unless marked Supervisor. `Native` command
bytes refer to binary monitor v2. `Ext` means a versioned, capability-negotiated VICE
extension is required; absence is a hard unsupported error.

| MCP operation | Native / extension plan | Completion evidence |
|---|---|---|
| `vice.ping` | Native `0x81` ping | correlated reply + post-state |
| `vice.capabilities.get`, `vice.version.get` | `0x85` VICE info, `0x82` banks, register discovery/probes | negotiated report fingerprint |
| `vice.health.get`, `vice.logs.get` | Supervisor process/pipes; ping for liveness | handle state / bounded log snapshot |
| `vice.run` | `0xAA` exit monitor | running observation and cycle advance |
| `vice.pause` | `0x81` ping/monitor entry | paused observation with cycle sample |
| `vice.step.instruction`, `vice.step.over` | `0x71` advance | paused; exact instruction/PC progress |
| `vice.advance.cycles`, `vice.advance.frames` | Ext deterministic cycle/frame advance | target delta event reached |
| `vice.run.until`, `vice.marker.wait` | `0x12` temporary checkpoint + `0xAA`; Ext for arbitrary predicates | cycle-stamped hit; cleanup verified |
| `vice.registers.list/get/set` | register available/get `0x83`/`0x31`, set `0x32` | returned/read-back named values |
| `vice.memory.read/write` | `0x01`/`0x02` with explicit memspace/bank/side effects | exact bytes; write read-back or Ext ack |
| `vice.resources.list/get/set` | resource get/set `0x51`/`0x52`; list via Ext if native lacks enumeration | returned/read-back value |
| `vice.config.verify` | Supervisor argv/overlay + `0x51` resource reads | requested/effective diff empty |
| `vice.disk.attach/detach/list` | Ext typed disk API (resource fallback only for proven machine/version pairs) | drive inventory/read-back + media fingerprint |
| `vice.drive.configure/state` | `0x51/0x52`, `0x31`, `0x01`; Ext for decoded VIA/CIA/ATNA/routine | effective model/device + coherent sampled state |
| `vice.autostart` | `0xDD` | completion event, load identity, requested run state |
| `vice.screen.capture` | display-get `0x84` | decoded image metadata + bytes fingerprint |
| `vice.screen.text`, `vice.screen.wait` | `0x01` plus dynamic screen/charset resources; Ext stable predicate | dynamic bases and stable-frame predicate |
| `vice.snapshot.save/load` | `0x41` dump / `0x42` undump | file/module validation; load round-trip probes |
| `vice.snapshot.diff` | Supervisor structural parser over validated snapshots | host + every drive module comparison complete |
| `vice.trace.start/stop` | Ext trace writer | writer-open event / closed validated file |
| `vice.checkpoint.*`, `vice.watchpoint.*` | `0x11` get, `0x12` set, `0x13` delete, `0x15` toggle, checkpoint events | registration read-back / cycle-stamped hit |
| `vice.keyboard.type/send/queue` | Ext queued PETSCII/key/matrix scheduler | queue sequence accepted then drained |
| `vice.keyboard.matrix.press/release/hold` | Ext frame-synchronous matrix API | sampled matrix state; release at target frame |
| `vice.keyboard.restore` | Ext RESTORE/NMI API | NMI edge/event at cycle |
| `vice.chip.cia/via/vic` | `0x01` raw I/O read; Ext atomic decoded sample | raw + decoded direction/line sample same cycle |
| `vice.reu.configure` | `0x51/0x52` resources | read-back after required restart |
| `vice.reu.dma` | memory/I/O `0x02`; Ext exact-cycle trigger | DMA completion + memory/status verification |
| `vice.io.capture`, `vice.iec.capture` | Ext cycle-stamped capture engine | stopped writer; ordered records and metadata |
| `vice.cycles.sync` | Ext atomic host/drive clock sample | correlation sample with error bound |
| `vice.memory.capture` | Ext trigger/sampler | requested samples and trigger metadata |
| `vice.experiment.run` | Supervisor orchestration of leased fresh actors | every case terminal; manifest + outputs validated |
| `vice.failure.bundle` | Supervisor + actor reads/files | bundle closed, manifest hashes verify |
| `vice.instance.create/list/get/stop/restart` | Supervisor registry/process controller | readiness; registry/handle terminal; new generation ready |
| `vice.instance.lease/release` | Supervisor atomic registry CAS | token ownership persisted/revoked |
| `vice.batch.run/cancel` | Supervisor bounded worker scheduler | all cases terminal/cancelled; JSON/CSV/JUnit validated |
| `vice.batch.capacity` | Supervisor benchmark | reproducible measurements + recommendation |

Native response/event decoding is transport-thread work; domain validation remains
on the actor. File parsing/hashing may use a bounded worker pool on immutable paths,
but the actor applies its result only if instance ID, generation and operation ID
still match. Extension work inside VICE runs exclusively in a main-thread trap,
except passive event buffering using VICE-approved synchronization.

## 9. Security, observability, and conformance

Paths are confined to per-instance allowed roots; tokens and monitor ports are never
logged. Requests have operation IDs and deadlines. Metrics cover queue time, monitor
latency, verification latency, timeouts, crashes, dropped events and port allocation.
Logs carry instance/generation/operation but redact secrets.

Conformance requires schema validation, lifecycle transition property tests, lease
and stale-generation races, simultaneous port launches, crash/timeout fault
injection, 10,000 mixed main/drive requests without transport error, and an
effect-based test for every mapped operation. Direct-native and adapter results must
match for communication experiments before adapter data is accepted as evidence.
