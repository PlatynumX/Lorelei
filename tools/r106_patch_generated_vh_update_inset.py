#!/usr/bin/env python3
from pathlib import Path
import re
import sys

MARK_HELPER = "ROTT64_R106_LOGICAL_CRT_INSET_HELPER"
MARK_CALL = "ROTT64_R106_VW_UPDATE_INSET_CALL"

def die(msg):
    raise SystemExit("ERROR: " + msg)

def find_function_span(text, name):
    """Find a C function definition allowing spaces between name and '('."""
    name_re = re.compile(r"\b" + re.escape(name) + r"\s*\(")
    spans = []

    for m in name_re.finditer(text):
        idx = m.start()
        line_start = text.rfind("\n", 0, idx) + 1
        prefix = text[line_start:idx].strip()

        # Skip obvious calls and control flow.
        if not prefix:
            continue
        if prefix.endswith(("=", "+", "-", "/", "!", "&", "|", "?", ":")):
            continue
        if any(word in prefix.split() for word in ("return", "if", "while", "for", "switch")):
            continue

        close_paren = text.find(")", m.end() - 1)
        if close_paren < 0:
            continue

        semi = text.find(";", close_paren)
        open_i = text.find("{", close_paren)
        if open_i < 0:
            continue
        if semi >= 0 and semi < open_i:
            continue

        sig = text[line_start:open_i].strip()
        if not (
            sig.startswith("void ")
            or sig.startswith("static void ")
            or sig.startswith("int ")
            or sig.startswith("static int ")
            or sig.startswith("boolean ")
            or sig.startswith("static boolean ")
            or sig.startswith("byte ")
            or sig.startswith("static byte ")
        ):
            continue

        depth = 0
        state = "code"
        quote = ""
        i = open_i
        end_i = None

        while i < len(text):
            ch = text[i]
            nx = text[i + 1] if i + 1 < len(text) else ""

            if state == "code":
                if ch == "/" and nx == "*":
                    state = "block"
                    i += 2
                    continue
                if ch == "/" and nx == "/":
                    state = "line"
                    i += 2
                    continue
                if ch in ("'", '"'):
                    state = "string"
                    quote = ch
                    i += 1
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end_i = i + 1
                        break
                i += 1
                continue

            if state == "block":
                if ch == "*" and nx == "/":
                    state = "code"
                    i += 2
                else:
                    i += 1
                continue

            if state == "line":
                if ch == "\n":
                    state = "code"
                i += 1
                continue

            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                state = "code"
            i += 1

        if end_i is None:
            die("unterminated function " + name)
        spans.append((line_start, open_i, end_i))

    if len(spans) == 1:
        return spans[0]
    if len(spans) > 1:
        die("multiple definitions found for " + name)
    return None

