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
- desktop file discovery.

## Deterministic import

`tools/prepare_engine.py` copies the pinned `rott/` source tree, applies guarded
single-match patches, overlays N64 files, removes unused desktop music sources,
and writes `.rott64-prepared`. It fails instead of guessing when the upstream
text no longer matches.

`tools/preflight_engine.py` then checks required files, entry-point patches,
resolution, silent mode, ROM path, excluded backends, and all SDL/Mix symbols
seen in the prepared C files.
