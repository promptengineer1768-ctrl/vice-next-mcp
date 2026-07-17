# Companion harness compatibility audit (W1-A)

Status: static audit complete on 2026-07-16. Paths are relative to `C:\Users\me\Documents\Coding Projects`. The YAML block is the machine-readable compatibility matrix. `new_server` is `pending-w2` throughout because Wave 2 has not built it.

## Machine-readable matrix

```yaml
schema_version: 1
classifications: [emulator-requirement, mcp-bug, harness-bug, timing-dependency, obsolete-behavior]
new_server_status: pending-w2
items:
  - id: transport-retry
    source: compiler2/tools/vice_harness.py:88-114
    workaround: three retries for transient HTTP/JSON failures, 150 ms apart
    classification: mcp-bug
    dependents: {count: 6, names: [test_keyboard_path_types_command_and_gets_basic_output, test_release_loader_installs_georam_and_answers_basic_query, test_irq_jiffy_clock_advances_while_machine_runs, test_device_save_and_load_round_trip, test_x64sc_version_is_reported, test_xplus4_version_is_reported]}
    reproduction: {existing_mcp: "pytest compiler2/tests/hardware/test_keyboard.py -q --count=100", native_monitor: "repeat 10000 connect/read requests using multi/tests/vice_binary_monitor.py", new_server: pending-w2}
    observed: {existing_mcp: "client catches HTTPError, URLError, TimeoutError and JSONDecodeError without a structured failure identity", native_monitor: "W0-B: 10000 operations each on x64sc and x128, zero errors", new_server: pending-w2}
    desired: one correlated response or structured transport failure; no client retry
    proposed_effect_test: 10000 fragmented mixed requests; exactly one correlated response each and zero client retries

  - id: per-character-spacing
    source: compiler2/tools/vice_harness.py:133-140
    workaround: split text, sleep 120 ms per character and 1 s after CR/LF
    classification: timing-dependency
    dependents: {count: 4, names: [test_keyboard_path_types_command_and_gets_basic_output, test_release_loader_installs_georam_and_answers_basic_query, test_device_save_and_load_round_trip, generate_vice_fixtures]}
    reproduction: {existing_mcp: "pytest compiler2/tests/hardware/test_keyboard.py -q", native_monitor: "unsupported stimulus: binary monitor has no keyboard command; use it only to inspect screen/RAM", new_server: pending-w2}
    observed: {existing_mcp: "protocol tests accept RPC response but do not prove characters were consumed", native_monitor: unsupported-stimulus, new_server: pending-w2}
    desired: frame-scheduled sequence, drain acknowledgement, observable effect
    proposed_effect_test: type a 1000-character numbered BASIC program bulk and per-character at normal/warp; compare screen and tokenized RAM byte-for-byte

  - id: explicit-run-after-keyboard
    source: compiler2/tools/vice_harness.py:167-183
    workaround: call execution.run after submission and sleep 500 ms
    classification: mcp-bug
    dependents: {count: 4, names: [test_keyboard_path_types_command_and_gets_basic_output, test_release_loader_installs_georam_and_answers_basic_query, test_device_save_and_load_round_trip, test_irq_jiffy_clock_advances_while_machine_runs]}
    reproduction: {existing_mcp: "remove line 170 then pytest compiler2/tests/hardware/test_keyboard.py -q", native_monitor: "monitor resume is explicit but monitor exposes no keyboard stimulus", new_server: pending-w2}
    observed: {existing_mcp: "successful keyboard request can leave input unusable while stopped", native_monitor: "execution state is explicit", new_server: pending-w2}
    desired: advance/run as requested or reject paused state
    proposed_effect_test: submit while running and paused; require completed effect or paused-state error without client run

  - id: stable-ready-read-tolerance
    source: compiler2/tools/vice_harness.py:200-229
    workaround: require repeated identical READY screens and tolerate read failures
    classification: timing-dependency
    dependents: {count: 5, names: [test_keyboard_path_types_command_and_gets_basic_output, test_release_loader_installs_georam_and_answers_basic_query, test_device_save_and_load_round_trip, create_snapshot, generate_vice_fixtures]}
    reproduction: {existing_mcp: "pytest compiler2/tests/hardware/test_keyboard.py -q --count=100", native_monitor: "read screen RAM per stopped frame and compare cycle stamps", new_server: pending-w2}
    observed: {existing_mcp: "polling can see torn/unavailable screens", native_monitor: "reads are coherent at explicit monitor-stop points but no stable-screen predicate exists", new_server: pending-w2}
    desired: atomic screen predicate with stable-frame count
    proposed_effect_test: animate writes and wait for READY stable for three frames; no partial frame or swallowed error may pass

  - id: snapshot-fingerprint-contract
    source: compiler2/tools/vice_snapshot.py:103-186
    workaround: hash artifact, profile, mailbox ABI and ROMs; preserve external metadata
    classification: emulator-requirement
    dependents: {count: 2, names: [test_snapshot_fingerprint_changes_with_mailbox_abi, test_generated_snapshot_contract_is_fingerprinted]}
    reproduction: {existing_mcp: "pytest compiler2/tests/hardware/test_vice_infrastructure.py -k snapshot -q", native_monitor: "save VSF, vary one contract input, validate before restore", new_server: pending-w2}
    observed: {existing_mcp: "server does not own full compatibility contract", native_monitor: "VSF lacks companion artifact/mailbox contract", new_server: pending-w2}
    desired: completed file identity and fingerprint; reject incompatible restore before mutation
    proposed_effect_test: vary every input independently; assert rejection and unchanged RAM/register/disk state

  - id: autostart-without-run
    source: basic v3/tests/vice_keyboard_injection.py:124-141
    workaround: autostart run=false, verify BASIC RAM/READY, then type RUN and verify screen/program bytes
    classification: emulator-requirement
    dependents: {count: 1, names: [basic-v3/tests/vice_keyboard_injection.py::main]}
    reproduction: {existing_mcp: "python 'basic v3/tests/vice_keyboard_injection.py' --help", native_monitor: "autostart without run; inspect $0801 and screen; keyboard stimulus unsupported", new_server: pending-w2}
    observed: {existing_mcp: "effect proof lives in companion, not protocol suite", native_monitor: "can inspect load/effect, not inject keys", new_server: pending-w2}
    desired: explicit loaded/running completion state and separately observable keyboard completion
    proposed_effect_test: assert BASIC bytes before RUN; then RUN changes screen and marker

  - id: matrix-transition-run-hold
    source: basic v3/tests/vice_keyboard_injection.py:83-94
    workaround: separate press/release, execution.run after each, approximately 180 ms hold
    classification: mcp-bug
    dependents: {count: 1, names: [basic-v3/tests/vice_keyboard_injection.py::main]}
    reproduction: {existing_mcp: "python 'basic v3/tests/vice_keyboard_injection.py' --help", native_monitor: "unsupported stimulus", new_server: pending-w2}
    observed: {existing_mcp: "request success does not guarantee transition duration or release", native_monitor: unsupported-stimulus, new_server: pending-w2}
    desired: emulated-frame press/hold/release with drain and all-keys-up state
    proposed_effect_test: scan CIA matrix every frame; exact row/column low for N frames and released afterward

  - id: kernal-buffer-fallback
    source: ti emul/tests/vice_harness.py:292-310
    workaround: on keyboard.type failure inject chunks of eight at $0277 with count at $00C6
    classification: mcp-bug
    dependents: {count: 24, names: [test_gpl_cart_menu_speed_and_launch, test_system_disk_enters_editor_and_accepts_basic_commands_and_lines, test_run_compiles_and_executes_for_next_print_on_real_c64, test_production_noel_is_faster_than_stock_c64_basic_ntsc, test_restore_abandons_running_program_and_reinitializes_editor, plus_19_other_ti_hardware_tests]}
    reproduction: {existing_mcp: "pytest 'ti emul/tests/hardware/test_editor_shell_vice.py' -q", native_monitor: "write $0277/$00c6 in chunks <=8, resume, inspect effect", new_server: pending-w2}
    observed: {existing_mcp: "hidden fallback bypasses matrix and supports a limited code map", native_monitor: "direct RAM injection deliberately bypasses matrix", new_server: pending-w2}
    desired: reliable keyboard path; separate explicit debug-only KERNAL-buffer tool
    proposed_effect_test: induced keyboard failure must not mutate $0277; separately validate labeled debug injection

  - id: sys-idle-pc-retry
    source: ti emul/tests/vice_harness.py:203-229
    workaround: retype SYS once per second when PC remains at known BASIC idle PCs
    classification: timing-dependency
    dependents: {count: 3, names: [test_under_kernal_ram_and_physical_vectors_on_real_c64, test_scroll_meets_both_video_standards_and_preserves_planes, test_ti_screen_charset_color_and_character_calls_in_vice]}
    reproduction: {existing_mcp: "pytest 'ti emul/tests/hardware/test_under_kernal_vice.py' -q", native_monitor: "inject via KERNAL buffer; resume; poll PC and marker", new_server: pending-w2}
    observed: {existing_mcp: "accepted input may remain unconsumed at BASIC idle", native_monitor: "can diagnose PC/marker but not provide keyboard stimulus", new_server: pending-w2}
    desired: drain acknowledgement or a reason delivery stalled
    proposed_effect_test: 100 runs from each idle PC; exactly one SYS and one marker transition

  - id: dynamic-screen-io-bank
    source: ti emul/tests/vice_harness.py:251-267
    workaround: read CIA2/VIC-II from io bank, compute screen base, read ram bank
    classification: emulator-requirement
    dependents: {count: 20, names: [test_ti_startup_and_cartridge_screens_are_layout_locked, test_gpl_cart_menu_speed_and_launch, test_restore_abandons_running_program_and_reinitializes_editor, plus_17_screen_waiting_tests]}
    reproduction: {existing_mcp: "pytest 'ti emul/tests/hardware/test_editor_shell_vice.py' -q", native_monitor: "read io:$dd00/io:$d018 then ram:<computed-base>", new_server: pending-w2}
    observed: {existing_mcp: "CPU-visible reads may return RAM shadows", native_monitor: "bank-qualified reads distinguish I/O/RAM", new_server: pending-w2}
    desired: atomic decoded screen including registers, base, bank and dimensions
    proposed_effect_test: every VIC bank/base with I/O visible/hidden; compare decoded text to raw banked reads

  - id: memory-under-io-rom
    source: ti emul/tests/vice_harness.py:87-103,135-139
    workaround: distinguish CPU-visible memory from explicit ram/io banks
    classification: emulator-requirement
    dependents: {count: 2, names: [test_under_kernal_ram_and_physical_vectors_on_real_c64, test_vice_memory_views_switch_between_ram_io_and_rom]}
    reproduction: {existing_mcp: "pytest 'ti emul/tests/hardware/test_under_kernal_vice.py' 'python/tests/vice/test_memory_views_vice.py' -q", native_monitor: "read same $d000/$e000 address from cpu/ram/io/rom", new_server: pending-w2}
    observed: {existing_mcp: "clients normalize optional bank and multiple response shapes", native_monitor: "bank values legitimately differ", new_server: pending-w2}
    desired: every response names machine, memspace, bank and mapping
    proposed_effect_test: distinct sentinels under I/O/ROM; verify all qualified reads

  - id: warm-snapshot-private-copy
    source: ti emul/tests/vice_harness.py:390-429,508-549
    workaround: artifact-named archive, stage, validate, and make private session snapshot
    classification: emulator-requirement
    dependents: {count: 14, names: [test_bundled_game_loads_and_lists_from_a_clean_base, test_bundled_game_reaches_its_running_program, plus_12_fixture_consumers]}
    reproduction: {existing_mcp: "pytest 'ti emul/tests/hardware/test_demo_games_vice.py' -q", native_monitor: "unique VSF paths; compare RAM/register/disk sentinels", new_server: pending-w2}
    observed: {existing_mcp: "stable managed names can alias stale/shared files", native_monitor: "path isolation remains caller responsibility", new_server: pending-w2}
    desired: per-instance paths and structural/fingerprint validation
    proposed_effect_test: four concurrent same-logical-name saves with unique sentinels; zero cross-restore

  - id: completion-markers
    source: ti emul/tests/vice_harness.py:203-212; detection/tests/vice_harness.py:266-284; compressor/tests/expansion_vice_harness.py:223-245
    workaround: poll completion/result memory instead of trusting sleep or request success
    classification: emulator-requirement
    dependents: {count: 43, names: [test_baseline_detection_finishes, test_real_memory_expansion_detection, test_reu_fetch_stash_and_no_false_ramdrive, test_forward_machine_code_execution, test_backward_overlap_decompression, test_multi_segment_decompression, plus_37_profile_cases]}
    reproduction: {existing_mcp: "pytest detection/tests/test_detection.py compressor/tests/test_vice_smoke_forward.py -q", native_monitor: "resume; poll fixture marker with cycle-stamped reads", new_server: pending-w2}
    observed: {existing_mcp: "marker is the real oracle", native_monitor: "reliable observation but client polling", new_server: pending-w2}
    desired: server-side marker predicate with final evidence
    proposed_effect_test: ordered markers return exact value/cycle; missing marker returns timeout failure bundle

  - id: python-interactive-delays
    source: python/tests/vice_harness.py:103-135
    workaround: explicit input delay plus screen/memory predicates for menus, LOAD/RUN and REPL
    classification: timing-dependency
    dependents: {count: 24, names: [test_repl_typed_program_run_prints_result, test_repl_typed_multiline_function_program, test_convert_roundtrips_seq_and_prg_files, test_vice_system_disk_json_loads_theme_catalog, test_system_disk_boot_help_and_course_flow, plus_19_named_tests]}
    reproduction: {existing_mcp: "pytest python/tests/vice -q", native_monitor: "observe screen/RAM; keyboard stimulus unsupported", new_server: pending-w2}
    observed: {existing_mcp: "24 tests depend on delay and effect predicates", native_monitor: unsupported-stimulus, new_server: pending-w2}
    desired: queued frame spacing, drain acknowledgement, composable waits
    proposed_effect_test: replay all streams with zero client delay at normal/warp; identical screen/RAM/disk effects

  - id: direct-prg-ram-injection
    source: detection/tests/vice_harness.py:237-245; compressor/tests/expansion_vice_harness.py:207-220
    workaround: pause, write PRG directly to RAM, run, type SYS; avoid autostart
    classification: emulator-requirement
    dependents: {count: 19, names: [test_baseline_detection_finishes, test_extended_result_and_jump_table_are_installed, test_basic_run_entry_mode, test_ram_under_io_segment_is_written_and_final_cpu_port_applied, plus_15_profile_cases]}
    reproduction: {existing_mcp: "pytest detection/tests compressor/tests/test_vice_* -q", native_monitor: "stop; write payload; resume; execute; inspect marker", new_server: pending-w2}
    observed: {existing_mcp: "avoids autostart side effects and supports under-I/O fixtures", native_monitor: "stop/write/resume supported", new_server: pending-w2}
    desired: explicit RAM load with bank, PC/run policy and completion evidence
    proposed_effect_test: inject through MCP and monitor; compare every byte and marker with no disk mutation

  - id: startup-menu-matrix
    source: detection/tests/vice_harness.py:247-264
    workaround: named or row/column matrix events followed by sleeps/fallback
    classification: timing-dependency
    dependents: {count: 4, names: [test_reu_fetch_stash_and_no_false_ramdrive, test_sold_c64_ramdos_resident_interface_is_reported, test_active_geos_reu_ramdrive_is_reported, test_real_memory_expansion_detection]}
    reproduction: {existing_mcp: "pytest detection/tests/test_driver_api.py -q", native_monitor: "unsupported stimulus", new_server: pending-w2}
    observed: {existing_mcp: "matrix path falls back to named key with hold_frames=5", native_monitor: unsupported-stimulus, new_server: pending-w2}
    desired: canonical row/column API with frame hold, release and drain
    proposed_effect_test: select every option by coordinate and name; identical state and no stuck bit

  - id: restore-nmi-release
    source: ti emul/tests/hardware/test_restore_nmi_vice.py:43-63
    workaround: press another key, RESTORE down, sleep 100 ms, RESTORE up, release key
    classification: emulator-requirement
    dependents: {count: 1, names: [test_restore_abandons_running_program_and_reinitializes_editor]}
    reproduction: {existing_mcp: "pytest 'ti emul/tests/hardware/test_restore_nmi_vice.py' -q", native_monitor: "observe NMI/PC only; input unsupported", new_server: pending-w2}
    observed: {existing_mcp: "protocol lines 1161-1173 check success/schema; companion verifies mode and READY", native_monitor: unsupported-stimulus, new_server: pending-w2}
    desired: RESTORE press/release duration, NMI evidence, cleanup on cancel/timeout
    proposed_effect_test: exactly one NMI; verify PC/vector and final released matrix/FLAG state

  - id: protocol-success-without-effect
    source: tools/vice-mcp/tools/tests/test_mcp_protocol.py:1102-1194,1326-1373,1423-1454
    workaround: tests accept success for keyboard/snapshot/screenshot/trace without validating effects/files
    classification: harness-bug
    dependents: {count: 28, names: [TestKeyboard.test_keyboard_type, TestKeyboard.test_keyboard_key_press, TestKeyboard.test_keyboard_key_release, TestKeyboard.test_keyboard_restore, TestKeyboard.test_keyboard_matrix, plus_23_schema_error_variants]}
    reproduction: {existing_mcp: "python -m pytest tools/tests/test_mcp_protocol.py -k Keyboard -q --tb=short", native_monitor: "perform equivalent state operation and inspect memory/register/file", new_server: pending-w2}
    observed: {existing_mcp: "2026-07-16: 28 skipped, 341 deselected; enabled assertions inspect response text, not effect", native_monitor: "effect oracle available except keyboard stimulus", new_server: pending-w2}
    desired: success only after promised effect is observable
    proposed_effect_test: replace success-only assertions with screen/RAM/register/file/state comparisons; trace must be nonempty and snapshot must round-trip sentinels
```

