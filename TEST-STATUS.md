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
