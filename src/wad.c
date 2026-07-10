#include "wad.h"

#include <ctype.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

#define ROTT_WAD_HEADER_SIZE 12U
#define ROTT_WAD_DIRECTORY_ENTRY_SIZE 16U
#define ROTT_WAD_MAX_LUMPS 200000U

static uint32_t read_le32(const uint8_t *bytes)
{
    return ((uint32_t)bytes[0])
        | ((uint32_t)bytes[1] << 8U)
        | ((uint32_t)bytes[2] << 16U)
        | ((uint32_t)bytes[3] << 24U);
}

static void set_error(rott_wad_report_t *report, const char *message)
{
    report->valid = false;
    (void)snprintf(report->error, sizeof(report->error), "%s", message);
}

bool rott_wad_inspect(const char *path, rott_wad_report_t *report)
{
    uint8_t header[ROTT_WAD_HEADER_SIZE];
    FILE *file;
    uint64_t directory_end;

    if (path == NULL || report == NULL) {
        return false;
    }

    memset(report, 0, sizeof(*report));
    file = fopen(path, "rb");
    if (file == NULL) {
        set_error(report, "HUNTBGIN.WAD is missing");
        return false;
    }

    report->file_present = true;

    if (fseek(file, 0L, SEEK_END) != 0) {
        set_error(report, "Could not determine WAD size");
        (void)fclose(file);
        return false;
    }

    report->file_size = ftell(file);
    if (report->file_size < (long)ROTT_WAD_HEADER_SIZE) {
        set_error(report, "WAD is smaller than its header");
        (void)fclose(file);
        return false;
    }

    if (fseek(file, 0L, SEEK_SET) != 0
        || fread(header, 1U, sizeof(header), file) != sizeof(header)) {
        set_error(report, "Could not read WAD header");
        (void)fclose(file);
        return false;
    }

    memcpy(report->identification, header, 4U);
    report->identification[4] = '\0';
    report->lump_count = read_le32(&header[4]);
    report->directory_offset = read_le32(&header[8]);

    if (memcmp(report->identification, "IWAD", 4U) != 0) {
        set_error(report, "Unexpected WAD signature (expected IWAD)");
        (void)fclose(file);
        return false;
    }

    if (report->lump_count == 0U || report->lump_count > ROTT_WAD_MAX_LUMPS) {
        set_error(report, "WAD lump count is not credible");
        (void)fclose(file);
        return false;
    }

    directory_end = (uint64_t)report->directory_offset
        + ((uint64_t)report->lump_count * (uint64_t)ROTT_WAD_DIRECTORY_ENTRY_SIZE);

    if (report->directory_offset < ROTT_WAD_HEADER_SIZE
        || directory_end > (uint64_t)report->file_size) {
        set_error(report, "WAD directory lies outside the file");
        (void)fclose(file);
        return false;
    }

    report->valid = true;
    report->error[0] = '\0';
    (void)fclose(file);
    return true;
}

size_t rott_wad_read_window(
    const char *path,
    const rott_wad_report_t *report,
    uint32_t first_lump,
    rott_wad_lump_t *lumps,
    size_t capacity
)
{
    FILE *file;
    uint64_t seek_offset;
    size_t read_count = 0U;

    if (path == NULL || report == NULL || lumps == NULL || capacity == 0U
        || !report->valid || first_lump >= report->lump_count) {
        return 0U;
    }

    seek_offset = (uint64_t)report->directory_offset
        + ((uint64_t)first_lump * (uint64_t)ROTT_WAD_DIRECTORY_ENTRY_SIZE);

    if (seek_offset > (uint64_t)LONG_MAX) {
        return 0U;
    }

    file = fopen(path, "rb");
    if (file == NULL) {
        return 0U;
    }

    if (fseek(file, (long)seek_offset, SEEK_SET) != 0) {
        (void)fclose(file);
        return 0U;
    }

    while (read_count < capacity
        && (first_lump + (uint32_t)read_count) < report->lump_count) {
        uint8_t entry[ROTT_WAD_DIRECTORY_ENTRY_SIZE];
        rott_wad_lump_t *lump = &lumps[read_count];
        uint64_t lump_end;
        size_t index;

        if (fread(entry, 1U, sizeof(entry), file) != sizeof(entry)) {
            break;
        }

        lump->file_offset = read_le32(&entry[0]);
        lump->size = read_le32(&entry[4]);

        for (index = 0U; index < ROTT_WAD_NAME_LENGTH; ++index) {
            const unsigned char character = entry[8U + index];
            lump->name[index] = (character == 0U)
                ? '\0'
                : (isprint((int)character) ? (char)character : '.');
        }
        lump->name[ROTT_WAD_NAME_LENGTH] = '\0';

        lump_end = (uint64_t)lump->file_offset + (uint64_t)lump->size;
        lump->range_valid = lump_end <= (uint64_t)report->file_size;
        ++read_count;
    }

    (void)fclose(file);
    return read_count;
}

static bool lump_name_matches(const char *left, const char *right)
{
    size_t index;

    if (left == NULL || right == NULL) {
        return false;
    }

    for (index = 0U; index < ROTT_WAD_NAME_LENGTH; ++index) {
        const unsigned char left_character = (unsigned char)left[index];
        const unsigned char right_character = (unsigned char)right[index];

        if (toupper((int)left_character) != toupper((int)right_character)) {
            return false;
        }
        if (left_character == 0U || right_character == 0U) {
            return left_character == right_character;
        }
    }

    return right[ROTT_WAD_NAME_LENGTH] == '\0';
}

bool rott_wad_find_lump(
    const char *path,
    const rott_wad_report_t *report,
    const char *name,
    uint32_t *lump_index,
    rott_wad_lump_t *lump
)
{
    uint32_t index;

    if (path == NULL || report == NULL || name == NULL || lump == NULL
        || !report->valid || name[0] == '\0') {
        return false;
    }

    for (index = 0U; index < report->lump_count; ++index) {
        rott_wad_lump_t candidate;
        if (rott_wad_read_window(path, report, index, &candidate, 1U) != 1U) {
            return false;
        }
        if (lump_name_matches(candidate.name, name)) {
            *lump = candidate;
            if (lump_index != NULL) {
                *lump_index = index;
            }
            return true;
        }
    }

    return false;
}

size_t rott_wad_read_lump(
    const char *path,
    const rott_wad_lump_t *lump,
    void *destination,
    size_t capacity
)
{
    FILE *file;
    size_t requested;
    size_t result;

    if (path == NULL || lump == NULL || destination == NULL
        || !lump->range_valid || capacity == 0U) {
        return 0U;
    }

    requested = lump->size < capacity ? (size_t)lump->size : capacity;
    if (requested == 0U || lump->file_offset > (uint32_t)LONG_MAX) {
        return 0U;
    }

    file = fopen(path, "rb");
    if (file == NULL) {
        return 0U;
    }

    if (fseek(file, (long)lump->file_offset, SEEK_SET) != 0) {
        (void)fclose(file);
        return 0U;
    }

    result = fread(destination, 1U, requested, file);
    (void)fclose(file);
    return result;
}
