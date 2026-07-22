# R42c SD_Startup return tracing fix

R42b failed during preparation because SD_Startup has more than one zero-success
return path and the tracer treated `return (0);` as unique.

R42c now:

- marks the early sound-disabled branch as S00E by its condition;
- finds the final standalone `return (0);` positionally and marks it S99;
- keeps the safe S00-S10 phase checkpoints;
- does not split multiline sound-remap expressions.

Final ROM hard limit remains 78,000,000 bytes.
