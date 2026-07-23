#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R85_DETAIL_FILTER_MENU"
COMPAT_MARK = "ROTT64_STOCK_VIDEO_OPTIONS_MENU_R59"


def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)


def scan_braces(text: str, open_i: int) -> int:
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
            if c in ("'", '"'):
                state = "string"; quote = c; i += 1; continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
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
    fail("unterminated brace block")


def array_span(text: str, typename: str, name: str) -> tuple[int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*{re.escape(typename)}[ \t]+{re.escape(name)}"
        rf"[ \t]*\[\][ \t]*=[ \t]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected one {typename} {name}[] definition, found {len(hits)}")
    m = hits[0]
    open_i = text.find("{", m.start(), m.end())
    close_i = scan_braces(text, open_i)
    semi = text.find(";", close_i)
    if semi < 0 or semi - close_i > 8:
        fail(f"could not find semicolon after {name}[]")
    return m.start(), semi + 1


def function_span(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?"
        rf"[^;\n]*\b{re.escape(name)}[ \t]*\([^;]*?\)"
        rf"[ \t\r\n]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected one {name} definition, found {len(hits)}")
    m = hits[0]
    open_i = text.find("{", m.start(), m.end())
    close_i = scan_braces(text, open_i)
    return m.start(), open_i, close_i + 1


def replace_array(text: str, typename: str, name: str, replacement: str) -> str:
    a, b = array_span(text, typename, name)
    return text[:a] + replacement.rstrip() + text[b:]


