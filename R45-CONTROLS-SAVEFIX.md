# R45 controls + save-header fix

Gameplay:
- Analog stick = relative mouse
- Z = fire
- A = use/open
- B = run
- C-Left / C-Right = strafe left/right
- C-Up = swap/toggle weapon
- C-Down = drop weapon
- D-pad Up / Down = look up/down
- D-pad Left = unassigned
- D-pad Right = autorun toggle
- L = map
- R = volte-face
- Start = pause/menu

Menus:
- D-pad = navigation
- A or Z = confirm
- B or Start = back
- Analog = ignored

The save crash backtrace ended in LoadTag -> GetSaveHeader. R44's native
FlashRAM file macros ended before GetLevel(), while GetSaveHeader() is later
in rt_game.c. R45 wraps GetSaveHeader itself with the native FlashRAM
SafeOpenRead/SafeRead/filelength/LoadFile/close implementation.

R43 REMOSTRT, R44 sound headroom, rumble, FlashRAM compression/CRC, and the
78,000,000-byte ROM ceiling are retained.
