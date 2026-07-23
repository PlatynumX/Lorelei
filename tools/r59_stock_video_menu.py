#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import sys

MARK = "ROTT64_STOCK_VIDEO_OPTIONS_MENU_R59"


def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)


def add_include(text: str, include_line: str) -> str:
    if include_line.strip() in text:
        return text
    includes = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if includes:
        return text[:includes[-1].end()] + include_line + text[includes[-1].end():]
    return include_line + text


def find_array(text: str, typename: str, name: str):
    pat = re.compile(
        rf"({re.escape(typename)}\s+{re.escape(name)}\s*\[\]\s*=\s*\{{\s*\n)(.*?)(\n\s*\}}\s*;)",
        re.S,
    )
    return pat.search(text)


def append_menu_name(text: str) -> str:
    m = find_array(text, "CP_MenuNames", "OptionsNames")
    if not m:
        fail("could not parse OptionsNames[]")
    body = m.group(2)
    if "VIDEO OPTIONS" in body:
        return text
    trimmed = body.rstrip()
    body2 = trimmed + ',\n       "VIDEO OPTIONS"'
    return text[:m.start(2)] + body2 + text[m.end(2):]


def bump_options_count(text: str) -> str:
    pat = re.compile(
        r"(CP_iteminfo\s+OptionsItems\s*=\s*\{\s*([^,]+),\s*([^,]+),\s*)(\d+)(\s*,\s*([^,]+),\s*([^,]+),\s*OptionsNames\s*,\s*mn_largefont\s*\}\s*;)"
    )
    m = pat.search(text)
    if not m:
        fail("could not parse OptionsItems count")
    old_count = int(m.group(4))
    opt_block = find_array(text, "CP_itemtype", "OptionsMenu")
    already_entry = bool(opt_block and "CP_Rott64VideoOptions" in opt_block.group(2))
    new_count = old_count if already_entry else old_count + 1
    return text[:m.start(4)] + str(new_count) + text[m.end(4):]


def append_options_menu_entry(text: str) -> str:
    m = find_array(text, "CP_itemtype", "OptionsMenu")
    if not m:
        fail("could not locate full OptionsMenu[] block")
    body = m.group(2)
    if "CP_Rott64VideoOptions" in body:
        return text
    # Do not require CP_ScreenSize here. Some generated ports keep SCREEN SIZE
    # in OptionsNames[] but route the item through a different function name.
    stripped = body.rstrip()
    if not stripped:
        fail("OptionsMenu[] block is empty")
    if not stripped.endswith(','):
        stripped += ','
    body2 = stripped + '\n       {1, "\\0",        \'V\', (menuptr)CP_Rott64VideoOptions}'
    return text[:m.start(2)] + body2 + text[m.end(2):]


def patch_options_toggle_loop(text: str) -> str:
    patterns = [
        (r"for\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*OptionsItems\.amount\s*-\s*5\s*;\s*i\+\+\s*\)", "for (i = 0; i < 4; i++)"),
        (r"for\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*\(\s*OptionsItems\.amount\s*-\s*5\s*\)\s*;\s*i\+\+\s*\)", "for (i = 0; i < 4; i++)"),
    ]
    total = 0
    for pat, repl in patterns:
        text, n = re.subn(pat, repl, text, count=1)
        total += n
    if total == 0:
        print("WARN: did not find stock DrawOptionsButtons amount-minus-5 loop; leaving draw loop unchanged")
    return text


