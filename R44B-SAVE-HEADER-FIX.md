# R44b save-menu crash fix

Hardware backtrace:

- `StringsNotEqual`
- `LoadTag`
- `GetSaveHeader`
- `CP_PreSelectedGame`

R44 exposed the in-progress RAM staging buffer as an existing save before the
FlashRAM transaction had completed. Returning to the save menu made Taradino
parse that partial buffer as a save header, producing the invalid-address
exception.

R44b separates staging state from committed state:

- Taradino's internal checksum pass may read the active staging transaction.
- Slot scanning, `GetSaveHeader`, and normal loading see only a committed image.
- A committed image must pass the outer header CRC and payload CRC before the
  slot is advertised.
- Aborted or incomplete writes remain invisible to the menu.

N64 controls relevant to menus:

- D-pad Up = Enter / confirm
- Start = Escape / back
- A = use/open during gameplay

Final ROM hard limit remains 78,000,000 bytes.
