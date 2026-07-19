# ROTT64 Split-Screen Comm-Bat Branch

Branch target: `feature/splitscreen-commbat`
Baseline: R28 (music + rumble + EEPROM/header test)

## Scope

This branch is intentionally isolated from the stable single-player port.
The target is local two-player competitive Comm-Bat using two N64 controllers
and a horizontal split screen. Co-op is explicitly out of scope.

## Milestones

1. Two-controller input plumbing without changing single-player behavior.
2. Two local Comm-Bat player slots driven independently by controller 1/2.
3. Dual render passes with 320x120 top/bottom viewports.
4. Per-player HUD clipping/layout.
5. Comm-Bat spawn, death, respawn and scoring flow for two local players.
6. Audio listener policy for split screen (initially nearest/local-max mix).
7. Performance tuning and optional reduced internal render resolution.

## First implementation boundary

`src/splitscreen_commbat.[ch]` defines branch-local helpers for controller-slot
mapping and horizontal viewport geometry. These helpers are deliberately engine-
agnostic so the branch can begin integrating with Taradino's Comm-Bat player
structures without destabilizing R28.

The branch does not yet claim playable split-screen. It is a clean development
fork and scaffold for the feature.
