#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R116_YAY_LOAD_TRACE"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def function_span(text: str, name: str) -> tuple[int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?boolean[ \t]+{re.escape(name)}"
        rf"[ \t]*\([^;{{}}]*\)[ \t\r\n]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected one boolean {name} definition, found {len(hits)}")
    m = hits[0]
    open_brace = text.find("{", m.start(), m.end())
    depth = 0
    state = "code"
    quote = ""
    i = open_brace
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if c == "/" and n == "*":
                state = "block"; i += 2; continue
            if c == "/" and n == "/":
                state = "line"; i += 2; continue
            if c in ("'", '"'):
                state = "string"; quote = c; i += 1; continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return m.start(), i + 1
            i += 1
            continue
        if state == "block":
            if c == "*" and n == "/":
                state = "code"; i += 2
            else:
                i += 1
            continue
        if state == "line":
            if c == "\n":
                state = "code"
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if c == quote:
            state = "code"
        i += 1
    fail("unterminated function: " + name)

def yay(n: int, label: str) -> str:
    return f'n64_platform_checkpoint("YAY {n:02d}  {label}");'

def before_once(body: str, token: str, insert: str, label: str) -> str:
    count = body.count(token)
    if count != 1:
        fail(f"{label}: expected one anchor, found {count}")
    return body.replace(token, insert + "\n\t" + token, 1)

def insert_before_between(
    body: str,
    start_token: str,
    end_token: str,
    target: str,
    insert: str,
    label: str,
) -> str:
    a = body.find(start_token)
    if a < 0:
        fail(label + ": start anchor missing")
    b = body.find(end_token, a + len(start_token))
    if b < 0:
        fail(label + ": end anchor missing")
    p = body.find(target, a, b)
    if p < 0:
        fail(label + ": target missing in section")
    if body.find(target, p + len(target), b) >= 0:
        fail(label + ": target is ambiguous in section")
    return body[:p] + insert + "\n\t" + body[p:]

def patch_body(body: str) -> str:
    if MARK in body:
        return body
    if "ROTT64_R115_ISOLATE_AFTER_OBJECT_RESTORE" in body:
        fail("r115 early-return diagnostic is already applied; r116 must replace it in workflow")

    # First checkpoint is immediately after the boundary already proven by r114.
    precache_end = "cache_transpatch_t);"
    if body.count(precache_end) != 1:
        fail(f"bullet-hole precache tail count is {body.count(precache_end)}, expected 1")
    body = body.replace(
        precache_end,
        precache_end
        + "\n\t/* "
        + MARK
        + ": simple YAY screens; a freeze leaves the last completed stage visible. */"
        + "\n\t"
        + yay(0, "LEVEL READY"),
        1,
    )

    # A YAY before each next tag proves the whole previous object block,
    # including LoadTag, LoadBuffer, object loader, and SafeFree, completed.
    object_boundaries = (
        ('LoadTag(&bufptr, "ELEVATORS", size);', 1, "DOORS"),
        ('LoadTag(&bufptr, "PWALL", size);', 2, "ELEVATORS"),
        ('LoadTag(&bufptr, "MWALL", size);', 3, "PUSHWALLS"),
        ('LoadTag(&bufptr, "SWITCH", size);', 4, "MASKED WALLS"),
        ('LoadTag(&bufptr, "STATIC", size);', 5, "SWITCHES"),
        ('LoadTag(&bufptr, "ACTOR", size);', 6, "STATICS"),
        ('LoadTag(&bufptr, "TOUCH", size);', 7, "ACTORS"),
        ("SetupWindows();", 8, "TOUCHPLATES"),
        ('LoadTag(&bufptr, "GAMESTATE", size);', 9, "WINDOWS"),
        ('LoadTag(&bufptr, "PLAYERSTATES", size);', 10, "GAMESTATE"),
        ('LoadTag(&bufptr, "MAPSEEN", size);', 11, "PLAYERSTATES"),
        ('LoadTag(&bufptr, "SONG", size);', 12, "MAPSEEN"),
    )
    for anchor, n, label in object_boundaries:
        body = before_once(body, anchor, yay(n, label), label)

    song_start = 'LoadTag(&bufptr, "SONG", size);'
    song_end = 'LoadTag(&bufptr, "MISC", size);'
    body = insert_before_between(
        body, song_start, song_end,
        "MU_LoadMusic(altbuffer, size);",
        yay(13, "SONG BUFFER"),
        "song buffer"
    )
    body = insert_before_between(
        body, song_start, song_end,
        "SafeFree(altbuffer);",
        yay(14, "MUSIC LOAD"),
        "music load"
    )
    body = before_once(body, song_end, yay(15, "SONG FREE"), "song free")

    body = before_once(body, "SetViewSize(viewsize);", yay(16, "MISC DATA"), "misc data")
    body = before_once(body, "ConnectAreas();", yay(17, "VIEW SIZE"), "view size")
    body = before_once(body, "SafeFree(loadbuffer);", yay(18, "CONNECT AREAS"), "connect areas")
    body = before_once(body, "Illuminate();", yay(19, "LOADBUFFER FREE"), "loadbuffer free")
    body = before_once(body, "IN_UpdateKeyboard();", yay(20, "ILLUMINATE"), "illuminate")
    body = before_once(body, "LoadPlayer();", yay(21, "KEYBOARD"), "keyboard")
    body = before_once(body, "SetupPlayScreen();", yay(22, "LOAD PLAYER"), "load player")
    body = before_once(body, "UpdateScore(gamestate.score);", yay(23, "PLAY SCREEN"), "play screen")
    body = before_once(body, "PreCache();", yay(24, "HUD"), "HUD")
    body = before_once(body, "InitializeMessages();", yay(25, "PRECACHE"), "precache")
    body = before_once(body, "for (i = 0; i < 100; i++)", yay(26, "MESSAGES"), "messages")

    calc = "CalcTics();"
    calc_hits = [m.start() for m in re.finditer(re.escape(calc), body)]
    if len(calc_hits) < 2:
        fail("fewer than two CalcTics calls in LoadTheGame")
    # Use the first CalcTics after the light loop.
    light = body.index("for (i = 0; i < 100; i++)")
    calc_after = [p for p in calc_hits if p > light]
    if len(calc_after) != 2:
        fail(f"expected exactly two CalcTics calls after light loop, found {len(calc_after)}")
    p = calc_after[0]
    body = body[:p] + yay(27, "LIGHTS") + "\n\t" + body[p:]

    body = before_once(body, "return (true);", yay(28, "LOAD COMPLETE"), "true return")
    return body

