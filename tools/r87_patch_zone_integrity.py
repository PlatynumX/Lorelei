#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R87_ZONE_GUARDS"

def die(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)

def function_span(text: str, name: str) -> tuple[int, int, int]:
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
    _a, o, _b = function_span(text, name)
    return text[:o + 1] + "\n" + code.rstrip() + "\n" + text[o + 1:]

def patch(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="strict")
    if MARK in text:
        print("PASS: r87 zone guards already present")
        return

    for token in (
        "#define ZONEID",
        "typedef struct memblock",
        "static memblock_t *blockbytag[PU_MAX];",
        "static size_t heapsize;",
        "void *Z_Malloc(size_t size, pu_tag tag, void **user)",
        "void Z_Free(void *p)",
        "void Z_ChangeTag(void *ptr, pu_tag tag)",
        "malloc(size + HEADER_SIZE)",
        "block->size = size;",
    ):
        if token not in text:
            die("z_zone.c shape changed; missing " + token)

    inc = "#if defined(__N64__)\n#include <libdragon.h>\n#endif\n"
    if "#include <libdragon.h>" not in text:
        includes = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
        if not includes:
            die("z_zone.c has no include block")
        text = text[:includes[-1].end()] + inc + text[includes[-1].end():]

    anchor = "static size_t heapsize;"
    pos = text.find(anchor) + len(anchor)

    helpers = r"""
#if defined(__N64__)
/* ROTT64_R87_ZONE_GUARDS
 * r86 now faults in _malloc_r -> Z_Malloc -> W_CacheLumpNum.
 * Validate all Taradino zone metadata before each libc malloc, and put a
 * 16-byte redzone after every Taradino allocation.
 */
#define ROTT64_R87_GUARD_BYTES 16u
#define ROTT64_R87_GUARD_VALUE 0xA5u

static int rott64_r87_heap_ptr_ok(const void *p, size_t bytes)
{
    unsigned long v;
    unsigned long phys;
    unsigned long mem;

    if (p == NULL)
        return 0;

    v = (unsigned long)p;
    if (((v & 0xE0000000ul) != 0x80000000ul) &&
        ((v & 0xE0000000ul) != 0xA0000000ul))
        return 0;

    phys = (unsigned long)PhysicalAddr(p);
    mem = (unsigned long)get_memory_size();

    if (phys >= mem)
        return 0;
    if (bytes > mem - phys)
        return 0;

    return 1;
}

static void rott64_r87_check_block(memblock_t *b, const char *where)
{
    unsigned char *guard;
    unsigned int i;
    size_t span;

    assertf(rott64_r87_heap_ptr_ok(b, sizeof(*b)),
        "R87 BAD ZONE PTR %s block=%p", where, (void *)b);

    assertf(b->id == ZONEID,
        "R87 BAD ZONEID %s block=%p id=%08lx tag=%d size=%lu",
        where, (void *)b, (unsigned long)b->id, (int)b->tag,
        (unsigned long)b->size);

    assertf((int)b->tag >= 0 && (int)b->tag < PU_MAX,
        "R87 BAD ZONE TAG %s block=%p tag=%d size=%lu",
        where, (void *)b, (int)b->tag, (unsigned long)b->size);

    assertf(b->size <= (size_t)get_memory_size(),
        "R87 BAD ZONE SIZE %s block=%p size=%lu",
        where, (void *)b, (unsigned long)b->size);

    span = HEADER_SIZE + b->size + ROTT64_R87_GUARD_BYTES;
    assertf(rott64_r87_heap_ptr_ok(b, span),
        "R87 ZONE SPAN OOB %s block=%p size=%lu span=%lu",
        where, (void *)b, (unsigned long)b->size, (unsigned long)span);

    guard = (unsigned char *)b + HEADER_SIZE + b->size;
    for (i = 0; i < ROTT64_R87_GUARD_BYTES; ++i)
    {
        assertf(guard[i] == ROTT64_R87_GUARD_VALUE,
            "R87 ZONE OVERRUN %s block=%p size=%lu guard[%u]=%02x",
            where, (void *)b, (unsigned long)b->size,
            i, (unsigned int)guard[i]);
    }
}

static void rott64_r87_validate_zone(const char *where)
{
    int tag;
    heap_stats_t hs;

    sys_get_heap_stats(&hs);
    assertf(hs.total > 0 && hs.used >= 0 && hs.used <= hs.total,
        "R87 HEAP STATS BAD %s total=%d used=%d",
        where, hs.total, hs.used);

    for (tag = 0; tag < PU_MAX; ++tag)
    {
        memblock_t *first = blockbytag[tag];
        memblock_t *cur;
        unsigned int count = 0;

        if (first == NULL)
            continue;

        assertf(rott64_r87_heap_ptr_ok(first, sizeof(*first)),
            "R87 BAD TAG HEAD %s tag=%d head=%p",
            where, tag, (void *)first);

        cur = first;
        do
        {
            memblock_t *next;
            memblock_t *prev;

            assertf(++count < 16384,
                "R87 ZONE LIST CYCLE %s tag=%d first=%p cur=%p",
                where, tag, (void *)first, (void *)cur);

            rott64_r87_check_block(cur, where);
            next = cur->next;
            prev = cur->prev;

            assertf(rott64_r87_heap_ptr_ok(next, sizeof(*next)),
                "R87 BAD ZONE NEXT %s tag=%d cur=%p next=%p",
                where, tag, (void *)cur, (void *)next);
            assertf(rott64_r87_heap_ptr_ok(prev, sizeof(*prev)),
                "R87 BAD ZONE PREV %s tag=%d cur=%p prev=%p",
                where, tag, (void *)cur, (void *)prev);

            assertf(next->prev == cur,
                "R87 NEXT BACKLINK %s tag=%d cur=%p next=%p nextprev=%p",
                where, tag, (void *)cur, (void *)next, (void *)next->prev);
            assertf(prev->next == cur,
                "R87 PREV FORWARDLINK %s tag=%d cur=%p prev=%p prevnext=%p",
                where, tag, (void *)cur, (void *)prev, (void *)prev->next);

            cur = next;
        } while (cur != first);
    }
}

static void rott64_r87_fill_guard(memblock_t *b)
{
    memset((unsigned char *)b + HEADER_SIZE + b->size,
           ROTT64_R87_GUARD_VALUE,
           ROTT64_R87_GUARD_BYTES);
}
#endif
"""
    text = text[:pos] + helpers + text[pos:]

    pre = r"""
#if defined(__N64__)
    rott64_r87_validate_zone("Z_Malloc:pre");
    assertf(size <= (size_t)get_memory_size(),
        "R87 ABSURD ALLOC size=%lu tag=%d",
        (unsigned long)size, (int)tag);
#endif
"""
    text = insert_after_open(text, "Z_Malloc", pre)

    old_alloc = "malloc(size + HEADER_SIZE)"
    new_alloc = """malloc(size + HEADER_SIZE
#if defined(__N64__)
                 + ROTT64_R87_GUARD_BYTES
#endif
                 )"""
    if text.count(old_alloc) != 1:
        die("expected exactly one malloc(size + HEADER_SIZE)")
    text = text.replace(old_alloc, new_alloc, 1)

    if text.count("block->size = size;") != 1:
        die("expected exactly one block->size assignment")
    text = text.replace(
        "block->size = size;",
        """block->size = size;
#if defined(__N64__)
    rott64_r87_fill_guard(block);
#endif""",
        1,
    )

    fa, _fo, fb = function_span(text, "Z_Free")
    freefn = text[fa:fb]
    m = re.search(r"if\s*\(\s*!p\s*\)\s*return\s*;", freefn)
    if not m:
        die("Z_Free null guard changed")
    freefn = freefn[:m.end()] + """
#if defined(__N64__)
    rott64_r87_check_block(block, "Z_Free");
#endif
""" + freefn[m.end():]
    text = text[:fa] + freefn + text[fb:]

    ca, _co, cb = function_span(text, "Z_ChangeTag")
    changefn = text[ca:cb]
    m = re.search(r"if\s*\(\s*!ptr\s*\)\s*return\s*;", changefn)
    if not m:
        die("Z_ChangeTag null guard changed")
    changefn = changefn[:m.end()] + """
#if defined(__N64__)
    rott64_r87_check_block(block, "Z_ChangeTag");
#endif
""" + changefn[m.end():]
    text = text[:ca] + changefn + text[cb:]

    for token in (
        MARK,
        "R87 ZONE OVERRUN",
        "R87 BAD ZONEID",
        "R87 NEXT BACKLINK",
        "R87 PREV FORWARDLINK",
        'rott64_r87_validate_zone("Z_Malloc:pre")',
        "rott64_r87_fill_guard(block)",
    ):
        if token not in text:
            die("post-patch missing " + token)

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    print("PASS: r87 zone redzones/list checks installed")

def main() -> None:
    if len(sys.argv) != 2:
        die("usage: r87_patch_zone_integrity.py <generated-rott-root>")
    root = Path(sys.argv[1]).resolve()
    path = root / "z_zone.c"
    if not path.is_file():
        die("missing " + str(path))
    patch(path)

if __name__ == "__main__":
    main()
