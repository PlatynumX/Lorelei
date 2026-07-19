#ifndef ROTT64_N64_SAVE_H
#define ROTT64_N64_SAVE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* First persistent-storage milestone. This container intentionally stays small
   enough for standard N64 cartridge EEPROM and provides a versioned/checksummed
   payload that later engine save serialization can target. */
#define ROTT64_SAVE_PAYLOAD_MAX 384u

bool n64_save_init(void);
bool n64_save_available(void);
uint32_t n64_save_boot_count(void);
size_t n64_save_capacity(void);
bool n64_save_read_payload(void *dst, size_t size);
bool n64_save_write_payload(const void *src, size_t size);

#endif