## Call-site inventory and exact coverage

The following searches were run over all named companion trees; debug scripts were inventoried but excluded from test counts.

```powershell
rg -n --glob '*.py' "from (tools\.)?vice_harness import|from vice_snapshot import|ViceMCP\(|running_vice\(" ..\compiler2
rg -n --glob '*.py' "vice\.keyboard\.|ViceMCP\(" '..\basic v3'
rg -n --glob '*.py' "from vice_harness import|vice_session\(|keyboard_type\(|vice\.keyboard\." '..\ti emul'
rg -n --glob '*.py' "from vice_harness import|vice_session\(|keyboard_type\(" ..\python
rg -n --glob '*.py' "ViceSession\(|vice\.keyboard\." ..\detection ..\compressor
rg -n "class TestKeyboard|vice\.keyboard\.|snapshot|trace" ..\tools\vice-mcp\tools\tests\test_mcp_protocol.py
```

| Companion | Named harness coverage | Logical test count |
|---|---|---:|
| compiler2 | `vice_harness.py`, `vice_snapshot.py`; keyboard, loader, IRQ, devices, version plus two snapshot-contract tests | 6 live + 2 contract |
| basic v3 | `vice_keyboard_injection.py::main`; three benchmark call sites are non-pytest | 1 + 3 benchmarks |
| ti emul | all 26 functions under `tests/hardware`; 24 transit keyboard helper | 26 |
| python | all eight `tests/vice/*.py`: memory 1, native VM 1, REPL 9, convert 3, harness 2, imports 5, E2E 2, loadcache 2 | 25 (24 session users) |
| detection | two detection and four driver-API live tests; assembly-only test excluded | 6 |
| compressor | seven `test_vice_*` families plus expansion profiles/detection | 12 |
| old MCP | `-k Keyboard` selects 28 protocol/schema/error tests | 28 |

