#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK_SAVE = "ROTT64_R95E_N64_SKIP_SAVEGAME_MUSIC_SAVE"
MARK_LOAD = "ROTT64_R95E_N64_SKIP_SAVEGAME_MUSIC_LOAD"
OLD_SAVE_RE = re.compile(r"ROTT64_R95[A-Z]_N64_SKIP_SAVEGAME_MUSIC_SAVE")
OLD_LOAD_RE = re.compile(r"ROTT64_R95[A-Z]_N64_SKIP_SAVEGAME_MUSIC_LOAD")

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def nearby(text: str, needle: str) -> str:
    pos = text.find(needle)
    if pos < 0:
        return f"{needle!r} not found"
    lines = text.splitlines()
    char = 0
    line_no = 0
    for i, line in enumerate(lines):
        nxt = char + len(line) + 1
        if char <= pos < nxt:
            line_no = i
            break
        char = nxt
    lo = max(0, line_no - 8)
    hi = min(len(lines), line_no + 10)
    return "\n".join(f"{i+1}: {lines[i]}" for i in range(lo, hi))

def upgrade_old_markers(text: str) -> str:
    text = OLD_SAVE_RE.sub(MARK_SAVE, text)
    text = OLD_LOAD_RE.sub(MARK_LOAD, text)
    return text

def find_line_sequence(text: str, names: list[str]) -> tuple[int, int, str] | None:
    lines = text.splitlines(keepends=True)
    offsets = []
    n = 0
    for line in lines:
        offsets.append(n)
        n += len(line)

    for i, line in enumerate(lines):
        if names[0] not in line:
            continue
        j = i
        matched = [i]
        ok = True
        for name in names[1:]:
            found = None
            for k in range(j + 1, min(len(lines), j + 9)):
                if name in lines[k]:
                    found = k
                    break
            if found is None:
                ok = False
                break
            matched.append(found)
            j = found
        if ok:
            start = offsets[i]
            end_line = matched[-1]
            end = offsets[end_line] + len(lines[end_line])
            indent = re.match(r"([ \t]*)", lines[i]).group(1)
            return start, end, indent
    return None

def already_has_save_skip(text: str) -> bool:
    return (
        "SafeWrite(savehandle, &size, sizeof(size));" in text
        and ("SKIP_SAVEGAME_MUSIC_SAVE" in text or "zero-length" in text)
    )

def already_has_load_skip(text: str) -> bool:
    return (
        "memcpy(&size, bufptr, sizeof(size));" in text
        and "bufptr += sizeof(size);" in text
        and "bufptr += size;" in text
        and ("SKIP_SAVEGAME_MUSIC_LOAD" in text or "MU_LoadMusic on N64" in text)
    )

def patch_save_song(text: str) -> str:
    text = upgrade_old_markers(text)
    if MARK_SAVE in text:
        return text
    if already_has_save_skip(text):
        return text.replace("SKIP_SAVEGAME_MUSIC_SAVE", MARK_SAVE, 1) if "SKIP_SAVEGAME_MUSIC_SAVE" in text else text + f"\n/* {MARK_SAVE} already present by structure */\n"

    # First try a regex against the common generated shape.
    pat = re.compile(
        r"(?P<indent>^[ \t]*)MU_SaveMusic\s*\(\s*&altbuffer\s*,\s*&size\s*\)\s*;\s*\n"
        r"^[ \t]*StoreBuffer\s*\(\s*savehandle\s*,\s*altbuffer\s*,\s*size\s*\)\s*;\s*\n"
        r"^[ \t]*SafeFree\s*\(\s*altbuffer\s*\)\s*;",
        re.M,
    )
    m = pat.search(text)
    if m:
        start, end, I, old = m.start(), m.end(), m.group("indent"), m.group(0)
    else:
        seq = find_line_sequence(text, ["MU_SaveMusic", "StoreBuffer", "SafeFree"])
        if not seq:
            fail("could not find MU_SaveMusic savegame SONG block to replace\n" + nearby(text, "MU_SaveMusic"))
        start, end, I = seq
        old = text[start:end].rstrip("\n")

    new = "\n".join([
        f"{I}#ifdef __N64__",
        f"{I}/* {MARK_SAVE}: keep SONG tag/layout, but write a zero-length",
        f"{I}   music-state payload. Restoring the saved wav64/VADPCM stream",
        f"{I}   state on N64 can lock or assert inside wav64_vadpcm_read. */",
        f"{I}size = 0;",
        f"{I}SafeWrite(savehandle, &size, sizeof(size));",
        f"{I}#else",
        old,
        f"{I}#endif",
    ])
    return text[:start] + new + text[end:]

