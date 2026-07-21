# R41b hardware startup trace

R40 passes all six N64 platform and Dark War data checks, then black-screens
after entering Taradino.

R41b removes the nonexistent GetPrefDir instrumentation anchor that prevented
R41 from preparing the real pinned Taradino source.

Visible checkpoints now run from T07 through T29 around the actual registered
startup calls. Record the final T-number and description visible before
blackness.

This diagnostic revision does not alter registered product selection, episode
handling, map loading, or other game behavior.

The final ROM remains subject to the 78,000,000-byte hard limit.