def audit(text: str) -> None:
    if text.count('#include "n64_platform.h"') != 1:
        fail("n64_platform.h include count is not exactly one")
    start, end = function_span(text, "LoadTheGame")
    body = text[start:end]
    if body.count(MARK) != 1:
        fail("r116 trace marker count is not exactly one")
    if "ROTT64_R115_ISOLATE_AFTER_OBJECT_RESTORE" in body:
        fail("stale r115 early-return marker survived")
    for n in range(29):
        token = f'n64_platform_checkpoint("YAY {n:02d}  '
        if body.count(token) != 1:
            fail(f"YAY {n:02d} count is {body.count(token)}, expected 1")

    required = (
        'LoadTag(&bufptr, "DOOR", size);',
        "LoadDoors(altbuffer, size);",
        "LoadElevators(altbuffer, size);",
        "LoadPushWalls(altbuffer, size);",
        "LoadMaskedWalls(altbuffer, size);",
        "LoadSwitches(altbuffer, size);",
        "LoadStatics(altbuffer, size);",
        "LoadActors(altbuffer, size);",
        "LoadTouchPlates(altbuffer, size);",
        "SetupWindows();",
        'LoadTag(&bufptr, "GAMESTATE", size);',
        'LoadTag(&bufptr, "PLAYERSTATES", size);',
        'LoadTag(&bufptr, "MAPSEEN", size);',
        'LoadTag(&bufptr, "SONG", size);',
        "MU_LoadMusic(altbuffer, size);",
        'LoadTag(&bufptr, "MISC", size);',
        "SafeFree(loadbuffer);",
        "LoadPlayer();",
        "SetupPlayScreen();",
        "PreCache();",
        "InitializeMessages();",
        "return (true);",
    )
    for token in required:
        if token not in body:
            fail("stock load path missing after trace instrumentation: " + token)

    positions = [body.index(f'n64_platform_checkpoint("YAY {n:02d}  ') for n in range(29)]
    if positions != sorted(positions):
        fail("YAY checkpoints are not in strict numerical order")

    print("PASS: 29 YAY checkpoints instrument the complete post-r114 restore path")
    print("PASS: stock restore calls and successful return remain intact")
    print("PASS: stale r115 early-return diagnostic is absent")

def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] != "--check"):
        fail("usage: r116_trace_load_yay.py generated/rott [--check]")
    root = Path(argv[1])
    game_path = root / "rt_game.c"
    if not game_path.is_file():
        fail("generated rt_game.c not found")
    s = game_path.read_text(encoding="utf-8", errors="strict")
    if len(argv) == 3:
        audit(s)
        return 0

    if "ROTT64_R115_ISOLATE_AFTER_OBJECT_RESTORE" in s:
        fail("r115 is already applied; remove it from workflow before r116")

    if '#include "n64_platform.h"' not in s:
        anchor = '#include "develop.h"'
        if s.count(anchor) != 1:
            fail(f"develop.h include count is {s.count(anchor)}, expected 1")
        s = s.replace(
            anchor,
            anchor + '\n#ifdef __N64__\n#include "n64_platform.h"\n#endif',
            1,
        )
    elif s.count('#include "n64_platform.h"') != 1:
        fail("n64_platform.h include is duplicated")

    start, end = function_span(s, "LoadTheGame")
    s = s[:start] + patch_body(s[start:end]) + s[end:]
    game_path.write_text(s.rstrip() + "\n", encoding="utf-8", newline="\n")
    audit(game_path.read_text(encoding="utf-8", errors="strict"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
