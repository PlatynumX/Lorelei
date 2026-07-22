# ROTT64 R46 HW1 v2 — direct RDP framebuffer proof

Baseline: exact R45d `full-version` commit `aadf56b5fbf28bb9ab88c604460df72ee6e2e701`.

The first HW1 script stopped safely before modifying `full-version` because it assumed
`platform/n64/sdl_n64.c` implemented `SDL_Flip`. R45d does not expose that function in
that form.

HW1 v2 searches the real R45d N64 sources for the actual `display_show(surface)` call and
wraps that presentation point instead.

## Hardware test

Boot the ROM normally. For the first 180 presented frames, the software image is replaced
at presentation time by a room drawn directly with libdragon RDPQ triangles into the N64
display framebuffer. The room has a dark ceiling, brown floor, red left wall, blue right
wall, gray back wall, moving brown door, and moving yellow bar.

After 180 frames it automatically returns to the untouched R45d software presentation.
No extra controller polling is introduced.

This is still a proof step: Taradino computes the software world before the presentation
hook. Once this hardware scene works on real N64 hardware, the next step is to feed actual
ROTT wall/door/floor geometry to the RDP and stop doing those pixels on the CPU.
