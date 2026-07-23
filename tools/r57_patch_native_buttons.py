#!/usr/bin/env python3
from __future__ import annotations
import re
import sys
from pathlib import Path

MARK = "ROTT64_NATIVE_BUTTONPOLL_DIRECT_R57"


def fail(msg: str) -> None:
    raise SystemExit("r57_patch_native_buttons.py: " + msg)


def span_function(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(rf"(?m)^[ \t]*(?:static[ \t]+)?[^;\n]*\b{re.escape(name)}[ \t]*\([^;]*?\)[ \t\r\n]*\{{")
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected one {name} definition, found {len(hits)}")
    m = hits[0]
    open_i = text.find("{", m.start(), m.end())
    depth = 0
    state = "code"
    quote = ""
    i = open_i
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if c == "/" and n == "*":
                state = "block"; i += 2; continue
            if c == "/" and n == "/":
                state = "line"; i += 2; continue
            if c in "'\"":
                state = "str"; quote = c; i += 1; continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return m.start(), open_i, i
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
    fail(f"unterminated function {name}")


def add_n64_include(text: str) -> str:
    if "#include <libdragon.h>" in text:
        return text
    lines = text.splitlines(True)
    last_include = None
    for i, line in enumerate(lines[:250]):
        if re.match(r"^[ \t]*#include\b", line):
            last_include = i
    if last_include is None:
        fail("could not find include block in rt_playr.c")
    lines.insert(last_include + 1, "#if defined(__N64__)\n#include <libdragon.h>\n#endif\n")
    return "".join(lines)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: r57_patch_native_buttons.py <generated-rott-root>")
    root = Path(sys.argv[1]).resolve()
    files = [p for p in root.rglob("rt_playr.c") if p.is_file()]
    if len(files) != 1:
        fail(f"expected one rt_playr.c below {root}, found {len(files)}")
    path = files[0]
    text = path.read_text(encoding="utf-8")

    if MARK in text:
        print("PASS: r57 native buttonpoll patch already present")
        return

    generated_text = text
    for gp in list(root.rglob("*.h")) + [p for p in root.rglob("*.c") if p != path]:
        try:
            generated_text += "\n" + gp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    required = [
        "buttonpoll", "PollControls", "PollKeyboardButtons",
        "bt_attack", "bt_use", "bt_run", "bt_strafeleft", "bt_straferight",
        "bt_swapweapon", "bt_dropweapon", "bt_lookup", "bt_lookdown",
        "bt_map", "bt_turnaround", "gamestate.autorun",
    ]
    missing = [x for x in required if x not in generated_text]
    if missing:
        fail("generated engine missing expected control tokens: " + ", ".join(missing))

    text = add_n64_include(text)

    start, _open_i, end = span_function(text, "PollControls")
    ctl = text[start:end + 1]
    if "ROTT64_START_DIRECT_EX_TITLES" in ctl:
        fail("old direct Start-to-title marker still exists; Start must remain platform Escape")

    kb = re.search(r"(?m)^(?P<i>[ \t]*)PollKeyboardButtons[ \t]*\([ \t]*\)[ \t]*;", ctl)
    if not kb:
        fail("could not find PollKeyboardButtons(); in PollControls")
    ind = kb.group("i")

    block = f'''
{ind}/* {MARK}: feed N64 gameplay buttons directly into ROTT actions.
{ind} * This bypasses broken PC keybinding/gamepad assignment for gameplay.
{ind} * Start is intentionally NOT mapped here; platform/n64/sdl_n64.c keeps Start as Escape.
{ind} */
{ind}#if defined(__N64__)
{ind}{{
{ind}   joypad_buttons_t rott64_n64_buttons;
{ind}   static int rott64_n64_autorun_latched = 0;
{ind}
{ind}   rott64_n64_buttons = joypad_get_buttons_held(JOYPAD_PORT_1);
{ind}
{ind}   buttonpoll[bt_attack]      |= rott64_n64_buttons.z       ? 1 : 0;
{ind}   buttonpoll[bt_use]         |= rott64_n64_buttons.a       ? 1 : 0;
{ind}   buttonpoll[bt_swapweapon]  |= rott64_n64_buttons.b       ? 1 : 0;
{ind}   buttonpoll[bt_strafeleft]  |= rott64_n64_buttons.c_left  ? 1 : 0;
{ind}   buttonpoll[bt_straferight] |= rott64_n64_buttons.c_right ? 1 : 0;
{ind}   buttonpoll[bt_swapweapon]  |= rott64_n64_buttons.c_up    ? 1 : 0;
{ind}   buttonpoll[bt_dropweapon]  |= rott64_n64_buttons.c_down  ? 1 : 0;
{ind}   buttonpoll[bt_lookup]      |= rott64_n64_buttons.d_up    ? 1 : 0;
{ind}   buttonpoll[bt_lookdown]    |= rott64_n64_buttons.d_down  ? 1 : 0;
{ind}   buttonpoll[bt_map]         |= rott64_n64_buttons.l       ? 1 : 0;
{ind}   buttonpoll[bt_turnaround]  |= rott64_n64_buttons.r       ? 1 : 0;
{ind}
{ind}   if (rott64_n64_buttons.d_right)
{ind}      {{
{ind}      if (!rott64_n64_autorun_latched)
{ind}         {{
{ind}         gamestate.autorun = gamestate.autorun ? 0 : 1;
{ind}         rott64_n64_autorun_latched = 1;
{ind}         }}
{ind}      }}
{ind}   else
{ind}      rott64_n64_autorun_latched = 0;
{ind}}}
{ind}#endif
'''

    ctl2 = ctl[:kb.end()] + block + ctl[kb.end():]
    text = text[:start] + ctl2 + text[end + 1:]
    path.write_text(text, encoding="utf-8", newline="\n")

    report_dir = root.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "r57-native-buttons-report.md").write_text(
        "# r57 native gameplay buttons\n\n"
        "- Direct buttonpoll mappings installed in PollControls after PollKeyboardButtons().\n"
        "- Z=fire, A=use, B=swap weapon, C-left/right=strafe, C-up=swap, C-down=drop.\n"
        "- D-up/down=look, D-right=autorun toggle, L=map, R=180 turn.\n"
        "- Start is not handled here; it remains platform SDL Escape.\n",
        encoding="utf-8",
    )
    print("PASS: installed r57 native gameplay buttonpoll mappings")
    print("PASS: Start was left as platform Escape, no direct restart/title path inserted")


if __name__ == "__main__":
    main()
