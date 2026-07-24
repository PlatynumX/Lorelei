#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R88_SD_SAVE_PATH"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def function_span(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?"
        rf"[^;\n{{}}]*\b{re.escape(name)}[ \t]*\([^;\n]*\)"
        rf"[ \t]*\r?\n?[ \t]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected one {name} definition, found {len(hits)}")
    m = hits[0]
    o = text.find("{", m.start(), m.end())
    depth = 0
    state = "code"
    quote = ""
    i = o
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if c == "/" and n == "*":
                state = "block"; i += 2; continue
            if c == "/" and n == "/":
                state = "line"; i += 2; continue
            if c in ("'", '"'):
                state = "str"; quote = c; i += 1; continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return m.start(), o, i + 1
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
    fail("unterminated function " + name)

def patch_main(path: Path) -> None:
    s = path.read_text(encoding="utf-8", errors="strict")
    if MARK in s:
        return

    old = "ApogeePath = GetPrefDir();"
    if s.count(old) != 1:
        fail(
            f"expected exactly one '{old}' in generated rt_main.c, "
            f"found {s.count(old)}"
        )

    replacement = r'''#if defined(__N64__)
    /* ROTT64_R88_SD_SAVE_PATH
     * Keep Taradino's normal file-based persistence. Only move the writable
     * preference/save root onto libdragon's SD filesystem when available.
     */
    extern int rott64_n64_sd_saves_ready(void);
    extern const char *rott64_n64_sd_save_root(void);

    if (rott64_n64_sd_saves_ready())
    {
        const char *rott64_r88_root = rott64_n64_sd_save_root();
        ApogeePath = malloc(strlen(rott64_r88_root) + 1);
        if (ApogeePath == NULL)
            Error("ROTT64: could not allocate SD preference path");
        strcpy(ApogeePath, rott64_r88_root);
    }
    else
    {
        ApogeePath = GetPrefDir();
    }
#else
    ApogeePath = GetPrefDir();
#endif'''

    s = s.replace(old, replacement, 1)
    path.write_text(s.rstrip() + "\n", encoding="utf-8", newline="\n")

def add_guard(text: str, fn: str, mark: str) -> str:
    a, o, b = function_span(text, fn)
    body = text[a:b]
    if mark in body:
        return text

    guard = f'''
#if defined(__N64__)
    /* {mark} */
    extern int rott64_n64_sd_saves_ready(void);
    if (!rott64_n64_sd_saves_ready())
        return;
#endif
'''
    return text[:o + 1] + guard + text[o + 1:]

def patch_menu(path: Path) -> None:
    s = path.read_text(encoding="utf-8", errors="strict")

    # Proof that generation is back on Taradino's normal file-save path.
    for token in (
        "ScanForSavedGames",
        "GetSavedMessage",
        "CP_SaveGame",
        "CP_LoadGame",
        "SaveGamesAvail",
        "rottgam?.rot",
        "M_StringJoin(ApogeePath",
    ):
        if token not in s:
            fail("generated stock save/menu path missing " + token)

    for stale in (
        "rott64_flash_save",
        "r45c-save-reader-owners",
        "ROTT64_FLASH_SAVE",
    ):
        if stale in s:
            fail("old custom save code leaked into generated menu: " + stale)

    if "ROTT64_R88_SD_MENU_GUARD" not in s:
        a, o, b = function_span(s, "ScanForSavedGames")
        guard = r'''
#if defined(__N64__)
    /* ROTT64_R88_SD_MENU_GUARD */
    extern int rott64_n64_sd_saves_ready(void);
    if (!rott64_n64_sd_saves_ready())
    {
        memset(&SaveGamesAvail[0], 0, sizeof(SaveGamesAvail));
        MainMenu[loadgame].active = CP_Inactive;
        MainMenu[savegame].active = CP_Inactive;
        return;
    }
#endif
'''
        s = s[:o + 1] + guard + s[o + 1:]

    s = add_guard(s, "CP_SaveGame", "ROTT64_R88_SD_GUARD_CP_SaveGame")
    s = add_guard(s, "CP_LoadGame", "ROTT64_R88_SD_GUARD_CP_LoadGame")

    path.write_text(s.rstrip() + "\n", encoding="utf-8", newline="\n")

def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: r88_patch_sd_saves.py <generated-rott-root>")
    root = Path(sys.argv[1]).resolve()
    main_c = root / "rt_main.c"
    menu_c = root / "rt_menu.c"
    if not main_c.is_file() or not menu_c.is_file():
        fail("generated rt_main.c/rt_menu.c missing")

    patch_main(main_c)
    patch_menu(menu_c)

    print("PASS: N64 writable Taradino root points at libdragon SD")
    print("PASS: stock Taradino Save/Load serialization retained")

if __name__ == "__main__":
    main()
