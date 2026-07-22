#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import subprocess
import tempfile
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def test_audit() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        run(
            "python3",
            "tools/audit_taradino.py",
            "tests/fixtures/taradino/rott",
            "--out",
            str(output),
        )
        report = json.loads((output / "taradino-port-audit.json").read_text())
        assert report["source_file_count"] == 2
        assert report["direct_dependency_file_count"] == 1
        assert report["candidate_platform_neutral_file_count"] == 1


def test_inventory() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        wad = output / "test.wad"
        payload = b"\x00" * 768
        directory_offset = 12 + len(payload)
        wad.write_bytes(
            struct.pack("<4sII", b"IWAD", 1, directory_offset)
            + payload
            + struct.pack("<II8s", 12, len(payload), b"PALTEST\0")
        )
        run("python3", "tools/wad_inventory.py", str(wad), "--out", str(output))
        report = json.loads((output / "test-wad-inventory.json").read_text())
        assert report["metadata"]["lump_count"] == 1
        assert report["lumps"][0]["size_hint"].startswith("possible 256")


def test_prepare_engine() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        upstream = base / "upstream"
        source = upstream / "rott"
        output = base / "prepared"
        source.mkdir(parents=True)
        fixture = ROOT / "tests/fixtures/taradino-20251222-rt_main-startup.c"
        (source / "rt_main.c").write_text(
            fixture.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (source / "rt_cfg.c").write_text(
            'int ConfigLoaded;\n'
            'void SetSoundDefaultValues(void) {}\n'
            'void SetConfigDefaultValues(void) {}\n'
            'void SetBattleDefaultValues(void) {}\n'
            'void ReadConfig(void)\n{\n    int desktop_probe = 1;\n}\n'
            'void WriteConfig(void)\n{\n    int untouched = 1;\n}\n',
            encoding="utf-8",
        )
        (source / "adlmusic.c").write_text('int desktop_adl;\n', encoding="utf-8")
        (source / "sdlmusic.c").write_text('int desktop_sdl_music;\n', encoding="utf-8")
        (source / "fx_mixer.c").write_text(
            '#include "SDL_mixer.h"\n'
            'void fx(void) { Mix_Chunk *c = Mix_LoadWAV_RW(0, 0); '
            'Mix_PlayChannelTimed(0, c, 0, -1); Mix_SetPanning(0, 255, 255); }\n',
            encoding="utf-8",
        )
        (source / "vgatext.c").write_text(
            'int vgatext_main(void) { SDL_CreateTexture(); return 0; }\n',
            encoding="utf-8",
        )
        (source / "rt_menu.c").write_text(
            'void a(char *source, int length) { while (*source && isspace(*source) && length) source++; }\n'
            'void b(char *source, int length) { while (*source && !isspace(*source) && length) source++; }\n'
            'void c(char *wordtext, int pos) { while (wordtext[pos] && isspace(wordtext[pos])) pos++; }\n'
            'void ScanForSavedGames(void) { int which; char *path; char *file; file = M_FileCaseExists(path); }\n'
            'void DeleteSave(char *filename) { unlink(filename); }\n',
            encoding="utf-8",
        )
        (source / "rt_game.c").write_text(
            'typedef struct { int dummy; } gamestorage_t;\n'
            'long CalculateSaveGameCheckSum(char *filename) { int handle = SafeOpenRead(filename); int n = filelength(handle); char b[4]; SafeRead(handle,b,n); close(handle); return 0; }\n'
            'int SaveTheGame(int num, void *game) { if (num > 15 || num < 0) Error("Illegal Saved game value=%d\\n", num); int h=SafeOpenWrite("rottgam0.rot"); SafeWrite(h,game,4); close(h); h=SafeOpenAppend("rottgam0.rot"); SafeWrite(h,game,4); close(h); return 1; }\n'
            'int LoadTheGame(int num, void *game) { if (num > 15 || num < 0) Error("Illegal Load game value=%d\\n", num); void *b; LoadFile("rottgam0.rot",&b); return 1; }\n'
            'void GetSavedMessage(int num, char *message) { void *b = 0; int n = LoadFile(\"rottgam0.rot\", &b); if (n > 0 && message) message[0] = 0; (void)num; }\n'
            'void GetSavedHeader(int num, gamestorage_t *game) { void *b = 0; (void)LoadFile(\"rottgam0.rot\", &b); (void)num; (void)game; }\n'
            'int GetLevel(int episode, int mapon) { return episode + mapon; }\n',
            encoding="utf-8",
        )
        (source / "rt_util.c").write_text(
            '#include <ctype.h>\n'
            'int a(char *parm) { return isalpha(*parm); }\n'
            'int b(char *parm, int length) { while ((!isalpha(*parm)) && (length > 0)) { parm++; length--; } return 0; }\n',
            encoding="utf-8",
        )
        (source / "rt_sound.c").write_text(
            'int SD_Startup(int bombonerror)\n'
            '{\n'
            '    int status;\n'
            '    int i;\n'
            '    if (SD_Started == true) { SD_Shutdown(); }\n'
            '    if (FXMode < 0 || FXMode > 1) { FXMode = 1; }\n'
            '    if (FXMode == 0) { return (0); }\n'
            '    soundstart = W_GetNumForName("digistrt") + 1;\n'
            '    soundtype = fx_digital;\n'
            '    if (SoundsRemapped == false)\n'
            '    {\n'
            '        for (i = 0; i < SD_LASTSOUND; i++)\n'
            '        {\n'
            '            int snd;\n'
            '            snd = sounds[i].snds[fx_digital];\n'
            '            if (snd >= 0)\n'
            '            {\n'
            '                sounds[i].snds[fx_digital] =\n'
            '                    W_GetNumForName(W_GetNameForNum(snd + soundstart));\n'
            '            }\n'
            '        }\n'
            '        SoundsRemapped = true;\n'
            '    }\n'
            '    soundstart = 0;\n'
            '    remotestart = W_GetNumForName("remostrt") + 1;\n'
            '    status = FX_Init();\n'
            '    if (status != FX_Ok) { return (status); }\n'
            '    FX_SetCallBack(SD_MakeCacheable);\n'
            '    SD_Started = true;\n'
            '    FX_SetVolume(FXvolume);\n'
            '    return (0);\n'
            'int SoundNumber(int x)\n'
            '{\n'
            '    if ((x >= SD_REMOTEM1SND) && (x <= SD_REMOTEM10SND))\n'
            '    {\n'
            '        return remotestart + x - SD_REMOTEM1SND;\n'
            '    }\n'
            '    return sounds[x].snds[soundtype] + soundstart;\n'
            '}\n'
            '}\n',
            encoding="utf-8",
        )
        (source / "rt_net.c").write_text(
            'void n(void) { SoftError("x=%4x y=%4x a=%4x time=%5d\\n", player->x,\n'
            '                         player->y, player->angle, oldpolltime); }\n',
            encoding="utf-8",
        )
        (source / "rt_actor.c").write_text(
            'typedef long fixed;\n'
            'typedef struct { fixed x, y; } actor_t;\n'
            'void a(actor_t *temp, int count) {\n'
            '    SoftError("\\n follower %d temp1 set to %4x, temp2 set to %4x",\n'
            '              count, temp->x, temp->y);\n'
            '}\n',
            encoding="utf-8",
        )
        (source / "rt_str.c").write_text(
            '#include <string.h>\n'
            'void normal(char *s, int cursor) {\n'
            '    strcpy(s + cursor - 1, s + cursor);\n'
            '    strcpy(s + cursor, s + cursor + 1);\n'
            '}\n'
            'void normal2(char *s, int cursor) {\n'
            '    strcpy(s + cursor - 1, s + cursor);\n'
            '    strcpy(s + cursor, s + cursor + 1);\n'
            '}\n'
            'void masked(char *xx, int cursor) {\n'
            '    strcpy(xx + cursor - 1, xx + cursor);\n'
            '    strcpy(xx + cursor, xx + cursor + 1);\n'
            '}\n',
            encoding="utf-8",
        )
        run(
            "python3", "tools/prepare_engine.py",
            "--upstream", str(upstream), "--output", str(output),
        )
        main = (output / "rt_main.c").read_text()
        assert "int main(void)" in main
        assert "rott64_argv" in main
        assert "n64_platform_init();" in main
        assert "NoSound = false;" in main
        assert "SetRottScreenRes(320, 200);" in main
        assert "T07: entered Taradino main" in main
        assert "T10: before PopulateEpisodeMenu" in main
        assert "T19: before SetupWads" in main
        assert "T30: entering VGA plane mode" in main
        assert main.count("n64_platform_checkpoint(") == 24
        assert main.count("T28: before messages") == 1
        assert main.count("InitializeMessages();") == 3
        cfg = (output / "rt_cfg.c").read_text()
        assert "SetSoundDefaultValues();" in cfg
        assert "SetConfigDefaultValues();" in cfg
        assert "SetBattleDefaultValues();" in cfg
        assert "ConfigLoaded = true;" in cfg
        assert not (output / "adlmusic.c").exists()
        assert not (output / "sdlmusic.c").exists()
        fx = (output / "fx_mixer.c").read_text()
        assert "Mix_LoadWAV_RW" in fx
        assert "Mix_PlayChannelTimed" in fx
        assert "Mix_SetPanning" in fx
        music = (output / "dukemusc.c").read_text()
        assert "wav64_open" in music
        assert "MUSIC_SetSongTime" in music
        assert (output / "dirent.h").is_file()
        dirent = (output / "dirent.h").read_text()
        assert "ROTT64_N64_DIRENT_H" in dirent
        assert "static inline DIR *opendir" in dirent
        vgatext = (output / "vgatext.c").read_text()
        assert "ROTT64 replacement for Taradino's desktop VGA text renderer" in vgatext
        assert "SDL_CreateTexture" not in vgatext
        game = (output / "rt_game.c").read_text()
        assert '#include "rott64_flash_save.h"' in game
        assert "#define SafeOpenWrite rott64_save_open_write" in game
        assert "if (num != 0) return false;" in game
        game = (output / "rt_game.c").read_text()
        assert "GetSavedMessage" in game
        assert "GetSavedHeader" in game
        assert game.count("#define LoadFile rott64_save_load_file") >= 3
        owner_report = (output.parent / "reports" / "r45c-save-reader-owners.txt").read_text()
        assert "GetSavedMessage=rt_game.c" in owner_report
        assert "GetSavedHeader=rt_game.c" in owner_report
        menu = (output / "rt_menu.c").read_text()
        assert menu.count("isspace((unsigned char)*source)") == 2
        assert "isspace((unsigned char)wordtext[pos])" in menu
        util = (output / "rt_util.c").read_text()
        assert util.count("isalpha((unsigned char)*parm)") == 2
        assert "isalpha(*parm)" not in util
        run(
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-Werror=char-subscripts", "-c", str(output / "rt_util.c"),
            "-o", str(base / "rt_util.o"),
        )
        net = (output / "rt_net.c").read_text()
        assert 'x=%4lx y=%4lx a=%4x time=%5d\\n' in net
        assert "(unsigned long)player->x" in net
        assert "(unsigned long)player->y" in net
        actor = (output / "rt_actor.c").read_text()
        assert "temp1 set to %4lx, temp2 set to %4lx" in actor
        assert "(unsigned long)temp->x" in actor
        assert "(unsigned long)temp->y" in actor
        sound = (output / "rt_sound.c").read_text()
        assert "S00: entered SD_Startup" in sound
        assert "S03: before digital sound remap" in sound
        assert "S04: remap loop completed" in sound
        assert "S00E: early sound-disabled path" in sound
        assert "S99: leaving SD_Startup" in sound
        assert "sounds[i].snds[fx_digital] =\n" in sound
        assert "W_GetNumForName(W_GetNameForNum(snd + soundstart));" in sound
        assert "=\n                    n64_platform_checkpoint" not in sound
        assert "remotestart = -1;" in sound
        assert 'W_GetNumForName("remostrt") + 1;' in sound
        assert "(remotestart >= 0)" in sound
        assert "return sounds[x].snds[soundtype] + soundstart;" in sound
        rt_str = (output / "rt_str.c").read_text()
        assert rt_str.count("memmove(s + cursor - 1, s + cursor, strlen(s + cursor) + 1);") == 2
        assert rt_str.count("memmove(s + cursor, s + cursor + 1, strlen(s + cursor + 1) + 1);") == 2
        assert "memmove(xx + cursor - 1, xx + cursor, strlen(xx + cursor) + 1);" in rt_str
        assert "memmove(xx + cursor, xx + cursor + 1, strlen(xx + cursor + 1) + 1);" in rt_str
        assert "strcpy(s + cursor" not in rt_str
        assert "strcpy(xx + cursor" not in rt_str
        run(
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-c", str(output / "rt_str.c"), "-o", str(base / "rt_str.o"),
        )
        version = (output / "version.h").read_text()
        assert "#define ROTTMAJORVERSION 1" in version
        assert "#define ROTTMINORVERSION 4" in version
        assert "#define ROTTVERSION ((ROTTMAJORVERSION * 10) + (ROTTMINORVERSION))" in version
        assert '#define CMAKE_PROJECT_VERSION "2025.12.22-rott64"' in version




def test_music_extraction_and_map() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        wad = base / "music.wad"
        out = base / "music"
        header = base / "n64_music_map_generated.h"
        midi_a = b"MThd" + b"\x00\x00\x00\x06" + b"\x00\x00\x00\x01\x00\x60"
        midi_b = b"MThd" + b"\x00\x00\x00\x06" + b"\x00\x01\x00\x02\x00\x78"
        payload = midi_a + midi_b
        directory = 12 + len(payload)
        wad.write_bytes(
            struct.pack("<4sII", b"IWAD", 2, directory)
            + payload
            + struct.pack("<II8s", 12, len(midi_a), b"RISE\0\0\0\0")
            + struct.pack("<II8s", 12 + len(midi_a), len(midi_b), b"GAZZ!\0\0\0")
        )
        run(
            "python3", "tools/extract_music.py", str(wad), str(out), str(header),
            "--mode", "any",
        )
        assert (out / "rise.mid").read_bytes() == midi_a
        assert (out / "gazz.mid").read_bytes() == midi_b
        text = header.read_text()
        assert "rott64_music_map_count = 2u" in text
        assert f"0x{zlib.crc32(midi_a) & 0xFFFFFFFF:08X}u" in text
        assert '"rom:/rott/music/rise.wav64"' in text
        report = json.loads((out / "music-map.json").read_text())
        assert [track["name"] for track in report["tracks"]] == ["RISE", "GAZZ!"]


def test_n64_posix_link_shims() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "platform/n64/posix_stubs.c" in makefile
    source = (ROOT / "platform/n64/posix_stubs.c").read_text(encoding="utf-8")
    assert "int access(" in source
    assert "char *getcwd(" in source
    assert "int chdir(" in source
    assert 'ROTT64_LOGICAL_CWD "rom://rott"' in source

def test_n64_warning_policy() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "-Wno-error=maybe-uninitialized" in makefile
    assert "-Wno-error" not in makefile.replace("-Wno-error=maybe-uninitialized", "")

def test_n64_runtime_boot_policy() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "-DDATADIR='\"rom://rott\"'" in makefile
    assert "N64_ROM_REGION = E" in makefile
    assert "N64_ROM_CATEGORY = N" in makefile
    assert "N64_ROM_ELFCOMPRESS = 0" in makefile
    platform = (ROOT / "platform/n64/n64_platform.c").read_text(encoding="utf-8")
    assert 'fopen("rom://rott/DARKWAR.WAD", "rb")' in platform
    assert 'fopen("rom://rott/DARKWAR.RTL", "rb")' in platform
    assert 'fopen("rom://rott/DARKWAR.RTC", "rb")' in platform
    assert "Stage 1/6: entered N64 main()" in platform
    assert "Stage 6/6: Dark War data found" in platform
    assert "HUNTBGIN.WAD" not in platform
    assert "ROTT64 SHAREWARE" not in platform
    # Current libdragon rejects FILTERS_DISABLED at 320px in 16bpp on NTSC hardware.
    assert "FILTERS_DISABLED" not in platform
    bootdiag = (ROOT / "platform/n64/bootdiag.c").read_text(encoding="utf-8")
    modex = (ROOT / "platform/n64/modexlib_n64.c").read_text(encoding="utf-8")
    assert "FILTERS_DISABLED" not in bootdiag
    assert "FILTERS_DISABLED" not in modex
    assert "FILTERS_RESAMPLE" in platform
    assert "FILTERS_RESAMPLE" in bootdiag
    assert "FILTERS_RESAMPLE" in modex
    for path in (ROOT / "platform/n64").glob("*.c"):
        assert "rom:/rott" not in path.read_text(encoding="utf-8")

def test_n64_audio_policy() -> None:
    mixer = (ROOT / "platform/n64/sdl_mixer_stub.c").read_text(encoding="utf-8")
    sdl = (ROOT / "platform/n64/sdl_n64.c").read_text(encoding="utf-8")
    prepare = (ROOT / "tools/prepare_engine.py").read_text(encoding="utf-8")
    preflight = (ROOT / "tools/preflight_engine.py").read_text(encoding="utf-8")

    assert "audio_init(" in mixer
    assert "mixer_init(" in mixer
    assert "mixer_poll(" in mixer
    assert "Mix_LoadWAV_RW" in mixer
    assert "Creative Voice File" in mixer
    assert "rott64_mixer_pump();" in sdl
    assert 'shutil.copy2(platform/"fx_silent.c", output/"fx_mixer.c")' not in prepare
    assert "NoSound = false;" in prepare
    assert "NoSound = true;" not in prepare
    assert 'shutil.copy2(platform/"music_wav64.c", output/"dukemusc.c")' in prepare
    assert "N64 sound effects enabled" in preflight
    assert '"SDL_Mixer"' in preflight
    assert "ignored_symbols" in preflight
    music = (ROOT / "platform/n64/music_wav64.c").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "ROTT64_MIXER_CHANNELS 9" in (ROOT / "platform/n64/rott64_audio.h").read_text()
    assert "wav64_open" in music
    assert "mixer_ch_get_pos" in music
    assert "mixer_ch_set_pos" in music
    assert "--wav-compress 1" in makefile


def test_shareware_omits_foreign_config() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        archive = base / "data.zip"
        output = base / "out"
        with zipfile.ZipFile(archive, "w") as zf:
            for name in ("HUNTBGIN.WAD", "HUNTBGIN.RTL", "HUNTBGIN.RTC"):
                zf.writestr(name, b"required")
            zf.writestr("CONFIG.ROT", b"rottds key map")
            zf.writestr("REMOTE1.RTS", b"optional")
        run("python3", "tools/prepare_shareware.py", str(archive), str(output))
        assert (output / "HUNTBGIN.WAD").is_file()
        assert (output / "REMOTE1.RTS").is_file()
        assert not (output / "CONFIG.ROT").exists()
        assert not (output / "huntbgin").exists()



def test_r45_controller_contract() -> None:
    sdl = (ROOT / "platform/n64/sdl_n64.c").read_text()
    prep = (ROOT / "tools/prepare_engine.py").read_text()
    save = (ROOT / "platform/n64/rott64_flash_save.c").read_text()

    assert "const bool menu_mode = (inmenu != 0) || (ingame == 0);" in sdl
    assert "relative_x += n64_mouse_axis(input.stick_x);" in sdl
    assert "relative_y -= n64_mouse_axis(input.stick_y);" in sdl
    assert "menu_mode && (buttons.a || buttons.z)" in sdl
    assert "menu_mode && (buttons.b || buttons.start)" in sdl
    assert "!menu_mode && buttons.c_left" in sdl
    assert "!menu_mode && buttons.c_right" in sdl
    assert "!menu_mode && buttons.r" in sdl
    assert "!menu_mode && buttons.l" in sdl
    assert "!menu_mode && buttons.d_right" in sdl
    gameplay = sdl.split("/* Gameplay:", 1)[1]
    assert "buttons.d_left" not in gameplay
    assert "buttonscan[18] = SDL_SCANCODE_BACKSPACE" in prep
    assert "buttonscan[24] = SDL_SCANCODE_M" in prep
    assert "expected one definition, found" in prep
    assert 'for function_name in ("GetSavedMessage", "GetSavedHeader")' in prep
    assert "r45c-save-reader-owners.txt" in prep
    assert "if (b != NULL) *b = NULL;" in save

if __name__ == "__main__":
    test_audit()
    test_inventory()
    test_prepare_engine()
    test_r45_controller_contract()
    test_n64_posix_link_shims()
    test_n64_warning_policy()
    test_n64_runtime_boot_policy()
    test_n64_audio_policy()
    test_music_extraction_and_map()
    test_shareware_omits_foreign_config()
    print("Taradino audit, import, shareware, and WAD inventory tests passed")


def test_n64_mixer_normalizes_over_unity_stereo_power():
    root = Path(__file__).resolve().parents[1]
    mixer = (root / "platform" / "n64" / "sdl_mixer_stub.c").read_text()
    assert "float power = left * left + right * right;" in mixer
    assert "if (power > 1.0f)" in mixer
    assert "1.0f / sqrtf(power)" in mixer
