#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import hashlib

VERSION = "r96a"

MAGIC_Z64 = b"\x80\x37\x12\x40"
MAGIC_V64 = b"\x37\x80\x40\x12"
MAGIC_N64 = b"\x40\x12\x37\x80"
ROM_SUFFIXES = {".z64", ".n64", ".v64", ".rom", ".bin"}


def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def safe_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        try:
            tmp.chmod(0o644)
        except OSError:
            pass
        tmp.unlink()

    tmp.write_bytes(data)
    tmp.chmod(0o644)

    if path.exists():
        try:
            path.chmod(0o644)
        except OSError:
            pass
        try:
            path.unlink()
        except OSError as exc:
            fail(f"could not replace existing output {path}: {exc}")

    tmp.replace(path)

def safe_write_text(path: Path, text: str) -> None:
    safe_write_bytes(path, text.encode("utf-8"))


def rom_kind(path: Path) -> str | None:
    try:
        with path.open("rb") as f:
            head = f.read(4)
    except OSError:
        return None
    if head == MAGIC_Z64:
        return "z64"
    if head == MAGIC_V64:
        return "v64"
    if head == MAGIC_N64:
        return "n64"
    return None


def likely_candidate(path: Path) -> bool:
    if not path.is_file() or ".git" in path.parts:
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size <= 1024 * 1024:
        return False
    if rom_kind(path) is not None:
        return True
    if path.suffix.lower() in ROM_SUFFIXES:
        return True
    return False


def score(path: Path, kind: str | None) -> tuple[int, int, str]:
    name = path.name.lower()
    parent = str(path.parent).lower()
    size = path.stat().st_size
    rank = 0
    if kind == "z64":
        rank += 120
    elif kind in {"n64", "v64"}:
        rank += 100
    if name == "rott64.z64":
        rank += 90
    if "rott64" in name:
        rank += 80
    if VERSION in name:
        rank += 60
    if "build" in parent:
        rank += 30
    if path.suffix.lower() in ROM_SUFFIXES:
        rank += 10
    return (-rank, -size, str(path))


def convert_to_z64_bytes(path: Path, kind: str | None) -> bytes:
    data = path.read_bytes()
    if len(data) <= 1024 * 1024:
        fail(f"discovered ROM is suspiciously small: {path} ({len(data)} bytes)")
    if kind is None:
        fail(f"candidate does not have recognized N64 ROM byte-order magic: {path}")
    if kind == "z64":
        return data
    if kind == "v64":
        if len(data) % 2:
            fail(f"v64 ROM has odd byte length: {path}")
        out = bytearray(len(data))
        out[0::2] = data[1::2]
        out[1::2] = data[0::2]
        if bytes(out[:4]) != MAGIC_Z64:
            fail(f"v64 byte-swap conversion failed: {path}")
        return bytes(out)
    if kind == "n64":
        if len(data) % 4:
            fail(f"n64 ROM has non-32-bit-aligned byte length: {path}")
        out = bytearray()
        for i in range(0, len(data), 4):
            out.extend(data[i:i+4][::-1])
        if bytes(out[:4]) != MAGIC_Z64:
            fail(f"n64 byte-order conversion failed: {path}")
        return bytes(out)
    fail(f"unsupported ROM kind: {kind}")


def main() -> int:
    root = Path(".").resolve()
    reports = Path("build/reports")
    reports.mkdir(parents=True, exist_ok=True)

    candidates: list[tuple[Path, str | None]] = []
    for p in root.rglob("*"):
        if likely_candidate(p):
            candidates.append((p, rom_kind(p)))

    report = reports / f"{VERSION}-rom-discovery.txt"
    with report.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"ROTT64 {VERSION} ROM discovery\n")
        f.write("path\tsize\tkind\n")
        for p, kind in sorted(candidates, key=lambda item: str(item[0])):
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = p
            f.write(f"{rel}\t{p.stat().st_size}\t{kind or 'unknown'}\n")

    recognized = [(p, kind) for p, kind in candidates if kind is not None]
    if not recognized:
        fail("successful build did not produce any recognized N64 ROM file (.z64/.n64/.v64 or ROM header)")

    recognized.sort(key=lambda item: score(item[0], item[1]))
    src, kind = recognized[0]
    z64_data = convert_to_z64_bytes(src, kind)

    canonical = Path("rott64.z64")
    versioned = Path(f"rott64-{VERSION}.z64")
    # If the discovered ROM already is root rott64.z64, do not rewrite it.
    # r92e failed when rott64.z64 existed but could not be reopened for writing.
    if src.resolve() != canonical.resolve():
        safe_write_bytes(canonical, z64_data)
    else:
        try:
            canonical.chmod(0o644)
        except OSError:
            pass

    safe_write_bytes(versioned, z64_data)

    sha = hashlib.sha256(z64_data).hexdigest()
    sha_file = Path(f"rott64-{VERSION}.z64.sha256")
    safe_write_text(sha_file, f"{sha}  rott64-{VERSION}.z64\n")

    for out in (canonical, versioned):
        if not out.is_file() or out.stat().st_size <= 1024 * 1024:
            fail(f"packaged ROM missing or too small: {out}")
        if out.read_bytes()[:4] != MAGIC_Z64:
            fail(f"packaged ROM is not canonical z64 byte order: {out}")

    if not sha_file.is_file() or sha not in sha_file.read_text(encoding="utf-8"):
        fail(f"sha256 sidecar missing or invalid: {sha_file}")

    print("PASS: ROTT64_R96A_ROM_DISCOVERY_PACKAGE")
    print(f"PASS: source ROM: {src} ({kind})")
    print(f"PASS: canonical ROM: {canonical} ({canonical.stat().st_size} bytes)")
    print(f"PASS: versioned ROM: {versioned} ({versioned.stat().st_size} bytes)")
    print(f"PASS: sha256: {sha_file}")
    print(f"PASS: report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
