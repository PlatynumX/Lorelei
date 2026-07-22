#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_WALLS = 640
MARK = "ROTT64_HW2_LIVE_WALLS_ENGINE"


def fail(msg: str) -> None:
    raise SystemExit("hw2_patch_engine.py: " + msg)


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


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: hw2_patch_engine.py <generated-rott-root>")

    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        fail(f"generated engine root does not exist: {root}")

    files = [p for p in root.rglob("rt_draw.c") if p.is_file()]
    if len(files) != 1:
        fail(f"expected one rt_draw.c, found {len(files)}")

    path = files[0]
    text = path.read_text(encoding="utf-8", errors="strict")

    if MARK in text:
        fail("generated rt_draw.c is already patched")

    _, wp_open, wp_close = function_span(text, "DrawWallPost")
    wallpost = text[wp_open:wp_close + 1]

    if not re.search(
        r"\bR_DrawWallColumn[ \t]*\([ \t]*buf[ \t]*\)[ \t]*;",
        wallpost,
    ):
        fail("DrawWallPost() no longer calls R_DrawWallColumn(buf)")

    for token in ("ceilingclip", "floorclip"):
        if token not in wallpost:
            fail(f"DrawWallPost() no longer exposes {token}")

    dw_start, _, _ = function_span(text, "DrawWalls")

    globals_block = f"""
/* {MARK}_GLOBALS_BEGIN */
#define ROTT64_HW2_MAX_WALLS {MAX_WALLS}
volatile unsigned int rott64_hw2_wall_seq = 0;
volatile int rott64_hw2_wall_count = 0;
volatile int rott64_hw2_viewwidth = 0;
volatile int rott64_hw2_viewheight = 0;
volatile int rott64_hw2_screenheight = 200;
volatile short rott64_hw2_wall_top[ROTT64_HW2_MAX_WALLS];
volatile short rott64_hw2_wall_bottom[ROTT64_HW2_MAX_WALLS];
volatile unsigned char rott64_hw2_wall_color[ROTT64_HW2_MAX_WALLS];
/* {MARK}_GLOBALS_END */

"""
    text = text[:dw_start] + globals_block + text[dw_start:]

    _, _, dw_close = function_span(text, "DrawWalls")

    export_block = r"""
   /* ROTT64_HW2_LIVE_WALLS_ENGINE_EXPORT_BEGIN */
   {
      int rott64_hw2_i;
      int rott64_hw2_count;

      rott64_hw2_count = viewwidth;
      if (rott64_hw2_count < 0)
         rott64_hw2_count = 0;
      if (rott64_hw2_count > ROTT64_HW2_MAX_WALLS)
         rott64_hw2_count = ROTT64_HW2_MAX_WALLS;

      for (rott64_hw2_i = 0;
           rott64_hw2_i < rott64_hw2_count;
           ++rott64_hw2_i)
         {
         int rott64_hw2_top;
         int rott64_hw2_bottom;

         rott64_hw2_top = posts[rott64_hw2_i].ceilingclip;
         rott64_hw2_bottom = posts[rott64_hw2_i].floorclip + 1;

         if (rott64_hw2_top < 0)
            rott64_hw2_top = 0;
         if (rott64_hw2_bottom < rott64_hw2_top)
            rott64_hw2_bottom = rott64_hw2_top;

         rott64_hw2_wall_top[rott64_hw2_i] = (short)rott64_hw2_top;
         rott64_hw2_wall_bottom[rott64_hw2_i] = (short)rott64_hw2_bottom;
         rott64_hw2_wall_color[rott64_hw2_i] =
            (unsigned char)(
               (posts[rott64_hw2_i].posttype +
                (rott64_hw2_i >> 4)) & 7
            );
         }

      rott64_hw2_wall_count = rott64_hw2_count;
      rott64_hw2_viewwidth = viewwidth;
      rott64_hw2_viewheight = viewheight;
      rott64_hw2_screenheight = iGLOBAL_SCREENHEIGHT;
      rott64_hw2_wall_seq++;
   }
   /* ROTT64_HW2_LIVE_WALLS_ENGINE_EXPORT_END */
"""
    text = text[:dw_close] + export_block + text[dw_close:]

    # Final structural checks. The software wall drawer intentionally remains
    # enabled in this geometry probe.
    _, wp_open2, wp_close2 = function_span(text, "DrawWallPost")
    wallpost2 = text[wp_open2:wp_close2 + 1]

    if "ROTT64_HW2_LIVE_WALLS_ENGINE_EXPORT_BEGIN" not in text:
        fail("export block was not installed")
    if not re.search(
        r"\bR_DrawWallColumn[ \t]*\([ \t]*buf[ \t]*\)[ \t]*;",
        wallpost2,
    ):
        fail("software wall fallback was unexpectedly removed")

    path.write_text(text, encoding="utf-8", newline="\n")
    print("HW2 wall export installed:", path)


if __name__ == "__main__":
    main()
