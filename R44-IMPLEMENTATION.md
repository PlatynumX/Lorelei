# R44 clean Dark War milestone

- R43 registered REMOSTRT fallback retained.
- WAV64 music retained.
- Existing firing and event rumble retained.
- FX headroom added for nearby overlapping sounds.
- Native FlashRAM save container added.
- Normal startup checkpoints silenced.
- 78,000,000-byte ROM limit retained.

The first hardware milestone exposes one complete slot. Taradino's ordinary
full save image is PackBits-compressed, wrapped in an outer CRC32-protected
header, and stored in 128 KiB FlashRAM. Raw fallback is used when compression
does not help. Taradino's own inner checksum remains intact.

Hardware test: save slot zero, power off fully, reload, and verify position,
actors, doors, switches, inventory, music state, rumble, and nearby audio.
