# R126 — 8-bit FX prewarm + DOS startup

Baseline: exact R125 commit `cad218aa0b0e81123dfac5ece50980e34b35f106`.

## Audio/OOM changes

1. FX mixer channels 0–7 are configured for the format actually decoded by
   ROTT64: 8-bit mono.
2. `tools/rott64_scan_voc_rates.py` scans the bundled registered DARKWAR.WAD
   and generates `rott64_fx_limits_generated.h` from the real highest supported
   Creative VOC source rate. No sample-rate constant is guessed.
3. All eight FX channel samplebuffers are forced to allocate during
   `Mix_OpenAudio()`, immediately after their tight limits are installed. Each
   channel plays/stops a one-sample silent waveform; libdragon keeps the
   samplebuffer allocation after `mixer_ch_stop()`.

This directly targets the repeated hardware Inspector crash whose top frame was
`mixer_ch_play()` with `ASSERTION FAILED: Out of memory`.

## Startup presentation

The N64 boot display is retained through Taradino's existing startup checkpoint
sequence. It presents a 320x240 DOS/VGA-style screen with a blue header:

    Rise of the Triad Startup  Version 64
    Registered Version

Real completed milestones are appended below it. At T30, immediately before
`VL_SetVGAPlaneMode()`, the screen displays save status briefly and closes so
Taradino can take over the display normally. There is deliberately no
"handing off" line.

## Preserved behavior

R124 one-screen load-transition scratch allocation, R125 load-trace cleanup,
and R125 SummerCart reset exit are preserved and checked by CI.
