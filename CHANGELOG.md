# ROTT64 change log

## Cross-build revision 8

- Revision 7 compiled the real Taradino engine through `rt_build.c` and then stopped in `rt_cfg.c`.
- The direct libdragon build generated an incomplete `version.h`: it provided the modern CMake project version but omitted the original ROTT configuration macros.
- Recreated Taradino's generated `version.h.in` definitions for `ROTTMAJORVERSION`, `ROTTMINORVERSION`, and `ROTTVERSION`, while retaining the project-version strings.
- Added host and preflight checks so an incomplete generated version header fails before the MIPS compilation.
- This revision is based directly on `n64-build.log` from the uploaded revision-7 Actions run.

## Cross-build revision 7

- The R6 build reached compilation of the real Taradino engine and compiled more than twenty engine modules before stopping.
- The only reported failures were GCC `-Wmaybe-uninitialized` diagnostics promoted to errors by libdragon's strict warning policy.
- Demoted only `maybe-uninitialized` from fatal to nonfatal for the N64 target; the warnings remain visible and every other warning class remains fatal.
- Added a host regression check that prevents accidentally disabling warnings globally.
- This revision is based directly on `latest-full-build.log` from Actions run `29101712275`.

## Cross-build revision 6

- Added an N64-local `dirent.h` compatibility shim because libdragon/newlib explicitly does not support POSIX directory streams.
- The shim makes optional directory scans return no entries while the port continues using its fixed `rom:/rott` DragonFS path and direct `fopen()` lookups.
- The engine preparation step now copies the shim into the generated Taradino tree so `<dirent.h>` resolves before the unsupported toolchain header.
- Added preflight and host regression tests for the compatibility header.
- This change is based on the first genuine MIPS cross-compiler error from revision 5: `sys/dirent.h: #error "<dirent.h> not supported"` while compiling `byteordr.c`.

# Android build-fix revision 5

- Reached the real N64 cross-compile stage.
- Fixed CI diagnostics being deleted by the project `make clean` target.
- Removed the redundant clean from the fresh GitHub Actions checkout.
- Stores `n64-build.log` and copies earlier reports under `ci-reports/`, outside the object directory.
- This revision intentionally does not guess at the compiler error; it preserves the exact log for the next grounded fix.

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
