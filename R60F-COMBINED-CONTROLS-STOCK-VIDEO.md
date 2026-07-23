# ROTT64 R60F — combined controls and stock Video Options

Branch: `software-controls`

## Controls

- Analog X/Y remains native gameplay movement/turning through the r49 axis bridge.
- Gameplay buttons are written directly into ROTT `buttonpoll[]` after `PollKeyboardButtons()`:
  - Z = fire
  - A = use/open
  - B = run
  - C-left/C-right = strafe left/right
  - C-up = swap weapon
  - C-down = drop weapon
  - D-up/D-down = look up/down
  - D-right = auto-run toggle
  - L = map
  - R = 180 turn
- Start remains SDL Escape through the existing platform path. It is not converted to a direct restart/title-state hack.

## Video Options

Stock menu location:

`Options -> User Options -> Video Options`

Entries:

- Resolution: 320 / 640 EXP
- Aspect: 4:3 / ORIGINAL
- Filter: SHARP / SMOOTH
- Screen Size: 80 / 85 / 90 / 95 / 100

Hidden r58 L+R hotkeys are disabled.
