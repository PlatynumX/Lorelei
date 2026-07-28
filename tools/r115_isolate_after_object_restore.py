#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R115_ISOLATE_AFTER_OBJECT_RESTORE"
OLD_MARK = "ROTT64_R114_ISOLATE_AFTER_LEVEL_SETUP"


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
                    return m.start(), open_brace, i + 1
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


def one(body: str, token: str, label: str) -> int:
    count = body.count(token)
    if count != 1:
        fail(f"{label}: expected exactly one occurrence, found {count}")
    return body.index(token)


def after(body: str, token: str, pos: int, label: str) -> int:
    hit = body.find(token, pos)
    if hit < 0:
        fail(f"{label}: not found after expected predecessor")
    return hit


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
    p["setup"] = one(body, "SetupGameLevel();", "SetupGameLevel")
    p["precache"] = one(body, 'PreCacheGroup(W_GetNumForName("BULLETHO"), W_GetNumForName("ALTBHO"),', "bullet-hole precache")

    sequence = (
        ("door_tag", 'LoadTag(&bufptr, "DOOR", size);', "DOOR tag"),
        ("doors", "LoadDoors(altbuffer, size);", "LoadDoors"),
        ("elev_tag", 'LoadTag(&bufptr, "ELEVATORS", size);', "ELEVATORS tag"),
        ("elev", "LoadElevators(altbuffer, size);", "LoadElevators"),
        ("pwall_tag", 'LoadTag(&bufptr, "PWALL", size);', "PWALL tag"),
        ("pwall", "LoadPushWalls(altbuffer, size);", "LoadPushWalls"),
        ("mwall_tag", 'LoadTag(&bufptr, "MWALL", size);', "MWALL tag"),
        ("mwall", "LoadMaskedWalls(altbuffer, size);", "LoadMaskedWalls"),
        ("switch_tag", 'LoadTag(&bufptr, "SWITCH", size);', "SWITCH tag"),
        ("switch", "LoadSwitches(altbuffer, size);", "LoadSwitches"),
        ("static_tag", 'LoadTag(&bufptr, "STATIC", size);', "STATIC tag"),
        ("static", "LoadStatics(altbuffer, size);", "LoadStatics"),
        ("actor_tag", 'LoadTag(&bufptr, "ACTOR", size);', "ACTOR tag"),
        ("actor", "LoadActors(altbuffer, size);", "LoadActors"),
        ("touch_tag", 'LoadTag(&bufptr, "TOUCH", size);', "TOUCH tag"),
        ("touch", "LoadTouchPlates(altbuffer, size);", "LoadTouchPlates"),
        ("windows", "SetupWindows();", "SetupWindows"),
        ("gamestate_tag", 'LoadTag(&bufptr, "GAMESTATE", size);', "GAMESTATE tag"),
    )
    cursor = p["precache"]
    for key, token, label in sequence:
        cursor = after(body, token, cursor, label)
        p[key] = cursor

    # Every object section above uses one serialized LoadBuffer before its loader.
    object_pairs = (
        ("door_tag", "doors"),
        ("elev_tag", "elev"),
        ("pwall_tag", "pwall"),
        ("mwall_tag", "mwall"),
        ("switch_tag", "switch"),
        ("static_tag", "static"),
        ("actor_tag", "actor"),
        ("touch_tag", "touch"),
    )
    p["object_loadbuffers"] = []
    for tag_key, load_key in object_pairs:
        hit = body.find("size = LoadBuffer(&altbuffer, &bufptr);", p[tag_key], p[load_key])
        if hit < 0:
            fail(f"serialized LoadBuffer missing between {tag_key} and {load_key}")
        p["object_loadbuffers"].append(hit)

    p["mark"] = body.find(MARK)
    return p


