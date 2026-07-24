#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R89D_GENERATED_MENU_POSTPATCH"
HELPER = "rott64_r89d_existing_save_path"

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
                state = "string"; quote = c; i += 1; continue
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

def ensure_stdio(text: str) -> str:
    if "#include <stdio.h>" in text:
        return text
    incs = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if incs:
        pos = incs[-1].end()
        return text[:pos] + "#include <stdio.h>\n" + text[pos:]
    return "#include <stdio.h>\n" + text

def ensure_helper(text: str) -> str:
    if "static char *" + HELPER in text:
        return text

    helper = f'''
/* {MARK}
 * Preserve the generated menu semantics: return a save path only when the
 * save file exists. Do not assign FILE * to char *.
 */
static char *{HELPER}(const char *path)
{{
    FILE *fp;

    if (path == NULL)
        return NULL;

    fp = fopen(path, "rb");
    if (fp == NULL)
        return NULL;

    fclose(fp);
    return (char *)path;
}}

'''
    try:
        a, _o, _b = function_span(text, "ScanForSavedGames")
        return text[:a] + helper + text[a:]
    except SystemExit:
        return helper + text

def replace_case_exists(text: str) -> tuple[str, int]:
    return re.subn(
        r"\brott64_save_case_exists\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        HELPER + r"(\1)",
        text,
    )

def replace_bad_fopen_assignment(text: str) -> tuple[str, int]:
    return re.subn(
        r"(\b[A-Za-z_][A-Za-z0-9_]*\s*=\s*[^;\n?]+?\?\s*)fopen\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*\"rb\"\s*\)(\s*:\s*NULL\s*;)",
        r"\1" + HELPER + r"(\2)\3",
        text,
    )

def replace_unlink(text: str) -> tuple[str, int]:
    return re.subn(
        r"\brott64_save_unlink\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;",
        r"remove(\1);",
        text,
    )

def fix_nonvoid_guard_return(text: str, fn: str) -> tuple[str, int]:
    a, _o, b = function_span(text, fn)
    body = text[a:b]

    if "ROTT64_R88_SD_GUARD_" not in body:
        fail(f"{fn} is missing the r88 SD availability guard")

    fixed, n = re.subn(
        r"(if\s*\(\s*!rott64_n64_sd_saves_ready\s*\(\s*\)\s*\)\s*\n[ \t]*)return\s*;",
        r"\1return 0;",
        body,
        count=1,
    )
    if n != 1 and "return 0;" not in body:
        fail(f"could not convert {fn} guard return to return 0")

    return text[:a] + fixed + text[b:], n

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r89d_post_patch_generated_menu.py generated/rott")

    gen = Path(argv[1])
    menu = gen / "rt_menu.c"
    if not menu.is_file():
        fail("missing generated rt_menu.c: " + str(menu))

    text = menu.read_text(encoding="utf-8", errors="strict")
    original = text

    text = ensure_stdio(text)
    text, n_exists = replace_case_exists(text)
    text, n_bad_fopen = replace_bad_fopen_assignment(text)
    text, n_unlink = replace_unlink(text)
    text = ensure_helper(text)
    text, n_load = fix_nonvoid_guard_return(text, "CP_LoadGame")
    text, n_save = fix_nonvoid_guard_return(text, "CP_SaveGame")

    for stale in ("rott64_save_case_exists", "rott64_save_unlink"):
        if stale in text:
            fail("stale old save helper survived in generated menu: " + stale)

    if re.search(r"=\s*[^;\n?]+?\?\s*fopen\s*\([^;\n]+:\s*NULL\s*;", text):
        fail("fopen() still feeds a conditional char* assignment")

    if n_exists == 0 and n_bad_fopen == 0 and HELPER + "(path)" not in text:
        fail("case-exists/helper path expression was not normalized")

    if n_unlink == 0 and "remove(filename);" not in text:
        fail("unlink helper was not replaced")

    if "static char *" + HELPER not in text:
        fail("save-existence helper definition was not inserted")

    for fn in ("CP_LoadGame", "CP_SaveGame"):
        a, _o, b = function_span(text, fn)
        body = text[a:b]
        if "ROTT64_R88_SD_GUARD_" in body and "return 0;" not in body:
            fail(fn + " still has a non-value SD guard return")

    if MARK not in text:
        text = "/* " + MARK + " */\n" + text

    if text != original:
        menu.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    print(f"PASS: {MARK}")
    print(f"PASS: rott64_save_case_exists replacements: {n_exists}")
    print(f"PASS: bad fopen conditional replacements: {n_bad_fopen}")
    print(f"PASS: unlink replacements: {n_unlink}")
    print(f"PASS: CP_LoadGame guard return updates: {n_load}")
    print(f"PASS: CP_SaveGame guard return updates: {n_save}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
