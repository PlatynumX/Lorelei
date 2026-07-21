#!/usr/bin/env python3
"""Create a deterministic Taradino source tree with the ROTT64 platform overlay."""
from __future__ import annotations
import argparse, re, shutil, sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_regex_once(
    text: str, pattern: str, replacement: str, label: str, flags: int = 0
) -> str:
    compiled = re.compile(pattern, flags)
    matches = list(compiled.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one match, found {len(matches)}")
    return compiled.sub(lambda _match: replacement, text, count=1)

def inject_function_return(text: str, name: str) -> str:
    pattern=re.compile(rf"(void\s+{re.escape(name)}\s*\([^)]*\)\s*\{{)")
    match=pattern.search(text)
    if not match:
        raise RuntimeError(f"could not locate {name}()")
    insertion=match.group(1)+"\n#ifdef __N64__\n    return;\n#endif"
    return text[:match.start()]+insertion+text[match.end():]

def prepare(root: Path, upstream: Path, output: Path) -> None:
    source=upstream/"rott"
    if not source.is_dir(): raise RuntimeError(f"missing Taradino rott source: {source}")
    if output.exists(): shutil.rmtree(output)
    shutil.copytree(source, output)

    platform=root/"platform"/"n64"
    shutil.copy2(platform/"modexlib_n64.c", output/"modexlib.c")
    shutil.copy2(platform/"SDL.h", output/"SDL.h")
    shutil.copy2(platform/"SDL_mixer.h", output/"SDL_mixer.h")
    # Shadow libdragon/newlib's unsupported POSIX <dirent.h> with the
    # fixed-data-directory compatibility shim used by the N64 target.
    shutil.copy2(platform/"dirent.h", output/"dirent.h")
    # Keep Taradino's real fx_mixer.c. The N64 SDL_mixer compatibility layer
    # decodes Creative VOC sound lumps and plays them through libdragon.
    shutil.copy2(platform/"music_wav64.c", output/"dukemusc.c")
    shutil.copy2(platform/"rt_datadir_n64.c", output/"rt_datadir.c")
    # Taradino's desktop VGA text screen creates its own SDL renderer, textures,
    # and 640x400 RGB surfaces. It is only an exit/shutdown presentation path,
    # so replace it with a no-op for the first gameplay target.
    shutil.copy2(platform/"vgatext_n64.c", output/"vgatext.c")

    # Desktop MIDI synthesizer backends remain excluded. ROTT64 streams
    # build-time-rendered WAV64 music through libdragon instead.
    for unused_backend in ("adlmusic.c", "sdlmusic.c"):
        candidate = output / unused_backend
        if candidate.exists():
            candidate.unlink()

    main_path=output/"rt_main.c"
    text=main_path.read_text(encoding="utf-8",errors="strict")
    text=replace_once(text,'#include "SDL.h"','#include "SDL.h"\n#include "n64_platform.h"',"rt_main include")
    text = replace_regex_once(
        text,
        r"int\s+main\s*\(\s*int\s+argc\s*,\s*char\s*\*\s*argv\s*\[\s*\]\s*\)\s*\{",
        'int main(void)\n{\n'
        '    static char rott64_program_name[] = \"rott64\";\n'
        '    static char *rott64_argv[] = { rott64_program_name, NULL };\n'
        '    int argc = 1;\n'
        '    char **argv = rott64_argv;\n'
        '    n64_platform_init();\n'
        '    n64_platform_checkpoint("T07: entered Taradino main");',
        "rt_main entry",
    )
    text = replace_regex_once(
        text,
        r"(?m)^[ \t]*CheckCommandLineParameters\s*\(\s*\)\s*;[ \t]*$",
        "    CheckCommandLineParameters();\n"
        "#ifdef __N64__\n"
        "    NoSound = false;\n"
        "    quiet = true;\n"
        "#endif",
        "enable N64 sound effects",
    )
    text = replace_regex_once(
        text,
        r"(?m)^[ \t]*SetRottScreenRes\s*\(\s*iGLOBAL_SCREENWIDTH\s*,\s*iGLOBAL_SCREENHEIGHT\s*\)\s*;[ \t]*$",
        "    SetRottScreenRes(320, 200);",
        "fixed N64 resolution",
    )

    # R41 hardware startup tracing. The working R40 build reaches Taradino
    # after all six platform/data checks, then black-screens. Insert visible
    # checkpoints before each major startup operation so the last displayed
    # label identifies the call that fails or never returns. This does not
    # alter product selection, episode handling, or other registered logic.
    if "PopulateEpisodeMenu(datadir);" in text:
        startup_markers = (
            (
                "    // Set which release version we're on",
                '    n64_platform_checkpoint("T08: before product/map detection");\n'
                "    // Set which release version we're on",
            ),
            (
                "    PopulateEpisodeMenu(datadir);",
                '    n64_platform_checkpoint("T09: before PopulateEpisodeMenu");\n'
                "    PopulateEpisodeMenu(datadir);",
            ),
            (
                "    DrawRottTitle();",
                '    n64_platform_checkpoint("T10: before DrawRottTitle");\n'
                "    DrawRottTitle();",
            ),
            (
                "    StartupSoftError();",
                '    n64_platform_checkpoint("T11: before StartupSoftError");\n'
                "    StartupSoftError();",
            ),
            (
                "    CheckCommandLineParameters();",
                '    n64_platform_checkpoint("T12: before command-line setup");\n'
                "    CheckCommandLineParameters();",
            ),
            (
                "    Z_Init(50000, 1000000);",
                '    n64_platform_checkpoint("T13: before Z_Init");\n'
                "    Z_Init(50000, 1000000);",
            ),
            (
                "    IN_Startup();",
                '    n64_platform_checkpoint("T14: before IN_Startup");\n'
                "    IN_Startup();",
            ),
            (
                "    InitializeGameCommands();",
                '    n64_platform_checkpoint("T15: before game commands");\n'
                "    InitializeGameCommands();",
            ),
            (
                "        ReadConfig();",
                '        n64_platform_checkpoint("T16: before ReadConfig");\n'
                "        ReadConfig();",
            ),
            (
                "        ReadSETUPFiles();",
                '        n64_platform_checkpoint("T17: before ReadSETUPFiles");\n'
                "        ReadSETUPFiles();",
            ),
            (
                "        SetupWads();",
                '        n64_platform_checkpoint("T18: before SetupWads");\n'
                "        SetupWads();",
            ),
            (
                "        BuildTables();",
                '        n64_platform_checkpoint("T19: before BuildTables");\n'
                "        BuildTables();",
            ),
            (
                "        GetMenuInfo();",
                '        n64_platform_checkpoint("T20: before GetMenuInfo");\n'
                "        GetMenuInfo();",
            ),
            (
                "    SetRottScreenRes(320, 200);",
                '    n64_platform_checkpoint("T21: before screen resolution");\n'
                "    SetRottScreenRes(320, 200);",
            ),
            (
                "            status2 = SD_SetupFXCard();",
                '            n64_platform_checkpoint("T22: before FX setup");\n'
                "            status2 = SD_SetupFXCard();",
            ),
            (
                "                SD_Startup(false);",
                '                n64_platform_checkpoint("T23: before SD_Startup");\n'
                "                SD_Startup(false);",
            ),
            (
                "                MU_Startup(false);",
                '                n64_platform_checkpoint("T24: before MU_Startup");\n'
                "                MU_Startup(false);",
            ),
            (
                "        Init_Tables();",
                '        n64_platform_checkpoint("T25: before Init_Tables");\n'
                "        Init_Tables();",
            ),
            (
                "        InitializeRNG();",
                '        n64_platform_checkpoint("T26: before RNG");\n'
                "        InitializeRNG();",
            ),
            (
                "        InitializeMessages();",
                '        n64_platform_checkpoint("T27: before messages");\n'
                "        InitializeMessages();",
            ),
            (
                "        LoadColorMap();",
                '        n64_platform_checkpoint("T28: before color map");\n'
                "        LoadColorMap();",
            ),
            (
                "    VL_SetVGAPlaneMode();",
                '    n64_platform_checkpoint("T29: entering VGA plane mode");\n'
                "    VL_SetVGAPlaneMode();",
            ),
        )
        for old_marker, new_marker in startup_markers:
            count = text.count(old_marker)
            if count != 1:
                raise RuntimeError(
                    "R41 startup trace marker "
                    f"{old_marker!r}: expected one match, found {count}"
                )
            text = text.replace(old_marker, new_marker, 1)

    main_path.write_text(text,encoding="utf-8")

    cfg_path=output/"rt_cfg.c"
    text=cfg_path.read_text(encoding="utf-8",errors="strict")
    # Do not probe or parse desktop config/save files from the read-only ROM.
    # Preserve Taradino's own defaults so buttonscan, view size, difficulty,
    # battle options, and violence settings are initialized normally.
    read_config_pattern = re.compile(r"(void\s+ReadConfig\s*\([^)]*\)\s*\{)")
    match = read_config_pattern.search(text)
    if match:
        replacement = (
            match.group(1)
            + "\n#ifdef __N64__\n"
              "    SetSoundDefaultValues();\n"
              "    SetConfigDefaultValues();\n"
              "    SetBattleDefaultValues();\n"
              "    ConfigLoaded = true;\n"
              "    return;\n"
              "#endif"
        )
        text = text[:match.start()] + replacement + text[match.end():]
    for function in ("CheckVendor","WriteScores","WriteBattleConfig","WriteConfig","WriteSoundFile"):
        if re.search(rf"void\s+{function}\s*\(", text):
            text=inject_function_return(text,function)
    cfg_path.write_text(text,encoding="utf-8")

    # Fix legacy ctype usage for targets where plain char is signed. The ctype
    # macros are only defined for EOF or values representable as unsigned char;
    # passing a negative char also trips libdragon's -Werror=char-subscripts.
    menu_path = output / "rt_menu.c"
    menu_text = menu_path.read_text(encoding="utf-8", errors="strict")
    for old, new, expected, label in (
        ("isspace(*source)", "isspace((unsigned char)*source)", 2, "rt_menu source ctype casts"),
        ("isspace(wordtext[pos])", "isspace((unsigned char)wordtext[pos])", 1, "rt_menu word ctype cast"),
    ):
        count = menu_text.count(old)
        if count != expected:
            raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
        menu_text = menu_text.replace(old, new)
    menu_path.write_text(menu_text, encoding="utf-8")

    # Apply the same signed-char ctype fix to the command-line helpers.
    # isalpha(), like the other ctype macros, only accepts EOF or values that
    # are representable as unsigned char. libdragon's strict MIPS build also
    # diagnoses the legacy plain-char calls as -Wchar-subscripts.
    util_path = output / "rt_util.c"
    util_text = util_path.read_text(encoding="utf-8", errors="strict")
    old = "isalpha(*parm)"
    new = "isalpha((unsigned char)*parm)"
    count = util_text.count(old)
    if count != 2:
        raise RuntimeError(f"rt_util isalpha casts: expected 2 matches, found {count}")
    util_text = util_text.replace(old, new)
    util_path.write_text(util_text, encoding="utf-8")

    # The N64 toolchain models Taradino's fixed type as long int. Match the
    # variadic debug format to the real argument width instead of relying on
    # the desktop ABI's sizeof(int) == sizeof(long) assumption.
    net_path = output / "rt_net.c"
    net_text = net_path.read_text(encoding="utf-8", errors="strict")
    net_text = replace_regex_once(
        net_text,
        r'SoftError\("x=%4x y=%4x a=%4x time=%5d\\n",\s*player->x,\s*player->y,\s*player->angle,\s*oldpolltime\);',
        'SoftError("x=%4lx y=%4lx a=%4x time=%5d\\n",\n'
        '                  (unsigned long)player->x,\n'
        '                  (unsigned long)player->y, player->angle, oldpolltime);',
        "rt_net fixed-width debug format",
    )
    net_path.write_text(net_text, encoding="utf-8")

    # Registered Dark War compiles T_SnakePath(), which is omitted by the
    # shareware preprocessor path. On the N64 ABI, Taradino's fixed type is
    # long int, so the legacy %x debug formats are invalid under libdragon's
    # strict -Werror=format policy. Match the argument width explicitly.
    actor_path = output / "rt_actor.c"
    if actor_path.exists():
        actor_text = actor_path.read_text(encoding="utf-8", errors="strict")
        old = (
            'SoftError("\\n follower %d temp1 set to %4x, temp2 set to %4x",'
        )
        new = (
            'SoftError("\\n follower %d temp1 set to %4lx, temp2 set to %4lx",'
        )
        count = actor_text.count(old)
        if count == 1:
            actor_text = actor_text.replace(old, new, 1)
            old_args = "count, temp->x, temp->y);"
            new_args = (
                "count, (unsigned long)temp->x, "
                "(unsigned long)temp->y);"
            )
            arg_count = actor_text.count(old_args)
            if arg_count != 1:
                raise RuntimeError(
                    "rt_actor fixed-width debug arguments: expected one "
                    f"match, found {arg_count}"
                )
            actor_text = actor_text.replace(old_args, new_args, 1)
        elif count != 0:
            raise RuntimeError(
                "rt_actor fixed-width debug format: expected at most one "
                f"match, found {count}"
            )
        actor_path.write_text(actor_text, encoding="utf-8")

    # The original text editors use strcpy() to shift the remainder of a
    # string left after Backspace/Delete. Those source and destination ranges
    # overlap, which is undefined for strcpy() and is rejected by GCC's
    # -Werror=restrict. memmove() is the intended operation; include the NUL
    # terminator in the moved byte count. Patch both the normal and masked
    # password-entry versions, including Backspace paths that GCC does not
    # currently diagnose but have the same overlap.
    str_path = output / "rt_str.c"
    str_text = str_path.read_text(encoding="utf-8", errors="strict")
    for old, new, expected, label in (
        (
            "strcpy(s + cursor - 1, s + cursor);",
            "memmove(s + cursor - 1, s + cursor, strlen(s + cursor) + 1);",
            2,
            "rt_str Backspace plain buffer",
        ),
        (
            "strcpy(xx + cursor - 1, xx + cursor);",
            "memmove(xx + cursor - 1, xx + cursor, strlen(xx + cursor) + 1);",
            1,
            "rt_str Backspace masked buffer",
        ),
        (
            "strcpy(s + cursor, s + cursor + 1);",
            "memmove(s + cursor, s + cursor + 1, strlen(s + cursor + 1) + 1);",
            2,
            "rt_str Delete plain buffer",
        ),
        (
            "strcpy(xx + cursor, xx + cursor + 1);",
            "memmove(xx + cursor, xx + cursor + 1, strlen(xx + cursor + 1) + 1);",
            1,
            "rt_str Delete masked buffer",
        ),
    ):
        count = str_text.count(old)
        if count != expected:
            raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
        str_text = str_text.replace(old, new)
    str_path.write_text(str_text, encoding="utf-8")

    # Taradino normally generates this from rott/version.h.in through CMake.
    # The legacy config parser still requires ROTTVERSION (1.4 -> 14), while
    # the modern title/version paths use CMAKE_PROJECT_VERSION. Reproduce both
    # parts of the generated header for the direct libdragon Makefile build.
    (output/"version.h").write_text(
        '#ifndef VERSION_H\n#define VERSION_H\n'
        '#define ROTTMAJORVERSION 1\n'
        '#define ROTTMINORVERSION 4\n'
        '#define ROTTVERSION ((ROTTMAJORVERSION * 10) + (ROTTMINORVERSION))\n'
        '#define CMAKE_PROJECT_VERSION "2025.12.22-rott64"\n'
        '#define CMAKE_PROJECT_VERSION_MAJOR 2025\n'
        '#define CMAKE_PROJECT_VERSION_MINOR 12\n'
        '#define CMAKE_PROJECT_VERSION_PATCH 22\n'
        '#endif\n', encoding="ascii")

    marker=output/".rott64-prepared"
    marker.write_text(
        "Taradino 20251222\n"
        "ROTT64 fixed 320x200 framebuffer\n"
        "ROTTDS-derived low-memory policy with libdragon sound effects and WAV64 music\n"
        "Desktop VGA text renderer disabled on N64\n"
        "POSIX directory enumeration stubbed for fixed DragonFS data path\n",encoding="utf-8")


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument("--upstream",type=Path); p.add_argument("--output",type=Path)
    a=p.parse_args(); root=a.root.resolve(); upstream=(a.upstream or root/"vendor/taradino/source").resolve(); output=(a.output or root/"generated/rott").resolve()
    try: prepare(root,upstream,output)
    except (OSError,RuntimeError) as exc: print(f"prepare_engine.py: {exc}",file=sys.stderr); return 1
    print(f"Prepared N64 engine tree: {output}"); return 0
if __name__=="__main__": raise SystemExit(main())
