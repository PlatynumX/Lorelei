#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import sys

VERSION = "r91f"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def score(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    parent = str(path.parent).lower()
    size = path.stat().st_size if path.exists() else 0

    rank = 0
    if name == "rott64.z64":
        rank += 100
    if "rott64" in name:
        rank += 80
    if VERSION in name:
        rank += 60
    if "build" in parent:
        rank += 20
    if size > 1024 * 1024:
        rank += 10
    return (-rank, -size, str(path))

def main() -> int:
    root = Path(".").resolve()
    reports = Path("build/reports")
    reports.mkdir(parents=True, exist_ok=True)

    found = []
    for p in root.rglob("*.z64"):
        if ".git" in p.parts:
            continue
        if p.is_file():
            found.append(p)

    report = reports / f"{VERSION}-rom-discovery.txt"
    with report.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"ROTT64 {VERSION} ROM discovery\n")
        for p in sorted(found, key=lambda x: str(x)):
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = p
            f.write(f"{rel}\t{p.stat().st_size}\n")

    if not found:
        fail("successful build did not produce any .z64 file")

    found.sort(key=score)
    src = found[0]

    if src.stat().st_size <= 1024 * 1024:
        fail(f"discovered ROM is suspiciously small: {src} ({src.stat().st_size} bytes)")

    canonical = Path("rott64.z64")
    versioned = Path(f"rott64-{VERSION}.z64")

    if src.resolve() != canonical.resolve():
        shutil.copyfile(src, canonical)
    if canonical.resolve() != versioned.resolve():
        shutil.copyfile(canonical, versioned)

    for out in (canonical, versioned):
        if not out.is_file() or out.stat().st_size <= 1024 * 1024:
            fail(f"packaged ROM missing or too small: {out}")

    print("PASS: ROTT64_R91F_ROM_DISCOVERY_PACKAGE")
    print(f"PASS: source ROM: {src}")
    print(f"PASS: canonical ROM: {canonical} ({canonical.stat().st_size} bytes)")
    print(f"PASS: versioned ROM: {versioned} ({versioned.stat().st_size} bytes)")
    print(f"PASS: report: {report}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
