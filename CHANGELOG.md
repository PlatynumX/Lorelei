# ROTT64 changelog

## Revision 36 - native sequenced MIDI music

- Replaced the build-time MIDI -> WAV -> WAV64 soundtrack pipeline with a native Standard MIDI File parser and lightweight real-time sequencer/synthesizer.
- Taradino now passes original MIDI lumps directly to the N64 music backend, so shareware, registered Dark War, and compatible custom MIDI can play without pre-rendered soundtrack assets.
- Removed WAV64 soundtrack dependencies from the ROM build, eliminating the previous streaming-loop assertion path and substantially reducing soundtrack storage overhead.
- Added basic General MIDI program-family timbres, percussion/noise, channel volume/expression, sustain, pitch bend, tempo changes, pause/resume, seek, and loop restart support.
- Added a hard CI check rejecting final ROMs larger than 78 MiB.
- Retains the R35 full/custom selector, SD save path, rumble support, and prior audio fixes.

# ROTT64 revision 35 - prepare_engine fixture guard

- Fixes the R34 host-validation regression by applying the generated `rt_actor.c` ABI format patch only when `rt_actor.c` exists in the prepared source tree.
- Preserves the real N64 cross-build fix while allowing the intentionally minimal `prepare_engine.py` host-test fixture to pass.
- No runtime feature changes from R34/R33.

# ROTT64 revision 33 - host validation fix

- Fixes the R32 `-Werror=unused-variable` host-validation failure by declaring `selected_custom_index` only for N64 builds, where the custom-content selector actually uses it.
- No runtime feature changes from R32: complete Dark War soundtrack, Shareware / Full Dark War / Custom Levels selector, SD-backed native saves, safe music looping, rumble, and audio fixes are retained.

# ROTT64 revision 32 - complete Dark War soundtrack bundle

- Music build now extracts and renders all 34 recognized ROTT tracks from the bundled registered `DARKWAR.WAD`, including the 16 full-version-exclusive songs.
- Generated runtime music map includes aliases for shareware MIDI lump variants from `HUNTBGIN.WAD`, so Shareware mode and Full Dark War mode both resolve to rendered WAV64 music.
- Keeps R31 Shareware / Full Dark War / Custom Levels selector, R30 save path, R29 safe channel-level music looping, rumble, and audio fixes.
- No copyrighted rendered WAV64 files are stored in the source archive; GitHub Actions renders them during the ROM build from the user-supplied bundled WAD.

# ROTT64 revision 31 - bundled data selector

- Bundles user-supplied DARKWAR.WAD, DARKWAR.RTL, and DARKWAR.RTC in DragonFS.
- Bundles extracted custom RTL/RTC level sets in DragonFS.
- Adds boot-time Shareware / Full Dark War / Custom Levels selector.
- Custom mode provides a runtime package picker and uses the full-version resource WAD.
- Builds the non-SHAREWARE Taradino code path; the N64 data backend maps shareware filenames at runtime.
- Retains R30 SD-backed native save files, R29 manual music restart loop fix, rumble, and Expansion Pak runtime requirement.

NOTE: Full/custom mode is the first hardware integration pass and requires testing; full-version music coverage may still need expansion beyond the currently rendered shareware music set.

# ROTT64 changelog

## Revision 30 - native game save/load on flashcart SD

- Routes Taradino's writable preference/save root to `sd:/`, producing native `sd://rottgam?.rot` save files.
- Preserves Taradino's existing save serializer, slot names, Save Game menu, Load Game menu, and save-file format instead of inventing an N64-specific game-state serializer.
- Keeps immutable game data under `rom://rott`; only writable save output moves to SD.
- N64 save-slot scanning now probes exact native save filenames directly, avoiding the DragonFS-only case-insensitive directory shim.
- Allows POSIX write-access checks for the `sd:/` filesystem while keeping DragonFS read-only.
- Retains revision 29's manual music-loop restart fix, rumble support, EEPROM persistence test, and homebrew header metadata.
- Intended hardware test target: SummerCart64 (and other libdragon-supported flashcarts exposing the `sd://` filesystem).

# Revision 29 - hardware WAV64 loop crash fix + full-save integration groundwork

- Disabled libdragon WAV64 internal looping for streamed music.
- Added channel-level music restart from the normal non-blocking mixer pump,
  avoiding the hardware assertion in `wav64form_waveform_read()` at loop wrap.
- Preserves working R24 music startup, R23 near-field normalization, R26 rumble,
  and R28 EEPROM/header behavior.
- Expanded save-porting plan around Taradino's native `rottgam?.rot` serializer.
  EEPROM remains a persistence probe; full save slots will move to a larger
  cartridge-backed store after exact native slot-size measurement.

# Revision 28

- Fixed the main ROM Advanced Homebrew Header to declare the 16-Kbit EEPROM save hardware used by the revision-27 persistence backend.
- Marked the main ROM region-free for compatible homebrew loaders while retaining NTSC/E region metadata.
- Kept the diagnostic ROM free of save-hardware metadata.
- Retains revision 27 dual-record CRC32 save persistence test, revision 26 rumble behavior, and revision 24 music startup fix.
- This is the preferred combined hardware test build for header detection, EEPROM persistence, rumble, music, and near-field audio.

# Revision 27

- Folded the first N64 persistent-save test into the current rumble build.
- Added a dual-record CRC32-protected EEPROM save container.
- Added a persistent boot counter displayed during startup so hardware/emulator save persistence can be verified immediately.
- Added a 384-byte versioned payload API as the boundary for the next Taradino save-game integration step.
- Retains revision 26 rumble behavior and revision 24 music initialization fix.

# ROTT64 revision 26