def insert_helper_before_vw(rt_vid):
    text = rt_vid.read_text(encoding="utf-8", errors="strict")
    if MARK_HELPER in text:
        return False

    span = find_function_span(text, "VW_UpdateScreen")
    if not span:
        die("rt_vid.c does not contain a VW_UpdateScreen definition with a function body")

    helper = """
#ifdef __N64__
/* ROTT64_R106_LOGICAL_CRT_INSET_HELPER
 *
 * Apply overscan compensation to ROTT's logical 320x200 byte framebuffer
 * before VW_UpdateScreen forwards it to the active video backend.
 *
 * 320x240 target safe area: 288x216.
 * Logical 320x200 equivalent: x=16 y=10 w=288 h=180.
 */
static void rott64_r106_crt_inset_logical_frame(void)
{
    enum {
        ROTT64_R106_SRC_W = 320,
        ROTT64_R106_SRC_H = 200,
        ROTT64_R106_SAFE_X = 16,
        ROTT64_R106_SAFE_Y = 10,
        ROTT64_R106_SAFE_W = 288,
        ROTT64_R106_SAFE_H = 180
    };
    static byte snapshot[ROTT64_R106_SRC_W * ROTT64_R106_SRC_H];
    byte *dstbase;
    int x;
    int y;

    if (bufferofs == 0)
        return;

    dstbase = (byte *)bufferofs;

    for (y = 0; y < ROTT64_R106_SRC_H; ++y)
    {
        const byte *src = (const byte *)(dstbase + ylookup[y]);
        for (x = 0; x < ROTT64_R106_SRC_W; ++x)
            snapshot[(y * ROTT64_R106_SRC_W) + x] = src[x];
    }

    for (y = 0; y < ROTT64_R106_SRC_H; ++y)
    {
        byte *dst = (byte *)(dstbase + ylookup[y]);
        for (x = 0; x < ROTT64_R106_SRC_W; ++x)
            dst[x] = 0;
    }

    for (y = 0; y < ROTT64_R106_SAFE_H; ++y)
    {
        const int dst_y = ROTT64_R106_SAFE_Y + y;
        const int src_y = (y * ROTT64_R106_SRC_H) / ROTT64_R106_SAFE_H;
        const byte *src = snapshot + (src_y * ROTT64_R106_SRC_W);
        byte *dst = (byte *)(dstbase + ylookup[dst_y]) + ROTT64_R106_SAFE_X;

        for (x = 0; x < ROTT64_R106_SAFE_W; ++x)
        {
            const int src_x = (x * ROTT64_R106_SRC_W) / ROTT64_R106_SAFE_W;
            dst[x] = src[src_x];
        }
    }
}
#endif

"""
    text = text[:span[0]] + helper + text[span[0]:]
    rt_vid.write_text(text, encoding="utf-8", newline="\n")
    return True

def patch_vw_update(rt_vid):
    text = rt_vid.read_text(encoding="utf-8", errors="strict")
    span = find_function_span(text, "VW_UpdateScreen")
    if not span:
        die("VW_UpdateScreen definition disappeared after helper insertion")

    a, open_i, b = span
    fn = text[a:b]
    if MARK_CALL in fn:
        print("PASS: VW_UpdateScreen already patched")
        return

    insert = (
        "\n#ifdef __N64__\n"
        "    /* " + MARK_CALL + " */\n"
        "    rott64_r106_crt_inset_logical_frame();\n"
        "#endif\n"
    )
    fn = fn[:open_i - a + 1] + insert + fn[open_i - a + 1:]
    text = text[:a] + fn + text[b:]
    rt_vid.write_text(text, encoding="utf-8", newline="\n")
    print("PASS: patched generated/rott/rt_vid.c:VW_UpdateScreen")

def write_candidate_report(root):
    lines = ["ROTT64 r106 video-update candidates", ""]
    for path in sorted(root.rglob("*.c")):
        text = path.read_text(encoding="utf-8", errors="strict")
        for name in ("VW_UpdateScreen", "VH_UpdateScreen"):
            span = find_function_span(text, name)
            if span:
                lines.append(f"{path}:{name}")
    report = Path("build/reports/r106-video-update-candidates.txt")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report

def main(argv):
    if len(argv) != 2:
        die("usage: r106_patch_generated_vh_update_inset.py generated/rott")

    root = Path(argv[1])
    if not root.is_dir():
        die("missing generated root " + str(root))

    rt_vid = root / "rt_vid.c"
    if not rt_vid.is_file():
        die("missing generated/rott/rt_vid.c")

    report = write_candidate_report(root)
    insert_helper_before_vw(rt_vid)
    patch_vw_update(rt_vid)

    text = rt_vid.read_text(encoding="utf-8", errors="strict")
    for token in (MARK_HELPER, MARK_CALL, "rott64_r106_crt_inset_logical_frame();"):
        if token not in text:
            die("generated/rott/rt_vid.c missing " + token)
    if "rott64_n64_display_show_crt_safe" in text:
        die("old broken display wrapper remains in rt_vid.c")

    print("PASS: ROTT64_R106_LOGICAL_CRT_INSET installed in VW_UpdateScreen")
    print("PASS: candidate report:", report)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
