# Contributing

Create a Python 3.11+ environment and install development tools:

```powershell
py -m pip install -e ".[dev]"
python -m pytest -q
ruff check src tests
black --check src tests
mypy src/vice_next_mcp
```

Keep subprocess arguments as sequences and avoid `shell=True` unless a batch
case explicitly opts into shell semantics. Add focused tests for lifecycle,
transport, and error paths. Live VICE tests are marked `live` and require an
installed emulator.
