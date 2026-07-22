# R45c Taradino 20251222 save API fix

The pinned Taradino public header declares:

```c
void GetSavedMessage(int num, char *message);
void GetSavedHeader(int num, gamestorage_t *game);
```

R45/R45b incorrectly targeted stale names `GetSaveHeader` and `LoadTag`.
R45c removes those assumptions. `prepare_engine.py` structurally finds exactly
one definition each of `GetSavedMessage` and `GetSavedHeader` in the fetched
Taradino source and wraps only those functions with the native FlashRAM read
API.

The build emits `generated/reports/r45c-save-reader-owners.txt` so GitHub
proves the actual source owner for each reader.

The existing SaveTheGame/LoadTheGame FlashRAM path, controller overhaul, R43
REMOSTRT fix, R44 audio headroom/rumble, compression/CRC, and 78,000,000-byte
ROM ceiling are retained.
