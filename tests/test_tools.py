


def test_r69_video_menu_cp_menunames_storage_contract():
    root = Path(__file__).resolve().parents[1]
    menu = (root / "tools" / "r59_stock_video_menu.py").read_text(encoding="utf-8")
    assert "CP_MenuNames Rott64VideoNames[]" in menu
    assert "Rott64VideoResolutionName" not in menu
    assert "Rott64VideoAspectName" not in menu
    assert "Rott64VideoFilterName" not in menu
    assert "Rott64VideoScreenName" not in menu
    assert "snprintf(Rott64VideoNames[0], sizeof(Rott64VideoNames[0])," in menu
    assert "snprintf(Rott64VideoNames[3], sizeof(Rott64VideoNames[3])," in menu

def test_r83_fixed_4x3_and_b_swap_contract():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]

    controls = (root / "tools" / "r57_patch_native_buttons.py").read_text(encoding="utf-8")
    menu = (root / "tools" / "r59_stock_video_menu.py").read_text(encoding="utf-8")

    platforms = []
    for p in (root / "platform" / "n64").rglob("*.c"):
        s = p.read_text(encoding="utf-8", errors="replace")
        if "ROTT64_STOCK_VIDEO_OPTIONS_BACKEND_R59" in s:
            platforms.append(s)
    assert len(platforms) == 1
    platform = platforms[0]

    assert "ROTT64_R83_STRETCH_320X200_TO_320X240" in platform
    assert "return RESOLUTION_320x240;" in platform
    assert "rott64_r83_present_4x3(" in platform
    assert "source_y = (y * 200) / 240" in platform

    assert '"FILTERING"' in menu
    assert 'Rott64VideoItems = {{ 20, MENU_Y, 1,' in menu
    assert 'rott64_video_r59_cycle_resolution' not in menu
    assert '"RESOLUTION"' not in menu

    assert "buttonpoll[bt_use]" in controls
    assert "rott64_n64_buttons.a" in controls
    assert "buttonpoll[bt_swapweapon]  |= rott64_n64_buttons.b" in controls
    assert "buttonpoll[bt_run]         |= rott64_n64_buttons.b" not in controls
