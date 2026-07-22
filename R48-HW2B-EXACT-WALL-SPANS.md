# ROTT64 R48 — HW2B exact wall spans

R47 HW2 v4 works on real N64 hardware, but the diagnostic merged each ray's
final ceilingclip/floorclip into one continuous rectangle.

ROTT can issue two separate R_DrawWallColumn calls for one screen column.
R48 captures the exact dc_yl/dc_yh range immediately before every real wall
draw and exports up to two disjoint spans per ray. The RDP draws those spans
separately rather than filling the space between them.

CPU wall drawing remains enabled for this test.

A separate known issue remains: the hardware wall overlay is currently applied
at final presentation time, after software sprites and the player weapon. Wall
spans may therefore cover foreground objects. That compositing-order issue is
the next target after exact wall-span geometry is confirmed.

Persistent Dark War music caching is preserved unchanged.

## Native N64 two-axis gamepad movement

This build keeps the R45d controller/menu ABI intact and changes only gameplay
analog movement.

- Analog X -> turn left/right through Taradino's JX path.
- Analog Y up -> forward, down -> backward through Taradino's JY path.
- Full Y deflection maps to normal keyboard walking speed.
- The existing run/auto-run state doubles analog movement.
- Desktop joystick initialization, calibration, threshold, and joypadenabled
  state are bypassed on N64.
- Gameplay PollMouseMove is suppressed to prevent double movement/turning.
- PollMouseButtons and the established digital/button/menu layer remain intact.

Locked assignments preserved:
- C-Left / C-Right: strafe left / right
- R: volte-face / 180-degree turn
- D-Right: auto-run toggle
- L: map
- C-Up: swap/toggle weapon
- C-Down: drop weapon
- D-Left: unassigned
- Menu D-Pad Up/Down: navigate
- Menu A or Z: confirm
- Menu B or Start: back

No vertical aiming is added.
