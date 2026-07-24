#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R89J_GENERATED_MENU_POSTPATCH"
HELPER = "rott64_r89j_existing_save_path"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def ensure_stdio(text: str) -> str:
    if "#include <stdio.h>" in text:
        return text
    incs = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if incs:
        pos = incs[-1].end()
        return text[:pos] + "#include <stdio.h>\n" + text[pos:]
    return "#include <stdio.h>\n" + text

def ensure_helper(text: str) -> str:
    if HELPER in text or re.search(r"rott64_r\d+[a-z]?_existing_save_path", text):
        return text
    helper = (
        f"\n/* {MARK}: return save path only when it exists; do not assign FILE * to char *. */\n"
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
    m = re.search(r"(?m)^[ \t]*void[ \t]+ScanForSavedGames[ \t]*\(", text)
    if m:
        return text[:m.start()] + helper + text[m.start():]
    return helper + text

def patch_text(text: str) -> tuple[str, int]:
    n_total = 0
    text = ensure_stdio(text)

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

    text = ensure_helper(text)

    text, n = re.subn(
        r"(if\s*\(\s*!rott64_n64_sd_saves_ready\s*\(\s*\)\s*\)\s*\n[ \t]*)return\s*;",
        r"\1return 0;",
        text,
    )
    n_total += n

    if MARK not in text and (HELPER in text or "remove(" in text):
        text = "/* " + MARK + " */\n" + text

    return text, n_total

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r89j_post_patch_generated_menu.py generated/rott")

    menu = Path(argv[1]) / "rt_menu.c"
    if not menu.is_file():
        fail("missing generated rt_menu.c")

    text = menu.read_text(encoding="utf-8", errors="strict")
    patched, n = patch_text(text)

    for stale in ("rott64_save_case_exists", "rott64_save_unlink"):
        if stale in patched:
            fail("stale save helper survived: " + stale)

    if re.search(r"=\s*[^;\n?]+?\?\s*fopen\s*\([^;\n]+:\s*NULL\s*;", patched):
        fail("bad FILE*/char* fopen conditional survived")

    if patched != text:
        menu.write_text(patched.rstrip() + "\n", encoding="utf-8", newline="\n")

    print(f"PASS: {MARK}")
    print(f"PASS: save-menu replacements/guard updates: {n}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
