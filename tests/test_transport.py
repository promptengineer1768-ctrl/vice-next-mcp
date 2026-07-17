import asyncio, os, socket, struct, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from vice_next_mcp.monitor import *
from vice_next_mcp.process import InstancePaths, PortAllocator, ProcessController


def packet(command, rid, body=b"", error=0):
    return (
        MAGIC
        + struct.pack("<I", len(body))
        + bytes((command, error))
        + struct.pack("<I", rid)
        + body
    )


def test_partial_and_invalid_frames():
    asyncio.run(_partial_and_invalid_frames())


async def _partial_and_invalid_frames():
    reader = asyncio.StreamReader()
    raw = packet(0x81, 7, b"abc")
    for byte in raw:
        reader.feed_data(bytes((byte,)))
    assert (await read_response(reader)).body == b"abc"
    reader = asyncio.StreamReader()
    reader.feed_data(b"NO" + b"\0" * 10)
    with pytest.raises(ProtocolError):
        await read_response(reader)


def test_demux_out_of_order_event_error_and_close():
    asyncio.run(_demux_out_of_order_event_error_and_close())


async def _demux_out_of_order_event_error_and_close():
    async def handler(reader, writer):
        req = []
        for _ in range(3):
            h = await reader.readexactly(11)
            size, rid = struct.unpack_from("<II", h, 2)
            await reader.readexactly(size)
            req.append((h[10], rid))
        writer.write(
            packet(0x11, EVENT_ID, b"event")
            + packet(*req[1], b"two")
            + packet(*req[0], b"one")
            + packet(*req[2], error=2)
        )
        await writer.drain()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    async with server:
        tx = BinaryMonitorTransport("127.0.0.1", server.sockets[0].getsockname()[1])
        await tx.connect()
        calls = [asyncio.create_task(tx.execute(x)) for x in (1, 2, 3)]
        assert (await calls[0]).body == b"one" and (await calls[1]).body == b"two"
        with pytest.raises(CommandError):
            await calls[2]
        assert (await tx.next_event(timeout=1)).body == b"event"
        await tx.close()
        assert tx.state is State.CLOSED


def test_cancel_late_reply_marks_failed():
    asyncio.run(_cancel_late_reply_marks_failed())


async def _cancel_late_reply_marks_failed():
    seen = asyncio.Event()

    async def handler(reader, writer):
        h = await reader.readexactly(11)
        size, rid = struct.unpack_from("<II", h, 2)
        await reader.readexactly(size)
        seen.set()
        await asyncio.sleep(0.03)
        writer.write(packet(h[10], rid))
        await writer.drain()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    async with server:
        tx = BinaryMonitorTransport("127.0.0.1", server.sockets[0].getsockname()[1])
        await tx.connect()
        task = asyncio.create_task(tx.execute(1))
        await seen.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(50):
            if tx.state is State.FAILED:
                break
            await asyncio.sleep(0.01)
        assert tx.state is State.FAILED
        await tx.close()


def test_ports_paths_media_and_profiles(tmp_path):
    allocator = PortAllocator()
    a = allocator.reserve()
    b = allocator.reserve()
    assert a.port != b.port
    allocator.release(a)
    allocator.release(b)
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    claim = allocator.reserve(busy.getsockname()[1])
    assert claim.port != busy.getsockname()[1]
    allocator.release(claim)
    busy.close()
    paths = InstancePaths.create(tmp_path / "out", "id", 1)
    disk = tmp_path / "disk.d64"
    disk.write_bytes(b"x")
    assert paths.isolate_media(disk).read_bytes() == b"x"
    with pytest.raises(ValueError):
        paths.isolate_media(disk, shared_read_only=True)
    exe = tmp_path / ("x64sc.exe" if os.name == "nt" else "x64sc")
    exe.write_bytes(b"x")
    command = ProcessController.command(exe, 6502)
    assert "-binarymonitor" in command
    assert "-default" in command
    with pytest.raises(ValueError):
        ProcessController.command(exe, 6502, ("-truedrive",))
