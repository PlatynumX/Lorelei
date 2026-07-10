# How ROTTDS is used

ROTTDS is a reference, not the engine compiled by this repository.

Useful proven ideas carried into this candidate:

- preserve ROTT's 320x200 software-rendered frame;
- translate console controls into the engine's existing key model;
- keep the first target single-player and narrowly scoped;
- package game data in a console-friendly read-only layout;
- postpone fragile music support;
- treat memory allocation failures as a primary porting risk;
- keep video and input in small replaceable platform files.

The DS-specific ARM, libnds, DLDI, touchscreen, and modified SDL code is not
compiled for N64. Taradino remains preferable for the game code because it has
newer portability fixes, including big-endian support. The optional ROTTDS fetch
is used to generate a comparison report and preserve traceability to the console
port that established feasibility.
