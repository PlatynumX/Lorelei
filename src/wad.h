#ifndef ROTT64_WAD_H
#define ROTT64_WAD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ROTT_WAD_NAME_LENGTH 8U

typedef struct {
    uint32_t file_offset;
    uint32_t size;
    char name[ROTT_WAD_NAME_LENGTH + 1U];
    bool range_valid;
} rott_wad_lump_t;

typedef struct {
    bool file_present;
    bool valid;
    char identification[5];
    uint32_t lump_count;
    uint32_t directory_offset;
    long file_size;
    char error[96];
} rott_wad_report_t;

bool rott_wad_inspect(const char *path, rott_wad_report_t *report);
size_t rott_wad_read_window(
    const char *path,
    const rott_wad_report_t *report,
    uint32_t first_lump,
    rott_wad_lump_t *lumps,
    size_t capacity
);

bool rott_wad_find_lump(
    const char *path,
    const rott_wad_report_t *report,
    const char *name,
    uint32_t *lump_index,
    rott_wad_lump_t *lump
);

size_t rott_wad_read_lump(
    const char *path,
    const rott_wad_lump_t *lump,
    void *destination,
    size_t capacity
);

#endif
