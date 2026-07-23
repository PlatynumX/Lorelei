#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import sys

MARK = "ROTT64_R53_START_DIRECT_MAIN_MENU"
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("generated/rott").resolve()
REPORTS = ROOT.parent / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
REPORT = REPORTS / "r53-controls-direct-report.md"
report: list[str] = []

def log(msg: str) -> None:
    print(msg)
    report.append(msg)

def fail(msg: str) -> None:
    REPORT.write_text("\n".join(report + ["FAIL: " + msg]) + "\n", encoding="utf-8", newline="\n")
    raise SystemExit("r53_controls_direct.py: " + msg)

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8", newline="\n")

def only_file(name: str) -> Path:
    hits = [p for p in ROOT.rglob(name) if p.is_file()]
    if len(hits) != 1:
        fail(f"expected one {name} under {ROOT}, found {len(hits)}: " + ", ".join(str(p) for p in hits[:8]))
    return hits[0]

def function_span_containing(text: str, needle_pos: int):
    # Match normal generated C functions; then brace-parse safely enough for generated source.
    pattern = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?(?P<head>(?:[A-Za-z_][A-Za-z0-9_]*|[*])[A-Za-z0-9_ \t\*]*?[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*\([^;{}]*\))[ \t\r\n]*\{")
    best = None
    for m in pattern.finditer(text):
        op = text.find("{", m.start(), m.end())
        if op < 0 or op > needle_pos:
            continue
        depth = 0
        state = "code"
        quote = ""
        i = op
        close = None
        while i < len(text):
            c = text[i]
            n = text[i+1] if i+1 < len(text) else ""
            if state == "code":
                if c == "/" and n == "*":
                    state = "block"; i += 2; continue
                if c == "/" and n == "/":
                    state = "line"; i += 2; continue
                if c in "'\"":
                    state = "string"; quote = c; i += 1; continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        close = i
                        break
                i += 1
            elif state == "block":
                if c == "*" and n == "/":
                    state = "code"; i += 2
                else:
                    i += 1
            elif state == "line":
                if c == "\n":
                    state = "code"
                i += 1
            else:
                if c == "\\":
                    i += 2; continue
                if c == quote:
                    state = "code"
                i += 1
        if close is not None and m.start() <= needle_pos <= close:
            if m.group("name") in {"if", "while", "for", "switch"}:
                continue
            best = (m.start(), op, close, m.group("head"), m.group("name"))
    if best is None:
        fail("could not identify function containing CP_CheckQuick")
    return best

rt_main = only_file("rt_main.c")
rt_playr = only_file("rt_playr.c")
log(f"rt_main: {rt_main}")
log(f"rt_playr: {rt_playr}")

main = read(rt_main)
playr = read(rt_playr)

# Verify r49 actually patched generated gameplay movement and did not leave mouse movement active.
required_playr = [
    "ROTT64_NATIVE_GAMEPAD_XY_ENGINE_V3_SOURCE_AWARE",
    "extern void rott64_n64_gamepad_axes",
    "rott64_n64_gamepad_axes(&joyx, &joyy);",
    "PollJoystickMove();",
    "PollKeyboardMove();",
]
for token in required_playr:
    if token not in playr:
        fail("generated rt_playr.c missing required token after r49: " + token)
if "PollMouseMove();" in playr:
    fail("generated rt_playr.c still has active PollMouseMove();")
if "INL_GetJoyDelta" in playr:
    fail("generated rt_playr.c still has old PC joystick INL_GetJoyDelta path")
if "KEYBOARDNORMALTURNAMOUNT / 127" in playr or "BASEMOVE / 127" in playr:
    fail("generated rt_playr.c still has divide-before-multiply analog math")
if "((-joyx) * KEYBOARDNORMALTURNAMOUNT) / 127" not in playr or "(joyy * BASEMOVE) / 127" not in playr:
    fail("generated rt_playr.c does not show multiply-before-divide analog math")
log("PASS: generated rt_playr.c has r49 native analog, mouse move disabled, and safe analog math")

# Patch rt_main before CP_CheckQuick/ControlPanel.
if MARK in main:
    log("INFO: rt_main.c already contains r53 direct Start/Escape main-menu intercept")
else:
    cp_match = re.search(r"\bCP_CheckQuick\s*\(\s*LastScan\s*\)", main)
    if not cp_match:
        fail("CP_CheckQuick(LastScan) was not found in rt_main.c")

    fstart, fopen, fclose, head, fname = function_span_containing(main, cp_match.start())
    func = main[fstart:fclose+1]
    if fname != "PlayLoop":
        fail(f"CP_CheckQuick(LastScan) is inside {fname}, not PlayLoop")
    if not re.search(r"\bvoid\b[^\n;{}]*\bPlayLoop\s*\(", head):
        fail("PlayLoop signature does not look void; refusing to insert bare return")
    for token in ("LastScan", "ControlPanel", "playstate"):
        if token not in func:
            fail(f"PlayLoop containing CP_CheckQuick is missing expected token {token}")

    line_start = main.rfind("\n", 0, cp_match.start()) + 1
    indent = main[line_start:cp_match.start()]
    if not re.fullmatch(r"[ \t]*", indent):
        indent = re.match(r"[ \t]*", main[line_start:]).group(0)

    block = (
        f"{indent}#if defined(__N64__) || defined(N64) || defined(PLATFORM_N64) || defined(TARGET_N64)\n"
        f"{indent}   /* {MARK}\n"
        f"{indent}    * Start is emitted as Escape by the N64 SDL/menu shim.\n"
        f"{indent}    * During gameplay, bypass CP_CheckQuick()/ControlPanel()/save-load preview code\n"
        f"{indent}    * and jump straight back to the title/main-menu state.\n"
        f"{indent}    */\n"
        f"{indent}   if ( LastScan == sc_Escape )\n"
        f"{indent}      {{\n"
        f"{indent}      Keyboard[ sc_Escape ] = 0;\n"
        f"{indent}      LastScan = 0;\n"
        f"{indent}      playstate = ex_titles;\n"
        f"{indent}      return;\n"
        f"{indent}      }}\n"
        f"{indent}#endif\n"
    )
    main = main[:line_start] + block + main[line_start:]
    write(rt_main, main)
    log("PASS: inserted r53 Start/Escape direct main-menu intercept before CP_CheckQuick")

main2 = read(rt_main)
mark_pos = main2.find(MARK)
if mark_pos < 0:
    fail("r53 marker missing after rt_main patch")
cp_m = re.search(r"\bCP_CheckQuick\s*\(\s*LastScan\s*\)", main2[mark_pos:])
cp_pos = mark_pos + cp_m.start() if cp_m else -1
if cp_pos < 0:
    fail("CP_CheckQuick(LastScan) missing after r53 marker")
if not (mark_pos < cp_pos):
    fail("r53 intercept is not before CP_CheckQuick")
win = main2[max(0, mark_pos - 500):cp_pos]
checks = {
    "LastScan == sc_Escape": r"LastScan\s*==\s*sc_Escape",
    "Keyboard[ sc_Escape ] = 0": r"Keyboard\s*\[\s*sc_Escape\s*\]\s*=\s*0",
    "playstate = ex_titles": r"playstate\s*=\s*ex_titles",
    "return;": r"\breturn\s*;",
}
for label, pat in checks.items():
    if not re.search(pat, win):
        fail("r53 intercept missing token before CP_CheckQuick: " + label)
if main2.count(MARK) != 1:
    fail(f"expected one {MARK}, found {main2.count(MARK)}")
log("PASS: r53 direct main-menu intercept validated before CP_CheckQuick")

REPORT.write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
log(f"PASS: wrote {REPORT}")
