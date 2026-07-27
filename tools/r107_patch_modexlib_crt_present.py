#!/usr/bin/env python3
from pathlib import Path
import re
import sys

REV = "r107"
MARK_HELPER = "ROTT64_R107_MODEXLIB_CRT_SAFE_PRESENT"
MARK_CALL = "ROTT64_R107_MODEXLIB_CRT_SAFE_CALL"
OLD_SYMBOL = "rott64_n64_display_show_crt_safe"
OLD_MARK = "ROTT64_R103_PRESENT_WRAP_CALLSITE"

def die(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def restore_stale_wrappers(root: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(root.rglob("*.c")):
        text = path.read_text(encoding="utf-8", errors="strict")
        original = text
        if OLD_SYMBOL in text:
            text = text.replace(OLD_SYMBOL + "(", "display_show(")
        text = text.replace(" /* " + OLD_MARK + " */", "")
        text = text.replace("/* " + OLD_MARK + " */", "")
        if text != original:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed.append(str(path))
    return changed

def add_helper_and_call(modexlib: Path) -> None:
    text = modexlib.read_text(encoding="utf-8", errors="strict")

    if OLD_SYMBOL in text or OLD_MARK in text:
        die("stale r103 wrapper remained in modexlib after cleanup")

    if '#include "n64_platform.h"\n' in text and "rott64_n64_" not in text:
        text = text.replace('#include "n64_platform.h"\n', "", 1)

    helper_match = re.search(
        r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+present_frame[ \t]*\(",
        text,
    )
    if helper_match is None:
        die("modexlib.c present_frame definition not found")

    if MARK_HELPER not in text:
        helper = r'''
#ifdef __N64__
/* ROTT64_R107_MODEXLIB_CRT_SAFE_PRESENT
 *
 * The real gameplay presenter lives here in generated/rott/modexlib.c.
 * ROTT supplies a 320x200 software frame in the top 200 rows of the N64
 * 320x240 surface. Present it inside a centered 288x216 safe rectangle so
 * consumer CRT overscan does not cut off the HUD/menu edges.
 *
 * This is deliberately local to modexlib.c: no public platform header,
 * no cross-translation-unit link dependency, and no bootdiag coupling.
 */
static void rott64_r107_crt_safe_present(surface_t *fb)
{
    enum {
        SRC_W = 320,
        SRC_H = 200,
        DST_W = 320,
        DST_H = 240,
        SAFE_X = 16,
        SAFE_Y = 12,
        SAFE_W = 288,
        SAFE_H = 216
    };
    static unsigned short source_row[SRC_W];
    unsigned char *base;
    int y;

    if (fb == NULL || fb->buffer == NULL)
        return;
    if (fb->width != DST_W || fb->height != DST_H || fb->stride == 0)
        return;

    base = (unsigned char *)fb->buffer;

    for (y = DST_H - 1; y >= 0; --y)
    {
        unsigned short *dst =
            (unsigned short *)(void *)(base + ((unsigned long)y * fb->stride));
        int x;

        if (y < SAFE_Y || y >= SAFE_Y + SAFE_H)
        {
            for (x = 0; x < DST_W; ++x)
                dst[x] = 0;
        }
        else
        {
            int local_y = y - SAFE_Y;
            int source_y = (local_y * SRC_H) / SAFE_H;
            const unsigned short *src =
                (const unsigned short *)(const void *)
                (base + ((unsigned long)source_y * fb->stride));

            for (x = 0; x < SRC_W; ++x)
                source_row[x] = src[x];

            for (x = 0; x < DST_W; ++x)
                dst[x] = 0;

            for (x = 0; x < SAFE_W; ++x)
            {
                int source_x = (x * SRC_W) / SAFE_W;
                dst[SAFE_X + x] = source_row[source_x];
            }
        }
    }
}
#endif

'''
        text = text[:helper_match.start()] + helper + text[helper_match.start():]

    call_re = re.compile(
        r"(?m)^(?P<indent>[ \t]*)display_show[ \t]*\([ \t]*(?P<arg>[A-Za-z_][A-Za-z0-9_]*)[ \t]*\)[ \t]*;[ \t]*(?:/\*.*\*/)?[ \t]*$"
    )
    calls = list(call_re.finditer(text))
    if len(calls) != 1:
        contexts = []
        for i, line in enumerate(text.splitlines(), 1):
            if "display_show" in line:
                contexts.append(f"{i}: {line}")
        die(
            "expected exactly one simple display_show() in modexlib.c, found "
            + str(len(calls))
            + "; contexts: "
            + " | ".join(contexts[:10])
        )

    call = calls[0]
    arg = call.group("arg")
    if MARK_CALL not in text:
        injected = (
            call.group("indent")
            + "#ifdef __N64__\n"
            + call.group("indent")
            + "/* "
            + MARK_CALL
            + " */\n"
            + call.group("indent")
            + f"rott64_r107_crt_safe_present({arg});\n"
            + call.group("indent")
            + "#endif\n"
        )
        text = text[:call.start()] + injected + text[call.start():]

    present_pos = re.search(
        r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+present_frame[ \t]*\(",
        text,
    )
    call_pos = text.find("rott64_r107_crt_safe_present(" + arg + ");")
    show_pos = text.find("display_show(" + arg + ")")
    if present_pos is None or not (present_pos.start() < call_pos < show_pos):
        die("CRT helper call is not inside the gameplay present path before display_show")

    modexlib.write_text(text, encoding="utf-8", newline="\n")

def audit(root: Path, modexlib: Path, restored: list[str]) -> None:
    text = modexlib.read_text(encoding="utf-8", errors="strict")
    for token in (MARK_HELPER, MARK_CALL, "rott64_r107_crt_safe_present("):
        if token not in text:
            die("modexlib final audit missing " + token)
    for token in (OLD_SYMBOL, OLD_MARK):
        for path in root.rglob("*.c"):
            if token in path.read_text(encoding="utf-8", errors="strict"):
                die(f"stale token {token} remains in {path}")

    report = Path("build/reports/r107-present-frame-audit.txt")
    report.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "ROTT64 r107 gameplay presenter audit",
        f"target={modexlib}",
        "present_function=present_frame",
        "safe_rect=288x216+16+12",
        "old_cross_tu_wrapper=absent",
        f"restored_stale_files={len(restored)}",
    ]
    lines.extend("restored=" + item for item in restored)

    for i, line in enumerate(text.splitlines(), 1):
        if (
            MARK_HELPER in line
            or MARK_CALL in line
            or "rott64_r107_crt_safe_present(" in line
            or "display_show(" in line
        ):
            lines.append(f"{i}: {line.strip()}")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("PASS: r107 gameplay CRT presenter patched in generated/rott/modexlib.c")
    print("PASS: stale r103 wrapper calls removed:", len(restored))
    print("PASS: report:", report)

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        die("usage: r107_patch_modexlib_crt_present.py generated/rott")
    root = Path(argv[1])
    if not root.is_dir():
        die("missing generated root " + str(root))
    modexlib = root / "modexlib.c"
    if not modexlib.is_file():
        die("missing " + str(modexlib))

    restored = restore_stale_wrappers(root)
    add_helper_and_call(modexlib)
    audit(root, modexlib, restored)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
