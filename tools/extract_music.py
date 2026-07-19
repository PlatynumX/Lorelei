#!/usr/bin/env python3
"""Extract ROTT MIDI lumps and generate the N64 runtime music lookup table."""
from __future__ import annotations

import argparse
import json
import re
import struct
import zlib
from pathlib import Path

HEADER = struct.Struct("<4sII")
ENTRY = struct.Struct("<II8s")

SHAREWARE_SONGS = (
    "FANFARE2", "RISE", "MMMENU", "DEADLY", "GOINGUP", "HOWDIDO",
    "FISHPOLK", "YOUSUCK", "WATZNEXT", "GAZZ!", "FASTWAY", "MISTACHE",
    "OWW", "SMOKE", "SPRAY", "RUNLIKE", "SMOOTH", "CHANT",
)
FULL_EXTRA_SONGS = (
    "MEDIEV1A", "TASKFORC", "KISSOFF", "RADAGIO", "SHARDS", "STAIRS",
    "SUCKTHIS", "EXCALIBR", "CCCOOL", "WORK_DAY", "WHERIZIT", "BOSSBLOW",
    "HELLERO", "EVINRUDE", "VICTORY", "HERE_BOY",
)
ALL_SONGS = SHAREWARE_SONGS + FULL_EXTRA_SONGS


def slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not value:
        raise ValueError(f"cannot create filename for lump {name!r}")
    return value


def parse_wad(path: Path) -> dict[str, bytes]:
    raw = path.read_bytes()
    if len(raw) < HEADER.size:
        raise ValueError("WAD is smaller than its header")
    signature, count, directory = HEADER.unpack_from(raw, 0)
    if signature != b"IWAD":
        raise ValueError(f"expected IWAD, got {signature!r}")
    end = directory + count * ENTRY.size
    if directory < HEADER.size or end > len(raw):
        raise ValueError("WAD directory lies outside file")
    wanted = {name.upper() for name in ALL_SONGS}
    found: dict[str, bytes] = {}
    for index in range(count):
        offset, size, raw_name = ENTRY.unpack_from(raw, directory + index * ENTRY.size)
        name = raw_name.split(b"\0", 1)[0].decode("ascii", errors="strict").upper()
        if name not in wanted or name in found:
            continue
        if offset + size > len(raw):
            raise ValueError(f"music lump {name} lies outside WAD")
        found[name] = raw[offset:offset + size]
    return found


def write_header(path: Path, entries: list[dict]) -> None:
    lines = [
        "#ifndef ROTT64_N64_MUSIC_MAP_GENERATED_H",
        "#define ROTT64_N64_MUSIC_MAP_GENERATED_H",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        "typedef struct {",
        "    uint32_t crc32;",
        "    uint32_t size;",
        "    const char *name;",
        "    const char *path;",
        "} rott64_music_map_entry_t;",
        "",
        "static const rott64_music_map_entry_t rott64_music_map[] = {",
    ]
    for entry in entries:
        lines.append(
            f'    {{ 0x{entry["crc32"]:08X}u, {entry["size"]}u, '
            f'"{entry["name"]}", "rom:/rott/music/{entry["slug"]}.wav64" }},'
        )
    if not entries:
        lines.append("    { 0u, 0u, NULL, NULL },")
    lines += [
        "};",
        f"static const size_t rott64_music_map_count = {len(entries)}u;",
        "",
        "#endif",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def extract(wad: Path, output: Path, header: Path, mode: str) -> list[dict]:
    lumps = parse_wad(wad)
    required = SHAREWARE_SONGS if mode == "shareware" else ALL_SONGS if mode == "full" else ()
    missing = [name for name in required if name not in lumps]
    if missing:
        raise ValueError("missing required music lumps: " + ", ".join(missing))
    selected = [name for name in ALL_SONGS if name in lumps]
    if mode == "any" and not selected:
        raise ValueError("no recognized ROTT music lumps found")

    output.mkdir(parents=True, exist_ok=True)
    for stale in list(output.glob("*.mid")) + list(output.glob("*.wav")):
        stale.unlink()

    entries: list[dict] = []
    for name in selected:
        data = lumps[name]
        if not data.startswith(b"MThd"):
            raise ValueError(f"music lump {name} is not a standard MIDI stream")
        stem = slug(name)
        (output / f"{stem}.mid").write_bytes(data)
        entries.append({
            "name": name,
            "slug": stem,
            "size": len(data),
            "crc32": zlib.crc32(data) & 0xFFFFFFFF,
        })
        print(f"[music] {name:8s} -> {stem}.mid ({len(data)} bytes)")

    write_header(header, entries)
    (output / "music-map.json").write_text(
        json.dumps({"mode": mode, "tracks": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[music] extracted {len(entries)} MIDI tracks")
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wad", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("header", type=Path)
    parser.add_argument("--mode", choices=("shareware", "full", "any"), default="shareware")
    args = parser.parse_args()
    try:
        extract(args.wad, args.output, args.header, args.mode)
    except (OSError, ValueError, struct.error) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
