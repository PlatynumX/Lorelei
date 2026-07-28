# ROTT64 r125 — clean release + SummerCart reset exit

Baseline: exact r124 commit `5067bef8ff0cef93a8ce6b39eb416e6a29fb1d59`.

- Preserves r124's N64 load-transition scratch allocation fix.
- Removes the r116-r123 YAY load-trace calls from the active overlays.
- Removes the r123 SC64 USB trace initialization/backend.
- Keeps `n64_platform_checkpoint()` as a silent no-op for older call sites.
- Leaves `n64_platform_fatal()` and `n64_platform_ticks_ms()` unchanged.
- On N64, Main Menu -> Quit -> Yes draws `PRESS RESET TO RETURN TO` / `SUMMERCART MENU` on the already-active 320x240 display and waits for reset; it does not reinitialize video through the fatal/boot-display path.
- Desktop quit behavior remains the normal `QuitGame()` path.
- ROM/artifact names are versioned as r125; the 78,000,000-byte Dark War limit remains enforced.
