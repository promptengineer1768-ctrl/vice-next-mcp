"""Cross-process isolation and teardown contracts."""

from __future__ import annotations

import multiprocessing
import socket
from pathlib import Path

from vice_next_mcp.process import InstancePaths, PortAllocator


def _reserve_in_child(
    lease_root: str, ready: multiprocessing.Queue[int], release: multiprocessing.Event
) -> None:
    """Reserve a port in a child process until its parent releases it."""
    allocator = PortAllocator(lease_root=lease_root)
    reservation = allocator.reserve()
    ready.put(reservation.port)
    release.wait(10)
    allocator.release(reservation)


def test_cross_process_port_leases_are_unique_and_released(tmp_path: Path) -> None:
    """Independent sessions cannot claim one monitor port and leave no leases."""
    context = multiprocessing.get_context("spawn")
    ready: multiprocessing.Queue[int] = context.Queue()
    release = context.Event()
    children = [
        context.Process(target=_reserve_in_child, args=(str(tmp_path / "leases"), ready, release))
        for _ in range(8)
    ]
    for child in children:
        child.start()
    ports = [ready.get(timeout=15) for _ in children]
    assert len(ports) == len(set(ports))
    release.set()
    for child in children:
        child.join(timeout=15)
        assert child.exitcode == 0
    assert not list((tmp_path / "leases").glob("*.json"))
    for port in ports:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))


def test_generation_paths_isolate_mutable_media_snapshots_and_temp(tmp_path: Path) -> None:
    """Every generation receives private mutable inputs and work products."""
    source = tmp_path / "source.d64"
    source.write_bytes(b"original")
    first = InstancePaths.create(tmp_path / "runs", "one", 1)
    second = InstancePaths.create(tmp_path / "runs", "two", 1)
    first_media = first.isolate_media(source)
    second_media = second.isolate_media(source)
    first_media.write_bytes(b"changed")
    assert second_media.read_bytes() == b"original"
    assert first.snapshots != second.snapshots
    assert first.temp != second.temp
    assert first.snapshots.is_dir() and second.temp.is_dir()
