#!/usr/bin/env python3
"""Extract ROTT shareware data from the official ROTTDS pack or DOS ZIP."""
from __future__ import annotations
import argparse, hashlib, shutil, sys, tarfile, zipfile
from pathlib import Path, PurePosixPath

REQUIRED = ("HUNTBGIN.WAD", "HUNTBGIN.RTL", "HUNTBGIN.RTC")
OPTIONAL = (
    "REMOTE1.RTS", "DEMO1_3.DMO", "DEMO2_3.DMO", "DEMO3_3.DMO", "DEMO4_3.DMO",
    "LICENSE.DOC", "VENDOR.DOC", "ORDER.FRM", "README.NDS", "COPYING",
)

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""): h.update(block)
    return h.hexdigest()

def safe_name(name: str) -> str:
    pure=PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts: raise ValueError(f"unsafe archive member: {name}")
    return pure.name.upper()

def read_archive(path: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                base=safe_name(info.filename)
                if base in REQUIRED+OPTIONAL and base not in found: found[base]=z.read(info)
        return found
    try:
        with tarfile.open(path, "r:*") as t:
            for member in t.getmembers():
                if not member.isfile(): continue
                base=safe_name(member.name)
                if base in REQUIRED+OPTIONAL and base not in found:
                    f=t.extractfile(member)
                    if f is not None: found[base]=f.read()
        return found
    except tarfile.TarError as exc:
        raise ValueError(f"unsupported archive: {exc}") from exc

def extract(path: Path, out: Path) -> None:
    files=read_archive(path)
    missing=[name for name in REQUIRED if name not in files]
    if missing: raise RuntimeError("missing required shareware data: "+", ".join(missing))
    out.mkdir(parents=True, exist_ok=True)
    written=[]
    for name,data in files.items():
        target=out/name; target.write_bytes(data); written.append(target)
        print(f"[shareware] {name}: {len(data)} bytes")
    (out/"SHA256SUMS.txt").write_text("".join(f"{sha256_file(p)}  {p.name}\n" for p in sorted(written)), encoding="ascii")
    (out/"SOURCE.txt").write_text(
        "Rise of the Triad: The HUNT Begins shareware data\n"
        f"Input archive: {path.name}\nArchive SHA-256: {sha256_file(path)}\n"
        "The original game-data/shareware license remains controlling.\n", encoding="utf-8")

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("archive",type=Path); p.add_argument("output",type=Path); a=p.parse_args()
    try: extract(a.archive,a.output)
    except (OSError,ValueError,RuntimeError,zipfile.BadZipFile) as exc:
        print(f"prepare_shareware.py: {exc}",file=sys.stderr); return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