## Keyboard dimension audit

| Required dimension | Existing evidence | Required effect test |
|---|---|---|
| bulk text | TI/Python whole-string calls | 1,000 chars; screen and tokenized RAM |
| per-character text | compiler2 at 120 ms | zero client delay, queue-drain proof |
| PETSCII | ASCII mailbox and limited TI map are not full PETSCII | all supported byte values; screen/KERNAL effect or explicit rejection |
| shifted/control keys | modifier-shaped old requests only | CIA matrix plus editing effect for SHIFT/CTRL/C= |
| row/column matrix | basic-v3/detection transitions | per-frame CIA row/column samples |
| press/hold/release | 180 ms and `hold_frames=5` workarounds | exact frame duration and all-keys-up terminal state |
| RESTORE/NMI | one TI effect test | event count, PC/vector and release cleanup |
| warp mode | TI defaults to warp | normal/warp identical emulated outcome |
| paused state | explicit-run workaround | effect or structured rejection, never silent queue |
| screen-off programs | uncovered | display-off fixture consumes input into RAM marker |
| C128 keyboard | uncovered | x128 40-column, function/keypad/C128-specific keys and RAM |
| dropped input | retries/fallback/sleeps signal risk | 100 repetitions; zero drop/duplicate/stuck |
| completion acknowledgement | absent | queue ID plus accepted/consumed/drained frames and predicate |

