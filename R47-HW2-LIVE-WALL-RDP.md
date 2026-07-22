# ROTT64 R47 HW2 — live Taradino wall spans on the N64 RDP

Retry v2 fixes the pre-push function locator so C functions with the opening brace on the following line are recognized correctly.

Parent: the R46 HW1 v4 ROM confirmed on real hardware.

HW1 proved the RDPQ framebuffer path. R47 connects that path to Taradino's
actual renderer.

Taradino still performs its normal ray casting and DrawWallPost calculations.
At the end of DrawWalls, R47 exports each visible column's ceiling/floor clip
span. The N64 presentation layer recognizes fresh gameplay-only wall data and
uses RDP fill rectangles to overlay those exact spans in diagnostic colors.

Intro, title and menus should remain normal because they do not generate a new
DrawWalls sequence.

The diagnostic runs for the first 900 live world frames, then stops and returns
to normal software presentation for an automatic A/B comparison.

R47 deliberately retains R_DrawWallColumn as a fallback. After this build proves
the geometry and screen mapping are correct on hardware, the next revision will
remove the matching CPU wall rasterization and start moving wall pixels/textures
to hardware for real performance gain.
