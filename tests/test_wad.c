#include "wad.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void put_le32(uint8_t *destination, uint32_t value)
{
    destination[0] = (uint8_t)(value & 0xFFU);
    destination[1] = (uint8_t)((value >> 8U) & 0xFFU);
    destination[2] = (uint8_t)((value >> 16U) & 0xFFU);
    destination[3] = (uint8_t)((value >> 24U) & 0xFFU);
}

int main(void)
{
    const char *path = "build-host/test.iwad";
    uint8_t bytes[52] = {0};
    uint8_t payload[4] = {0};
    FILE *file;
    rott_wad_report_t report;
    rott_wad_lump_t lumps[2];
    rott_wad_lump_t found;
    uint32_t found_index = UINT32_MAX;

    memcpy(&bytes[0], "IWAD", 4U);
    put_le32(&bytes[4], 2U);
    put_le32(&bytes[8], 20U);

    bytes[12] = 1U;
    bytes[13] = 2U;
    bytes[14] = 3U;
    bytes[15] = 4U;
    bytes[16] = 9U;
    bytes[17] = 8U;
    bytes[18] = 7U;
    bytes[19] = 6U;

    put_le32(&bytes[20], 12U);
    put_le32(&bytes[24], 4U);
    memcpy(&bytes[28], "TEST", 4U);

    put_le32(&bytes[36], 16U);
    put_le32(&bytes[40], 4U);
    memcpy(&bytes[44], "SECOND", 6U);

    file = fopen(path, "wb");
    assert(file != NULL);
    assert(fwrite(bytes, 1U, sizeof(bytes), file) == sizeof(bytes));
    assert(fclose(file) == 0);

    assert(rott_wad_inspect(path, &report));
    assert(report.valid);
    assert(report.lump_count == 2U);
    assert(report.directory_offset == 20U);
    assert(rott_wad_read_window(path, &report, 0U, lumps, 2U) == 2U);
    assert(strcmp(lumps[0].name, "TEST") == 0);
    assert(lumps[0].file_offset == 12U);
    assert(lumps[0].size == 4U);
    assert(lumps[0].range_valid);

    assert(rott_wad_find_lump(path, &report, "second", &found_index, &found));
    assert(found_index == 1U);
    assert(strcmp(found.name, "SECOND") == 0);
    assert(rott_wad_read_lump(path, &found, payload, sizeof(payload)) == sizeof(payload));
    assert(payload[0] == 9U && payload[1] == 8U && payload[2] == 7U && payload[3] == 6U);
    assert(!rott_wad_find_lump(path, &report, "MISSING", NULL, &found));

    puts("WAD parser, lookup, and lump read host tests passed");
    return 0;
}
