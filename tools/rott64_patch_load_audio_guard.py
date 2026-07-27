#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK_HELPER = "ROTT64_R94A_LOAD_AUDIO_GUARD_HELPER"
MARK_CALL = "ROTT64_R94A_STOP_AUDIO_BEFORE_LOAD"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def find_function(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(r"(?m)^[A-Za-z_][A-Za-z0-9_ \t\*]*\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{", re.S)
    m = pat.search(text)
    if not m:
        fail(f"function {name} not found")
    open_brace = text.find("{", m.start(), m.end())
    if open_brace < 0:
        fail(f"opening brace for {name} not found")
    depth = 0
    i = open_brace
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return m.start(), open_brace, i
        i += 1
    fail(f"closing brace for {name} not found")

def insert_after_open_brace(text: str, open_brace: int, block: str) -> str:
    insert_at = open_brace + 1
    if insert_at < len(text) and text[insert_at] == "\n":
        insert_at += 1
    return text[:insert_at] + block + text[insert_at:]

def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("generated/rott")
    game_path = root / "rt_game.c"
    if not game_path.is_file():
        fail(f"missing {game_path}")

    text = game_path.read_text(encoding="utf-8", errors="strict")
    orig = text

    if MARK_HELPER not in text:
        decl_start, _open, _close = find_function(text, "LoadTheGame")
        helper = f"""
/* {MARK_HELPER}:
   Loading a save can run menu/input waits while the libdragon mixer is still
   pulling VADPCM music. On N64 that exposed invalid wav64 seek-point asserts
   such as rom:/rott/music/suckthis.wav64 during Load Game. Stop active music
   and SFX before restoring the saved game; the loaded level will start its
   correct music normally after restore. */
#ifdef __N64__
extern void MU_StopSong(void);
extern void SD_StopAllSounds(void);
#endif
static void rott64_r94a_stop_audio_before_load(void)
{{
#ifdef __N64__
    MU_StopSong();
    SD_StopAllSounds();
#endif
}}

"""
        text = text[:decl_start] + helper + text[decl_start:]

    decl_start, open_brace, close_brace = find_function(text, "LoadTheGame")
    load_body = text[open_brace:close_brace]
    if MARK_CALL not in load_body:
        call = f"""#ifdef __N64__
    /* {MARK_CALL} */
    rott64_r94a_stop_audio_before_load();
#endif
"""
        text = insert_after_open_brace(text, open_brace, call)

    decl_start, open_brace, close_brace = find_function(text, "LoadTheGame")
    load_body = text[open_brace:close_brace]
    for item in [
        MARK_HELPER,
        MARK_CALL,
        "rott64_r94a_stop_audio_before_load();",
        "MU_StopSong();",
        "SD_StopAllSounds();",
    ]:
        if item not in text:
            fail(f"missing generated load audio guard item: {item}")
    if load_body.count(MARK_CALL) != 1:
        fail("LoadTheGame must contain exactly one stop-audio guard call")

    if text != orig:
        game_path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        print(f"PASS: {MARK_CALL} installed in {game_path}")
    else:
        print(f"PASS: {MARK_CALL} already present in {game_path}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
