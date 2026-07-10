#include "indexed_video.h"

static uint16_t vga6_to_five_bits(uint8_t component)
{
    const uint16_t clamped = component > 63U ? 63U : component;
    return (uint16_t)(((clamped * 31U) + 31U) / 63U);
}

uint16_t rott_video_vga6_to_rgba5551(uint8_t red, uint8_t green, uint8_t blue)
{
    const uint16_t r = vga6_to_five_bits(red);
    const uint16_t g = vga6_to_five_bits(green);
    const uint16_t b = vga6_to_five_bits(blue);

    return (uint16_t)((r << 11U) | (g << 6U) | (b << 1U) | 1U);
}

bool rott_video_build_palette(
    const uint8_t *vga_palette,
    size_t palette_size,
    uint16_t *rgba5551,
    size_t color_capacity
)
{
    size_t index;

    if (vga_palette == NULL || rgba5551 == NULL
        || palette_size < ROTT_VIDEO_PALETTE_BYTES
        || color_capacity < ROTT_VIDEO_PALETTE_ENTRIES) {
        return false;
    }

    for (index = 0U; index < ROTT_VIDEO_PALETTE_ENTRIES; ++index) {
        const size_t source = index * 3U;
        rgba5551[index] = rott_video_vga6_to_rgba5551(
            vga_palette[source],
            vga_palette[source + 1U],
            vga_palette[source + 2U]);
    }

    return true;
}

bool rott_video_expand_320x200(
    const uint8_t *indexed_pixels,
    size_t indexed_stride,
    const uint16_t *rgba5551,
    uint16_t border_color,
    uint16_t *output_pixels,
    size_t output_stride,
    size_t output_height
)
{
    size_t y;

    if (indexed_pixels == NULL || rgba5551 == NULL || output_pixels == NULL
        || indexed_stride < ROTT_VIDEO_WIDTH
        || output_stride < ROTT_VIDEO_WIDTH
        || output_height < ROTT_VIDEO_OUTPUT_HEIGHT) {
        return false;
    }

    for (y = 0U; y < ROTT_VIDEO_OUTPUT_HEIGHT; ++y) {
        size_t x;
        uint16_t *destination = output_pixels + (y * output_stride);

        if (y < ROTT_VIDEO_BORDER_ROWS
            || y >= (ROTT_VIDEO_BORDER_ROWS + ROTT_VIDEO_HEIGHT)) {
            for (x = 0U; x < ROTT_VIDEO_WIDTH; ++x) {
                destination[x] = border_color;
            }
            continue;
        }

        {
            const uint8_t *source = indexed_pixels
                + ((y - ROTT_VIDEO_BORDER_ROWS) * indexed_stride);
            for (x = 0U; x < ROTT_VIDEO_WIDTH; ++x) {
                destination[x] = rgba5551[source[x]];
            }
        }
    }

    return true;
}
