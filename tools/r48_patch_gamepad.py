#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

MARK = "ROTT64_NATIVE_GAMEPAD_XY_ENGINE_V2"


def fail(msg: str) -> None:
    raise SystemExit("r48_patch_gamepad.py: " + msg)


def function_span(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?[^;\n]*\b{re.escape(name)}"
        rf"[ \t]*\([^;]*?\)[ \t\r\n]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected one {name}() definition, found {len(hits)}")

    start = hits[0].start()
    op = text.find("{", hits[0].start(), hits[0].end())
    if op < 0:
        fail(f"opening brace not found for {name}()")

    depth = 0
    state = "code"
    quote = ""
    i = op

    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""

        if state == "code":
            if c == "/" and n == "*":
                state = "block"
                i += 2
                continue
            if c == "/" and n == "/":
                state = "line"
                i += 2
                continue
            if c in ("'", '"'):
                state = "str"
                quote = c
                i += 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return start, op, i
            i += 1
            continue

        if state == "block":
            if c == "*" and n == "/":
                state = "code"
                i += 2
            else:
                i += 1
            continue

        if state == "line":
            if c == "\n":
                state = "code"
            i += 1
            continue

        if state == "str":
            if c == "\\":
                i += 2
                continue
            if c == quote:
                state = "code"
            i += 1

    fail(f"closing brace not found for {name}()")


def only_rt_playr(root: Path) -> Path:
    files = [p for p in root.rglob("rt_playr.c") if p.is_file()]
    if len(files) != 1:
        fail(f"expected exactly one rt_playr.c, found {len(files)}")
    return files[0]


def patch(text: str) -> str:
    if MARK in text:
        fail("generated rt_playr.c is already native-XY patched")

    _, pj_open, pj_close = function_span(text, "PollJoystickMove")
    old_joy = text[pj_open:pj_close + 1]

    for token in (
        "joyx",
        "joyy",
        "JX",
        "JY",
        "INL_GetJoyDelta",
        "buttonpoll[bt_run]",
    ):
        if token not in old_joy:
            fail("PollJoystickMove() missing expected token: " + token)

    new_joy = r'''{
   int joyx;
   int joyy;

   rott64_n64_gamepad_axes(&joyx, &joyy);

   /*
    * Full X deflection is approximately normal keyboard turn speed.
    * Divide first to avoid overflow and retain linear partial-stick response.
    */
   JX = (-joyx) * (KEYBOARDNORMALTURNAMOUNT / 127);

   /*
    * Full Y deflection is normal keyboard walk speed.
    * Platform code already inverted N64 Y so negative is forward.
    */
   JY = joyy * (BASEMOVE / 127);

   if (JX != 0)
      turnheldtime += tics;
   else
      turnheldtime = 0;

   if (buttonpoll[bt_run])
      {
      JX <<= 1;
      JY <<= 1;
      }
   }'''

    text = text[:pj_open] + new_joy + text[pj_close + 1:]

    pj_start, _, _ = function_span(text, "PollJoystickMove")
    decl = (
        f"/* {MARK}_DECL */\n"
        "extern void rott64_n64_gamepad_axes(int *turn_x, int *move_y);\n\n"
    )
    text = text[:pj_start] + decl + text[pj_start:]

    _, pc_open, pc_close = function_span(text, "PollControls")
    controls = text[pc_open:pc_close + 1]

    for token in (
        "PollKeyboardButtons",
        "PollMouseButtons",
        "PollJoystickButtons",
        "PollKeyboardMove",
        "PollMouseMove",
        "PollJoystickMove",
        "PollMove",
    ):
        if token not in controls:
            fail("PollControls() missing expected token: " + token)

    joy_move = re.compile(
        r"(?P<i>^[ \t]*)if[ \t]*\([ \t]*joystickenabled[ \t]*\)"
        r"[ \t\r\n]+(?P<ci>[ \t]*)PollJoystickMove[ \t]*\(\s*\)[ \t]*;",
        re.MULTILINE,
    )
    joy_hits = list(joy_move.finditer(controls))
    if len(joy_hits) != 1:
        fail(
            "expected exactly one conditional PollJoystickMove() call; "
            f"found {len(joy_hits)}"
        )

    m = joy_hits[0]
    indent = m.group("i")
    controls = (
        controls[:m.start()]
        + f"{indent}/* {MARK}_MOVE_ALWAYS */\n"
        + f"{indent}PollJoystickMove();"
        + controls[m.end():]
    )

    # Replace only gameplay mouse MOVEMENT with a no-op while keeping the
    # surrounding if/else structure valid.
    mouse_move = re.compile(
        r"(?P<head>^[ \t]*(?:else[ \t]+)?if[ \t]*"
        r"\([^\n;{}]*mouseenabled[^\n;{}]*\)"
        r"[ \t\r\n]+(?P<ci>[ \t]*))"
        r"PollMouseMove[ \t]*\(\s*\)[ \t]*;",
        re.MULTILINE,
    )
    mouse_hits = list(mouse_move.finditer(controls))
    if len(mouse_hits) != 1:
        fail(
            "expected exactly one conditional PollMouseMove() call; "
            f"found {len(mouse_hits)}"
        )

    m = mouse_hits[0]
    controls = (
        controls[:m.start()]
        + m.group("head")
        + f"/* {MARK}_NO_MOUSE_MOVE */ (void)0;"
        + controls[m.end():]
    )

    for token in (
        "PollMouseButtons",
        "PollKeyboardButtons",
        "PollJoystickButtons",
        "PollKeyboardMove",
        "PollMove",
    ):
        if token not in controls:
            fail("controller regression: token disappeared from PollControls: " + token)

    text = text[:pc_open] + controls + text[pc_close + 1:]

    for token in (
        MARK + "_DECL",
        "extern void rott64_n64_gamepad_axes(int *turn_x, int *move_y);",
        "rott64_n64_gamepad_axes(&joyx, &joyy);",
        "KEYBOARDNORMALTURNAMOUNT / 127",
        "BASEMOVE / 127",
        MARK + "_MOVE_ALWAYS",
        MARK + "_NO_MOUSE_MOVE",
        "PollMouseButtons",
        "PollKeyboardButtons",
        "PollKeyboardMove",
    ):
        if token not in text:
            fail("final engine source missing: " + token)

    _, final_open, final_close = function_span(text, "PollJoystickMove")
    final_joy = text[final_open:final_close + 1]

    for forbidden in ("INL_GetJoyDelta", "joypadenabled", "threshold"):
        if forbidden in final_joy:
            fail("desktop joystick behavior survived in PollJoystickMove: " + forbidden)

    for forbidden in ("horizon", "yzangle", "bt_lookup", "bt_lookdown"):
        if forbidden in final_joy:
            fail("vertical-look token entered native joystick movement: " + forbidden)

    return text


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: r48_patch_gamepad.py <generated-rott-root>")

    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        fail(f"generated engine root does not exist: {root}")

    path = only_rt_playr(root)
    original = path.read_text(encoding="utf-8", errors="strict")
    patched = patch(original)
    path.write_text(patched, encoding="utf-8", newline="\n")

    print("Native N64 XY movement installed:", path)
    print("X: analog turn")
    print("Y: analog forward/back")
    print("Desktop joystick calibration: bypassed")
    print("Mouse movement: suppressed; button polling preserved")


if __name__ == "__main__":
    main()
