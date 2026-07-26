#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R92I_ATOMIC_SAVE_VALIDATE"


def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)


def function_span(text: str, name: str) -> tuple[int, int, int]:
    pat = re.compile(
        rf"(?m)^[ \t]*(?:static[ \t]+)?[^#;\n{{}}]*\b{re.escape(name)}[ \t]*"
        rf"\([^;\n{{}}]*\)[ \t]*\r?\n?[ \t]*\{{"
    )
    hits = list(pat.finditer(text))
    if not hits:
        fail("function not found: " + name)
    if len(hits) > 1:
        fail("multiple functions found: " + name)

    m = hits[0]
    o = text.find("{", m.start(), m.end())
    depth = 0
    state = "code"
    quote = ""
    i = o
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
                    return m.start(), o, i + 1
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
    fail("unterminated function: " + name)


def add_include(text: str, include: str) -> str:
    if include in text:
        return text
    incs = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if incs:
        return text[:incs[-1].end()] + include + "\n" + text[incs[-1].end():]
    return include + "\n" + text


def patch_rt_game(gen: Path) -> None:
    path = gen / "rt_game.c"
    if not path.is_file():
        fail("missing generated rt_game.c")

    text = path.read_text(encoding="utf-8", errors="strict")
    text = add_include(text, "#include <errno.h>")

    helper = r'''
/* ROTT64_R92I_ATOMIC_SAVE_VALIDATE: N64-safe save probing/commit.
 * Menu scans must not LoadFile() an entire save just to show a name/picture.
 * Saves are written to rotttmpN.rot, streamed/checked, then committed.
 */
static char *ROTT64_BuildSavePathForBase(const char *base, int num)
{
    char name[] = "rottgam0.rot";

    if (base == NULL)
        return NULL;

    strcpy(name, base);
    itoa(num, &name[7], 16);
    name[8] = '.';
    return M_StringJoin(ApogeePath, PATH_SEP_STR, name, NULL);
}

static boolean ROTT64_ValidateSaveGameFile(const char *filename, gamestorage_t *out_game, boolean strict)
{
    FILE *fp;
    long total;
    char tag[4];
    gamestorage_t game;
    int savedchecksum = 0;
    long checksum = 0;

    if (filename == NULL)
        return false;

    fp = fopen(filename, "rb");
    if (fp == NULL)
        return false;

    if (fseek(fp, 0, SEEK_END) != 0)
    {
        fclose(fp);
        return false;
    }

    total = ftell(fp);
    if (total < (long)(4 + sizeof(game) + sizeof(savedchecksum)))
    {
        fclose(fp);
        return false;
    }

    if (fseek(fp, 0, SEEK_SET) != 0)
    {
        fclose(fp);
        return false;
    }

    if (fread(tag, 1, sizeof(tag), fp) != sizeof(tag) || memcmp(tag, "ROTT", 4) != 0)
    {
        fclose(fp);
        return false;
    }

    if (fread(&game, 1, sizeof(game), fp) != sizeof(game))
    {
        fclose(fp);
        return false;
    }

    if (game.version != ROTTVERSION)
    {
        fclose(fp);
        return false;
    }

    if (game.episode < 1 || game.episode > 6 || game.area < 0 || game.area > 99)
    {
        fclose(fp);
        return false;
    }

    if (memchr(game.message, '\0', sizeof(game.message)) == NULL)
    {
        fclose(fp);
        return false;
    }

    if (strict)
    {
        byte buffer[1024];
        long left = total - (long)sizeof(savedchecksum);

        if (fseek(fp, 0, SEEK_SET) != 0)
        {
            fclose(fp);
            return false;
        }

        while (left > 0)
        {
            size_t want = sizeof(buffer);
            size_t got;

            if ((long)want > left)
                want = (size_t)left;

            got = fread(buffer, 1, want, fp);
            if (got != want)
            {
                fclose(fp);
                return false;
            }

            checksum = DoCheckSum(buffer, (int)got, checksum);
            left -= (long)got;
        }

        if (fread(&savedchecksum, 1, sizeof(savedchecksum), fp) != sizeof(savedchecksum))
        {
            fclose(fp);
            return false;
        }

        if ((int)checksum != savedchecksum)
        {
            fclose(fp);
            return false;
        }
    }

    fclose(fp);

    if (out_game != NULL)
        memcpy(out_game, &game, sizeof(game));

    return true;
}

boolean ROTT64_ValidateSaveGameSlot(int num, gamestorage_t *out_game, boolean strict)
{
    char *filename;
    boolean ok;

    if (num > 15 || num < 0)
        return false;

    filename = ROTT64_BuildSavePathForBase("rottgam0.rot", num);
    ok = ROTT64_ValidateSaveGameFile(filename, out_game, strict);
    free(filename);
    return ok;
}

static boolean ROTT64_CopyFileStreaming(const char *srcname, const char *dstname)
{
    FILE *src;
    FILE *dst;
    byte buffer[1024];
    size_t got;

    src = fopen(srcname, "rb");
    if (src == NULL)
        return false;

    dst = fopen(dstname, "wb");
    if (dst == NULL)
    {
        fclose(src);
        return false;
    }

    while ((got = fread(buffer, 1, sizeof(buffer), src)) > 0)
    {
        if (fwrite(buffer, 1, got, dst) != got)
        {
            fclose(src);
            fclose(dst);
            return false;
        }
    }

    if (ferror(src) || fflush(dst) != 0)
    {
        fclose(src);
        fclose(dst);
        return false;
    }

    fclose(src);
    fclose(dst);
    return true;
}

static boolean ROTT64_CommitSaveFile(const char *tmpname, const char *finalname)
{
    remove(finalname);

    if (rename(tmpname, finalname) == 0)
        return true;

    if (ROTT64_CopyFileStreaming(tmpname, finalname))
    {
        remove(tmpname);
        return true;
    }

    remove(finalname);
    return false;
}

'''

    if "ROTT64_ValidateSaveGameSlot" not in text:
        a, _o, _b = function_span(text, "SaveTheGame")
        text = text[:a] + helper + text[a:]

    a, o, b = function_span(text, "GetSavedMessage")
    text = text[:o] + r'''{
    gamestorage_t game;

    if (num > 15 || num < 0)
        Error("Illegal Load game value=%d\n", num);

    if (!ROTT64_ValidateSaveGameSlot(num, &game, true))
    {
        strcpy(message, "     - \x81 -");
        return;
    }

    strcpy(message, game.message);
}''' + text[b:]

    a, o, b = function_span(text, "GetSavedHeader")
    text = text[:o] + r'''{
    if (num > 15 || num < 0)
        Error("Illegal Load game value=%d\n", num);

    memset(game, 0, sizeof(*game));
    ROTT64_ValidateSaveGameSlot(num, game, true);
}''' + text[b:]

    a, o, b = function_span(text, "LoadTheGame")
    load_func = text[a:b]
    if "ROTT64_R92I_LOAD_VALIDATE_BEFORE_FULL_LOAD" not in load_func:
        needle = "\t// Load the file\n"
        if needle not in load_func:
            needle = "    // Load the file\n"
        if needle not in load_func:
            fail("LoadTheGame load-file anchor not found")
        guard = r'''
    /* ROTT64_R92I_LOAD_VALIDATE_BEFORE_FULL_LOAD */
    if (!ROTT64_ValidateSaveGameSlot(num, NULL, true))
    {
        free(filename);
        return false;
    }

'''
        load_func = load_func.replace(needle, guard + needle, 1)
        text = text[:a] + load_func + text[b:]

    a, o, b = function_span(text, "SaveTheGame")
    save_func = text[a:b]
    if "ROTT64_R92I_SAVE_TEMP_PATH" not in save_func:
        if "\tchar *filename;" in save_func:
            save_func = save_func.replace("\tchar *filename;", "\tchar *filename;\n\tchar *finalname;\n\tchar tmplname[] = \"rotttmp0.rot\";", 1)
            indent = "\t"
        elif "    char *filename;" in save_func:
            save_func = save_func.replace("    char *filename;", "    char *filename;\n    char *finalname;\n    char tmplname[] = \"rotttmp0.rot\";", 1)
            indent = "    "
        else:
            fail("SaveTheGame filename local declaration not found")

        old = "filename = M_StringJoin(ApogeePath, PATH_SEP_STR, loadname, NULL);"
        if old not in save_func:
            old = "filename =\n\t\tM_StringJoin(ApogeePath, PATH_SEP_STR, loadname, NULL);"
        if old not in save_func:
            fail("SaveTheGame filename creation anchor not found")
        new = ("/* ROTT64_R92I_SAVE_TEMP_PATH */\n"
               f"{indent}finalname = M_StringJoin(ApogeePath, PATH_SEP_STR, loadname, NULL);\n"
               f"{indent}itoa(num, &tmplname[7], 16);\n"
               f"{indent}tmplname[8] = '.';\n"
               f"{indent}filename = M_StringJoin(ApogeePath, PATH_SEP_STR, tmplname, NULL);\n"
               f"{indent}remove(filename);")
        save_func = save_func.replace(old, new, 1)

        new_end_template = r'''{indent}close(savehandle);

{indent}if (!ROTT64_ValidateSaveGameFile(filename, NULL, true))
{indent}{{
{indent}{indent}printf("ROTT64 r92i: temp save failed validation, deleting %s\n", filename);
{indent}{indent}remove(filename);
{indent}{indent}free(filename);
{indent}{indent}free(finalname);
{indent}{indent}return false;
{indent}}}

{indent}if (!ROTT64_CommitSaveFile(filename, finalname))
{indent}{{
{indent}{indent}printf("ROTT64 r92i: failed to commit save %s -> %s\n", filename, finalname);
{indent}{indent}remove(filename);
{indent}{indent}free(filename);
{indent}{indent}free(finalname);
{indent}{indent}return false;
{indent}}}

{indent}free(filename);
{indent}free(finalname);

{indent}pickquick = true;
{indent}return (true);'''
        new_end = new_end_template.format(indent=indent)
        save_func, n_end = re.subn(
            r"(?m)^[ \t]*free\(filename\);\n[ \t]*close\(savehandle\);\n\s*pickquick[ \t]*=[ \t]*true;\n[ \t]*return[ \t]*\(true\);",
            lambda _m: new_end,
            save_func,
            count=1,
        )
        if n_end != 1:
            fail("SaveTheGame final free/close anchor not found")

        if "char *finalname" not in save_func or "ROTT64_R92I_SAVE_TEMP_PATH" not in save_func:
            fail("SaveTheGame temp path patch failed")
        text = text[:a] + save_func + text[b:]

    if MARK not in text:
        text = "/* " + MARK + " */\n" + text

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    out = path.read_text(encoding="utf-8", errors="ignore")
    for token in (
        "ROTT64_ValidateSaveGameSlot",
        "ROTT64_ValidateSaveGameFile",
        "ROTT64_CommitSaveFile",
        "ROTT64_R92I_SAVE_TEMP_PATH",
        "ROTT64_R92I_LOAD_VALIDATE_BEFORE_FULL_LOAD",
    ):
        if token not in out:
            fail("rt_game.c missing " + token)

    for fn in ("GetSavedMessage", "GetSavedHeader"):
        a, _o, b = function_span(out, fn)
        body = out[a:b]
        if "LoadFile" in body:
            fail(fn + " still LoadFile()s full save")

    print("PASS: " + MARK + " rt_game.c")


