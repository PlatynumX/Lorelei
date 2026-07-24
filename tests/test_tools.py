

def test_r85_controls_and_menu_contract():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]

    sdl = (root / "platform" / "n64" / "sdl_n64.c").read_text(encoding="utf-8")
    controls = (root / "tools" / "r57_patch_native_buttons.py").read_text(encoding="utf-8")
    menu = (root / "tools" / "r59_stock_video_menu.py").read_text(encoding="utf-8")

    assert "ROTT64_R85_MENU_INPUT_ONLY" in sdl
    assert "update_binding(5, menu_mode && (buttons.a || buttons.z));" in sdl
    assert "(!menu_mode && buttons.start)" in sdl
    for token in (
        "update_binding(4,", "update_binding(6,", "update_binding(8,",
        "update_binding(9,", "update_binding(10,", "update_binding(11,",
        "update_binding(12,", "update_binding(13,", "update_binding(14,"):
        assert token not in sdl

    assert "buttonpoll[bt_use]" in controls
    assert "rott64_n64_buttons.a" in controls
    assert "buttonpoll[bt_swapweapon]" in controls
    assert "rott64_n64_buttons.b" in controls

    assert "ROTT64_R85_DETAIL_FILTER_MENU" in menu
    assert '"DOUBLE-CLICK SPEED"' in menu
    assert '"MENU FLIP SPEED"' in menu
    assert '"DETAIL LEVELS"' in menu
    assert '"VIOLENCE LEVEL"' in menu
    assert '"FILTER: SHARP"' in menu
    assert "Rott64DetailButtonItems" in menu
    assert "CP_Rott64VideoOptions" not in menu
    assert '"VIDEO OPTIONS"' not in menu


def test_r88e_libdragon_sd_save_contract():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    platform = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in (root / "platform" / "n64").glob("*.c")
    )
    patcher = (root / "tools" / "r88_patch_sd_saves.py").read_text(
        encoding="utf-8"
    )
    workflow = (root / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )

    assert "ROTT64_R88_LIBDRAGON_SD_SAVES" in platform
    assert 'debug_init_sdfs("sd:/", -1)' in platform
    assert "#if defined(__N64__)" in platform
    assert "Host-test stubs" in platform
    assert 'fopen(pathbuf, "wb")' in platform
    assert 'fopen(pathbuf, "rb")' in platform
    assert "rott64_n64_sd_save_root" in platform

    assert "ROTT64_R88_SD_SAVE_PATH" in patcher
    assert "ROTT64_R88_SD_MENU_GUARD" in patcher
    assert "rottgam?.rot" in patcher
    assert "M_StringJoin(ApogeePath" in patcher

    assert "tools/r88_patch_sd_saves.py" in workflow
    assert "rott64-r88e.z64" in workflow
    assert "rott64-r88e-build" in workflow

    old_base = "rott64_" + "flash_save"
    assert not (root / "platform" / "n64" / (old_base + ".c")).exists()
    assert not (root / "platform" / "n64" / (old_base + ".h")).exists()
