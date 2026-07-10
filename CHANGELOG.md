# Changelog

## Android build-fix revision 4

- Replaced Taradino's desktop-only `vgatext.c` with a tiny N64 no-op implementation.
- Removes the exact SDL renderer/texture/surface API set reported by the real `preflight.log`.
- Added regression coverage proving the desktop VGA text renderer is overwritten during engine preparation.
- This fix is based on the uploaded preflight report rather than another source-format assumption.

## Android build-fix revision 3

- Fixed the Taradino preparation step to match the real upstream whitespace around `CheckCommandLineParameters()` instead of requiring exactly four leading spaces.
- Made the fixed 320x200 resolution patch whitespace-tolerant for the same reason.
- Added a regression test using tabbed and spaced call syntax so this preparation failure cannot silently return.
- Keeps all revision-2 diagnostics improvements and N64 FPS controls.

## Android build-fix revision 2

- Fixed the Taradino `main()` patcher to accept the upstream formatting where a blank line appears between the function signature and opening brace.
- Added a regression test using that exact formatting.
- GitHub Actions now saves `prepare-engine.log` and `preflight.log`, so failures before cross-compilation still produce a downloadable diagnostics artifact.


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
