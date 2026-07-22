# R43 registered DARKWAR.WAD REMOSTRT compatibility

Hardware stopped at:

    S05: before REMOSTRT lookup

The registered DARKWAR.WAD bundled with the project contains DIGISTRT but no
REMOSTRT marker. Upstream Taradino calls W_GetNumForName("remostrt")
unconditionally and enters its fatal missing-lump path.

R43 changes only the N64 registered build:

```c
#if defined(__N64__) && (SHAREWARE == 0)
remotestart = -1;
#else
remotestart = W_GetNumForName("remostrt") + 1;
#endif
```

SoundNumber() uses the special contiguous remote block only when
`remotestart >= 0`. Otherwise it falls through to the ordinary `sounds[]`
entry, which SD_Startup already remapped against DARKWAR.WAD between S03 and
S04.

Shareware behavior remains unchanged. S05-S99 diagnostics remain enabled.

Final ROM hard limit remains 78,000,000 bytes.
