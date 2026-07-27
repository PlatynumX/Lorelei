#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK_HELPER = "ROTT64_R94C_SAVE_LOAD_AUDIO_GUARD_HELPER"
MARK_LOAD = "ROTT64_R94C_STOP_AUDIO_BEFORE_LOAD"
MARK_SAVE = "ROTT64_R94C_STOP_AUDIO_BEFORE_SAVE"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def find_function(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(
        r"(?m)^[A-Za-z_][A-Za-z0-9_ \t\*]*\b"
        + re.escape(name)
        + r"\s*\([^;]*?\)\s*\{",
        re.S,
    )
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

def install_helper(text: str) -> str:
    if MARK_HELPER in text:
        return text

    save_start, _open, _close = find_function(text, "SaveTheGame")
    load_start, _open2, _close2 = find_function(text, "LoadTheGame")
    decl_start = min(save_start, load_start)

    helper = f"""
/* {MARK_HELPER}:
   On N64, the menu/input waits can continue polling the libdragon mixer while
   a VADPCM music stream is mid-transition. That exposed wav64_vadpcm_read
   seek-point assertions such as rom:/rott/music/suckthis.wav64 after Save
   and during Load. Stop active music/SFX before save/load menu waits. */
#ifdef __N64__
extern void MU_StopSong(void);
extern void SD_StopAllSounds(void);
#endif
static void rott64_r94c_stop_audio_for_save_load(void)
{{
#ifdef __N64__
    MU_StopSong();
    SD_StopAllSounds();
#endif
}}

"""
    return text[:decl_start] + helper + text[decl_start:]

def install_call(text: str, func: str, mark: str) -> str:
    decl_start, open_brace, close_brace = find_function(text, func)
    body = text[open_brace:close_brace]
    if mark in body:
        return text

    call = f"""#ifdef __N64__
    /* {mark} */
    rott64_r94c_stop_audio_for_save_load();
#endif
"""
    return insert_after_open_brace(text, open_brace, call)

def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("generated/rott")
    game_path = root / "rt_game.c"
    if not game_path.is_file():
        fail(f"missing {game_path}")

    text = game_path.read_text(encoding="utf-8", errors="strict")
    orig = text

    text = install_helper(text)
    text = install_call(text, "SaveTheGame", MARK_SAVE)
    text = install_call(text, "LoadTheGame", MARK_LOAD)

    for func, mark in [("SaveTheGame", MARK_SAVE), ("LoadTheGame", MARK_LOAD)]:
        _start, open_brace, close_brace = find_function(text, func)
        body = text[open_brace:close_brace]
        if body.count(mark) != 1:
            fail(f"{func} must contain exactly one audio stop guard call marker {mark}")

    for item in [
        MARK_HELPER,
        MARK_LOAD,
        MARK_SAVE,
        "rott64_r94c_stop_audio_for_save_load();",
        "MU_StopSong();",
        "SD_StopAllSounds();",
    ]:
        if item not in text:
            fail(f"missing generated save/load audio guard item: {item}")

    if text != orig:
        game_path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        print(f"PASS: {MARK_SAVE} and {MARK_LOAD} installed in {game_path}")
    else:
        print(f"PASS: {MARK_SAVE} and {MARK_LOAD} already present in {game_path}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