def audit(game: str, util: str) -> None:
    if OLD_MARK in game:
        fail("stale r114 diagnostic marker survived into generated rt_game.c")
    if util.count("ROTT64_R111_STDIO_LOADFILE") != 1:
        fail("exact r111 stdio LoadFile marker is not present once in rt_util.c")
    for baseline in ("ROTT64_R109_ROTTDS_SAVE_SCRATCH", "ROTT64_R110_MESSAGE_HEADER_ONLY"):
        if baseline not in game:
            fail("required save baseline missing from rt_game.c: " + baseline)

    start, _open, end = function_span(game, "LoadTheGame")
    body = game[start:end]
    if body.count(MARK) != 1:
        fail("r115 diagnostic marker count in LoadTheGame is not exactly one")
    p = positions(body)
    if p["mark"] < 0:
        fail("r115 marker position not found")

    core_order = [
        p["load"], p["checksum"], p["rott"], p["header"], p["mapcrc"], p["mapfail"],
        p["setup"], p["precache"], p["door_tag"], p["doors"], p["elev_tag"], p["elev"],
        p["pwall_tag"], p["pwall"], p["mwall_tag"], p["mwall"], p["switch_tag"], p["switch"],
        p["static_tag"], p["static"], p["actor_tag"], p["actor"], p["touch_tag"], p["touch"],
        p["windows"], p["mark"], p["gamestate_tag"],
    ]
    if core_order != sorted(core_order):
        fail("LoadTheGame validation -> object restore -> r115 -> GAMESTATE order is not exact")
    for lb in p["object_loadbuffers"]:
        if not (p["door_tag"] < lb < p["mark"]):
            fail("object LoadBuffer escaped expected pre-r115 region")

    guard_start = body.rfind("#ifdef __N64__", p["windows"], p["mark"])
    if guard_start < 0:
        fail("r115 #ifdef __N64__ guard not found after SetupWindows")
    guard_end = body.find("#endif", p["mark"], p["gamestate_tag"])
    if guard_end < 0:
        fail("r115 #endif not found before GAMESTATE")
    diagnostic = body[guard_start:guard_end + len("#endif")]
    for required in (
        "#ifdef __N64__",
        MARK,
        "return false;",
        "DOOR through TOUCH",
        "SetupWindows completed",
        "before GAMESTATE",
    ):
        if required not in diagnostic:
            fail("r115 diagnostic block missing: " + required)

    before = body[:guard_start]
    for required in (
        'LoadTag(&bufptr, "DOOR", size);',
        "LoadDoors(altbuffer, size);",
        'LoadTag(&bufptr, "ELEVATORS", size);',
        "LoadElevators(altbuffer, size);",
        'LoadTag(&bufptr, "PWALL", size);',
        "LoadPushWalls(altbuffer, size);",
        'LoadTag(&bufptr, "MWALL", size);',
        "LoadMaskedWalls(altbuffer, size);",
        'LoadTag(&bufptr, "SWITCH", size);',
        "LoadSwitches(altbuffer, size);",
        'LoadTag(&bufptr, "STATIC", size);',
        "LoadStatics(altbuffer, size);",
        'LoadTag(&bufptr, "ACTOR", size);',
        "LoadActors(altbuffer, size);",
        'LoadTag(&bufptr, "TOUCH", size);',
        "LoadTouchPlates(altbuffer, size);",
        "SetupWindows();",
    ):
        if required not in before:
            fail("required object restore work does not occur before r115: " + required)
    if before.count("size = LoadBuffer(&altbuffer, &bufptr);") < 8:
        fail("fewer than eight serialized object LoadBuffer calls occur before r115")

    after_guard = body[guard_end + len("#endif"):]
    for forbidden in (
        'LoadTag(&bufptr, "GAMESTATE", size);',
        'LoadTag(&bufptr, "PLAYERSTATES", size);',
        'LoadTag(&bufptr, "MAPSEEN", size);',
        'LoadTag(&bufptr, "SONG", size);',
        'LoadTag(&bufptr, "MISC", size);',
        "MU_LoadMusic(altbuffer, size);",
        "LoadPlayer();",
        "SetupPlayScreen();",
        "PreCache();",
        "return (true);",
    ):
        if forbidden not in after_guard:
            fail("stock post-r115 restore code missing: " + forbidden)

    print("PASS: file/checksum/header/map validation executes before r115")
    print("PASS: level rebuild plus DOOR/ELEVATORS/PWALL/MWALL/SWITCH/STATIC/ACTOR/TOUCH restore executes before r115")
    print("PASS: SetupWindows executes before r115")
    print("PASS: r115 returns before GAMESTATE/PLAYERSTATES/MAPSEEN/SONG/MISC restore")


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] != "--check"):
        fail("usage: r115_isolate_after_object_restore.py generated/rott [--check]")
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
        fail("r114 diagnostic is still applied; r115 must patch the clean r111-generated path")

    if MARK not in game:
        start, _open, end = function_span(game, "LoadTheGame")
        body = game[start:end]
        windows = one(body, "SetupWindows();", "SetupWindows")
        game_tag = one(body, 'LoadTag(&bufptr, "GAMESTATE", size);', "GAMESTATE tag")
        if windows >= game_tag:
            fail("SetupWindows no longer precedes GAMESTATE")
        between = body[windows:game_tag]
        if between.count("SetupWindows();") != 1:
            fail("SetupWindows -> GAMESTATE boundary is ambiguous")

        line_end = body.find("\n", windows)
        if line_end < 0:
            fail("SetupWindows line ending not found")
        insert_at = line_end + 1
        line_start = body.rfind("\n", 0, windows) + 1
        indent = body[line_start:windows]
        if indent.strip():
            fail("unexpected non-whitespace before SetupWindows")

        insert = (
            "#ifdef __N64__\n"
            + indent + "/* ROTT64_R115_ISOLATE_AFTER_OBJECT_RESTORE:\n"
            + indent + "   DIAGNOSTIC ONLY. DOOR through TOUCH serialized object restore and\n"
            + indent + "   SetupWindows completed. Return before GAMESTATE/PLAYERSTATES and\n"
            + indent + "   all later state/music/misc restoration. */\n"
            + indent + "return false;\n"
            + "#endif\n"
        )
        body = body[:insert_at] + insert + body[insert_at:]
        game = game[:start] + body + game[end:]
        game_path.write_text(game.rstrip() + "\n", encoding="utf-8", newline="\n")

    audit(
        game_path.read_text(encoding="utf-8", errors="strict"),
        util_path.read_text(encoding="utf-8", errors="strict"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