def replace_statement(text: str, name: str, replacement: str) -> str:
    pat = re.compile(
        rf"(?m)^[ \t]*CP_iteminfo[ \t]+{re.escape(name)}[ \t]*="
        rf"[ \t]*\{{.*?\}}[ \t]*;"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        fail(f"expected one CP_iteminfo {name} statement, found {len(hits)}")
    m = hits[0]
    return text[:m.start()] + replacement.rstrip() + text[m.end():]


def replace_function(text: str, name: str, replacement: str) -> str:
    a, _o, b = function_span(text, name)
    return text[:a] + replacement.rstrip() + "\n" + text[b:]


def replace_switch_in_function(text: str, func_name: str, replacement: str) -> str:
    a, _o, b = function_span(text, func_name)
    func = text[a:b]
    m = re.search(r"\bswitch[ \t]*\([ \t]*which[ \t]*\)[ \t\r\n]*\{", func)
    if not m:
        fail(f"{func_name} missing switch(which)")
    open_i = func.find("{", m.start(), m.end())
    close_i = scan_braces(func, open_i)
    func2 = func[:m.start()] + replacement.rstrip() + func[close_i + 1:]
    return text[:a] + func2 + text[b:]


def add_include(text: str, include_line: str) -> str:
    if include_line.strip() in text:
        return text
    incs = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if not incs:
        fail("could not locate include block")
    return text[:incs[-1].end()] + include_line + text[incs[-1].end():]


def patch(path: Path) -> None:
    if not path.is_file():
        fail("missing generated rt_menu.c: " + str(path))

    text = path.read_text(encoding="utf-8", errors="strict")

    if MARK in text:
        print("PASS: r85 menu patch already present")
        return

    # This tool must operate on the freshly prepared Taradino menu, not on an
    # already-customized Video Options tree.
    for required in (
        "CP_MenuNames OptionsNames[]",
        "CP_iteminfo OptionsItems",
        "CP_itemtype OptionsMenu[]",
        "CP_MenuNames DetailMenuNames[]",
        "CP_iteminfo DetailItems",
        "CP_itemtype DetailMenu[]",
        "void CP_OptionsMenu",
        "void CP_DetailMenu",
        "void DrawDetailMenu",
        "void DrawOptionsButtons",
    ):
        if required not in text:
            fail("fresh generated rt_menu.c missing " + required)

    if "CP_Rott64VideoOptions" in text or "Rott64VideoItems" in text:
        fail("r85 received an already-customized Video Options tree; patch order is wrong")

    text = add_include(text, "#include <stdio.h>\n")

    # Expose only the remaining N64 video setting: VI filtering.
    decl = r'''
/* ROTT64_R85_DETAIL_FILTER_MENU
 * ROTT64_STOCK_VIDEO_OPTIONS_MENU_R59 compatibility marker
 * Fixed 320x240 output: Filtering now lives in Detail Levels.
 */
#if defined(__N64__)
extern const char *rott64_video_r59_filter_label(void);
extern void rott64_video_r59_cycle_filter(void);
#else
static const char *rott64_video_r59_filter_label(void) { return "SHARP"; }
static void rott64_video_r59_cycle_filter(void) { }
#endif

'''
    anchor = text.find("CP_MenuNames OptionsNames[]")
    if anchor < 0:
        fail("OptionsNames anchor disappeared")
    text = text[:anchor] + decl + text[anchor:]

    options_names = r'''CP_MenuNames OptionsNames[] = {
   "DOUBLE-CLICK SPEED",
   "MENU FLIP SPEED",
   "DETAIL LEVELS",
   "VIOLENCE LEVEL"
};'''
    text = replace_array(text, "CP_MenuNames", "OptionsNames", options_names)

    text = replace_statement(
        text,
        "OptionsItems",
        "CP_iteminfo OptionsItems = { 20, MENU_Y, 4, 0, 43, OptionsNames, mn_largefont };",
    )

    options_menu = r'''CP_itemtype OptionsMenu[] = {
   { 2, "double\0", 'D', { .vv = CP_DoubleClickSpeed } },
   { 1, "menuspd\0", 'M', { .vv = MenuFlipSpeed } },
   { 1, "detail\0", 'D', { .vv = CP_DetailMenu } },
   { 1, "vlevel\0", 'V', { .vv = CP_ViolenceMenu } }
};'''
    text = replace_array(text, "CP_itemtype", "OptionsMenu", options_menu)

    # No remaining User Options row is an ON/OFF toggle.
    draw_options_buttons = r'''void DrawOptionsButtons (void)
{
   /* R85: all four surviving User Options rows dispatch to submenus/sliders. */
}'''
    text = replace_function(text, "DrawOptionsButtons", draw_options_buttons)

    # Preserve stock CP_OptionsMenu setup/exit code but remove the old cases 0-3
    # that toggled AutoDetailOn, fulllight, BobbinOn and fandc.
    text = replace_switch_in_function(
        text,
        "CP_OptionsMenu",
        r'''/* R85: HandleMenu dispatches all four surviving rows through
            their CP_itemtype routines. There are no direct toggle rows here. */
      (void)which;''',
    )

    detail_names = r'''CP_MenuNames DetailMenuNames[] = {
   "LOW DETAIL",
   "MEDIUM DETAIL",
   "HIGH DETAIL",
   "FILTER: SHARP"
};'''
    text = replace_array(text, "CP_MenuNames", "DetailMenuNames", detail_names)

    # DetailItems has four selectable rows. Rott64DetailButtonItems stays at 3
    # because Taradino MN_DrawButtons indexes OptionNums[i], which only has the
    # original three detail entries.
    detail_info = r'''CP_iteminfo DetailItems = { 32, 64, 4, 0, 43, DetailMenuNames, mn_largefont };
static CP_iteminfo Rott64DetailButtonItems = { 32, 64, 3, 0, 43, DetailMenuNames, mn_largefont };'''
    text = replace_statement(text, "DetailItems", detail_info)

    detail_menu = r'''CP_itemtype DetailMenu[] = {
   { 2, "lowdtl\0", 'L', { NULL } },
   { 1, "meddtl\0", 'M', { NULL } },
   { 1, "hidtl\0", 'H', { NULL } },
   { 1, "\0", 'F', { NULL } }
};'''
    text = replace_array(text, "CP_itemtype", "DetailMenu", detail_menu)

    # Change every Detail-level button draw in the two relevant functions to
    # the safe 3-row descriptor, then add a dynamic filter label.
    detail_draw_re = re.compile(
        r"MN_DrawButtons\s*\(\s*&DetailItems\s*,\s*&DetailMenu\s*"
        r"\[\s*0\s*\]\s*,\s*DetailLevel\s*,\s*OptionNums\s*\)\s*;"
    )

    da, do, db = function_span(text, "DrawDetailMenu")
    draw = text[da:db]
    draw, n = detail_draw_re.subn(
        "MN_DrawButtons(&Rott64DetailButtonItems, &DetailMenu[0], DetailLevel, OptionNums);",
        draw,
    )
    if n < 1:
        fail("could not redirect DrawDetailMenu MN_DrawButtons to safe 3-row descriptor")
    brace = draw.find("{")
    dynamic = r'''
   snprintf(DetailMenuNames[3], sizeof(DetailMenuNames[3]),
      "FILTER: %s", rott64_video_r59_filter_label());
'''
    draw = draw[:brace + 1] + dynamic + draw[brace + 1:]
    text = text[:da] + draw + text[db:]

    ca, co, cb = function_span(text, "CP_DetailMenu")
    cp = text[ca:cb]
    cp, n = detail_draw_re.subn(
        "MN_DrawButtons(&Rott64DetailButtonItems, &DetailMenu[0], DetailLevel, OptionNums);",
        cp,
    )
    if n < 1:
        fail("could not redirect CP_DetailMenu MN_DrawButtons to safe 3-row descriptor")

    sw = re.search(r"\bswitch[ \t]*\([ \t]*which[ \t]*\)[ \t\r\n]*\{", cp)
    if not sw:
        fail("CP_DetailMenu missing switch(which)")
    sw_open = cp.find("{", sw.start(), sw.end())
    sw_close = scan_braces(cp, sw_open)
    if re.search(r"\bcase[ \t]+3[ \t]*:", cp[sw_open:sw_close]):
        fail("unexpected pre-existing case 3 in stock CP_DetailMenu")
    filter_case = r'''
         case 3:
            rott64_video_r59_cycle_filter();
            DrawDetailMenu();
            break;
'''
    cp = cp[:sw_close] + filter_case + cp[sw_close:]
    text = text[:ca] + cp + text[cb:]

    # Hard postconditions.
    for forbidden in (
        '"AUTO DETAIL ADJUST"',
        '"LIGHT DIMINISHING"',
        '"BOBBIN\'"',
        '"FLOOR AND CEILING"',
        '"SCREEN SIZE"',
        '"VIDEO OPTIONS"',
        "CP_Rott64VideoOptions",
        "Rott64VideoNames",
        "Rott64VideoItems",
        "Rott64VideoMenu",
    ):
        if forbidden in text:
            fail("removed User/Video option survived generated menu: " + forbidden)

    for required in (
        MARK,
        '"DOUBLE-CLICK SPEED"',
        '"MENU FLIP SPEED"',
        '"DETAIL LEVELS"',
        '"VIOLENCE LEVEL"',
        "CP_iteminfo OptionsItems = { 20, MENU_Y, 4",
        "CP_iteminfo DetailItems = { 32, 64, 4",
        "Rott64DetailButtonItems = { 32, 64, 3",
        '"FILTER: %s"',
        "rott64_video_r59_cycle_filter();",
        "case 3:",
    ):
        if required not in text:
            fail("generated r85 menu missing " + required)

    # Specifically prove the old direct-toggle globals are not touched by
    # CP_OptionsMenu anymore.
    oa, _oo, ob = function_span(text, "CP_OptionsMenu")
    opt_func = text[oa:ob]
    for bad in ("AutoDetailOn", "fulllight", "BobbinOn", "fandc"):
        if bad in opt_func:
            fail("CP_OptionsMenu still toggles removed setting: " + bad)

    # Prove every Detail MN_DrawButtons call in our modified functions uses the
    # three-entry descriptor, never DetailItems.amount==4 with OptionNums.
    for fn in ("DrawDetailMenu", "CP_DetailMenu"):
        fa, _fo, fb = function_span(text, fn)
        body = text[fa:fb]
        if re.search(
            r"MN_DrawButtons\s*\(\s*&DetailItems\s*,\s*&DetailMenu",
            body,
        ):
            fail(fn + " still uses four-row DetailItems with three-entry OptionNums")
        if "MN_DrawButtons" in body and "Rott64DetailButtonItems" not in body:
            fail(fn + " button draw does not use safe three-row descriptor")

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    print("PASS: User Options reduced to Double-click / Menu speed / Detail / Violence")
    print("PASS: Video Options submenu removed")
    print("PASS: Filtering moved to Detail Levels as row 4")
    print("PASS: Detail button drawing remains limited to original three OptionNums entries")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: r59_stock_video_menu.py <generated-rott-root>")
    root = Path(sys.argv[1]).resolve()
    patch(root / "rt_menu.c")


if __name__ == "__main__":
    main()
