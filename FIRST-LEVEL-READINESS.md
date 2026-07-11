## Runtime revision 13

The first completed ROM exited back to the Android emulator list. Direct source inspection found the DragonFS root was wrong: `rom:/rott` instead of `rom://rott`. Revision 13 corrects all paths, verifies `HUNTBGIN.WAD` with a direct boot-time open, displays four early checkpoints, sets region/category metadata, and disables ELF compression for the next compatibility build.

# First-level readiness assessment

## What is actually wired

The build imports every Taradino C source file, removes its two desktop music
backends, and replaces these engine boundary files:

- `modexlib.c`: fixed 320x200 indexed framebuffer and libdragon presentation;
- `rt_datadir.c`: read-only `rom://rott` lookup;
- `fx_mixer.c`: silent sound-effect API;
- `dukemusc.c`: silent music API;
- `SDL.h` / `SDL_mixer.h`: narrow compatibility declarations.

Additional platform objects supply event polling, ticks, delays, startup,
Expansion Pak enforcement, DragonFS mounting, and narrow read-only replacements
for the three missing POSIX calls (`access`, `getcwd`, and `chdir`). `rt_main.c` is patched to use
`main(void)`, initialize the N64, construct a deterministic one-item argument
vector, force silent mode, and request 320x200 output.

## Why this could reach level one

The gameplay, renderer, map loading, actors, weapons, menus, WAD handling, RTL
handling, and shareware restrictions remain Taradino code. The N64 layer avoids
reimplementing them. The official shareware WAD/RTL/RTC files are embedded and
looked up with the correct case-sensitive DragonFS paths.

ROTTDS demonstrated that the ROTT engine can be adapted to a memory-constrained
Nintendo console with fixed software video and console controls. This candidate
does not copy the old ARM/DS hardware layer; it applies the same conservative
scope to Taradino's newer big-endian-capable code.

## Most likely first-build failures

1. A Taradino function signature changed from the compatibility declaration.
2. An SDL structure field or constant used indirectly was missed by preflight.
3. A desktop/POSIX function is present under a path not detected by the audit.
4. libdragon changed an API name or surface layout after this source was written.
5. Multiple upstream globals expected from the original platform files collide
   with or are absent from the replacements.

The GitHub workflow always retains the complete compiler log to make these
mechanical to fix.

## Most likely first-boot failures

1. Heap exhaustion while loading the first map despite the Expansion Pak.
2. An unaligned little-endian read not covered by Taradino's portability work.
3. A renderer pointer assumes desktop allocation or a wider native integer.
4. Event pumping does not occur frequently enough in a menu/game state.
5. A write to configuration, scores, or save data reaches an unpatched path.
6. Frame conversion is too slow and causes timing instability.

## Definition of success for this candidate

A successful test is:

- the ROM reaches the real ROTT title/menu;
- a new shareware game can be selected;
- the first map appears;
- the player can move, turn, open the first door, fire, and continue far enough
  to establish that actors, collision, map triggers, and rendering run;
- silence is expected;
- saving, networking, multiplayer, and music are not expected.

Getting all the way to the level exit would be excellent but is not assumed
without a real build and play test.


### Revision 6 cross-build note

The first real MIPS build reached Taradino compilation and stopped because the N64 C library rejects `<dirent.h>`. Revision 6 supplies a target-local compatibility header. Directory enumeration is intentionally empty; game data discovery remains the fixed `rom://rott` path with direct file opens. This removes the exact compiler error without introducing a fake writable filesystem.
