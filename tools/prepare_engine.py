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

    # R42b: safe SD_Startup phase tracing.
    # R42's generic call-line tracer split a multiline assignment in
    # SD_Startup and caused the prior "void value not ignored" compile error.
    # This version instruments only complete statements/blocks.
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
            "R42b SD_Startup trace: expected one function definition, "
            f"found {len(sd_defs)}"
        )

    sd_path, sd_text, sd_match = sd_defs[0]
    sd_open = sd_text.rfind("{", sd_match.start(), sd_match.end())
    depth = 0
    sd_close = None
    for pos in range(sd_open, len(sd_text)):
        if sd_text[pos] == "{":
            depth += 1
        elif sd_text[pos] == "}":
            depth -= 1
            if depth == 0:
                sd_close = pos + 1
                break
    if sd_close is None:
        raise RuntimeError("R42b SD_Startup trace: closing brace missing")

    sd_func = sd_text[sd_match.start():sd_close]

    def trace_before_once(source, pattern, label, description):
        matches = list(re.finditer(pattern, source))
        if len(matches) != 1:
            raise RuntimeError(
                f"R42b {description}: expected one match, found "
                f"{len(matches)}"
            )
        m = matches[0]
        indent = re.match(r"[ \t]*", m.group(0)).group(0)
        return (
            source[:m.start()]
            + f'{indent}n64_platform_checkpoint("{label}");\n'
            + source[m.start():]
        )

    local_open = sd_func.find("{")
    sd_func = (
        sd_func[:local_open + 1]
        + '\n n64_platform_checkpoint("S00: entered SD_Startup");'
        + sd_func[local_open + 1:]
    )

    phase_specs = (
        (
            r"(?m)^[ \t]*if[ \t]*\([ \t]*SD_Started[ \t]*==[ \t]*true[ \t]*\)",
            "S01: before prior-sound shutdown check",
            "SD_Started shutdown check",
        ),
        (
            r'(?m)^[ \t]*soundstart[ \t]*=[ \t]*W_GetNumForName\("digistrt"\)[ \t]*\+[ \t]*1[ \t]*;',
            "S02: before DIGISTRT lookup",
            "DIGISTRT lookup",
        ),
        (
            r"(?m)^[ \t]*if[ \t]*\([ \t]*SoundsRemapped[ \t]*==[ \t]*false[ \t]*\)",
            "S03: before digital sound remap",
            "sound remap block",
        ),
        (
            r"(?m)^[ \t]*SoundsRemapped[ \t]*=[ \t]*true[ \t]*;",
            "S04: remap loop completed",
            "SoundsRemapped assignment",
        ),
        (
            r'(?m)^[ \t]*remotestart[ \t]*=[ \t]*W_GetNumForName\("remostrt"\)[ \t]*\+[ \t]*1[ \t]*;',
            "S05: before REMOSTRT lookup",
            "REMOSTRT lookup",
        ),
        (
            r"(?m)^[ \t]*status[ \t]*=[ \t]*FX_Init[ \t]*\([ \t]*\)[ \t]*;",
            "S06: before FX_Init",
            "FX_Init",
        ),
        (
            r"(?m)^[ \t]*if[ \t]*\([ \t]*status[ \t]*!=[ \t]*FX_Ok[ \t]*\)",
            "S07: FX_Init returned",
            "FX_Init result check",
        ),
        (
            r"(?m)^[ \t]*FX_SetCallBack[ \t]*\([ \t]*SD_MakeCacheable[ \t]*\)[ \t]*;",
            "S08: before FX callback",
            "FX callback",
        ),
        (
            r"(?m)^[ \t]*SD_Started[ \t]*=[ \t]*true[ \t]*;",
            "S09: before marking sound started",
            "SD_Started assignment",
        ),
        (
            r"(?m)^[ \t]*FX_SetVolume[ \t]*\([ \t]*FXvolume[ \t]*\)[ \t]*;",
            "S10: before FX volume",
            "FX volume",
        ),
    )

    for pattern, label, description in phase_specs:
        sd_func = trace_before_once(sd_func, pattern, label, description)

    # SD_Startup has an early zero-success path and a normal final zero return.
    # The early return may be on the same line as its `if`, so do not search
    # only for line-leading return statements. Mark the early branch by its
    # condition, then mark the final standalone return by taking the last
    # matching return statement in the function.
    early_patterns = (
        r"(?m)^(?P<i>[ \t]*)if[ \t]*\([ \t]*FXMode[ \t]*==[ \t]*0[ \t]*\)",
        r"(?m)^(?P<i>[ \t]*)if[ \t]*\([ \t]*NoSound[ \t]*\)",
    )
    early_match = None
    for early_pattern in early_patterns:
        matches = list(re.finditer(early_pattern, sd_func))
        if len(matches) == 1:
            early_match = matches[0]
            break
    if early_match is not None:
        early_indent = early_match.group("i")
        sd_func = (
            sd_func[:early_match.start()]
            + f'{early_indent}n64_platform_checkpoint("S00E: early sound-disabled path");\n'
            + sd_func[early_match.start():]
        )

    zero_returns = list(
        re.finditer(
            r"(?m)^(?P<i>[ \t]*)return[ \t]*\([ \t]*0[ \t]*\)[ \t]*;",
            sd_func,
        )
    )
    if not zero_returns:
        raise RuntimeError(
            "R42c SD_Startup final return: no standalone return (0) found"
        )

    final_return = zero_returns[-1]
    final_indent = final_return.group("i")
    final_stmt = final_return.group(0).lstrip(" \t")
    sd_func = (
        sd_func[:final_return.start()]
        + f'{final_indent}n64_platform_checkpoint("S99: leaving SD_Startup");\n'
        + f"{final_indent}{final_stmt}"
        + sd_func[final_return.end():]
    )

    if "n64_platform_checkpoint(const char *message)" not in sd_text:
        prefix = (
            '#ifdef __N64__\n'
            'extern void n64_platform_checkpoint(const char *message);\n'
            '#endif\n'
        )
        sd_text = prefix + sd_text
        rematch = sd_def_pattern.search(sd_text)
        if not rematch:
            raise RuntimeError("R42b SD_Startup definition lost after prefix")
        ropen = sd_text.rfind("{", rematch.start(), rematch.end())
        rdepth = 0
        rclose = None
        for pos in range(ropen, len(sd_text)):
            if sd_text[pos] == "{":
                rdepth += 1
            elif sd_text[pos] == "}":
                rdepth -= 1
                if rdepth == 0:
                    rclose = pos + 1
                    break
        if rclose is None:
            raise RuntimeError("R42b SD_Startup rematch closing brace missing")
        sd_text = sd_text[:rematch.start()] + sd_func + sd_text[rclose:]
    else:
        sd_text = sd_text[:sd_match.start()] + sd_func + sd_text[sd_close:]

    sd_path.write_text(sd_text, encoding="utf-8")

    # R43: Dark War registered WAD compatibility.
    #
    # The bundled registered DARKWAR.WAD has DIGISTRT but no REMOSTRT marker.
    # Upstream Taradino performs W_GetNumForName("remostrt") unconditionally,
    # which enters the fatal missing-lump path at hardware checkpoint S05.
    #
    # Keep Shareware semantics unchanged. On N64 registered builds, disable
    # the absent contiguous remote-sound block and let SoundNumber() use the
    # already-remapped registered sounds[] entry instead.
    sd_text = sd_path.read_text(encoding="utf-8", errors="strict")

    remote_lookup_pattern = re.compile(
        r'(?m)^(?P<i>[ \t]*)remotestart[ \t]*=[ \t]*'
        r'W_GetNumForName[ \t]*\([ \t]*"remostrt"[ \t]*\)'
        r'[ \t]*\+[ \t]*1[ \t]*;'
    )
    remote_matches = list(remote_lookup_pattern.finditer(sd_text))
    if len(remote_matches) != 1:
        raise RuntimeError(
            "R43 REMOSTRT lookup: expected one match, found "
            f"{len(remote_matches)}"
        )
    rm = remote_matches[0]
    indent = rm.group("i")
    replacement = (
        f"{indent}#if defined(__N64__) && (SHAREWARE == 0)\n"
        f"{indent}remotestart = -1;\n"
        f"{indent}#else\n"
        f"{indent}remotestart = W_GetNumForName(\"remostrt\") + 1;\n"
        f"{indent}#endif"
    )
    sd_text = sd_text[:rm.start()] + replacement + sd_text[rm.end():]

    # Find SoundNumber() structurally and modify only its remote-message branch.
    sound_number_pattern = re.compile(
        r"(?m)^[ \t]*int[ \t]+SoundNumber[ \t]*\([^;{}]*\)"
        r"[ \t\r\n]*\{"
    )
    sn_matches = list(sound_number_pattern.finditer(sd_text))
    if len(sn_matches) != 1:
        raise RuntimeError(
            "R43 SoundNumber definition: expected one match, found "
            f"{len(sn_matches)}"
        )

    snm = sn_matches[0]
    sn_open = sd_text.rfind("{", snm.start(), snm.end())
    depth = 0
    sn_close = None
    for pos in range(sn_open, len(sd_text)):
        if sd_text[pos] == "{":
            depth += 1
        elif sd_text[pos] == "}":
            depth -= 1
            if depth == 0:
                sn_close = pos + 1
                break
    if sn_close is None:
        raise RuntimeError("R43 SoundNumber closing brace missing")

    sn_func = sd_text[snm.start():sn_close]

    # Upstream remote branch may span several lines; add remotestart validity
    # to the branch condition without replacing its existing range checks.
    remote_if_pattern = re.compile(
        r"(?ms)(?P<head>^[ \t]*if[ \t]*\()"
        r"(?P<cond>.*?SD_REMOTEM1SND.*?SD_REMOTEM10SND.*?)"
        r"(?P<tail>\)[ \t\r\n]*\{)"
    )
    rif_matches = list(remote_if_pattern.finditer(sn_func))
    if len(rif_matches) != 1:
        raise RuntimeError(
            "R43 SoundNumber remote branch: expected one match, found "
            f"{len(rif_matches)}"
        )
    rif = rif_matches[0]
    old_cond = rif.group("cond").rstrip()
    new_cond = old_cond + " &&\n        (remotestart >= 0)"
    sn_func = (
        sn_func[:rif.start("cond")]
        + new_cond
        + sn_func[rif.end("cond"):]
    )

    sd_text = sd_text[:snm.start()] + sn_func + sd_text[sn_close:]
    sd_path.write_text(sd_text, encoding="utf-8")


    report_dir = output.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "r42b-sd-startup-trace-map.txt").write_text(
        "\n".join(
            [
                f"source={sd_path.name}",
                "S00: entered SD_Startup",
                "S01: before prior-sound shutdown check",
                "S02: before DIGISTRT lookup",
                "S03: before digital sound remap",
                "S04: remap loop completed",
                "S05: before REMOSTRT lookup",
                "S06: before FX_Init",
                "S07: FX_Init returned",
                "S08: before FX callback",
                "S09: before marking sound started",
                "S10: before FX volume",
                "S00E: early sound-disabled path",
                "S99: leaving SD_Startup",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


    cfg_path=output/"rt_cfg.c"
    text=cfg_path.read_text(encoding="utf-8",errors="strict")
    # R45d: N64 controller defaults below use SDL_SCANCODE_* constants.
    # Pinned Taradino rt_cfg.c does not include SDL.h itself. Prepend the
    # N64 compatibility header without depending on any exact upstream include
    # ordering so the real source and host fixture are both covered.
    if '#include "SDL.h"' not in text:
        text = (
            '#ifdef __N64__\n'
            '#include "SDL.h"\n'
            '#endif\n'
            + text
        )
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

    # R45: force gameplay action scancodes to match the N64 controller shim.
    cfg_text = cfg_path.read_text(encoding="utf-8", errors="strict")
    defaults_match = re.search(
        r"(?m)^[ \t]*void[ \t]+SetConfigDefaultValues[ \t]*"
        r"\([^)]*\)[ \t\r\n]*\{",
        cfg_text,
    )
    if defaults_match is None:
        raise RuntimeError("R45 SetConfigDefaultValues definition not found")
    defaults_open = cfg_text.find("{", defaults_match.start(), defaults_match.end())
    depth = 0
    defaults_close = None
    for pos in range(defaults_open, len(cfg_text)):
        if cfg_text[pos] == "{":
            depth += 1
        elif cfg_text[pos] == "}":
            depth -= 1
            if depth == 0:
                defaults_close = pos
                break
    if defaults_close is None:
        raise RuntimeError("R45 SetConfigDefaultValues closing brace missing")

    n64_bindings = (
        '\n#ifdef __N64__\n'
        '    buttonscan[0] = SDL_SCANCODE_LCTRL;      /* Fire */\n'
        '    buttonscan[2] = SDL_SCANCODE_LSHIFT;     /* Run */\n'
        '    buttonscan[3] = SDL_SCANCODE_SPACE;      /* Use */\n'
        '    buttonscan[4] = SDL_SCANCODE_I;          /* LookUp */\n'
        '    buttonscan[5] = SDL_SCANCODE_K;          /* LookDn */\n'
        '    buttonscan[6] = SDL_SCANCODE_RETURN;     /* Swap */\n'
        '    buttonscan[7] = SDL_SCANCODE_TAB;        /* Drop */\n'
        '    buttonscan[14] = SDL_SCANCODE_CAPSLOCK;  /* AutoRun */\n'
        '    buttonscan[16] = SDL_SCANCODE_COMMA;     /* StrafeLeft */\n'
        '    buttonscan[17] = SDL_SCANCODE_PERIOD;    /* StrafeRight */\n'
        '    buttonscan[18] = SDL_SCANCODE_BACKSPACE; /* VolteFace */\n'
        '    buttonscan[24] = SDL_SCANCODE_M;         /* Map */\n'
        '#endif\n'
    )
    cfg_text = cfg_text[:defaults_close] + n64_bindings + cfg_text[defaults_close:]
    cfg_path.write_text(cfg_text, encoding="utf-8")

    cfg_verify = cfg_path.read_text(encoding="utf-8", errors="strict")
    if "SDL_SCANCODE_" in cfg_verify and '#include "SDL.h"' not in cfg_verify:
        raise RuntimeError(
            "R45d rt_cfg uses SDL_SCANCODE_* without including SDL.h"
        )


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

    # R45c: Taradino 20251222 save-reader API fix.
    #
    # The pinned 20251222 public API declares GetSavedMessage() and
    # GetSavedHeader() in rt_game.h. Do not assume formatting or source-file
    # placement; locate their real definitions structurally across fetched
    # engine .c files and wrap only those functions with native reads.
    def find_named_function(name):
        pattern = re.compile(
            rf"(?m)^[ \t]*(?!#)(?P<head>[^;\n{{}}]*\b{re.escape(name)}"
            rf"[ \t]*\([^;{{}}]*\)[ \t\r\n]*)\{{"
        )
        found = []
        for candidate in sorted(output.glob("*.c")):
            candidate_text = candidate.read_text(
                encoding="utf-8", errors="strict"
            )
            for match in pattern.finditer(candidate_text):
                open_brace = candidate_text.find(
                    "{", match.start(), match.end()
                )
                depth = 0
                close_brace = None
                for pos in range(open_brace, len(candidate_text)):
                    ch = candidate_text[pos]
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            close_brace = pos + 1
                            break
                if close_brace is None:
                    raise RuntimeError(
                        f"R45c {name}: closing brace missing in "
                        f"{candidate.name}"
                    )
                found.append(
                    (candidate, candidate_text, match.start(), close_brace)
                )
        if len(found) != 1:
            owners = ", ".join(item[0].name for item in found) or "none"
            raise RuntimeError(
                f"R45c {name}: expected one definition, found "
                f"{len(found)} ({owners})"
            )
        return found[0]

    read_undefs = (
        '\n#ifdef __N64__\n'
        '#undef SafeOpenRead\n'
        '#undef SafeRead\n'
        '#undef filelength\n'
        '#undef LoadFile\n'
        '#undef close\n'
        '#endif\n'
    )

    save_reader_report = []

    # Re-scan after mutation and record exactly where the pinned source put
    # these functions.  This report travels with GitHub build diagnostics.
    report_dir = output.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

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


    # R44: route Taradino's complete save serializer into native FlashRAM.
    game_path = output / "rt_game.c"
    game_text = game_path.read_text(encoding="utf-8", errors="strict")
    getlevel_anchor = re.search(r"(?m)^[ \t]*int[ \t]+GetLevel[ \t]*\(", game_text)
    save_undefs = (
        '#ifdef __N64__\n#undef SafeOpenWrite\n#undef SafeOpenAppend\n'
        '#undef SafeOpenRead\n#undef SafeWrite\n#undef SafeRead\n'
        '#undef filelength\n#undef LoadFile\n#undef close\n#endif\n'
    )
    game_text = game_text.replace(
        'if (num > 15 || num < 0) Error("Illegal Saved game value=%d\\n", num);',
        'if (num != 0) return false;')
    game_text = game_text.replace(
        'if (num > 15 || num < 0) Error("Illegal Load game value=%d\\n", num);',
        'if (num != 0) return false;')
    game_path.write_text(game_text, encoding="utf-8")

    menu_path = output / "rt_menu.c"
    menu_text = menu_path.read_text(encoding="utf-8", errors="strict")
    old = 'file = M_FileCaseExists(path);'
    if menu_text.count(old) != 1:
        raise RuntimeError(f"R44 save scan expected one match, found {menu_text.count(old)}")
    menu_text = menu_text.replace(
        old,
        '#ifdef __N64__\n'
        '        file = (which == 0) ? rott64_save_case_exists(path) : NULL;\n'
        '#else\n        file = M_FileCaseExists(path);\n#endif',
        1)
    menu_text = menu_text.replace(
        'unlink(filename);',
        '#ifdef __N64__\n            rott64_save_unlink(filename);\n'
        '#else\n            unlink(filename);\n#endif')
    menu_path.write_text(menu_text, encoding="utf-8")

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
    try:
        prepare(root, upstream, output)
        # ROTT64_R89J_PREPARE_ENGINE_AUDIO_SILENCE_HOOK
        import subprocess as _rott64_r89j_subprocess
        import sys as _rott64_r89j_sys
        from pathlib import Path as _Rott64R89jPath
        r89j_audio_tool = _Rott64R89jPath(__file__).with_name("r89j_silence_generated_direct_audio.py")
        if r89j_audio_tool.exists():
            _rott64_r89j_subprocess.run([_rott64_r89j_sys.executable, str(r89j_audio_tool), str(output)], check=True)

    except (OSError,RuntimeError) as exc: print(f"prepare_engine.py: {exc}",file=sys.stderr); return 1
    print(f"Prepared N64 engine tree: {output}"); return 0
if __name__=="__main__": raise SystemExit(main())