def patch_rt_menu(path: Path) -> None:
    if not path.is_file():
        fail(f"missing {path}")
    text = path.read_text(encoding="utf-8", errors="strict")
    if MARK in text:
        print(f"PASS: {path} already has {MARK}")
        return

    text = add_include(text, "#include <stdio.h>\n")

    for required in ("CP_MenuNames OptionsNames[]", "CP_iteminfo OptionsItems", "CP_itemtype OptionsMenu[]"):
        if required not in text:
            fail("rt_menu.c does not contain stock User Options menu structure: " + required)

    decl_block = f"""
/* {MARK}_DECLS_BEGIN */
#if defined(__N64__)
extern const char *rott64_video_r59_resolution_label(void);
extern const char *rott64_video_r59_aspect_label(void);
extern const char *rott64_video_r59_filter_label(void);
extern int rott64_video_r59_screen_percent(void);
extern void rott64_video_r59_cycle_resolution(void);
extern void rott64_video_r59_cycle_aspect(void);
extern void rott64_video_r59_cycle_filter(void);
extern void rott64_video_r59_adjust_screen(int delta);
#else
static const char *rott64_video_r59_resolution_label(void) {{ return "320"; }}
static const char *rott64_video_r59_aspect_label(void) {{ return "4:3"; }}
static const char *rott64_video_r59_filter_label(void) {{ return "SHARP"; }}
static int rott64_video_r59_screen_percent(void) {{ return 95; }}
static void rott64_video_r59_cycle_resolution(void) {{ }}
static void rott64_video_r59_cycle_aspect(void) {{ }}
static void rott64_video_r59_cycle_filter(void) {{ }}
static void rott64_video_r59_adjust_screen(int delta) {{ (void)delta; }}
#endif
void CP_Rott64VideoOptions(void);
/* {MARK}_DECLS_END */
"""
    pos = text.find("CP_iteminfo OptionsItems")
    if pos < 0:
        fail("could not find OptionsItems declaration anchor")
    text = text[:pos] + decl_block + text[pos:]

    text = append_menu_name(text)
    text = bump_options_count(text)
    text = append_options_menu_entry(text)
    text = patch_options_toggle_loop(text)

    tables = f'''
/* {MARK}_TABLES_BEGIN */
CP_MenuNames Rott64VideoNames[] =
   {{
   "RESOLUTION",
   "ASPECT RATIO",
   "FILTERING",
   "SCREEN SIZE"
   }};
CP_iteminfo Rott64VideoItems = {{ 20, MENU_Y, 4, 0, 43, Rott64VideoNames, mn_largefont }};
CP_itemtype Rott64VideoMenu[] =
   {{
   {{2, "\\0", 'R', {{ NULL }}}},
   {{1, "\\0", 'A', {{ NULL }}}},
   {{1, "\\0", 'F', {{ NULL }}}},
   {{1, "\\0", 'S', {{ NULL }}}}
   }};
/* {MARK}_TABLES_END */
'''
    m = find_array(text, "CP_itemtype", "OptionsMenu")
    if not m:
        fail("could not locate OptionsMenu[] after insertion")
    text = text[:m.end()] + tables + text[m.end():]

    funcs = f'''
//****************************************************************************
//
// CP_Rott64VideoOptions () -- {MARK}
//
// Software-renderer video options live under stock User Options.
//
//****************************************************************************
static void Rott64VideoUpdateNames(void)
{{
   snprintf(Rott64VideoNames[0], sizeof(Rott64VideoNames[0]),
      "RESOLUTION: %s", rott64_video_r59_resolution_label());
   snprintf(Rott64VideoNames[1], sizeof(Rott64VideoNames[1]),
      "ASPECT: %s", rott64_video_r59_aspect_label());
   snprintf(Rott64VideoNames[2], sizeof(Rott64VideoNames[2]),
      "FILTER: %s", rott64_video_r59_filter_label());
   snprintf(Rott64VideoNames[3], sizeof(Rott64VideoNames[3]),
      "SCREEN SIZE: %d%%", rott64_video_r59_screen_percent());
}}

void DrawRott64VideoOptionsMenu (void)
{{
   MenuNum = 1;
   SetAlternateMenuBuf();
   ClearMenuBuf();
   SetMenuTitle ("Video Options");
   Rott64VideoUpdateNames();
   MN_GetCursorLocation( &Rott64VideoItems, &Rott64VideoMenu[ 0 ] );
   DrawMenu (&Rott64VideoItems, &Rott64VideoMenu[0]);
   DisplayInfo (0);
   FlipMenuBuf();
}}

void CP_Rott64VideoOptions (void)
{{
   int which;

   DrawRott64VideoOptionsMenu();
   do
   {{
      which = HandleMenu (&Rott64VideoItems, &Rott64VideoMenu[0], NULL);
      switch (which)
      {{
         case 0:
            rott64_video_r59_cycle_resolution();
            DrawRott64VideoOptionsMenu();
            break;
         case 1:
            rott64_video_r59_cycle_aspect();
            DrawRott64VideoOptionsMenu();
            break;
         case 2:
            rott64_video_r59_cycle_filter();
            DrawRott64VideoOptionsMenu();
            break;
         case 3:
            rott64_video_r59_adjust_screen(5);
            DrawRott64VideoOptionsMenu();
            break;
      }}
   }} while (which >= 0);

   handlewhich = OptionsItems.amount - 1;
   DrawOptionsMenu();
}}

/* {MARK}_FUNCS_END */
'''
    pos = text.find("//  DrawOptionsMenu")
    if pos < 0:
        pos = text.find("void DrawOptionsMenu")
    if pos < 0:
        fail("could not find DrawOptionsMenu anchor")
    text = text[:pos] + funcs + text[pos:]

    for token in (MARK, "VIDEO OPTIONS", "CP_Rott64VideoOptions", "Rott64VideoUpdateNames", "CP_iteminfo OptionsItems"):
        if token not in text:
            fail("post-patch missing token: " + token)
    opt = find_array(text, "CP_itemtype", "OptionsMenu")
    if not opt or "CP_Rott64VideoOptions" not in opt.group(2):
        fail("OptionsMenu[] still missing CP_Rott64VideoOptions entry")
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"PASS: patched stock User Options menu in {path}")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: r59_stock_video_menu.py <generated/rott dir>")
    patch_rt_menu(Path(sys.argv[1]) / "rt_menu.c")


if __name__ == "__main__":
    main()
