#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R109_ROTTDS_SAVE_SCRATCH"
SCRATCH = "rott64_save_scratch"

RETURN_TYPES = {
    "ROTT64_ValidateSaveGameFile": "boolean",
    "GetSavedMessage": "void",
    "ScanForSavedGames": "void",
    "CP_DrawSelectedGame": "void",
    "DoLoad": "int",
    "QuickSaveGame": "void",
    "CP_SaveGame": "int",
}


def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)


def function_span(text: str, name: str) -> tuple[int, int, int]:
    rtype = RETURN_TYPES.get(name)
    if rtype is None:
        fail("no verified return type registered for " + name)

    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?{re.escape(rtype)}[ \t]+"
        rf"{re.escape(name)}[ \t]*\([^;{{}}]*\)[ \t\r\n]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected exactly one {rtype} {name} definition, found {len(hits)}")

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


def pointerize_local_game(func: str, name: str) -> str:
    decl = re.compile(
        r"(?m)^(?P<indent>[ \t]*)gamestorage_t[ \t]+game[ \t]*;[ \t]*$"
    )
    hits = list(decl.finditer(func))
    if len(hits) != 1:
        fail(
            f"{name}: expected exactly one automatic gamestorage_t game; "
            f"found {len(hits)}"
        )

    m = hits[0]
    replacement = (
        m.group("indent")
        + f"gamestorage_t *game = &{SCRATCH}; /* {MARK} */"
    )
    func = func[:m.start()] + replacement + func[m.end():]

    func = re.sub(r"\bgame\.", "game->", func)
    func = re.sub(r"\bsizeof[ \t]*\([ \t]*game[ \t]*\)", "sizeof(*game)", func)
    func = re.sub(r"\bsizeof[ \t]+game\b", "sizeof(*game)", func)
    func = re.sub(r"&game\b(?![ \t]*->)", "game", func)

    if re.search(r"(?m)^[ \t]*gamestorage_t[ \t]+game[ \t]*;", func):
        fail(name + ": automatic gamestorage_t survived")
    if re.search(r"\bgame\.", func):
        fail(name + ": dot access survived pointer conversion")

    return func


def patch_function(text: str, name: str) -> str:
    start, _open, end = function_span(text, name)
    func = pointerize_local_game(text[start:end], name)
    return text[:start] + func + text[end:]


def patch_rt_game(gen: Path) -> None:
    path = gen / "rt_game.c"
    if not path.is_file():
        fail("missing generated rt_game.c")

    text = path.read_text(encoding="utf-8", errors="strict")
    anchor = "static char *ROTT64_BuildSavePathForBase"

    if anchor not in text:
        fail("atomic save helper anchor missing")

    if f"gamestorage_t {SCRATCH};" not in text:
        pos = text.index(anchor)
        text = (
            text[:pos]
            + f"/* {MARK}: ROTTDS-style shared save header scratch.\n"
              " * gamestorage_t is >16 KiB; keep it off the N64 call stack.\n"
              " */\n"
            + f"gamestorage_t {SCRATCH};\n\n"
            + text[pos:]
        )

    text = patch_function(text, "ROTT64_ValidateSaveGameFile")
    text = patch_function(text, "GetSavedMessage")

    start, _open, end = function_span(text, "ROTT64_ValidateSaveGameFile")
    func = text[start:end]
    copy_pat = re.compile(
        r"if[ \t]*\([ \t]*out_game[ \t]*!=[ \t]*NULL[ \t]*\)[ \t]*\n"
        r"(?P<indent>[ \t]*)memcpy[ \t]*\([ \t]*out_game[ \t]*,[ \t]*game[ \t]*,"
        r"[ \t]*sizeof[ \t]*\([ \t]*\*game[ \t]*\)[ \t]*\)[ \t]*;"
    )
    hits = list(copy_pat.finditer(func))
    if len(hits) != 1:
        fail(
            "ROTT64_ValidateSaveGameFile: expected one out_game memcpy "
            f"after pointer conversion, found {len(hits)}"
        )
    m = hits[0]
    replacement = (
        "if (out_game != NULL && out_game != game)\n"
        + m.group("indent")
        + "memcpy(out_game, game, sizeof(*game));"
    )
    func = func[:m.start()] + replacement + func[m.end():]
    text = text[:start] + func + text[end:]

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def patch_rt_menu(gen: Path) -> None:
    path = gen / "rt_menu.c"
    if not path.is_file():
        fail("missing generated rt_menu.c")

    text = path.read_text(encoding="utf-8", errors="strict")
    validator_decl = (
        "extern boolean ROTT64_ValidateSaveGameSlot(int num, "
        "gamestorage_t *game, boolean strict);"
    )
    if validator_decl not in text:
        fail("atomic validator declaration missing")

    scratch_decl = f"extern gamestorage_t {SCRATCH}; /* {MARK} */"
    if scratch_decl not in text:
        pos = text.index(validator_decl) + len(validator_decl)
        text = text[:pos] + "\n" + scratch_decl + text[pos:]

    for name in (
        "ScanForSavedGames",
        "CP_DrawSelectedGame",
        "DoLoad",
        "QuickSaveGame",
        "CP_SaveGame",
    ):
        text = patch_function(text, name)

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def audit(gen: Path) -> None:
    game = (gen / "rt_game.c").read_text(encoding="utf-8", errors="strict")
    menu = (gen / "rt_menu.c").read_text(encoding="utf-8", errors="strict")
    if game.count(f"gamestorage_t {SCRATCH};") != 1:
        fail("shared save scratch definition count is not 1")
    if menu.count(f"extern gamestorage_t {SCRATCH};") != 1:
        fail("shared save scratch extern count is not 1")
    for name, text in (
        ("ROTT64_ValidateSaveGameFile", game),
        ("GetSavedMessage", game),
        ("ScanForSavedGames", menu),
        ("CP_DrawSelectedGame", menu),
        ("DoLoad", menu),
        ("QuickSaveGame", menu),
        ("CP_SaveGame", menu),
    ):
        start, _o, end = function_span(text, name)
        body = text[start:end]
        if re.search(r"(?m)^[ \t]*gamestorage_t[ \t]+game[ \t]*;", body):
            fail(name + ": stack gamestorage_t survived")
        if SCRATCH not in body:
            fail(name + ": shared scratch missing")
    if "out_game != NULL && out_game != game" not in game:
        fail("validator self-copy guard missing")
    print("PASS: ROTT64_R109_ROTTDS_SAVE_SCRATCH")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r109_patch_rottds_save_scratch.py generated/rott")
    gen = Path(argv[1])
    patch_rt_game(gen)
    patch_rt_menu(gen)
    audit(gen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
