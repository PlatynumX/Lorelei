**Revision 14:** GitHub now validates and uploads `rott64.z64` whenever the file was produced, with a backup copy in diagnostics.

> **Runtime revision 13:** the first linked ROM was structurally valid but returned to the Android emulator list. The port had been using the incorrect DragonFS prefix `rom:/rott`; current libdragon uses `rom://rott`. This revision fixes every runtime path, adds visible boot checkpoints, sets conventional region/category metadata, and disables ELF compression for the next M64Plus FZ compatibility test.

> **Revision 12 linker fix:** the complete imported engine now compiles to objects and reaches the final N64 link. The remaining undefined symbols were `access()`, `getcwd()`, and `chdir()`. A target-local, read-only compatibility object now supplies those exact functions for the fixed `rom://rott` filesystem model.

> **Revision 11 cross-build fix:** the latest MIPS build reached `rt_util.c` and failed on two signed-`char` calls to `isalpha()`. The N64 preparation step now casts both inputs to `unsigned char`, preserving strict warning-as-error behavior.

> **Revision 10 cross-build fix:** the latest MIPS build reached `rt_str.c` and exposed overlapping `strcpy()` calls used to delete characters from menu text buffers. The N64 preparation step now converts all six normal/password Backspace and Delete shifts to `memmove()` with the terminating NUL included.

> **Revision 4 build fix:** the real preflight report showed that all remaining uncovered SDL renderer symbols came from Taradino's desktop `vgatext.c` shutdown screen. The N64 preparation step now replaces that file with a no-op instead of emulating a second 640x400 SDL renderer.

> **Revision 2:** fixes the first Android/GitHub Actions failure in the engine-preparation stage caused by Taradino's blank line before the `main()` opening brace.

> **Revision 3 build fix:** the Taradino source preparer now patches startup calls with whitespace-tolerant regular expressions. This addresses the GitHub Actions failure `force silent mode: expected one match, found 0`.

# ROTT64 shareware — first-level candidate

This repository is a serious first attempt to run **Rise of the Triad: The HUNT
Begins** on Nintendo 64 with libdragon.

The engine base is the pinned Taradino release. The port policy is informed by
ROTTDS 0.7: fixed low-resolution software rendering, console key emulation,
read-only packaged data, reduced optional subsystems, and audio postponed until
silent gameplay is stable.

## Intended result

When the cross-build succeeds, `rott64.z64` should:

1. require and detect the Expansion Pak;
2. mount the embedded shareware files at `rom://rott`;
3. start Taradino with a fixed N64 argument vector;
4. use the real ROTT startup, title, menu, map, renderer, and game logic;
5. render the original 320x200 indexed framebuffer centered in 320x240;
6. translate controller input into the keyboard events ROTT already understands;
7. run without sound or music for the first stability target;
8. allow starting and attempting the first shareware level.

This is not a claim that the ROM has been hardware-tested. The source has passed
all available host tests and static preflight checks, but this environment cannot
run the libdragon MIPS compiler or an N64 emulator. The first GitHub build may
still expose compiler API mismatches, and the first boot may reveal memory,
alignment, timing, or renderer assumptions.

## Controller layout

- Analog stick: move and turn
- C-Up/C-Down: move forward/back
- C-Left/C-Right: turn left/right
- Z: fire
- A: use/open
- B: run
- L/R: strafe left/right
- D-Up: Enter/menu confirm and weapon swap
- D-Left/D-Right: weapon slots 1/2
- D-Down: turn 180 degrees
- Start: Escape/pause/menu back

The C-button movement cluster follows the convention used by many N64 first-person
games, while preserving ROTT's existing keyboard input path. The D-pad now carries
the shortcuts previously assigned to the C-buttons.

## GitHub build

