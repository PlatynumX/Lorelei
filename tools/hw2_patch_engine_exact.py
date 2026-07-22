#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_WALLS = 640
MARK = "ROTT64_HW2B_EXACT_SPANS_ENGINE"


def fail(msg: str) -> None:
    raise SystemExit("hw2_patch_engine_exact.py: " + msg)


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
        fail("usage: hw2_patch_engine_exact.py <generated-rott-root>")

    root = Path(sys.argv[1]).resolve()
    files = [p for p in root.rglob("rt_draw.c") if p.is_file()]
    if len(files) != 1:
        fail(f"expected one rt_draw.c, found {len(files)}")

    path = files[0]
    text = path.read_text(encoding="utf-8", errors="strict")

    if MARK in text:
        fail("rt_draw.c already has R48 exact-span instrumentation")
    if "ROTT64_HW2_LIVE_WALLS_ENGINE_EXPORT_BEGIN" in text:
        fail("old R47 generated block already exists before R48 patch")

    wp_start, wp_open, wp_close = function_span(text, "DrawWallPost")
    wallpost = text[wp_open:wp_close + 1]

    draw_pat = re.compile(
        r"\bR_DrawWallColumn[ \t]*\([ \t]*buf[ \t]*\)[ \t]*;"
    )
    draw_count = len(draw_pat.findall(wallpost))
    if draw_count < 1 or draw_count > 2:
        fail(
            f"expected one or two R_DrawWallColumn(buf) calls, found {draw_count}"
        )

    helper = f"""
/* {MARK}_GLOBALS_BEGIN */
#define ROTT64_HW2_MAX_WALLS {MAX_WALLS}

volatile unsigned int rott64_hw2_wall_seq = 0;
volatile int rott64_hw2_wall_count = 0;
volatile int rott64_hw2_viewwidth = 0;
volatile int rott64_hw2_viewheight = 0;
volatile int rott64_hw2_screenheight = 200;

volatile unsigned char rott64_hw2_wall_segments[ROTT64_HW2_MAX_WALLS];
volatile short rott64_hw2_wall_top[ROTT64_HW2_MAX_WALLS];
volatile short rott64_hw2_wall_bottom[ROTT64_HW2_MAX_WALLS];
volatile short rott64_hw2_wall_top2[ROTT64_HW2_MAX_WALLS];
volatile short rott64_hw2_wall_bottom2[ROTT64_HW2_MAX_WALLS];
volatile unsigned char rott64_hw2_wall_color[ROTT64_HW2_MAX_WALLS];

static void rott64_hw2_capture_wall_span(
    wallcast_t *post,
    int top,
    int bottom
)
{{
    int index;
    int segments;

    index = (int)(post - posts);
    if (index < 0 || index >= ROTT64_HW2_MAX_WALLS)
        return;

    if (top < 0)
        top = 0;
    if (bottom > viewheight)
        bottom = viewheight;
    if (bottom <= top)
        return;

    segments = (int)rott64_hw2_wall_segments[index];

    if (segments >= 1 &&
        rott64_hw2_wall_top[index] == top &&
        rott64_hw2_wall_bottom[index] == bottom)
        return;

    if (segments >= 2 &&
        rott64_hw2_wall_top2[index] == top &&
        rott64_hw2_wall_bottom2[index] == bottom)
        return;

    if (segments == 0)
    {{
        rott64_hw2_wall_top[index] = (short)top;
        rott64_hw2_wall_bottom[index] = (short)bottom;
        rott64_hw2_wall_segments[index] = 1;
    }}
    else if (segments == 1)
    {{
        rott64_hw2_wall_top2[index] = (short)top;
        rott64_hw2_wall_bottom2[index] = (short)bottom;
        rott64_hw2_wall_segments[index] = 2;
    }}
}}
/* {MARK}_GLOBALS_END */

"""

    text = text[:wp_start] + helper + text[wp_start:]

    _, wp_open, wp_close = function_span(text, "DrawWallPost")
    wallpost = text[wp_open:wp_close + 1]

    call_pat = re.compile(
        r"(?P<i>^[ \t]*)(?P<c>R_DrawWallColumn[ \t]*"
        r"\([ \t]*buf[ \t]*\)[ \t]*;)",
        re.MULTILINE,
    )

    def instrument(m: re.Match[str]) -> str:
        indent = m.group("i")
        return (
            f"{indent}rott64_hw2_capture_wall_span(post, dc_yl, dc_yh);\n"
            f"{indent}{m.group('c')}"
        )

    new_wallpost, replaced = call_pat.subn(instrument, wallpost)
    if replaced != draw_count:
        fail(f"instrumented {replaced} wall draws, expected {draw_count}")

    text = text[:wp_open] + new_wallpost + text[wp_close + 1:]

    _, dw_open, dw_close = function_span(text, "DrawWalls")

    init = """
   /* ROTT64_HW2B_EXACT_SPANS_FRAME_BEGIN */
   {
      int i;
      int count;

      count = viewwidth;
      if (count < 0) count = 0;
      if (count > ROTT64_HW2_MAX_WALLS)
         count = ROTT64_HW2_MAX_WALLS;

      for (i = 0; i < count; ++i)
         {
         rott64_hw2_wall_segments[i] = 0;
         rott64_hw2_wall_top[i] = 0;
         rott64_hw2_wall_bottom[i] = 0;
         rott64_hw2_wall_top2[i] = 0;
         rott64_hw2_wall_bottom2[i] = 0;
         }
   }
   /* ROTT64_HW2B_EXACT_SPANS_FRAME_END */
"""
    text = text[:dw_open + 1] + init + text[dw_open + 1:]

    _, _, dw_close = function_span(text, "DrawWalls")

    publish = """
   /* ROTT64_HW2B_EXACT_SPANS_PUBLISH_BEGIN */
   {
      int i;
      int count;

      count = viewwidth;
      if (count < 0) count = 0;
      if (count > ROTT64_HW2_MAX_WALLS)
         count = ROTT64_HW2_MAX_WALLS;

      if (doublestep > 1)
         {
         for (i = 1; i < count; i += 2)
            {
            rott64_hw2_wall_segments[i] =
               rott64_hw2_wall_segments[i - 1];
            rott64_hw2_wall_top[i] =
               rott64_hw2_wall_top[i - 1];
            rott64_hw2_wall_bottom[i] =
               rott64_hw2_wall_bottom[i - 1];
            rott64_hw2_wall_top2[i] =
               rott64_hw2_wall_top2[i - 1];
            rott64_hw2_wall_bottom2[i] =
               rott64_hw2_wall_bottom2[i - 1];
            }
         }

      for (i = 0; i < count; ++i)
         {
         rott64_hw2_wall_color[i] =
            (unsigned char)((posts[i].posttype + (i >> 4)) & 7);
         }

      rott64_hw2_wall_count = count;
      rott64_hw2_viewwidth = viewwidth;
      rott64_hw2_viewheight = viewheight;
      rott64_hw2_screenheight = iGLOBAL_SCREENHEIGHT;
      rott64_hw2_wall_seq++;
   }
   /* ROTT64_HW2B_EXACT_SPANS_PUBLISH_END */
"""

    text = text[:dw_close] + publish + text[dw_close:]

    for token in (
        "ROTT64_HW2B_EXACT_SPANS_FRAME_BEGIN",
        "ROTT64_HW2B_EXACT_SPANS_PUBLISH_BEGIN",
        "rott64_hw2_wall_segments",
        "rott64_hw2_wall_top2",
        "rott64_hw2_wall_bottom2",
        "rott64_hw2_capture_wall_span(post, dc_yl, dc_yh);",
    ):
        if token not in text:
            fail("final source missing: " + token)

    _, wp_open2, wp_close2 = function_span(text, "DrawWallPost")
    final_wp = text[wp_open2:wp_close2 + 1]

    if final_wp.count(
        "rott64_hw2_capture_wall_span(post, dc_yl, dc_yh);"
    ) != draw_count:
        fail("not every real wall draw is instrumented exactly once")

    if not draw_pat.search(final_wp):
        fail("software R_DrawWallColumn fallback disappeared")

    path.write_text(text, encoding="utf-8", newline="\n")
    print("R48 exact-span exporter installed:", path)


if __name__ == "__main__":
    main()