def patch_rt_menu(gen: Path) -> None:
    path = gen / "rt_menu.c"
    if not path.is_file():
        fail("missing generated rt_menu.c")

    text = path.read_text(encoding="utf-8", errors="strict")

    decl = "extern boolean ROTT64_ValidateSaveGameSlot(int num, gamestorage_t *game, boolean strict);"
    if decl not in text:
        incs = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
        if incs:
            text = text[:incs[-1].end()] + decl + "\n" + text[incs[-1].end():]
        else:
            text = decl + "\n" + text

    a, o, b = function_span(text, "ScanForSavedGames")
    text = text[:o] + r'''{
    int which;
    boolean found = false;
    gamestorage_t game;

    /* ROTT64_R92I_SCAN_VALIDATES_SLOTS */
    memset(&SaveGamesAvail[0], 0, sizeof(SaveGamesAvail));
    memset(&SaveGameNames[0][0], 0, sizeof(SaveGameNames));

    for (which = 0; which < NUMSAVEGAMES; which++)
    {
        if (ROTT64_ValidateSaveGameSlot(which, &game, true))
        {
            found = true;
            SaveGamesAvail[which] = 1;
            strcpy(&SaveGameNames[which][0], game.message);
        }
    }

    if (found)
    {
        if (MainMenu[loadgame].active == CP_Inactive)
            MainMenu[loadgame].active = CP_Active;
    }
    else
        MainMenu[loadgame].active = CP_Inactive;
}''' + text[b:]

    # ROTT64_R92I_NO_QUICKSAVE_ELSE_SPLICE:
    # Do not splice an else into QuickSaveGame(). The stock function has
    # nested UI logic, and a blind first-brace insertion generated invalid C
    # in r92b. Save visibility is handled by ScanForSavedGames(), while actual
    # save validity/commit is handled in rt_game.c.

    if MARK not in text:
        text = "/* " + MARK + " */\n" + text

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")

    out = path.read_text(encoding="utf-8", errors="ignore")
    if "ROTT64_R92I_SCAN_VALIDATES_SLOTS" not in out:
        fail("ScanForSavedGames was not rewritten")
    scan_start, _scan_open, scan_end = function_span(out, "ScanForSavedGames")
    scan_body = out[scan_start:scan_end]
    if "M_FileCaseExists(path)" in scan_body or "GetSavedMessage(which" in scan_body:
        fail("ScanForSavedGames still uses old file-exists/message scan")
    if "extern boolean ROTT64_ValidateSaveGameSlot" not in out:
        fail("rt_menu.c missing ROTT64_ValidateSaveGameSlot declaration")

    print("PASS: " + MARK + " rt_menu.c")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: r92i_patch_atomic_save_validate.py generated/rott")
    gen = Path(argv[1])
    if not gen.is_dir():
        fail("generated/rott directory not found")
    patch_rt_game(gen)
    patch_rt_menu(gen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
