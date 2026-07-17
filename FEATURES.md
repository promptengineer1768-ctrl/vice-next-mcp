# VICE Next MCP feature catalog

Status: Wave 1 integrated API contract. This catalog is normative for operation
arguments, results, capability gates, completion predicates, and effect tests. The
envelopes and routing objects are normative in `schemas/api.schema.json` and
`schemas/request.schema.json`; this document supplies the per-operation schemas that
their `arguments` and `result` extension points intentionally leave open.

## 1. Contract notation and universal rules

`T` means the exact `request.schema.json#/$defs/instanceTarget`. Every instance row
has this exact request shape:

```text
request = {operation: <row operation>, operation_id: uuid, target: T,
           deadline_ms: int[1..3600000], arguments: <row Args>}
```

The four supervisor operations `vice.instance.create`, `vice.instance.list`,
`vice.batch.capacity`, and the orchestration entry points explicitly marked
Supervisor use the exact `supervisorRequest` shape, without `target`. All result
shapes below occupy `api.schema.json#/$defs/successEnvelope/properties/result`.
Every field shown is required unless suffixed `?`; objects are closed (unknown
properties are invalid). `bytes` is base64, `path` is a canonical server-side path,
`hash` is `{algorithm:"sha256", value:hex64}`, and `target_meta` is
`{memspace_id:uint8, memspace_name:string, bank:string|int|null, address_start?:uint16,
address_end?:uint16}`. Integer ranges are inclusive. Lists are arrays of their item
type. Enumerations use `a|b`. Predicate is a tagged closed object appropriate to its
domain (memory/register/I/O/screen/checkpoint); arbitrary executable code is never
accepted.

All successes use `successEnvelope`, including post-predicate context and a
`completion` with `effect_occurred:true` and nonempty evidence. Failures use
`errorEnvelope`. Universal errors are `INVALID_REQUEST`, `INSTANCE_NOT_FOUND`,
`STALE_GENERATION`, `LEASE_REQUIRED`, `LEASE_CONFLICT`, `STATE_CONFLICT`,
`CHILD_PROCESS_CRASHED`, `TIMEOUT`, `UNSUPPORTED_COMMAND`, `VICE_MONITOR_ERROR`,
`TRANSPORT_ERROR`, `VERIFICATION_FAILED`, and `CANCELLED`, with the exact semantics
in DESIGN section 5. “Errors” in tables are additional expected cases or detail
requirements, not replacements for that universal set. A missing capability is
always `UNSUPPORTED_COMMAND` before any effect. No operation silently degrades,
no-ops, or reports success from command acceptance alone.

Capabilities use `api.schema.json#/$defs/capability`. Unless a row says Supervisor,
scope is `instance`; host and drive observations additionally advertise `host` or
`drive` scope. Capability constraints declare supported machines, memspaces, banks,
drive units, limits, modes, and extension version. Configuration changes trigger
rediscovery. Each operation requires the capability named in its row at version 1.

## 2. Core, execution, registers, and memory

