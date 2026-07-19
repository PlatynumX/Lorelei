# ROTT64 save porting

## Revision 30: native Taradino saves enabled

ROTT64 now points Taradino's writable preference/save directory at libdragon's flashcart SD filesystem (`sd:/`). The engine therefore uses its existing `ROTTGAM?.ROT` serializer and loader unchanged. Save Game and Load Game should operate on real persistent files on the SD card, preserving the original slot format.

This deliberately avoids Controller Pak storage for full game saves: observed native ROTT save files are roughly 58-67 KiB, while a standard Controller Pak has only 32 KiB total capacity. The small EEPROM backend from revisions 27-29 remains available for future compact settings/high-score data, but it is not used to hold full game-state files.

Hardware test procedure:
1. Start a new game and reach a recognizable location.
2. Open Save Game and write slot 0 with a recognizable name.
3. Return to play, then reset or power-cycle the console.
4. Reopen Load Game and confirm the slot name appears.
5. Load it and verify player position, health, weapons, enemies, doors, and map state restore correctly.

# ROTT64 save-porting status — revision 27

Revision 27 folds the first persistent-storage test into the rumble test ROM.

## What this revision does

- Detects cartridge EEPROM through libdragon at boot.
- Maintains two alternating versioned save records with CRC32 validation.
- Increments and persists a boot counter so persistence is directly visible on
  the N64 startup screen after a power cycle/reload.
- Exposes a 384-byte payload API for the next stage of engine integration.
- Does not yet claim full ROTT `ROTTGAM*.ROT` save-slot compatibility.

The boot screen reports either `EEPROM save storage OK - boot N` or that save
storage is unavailable. A second boot showing a larger N proves that the
cartridge/emulator save medium survives resets.

## Why this is staged

DragonFS is read-only. Taradino's original game-save files are larger and more
complex than a configuration flag, so revision 27 first validates reliable N64
persistent storage before serializing live engine state into it. The two-record
layout is deliberately power-loss tolerant: the newest valid generation wins.

The next save milestone is to trace Taradino's ROTTGAM serialization, measure an
actual shareware save slot, then choose between compact cartridge storage and a
larger native N64 save medium without changing the public save API introduced
here.


## Revision 29: full-save integration path

Revision 29 keeps the EEPROM persistence probe intact while beginning the real
save-game integration work. The important constraint is capacity: EEPROM16 is
only 2 KiB, which is suitable for the current boot/config probe but is not a
credible final backing store for Taradino's complete `rottgam?.rot` files.

The full implementation is therefore split into two layers:

1. Preserve Taradino's existing save serialization and slot/menu semantics.
2. Replace only the file-storage boundary with an N64 cartridge-backed blob
   store large enough for complete save files, with per-slot CRC/version data.

Before switching the declared cartridge save type, the next build-stage probe
will measure the exact byte size produced by Taradino's native serializer. That
prevents guessing between SRAM (32 KiB) and FlashRAM (128 KiB), and keeps the
shareware/full-version format compatible. The EEPROM boot counter remains a
hardware persistence test only and must not be mistaken for completed game-slot
saving.