1. Extract this ZIP on a PC.
2. Upload the folder contents to a new GitHub repository, including `.github`.
3. Open **Actions**.
4. Run **Build ROTT64 first-level candidate**.
5. On success, download `rott64-shareware-first-level-candidate`.
6. On failure, download `rott64-first-level-build-diagnostics`; it contains the
   complete `n64-build.log` rather than hiding the first compiler error.

The workflow downloads the shareware data and pinned engine/reference sources at
build time. Commercial `DARKWAR.*` data is not used.

## Local build

Requirements: Docker, Git, curl, Python 3, Make, and a host C compiler.

```sh
./build.sh
```

Host-only validation:

```sh
make test-host
```

## Architecture

- `vendor/taradino/source`: fetched, pinned desktop engine source
- `vendor/rottds/source`: optional fetched DS reference source
- `generated/rott`: deterministic Taradino copy with the N64 overlay applied
- `platform/n64`: libdragon, SDL compatibility, video, input, data, and silent audio
- `filesystem/rott`: embedded shareware data prepared during the build
- `tools/preflight_engine.py`: checks that required platform substitutions exist

Read `FIRST-LEVEL-READINESS.md` before interpreting a successful compile as a
finished port.


### Revision 6 cross-build note

The first real MIPS build reached Taradino compilation and stopped because the N64 C library rejects `<dirent.h>`. Revision 6 supplies a target-local compatibility header. Directory enumeration is intentionally empty; game data discovery remains the fixed `rom://rott` path with direct file opens. This removes the exact compiler error without introducing a fake writable filesystem.
## Current cross-build status

Revision 11 compiled the full Taradino source list, the N64 platform layer, and the DragonFS image, then reached the final ELF link. The linker stopped only on missing `access()`, `getcwd()`, and `chdir()` symbols. Revision 12 supplies narrow read-only implementations for those exact calls. A successful link, ROM conversion, and boot are still unverified until the next Actions run.



## Mupen64Plus runtime isolation build (revision 16)

GitHub Actions now produces two ROMs:

- `rott64-diag.z64` — a tiny staged boot diagnostic with no Taradino engine linked.
- `rott64.z64` — the full shareware port candidate.

Test `rott64-diag.z64` first on Mupen64Plus. It displays six stages. Report the
last stage visible before an emulator crash or return to the ROM list. If the
diagnostic reaches Stage 6 and remains there, the libdragon runtime, Expansion
Pak detection, DragonFS mount, and WAD access all work in that emulator and the
remaining crash is inside Taradino startup/game initialization.


## Revision 17 build fix

Revision 16 did not reach the N64 cross-compile because a host regression test expected a slightly different Stage 4 checkpoint string. Revision 17 fixes only that mismatch; the two-ROM Mupen diagnostic strategy remains unchanged.


## Revision 18 hardware finding

A real N64 successfully entered the libdragon runtime and crash inspector. The first hardware failure was not Taradino: `display_init()` rejected `FILTERS_DISABLED` at 320x240/16bpp. Revision 18 uses `FILTERS_RESAMPLE` for every 320x240 display initialization path.


## Revision 19 Android/GitHub upload fix

GitHub Actions now invokes shell scripts with `bash` explicitly. This avoids exit code 126 (`Permission denied`) when executable permission bits are lost while moving the repository through ZIP files and Android storage.


## Revision 20: first N64 sound-effects milestone

This revision enables ROTT sound effects on top of the proven real-hardware booting branch. Taradino's original FX layer chooses sounds and applies game panning/volume; the local SDL_mixer bridge decodes the shareware Creative VOC lumps and feeds them to libdragon's mixer.

Expected hardware behavior: game/menu sound effects should play; music is still intentionally silent. Eight simultaneous FX channels are available. The one VOC using repeat markers currently plays a single pass.


## Revision 21 audio-build fix

Revision 20 stopped during preflight because the scanner interpreted the word `SDL_Mixer` in a Taradino source comment as an uncovered SDL symbol. Revision 21 corrects that scanner false positive without changing the sound-effects backend.