| Operations (capability) | Args -> Result schema | Errors / capability rules | Effect-completion predicate | Planned effect-based test |
|---|---|---|---|---|
| `vice.ping` (`vice.ping`) | `{}` -> `{nonce:uuid, vice_reply_id:uint32}` | native ping required | correlated reply followed by coherent post-state observation | delay post-state after reply; assert no success until it arrives |
| `vice.capabilities.get` (`vice.capabilities.get`), `vice.version.get` (`vice.version.get`) | `{}` -> `{capabilities:capability[], fingerprint:hash}`; `{}` -> `{emulator:string, version:string, revision?:string, executable:hash}` | negotiated monitor info required; unavailable actions remain listed with reason | discovery probes complete and report fingerprint is stable | remove extension handshake and assert affected actions reject before mutation |
| `vice.health.get` (`vice.health.get`), `vice.logs.get` (`vice.logs.get`) | `{probe:process|monitor|both}` -> `{pid:uint32, alive:bool, monitor_ready:bool, exit?:{code?:int,signal?:int}}`; `{stream:stdout|stderr|both, since_seq?:uint64, limit:int[1..10000]}` -> `{records:[{seq:uint64,stream:string,text:string,truncated:bool}], next_seq:uint64}` | logs are bounded/redacted; crashed health remains a successful observation, but transport probe failure is not | process handle sampled; monitor probe correlated / requested immutable log snapshot copied | kill child and verify health plus bounded crash logs, with no fabricated liveness |
| `vice.run`, `vice.pause` (same names) | `{}` -> `{previous:running|paused, current:running|paused}` | state conflicts during transient lifecycle | run: running observation and cycle delta; pause: paused observation and stable cycle sample | hold state event after native reply and assert response remains pending |
| `vice.step.instruction`, `vice.step.over` (same names) | `{count:int[1..100000]=1}` -> `{count:uint32, pc_before:uint16, pc_after:uint16, cycles:uint64}` | paused state and CPU scope required | exact instruction count/PC progress and paused terminal state | step branch/JSR fixtures and compare PC/cycles with direct monitor |
| `vice.advance.cycles`, `vice.advance.frames` (same names) | `{count:int[1..2^31-1]}` -> `{requested:uint32, advanced:uint64, terminal:paused}` | extension and deterministic-advance mode required | cycle/frame target event reached exactly; paused terminal state | delay target event and test exact delta at normal and warp speed |
| `vice.run.until` (`vice.run.until`) | `{predicate:Predicate, max_cycles:uint64, leave_checkpoint:bool=false}` -> `{matched:bool, event:event, checkpoint_id?:uint32}` | representable predicates may use native checkpoint; others require extension | cycle-stamped predicate hit, paused state, temporary checkpoint deletion verified | hit ordered markers; missing marker yields TIMEOUT and no leaked checkpoint |
| `vice.registers.list`, `vice.registers.get`, `vice.registers.set` (respective names) | `{memspace:string|uint8}` -> `{target:target_meta, registers:[{id:uint8,name:string,width:int[1..64],writable:bool}]}`; `{memspace, names:string[]}` -> `{target,values:{name:uint64}}`; `{memspace,values:{name:uint64}}` -> same | drive capability is per configured unit; unknown/read-only name invalid | discovery/get response is observation; set re-reads every named value | enumerate host and drives 8-11, set writable flags/PC, compare native reads |
| `vice.memory.read` (`vice.memory.read`) | `{memspace:string|uint8, bank:string|int, address:uint16, length:int[1..65536], side_effects:allow|suppress}` -> `{target:target_meta, data:bytes, length:uint32, hash:hash}` | bank and suppression mode must be advertised; never substitute computer memspace | exact returned bytes plus resolved target metadata | same address in host/drives with distinct sentinels proves no memspace alias |
| `vice.memory.write` (`vice.memory.write`) | `{memspace,bank,address:uint16,data:bytes,side_effects:allow|suppress,verify:read_back|extension_ack}` -> `{target:target_meta,length:uint32,hash:hash,ack_cycle?:uint64}` | unsafe side-effect target requires exact-cycle extension ack | read-back exact bytes or extension ack at exact emulated cycle | delay read-back/ack, inject mismatch, assert no early/false success |
| `vice.marker.wait` (`vice.marker.wait`) | `{predicate:Predicate, timeout_cycles?:uint64, stable_samples:int[1..100]=1}` -> `{matched_value:object,event:event,samples:uint32}` | predicate target capability required | last required cycle-stamped stable sample satisfies predicate | ordered RAM/register/I/O markers return exact cycle; missing marker times out |

## 3. Resources, media, startup, screen, snapshots, and trace

