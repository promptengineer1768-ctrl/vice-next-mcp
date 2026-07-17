"""Optional pytest integration: fixtures are safe with or without xdist."""

from pathlib import Path
import os, uuid, pytest
from .batch import sanitize


def pytest_configure(config):
    for name in ("vice", "vice_serial", "vice_c64", "vice_c128", "vice_drive", "vice_capture"):
        config.addinivalue_line("markers", f"{name}: VICE experiment marker")


@pytest.fixture
def vice_artifact_dir(request, tmp_path_factory):
    worker = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    run = uuid.uuid4().hex[:10]
    node = sanitize(request.node.nodeid)
    path = tmp_path_factory.mktemp("vice") / f"{run}-{worker}-{node}"
    path.mkdir(parents=True, exist_ok=True)
    return Path(path)


@pytest.fixture
def vice_case_id(request):
    from .batch import case_id

    return case_id({"nodeid": request.node.nodeid})


@pytest.fixture
def vice_instance_factory(vice_artifact_dir):
    instances = []

    def factory(machine="c64", **metadata):
        item = {
            "machine": machine,
            "generation": 1,
            "artifact_dir": str(vice_artifact_dir),
            **metadata,
        }
        instances.append(item)
        return item

    yield factory
    # Real supervisors may attach a stop() callback; teardown is best-effort and idempotent.
    for item in instances:
        stop = item.get("stop")
        if callable(stop):
            try:
                stop()
            except Exception:
                pass
