#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R113_ISOLATE_BEFORE_LEVEL_TEARDOWN"
OLD_MARK = "ROTT64_R112_ISOLATE_IMMEDIATELY_AFTER_LOADFILE"


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


def one(body: str, token: str, label: str) -> int:
    count = body.count(token)
    if count != 1:
        fail(f"{label}: expected exactly one occurrence, found {count}")
    return body.index(token)


def audit(game: str, util: str) -> None:
    if OLD_MARK in game:
        fail("stale r112 diagnostic marker survived into generated rt_game.c")
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
        fail("r113 diagnostic marker count in LoadTheGame is not exactly one")

    tokens = {
        "load": 'totalsize = LoadFile(filename, (void **)&loadbuffer);',
        "bufptr": "bufptr = loadbuffer;",
        "free_filename": "free(filename);",
        "checksum": "checksum = DoCheckSum(loadbuffer, totalsize - sizeof(checksum), 0);",
        "saved_checksum": "memcpy(&savedchecksum, loadbuffer + (totalsize - sizeof(savedchecksum)),",
        "rott_tag": 'LoadTag(&bufptr, "ROTT", size);',
        "header": "memcpy(game, bufptr, size);",
        "version": "if (game->version != ROTTVERSION)",
        "map_crc": "mapcrc = GetMapCRC(gamestate.mapon);",
        "map_fail": "if (mapcrc != game->mapcrc)",
        "mark": MARK,
        "printf": 'printf("Load Game: Using ROTTMAPS = %s\\n", ROTTMAPS);',
        "free_level": "Z_FreeTags(PU_LEVELSTRUCT, PU_LEVELEND);",
        "setup": "SetupGameLevel();",
    }
    pos = {k: one(body, v, k) for k, v in tokens.items() if k != "map_crc"}

    # GetMapCRC legitimately appears in the initial lookup and again inside the
    # episode-search loop. We only need to prove at least one lookup precedes
    # the final map mismatch check and the r113 boundary.
    map_hits = [m.start() for m in re.finditer(re.escape(tokens["map_crc"]), body)]
    if not map_hits:
        fail("no GetMapCRC(gamestate.mapon) call found in LoadTheGame")
    first_map_crc = map_hits[0]
    first_loadbuffer = body.find("size = LoadBuffer(&altbuffer, &bufptr);", pos["setup"])
    if first_loadbuffer < 0:
        fail("no serialized LoadBuffer found after SetupGameLevel")

    ordered = (
        pos["load"] < pos["bufptr"] < pos["free_filename"] < pos["checksum"]
        < pos["saved_checksum"] < pos["rott_tag"] < pos["header"] < pos["version"]
        < first_map_crc < pos["map_fail"] < pos["mark"] < pos["printf"]
        < pos["free_level"] < pos["setup"] < first_loadbuffer
    )
    if not ordered:
        fail("LoadTheGame validation -> r113 -> teardown/restore ordering is not exact")

    guard_start = body.rfind("#ifdef __N64__", pos["map_fail"], pos["mark"])
    if guard_start < 0:
        fail("r113 #ifdef __N64__ guard not found immediately before marker")
    guard_end = body.find("#endif", pos["mark"], pos["printf"])
    if guard_end < 0:
        fail("r113 #endif not found before stock printf/teardown")
    diagnostic = body[guard_start:guard_end + len("#endif")]
    for required in (
        "#ifdef __N64__",
        MARK,
        "return false;",
        "before Z_FreeTags",
    ):
        if required not in diagnostic:
            fail("r113 diagnostic block missing: " + required)

    # Nothing that destroys/rebuilds level state or consumes serialized body
    # data may execute before the r113 return. File/header/checksum/map checks
    # are intentionally allowed and required above.
    before = body[:guard_start]
    destructive = (
        "Z_FreeTags(",
        "InitStaticList(",
        "BATTLE_SetOptions(",
        "BATTLE_Init(",
        "SetupGameLevel(",
        "PreCacheGroup(",
        "LoadBuffer(",
        "LoadDoors(",
        "LoadElevators(",
        "LoadPushWalls(",
        "LoadMaskedWalls(",
        "LoadSwitches(",
        "LoadStatics(",
        "LoadActors(",
        "LoadTouchPlates(",
        "SetupWindows(",
        "MU_LoadMusic(",
        "LoadPlayer(",
        "SetupPlayScreen(",
        "PreCache();",
    )
    for token in destructive:
        if token in before:
            fail("destructive/deserialize work occurs before r113 return: " + token)

    # The stock restore body must remain behind the diagnostic return.
    after = body[guard_end + len("#endif"):]
    for required in (
        'printf("Load Game: Using ROTTMAPS = %s\\n", ROTTMAPS);',
        "Z_FreeTags(PU_LEVELSTRUCT, PU_LEVELEND);",
        "InitStaticList();",
        "BATTLE_SetOptions(&BATTLE_Options[battle_StandAloneGame]);",
        "BATTLE_Init(gamestate.battlemode, 1);",
        "SetupGameLevel();",
        "PreCacheGroup(",
        'LoadTag(&bufptr, "DOOR", size);',
        "size = LoadBuffer(&altbuffer, &bufptr);",
        "LoadDoors(altbuffer, size);",
    ):
        if required not in after:
            fail("stock post-boundary restore code missing: " + required)

    print("PASS: full file/checksum/header/version/map validation executes before r113")
    print("PASS: r113 return occurs before Z_FreeTags / level rebuild / serialized body restore")
    print("PASS: stock destructive restore path remains intact after the diagnostic block")


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] != "--check"):
        fail("usage: r113_isolate_before_level_teardown.py generated/rott [--check]")

    gen = Path(argv[1])
    check_only = len(argv) == 3
    game_path = gen / "rt_game.c"
    util_path = gen / "rt_util.c"
    if not game_path.is_file() or not util_path.is_file():
        fail("generated rt_game.c/rt_util.c not found")

    game = game_path.read_text(encoding="utf-8", errors="strict")
    util = util_path.read_text(encoding="utf-8", errors="strict")

    if check_only:
        audit(game, util)
        return 0

    if OLD_MARK in game:
        fail("r112 diagnostic is still applied; r113 must patch the clean r111-generated path")

    if MARK not in game:
        start, _open, end = function_span(game, "LoadTheGame")
        body = game[start:end]
        printf_token = 'printf("Load Game: Using ROTTMAPS = %s\\n", ROTTMAPS);'
        if body.count(printf_token) != 1:
            fail("verified stock pre-teardown printf anchor count is not one")
        p_printf = body.index(printf_token)
        line_start = body.rfind("\n", 0, p_printf) + 1
        indent = body[line_start:p_printf]
        if indent.strip():
            fail("unexpected non-whitespace before stock pre-teardown printf")

        map_if = "if (mapcrc != game->mapcrc)"
        p_map_if = body.rfind(map_if, 0, p_printf)
        if p_map_if < 0:
            fail("final map CRC mismatch guard not found before teardown anchor")
        between = body[p_map_if:p_printf]
        if between.count("return false;") != 1:
            fail("final map CRC guard does not contain exactly one return false")
        for forbidden in ("Z_FreeTags(", "SetupGameLevel(", "LoadBuffer("):
            if forbidden in between:
                fail("destructive work unexpectedly appears before stock teardown anchor: " + forbidden)

        insert = (
            "#ifdef __N64__\n"
            + indent + "/* ROTT64_R113_ISOLATE_BEFORE_LEVEL_TEARDOWN:\n"
            + indent + "   DIAGNOSTIC ONLY. LoadFile, full checksum, saved checksum fetch,\n"
            + indent + "   ROTT tag/header/version checks, and map CRC lookup all completed.\n"
            + indent + "   Return before Z_FreeTags, level rebuild, or serialized body restore. */\n"
            + indent + "return false;\n"
            + "#endif\n"
        )
        body = body[:line_start] + insert + body[line_start:]
        game = game[:start] + body + game[end:]
        game_path.write_text(game.rstrip() + "\n", encoding="utf-8", newline="\n")

    audit(
        game_path.read_text(encoding="utf-8", errors="strict"),
        util_path.read_text(encoding="utf-8", errors="strict"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