| Operations (capability) | Args -> Result schema | Errors / capability rules | Effect-completion predicate | Planned effect-based test |
|---|---|---|---|---|
| `vice.resources.list`, `vice.resources.get`, `vice.resources.set` (respective names) | `{prefix?:string}` -> `{resources:[{name,type:string,value:scalar,mutable:bool,requires_restart:bool}]}`; `{names:string[]}` -> `{values:{name:scalar}}`; `{values:{name:scalar},restart:never|if_required}` -> `{requested:object,effective:object,restarted:bool}` | enumeration extension required if native lacks it; allow-list only | returned/read-back effective values after any generation-changing restart | set values needing/no restart and compare fresh VICE reads, not overlay |
| `vice.config.verify` (`vice.config.verify`) | `{argv:string[],resources:object}` -> `{requested:object,effective:object,diff:[]}` | argv allow-list; secrets excluded; mismatch is `VERIFICATION_FAILED` | live resource/VICE-info diff is empty | corrupt overlay after launch; verification must fail with precise diff |
| `vice.disk.attach`, `vice.disk.detach`, `vice.disk.list` (respective names) | `{unit:int[8..30],path:path,read_only:bool}` -> `{unit,media:{path,format:string,size:uint64,fingerprint:hash},attached:bool}`; `{unit}` -> `{unit,detached:bool}`; `{}` -> `{drives:[{unit,device_number:uint8,model:string,media?:object}]}` | typed extension unless a machine/version fallback is proven and advertised | inventory read-back matches unit/media hash or absence | attach two same-name images with different hashes, mutate one, detach and verify isolation |
| `vice.drive.configure` (`vice.drive.configure`) | `{unit:int[8..30],model:string,device_number:int[4..30],enabled:bool}` -> `{unit,model,device_number,enabled,restarted:bool}` | model/device constraints per machine; restart policy explicit | effective inventory/resources read back after restart if required | configure units 8-11 distinctly and compare discovered memspaces/inventory |
| `vice.autostart` (`vice.autostart`) | `{path:path,mode:load_only|load_and_run,drive?:int,program_index?:int}` -> `{path,identity:hash,mode,load_address:uint16,end_address:uint16,completion_event:event}` | format/mode constraints advertised | autostart completion event, load identity, bytes, and requested execution state | delayed event test; load-only remains paused and load-and-run reaches marker |
| `vice.screen.capture` (`vice.screen.capture`) | `{format:png|rgba,include_border:bool}` -> `{width:uint32,height:uint32,format:string,data:bytes,fingerprint:hash}` | display-get support for current machine | complete decoded frame and hash after capture observation | known raster fixture pixel/hash comparison; truncated frame must fail |
| `vice.screen.text` (`vice.screen.text`) | `{region?:{x,y,width,height},encoding:unicode|petscii,include_attributes:bool}` -> `{text:string,rows:string[],screen_base:uint16,charset_base:uint16,attributes?:bytes,frame:uint64}` | dynamic layout decoder for machine/video mode required | bases/resources and memory sampled coherently at reported frame | relocate screen/charset and compare visible text before/after mode switch |
| `vice.screen.wait` (`vice.screen.wait`) | `{predicate:{contains?:string,equals?:string,regex?:string,region?:object},stable_frames:int[1..100]}` -> `{matched_text:string,first_frame:uint64,stable_through_frame:uint64,screen_base:uint16}` | regex limits bounded; display-off unsupported unless predicate uses observable RAM mode | predicate holds for required consecutive frames at dynamic base | transient text must not complete; relocated stable READY text must complete |
| `vice.snapshot.save` (`vice.snapshot.save`) | `{path:path,include_disks:bool}` -> `{path,metadata:{machine:string,version:string,modules:[string],include_disks:bool,size:uint64},fingerprint:hash}` | path confined; unsupported disk-module mode rejected | close/fsync, file exists, parser validates required modules, hash computed | file appears before close and corrupt-module injections never report success |
| `vice.snapshot.load` (`vice.snapshot.load`) | `{path:path,include_disks:bool,expected_fingerprint?:hash,compare:{memory:[object],registers:string[],drives:bool}}` -> `{path,fingerprint:hash,comparison:{equal:bool,probes:[object]},completion_event:event}` | fingerprint/module mismatch `VERIFICATION_FAILED` | completion event plus host and enabled-drive round-trip probe equality | unique host/drive/disk sentinels survive save/load; swapped file fails |
| `vice.snapshot.diff` (`vice.snapshot.diff`, Supervisor parser) | `{left:path,right:path}` -> `{equal:bool,host:[object],drives:{unit:[object]},metadata:[object]}` | both inputs must structurally validate | every module classified and comparison manifest complete | alter one host and each drive module; exact paths/offsets reported |
| `vice.trace.start`, `vice.trace.stop` (respective names) | `{path:path,filters?:object}` -> `{trace_id:uuid,path}`; `{trace_id:uuid,expect_events:bool=true}` -> `{path,size:uint64,event_count:uint64,fingerprint:hash}` | one writer per trace ID; extension required | start writer-open event; stop writer closed/fsynced, file parses and has events if expected | delay close and append; success only after final event is parseable |

## 4. Checkpoints, keyboard, chips, and REU

