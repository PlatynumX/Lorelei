# R38 clean registered conversion

Baseline SHA-256: `9db7cbf0e25818e792a22518f381a90d971bf8a78117b53298d76eaef150a3a0`

Functional changes from the hardware-tested R25 baseline:

- Removed `-DSHAREWARE=1`.
- Bundled `DARKWAR.WAD`, `DARKWAR.RTL`, and `DARKWAR.RTC`.
- Switched music extraction to `--mode full`.
- Switched WAD reporting and boot diagnostics to `DARKWAR.WAD`.
- Changed ROM/package labels.

No registered product-selection, episode-menu, or startup rewrites were added.