- Expanded Rumble Pak feedback with distance-scaled nearby blast/damage pulses.
- Loud firing SFX immediately following Z-trigger input now upgrades recoil for heavy weapons.
- Kept sustained-fire recoil and the revision-24 working music path unchanged.
- Added `SAVE-PORTING.md` documenting the current read-only save boundary and a FlashRAM-oriented persistence plan.

# Revision 25 - N64 Rumble Pak support

- Added non-blocking Rumble Pak support through libdragon's joypad subsystem.
- Added short recoil pulses when Z fires and repeating lighter pulses during sustained fire.
- Added tactile feedback for loud, centered near-field sound effects, covering common close explosions, impacts, and damage-adjacent events without changing Taradino gameplay logic.
- Rumble automatically remains inactive when no supported rumble device is attached.
- Preserved revision 24's working WAV64 music initialization and revision 23's near-field audio normalization.

# Revision 24 — music startup-order fix

- Fixed silent music when Taradino initializes MUSIC before FX.
- `MUSIC_Init()` now bootstraps the shared SDL/libdragon mixer if it is not already active.
- Later FX initialization safely reuses the same mixer instance.
- Keeps the R23 near-field SFX normalization and all existing 22050 Hz WAV64 music parameters unchanged.

# Revision 23 — Near-field positional SFX normalization

- Keeps revision 22 streaming music and the proven real-hardware audio path.
- Fixes the N64 SDL_mixer compatibility boundary for positional sounds that are effectively immediately beside the listener.
- Preserves Taradino's requested stereo direction while applying constant-power normalization only when left/right combined output power would exceed unity.
- Leaves distant and normally panned effects unchanged.
- Leaves sample rates, the eight SFX channels, reserved music channel, music streaming, and master/channel volume parameters unchanged.
- The sustained-machine-gun issue remains separately tracked; this revision may reduce it only where near-field overdrive was contributing.

# Revision 22 — Streaming ROTT music on N64

- Keeps revision 21 sound effects and the known-good hardware boot path.
- Extracts the original ROTT MIDI lumps from `HUNTBGIN.WAD` during GitHub Actions.
- Renders MIDI offline with TiMidity/FreePats at 22050 Hz mono, following the proven ROTTDS console-port approach.
- Converts rendered tracks to libdragon WAV64/VADPCM and streams them directly from DragonFS.
- Reserves mixer channel 8 for music while sound effects remain on channels 0–7.
- Adds looping, pause/resume, independent music volume, and millisecond seek/reporting for future save-game music-position support.
- Generates the runtime MIDI-to-WAV64 map from the actual WAD using CRC32 and size, so the same pipeline can later target the registered `DARKWAR.WAD`.
- Music fades are immediate in this first milestone; smooth fades can be added after hardware validation.
- The sustained-machine-gun sound issue remains a known SFX issue and is intentionally deferred.

# Revision 21 — Audio preflight false-positive fix

- Fixes `Run engine preflight` failing with `uncovered SDL symbols: SDL_Mixer`.
- `SDL_Mixer` is only text in an upstream Taradino comment, not a callable SDL symbol.
- Adds `SDL_Mixer` to the preflight scanner's explicit non-symbol ignore set.
- Adds a regression check for this exact false positive.
- The revision 20 libdragon sound-effects implementation is otherwise unchanged.

# Revision 20 — First real N64 sound-effects build

- Keeps revision 19 as the proven real-hardware boot baseline.
- Enables Taradino's real `fx_mixer.c` instead of the silent FX shim.
- Adds an SDL_mixer compatibility backend implemented with libdragon `audio` + `mixer`.
- Decodes ROTT Creative VOC sound lumps directly from WAD memory.
- Supports VOC type 1, type 2 continuation, and type 9 unsigned 8-bit PCM.
- Converts VOC audio to signed 8-bit PCM for libdragon playback.
- Supports 8 simultaneous FX channels, stereo panning, channel volume, and master volume.
- Pumps all writable libdragon audio buffers during SDL polling/delays and primes the queue at startup.
- Music remains intentionally silent for this milestone.
- Pitch shifting remains a no-op, matching Taradino's SDL_mixer FX path.
- VOC repeat markers are accepted but not looped yet; the looping missile sound plays one pass.

# Revision 19 — GitHub shell permission fix

- Fixes GitHub Actions failing at `Fetch shareware episode` with exit code 126 / `Permission denied`.
- Invokes repository shell scripts through `bash` explicitly so ZIP/Android uploads do not depend on executable permission bits being preserved.
- Keeps all revision 18 real-hardware display fixes unchanged.

# Revision 18 — Real-hardware VI filter fix

- Real N64 hardware booted the diagnostic ROM and entered libdragon's crash inspector.
- The crash was the `res.width > 320` assertion in `display_init()` because current libdragon forbids `FILTERS_DISABLED` for 16-bit display widths of 320 pixels or less on NTSC hardware.
- Replaces `FILTERS_DISABLED` with `FILTERS_RESAMPLE` in the diagnostic display, full-ROM startup checkpoints, and Taradino framebuffer display.
- Adds host regression checks preventing this invalid 320x240 filter combination.
- No Taradino gameplay logic changed.

# Revision 17 — Host validation fix

- Fixes the revision 16 checkpoint/test string mismatch that caused `make test-host` to fail before any N64 build began.
- The runtime checkpoint now reads `Stage 4/4: shareware WAD found`, matching the regression test.
- No N64 runtime behavior is otherwise changed from revision 16.

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

## Revision 34

- Fixed the N64 cross-build failure in `rt_actor.c` by patching Taradino's generated `T_SnakePath` debug format to use `%lx` with explicit `unsigned long` casts for `fixed` coordinates.
- Applies the fix in `tools/prepare_engine.py`, so clean GitHub Actions builds retain it when regenerating the engine tree.
- No gameplay/content changes from R33.