| Operations (capability) | Args -> Result schema | Errors / capability rules | Effect-completion predicate | Planned effect-based test |
|---|---|---|---|---|
| `vice.checkpoint.list`, `vice.checkpoint.set`, `vice.checkpoint.delete`, `vice.checkpoint.toggle`, `vice.watchpoint.list`, `vice.watchpoint.set`, `vice.watchpoint.delete`, `vice.watchpoint.toggle` (corresponding name) | list `{}` -> `{registrations:[Registration]}`; set `{memspace,start:uint16,end:uint16,access:exec|load|store,enabled:bool,temporary:bool}` -> `{registration:Registration}`; delete `{id:uint32}` -> `{id,absent:bool}`; toggle `{id,enabled:bool}` -> `{registration}`; `Registration={id:uint32,target:target_meta,start,end,access,enabled,temporary}` | memspace/access constraints apply; missing ID invalid | registration read-back/absence; hits are `event` with access/address/value and cycle-stamped context before waiter returns | create/read/toggle/hit/delete on host and drive; lost event causes timeout, never success |
| `vice.keyboard.type` (`vice.keyboard.type`) | `{text:string,encoding:unicode|petscii,spacing_frames:uint16,modifiers?:[shift|control|commodore]}` -> `{queue:QueueStatus,observable?:object}` | character map/machine constraints; paused behavior explicitly advertised | all translated events consumed at spacing and queue drained | 1,000 chars normal/warp with zero drops/duplicates; screen/RAM oracle |
| `vice.keyboard.send` (`vice.keyboard.send`) | `{events:[{mode:petscii|key|matrix,value:object,modifiers?:string[],hold_frames?:uint16}],spacing_frames:uint16,observable_predicate?:Predicate}` -> `{queue:QueueStatus,observable?:object}` | extension scheduler; unsupported keys rejected atomically before enqueue | queue drained, all keys released, optional observable predicate passes | replay harness streams with zero client delay in C64/C128 and screen-off fixture |
| `vice.keyboard.queue.get`, `vice.keyboard.queue.drain` (`vice.keyboard.queue`) | `{queue_id?:uuid}` -> `{queue:QueueStatus}`; `{queue_id:uuid}` -> `{queue:QueueStatus}` where `QueueStatus={id:uuid,accepted:uint32,consumed:uint32,pending:uint32,first_frame?:uint64,last_frame?:uint64,drained:bool,all_released:bool}` | queue IDs instance/generation scoped | get is coherent observation; drain waits for pending=0 and all_released | cancel midway; drain cannot succeed while held key or pending item remains |
| `vice.keyboard.matrix.press`, `vice.keyboard.matrix.release`, `vice.keyboard.matrix.hold` (`vice.keyboard.matrix`) | press/release `{row:uint8,column:uint8,modifiers?:string[]}` -> `{row,column,pressed:bool,frame:uint64}`; hold adds `{frames:uint32}` -> `{row,column,pressed:false,down_frame:uint64,up_frame:uint64}` | matrix bounds and model map advertised | sampled matrix state; hold release exactly at target frame and final all-up | every coordinate/name equivalence, exact duration, no stuck bits |
| `vice.keyboard.restore` (`vice.keyboard.restore`) | `{hold_frames:uint32=1}` -> `{nmi_cycle:uint64,down_frame:uint64,up_frame:uint64,count:uint32}` | machine must expose RESTORE/NMI | exactly one NMI edge/event and released terminal state | running fixture checks vector/PC, one NMI, and FLAG/matrix cleanup |
| `vice.chip.cia`, `vice.chip.via`, `vice.chip.vic` (same names) | `{unit?:int,index?:uint8}` -> `{chip:string,target:target_meta,cycle:uint64,raw:{name:uint8},decoded:{ports:[{name,latch:uint8,ddr:uint8,pins:uint8,lines:{name:high|low|input}}],state:object}}` | chip/unit inventory scoped; atomic decode extension required | raw and decoded values from same emulated-cycle sample | toggle DDR/latches and verify decoded inputs/outputs and IEC lines at cycle |
| `vice.reu.configure` (`vice.reu.configure`) | `{enabled:bool,size_kib:int,base?:uint32}` -> `{enabled,size_kib,base?:uint32,restarted:bool}` | REU machine/size constraints; required restart explicit | live resources and REU register presence read back | configure each size, restart, verify resource/register/memory aperture |
| `vice.reu.dma` (`vice.reu.dma`) | `{direction:c64_to_reu|reu_to_c64|swap|verify,c64_address:uint16,reu_address:uint32,length:int[1..65536],trigger:immediate|cycle,cycle?:uint64}` -> `{status:uint8,transferred:uint32,completion_cycle:uint64,source_hash:hash,destination_hash:hash}` | exact-cycle trigger requires extension; bounds validated before effect | DMA completion/status plus destination memory and length verification | all directions with boundary/wrap cases; delayed completion and mismatch fail |

## 5. Cycle capture and drive diagnostics

