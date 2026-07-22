"""Validate generated source and wheel distributions in isolated environments."""

from __future__ import annotations

import argparse
import os
import subprocess
import tarfile
import tempfile
import venv
from pathlib import Path


def run(command: list[str], *, cwd: Path) -> None:
    """Run a validation command from an explicit isolated directory."""
    subprocess.run(command, cwd=cwd, check=True)


def environment_python(root: Path) -> Path:
    """Create a clean virtual environment and return its Python executable."""
    venv.EnvBuilder(with_pip=True).create(root)
    suffix = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return root / suffix


def validate_sdist(sdist: Path, scratch: Path) -> None:
    """Extract and execute the complete packaged test suite from an sdist."""
    source_root = scratch / "source"
    source_root.mkdir()
    with tarfile.open(sdist, "r:gz") as archive:
        archive.extractall(source_root, filter="data")
    projects = [path for path in source_root.iterdir() if path.is_dir()]
    if len(projects) != 1:
        raise RuntimeError(f"expected one sdist root, found {projects}")
    project = projects[0]
    python = environment_python(scratch / "sdist-venv")
    run([str(python), "-m", "pip", "install", ".[dev]"], cwd=project)
    run([str(python), "-m", "pytest", "-q"], cwd=project)


def validate_wheel(wheel: Path, scratch: Path) -> None:
    """Import and smoke-test a wheel where checkout sources cannot shadow it."""
    python = environment_python(scratch / "wheel-venv")
    isolated = scratch / "wheel-cwd"
    isolated.mkdir()
    run([str(python), "-m", "pip", "install", str(wheel)], cwd=isolated)
    probe = (
        "import pathlib, vice_next_mcp; "
        "p=pathlib.Path(vice_next_mcp.__file__).resolve(); "
        "print(p); "
        "assert 'site-packages' in str(p).lower(), p"
    )
    run([str(python), "-c", probe], cwd=isolated)
    run([str(python), "-m", "vice_next_mcp.cli", "--help"], cwd=isolated)


def main() -> int:
    """Validate the single sdist and wheel found in a distribution directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", type=Path)
    args = parser.parse_args()
    sdists = sorted(args.dist.resolve().glob("*.tar.gz"))
    wheels = sorted(args.dist.resolve().glob("*.whl"))
    if len(sdists) != 1 or len(wheels) != 1:
        raise SystemExit("expected exactly one sdist and one wheel")
    with tempfile.TemporaryDirectory(prefix="vice-next-dist-") as directory:
        scratch = Path(directory)
        validate_sdist(sdists[0], scratch)
        validate_wheel(wheels[0], scratch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
