# ROTT64 R47 HW2 — live Taradino wall spans on the N64 RDP

Retry v2 fixes the pre-push function locator so C functions with the opening brace on the following line are recognized correctly.

Parent: the R46 HW1 v4 ROM confirmed on real hardware.

HW1 proved the RDPQ framebuffer path. R47 connects that path to Taradino's
actual renderer.

Taradino still performs its normal ray casting and DrawWallPost calculations.
At the end of DrawWalls, R47 exports each visible column's ceiling/floor clip
span. The N64 presentation layer recognizes fresh gameplay-only wall data and
uses RDP fill rectangles to overlay those exact spans in diagnostic colors.

Intro, title and menus should remain normal because they do not generate a new
DrawWalls sequence.

The diagnostic runs for the first 900 live world frames, then stops and returns
to normal software presentation for an automatic A/B comparison.

R47 deliberately retains R_DrawWallColumn as a fallback. After this build proves
the geometry and screen mapping are correct on hardware, the next revision will
remove the matching CPU wall rasterization and start moving wall pixels/textures
to hardware for real performance gain.

## v3 compile-order correction

The v2 source reached and passed engine preflight, then reached the N64 compiler.

The compiler exposed one source-order issue in the generated `modexlib.c`:
`present_frame()` calls `rott64_hw2_present()` before the static helper definition.
With warnings promoted to errors, that produced an implicit declaration followed
by a conflicting static declaration.

V3 adds only a file-scope forward declaration before `present_frame()`.  The
live Taradino wall exporter and RDP diagnostic behavior are otherwise unchanged.

## v3 persistent full-version music cache

This revision also stops rebuilding the unchanged Dark War soundtrack on every
GitHub Actions run.

Two content-addressed caches are used:

- Rendered soundtrack:
  `assets/music` and `platform/n64/n64_music_map_generated.h`
  keyed by DARKWAR.WAD, extract_music.py, and render_music.sh.
  A cache hit skips installation of the heavy music preparation packages and
  skips the 34-track MIDI-to-WAV render.

- Final N64 soundtrack:
  `filesystem/rott/music`
  keyed by the same music inputs plus Makefile, which owns the WAV-to-WAV64
  conversion rules.

The rendered soundtrack is saved immediately after generation, before the
cross-compile starts. The final WAV64 cache is saved whenever those files exist,
even when a later compile step fails.

Changing the WAD or music conversion logic changes the key automatically and
forces one fresh generation.
