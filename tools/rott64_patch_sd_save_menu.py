#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import sys

MARK = "ROTT64_R94F_SD_SAVE_MENU_HELPER"
HELPER = "rott64_r94f_existing_save_path"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def helper_definition_exists(text: str) -> bool:
    return re.search(
        r"(?m)^static[ \t]+char[ \t]*\*[ \t]*" + re.escape(HELPER) + r"[ \t]*\(",
        text,
    ) is not None

def ensure_stdio(text: str) -> str:
    if "#include <stdio.h>" in text:
        return text
    incs = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if incs:
        return text[:incs[-1].end()] + "#include <stdio.h>\n" + text[incs[-1].end():]
    return "#include <stdio.h>\n" + text

def ensure_helper(text: str) -> str:
    if helper_definition_exists(text):
        return text
    helper = (
        f"\n/* {MARK}: return path only when save file exists. */\n"
        f"static char *{HELPER}(const char *path)\n"
        "{\n"
        "    FILE *fp;\n\n"
        "    if (path == NULL)\n"
        "        return NULL;\n\n"
        "    fp = fopen(path, \"rb\");\n"
        "    if (fp == NULL)\n"
        "        return NULL;\n\n"
        "    fclose(fp);\n"
        "    return (char *)path;\n"
        "}\n\n"
    )
    m = re.search(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+ScanForSavedGames[ \t]*\(", text)
    if not m:
        fail("ScanForSavedGames not found")
    return text[:m.start()] + helper + text[m.start():]

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r94f_patch_sd_save_menu.py generated/rott")
    menu = Path(argv[1]) / "rt_menu.c"
    if not menu.is_file():
        fail("missing generated rt_menu.c")

    text = menu.read_text(encoding="utf-8", errors="strict")
    original = text
    n_total = 0

    text = ensure_stdio(text)

    text, n = re.subn(
        r"\brott64_r\d+[a-z]?_existing_save_path\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        HELPER + r"(\1)",
        text,
    )
    n_total += n

    text, n = re.subn(
        r"\brott64_save_case_exists\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        HELPER + r"(\1)",
        text,
    )
    n_total += n

    text, n = re.subn(
        r"(\b[A-Za-z_][A-Za-z0-9_]*\s*=\s*[^;\n?]+?\?\s*)fopen\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*\"rb\"\s*\)(\s*:\s*NULL\s*;)",
        r"\1" + HELPER + r"(\2)\3",
        text,
    )
    n_total += n

    text, n = re.subn(
        r"\brott64_save_unlink\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;",
        r"remove(\1);",
        text,
    )
    n_total += n

    text, n = re.subn(
        r"(if\s*\(\s*!rott64_n64_sd_saves_ready\s*\(\s*\)\s*\)\s*\n[ \t]*)return\s*;",
        r"\1return 0;",
        text,
    )
    n_total += n

    text = ensure_helper(text)

    for stale in ("rott64_save_case_exists", "rott64_save_unlink"):
        if stale in text:
            fail("stale helper survived: " + stale)
    if re.search(r"=\s*[^;\n?]+?\?\s*fopen\s*\([^;\n]+:\s*NULL\s*;", text):
        fail("bad FILE*/char* fopen conditional survived")

    definition_match = re.search(
        r"(?m)^static[ \t]+char[ \t]*\*[ \t]*" + re.escape(HELPER) + r"[ \t]*\(",
        text,
    )
    first_call = text.find(HELPER + "(")
    if definition_match is None or first_call < 0:
        fail("helper definition/call missing")
    if first_call < definition_match.start():
        fail("helper is called before it is defined")

    if MARK not in text:
        text = "/* " + MARK + " */\n" + text

    if text != original:
        menu.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    print("PASS: " + MARK)
    print(f"PASS: replacements/guard updates: {n_total}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
