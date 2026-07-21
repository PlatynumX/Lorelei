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

    # R41d startup tracing synchronized to Taradino 20251222.
    # First isolate the main() function, then match startup calls only there.
    # main() signature formatting is deliberately whitespace-tolerant.
    main_match = re.search(
        r"(?ms)^[ \t]*int[ \t]+main[ \t]*\([^)]*\)[ \t\r\n]*\{",
        text,
    )
    if not main_match:
        raise RuntimeError("R41d startup trace: could not locate main()")

    brace_start = text.rfind("{", main_match.start(), main_match.end())
    if brace_start == -1:
        raise RuntimeError("R41d startup trace: main() opening brace missing")

    depth = 0
    brace_end = None
    for pos in range(brace_start, len(text)):
        ch = text[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                brace_end = pos + 1
                break
    if brace_end is None:
        raise RuntimeError("R41d startup trace: main() closing brace missing")

    main_text = text[main_match.start():brace_end]

    trace_specs = (
        ("T08: before GetPrefDir", r"(?m)^(?P<i>[ \t]*)ApogeePath\s*=\s*GetPrefDir\(\)\s*;"),
        ("T09: before product/map detection", r"(?m)^(?P<i>[ \t]*)gamestate\.Version\s*=\s*ROTTVERSION\s*;"),
        ("T10: before PopulateEpisodeMenu", r"(?m)^(?P<i>[ \t]*)PopulateEpisodeMenu\s*\(\s*datadir\s*\)\s*;"),
        ("T11: before DrawRottTitle", r"(?m)^(?P<i>[ \t]*)DrawRottTitle\s*\(\s*\)\s*;"),
        ("T12: before StartupSoftError", r"(?m)^(?P<i>[ \t]*)StartupSoftError\s*\(\s*\)\s*;"),
        ("T13: before command-line setup", r"(?m)^(?P<i>[ \t]*)CheckCommandLineParameters\s*\(\s*\)\s*;"),
        ("T14: before Z_Init", r"(?m)^(?P<i>[ \t]*)Z_Init\s*\(\s*50000\s*,\s*1000000\s*\)\s*;"),
        ("T15: before IN_Startup", r"(?m)^(?P<i>[ \t]*)IN_Startup\s*\(\s*\)\s*;"),
        ("T16: before game commands", r"(?m)^(?P<i>[ \t]*)InitializeGameCommands\s*\(\s*\)\s*;"),
        ("T17: before ReadConfig", r"(?m)^(?P<i>[ \t]*)ReadConfig\s*\(\s*\)\s*;"),
        ("T18: before ReadSETUPFiles", r"(?m)^(?P<i>[ \t]*)ReadSETUPFiles\s*\(\s*\)\s*;"),
        ("T19: before SetupWads", r"(?m)^(?P<i>[ \t]*)SetupWads\s*\(\s*\)\s*;"),
        ("T20: before BuildTables", r"(?m)^(?P<i>[ \t]*)BuildTables\s*\(\s*\)\s*;"),
        ("T21: before GetMenuInfo", r"(?m)^(?P<i>[ \t]*)GetMenuInfo\s*\(\s*\)\s*;"),
        ("T22: before screen resolution", r"(?m)^(?P<i>[ \t]*)SetRottScreenRes\s*\(\s*320\s*,\s*200\s*\)\s*;"),
        ("T23: before FX setup", r"(?m)^(?P<i>[ \t]*)status2\s*=\s*SD_SetupFXCard\s*\(\s*\)\s*;"),
        ("T24: before SD_Startup", r"(?m)^(?P<i>[ \t]*)SD_Startup\s*\(\s*false\s*\)\s*;"),
        ("T25: before MU_Startup", r"(?m)^(?P<i>[ \t]*)MU_Startup\s*\(\s*false\s*\)\s*;"),
        ("T26: before Init_Tables", r"(?m)^(?P<i>[ \t]*)Init_Tables\s*\(\s*\)\s*;"),
        ("T27: before RNG", r"(?m)^(?P<i>[ \t]*)InitializeRNG\s*\(\s*\)\s*;"),
        ("T28: before messages", r"(?m)^(?P<i>[ \t]*)InitializeMessages\s*\(\s*\)\s*;"),
        ("T29: before color map", r"(?m)^(?P<i>[ \t]*)LoadColorMap\s*\(\s*\)\s*;"),
        ("T30: entering VGA plane mode", r"(?m)^(?P<i>[ \t]*)VL_SetVGAPlaneMode\s*\(\s*\)\s*;"),
    )

    for label, pattern in trace_specs:
        matches = list(re.finditer(pattern, main_text))
        if len(matches) != 1:
            raise RuntimeError(
                f"R41d startup trace {label!r}: expected one match "
                f"inside main(), found {len(matches)}"
            )
        match = matches[0]
        indent = match.group("i")
        statement = match.group(0).lstrip(" \t")
        replacement = (
            f'{indent}n64_platform_checkpoint("{label}");\n'
            f"{indent}{statement}"
        )
        main_text = main_text[:match.start()] + replacement + main_text[match.end():]

    text = text[:main_match.start()] + main_text + text[brace_end:]

    main_path.write_text(text,encoding="utf-8")

    # R42: trace inside SD_Startup() itself. R41d hardware reached T24 and
    # black-screened before T25, proving the failure occurs within
    # SD_Startup(false). Locate the actual definition dynamically.
    sd_defs = []
    sd_def_pattern = re.compile(
        r"(?m)^[ \t]*(?:void|int|boolean)[ \t]+SD_Startup[ \t]*"
        r"\([^;{}]*\)[ \t\r\n]*\{"
    )

    for sd_path in output.glob("*.c"):
        sd_text = sd_path.read_text(encoding="utf-8", errors="strict")
        for match in sd_def_pattern.finditer(sd_text):
            sd_defs.append((sd_path, sd_text, match))

    if len(sd_defs) != 1:
        raise RuntimeError(
            "R42 SD_Startup trace: expected one function definition, "
            f"found {len(sd_defs)}"
        )

    sd_path, sd_text, sd_match = sd_defs[0]
    sd_brace_start = sd_text.rfind("{", sd_match.start(), sd_match.end())
    if sd_brace_start < 0:
        raise RuntimeError("R42 SD_Startup trace: opening brace missing")

    sd_depth = 0
    sd_brace_end = None
    for sd_pos in range(sd_brace_start, len(sd_text)):
        sd_ch = sd_text[sd_pos]
        if sd_ch == "{":
            sd_depth += 1
        elif sd_ch == "}":
            sd_depth -= 1
            if sd_depth == 0:
                sd_brace_end = sd_pos + 1
                break
    if sd_brace_end is None:
        raise RuntimeError("R42 SD_Startup trace: closing brace missing")

    sd_func = sd_text[sd_match.start():sd_brace_end]

    local_brace = sd_func.find("{")
    sd_func = (
        sd_func[:local_brace + 1]
        + '\n n64_platform_checkpoint("S00: entered SD_Startup");'
        + sd_func[local_brace + 1:]
    )

    call_line = re.compile(
        r"(?m)^(?P<i>[ \t]*)(?P<line>"
        r"(?:(?:[A-Za-z_][A-Za-z0-9_]*[ \t]*=[ \t]*)?)"
        r"(?P<fn>[A-Za-z_][A-Za-z0-9_]*)[ \t]*"
        r"\([^;\n]*\)[ \t]*;[ \t]*)$"
    )
    excluded = {
        "if", "for", "while", "switch", "return", "sizeof",
        "n64_platform_checkpoint",
    }

    trace_map = []
    checkpoint_no = 1
    cursor = 0
    rebuilt = []
    for call_match in call_line.finditer(sd_func):
        fn = call_match.group("fn")
        if fn in excluded:
            continue
        rebuilt.append(sd_func[cursor:call_match.start()])
        indent = call_match.group("i")
        statement = call_match.group("line").lstrip(" \t")
        label = f"S{checkpoint_no:02d}: before {fn}"
        rebuilt.append(
            f'{indent}n64_platform_checkpoint("{label}");\n'
            f"{indent}{statement}"
        )
        trace_map.append(f"{label} :: {statement.strip()}")
        cursor = call_match.end()
        checkpoint_no += 1

    rebuilt.append(sd_func[cursor:])
    sd_func = "".join(rebuilt)

    final_close = sd_func.rfind("}")
    sd_func = (
        sd_func[:final_close]
        + '\n n64_platform_checkpoint("S99: leaving SD_Startup");\n'
        + sd_func[final_close:]
    )

    if "n64_platform_checkpoint(const char *message)" not in sd_text:
        sd_text = (
            '#ifdef __N64__\n'
            'extern void n64_platform_checkpoint(const char *message);\n'
            '#endif\n'
            + sd_text
        )
        rematch = sd_def_pattern.search(sd_text)
        if not rematch:
            raise RuntimeError(
                "R42 SD_Startup trace: definition lost after declaration"
            )
        prefix_start = rematch.start()
        brace_start2 = sd_text.rfind("{", rematch.start(), rematch.end())
        depth2 = 0
        brace_end2 = None
        for pos2 in range(brace_start2, len(sd_text)):
            ch2 = sd_text[pos2]
            if ch2 == "{":
                depth2 += 1
            elif ch2 == "}":
                depth2 -= 1
                if depth2 == 0:
                    brace_end2 = pos2 + 1
                    break
        if brace_end2 is None:
            raise RuntimeError(
                "R42 SD_Startup trace: rematched closing brace missing"
            )
        sd_text = sd_text[:prefix_start] + sd_func + sd_text[brace_end2:]
    else:
        sd_text = (
            sd_text[:sd_match.start()]
            + sd_func
            + sd_text[sd_brace_end:]
        )

    sd_path.write_text(sd_text, encoding="utf-8")

    report_dir = output.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "r42-sd-startup-trace-map.txt").write_text(
        f"source={sd_path.name}\n"
        f"call_checkpoints={len(trace_map)}\n"
        + "\n".join(trace_map)
        + "\nS99: leaving SD_Startup\n",
        encoding="utf-8",
    )


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
