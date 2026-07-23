#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R86_STAT_INTEGRITY"


def die(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)


def function_span(text: str, name: str) -> tuple[int, int, int]:
    # Function name and argument list must be on a real source line. This avoids
    # accidentally matching comments that mention a function name.
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?"
        rf"[^;\n{{}}]*\b{re.escape(name)}[ \t]*\([^;\n]*\)"
        rf"[ \t]*\r?\n?[ \t]*\{{"
    )
    hits = list(pat.finditer(text))
    if len(hits) != 1:
        die(f"expected one definition of {name}, found {len(hits)}")

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
            if c in ("'", '"'):
                state = "string"; quote = c; i += 1; continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return m.start(), open_i, i + 1
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

    die("unterminated function " + name)


def insert_after_open(text: str, name: str, code: str) -> str:
    _start, open_i, _end = function_span(text, name)
    return text[:open_i + 1] + "\n" + code.rstrip() + "\n" + text[open_i + 1:]


def patch(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="strict")

    if MARK in text:
        print("PASS: r86 stat diagnostics already present")
        return

    for token in (
        "void MakeStatActive(statobj_t *x)",
        "void MakeStatInactive(statobj_t *stat)",
        "void DoSprites(void)",
        "for (temp = firstactivestat; temp;)",
        "tempnext = temp->nextactive;",
        "index = temp->itemnumber;",
        "if (temp->count < temp->numanims)",
        "stats[index].picnum",
    ):
        if token not in text:
            die("audited rt_stat.c shape changed; missing " + token)

    # N64-only libdragon diagnostics. Host builds see no libdragon dependency.
    inc = "#if defined(__N64__)\n#include <libdragon.h>\n#endif\n"
    if "#include <libdragon.h>" not in text:
        includes = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
        if not includes:
            die("rt_stat.c has no include block")
        text = text[:includes[-1].end()] + inc + text[includes[-1].end():]

    # Insert helpers immediately before the first active-list mutator.
    pos, _o, _e = function_span(text, "MakeStatActive")
    helper = r'''
#if defined(__N64__)
/* ROTT64_R86_STAT_INTEGRITY
 * Hardware crash was symbolized at DoSprites(), rt_stat.c:1840.
 * Catch the active-static list/object corruption before that dereference.
 */
static int rott64_r86_stat_ptr_ok(const statobj_t *p)
{
    uintptr_t v;
    uint32_t phys;
    uint32_t mem;

    if (p == NULL)
        return 0;

    v = (uintptr_t)p;
    if (((v & 0xE0000000u) != 0x80000000u) &&
        ((v & 0xE0000000u) != 0xA0000000u))
        return 0;
    if ((v & 3u) != 0)
        return 0;

    mem = (uint32_t)get_memory_size();
    if (mem < (uint32_t)sizeof(statobj_t))
        return 0;

    phys = PhysicalAddr(p);
    return phys <= mem - (uint32_t)sizeof(statobj_t);
}

static void rott64_r86_check_stat(const statobj_t *p, const char *where)
{
    assertf(rott64_r86_stat_ptr_ok(p),
        "R86 BAD STAT PTR %s p=%p first=%p last=%p afirst=%p alast=%p count=%d",
        where, (void *)p, (void *)FIRSTSTAT, (void *)LASTSTAT,
        (void *)firstactivestat, (void *)lastactivestat, statcount);
}

static void rott64_r86_check_stat_or_null(const statobj_t *p, const char *where)
{
    if (p != NULL)
        rott64_r86_check_stat(p, where);
}
#endif
'''
    text = text[:pos] + helper + "\n" + text[pos:]

    active_guard = r'''
#if defined(__N64__)
    rott64_r86_check_stat(x, "MakeStatActive:x");
    rott64_r86_check_stat_or_null(firstactivestat, "MakeStatActive:first");
    rott64_r86_check_stat_or_null(lastactivestat, "MakeStatActive:last");

    assertf((firstactivestat == NULL) == (lastactivestat == NULL),
        "R86 ACTIVE HEAD/TAIL MISMATCH first=%p last=%p x=%p",
        (void *)firstactivestat, (void *)lastactivestat, (void *)x);

    assertf(x != firstactivestat && x != lastactivestat &&
            x->prevactive == NULL && x->nextactive == NULL,
        "R86 DOUBLE/BAD ACTIVATE x=%p prev=%p next=%p item=%d flags=%08lx",
        (void *)x, (void *)x->prevactive, (void *)x->nextactive,
        x->itemnumber, (unsigned long)x->flags);

    if (lastactivestat != NULL)
        assertf(lastactivestat->nextactive == NULL,
            "R86 ACTIVE TAIL HAS NEXT tail=%p next=%p adding=%p",
            (void *)lastactivestat, (void *)lastactivestat->nextactive,
            (void *)x);
#endif

    /* Valid active-list insertion always creates a new tail. */
    x->nextactive = NULL;
'''
    text = insert_after_open(text, "MakeStatActive", active_guard)

    inactive_guard = r'''
#if defined(__N64__)
    rott64_r86_check_stat(stat, "MakeStatInactive:stat");
    rott64_r86_check_stat_or_null(stat->prevactive, "MakeStatInactive:prev");
    rott64_r86_check_stat_or_null(stat->nextactive, "MakeStatInactive:next");

    assertf(stat == firstactivestat || stat->prevactive != NULL,
        "R86 BAD INACTIVE HEAD stat=%p first=%p prev=%p next=%p",
        (void *)stat, (void *)firstactivestat,
        (void *)stat->prevactive, (void *)stat->nextactive);

    assertf(stat == lastactivestat || stat->nextactive != NULL,
        "R86 BAD INACTIVE TAIL stat=%p last=%p prev=%p next=%p",
        (void *)stat, (void *)lastactivestat,
        (void *)stat->prevactive, (void *)stat->nextactive);

    if (stat->prevactive != NULL)
        assertf(stat->prevactive->nextactive == stat,
            "R86 BROKEN PREV LINK stat=%p prev=%p prevnext=%p",
            (void *)stat, (void *)stat->prevactive,
            (void *)stat->prevactive->nextactive);

    if (stat->nextactive != NULL)
        assertf(stat->nextactive->prevactive == stat,
            "R86 BROKEN NEXT LINK stat=%p next=%p nextprev=%p",
            (void *)stat, (void *)stat->nextactive,
            (void *)stat->nextactive->prevactive);
#endif
'''
    text = insert_after_open(text, "MakeStatInactive", inactive_guard)

    # Re-isolate DoSprites after helper insertion.
    a, _open, b = function_span(text, "DoSprites")
    fn = text[a:b]

    decl = "statobj_t *temp, *tempnext;"
    if decl not in fn:
        die("DoSprites declaration changed")
    fn = fn.replace(
        decl,
        decl + r'''
#if defined(__N64__)
    int rott64_r86_iterations = 0;
#endif''',
        1,
    )

    loop_re = re.compile(
        r"for\s*\(\s*temp\s*=\s*firstactivestat\s*;\s*temp\s*;\s*\)\s*\{"
    )
    m = loop_re.search(fn)
    if not m:
        die("DoSprites active loop changed")
    guard = r'''
#if defined(__N64__)
        assertf(++rott64_r86_iterations < 4096,
            "R86 ACTIVE LIST CYCLE first=%p last=%p temp=%p statcount=%d",
            (void *)firstactivestat, (void *)lastactivestat,
            (void *)temp, statcount);
        rott64_r86_check_stat(temp, "DoSprites:temp");
#endif
'''
    fn = fn[:m.end()] + guard + fn[m.end():]

    next_stmt = "tempnext = temp->nextactive;"
    if next_stmt not in fn:
        die("DoSprites nextactive assignment changed")
    fn = fn.replace(
        next_stmt,
        next_stmt + r'''
#if defined(__N64__)
        rott64_r86_check_stat_or_null(tempnext, "DoSprites:tempnext");
        if (tempnext != NULL)
            assertf(tempnext->prevactive == temp,
                "R86 ACTIVE LINK BROKEN temp=%p next=%p nextprev=%p item=%d",
                (void *)temp, (void *)tempnext,
                (void *)tempnext->prevactive, temp->itemnumber);
#endif''',
        1,
    )

    index_stmt = "index = temp->itemnumber;"
    if index_stmt not in fn:
        die("DoSprites index assignment changed")
    fn = fn.replace(
        index_stmt,
        index_stmt + r'''
#if defined(__N64__)
            assertf(index >= 0 && index < NUMSTATS,
                "R86 BAD STAT INDEX temp=%p index=%d count=%d anims=%d tic=%d flags=%08lx",
                (void *)temp, index, temp->count, temp->numanims,
                temp->ticcount, (unsigned long)temp->flags);
#endif''',
        1,
    )

    text = text[:a] + fn + text[b:]

    for token in (
        MARK,
        "R86 DOUBLE/BAD ACTIVATE",
        "R86 BROKEN PREV LINK",
        "R86 BROKEN NEXT LINK",
        "R86 ACTIVE LIST CYCLE",
        'rott64_r86_check_stat(temp, "DoSprites:temp")',
        'rott64_r86_check_stat_or_null(tempnext, "DoSprites:tempnext")',
        "R86 BAD STAT INDEX",
        "if (temp->count < temp->numanims)",
    ):
        if token not in text:
            die("post-patch token missing: " + token)

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    print("PASS: r86 stat integrity diagnostics installed")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: r86_patch_stat_integrity.py <generated-rott-root>")
    root = Path(sys.argv[1]).resolve()
    path = root / "rt_stat.c"
    if not path.is_file():
        die("missing " + str(path))
    patch(path)


if __name__ == "__main__":
    main()
