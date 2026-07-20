#!/usr/bin/env python3
"""Fail early when the prepared source or platform overlay is incomplete."""
from __future__ import annotations
import argparse,re,sys
from pathlib import Path

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("engine",type=Path); p.add_argument("platform",type=Path); a=p.parse_args()
    required=["rt_datadir.c","rt_main.c","rt_game.c","rt_playr.c","rt_in.c","rt_vid.c","rt_cfg.c","w_wad.c","z_zone.c","modexlib.c","fx_mixer.c","SDL.h","SDL_mixer.h","dirent.h","version.h"]
    missing=[n for n in required if not (a.engine/n).is_file()]
    if missing: print("missing prepared files: "+", ".join(missing),file=sys.stderr); return 1
    main=(a.engine/"rt_main.c").read_text(errors="replace")
    checks={"N64 main entry":"int main(void)","built-in argv":"rott64_argv","platform init":"n64_platform_init();","N64 sound effects enabled":"NoSound = false;","320x200":"SetRottScreenRes(320, 200);"}
    failures=[name for name,needle in checks.items() if needle not in main]
    if "rom://rott" not in (a.engine/"rt_datadir.c").read_text(errors="replace"):
        failures.append("N64 data path")
    music=(a.engine/"dukemusc.c").read_text(errors="replace")
    for needle, label in (
        ("wav64_open", "N64 WAV64 music backend"),
        ("MUSIC_SetSongTime", "music seek support"),
        ("MUSIC_GetSongPosition", "music position support"),
        ("ROTT64_MUSIC_CHANNEL", "reserved N64 music mixer channel"),
    ):
        if needle not in music:
            failures.append(label)
    music_map_path=a.platform/"n64_music_map_generated.h"
    if not music_map_path.is_file():
        failures.append("generated N64 music map")
    else:
        music_map=music_map_path.read_text(errors="replace")
        match=re.search(r"rott64_music_map_count\s*=\s*(\d+)u", music_map)
        if not match or int(match.group(1)) < 18:
            failures.append("shareware music map (18 tracks)")

    fx=(a.engine/"fx_mixer.c").read_text(errors="replace")
    for needle, label in (
        ("Mix_LoadWAV_RW", "Taradino VOC sound loading"),
        ("Mix_PlayChannelTimed", "Taradino sound playback"),
        ("Mix_SetPanning", "Taradino stereo panning"),
    ):
        if needle not in fx:
            failures.append(label)
    dirent=(a.engine/"dirent.h").read_text(errors="replace")
    if "ROTT64_N64_DIRENT_H" not in dirent or "static inline DIR *opendir" not in dirent:
        failures.append("N64 dirent compatibility shim")
    posix_path = a.platform / "posix_stubs.c"
    if not posix_path.is_file():
        failures.append("N64 POSIX compatibility source")
    else:
        posix = posix_path.read_text(errors="replace")
        for needle, label in (
            ("int access(", "N64 access shim"),
            ("char *getcwd(", "N64 getcwd shim"),
            ("int chdir(", "N64 chdir shim"),
            ("rom://rott", "N64 logical working directory"),
        ):
            if needle not in posix:
                failures.append(label)
    vgatext=(a.engine/"vgatext.c").read_text(errors="replace")
    if "ROTT64 replacement for Taradino's desktop VGA text renderer" not in vgatext:
        failures.append("N64 VGA text replacement")
    for desktop_symbol in ("SDL_CreateTexture", "SDL_GetRenderer", "SDL_RenderPresent"):
        if desktop_symbol in vgatext:
            failures.append(f"desktop VGA text renderer still references {desktop_symbol}")
    version=(a.engine/"version.h").read_text(errors="replace")
    for needle, label in (
        ("#define ROTTMAJORVERSION 1", "ROTT major config version"),
        ("#define ROTTMINORVERSION 4", "ROTT minor config version"),
        ("#define ROTTVERSION", "ROTT config version macro"),
        ("#define CMAKE_PROJECT_VERSION", "Taradino project version"),
    ):
        if needle not in version:
            failures.append(label)
    cfg=(a.engine/"rt_cfg.c").read_text(errors="replace")
    for needle, label in (
        ("SetSoundDefaultValues();", "read-only sound defaults"),
        ("SetConfigDefaultValues();", "read-only control defaults"),
        ("SetBattleDefaultValues();", "read-only battle defaults"),
        ("ConfigLoaded = true;", "read-only config completion"),
    ):
        if needle not in cfg:
            failures.append(label)
    for excluded in ("adlmusic.c", "sdlmusic.c"):
        if (a.engine / excluded).exists():
            failures.append(f"excluded backend still present: {excluded}")
    symbols=set()
    for f in a.engine.glob("*.c"):
        text=f.read_text(errors="replace")
        symbols.update(re.findall(r"\b(?:SDL|Mix)_[A-Za-z0-9_]+\b",text))
    declarations=(a.engine/"SDL.h").read_text()+"\n"+(a.engine/"SDL_mixer.h").read_text()+"\n"+(a.platform/"sdl_n64.c").read_text()+"\n"+(a.platform/"sdl_mixer_stub.c").read_text()
    # `SDL_Mixer` appears in an upstream Taradino comment ("let SDL_Mixer do
    # the actual sound mixing"). It is a project/library name, not an SDL symbol
    # that must be implemented by the N64 compatibility layer.
    ignored_symbols={"SDL_VERSION_ATLEAST","SDL_Mixer"}
    uncovered=sorted(s for s in symbols if s not in declarations and s not in ignored_symbols)
    if failures: print("failed engine patches: "+", ".join(failures),file=sys.stderr)
    if uncovered: print("uncovered SDL symbols:\n  "+"\n  ".join(uncovered),file=sys.stderr)
    if failures or uncovered: return 1
    print(f"Preflight passed: {len(list(a.engine.glob('*.c')))} C files, {len(symbols)} SDL/Mix symbols covered")
    return 0
if __name__=="__main__": raise SystemExit(main())
