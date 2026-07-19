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
