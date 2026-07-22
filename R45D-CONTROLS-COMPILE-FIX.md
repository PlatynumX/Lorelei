# R45d control compile + Taradino menu-state ABI fix

R45c's real GitHub build confirmed the save-reader patch worked:

    GetSavedMessage=rt_game.c
    GetSavedHeader=rt_game.c

`make prepare` and preflight both passed.

The cross-compile then failed because generated `rt_cfg.c` used
`SDL_SCANCODE_*` constants from the N64 controller defaults without including
`SDL.h`. Pinned Taradino's `rt_cfg.c` does not include SDL directly.

R45d prepends the N64 SDL compatibility header to generated `rt_cfg.c` whenever
it is absent, and both prepare_engine.py and the GitHub workflow contain guards
against scancode usage without the header.

R45d also fixes an ABI mismatch in the controller shim. Pinned Taradino defines
`boolean` as `unsigned char` and declares `boolean ingame` / `boolean inmenu`.
The R45 shim declared both as `extern int`, which could read four bytes from
one-byte objects. They now use `extern unsigned char`.

Everything else from R45c is retained.