## Runtime observations

The official native binary monitor is the independent oracle for memory, banks, registers, execution state and snapshot state, but it has no keyboard-injection command. W0-B already established 10,000 zero-error operations on official x64sc and x128 and independent drive memspaces 8-11. Keyboard cases therefore use MCP/UI for stimulus and native-monitor reads for effect.

Old-MCP reproduction executed:

```text
cd C:\Users\me\Documents\Coding Projects\tools\vice-mcp
python -m pytest tools\tests\test_mcp_protocol.py -k Keyboard -q --tb=short
result: 28 skipped, 341 deselected, 45 marker warnings; 3.08 s pytest time
```

The skip records a real fixture gap: the suite requires an externally configured emulator. Static inspection of lines 1102-1194 proves the keyboard assertions inspect response text/schema, not screen, RAM, CIA or NMI effects.

## Acceptance and blockers

- Read every named harness, all eight `python/tests/vice/*.py` files, RESTORE test, and old protocol test.
- Recorded 18 workaround rows. Every row has file/line, reproduction command for existing MCP/native/new server, observed and desired behavior, classification, dependent count/names, and proposed effect test.
- Covered all 13 mandated keyboard dimensions explicitly.
- All 18 new-server reproductions are `pending-w2`; none are misrepresented as executed.
- Native monitor cannot generate keyboard stimuli; it remains the effect oracle.
- Old MCP runtime tests skipped without configured fixture; exact result is preserved and static evidence shows the coverage weakness.

No W1-A design blocker remains. New-server execution belongs to W2/W3.