| Operations (capability) | Args -> Result schema | Errors / capability rules | Effect-completion predicate | Planned effect-based test |
|---|---|---|---|---|
| `vice.io.capture` (`vice.io.capture`) | `{targets:[{memspace,address_start:uint16,address_end:uint16,access:read|write|both}],trigger:Predicate,pre_cycles:uint64,post_cycles:uint64,path?:path}` -> `{capture_id:uuid,records:[{cycle:uint64,target:target_meta,address:uint16,access:string,value:uint8,line_changes?:object}],path?:path,fingerprint?:hash}` | cycle capture extension and target constraints | trigger found; requested windows complete; ordered records validated; optional file closed | known read/write train verifies order, pre/post bounds, values, and delayed writer close |
| `vice.iec.capture` (`vice.iec.capture`) | `{units:int[],trigger:Predicate,pre_cycles:uint64,post_cycles:uint64,path?:path}` -> `{records:[{host_cycle:uint64,drive_cycles:{unit:uint64},lines:{atn,clk,data,srq:high|low},drivers:{line:[string]},registers:{chip:{latch:uint8,ddr:uint8}},markers:[contention|timeout]}],path?:path,fingerprint?:hash}` | IEC extension; SRQ only where available and otherwise explicit unavailable constraint | atomic/bounded decoded records span windows and file validates | TALK/LISTEN exchange compared to raw CIA/VIA samples; forced contention marker |
| `vice.drive.state` (`vice.drive.state`) | `{unit:int}` -> `{unit,model,device_number:uint8,clock:uint64,cpu:{registers:object},ports:object,atna:bool,active_rom_routine?:{name,address:uint16},iec_outputs:object,sample_quality:string}` | configured drive and decode extension for coherent state | all fields sampled atomically or with advertised error bound | distinct states on drives 8-11; compare raw monitor registers/RAM/ports |
| `vice.cycles.sync` (`vice.cycles.sync`) | `{units:int[],samples:int[1..1000]}` -> `{samples:[{host_cycle:uint64,drive_cycles:{unit:uint64},quality:atomic|bounded,error_bound_cycles:uint32}]}` | atomic extension or bounded mode explicitly supported | requested correlated samples collected with measured bound | deterministic loops establish ratios; injected delay widens bound, never claims atomic |
| `vice.memory.capture` (`vice.memory.capture`) | `{targets:[{memspace,bank,address:uint16,length:uint32}],mode:periodic|triggered,period_cycles?:uint64,trigger?:Predicate,count:uint32,path?:path}` -> `{samples:[{host_cycle:uint64,drive_cycle?:uint64,target:target_meta,data:bytes,hash:hash}],path?:path,fingerprint?:hash}` | sampler extension; aggregate byte/count limits advertised | exact sample count/trigger and ordered timestamps; optional file validates | changing counter and REU-DMA fixture compare every sample/value/cycle |

## 6. Isolation, experiments, failure evidence, and batching

Supervisor schemas below still use the W1-B `supervisorRequest` envelope. Because
`request.schema.json` currently enumerates only create/list/capacity as supervisor
operations, `vice.experiment.run`, `vice.batch.run`, and `vice.batch.cancel` are
implemented as instance-targeted orchestration in version 1: the target is the
leased coordinator instance, while cases always create fresh child instances. This
avoids silently widening W1-B routing. A future supervisor-only v2 requires an
explicit schema revision.

