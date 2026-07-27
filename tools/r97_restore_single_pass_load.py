#!/usr/bin/env python3
from pathlib import Path
import re
import sys

MARK = "ROTT64_R97_TARADINO_SINGLE_PASS_LOAD"

def fail(msg):
    raise SystemExit("ERROR: " + msg)

def function_span(text, name):
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?[^#;\n{{}}]*\b{re.escape(name)}[ \t]*"
        rf"\([^;\n{{}}]*\)[ \t]*\r?\n?[ \t]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected exactly one {name} definition, found {len(hits)}")
    m = hits[0]
    o = text.find("{", m.start(), m.end())
    depth = 0
    state = "code"
    quote = ""
    i = o
    while i < len(text):
        c = text[i]
        n = text[i+1] if i+1 < len(text) else ""
        if state == "code":
            if c == "/" and n == "*": state="block"; i+=2; continue
            if c == "/" and n == "/": state="line"; i+=2; continue
            if c in "\"'": state="string"; quote=c; i+=1; continue
            if c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return m.start(), o, i+1
            i += 1
        elif state == "block":
            if c == "*" and n == "/": state="code"; i+=2
            else: i+=1
        elif state == "line":
            if c == "\n": state="code"
            i+=1
        else:
            if c == "\\": i+=2; continue
            if c == quote: state="code"
            i+=1
    fail("unterminated " + name)

def main(argv):
    if len(argv) != 2:
        fail("usage: r97_restore_single_pass_load.py generated/rott")

    path = Path(argv[1]) / "rt_game.c"
    if not path.is_file():
        fail("missing " + str(path))

    text = path.read_text(encoding="utf-8", errors="strict")
    a, o, b = function_span(text, "LoadTheGame")
    func = text[a:b]

    pat = re.compile(
        r'''(?ms)
        [ \t]*/\*[ \t]*ROTT64_R[0-9A-Z_]*LOAD_VALIDATE_BEFORE_FULL_LOAD[ \t]*\*/[ \t]*\r?\n
        [ \t]*if[ \t]*\([ \t]*!ROTT64_ValidateSaveGameSlot[ \t]*\(
            [ \t]*num[ \t]*,[ \t]*NULL[ \t]*,[ \t]*true[ \t]*\)[ \t]*\)[ \t]*\r?\n
        [ \t]*\{[ \t]*\r?\n
        [ \t]*free[ \t]*\([ \t]*filename[ \t]*\)[ \t]*;[ \t]*\r?\n
        [ \t]*return[ \t]+false[ \t]*;[ \t]*\r?\n
        [ \t]*\}[ \t]*\r?\n
        ''',
        re.X
    )

    new_func, n = pat.subn(
        "\n    /* " + MARK + ": no second full-file checksum/read before stock restore. */\n",
        func,
        count=1
    )

    if n != 1:
        nearby = []
        for line in func.splitlines():
            if "ValidateSaveGameSlot" in line or "LOAD_VALIDATE" in line:
                nearby.append(line)
        fail("expected r96 pre-load validator block not found; nearby: " + " | ".join(nearby[:12]))

    if "ROTT64_ValidateSaveGameSlot" in new_func:
        fail("LoadTheGame still contains ROTT64_ValidateSaveGameSlot after patch")

    text = text[:a] + new_func + text[b:]
    if MARK not in text:
        fail("r97 marker missing after patch")

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    print("PASS:", MARK)
    print("PASS: LoadTheGame no longer performs an extra full-file validation/read")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
