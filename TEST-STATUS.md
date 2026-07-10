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

The first real MIPS build reached Taradino compilation and stopped because the N64 C library rejects `<dirent.h>`. Revision 6 supplies a target-local compatibility header. Directory enumeration is intentionally empty; game data discovery remains the fixed `rom:/rott` path with direct file opens. This removes the exact compiler error without introducing a fake writable filesystem.
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
