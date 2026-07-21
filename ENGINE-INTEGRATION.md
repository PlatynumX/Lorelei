## Runtime revision 13

The first completed ROM exited back to the Android emulator list. Direct source inspection found the DragonFS root was wrong: `rom:/rott` instead of `rom://rott`. Revision 13 corrects all paths, verifies `DARKWAR.WAD` with a direct boot-time open, displays four early checkpoints, sets region/category metadata, and disables ELF compression for the next compatibility build.

# Engine integration contract

## Preserved from Taradino

- startup and menu flow;
- shareware restrictions;
- WAD, RTL, and RTC semantics;
- map loading and game loop;
- actors, weapons, doors, elevators, pushwalls, and triggers;
- software renderer and palette effects;
- keyboard-oriented input processing.

## Replaced for Nintendo 64

- process entry point and desktop argument assumptions;
- SDL video/window creation;
- SDL event source;
- SDL ticks and delays;
- SDL_mixer effects and music;
- writable desktop data directories;
- configuration/score writes for the initial read-only build;
- desktop file discovery;
- unsupported POSIX working-directory/existence calls through a fixed read-only shim.

## Deterministic import

`tools/prepare_engine.py` copies the pinned `rott/` source tree, applies guarded
single-match patches, overlays N64 files, removes unused desktop music sources,
and writes `.rott64-prepared`. It fails instead of guessing when the upstream
text no longer matches.

`tools/preflight_engine.py` then checks required files, entry-point patches,
resolution, silent mode, ROM path, excluded backends, and all SDL/Mix symbols
seen in the prepared C files.


### Revision 6 cross-build note

The first real MIPS build reached Taradino compilation and stopped because the N64 C library rejects `<dirent.h>`. Revision 6 supplies a target-local compatibility header. Directory enumeration is intentionally empty; game data discovery remains the fixed `rom://rott` path with direct file opens. This removes the exact compiler error without introducing a fake writable filesystem.
