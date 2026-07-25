#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R91A_START_INGAME_SAVE_CONTEXT"

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def add_include(text: str, include: str) -> str:
    if include in text:
        return text
    incs = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if incs:
        return text[:incs[-1].end()] + include + "\n" + text[incs[-1].end():]
    return include + "\n" + text

def function_span(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?[^#;\n{{}}]*\b{re.escape(name)}[ \t]*"
        rf"\([^;\n{{}}]*\)[ \t]*\r?\n?[ \t]*\{{"
    )
    hits = list(pat.finditer(text))
    if not hits:
        fail("function not found: " + name)
    if len(hits) > 1:
        fail("multiple functions found: " + name)

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
    fail("unterminated function: " + name)

def find_existing_game_state_symbol(texts: dict[str, str]) -> str:
    blob = "\n".join(texts.values())
    if "gamestate.mapon" in blob or ("gamestate" in blob and "mapon" in blob):
        return "gamestate.mapon"
    if "gamestate.TimeCount" in blob or ("gamestate" in blob and "TimeCount" in blob):
        return "gamestate.TimeCount"
    if re.search(r"\bplayer\b", blob):
        return "player"
    fail("could not find a generated gameplay-state symbol for save guard")

def guard_expr(symbol: str) -> str:
    if symbol == "gamestate.mapon":
        return "(gamestate.mapon >= 0)"
    if symbol == "gamestate.TimeCount":
        return "(gamestate.TimeCount > 0)"
    if symbol == "player":
        return "(player != NULL)"
    return "(" + symbol + ")"

def patch_menu(gen: Path) -> None:
    menu = gen / "rt_menu.c"
    if not menu.is_file():
        fail("missing generated rt_menu.c")

    texts = {p.name: p.read_text(encoding="utf-8", errors="ignore") for p in gen.glob("*.c")}
    state_symbol = find_existing_game_state_symbol(texts)
    expr = guard_expr(state_symbol)

    text = menu.read_text(encoding="utf-8", errors="strict")
    original = text
    text = add_include(text, "#include <stdio.h>")

    helper_name = "rott64_r91a_can_save_in_current_context"
    if helper_name not in text:
        helper = (
            f"\n/* {MARK}: saves require an active gameplay context, not title/menu state. */\n"
            f"static int {helper_name}(void)\n"
            "{\n"
            f"    return {expr};\n"
            "}\n\n"
        )
        m = re.search(r"(?m)^[ \t]*(?:static[ \t]+)?int[ \t]+CP_SaveGame[ \t]*\(", text)
        if not m:
            m = re.search(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+ScanForSavedGames[ \t]*\(", text)
        if not m:
            fail("could not locate CP_SaveGame/ScanForSavedGames for save-context helper")
        text = text[:m.start()] + helper + text[m.start():]

    a, o, b = function_span(text, "CP_SaveGame")
    func = text[a:b]
    if "ROTT64_R91A_SAVE_CONTEXT_GUARD" not in func:
        insert = (
            "{\n"
            "    /* ROTT64_R91A_SAVE_CONTEXT_GUARD */\n"
            f"    if (!{helper_name}())\n"
            "    {\n"
            "        printf(\"ROTT64 r91a: Save rejected outside active game context\\n\");\n"
            "        return 0;\n"
            "    }\n"
        )
        func = func[:func.find("{")] + insert + func[func.find("{")+1:]
        text = text[:a] + func + text[b:]

    if MARK not in text:
        text = "/* " + MARK + " */\n" + text

    if text != original:
        menu.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    out = menu.read_text(encoding="utf-8", errors="ignore")
    if "ROTT64_R91A_SAVE_CONTEXT_GUARD" not in out:
        fail("save context guard did not apply")
    if helper_name not in out:
        fail("save context helper missing")

    print("PASS: " + MARK)
    print("PASS: save context guard uses " + state_symbol)

def patch_start_sources(gen: Path) -> None:
    changed = []
    suspicious = []
    roots = list(gen.glob("*.c")) + list(Path("platform/n64").glob("*.c"))
    for path in sorted(roots):
        text = path.read_text(encoding="utf-8", errors="ignore")
        original = text

        if "ROTT64_START_DIRECT_EX_TITLES" in text:
            suspicious.append(str(path) + ":ROTT64_START_DIRECT_EX_TITLES")

        # Only remove the known bad standalone direct jump inserted by old
        # Start patches. Do not rewrite normal title-screen code.
        text = re.sub(
            r"(?m)^([ \t]*)(?:return[ \t]+)?ex_titles[ \t]*\([^;\n]*\)[ \t]*;[ \t]*(?://.*)?$",
            r'\1/* ROTT64_R91A_START_NO_TITLE_JUMP: Start must use in-game ControlPanel/Escape path. */',
            text,
        )

        if text != original:
            path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
            changed.append(str(path))

    if suspicious:
        raise SystemExit(
            "ERROR: stale Start-to-title marker remains:\n" + "\n".join(suspicious)
        )

    print("PASS: Start-to-title marker absent")
    if changed:
        print("PASS: removed direct ex_titles Start jumps:")
        for item in changed:
            print("  " + item)
    else:
        print("PASS: no direct ex_titles Start jump found to remove")

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r91a_patch_start_save_context.py generated/rott")
    gen = Path(argv[1])
    if not gen.is_dir():
        fail("generated/rott directory not found")
    patch_menu(gen)
    patch_start_sources(gen)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
