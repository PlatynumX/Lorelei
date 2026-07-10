# Changelog

## First-level candidate — N64 FPS controls revision

- Swapped the C-button and D-pad groups: C-buttons now provide digital movement/turning, while the D-pad handles confirm, weapon shortcuts, and 180-degree turn.
- Updated both the real SDL/libdragon input backend and the host-tested controller abstraction.

## First-level candidate

- Pivoted from the WAD-browser bootstrap to the full Taradino shareware engine.
- Added an N64 `main(void)` startup and fixed built-in argument vector.
- Added DragonFS `rom:/rott` data-directory replacement.
- Added fixed 320x200 indexed software-video presentation to 320x240 RGBA5551.
- Added controller-generated keyboard events based on console ROTT controls.
- Added silent effects and music backends for the first gameplay target.
- Disabled embedded foreign configuration and initial write paths.
- Added Expansion Pak enforcement.
- Added deterministic engine preparation and stricter SDL/Mix preflight.
- Added optional ROTTDS 0.7 source comparison and documentation.
- Fixed `make clean` so it no longer deletes the prepared engine before build.
- Reworked GitHub Actions to retain full diagnostics even when cross-compilation
  fails.

## Milestone 0.5

- Added pinned Taradino source audit, WAD inventory, indexed-video conversion,
  controller mapping, and strict host tests.

## Milestone 0

- Added the libdragon ROM/data bootstrap and endian-safe WAD directory browser.
