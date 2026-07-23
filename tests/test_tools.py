


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
