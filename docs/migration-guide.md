# Migration guide

Replace local `ViceMCP`/`ViceSession` helpers with `Supervisor` leases for live
instances, `BatchRunner` for matrices, and the optional pytest plugin. A case is a plain dictionary; its SHA-256-derived `case_id` is
stable, while each run receives an isolated artifact directory. Set
`PYTEST_PLUGINS=vice_next_mcp.pytest_plugin` (or add it to `pytest_plugins`) to
obtain `vice_artifact_dir`, `vice_case_id`, and `vice_instance_factory` fixtures.

Use `vice-next batch --cases cases.json --workers 4 --base-port 6510`, or
`BatchRunner("results", workers=4, base_port=int(os.getenv("VICE_MCP_BASE_PORT",0)))`.
The callback receives `(case, artifact_dir, assigned_port)` and should launch a
fresh emulator. Failures include a serial `pytest -n 0` reproduction hint.
Markers `vice`, `vice_serial`, `vice_c64`, `vice_c128`, `vice_drive`, and
`vice_capture` are registered by the plugin; runs without VICE can skip normally.
