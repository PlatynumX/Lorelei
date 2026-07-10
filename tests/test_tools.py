#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import subprocess
import tempfile
import zipfile
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
        report = json.loads((output / "huntbgin-wad-inventory.json").read_text())
        assert report["metadata"]["lump_count"] == 1
        assert report["lumps"][0]["size_hint"].startswith("possible 256")


def test_prepare_engine() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        upstream = base / "upstream"
        source = upstream / "rott"
        output = base / "prepared"
        source.mkdir(parents=True)
        (source / "rt_main.c").write_text(
            '#include "SDL.h"\n'
            'int main(int argc, char *argv[])\n'
            '\n'
            '{\n'
            '\tCheckCommandLineParameters ( );\n'
            'SetRottScreenRes ( iGLOBAL_SCREENWIDTH , iGLOBAL_SCREENHEIGHT );\n'
            '}\n',
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
        (source / "vgatext.c").write_text(
            'int vgatext_main(void) { SDL_CreateTexture(); return 0; }\n',
            encoding="utf-8",
        )
        (source / "rt_menu.c").write_text(
            'void a(char *source, int length) { while (*source && isspace(*source) && length) source++; }\n'
            'void b(char *source, int length) { while (*source && !isspace(*source) && length) source++; }\n'
            'void c(char *wordtext, int pos) { while (wordtext[pos] && isspace(wordtext[pos])) pos++; }\n',
            encoding="utf-8",
        )
        (source / "rt_util.c").write_text(
            '#include <ctype.h>\n'
            'int a(char *parm) { return isalpha(*parm); }\n'
            'int b(char *parm, int length) { while ((!isalpha(*parm)) && (length > 0)) { parm++; length--; } return 0; }\n',
            encoding="utf-8",
        )
        (source / "rt_net.c").write_text(
            'void n(void) { SoftError("x=%4x y=%4x a=%4x time=%5d\\n", player->x,\n'
            '                         player->y, player->angle, oldpolltime); }\n',
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
        assert "NoSound = true;" in main
        assert "SetRottScreenRes(320, 200);" in main
        cfg = (output / "rt_cfg.c").read_text()
        assert "SetSoundDefaultValues();" in cfg
        assert "SetConfigDefaultValues();" in cfg
        assert "SetBattleDefaultValues();" in cfg
        assert "ConfigLoaded = true;" in cfg
        assert not (output / "adlmusic.c").exists()
        assert not (output / "sdlmusic.c").exists()
        assert (output / "dirent.h").is_file()
        dirent = (output / "dirent.h").read_text()
        assert "ROTT64_N64_DIRENT_H" in dirent
        assert "static inline DIR *opendir" in dirent
        vgatext = (output / "vgatext.c").read_text()
        assert "ROTT64 replacement for Taradino's desktop VGA text renderer" in vgatext
        assert "SDL_CreateTexture" not in vgatext
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




def test_n64_posix_link_shims() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "platform/n64/posix_stubs.c" in makefile
    source = (ROOT / "platform/n64/posix_stubs.c").read_text(encoding="utf-8")
    assert "int access(" in source
    assert "char *getcwd(" in source
    assert "int chdir(" in source
    assert 'ROTT64_LOGICAL_CWD "rom:/rott"' in source

def test_n64_warning_policy() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "-Wno-error=maybe-uninitialized" in makefile
    assert "-Wno-error" not in makefile.replace("-Wno-error=maybe-uninitialized", "")

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


if __name__ == "__main__":
    test_audit()
    test_inventory()
    test_prepare_engine()
    test_n64_posix_link_shims()
    test_n64_warning_policy()
    test_shareware_omits_foreign_config()
    print("Taradino audit, import, shareware, and WAD inventory tests passed")
