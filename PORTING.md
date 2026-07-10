# ROTT64 port status

## Current candidate

This revision attempts the complete Taradino shareware executable rather than a
standalone WAD browser. The platform replacements are intentionally minimal:

1. N64 startup, DragonFS, timers, and Expansion Pak gate;
2. read-only data lookup under `rom:/rott`;
3. original indexed software framebuffer converted to a 16-bit N64 surface;
4. controller-generated SDL keyboard events;
5. silent audio entry points;
6. no networking and no desktop command-line/config dependency.

## Bring-up order after the first compile

Fix only the earliest failure in this order:

1. compiler and linker errors;
2. boot/DragonFS/data lookup;
3. title palette and frame presentation;
4. menu input;
5. first-map allocation and loading;
6. gameplay input and frame pacing;
7. renderer correctness;
8. sound effects;
9. saves;
10. music and optimization.

Do not add audio while the first map is unstable. Do not replace the software
renderer with an RDP rewrite before the original renderer is visibly correct.

## Memory policy

The Expansion Pak is mandatory. The initial build uses two 320x240x16 display
buffers plus one 320x200 indexed engine buffer. It avoids audio buffers and
writeable save/config state. Once a ROM boots, instrument the zone allocator and
record the free heap before and after WAD initialization and first-map loading.

## Performance policy

The first implementation converts all 64,000 source pixels on every presented
frame. Correctness comes first. Later options include a CI8/RDP upload path,
dirty-region conversion, cached palette conversion, or a lower presentation
rate while keeping game simulation timing intact.
