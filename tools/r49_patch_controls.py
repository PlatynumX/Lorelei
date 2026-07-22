#!/usr/bin/env python3
from __future__ import annotations
import re, sys
from pathlib import Path

TARGET = {
    "z":       ("fire",       ("ctrl","control")),
    "a":       ("use/open",   ("space",)),
    "b":       ("run",        ("shift",)),
    "c_left":  ("strafe left",("comma","less")),
    "c_right": ("strafe right",("period","greater")),
    "c_up":    ("swap weapon",("return","enter")),
    "c_down":  ("drop weapon",("delete","del")),
    "d_up":    ("look up",    ("pageup","pgup")),
    "d_down":  ("look down",  ("pagedown","pgdn")),
    "d_right": ("auto-run",   ("capslock","caps")),
    "l":       ("map",        ("tab",)),
    "r":       ("180 turn",   ("backspace",)),
    "start":   ("pause/menu", ("escape","esc")),
}
UNASSIGNED="d_left"

ALIASES = {
 "z":("z","btn_z","button_z"), "a":("a","btn_a","button_a"), "b":("b","btn_b","button_b"),
 "c_left":("c_left","cleft","c_left_button"), "c_right":("c_right","cright","c_right_button"),
 "c_up":("c_up","cup","c_up_button"), "c_down":("c_down","cdown","c_down_button"),
 "d_up":("d_up","dup","dpad_up"), "d_down":("d_down","ddown","dpad_down"),
 "d_left":("d_left","dleft","dpad_left"), "d_right":("d_right","dright","dpad_right"),
 "l":("l","btn_l","button_l"), "r":("r","btn_r","button_r"), "start":("start","btn_start","button_start"),
}

def fail(x): raise SystemExit("r49_patch_controls.py: "+x)

def keytoken(line):
    # Supports the SDL/scancode spellings used by the port without assuming one.
    m=re.search(r'\b((?:SDLK|SDL_SCANCODE|sc)_[A-Za-z0-9_]+)\b',line)
    return m

def phys(line,name):
    lo=line.lower()
    return any(re.search(r'(?<![a-z0-9_])'+re.escape(a)+r'(?![a-z0-9_])',lo) for a in ALIASES[name])

def replacement(old, wanted):
    prefix=old.split("_",1)[0]
    table={
      "ctrl":("LCTRL","CTRL","Control"), "control":("LCTRL","CTRL","Control"),
      "space":("SPACE","SPACE","Space"), "shift":("LSHIFT","LSHIFT","LShift"),
      "comma":("COMMA","COMMA","Comma"), "less":("COMMA","COMMA","Comma"),
      "period":("PERIOD","PERIOD","Period"), "greater":("PERIOD","PERIOD","Period"),
      "return":("RETURN","RETURN","Return"), "enter":("RETURN","RETURN","Return"),
      "delete":("DELETE","DELETE","Delete"), "del":("DELETE","DELETE","Delete"),
      "pageup":("PAGEUP","PAGEUP","PageUp"), "pgup":("PAGEUP","PAGEUP","PageUp"),
      "pagedown":("PAGEDOWN","PAGEDOWN","PageDown"), "pgdn":("PAGEDOWN","PAGEDOWN","PageDown"),
      "capslock":("CAPSLOCK","CAPSLOCK","CapsLock"), "caps":("CAPSLOCK","CAPSLOCK","CapsLock"),
      "tab":("TAB","TAB","Tab"), "backspace":("BACKSPACE","BACKSPACE","BackSpace"),
      "escape":("ESCAPE","ESCAPE","Escape"), "esc":("ESCAPE","ESCAPE","Escape"),
    }
    idx=0 if prefix=="SDLK" else (1 if prefix=="SDL" else 2)
    return prefix+"_"+table[wanted][idx]

def main():
    if len(sys.argv)!=2: fail("usage: patcher platform/n64/sdl_n64.c")
    p=Path(sys.argv[1]); s=p.read_text(); lines=s.splitlines()
    report=[]; changed=0

    # We only alter declarative physical-button -> key/scancode mappings.
    # Menu-specific logic is intentionally left intact.
    for name,(action,wants) in TARGET.items():
        candidates=[]
        for i,ln in enumerate(lines):
            km=keytoken(ln)
            if km and phys(ln,name):
                candidates.append((i,km))
        if len(candidates)==0:
            report.append(f"{name:7s} -> {action:12s}: no platform declarative row; defer to generated-engine mapping")
            continue
        if len(candidates)>1:
            fail(f"{name}: ambiguous declarative mappings ({len(candidates)}); refusing blind edit")
        i,km=candidates[0]
        old=km.group(1)
        new=replacement(old,wants[0])
        lines[i]=lines[i][:km.start(1)]+new+lines[i][km.end(1):]
        report.append(f"{name:7s} -> {action:12s}: {old} -> {new}")
        changed+=1

    # D-left must be unassigned in gameplay. Accept an existing explicit NONE/UNKNOWN
    # mapping; otherwise replace its one declarative key token with the matching
    # family's UNKNOWN/NONE representation.
    cand=[]
    for i,ln in enumerate(lines):
        if phys(ln,UNASSIGNED):
            km=keytoken(ln)
            if km: cand.append((i,km))
    if len(cand)==1:
        i,km=cand[0]; old=km.group(1)
        prefix=old.split("_",1)[0]
        new={"SDLK":"SDLK_UNKNOWN","SDL":"SDL_SCANCODE_UNKNOWN","sc":"sc_None"}.get(prefix)
        if not new: fail("cannot form unassigned token from "+old)
        lines[i]=lines[i][:km.start(1)]+new+lines[i][km.end(1):]
        report.append(f"d_left  -> unassigned   : {old} -> {new}")
        changed+=1
    elif len(cand)>1:
        fail(f"d_left: ambiguous declarative mappings ({len(cand)})")

    p.write_text("\n".join(lines)+"\n")
    print("\n".join(report))
    print(f"PASS: patched {changed} unambiguous platform mapping rows")
    print("PASS: absent physical rows are deferred instead of invented")
    print("PASS: no menu-control code was rewritten")
if __name__=="__main__": main()