def patch_load_song(text: str) -> str:
    text = upgrade_old_markers(text)
    if MARK_LOAD in text:
        return text
    if already_has_load_skip(text):
        return text.replace("SKIP_SAVEGAME_MUSIC_LOAD", MARK_LOAD, 1) if "SKIP_SAVEGAME_MUSIC_LOAD" in text else text + f"\n/* {MARK_LOAD} already present by structure */\n"

    pat = re.compile(
        r"(?P<indent>^[ \t]*)size\s*=\s*LoadBuffer\s*\(\s*&altbuffer\s*,\s*&bufptr\s*\)\s*;\s*\n"
        r"^[ \t]*MU_LoadMusic\s*\(\s*altbuffer\s*,\s*size\s*\)\s*;\s*\n"
        r"^[ \t]*SafeFree\s*\(\s*altbuffer\s*\)\s*;",
        re.M,
    )
    m = pat.search(text)
    if m:
        start, end, I, old = m.start(), m.end(), m.group("indent"), m.group(0)
    else:
        seq = find_line_sequence(text, ["LoadBuffer", "MU_LoadMusic", "SafeFree"])
        if not seq:
            fail("could not find LoadBuffer/MU_LoadMusic savegame SONG block to replace\n" + nearby(text, "MU_LoadMusic"))
        start, end, I = seq
        old = text[start:end].rstrip("\n")

    new = "\n".join([
        f"{I}#ifdef __N64__",
        f"{I}/* {MARK_LOAD}: consume the saved SONG payload without calling",
        f"{I}   MU_LoadMusic on N64. Normal level/game music startup can resume",
        f"{I}   after load without resurrecting a stale wav64 stream. */",
        f"{I}memcpy(&size, bufptr, sizeof(size));",
        f"{I}bufptr += sizeof(size);",
        f"{I}bufptr += size;",
        f"{I}#else",
        old,
        f"{I}#endif",
    ])
    return text[:start] + new + text[end:]

def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("generated/rott")
    game_path = root / "rt_game.c"
    if not game_path.is_file():
        fail(f"missing {game_path}")

    text = game_path.read_text(encoding="utf-8", errors="strict")
    orig = text

    text = patch_save_song(text)
    text = patch_load_song(text)
    text = upgrade_old_markers(text)

    for item in [
        MARK_SAVE,
        MARK_LOAD,
        "SafeWrite(savehandle, &size, sizeof(size));",
        "memcpy(&size, bufptr, sizeof(size));",
        "bufptr += sizeof(size);",
        "bufptr += size;",
    ]:
        if item not in text:
            fail(f"missing N64 savegame music skip item: {item}")

    save_tag_re = re.compile(r'SaveTag\s*\(\s*savehandle\s*,\s*"SONG"\s*,\s*size\s*\)\s*;')
    load_tag_re = re.compile(r'LoadTag\s*\(\s*&bufptr\s*,\s*"SONG"\s*,\s*size\s*\)\s*;')
    if not save_tag_re.search(text):
        fail("SONG save tag missing after patch\n" + nearby(text, "SONG"))
    if not load_tag_re.search(text):
        fail("SONG load tag missing after patch\n" + nearby(text, "SONG"))

    if text != orig:
        game_path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        print(f"PASS: {MARK_SAVE} and {MARK_LOAD} installed/upgraded in {game_path}")
    else:
        print(f"PASS: {MARK_SAVE} and {MARK_LOAD} already present in {game_path}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
