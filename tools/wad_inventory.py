#!/usr/bin/env python3
"""Create machine-readable and human-readable inventories of a ROTT WAD."""

from __future__ import annotations

import argparse
import csv
import json
import struct
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

HEADER = struct.Struct("<4sII")
ENTRY = struct.Struct("<II8s")
MAX_LUMPS = 200_000


@dataclass(frozen=True)
class Lump:
    index: int
    name: str
    offset: int
    size: int
    range_valid: bool
    size_hint: str


def hint_for_size(size: int) -> str:
    if size == 768:
        return "possible 256xRGB VGA palette"
    if size == 64_000:
        return "possible raw 320x200 indexed frame"
    if size == 76_800:
        return "possible raw 320x240 indexed frame"
    if size == 0:
        return "marker/empty lump"
    return ""


def parse(path: Path) -> tuple[dict, list[Lump]]:
    file_size = path.stat().st_size
    with path.open("rb") as handle:
        raw_header = handle.read(HEADER.size)
        if len(raw_header) != HEADER.size:
            raise ValueError("WAD is smaller than its header")
        signature, count, directory_offset = HEADER.unpack(raw_header)
        if signature != b"IWAD":
            raise ValueError(f"unexpected signature {signature!r}; expected b'IWAD'")
        if not 0 < count <= MAX_LUMPS:
            raise ValueError(f"implausible lump count: {count}")
        directory_end = directory_offset + count * ENTRY.size
        if directory_offset < HEADER.size or directory_end > file_size:
            raise ValueError("directory lies outside the WAD")
        handle.seek(directory_offset)
        lumps: list[Lump] = []
        for index in range(count):
            raw = handle.read(ENTRY.size)
            if len(raw) != ENTRY.size:
                raise ValueError(f"short directory read at lump {index}")
            offset, size, raw_name = ENTRY.unpack(raw)
            name = raw_name.split(b"\0", 1)[0].decode("ascii", errors="replace")
            lumps.append(
                Lump(
                    index=index,
                    name=name,
                    offset=offset,
                    size=size,
                    range_valid=(offset + size) <= file_size,
                    size_hint=hint_for_size(size),
                )
            )
    metadata = {
        "path": str(path),
        "signature": signature.decode("ascii"),
        "file_size": file_size,
        "lump_count": count,
        "directory_offset": directory_offset,
        "invalid_range_count": sum(not lump.range_valid for lump in lumps),
        "duplicate_name_count": sum(value - 1 for value in Counter(l.name for l in lumps).values() if value > 1),
    }
    return metadata, lumps


def write_reports(out: Path, metadata: dict, lumps: list[Lump]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "lumps": [asdict(lump) for lump in lumps]}
    (out / "huntbgin-wad-inventory.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (out / "huntbgin-wad-inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(lumps[0]).keys()) if lumps else ["index"])
        writer.writeheader()
        for lump in lumps:
            writer.writerow(asdict(lump))

    likely_assets = [lump for lump in lumps if lump.size_hint]
    lines = [
        "# HUNTBGIN.WAD inventory",
        "",
        f"- File size: **{metadata['file_size']} bytes**",
        f"- Lumps: **{metadata['lump_count']}**",
        f"- Directory offset: **0x{metadata['directory_offset']:08X}**",
        f"- Invalid lump ranges: **{metadata['invalid_range_count']}**",
        f"- Repeated directory names beyond first occurrence: **{metadata['duplicate_name_count']}**",
        "",
        "## Size-based graphics/palette candidates",
        "",
    ]
    if likely_assets:
        lines.extend(
            f"- `{lump.index:05d}` `{lump.name}` — {lump.size} bytes: {lump.size_hint}"
            for lump in likely_assets
        )
    else:
        lines.append("No exact-size raw framebuffer or VGA palette candidates were found.")
    lines.extend(
        [
            "",
            "The size hints are probes, not format declarations. ROTT assets may be compressed or use custom headers.",
            "",
        ]
    )
    (out / "huntbgin-wad-inventory.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wad", type=Path)
    parser.add_argument("--out", type=Path, default=Path("build/reports"))
    args = parser.parse_args()
    metadata, lumps = parse(args.wad)
    write_reports(args.out, metadata, lumps)
    print(f"Inventoried {metadata['lump_count']} lumps from {args.wad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
