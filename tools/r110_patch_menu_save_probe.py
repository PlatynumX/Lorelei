#!/usr/bin/env python3
from pathlib import Path
import sys

MARK_SCAN = "ROTT64_R110_MENU_HEADER_ONLY_SCAN"
MARK_MSG = "ROTT64_R110_MESSAGE_HEADER_ONLY"
MARK_HDR = "ROTT64_R110_PREVIEW_HEADER_ONLY"


def fail(msg: str) -> None:
    raise SystemExit("ERROR: " + msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: r110_patch_menu_save_probe.py generated/rott")

    gen = Path(sys.argv[1])
    game_path = gen / "rt_game.c"
    menu_path = gen / "rt_menu.c"

    if not game_path.is_file() or not menu_path.is_file():
        fail("generated rt_game.c/rt_menu.c not found")

    game = game_path.read_text(encoding="utf-8", errors="strict")
    menu = menu_path.read_text(encoding="utf-8", errors="strict")

    # r109 is a required baseline: this experiment intentionally changes only
    # redundant menu/header validation, not the save format or scratch fix.
    if "ROTT64_R109_ROTTDS_SAVE_SCRATCH" not in game:
        fail("r109 save-scratch baseline missing from rt_game.c")
    if "ROTT64_R109_ROTTDS_SAVE_SCRATCH" not in menu:
        fail("r109 save-scratch baseline missing from rt_menu.c")

    # Main-menu save discovery. The actual r109 generated source has exactly
    # one strict slot validation here.
    menu = replace_once(
        menu,
        "        if (ROTT64_ValidateSaveGameSlot(which, game, true))\n",
        "        /* " + MARK_SCAN + ": do not checksum the whole save while opening the menu. */\n"
        "        if (ROTT64_ValidateSaveGameSlot(which, game, false))\n",
        "ScanForSavedGames strict validation",
    )

    # Save-name read used by menu code.
    game = replace_once(
        game,
        "    if (!ROTT64_ValidateSaveGameSlot(num, game, true))\n",
        "    /* " + MARK_MSG + ": header validation only; LoadTheGame owns the full checksum. */\n"
        "    if (!ROTT64_ValidateSaveGameSlot(num, game, false))\n",
        "GetSavedMessage strict validation",
    )

    # Save screenshot/header preview when entering/highlighting the Load menu.
    game = replace_once(
        game,
        "    ROTT64_ValidateSaveGameSlot(num, game, true);\n",
        "    /* " + MARK_HDR + ": header validation only; LoadTheGame owns the full checksum. */\n"
        "    ROTT64_ValidateSaveGameSlot(num, game, false);\n",
        "GetSavedHeader strict validation",
    )

    # The safety checks that MUST remain strict.
    if game.count("ROTT64_ValidateSaveGameFile(filename, NULL, true)") != 1:
        fail("atomic post-save strict validation was changed or is missing")

    load_checksum = "checksum = DoCheckSum(loadbuffer, totalsize - sizeof(checksum), 0);"
    if game.count(load_checksum) != 1:
        fail("LoadTheGame checksum verification was changed or is missing")

    # Ensure no redundant strict slot validation survived.
    if "ROTT64_ValidateSaveGameSlot(which, game, true)" in menu:
        fail("strict menu scan survived")
    if "ROTT64_ValidateSaveGameSlot(num, game, true)" in game:
        fail("strict menu/header validation survived")

    for mark in (MARK_SCAN,):
        if menu.count(mark) != 1:
            fail(mark + " marker count is not one")
    for mark in (MARK_MSG, MARK_HDR):
        if game.count(mark) != 1:
            fail(mark + " marker count is not one")

    game_path.write_text(game.rstrip() + "\n", encoding="utf-8", newline="\n")
    menu_path.write_text(menu.rstrip() + "\n", encoding="utf-8", newline="\n")

    print("PASS:", MARK_SCAN)
    print("PASS:", MARK_MSG)
    print("PASS:", MARK_HDR)
    print("PASS: atomic post-save strict validation preserved")
    print("PASS: LoadTheGame full checksum preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
