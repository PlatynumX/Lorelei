


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


def test_r73_video_menu_matches_taradino_types():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    menu = (root / "tools" / "r59_stock_video_menu.py").read_text(encoding="utf-8")
    assert "\x00" not in menu
    assert "CP_MenuNames Rott64VideoNames[]" in menu
    assert '{{{{ "RESOLUTION" }}}}' not in menu
    assert '{{{{ "ASPECT RATIO" }}}}' not in menu
    assert '{{{{ "FILTERING" }}}}' not in menu
    assert '{{{{ "SCREEN SIZE" }}}}' not in menu
    assert "{{2, \"\\\\0\", 'R', {{ NULL }}}}" in menu
    assert "{{1, \"\\\\0\", 'A', {{ NULL }}}}" in menu
    assert "{{1, \"\\\\0\", 'F', {{ NULL }}}}" in menu
    assert "{{1, \"\\\\0\", 'S', {{ NULL }}}}" in menu
    assert "handlewhich = OptionsItems.amount - 1;" in menu

test_r73_video_menu_matches_taradino_types()
