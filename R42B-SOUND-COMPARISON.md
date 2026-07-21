# R42b Shareware vs Registered SD_Startup comparison

Taradino uses the same SD_Startup function in Shareware and registered builds.
The compile-time difference here is the sound table header:

- SHAREWARE=1 includes snd_shar.h
- registered/full includes snd_reg.h

SD_Startup remaps each table's digital sound indices through the active WAD.

R41d hardware reached T24, immediately before SD_Startup(false).

The prior R42 compile failure was caused by the diagnostic tracer splitting the
multiline remap assignment, not by that assignment itself.

R42b leaves the expression intact and traces safe phases S00-S10 and S99.

Final ROM hard limit remains 78,000,000 bytes.
