## Runtime revision 13

The first completed ROM exited back to the Android emulator list. Direct source inspection found the DragonFS root was wrong: `rom:/rott` instead of `rom://rott`. Revision 13 corrects all paths, verifies `HUNTBGIN.WAD` with a direct boot-time open, displays four early checkpoints, sets region/category metadata, and disables ELF compression for the next compatibility build.

# Validation status

## Passed in this package

- strict C11 host compile with `-Wall -Wextra -Werror` for the WAD parser;
- WAD header, directory, name lookup, and bounded read tests;
- indexed framebuffer and VGA-palette conversion tests;
- normalized controller mapping tests;
- SDL compatibility queue, timing, path, RWops, and mixer-stub host tests;
- Python shareware extraction, WAD inventory, source audit, deterministic
  engine-preparation tests, and desktop `vgatext.c` replacement regression test;
- shell syntax checks for all build/fetch scripts;
- Python bytecode compilation for all tools and tests;
- GitHub Actions YAML parse;
- checks for stale filesystem prefixes and obsolete milestone descriptions.

## Not performed here

- libdragon/MIPS cross-compilation;
- link of the full imported Taradino engine;
- execution in Ares or another N64 emulator;
- flashcart or real-hardware boot;
- title/menu rendering verification;
- first-map loading or gameplay verification.

The GitHub workflow is structured to turn the first missing cross-compiler symbol
or header mismatch into a downloadable `n64-build.log`. A successful workflow
produces `rott64.z64`; it does not by itself prove runtime success.

## Revision 5 CI diagnostics

The revision-4 workflow reached the Nintendo 64 cross-compile, but its own
`make clean` target deleted `build/reports/n64-build.log` before artifact
upload. Revision 5 writes persistent diagnostics to `ci-reports/` and removes
that redundant clean step. No engine/compiler fix is claimed until the actual
cross-compiler output is captured.


### Revision 6 cross-build note

The first real MIPS build reached Taradino compilation and stopped because the N64 C library rejects `<dirent.h>`. Revision 6 supplies a target-local compatibility header. Directory enumeration is intentionally empty; game data discovery remains the fixed `rom://rott` path with direct file opens. This removes the exact compiler error without introducing a fake writable filesystem.
## Revision 7

- Grounded failure: MIPS GCC emitted four `-Wmaybe-uninitialized` diagnostics while compiling `rt_build.c` and `rt_actor.c`; libdragon promoted them to errors.
- Change: only that warning class is now nonfatal for the N64 build.
- Host regression test confirms there is no blanket `-Wno-error`.
- N64 cross-build and runtime remain unverified until the next Actions run.
## Revision 8

- Grounded failure: `rt_cfg.c` could not compile because `ROTTVERSION` was undeclared in six config parsing/writing functions.
- Cause: the direct Makefile build bypasses CMake's `configure_file(rott/version.h.in, ...)`, and the replacement header included only modern project-version fields.
- Change: generate the original ROTT 1.4 config macros (`ROTTMAJORVERSION`, `ROTTMINORVERSION`, and `ROTTVERSION`) plus the Taradino project version.
- Host preparation and preflight now verify those definitions before cross-compilation.
- N64 link and runtime remain unverified until the next Actions run.

## Revision 9

- Grounded failures: `rt_menu.c` passed plain signed `char` values to `isspace()`, producing fatal `-Wchar-subscripts`; `rt_net.c` printed `fixed` (`long int`) coordinates with `%x`, producing fatal `-Wformat` diagnostics.
- Change: cast ctype inputs to `unsigned char`, use `%lx` for the fixed-width coordinates, and cast those variadic arguments to `unsigned long`.
- Host preparation tests verify all four exact transformations.
- N64 link and runtime remain unverified until the next Actions run.
## Revision 10

- Grounded failure: `rt_str.c` used overlapping `strcpy()` calls while shifting text left after Delete; MIPS GCC rejected three calls with fatal `-Werror=restrict`.
- Change: replace all six equivalent Backspace/Delete shifts across `US_LineInput()` and `US_lineinput()` with `memmove()`, moving `strlen(source) + 1` bytes so the NUL terminator is preserved.
- Host engine-preparation tests verify all six transformations and reject any remaining overlapping `strcpy()` form.
- N64 link and runtime remain unverified until the next Actions run.
## Revision 11

- Grounded failure: `rt_util.c` passed plain `char` values to `isalpha()` in `CheckParm()` and `US_CheckParm()`, producing two fatal `-Wchar-subscripts` diagnostics.
- Change: cast both ctype inputs to `unsigned char`; no warning classes were disabled.
- Host engine-preparation tests verify both transformations and compile the prepared fixture with `-Werror=char-subscripts`.
- N64 link and runtime remain unverified until the next Actions run.


## Revision 12

- Grounded failure: the full engine compiled and the final ELF link reported undefined references to `access`, `getcwd`, and `chdir`.
- Change: add a read-only N64 POSIX compatibility object implementing only those three functions for the fixed `rom://rott` data path.
- Host runtime tests verify file-existence checks, read-only rejection, logical working-directory reporting, buffer bounds, and the no-op directory change.
- The next Actions run will determine whether the ELF now links and whether a `.z64` is produced.
