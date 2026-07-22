# R45b Taradino save-reader ownership fix

## What R45 got wrong

R45 assumed `GetSaveHeader()` was defined in `rt_game.c`.

The pinned Taradino 20251222 layout puts the save menu state in `rt_menu.c`
(`SaveGamesAvail`, `SaveGameNames`, and related save-menu code). The hardware
backtrace also reached `CP_PreSelectedGame -> GetSaveHeader -> LoadTag`, which
is menu-side parsing.

R45 therefore failed during `make prepare` before compilation because its
hard-coded `rt_game.c` matcher could not find the function.

## R45b fix

`prepare_engine.py` no longer assumes a source file or return type.

It structurally searches every fetched Taradino `.c` file for exactly one
definition each of:

- `LoadTag`
- `GetSaveHeader`

It finds the full function body by balanced braces, wraps only that function
with the ROTT64 native FlashRAM read API, and then removes the macros after the
function.

This preserves Taradino's own save-header/tag parsing while redirecting only
the backing file reads.

A build report records the actual owners discovered from the pinned source:

    generated/reports/r45b-save-reader-owners.txt

The host fixture now mirrors Taradino's actual split:
`rt_game.c` owns game serialization while `rt_menu.c` owns save header/menu
parsing.

All R45 controller changes, R43 REMOSTRT compatibility, audio headroom,
rumble, FlashRAM compression/CRC, and the 78,000,000-byte ROM ceiling remain.
