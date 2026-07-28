#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R114_ISOLATE_AFTER_LEVEL_SETUP"
OLD_MARK = "ROTT64_R113_ISOLATE_BEFORE_LEVEL_TEARDOWN"


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


def positions(body: str) -> dict[str, int]:
    p: dict[str, int] = {}
    p["load"] = one(body, 'totalsize = LoadFile(filename, (void **)&loadbuffer);', "LoadFile")
    p["checksum"] = one(body, "checksum = DoCheckSum(loadbuffer, totalsize - sizeof(checksum), 0);", "checksum")
    p["rott"] = one(body, 'LoadTag(&bufptr, "ROTT", size);', "ROTT tag")
    p["header"] = one(body, "memcpy(game, bufptr, size);", "header memcpy")
    map_hits = [m.start() for m in re.finditer(re.escape("mapcrc = GetMapCRC(gamestate.mapon);"), body)]
    if not map_hits:
        fail("no GetMapCRC(gamestate.mapon) call found")
    p["mapcrc"] = map_hits[0]
    p["mapfail"] = one(body, "if (mapcrc != game->mapcrc)", "final map mismatch")
    p["printf"] = one(body, 'printf("Load Game: Using ROTTMAPS = %s\\n", ROTTMAPS);', "map printf")
    p["free"] = one(body, "Z_FreeTags(PU_LEVELSTRUCT, PU_LEVELEND);", "Z_FreeTags")
    p["init"] = one(body, "InitStaticList();", "InitStaticList")
    p["battle_opts"] = one(body, "BATTLE_SetOptions(&BATTLE_Options[battle_StandAloneGame]);", "BATTLE_SetOptions")
    p["battle_init"] = one(body, "BATTLE_Init(gamestate.battlemode, 1);", "BATTLE_Init")
    p["setup"] = one(body, "SetupGameLevel();", "SetupGameLevel")
    p["precache"] = one(body, "PreCacheGroup(W_GetNumForName(\"BULLETHO\"), W_GetNumForName(\"ALTBHO\"),", "BULLETHO PreCacheGroup")
    p["door"] = one(body, 'LoadTag(&bufptr, "DOOR", size);', "DOOR tag")
    first_loadbuffer = body.find("size = LoadBuffer(&altbuffer, &bufptr);", p["door"])
    if first_loadbuffer < 0:
        fail("first serialized LoadBuffer after DOOR tag not found")
    p["loadbuffer"] = first_loadbuffer
    p["loaddoors"] = one(body, "LoadDoors(altbuffer, size);", "LoadDoors")
    p["mark"] = body.find(MARK)
    return p


