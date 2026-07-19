#!/usr/bin/env python3
"""Report which engine files ROTTDS changed relative to Taradino by filename/size."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def digest(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()
def locate(root:Path,name:str)->Path|None:
    matches=[p for p in root.rglob(name) if p.is_file()]
    return matches[0] if matches else None
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("taradino",type=Path); ap.add_argument("rottds",type=Path); ap.add_argument("--out",type=Path,default=Path("build/reports")); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    keys=["rt_main.c","rt_in.c","modexlib.c","rt_cfg.c","z_zone.c","w_wad.c","rt_sound.c","isr.c","rt_game.c","rt_playr.c"]
    rows=[]
    for name in keys:
        left=locate(a.taradino,name); right=locate(a.rottds,name)
        rows.append({"file":name,"taradino":str(left) if left else None,"rottds":str(right) if right else None,"taradino_size":left.stat().st_size if left else None,"rottds_size":right.stat().st_size if right else None,"same_sha256":bool(left and right and digest(left)==digest(right))})
    (a.out/"rottds-reference.json").write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
    lines=["# ROTTDS reference inventory","","ROTTDS is used as a console-port design reference; Taradino remains the compiled engine for big-endian fixes.","","| File | Taradino bytes | ROTTDS bytes | Identical |","|---|---:|---:|---|"]
    for r in rows: lines.append(f"| `{r['file']}` | {r['taradino_size'] or '-'} | {r['rottds_size'] or '-'} | {'yes' if r['same_sha256'] else 'no'} |")
    lines += ["","Applied ROTTDS lessons in this candidate: fixed 320x200 output, controller-to-key translation, Expansion Pak requirement, single-player startup, disabled native music, and read-only initial configuration.",""]
    (a.out/"rottds-reference.md").write_text("\n".join(lines),encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
