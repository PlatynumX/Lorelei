#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R96C_N64_NOOP_DOLOADGAMEACTION"

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

def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("generated/rott")
    game_path = root / "rt_game.c"
    if not game_path.is_file():
        fail(f"missing {game_path}")

    text = game_path.read_text(encoding="utf-8", errors="strict")
    orig = text

    _start, open_brace, close_brace = find_function(text, "DoLoadGameAction")
    body = text[open_brace:close_brace]
    if MARK not in body:
        insert = "\n".join([
            "#ifdef __N64__",
            f"   /* {MARK}:",
            "      DoLoadGameAction only draws load-progress dots by swapping bufferofs to",
            "      displayofs and drawing tiny text. During N64 SD save restore this runs",
            "      dozens of times between LoadBuffer/Load* calls and can wedge the video/",
            "      input/audio pump path right after the SD activity flash. Save restore",
            "      does not require progress-dot rendering on console, so no-op it. */",
            "   return;",
            "#endif",
            "",
        ])
        at = open_brace + 1
        if at < len(text) and text[at] == "\n":
            at += 1
        text = text[:at] + insert + text[at:]

    _start, open_brace, close_brace = find_function(text, "DoLoadGameAction")
    body = text[open_brace:close_brace]
    for item in [
        MARK,
        "#ifdef __N64__",
        "return;",
        "bufferofs = displayofs",
        "VW_DrawPropString",
    ]:
        if item not in body:
            fail(f"DoLoadGameAction N64 no-op audit missing item: {item}")

    if body.find(MARK) > body.find("bufferofs = displayofs"):
        fail("N64 no-op guard must appear before progress-dot rendering")

    if text != orig:
        game_path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        print(f"PASS: {MARK} installed in {game_path}")
    else:
        print(f"PASS: {MARK} already present in {game_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