def audit(game: str, util: str) -> None:
    if OLD_MARK in game:
        fail("stale r113 diagnostic marker survived into generated rt_game.c")
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
        fail("r114 diagnostic marker count in LoadTheGame is not exactly one")

    p = positions(body)
    if p["mark"] < 0:
        fail("r114 marker position not found")
    ordered = (
        p["load"] < p["checksum"] < p["rott"] < p["header"] < p["mapcrc"]
        < p["mapfail"] < p["printf"] < p["free"] < p["init"]
        < p["battle_opts"] < p["battle_init"] < p["setup"] < p["precache"]
        < p["mark"] < p["door"] < p["loadbuffer"] < p["loaddoors"]
    )
    if not ordered:
        fail("LoadTheGame validation -> teardown/setup -> r114 -> DOOR restore ordering is not exact")

    guard_start = body.rfind("#ifdef __N64__", p["precache"], p["mark"])
    if guard_start < 0:
        fail("r114 #ifdef __N64__ guard not found after PreCacheGroup")
    guard_end = body.find("#endif", p["mark"], p["door"])
    if guard_end < 0:
        fail("r114 #endif not found before DOOR tag")
    diagnostic = body[guard_start:guard_end + len("#endif")]
    for required in (
        "#ifdef __N64__",
        MARK,
        "return false;",
        "SetupGameLevel and BULLETHO/ALTBHO PreCacheGroup completed",
        "before DOOR tag or serialized LoadBuffer",
    ):
        if required not in diagnostic:
            fail("r114 diagnostic block missing: " + required)

    before_guard = body[:guard_start]
    for required in (
        "Z_FreeTags(PU_LEVELSTRUCT, PU_LEVELEND);",
        "InitStaticList();",
        "BATTLE_SetOptions(&BATTLE_Options[battle_StandAloneGame]);",
        "BATTLE_Init(gamestate.battlemode, 1);",
        "SetupGameLevel();",
        "PreCacheGroup(W_GetNumForName(\"BULLETHO\"), W_GetNumForName(\"ALTBHO\"),",
    ):
        if required not in before_guard:
            fail("required teardown/setup work does not occur before r114: " + required)

    # No serialized save body may be consumed before the diagnostic return.
    forbidden_before = (
        'LoadTag(&bufptr, "DOOR", size);',
        "size = LoadBuffer(&altbuffer, &bufptr);",
        "LoadDoors(altbuffer, size);",
        "LoadElevators(altbuffer, size);",
        "LoadPushWalls(altbuffer, size);",
        "LoadMaskedWalls(altbuffer, size);",
        "LoadSwitches(altbuffer, size);",
        "LoadStatics(altbuffer, size);",
        "LoadActors(altbuffer, size);",
        "LoadTouchPlates(altbuffer, size);",
    )
    for token in forbidden_before:
        if token in before_guard:
            fail("serialized restore work occurs before r114 return: " + token)

    after = body[guard_end + len("#endif"):]
    for required in (
        'LoadTag(&bufptr, "DOOR", size);',
        "size = LoadBuffer(&altbuffer, &bufptr);",
        "LoadDoors(altbuffer, size);",
        'LoadTag(&bufptr, "ELEVATORS", size);',
        "LoadElevators(altbuffer, size);",
        'LoadTag(&bufptr, "ACTOR", size);',
        "LoadActors(altbuffer, size);",
        'LoadTag(&bufptr, "SONG", size);',
        "MU_LoadMusic(altbuffer, size);",
        "SafeFree(loadbuffer);",
        "LoadPlayer();",
        "SetupPlayScreen();",
        "PreCache();",
        "return (true);",
    ):
        if required not in after:
            fail("stock post-r114 restore code missing: " + required)

    print("PASS: file/checksum/header/map validation executes before r114")
    print("PASS: Z_FreeTags + list/battle reset + SetupGameLevel + bullet-hole precache execute before r114")
    print("PASS: r114 returns before DOOR tag and every serialized LoadBuffer restore")
    print("PASS: complete stock serialized restore path remains intact behind the diagnostic return")


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] != "--check"):
        fail("usage: r114_isolate_after_level_setup.py generated/rott [--check]")

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
        fail("r113 diagnostic is still applied; r114 must patch the clean r111-generated path")

    if MARK not in game:
        start, _open, end = function_span(game, "LoadTheGame")
        body = game[start:end]

        setup = one(body, "SetupGameLevel();", "SetupGameLevel")
        precache = one(
            body,
            'PreCacheGroup(W_GetNumForName("BULLETHO"), W_GetNumForName("ALTBHO"),',
            "BULLETHO PreCacheGroup",
        )
        door = one(body, 'LoadTag(&bufptr, "DOOR", size);', "DOOR tag")
        first_loadbuffer = body.find("size = LoadBuffer(&altbuffer, &bufptr);", door)
        if first_loadbuffer < 0:
            fail("first serialized LoadBuffer after DOOR not found")
        if not (setup < precache < door < first_loadbuffer):
            fail("SetupGameLevel -> PreCacheGroup -> DOOR -> LoadBuffer ordering changed")

        # Insert before the unique size=4 statement that directly feeds DOOR LoadTag.
        size_pos = body.rfind("size = 4;", precache, door)
        if size_pos < 0:
            fail("DOOR size=4 assignment not found after PreCacheGroup")
        between_size_and_door = body[size_pos:door]
        if between_size_and_door.count("size = 4;") != 1:
            fail("DOOR size assignment anchor is ambiguous")
        line_start = body.rfind("\n", 0, size_pos) + 1
        indent = body[line_start:size_pos]
        if indent.strip():
            fail("unexpected non-whitespace before DOOR size assignment")

        insert = (
            "#ifdef __N64__\n"
            + indent + "/* ROTT64_R114_ISOLATE_AFTER_LEVEL_SETUP:\n"
            + indent + "   DIAGNOSTIC ONLY. Z_FreeTags, list/battle reset,\n"
            + indent + "   SetupGameLevel and BULLETHO/ALTBHO PreCacheGroup completed.\n"
            + indent + "   Return before DOOR tag or serialized LoadBuffer restore. */\n"
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
