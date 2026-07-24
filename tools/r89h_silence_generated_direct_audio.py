#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R89H_GENERATED_DIRECT_AUDIO_DISABLED"

FORBIDDEN = (
    "mixer_ch_play",
    "mixer_ch_stop",
    "mixer_ch_playing",
    "mixer_poll",
    "mixer_init",
    "audio_init",
    "audio_write_begin",
    "audio_write_end",
    "rspq_highpri_sync",
    "rspq_block_begin",
    "rspq_block_run",
)

def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def scrub_for_scan(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    return text

def has_forbidden_call(text: str) -> bool:
    clean = scrub_for_scan(text)
    return any(
        re.search(r"\b" + re.escape(name) + r"\s*\(", clean)
        for name in FORBIDDEN
    )

def function_spans(text: str) -> list[tuple[str, int, int, int]]:
    pat = re.compile(
        r"(?m)^[ \t]*(?:static[ \t]+)?"
        r"[^#;\n{}][^;\n{}]*\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*"
        r"\([^;\n{}]*\)[ \t]*\r?\n?[ \t]*\{"
    )

    spans: list[tuple[str, int, int, int]] = []

    for m in pat.finditer(text):
        name = m.group(1)
        open_brace = text.find("{", m.start(), m.end())
        if open_brace < 0:
            continue

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
                        spans.append((name, m.start(), open_brace, i + 1))
                        break
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

    return spans

def return_stmt_for_signature(signature: str) -> str:
    compact = " ".join(signature.replace("\n", " ").split())
    if re.search(r"\bvoid\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", compact):
        return "return;"
    if "*" in compact.split("(", 1)[0]:
        return "return NULL;"
    return "return 0;"

def stub_func(text: str, start: int, open_brace: int, end: int) -> str:
    signature = text[start:open_brace].rstrip()
    ret = return_stmt_for_signature(signature)
    return (
        text[:start]
        + signature
        + "\n{\n"
        + f"    /* {MARK}: direct libdragon mixer/RSP playback disabled. */\n"
        + f"    {ret}\n"
        + "}\n"
        + text[end:]
    )

def strip_leftover_call_lines(text: str) -> tuple[str, int]:
    count = 0
    out = []
    for line in text.splitlines(True):
        if has_forbidden_call(line):
            out.append(f"/* {MARK}: removed one direct audio/RSP call line. */\n")
            count += 1
        else:
            out.append(line)
    return "".join(out), count

def process_file(path: Path) -> tuple[bool, int, int]:
    text = path.read_text(encoding="utf-8", errors="strict")
    original = text
    stubbed = 0

    while True:
        changed_this_round = False
        for _name, start, open_brace, end in reversed(function_spans(text)):
            body = text[start:end]
            if MARK in body:
                continue
            if has_forbidden_call(body):
                text = stub_func(text, start, open_brace, end)
                stubbed += 1
                changed_this_round = True
        if not changed_this_round:
            break

    text, stripped = strip_leftover_call_lines(text)

    if text != original:
        path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        return True, stubbed, stripped

    return False, 0, 0

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r89h_silence_generated_direct_audio.py generated/rott")

    gen = Path(argv[1])
    if not gen.is_dir():
        fail("generated/rott directory not found")

    changed_files: list[str] = []
    total_stubbed = 0
    total_stripped = 0

    # Scan every generated C file. r89f missed dukemusc.c because the filename
    # did not contain "music"; do not rely on filenames for this diagnostic.
    for path in sorted(gen.glob("*.c")):
        changed, stubbed, stripped = process_file(path)
        if changed:
            changed_files.append(str(path))
            total_stubbed += stubbed
            total_stripped += stripped

    remaining = []
    for path in sorted(gen.glob("*.c")):
        clean = scrub_for_scan(path.read_text(encoding="utf-8", errors="ignore"))
        for name in FORBIDDEN:
            if re.search(r"\b" + re.escape(name) + r"\s*\(", clean):
                remaining.append(f"{path}:{name}")

    if remaining:
        raise SystemExit(
            "ERROR: generated direct audio/RSP calls remain:\n"
            + "\n".join(remaining[:80])
        )

    if not changed_files:
        fail("no generated C files changed; expected direct audio/RSP calls to be present")

    print("PASS: " + MARK)
    print("PASS: changed generated C files:")
    for item in changed_files:
        print("  " + item)
    print(f"PASS: functions stubbed: {total_stubbed}")
    print(f"PASS: direct call lines removed/commented: {total_stripped}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
