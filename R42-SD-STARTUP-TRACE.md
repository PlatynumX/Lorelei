# R42 SD_Startup internal trace

R41d hardware result: T24 was the final visible checkpoint.

T24 is immediately before SD_Startup(false), while T25 appears only after
SD_Startup returns. Therefore the remaining failure is inside SD_Startup.

R42 dynamically locates the actual SD_Startup definition in the fetched
Taradino source and inserts:

- S00 at function entry
- S01... before each standalone function-call statement
- S99 immediately before leaving SD_Startup

The build diagnostics include r42-sd-startup-trace-map.txt mapping each
S-number to the actual statement from the pinned source.

Report the last S-number and description visible before blackness.

Final ROM hard limit remains 78,000,000 bytes.
