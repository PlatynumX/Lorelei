# Revision 16 — Mupen runtime isolation

- Adds `rott64-diag.z64`, a minimal staged libdragon boot diagnostic that does not link Taradino.
- Diagnostic stages test VI/display, timers, RDRAM/Expansion Pak detection, Joybus init, DragonFS, and `HUNTBGIN.WAD` access.
- Replaces full-ROM startup `console_init()` checkpoints with direct display/graphics checkpoints.
- Removes `debug_init_isviewer()` from normal startup during Android emulator testing.
- Uses `FILTERS_DISABLED` for both diagnostic and game display paths to reduce emulator-specific variables.
- GitHub Actions now uploads the diagnostic ROM separately from the full ROTT64 ROM.

# ROTT64 change log

## Artifact/workflow revision 15

- Fix GitHub Actions YAML syntax error at the ROM-validation step.
- Replace the indentation-sensitive inline Python heredoc with a YAML-safe `python3 -c` validator.
- Preserve revision 14 runtime fixes and artifact fallback behavior unchanged.

# Runtime/artifact revision 14

- Fixed GitHub Actions packaging after a successful `[Z64] rott64.z64` build.
- Validates the generated ROM by byte-order magic and minimum size.
- Uploads the ROM based on validation of the output file rather than the Docker step outcome alone.
- Includes a backup copy of `rott64.z64` in the diagnostics artifact.
- Keeps the dedicated ROM artifact small and unambiguous.

# ROTT64 change log

## Runtime revision 13 — first emulator boot diagnosis

- The first successfully linked ROM returned immediately to the Android emulator list.
- Inspection of the built source found that every DragonFS path used `rom:/rott`; current libdragon mounts its in-ROM filesystem under `rom://`, so the game could not find `HUNTBGIN.WAD` even though it was embedded.
- Corrected the data directory, SDL base/pref paths, POSIX compatibility path, tests, and preflight checks to `rom://rott`.
- Added four visible boot checkpoints: entry into N64 `main()`, DragonFS mount, Expansion Pak detection, and direct opening of `rom://rott/HUNTBGIN.WAD`.
- The temporary boot console is closed before Taradino initializes its 320x240 display.
- Added conservative ROM metadata (`N` cartridge category and `E` region) and disabled ELF compression for this compatibility test so older Mupen64Plus Android cores do not also have to exercise libdragon's compressed-ELF boot path.
- This revision is based on direct inspection of the uploaded `rott64.z64` and the source that produced it.

## Cross-build revision 12

- Revision 11 compiled every Taradino and N64 platform object and reached the final linker stage.
- The only unresolved symbols were `access`, `getcwd`, and `chdir`, which are declared by the N64 C library but not implemented.
- Added a narrow read-only POSIX compatibility object: `access()` checks files through `fopen()`, `getcwd()` reports the logical `rom://rott` data directory, and `chdir()` is a harmless no-op because all game-data paths are absolute.
- Added host runtime tests and preflight checks for all three symbols.
- This revision is based directly on the uploaded revision-11 `n64-build.log`.

## Cross-build revision 11

- Revision 10 compiled through `rt_str.c` and stopped near the end of the Taradino source list while compiling `rt_util.c`.
- Fixed both legacy `isalpha(*parm)` calls by converting the input through `unsigned char`, as required by the C ctype contract.
- This resolves the two fatal `-Werror=char-subscripts` diagnostics in `CheckParm()` and `US_CheckParm()` without weakening the compiler warning policy.
- Added deterministic preparation and host-compile regression checks for the two exact source transformations.
- This revision is based directly on the uploaded revision-10 `n64-build.log`.

## Cross-build revision 10

- Revision 9 advanced through nearly the entire Taradino C source list and stopped while compiling `rt_str.c`.
- Replaced six overlapping `strcpy()` string-shift operations in the normal and masked text editors with length-bounded `memmove()` calls that include the terminating NUL byte.
- This fixes the three fatal `-Werror=restrict` diagnostics reported for Delete and also corrects the equivalent Backspace paths before they can trigger the same undefined behavior.
- Added deterministic preparation regression tests for all six replacements.
- This revision is based directly on the uploaded `n64-build.log` from commit `c6e22b11e977d86d55b123b1b98e1c628fab499a`.

## Cross-build revision 9

- Revision 8 advanced through more of the real Taradino MIPS build and stopped in `rt_menu.c` and `rt_net.c`.
- Fixed three unsafe legacy `isspace()` calls by casting the input to `unsigned char`, which also resolves libdragon's fatal `-Wchar-subscripts` diagnostics.
- Fixed the network/debug `SoftError()` format to match the N64 build's `fixed` width (`long int`) and added explicit `unsigned long` casts for hexadecimal output.
- Added preparation regression tests for both source transformations.
- This revision is based directly on `n64-build.log` from Actions run `29102714206`.

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
- The shim makes optional directory scans return no entries while the port continues using its fixed `rom://rott` DragonFS path and direct `fopen()` lookups.
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
- Added DragonFS `rom://rott` data-directory replacement.
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