| Operations (capability) | Args -> Result schema | Errors / capability rules | Effect-completion predicate | Planned effect-based test |
|---|---|---|---|---|
| `vice.instance.create` (`vice.instance.create`, Supervisor) | `{machine:string,executable?:path,resources?:object,experiment_id?:string}` -> exact `api.schema.json#/$defs/instanceMetadata` plus `{lease_token:string}` | capacity/path/config validation; startup failures are structured | child alive, monitor ready, info/register/bank probes succeed, observed machine matches | concurrent launches with occupied ports; none succeeds before readiness |
| `vice.instance.list` (`vice.instance.list`, Supervisor) | `{include_terminal:bool=false}` -> `{instances:[instanceMetadata]}` | registry read only; tokens never returned | atomic registry snapshot | crash/restart race returns coherent generations and states |
| `vice.instance.get`, `vice.instance.stop`, `vice.instance.restart` (respective names) | `{}` -> `{instance:instanceMetadata}`; `{force_after_ms?:uint32}` -> `{instance_id,generation,execution_state:terminated}`; `{resources?:object}` -> `{instance:instanceMetadata,lease_token:string}` | restart invalidates token and increments generation; stop idempotency is explicit observation only | registry/handle terminal; restart generation incremented and full readiness gate passed | kill/restart and assert stale requests rejected; no success while old handle lives |
| `vice.instance.lease`, `vice.instance.release` (respective names) | `{experiment_id:string,ttl_ms:int[1..86400000]}` -> `{lease_token:string,expires_at:string,generation:uint64}`; `{}` -> `{released:bool}` | atomic CAS, conflicts expose owner metadata but never token | ownership persisted / token revoked and queued mutations cancelled | simultaneous lease CAS yields one winner; released token cannot mutate |
| `vice.experiment.run` (`vice.experiment.run`) | `{cases:[{case_id:string,machine:string,resources:object,steps:[{operation:string,arguments:object}]}],outputs:{json:path,csv?:path},continue_on_error:bool}` -> `{cases:[CaseResult],manifest:path,files:[{path,hash}],reproduction_commands:{case_id:string}}` | coordinator lease; nested operations capability-checked before each case | every fresh case terminal; provenance manifest and closed/parsed outputs validate | variant matrix with one crash: deterministic IDs, isolation, terminal rows, replay parity |
| `vice.failure.bundle` (`vice.failure.bundle`) | `{reason:string,memory_windows:[object],include_screen:bool=true,include_resources:bool=true,event_limit:uint32}` -> `{path:path,manifest:[{name,size:uint64,hash}],fingerprint:hash,partial:[string]}` | best-effort components recorded as partial; bundle failure itself never hidden | archive closed and every manifest hash verifies | timeout/crash fixture validates logs/registers/windows/screen/events and redaction |
| `vice.batch.run` (`vice.batch.run`) | `{cases:[Case],worker_count:uint16,policy:fail_fast|continue,outputs:{json:path,csv?:path,junit?:path}}` -> `{batch_id:uuid,cases:[CaseResult],progress:{terminal,total:uint32},files:[{path,hash}],serial_reproduction:{case_id:string}}` | coordinator lease; worker count bounded by capacity; deterministic unique case IDs | every case terminal/cancelled and each requested aggregate closes/parses | concurrency bound instrumentation, fail-fast/continue, stable ordering and serial replay |
| `vice.batch.cancel` (`vice.batch.cancel`) | `{batch_id:uuid}` -> `{batch_id,cancelled:uint32,terminal:uint32,effect_may_have_occurred_cases:[string]}` | only owning generation/lease; unknown batch invalid | scheduler stopped admitting work; queued cases cancelled; running cases terminal or explicitly uncertain | cancel under load and prove no new starts after acknowledgement |
| `vice.batch.capacity` (`vice.batch.capacity`, Supervisor) | `{machines:string[],max_workers:uint16,duration_ms:uint32}` -> `{measurements:[{workers:uint16,throughput:number,p95_ms:number,error_rate:number,cpu:number,memory_bytes:uint64}],recommended_workers:uint16,reproduction_command:string}` | benchmark allow-list and resource ceiling; no instance target | all benchmark workers terminal; measurements complete and recommendation rule applied | synthetic saturation produces repeatable recommendation and no orphan processes |

`Case` is closed `{case_id:string,machine:string,resources:object,steps:[{operation:
string,arguments:object}]}`. `CaseResult` is closed `{case_id:string,status:
passed|failed|cancelled,started_at:string,ended_at:string,instance_id:uuid,
generation:uint64,error?:api.error,artifacts:[{path,hash}]}`.

## 7. No-early-success conformance gate

The catalog contains 75 named operations. The implementation must maintain a
machine-readable conformance matrix generated from these rows. For every operation,
the test suite must (1) validate its request and result schema, (2) remove its
capability and prove rejection happens before transport dispatch, (3) inject every
feature-specific failure, and (4) hold back the last item of completion evidence and
prove that no success response is observable. It then releases valid evidence and
expects exactly one success. File tests additionally expose an early/truncated file;
event tests delay/drop the event; read-back tests inject mismatches; and process tests
delay readiness or termination.

The Wave 1 gate is satisfied by design only if review can trace every success to the
predicate in its row and to the universal completion envelope. A native monitor
reply is never sufficient evidence except where the row explicitly defines the
reply itself as the effect (ping/read-only discovery), and even those rows require a
coherent observation or completed report. W2/W3 must not mark any conformance row
implemented until its delayed-evidence test passes.
