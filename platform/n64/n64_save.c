#include "n64_save.h"

#include <string.h>
#ifdef __N64__
#include <libdragon.h>
#endif

#define SAVE_MAGIC 0x52363453u /* R64S */
#define SAVE_VERSION 1u
#define SAVE_SLOT_SIZE 448u
#define SAVE_HEADER_SIZE 24u
#define SAVE_SLOT0_OFFSET 0u
#define SAVE_SLOT1_OFFSET SAVE_SLOT_SIZE

typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t payload_size;
    uint32_t generation;
    uint32_t boot_count;
    uint32_t payload_crc;
    uint32_t header_crc;
    uint8_t payload[ROTT64_SAVE_PAYLOAD_MAX];
} save_record_t;

static bool save_ready;
static size_t save_capacity_bytes;
static save_record_t current;

static uint32_t crc32_bytes(const uint8_t *data, size_t size)
{
    uint32_t crc = 0xFFFFFFFFu;
    size_t i;
    for (i = 0; i < size; ++i) {
        unsigned bit;
        crc ^= data[i];
        for (bit = 0; bit < 8u; ++bit)
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

static uint32_t record_header_crc(const save_record_t *record)
{
    uint8_t header[20];
    memcpy(header + 0, &record->magic, 4);
    memcpy(header + 4, &record->version, 2);
    memcpy(header + 6, &record->payload_size, 2);
    memcpy(header + 8, &record->generation, 4);
    memcpy(header + 12, &record->boot_count, 4);
    memcpy(header + 16, &record->payload_crc, 4);
    return crc32_bytes(header, sizeof(header));
}

static bool record_valid(const save_record_t *record)
{
    if (record->magic != SAVE_MAGIC || record->version != SAVE_VERSION)
        return false;
    if (record->payload_size > ROTT64_SAVE_PAYLOAD_MAX)
        return false;
    if (record->header_crc != record_header_crc(record))
        return false;
    return record->payload_crc == crc32_bytes(record->payload, record->payload_size);
}

#ifdef __N64__
static void read_record(size_t offset, save_record_t *record)
{
    memset(record, 0, sizeof(*record));
    eeprom_read_bytes((uint8_t *)record, offset, sizeof(*record));
}

static void write_record(size_t offset, save_record_t *record)
{
    record->payload_crc = crc32_bytes(record->payload, record->payload_size);
    record->header_crc = record_header_crc(record);
    eeprom_write_bytes((const uint8_t *)record, offset, sizeof(*record));
}
#endif

bool n64_save_init(void)
{
#ifdef __N64__
    save_record_t a, b;
    size_t blocks = eeprom_total_blocks();
    if (blocks == 0u) {
        save_ready = false;
        return false;
    }
    save_capacity_bytes = blocks * EEPROM_BLOCK_SIZE;
    if (save_capacity_bytes < (SAVE_SLOT1_OFFSET + sizeof(save_record_t))) {
        save_ready = false;
        return false;
    }

    read_record(SAVE_SLOT0_OFFSET, &a);
    read_record(SAVE_SLOT1_OFFSET, &b);
    if (record_valid(&a) && record_valid(&b))
        current = (b.generation > a.generation) ? b : a;
    else if (record_valid(&a))
        current = a;
    else if (record_valid(&b))
        current = b;
    else {
        memset(&current, 0, sizeof(current));
        current.magic = SAVE_MAGIC;
        current.version = SAVE_VERSION;
    }

    current.boot_count++;
    current.generation++;
    write_record((current.generation & 1u) ? SAVE_SLOT1_OFFSET : SAVE_SLOT0_OFFSET, &current);
    save_ready = true;
    return true;
#else
    save_ready = false;
    return false;
#endif
}

bool n64_save_available(void) { return save_ready; }
uint32_t n64_save_boot_count(void) { return save_ready ? current.boot_count : 0u; }
size_t n64_save_capacity(void) { return save_capacity_bytes; }

bool n64_save_read_payload(void *dst, size_t size)
{
    if (!save_ready || dst == NULL || size > current.payload_size)
        return false;
    memcpy(dst, current.payload, size);
    return true;
}

bool n64_save_write_payload(const void *src, size_t size)
{
#ifdef __N64__
    if (!save_ready || src == NULL || size > ROTT64_SAVE_PAYLOAD_MAX)
        return false;
    memset(current.payload, 0, sizeof(current.payload));
    memcpy(current.payload, src, size);
    current.payload_size = (uint16_t)size;
    current.generation++;
    write_record((current.generation & 1u) ? SAVE_SLOT1_OFFSET : SAVE_SLOT0_OFFSET, &current);
    return true;
#else
    (void)src; (void)size;
    return false;
#endif
}
