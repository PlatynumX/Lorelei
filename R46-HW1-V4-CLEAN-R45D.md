# ROTT64 R46 HW1 v4 — clean R45d direct-RDP probe

Baseline:
`aadf56b5fbf28bb9ab88c604460df72ee6e2e701`

This revision is rebuilt directly from the preserved R45d baseline rather than
from the failed HW1 v2 commit.

The failed v2 build stopped during the repository's engine dependency preflight.
The cause was an explanatory comment in the injected N64 source containing a
legacy SDL flip identifier. The preflight scanner interpreted that comment token
as an uncovered platform dependency.

The v3 helper script correctly repaired that token, but its additional local
engine-regeneration check could not run in a plain Termux repository clone because
that temporary clone does not contain the vendor Taradino source tree used by the
CI preparation path. V3 stopped before pushing.

HW1 v4 therefore starts cleanly from R45d, installs the RDP probe without the
false dependency token, performs source/package validation locally, and leaves
the actual engine preparation and preflight to the existing GitHub Actions
environment that already supplies the engine source.

Hardware test:
For the first 180 presented frames, RDPQ draws a moving perspective test room
directly into the existing N64 framebuffer. After 180 frames, normal R45d
software presentation resumes automatically.
