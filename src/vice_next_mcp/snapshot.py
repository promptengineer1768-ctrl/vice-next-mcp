"""Validated snapshot artifacts and round-trip helpers.

The binary monitor owns the actual dump/undump operation; this module owns the
filesystem contract so a successful response can never refer to a missing or
malformed file.
"""
from __future__ import annotations
import hashlib, json, os, struct
from pathlib import Path

MAGIC = b"VICE Snapshot File"

class SnapshotError(ValueError): pass

def fingerprint(path: str|Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def validate_snapshot(path: str|Path, *, required_modules=()) -> dict:
    p=Path(path)
    if not p.is_file() or p.stat().st_size < len(MAGIC):
        raise SnapshotError("snapshot file is missing or empty")
    data=p.read_bytes()
    if not data.startswith(MAGIC):
        raise SnapshotError("invalid VICE snapshot magic")
    # VSF modules have an 8-byte name and length; scan only structurally valid
    # headers, never unqualified byte signatures.
    modules=[]; pos=len(MAGIC)
    while pos + 16 <= len(data):
        name=data[pos:pos+8].rstrip(b"\0").decode("ascii","replace")
        length=struct.unpack_from("<I",data,pos+12)[0]
        if not name or length < 0 or pos+16+length > len(data): break
        modules.append(name); pos += 16+length
    missing=[m for m in required_modules if m not in modules]
    if missing: raise SnapshotError(f"snapshot missing required modules: {missing}")
    return {"path":str(p),"size":len(data),"modules":modules,"fingerprint":fingerprint(p)}

def metadata(path, *, machine, version="unknown", include_disks=False, required_modules=()):
    info=validate_snapshot(path, required_modules=required_modules)
    return {**info,"machine":machine,"version":version,"include_disks":bool(include_disks)}

def ensure_path(path, root=None) -> Path:
    p=Path(path).resolve()
    if root is not None and not p.is_relative_to(Path(root).resolve()):
        raise SnapshotError("snapshot path escapes instance artifact root")
    p.parent.mkdir(parents=True,exist_ok=True); return p

