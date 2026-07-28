#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R112_ISOLATE_IMMEDIATELY_AFTER_LOADFILE"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def function_span(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?boolean[ \t]+{re.escape(name)}"
        rf"[ \t]*\([^;{{}}]*\)[ \t\r\n]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected exactly one boolean {name} definition, found {len(hits)}")

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
                state = "block"
                i += 2
                continue
            if c == "/" and n == "/":
                state = "line"
                i += 2
                continue
            if c in ("'", '"'):
                state = "string"
                quote = c
                i += 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return m.start(), open_brace, i + 1
            i += 1
            continue

        if state == "block":
            if c == "*" and n == "/":
                state = "code"
                i += 2
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

def audit(game: str, util: str) -> None:
    if util.count("ROTT64_R111_STDIO_LOADFILE") != 1:
        fail("exact r111 stdio LoadFile marker is not present once in rt_util.c")

    for baseline in (
        "ROTT64_R109_ROTTDS_SAVE_SCRATCH",
        "ROTT64_R110_MESSAGE_HEADER_ONLY",
    ):
        if baseline not in game:
            fail("required save baseline missing from rt_game.c: " + baseline)

    start, _open, end = function_span(game, "LoadTheGame")
    body = game[start:end]

    if body.count(MARK) != 1:
        fail("r112 isolation marker count in LoadTheGame is not exactly one")

    load = 'totalsize = LoadFile(filename, (void **)&loadbuffer);'
    checksum = 'checksum = DoCheckSum(loadbuffer, totalsize - sizeof(checksum), 0);'

    if body.count(load) != 1:
        fail("LoadTheGame does not contain exactly one verified LoadFile call")
    if body.count(checksum) != 1:
        fail("LoadTheGame does not contain exactly one stock full-buffer checksum")

    p_load = body.index(load)
    p_mark = body.index(MARK)
    p_buf = body.index("bufptr = loadbuffer;")
    p_free = body.index("free(filename);")
    p_crc = body.index(checksum)
    p_ifdef = body.rfind("#ifdef __N64__", p_load, p_mark)

    if p_ifdef < 0:
        fail("r112 N64 preprocessor guard not found before diagnostic marker")
    if not (p_load < p_ifdef < p_mark < p_buf < p_free < p_crc):
        fail("r112 boundary is not immediately after LoadFile and before all consumers")

    marker_window = body[p_ifdef:p_buf]
    for required in (
        "#ifdef __N64__",
        "return false;",
        "do not free loadbuffer",
    ):
        if required not in marker_window:
            fail("r112 diagnostic block missing: " + required)

    forbidden = (
        "SafeFree(",
        "free(",
        "DoCheckSum(",
        "memcpy(",
        "LoadTag(",
        "GetMapCRC(",
        "SetupGameLevel(",
        "LoadBuffer(",
    )
    for token in forbidden:
        if token in marker_window:
            fail("r112 diagnostic block executes extra work before return: " + token)

    print("PASS: r112 return is the first N64 action after LoadFile()")
    print("PASS: no free/checksum/tag/deserialize/level setup occurs before diagnostic return")
    print("PASS: stock checksum and restore code remain intact after the diagnostic block")

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r112_isolate_after_loadfile.py generated/rott")

    gen = Path(argv[1])
    game_path = gen / "rt_game.c"
    util_path = gen / "rt_util.c"
    if not game_path.is_file() or not util_path.is_file():
        fail("generated rt_game.c/rt_util.c not found")

    game = game_path.read_text(encoding="utf-8", errors="strict")
    util = util_path.read_text(encoding="utf-8", errors="strict")

    if MARK not in game:
        start, _open, end = function_span(game, "LoadTheGame")
        body = game[start:end]
        anchor = 'totalsize = LoadFile(filename, (void **)&loadbuffer);'
        if body.count(anchor) != 1:
            fail("verified LoadTheGame LoadFile anchor count is not one")

        insert = anchor + r'''
#ifdef __N64__
    /* ROTT64_R112_ISOLATE_IMMEDIATELY_AFTER_LOADFILE:
       DIAGNOSTIC ONLY. If control reaches here, r111 LoadFile() returned.
       Return before bufptr assignment, filename free, SafeFree, checksum,
       tag parsing, map CRC lookup, level teardown, or any deserialize work.
       Deliberately do not free loadbuffer/filename: even a free would add
       another possible freeze point and muddy this one-test boundary. */
    return false;
#endif
'''
        body = body.replace(anchor, insert, 1)
        game = game[:start] + body + game[end:]
        game_path.write_text(game.rstrip() + "\n", encoding="utf-8", newline="\n")

    audit(
        game_path.read_text(encoding="utf-8", errors="strict"),
        util_path.read_text(encoding="utf-8", errors="strict"),
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
